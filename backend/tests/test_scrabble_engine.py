from app.games.registry import get_game, list_games
from app.games.scrabble.ai import choose_action
from app.games.scrabble.dictionary import is_word
from app.games.scrabble.engine import ScrabbleEngine


def _players(count=2, ai=False):
    seats = [{"id": "p1", "nickname": "Ada", "is_ai": False}]
    for index in range(1, count):
        seats.append(
            {
                "id": f"p{index + 1}",
                "nickname": f"Bot {index}",
                "is_ai": ai or index > 0,
            }
        )
    return seats


def _tile(tile_id, letter, blank=False):
    return {"id": tile_id, "l": "" if blank else letter, "b": blank}


def _set_rack(state, player_id, tiles):
    state["racks"][player_id] = list(tiles)
    if not state["bag"]:
        state["bag"] = [_tile("bag-keep", "E")]


def test_scrabble_is_listed():
    ids = {game["id"] for game in list_games()}
    assert "scrabble" in ids
    assert get_game("scrabble").game_type == "scrabble"


def test_opening_word_covers_center_and_scores_double():
    engine = ScrabbleEngine()
    state = engine.create_initial_state(_players(), {})
    _set_rack(state, "p1", [_tile("a", "H"), _tile("b", "I"), _tile("keep", "E")])
    state, events = engine.apply_action(
        state,
        {
            "type": "play",
            "placements": [
                {"row": 7, "col": 7, "tile_id": "a", "letter": "H"},
                {"row": 7, "col": 8, "tile_id": "b", "letter": "I"},
            ],
        },
        {"id": "p1"},
    )
    assert state["board"][7][7]["l"] == "H"
    assert state["players"][0]["score"] == 10
    assert events[0]["score"] == 10
    assert state["current_actor_id"] == "p2"


def test_first_word_must_cover_center():
    engine = ScrabbleEngine()
    state = engine.create_initial_state(_players(), {})
    _set_rack(state, "p1", [_tile("a", "H"), _tile("b", "I"), _tile("keep", "E")])
    try:
        engine.apply_action(
            state,
            {
                "type": "play",
                "placements": [
                    {"row": 0, "col": 0, "tile_id": "a"},
                    {"row": 0, "col": 1, "tile_id": "b"},
                ],
            },
            {"id": "p1"},
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "center" in str(exc).lower()


def test_unknown_word_rejected():
    assert is_word("HELLO")
    engine = ScrabbleEngine()
    state = engine.create_initial_state(_players(), {})
    _set_rack(state, "p1", [_tile("a", "Z"), _tile("b", "Z")])
    try:
        engine.apply_action(
            state,
            {
                "type": "play",
                "placements": [
                    {"row": 7, "col": 7, "tile_id": "a"},
                    {"row": 7, "col": 8, "tile_id": "b"},
                ],
            },
            {"id": "p1"},
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "dictionary" in str(exc).lower()


def test_cross_word_adds_score():
    engine = ScrabbleEngine()
    state = engine.create_initial_state(_players(), {})
    _set_rack(state, "p1", [_tile("a", "A"), _tile("b", "T"), _tile("keep", "E")])
    state, _ = engine.apply_action(
        state,
        {
            "type": "play",
            "placements": [
                {"row": 7, "col": 7, "tile_id": "a"},
                {"row": 7, "col": 8, "tile_id": "b"},
            ],
        },
        {"id": "p1"},
    )
    _set_rack(state, "p2", [_tile("c", "C"), _tile("keep2", "E")])
    state, events = engine.apply_action(
        state,
        {"type": "play", "placements": [{"row": 7, "col": 6, "tile_id": "c"}]},
        {"id": "p2"},
    )
    assert events[0]["words"][0]["word"] == "CAT"
    assert state["players"][1]["score"] == 5


def test_bingo_adds_fifty():
    engine = ScrabbleEngine()
    state = engine.create_initial_state(_players(), {})
    letters = list("READING")
    state["racks"]["p1"] = [_tile(str(i), letter) for i, letter in enumerate(letters)]
    state["bag"] = []
    placements = [
        {"row": 7, "col": 4 + index, "tile_id": str(index)}
        for index in range(7)
    ]
    state, events = engine.apply_action(
        state, {"type": "play", "placements": placements}, {"id": "p1"}
    )
    assert events[0]["score"] >= 50
    assert state["last_move"]["bingo"] is True
    assert state["phase"] == "game_over"
    assert state["win_reason"] == "out"
    assert state["winner"] == "p1"


def test_exchange_needs_seven_in_the_bag():
    engine = ScrabbleEngine()
    state = engine.create_initial_state(_players(), {})
    state["racks"]["p1"] = [_tile("a", "Q")]
    state["bag"] = [_tile(f"b{i}", "A") for i in range(6)]
    try:
        engine.apply_action(state, {"type": "exchange", "tile_ids": ["a"]}, {"id": "p1"})
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "bag" in str(exc).lower()

    state["bag"].append(_tile("extra", "E"))
    state, events = engine.apply_action(
        state, {"type": "exchange", "tile_ids": ["a"]}, {"id": "p1"}
    )
    assert events[0]["type"] == "exchange"
    assert len(state["racks"]["p1"]) == 7
    assert state["current_actor_id"] == "p2"


def test_six_passes_end_the_game():
    engine = ScrabbleEngine()
    state = engine.create_initial_state(_players(), {})
    for _ in range(6):
        actor = state["current_actor_id"]
        state, _ = engine.apply_action(state, {"type": "pass"}, {"id": actor})
    assert state["phase"] == "game_over"
    assert state["win_reason"] == "passes"


def test_public_state_hides_the_other_rack():
    engine = ScrabbleEngine()
    state = engine.create_initial_state(_players(), {})
    public = engine.get_public_state(state, {"id": "p1"})
    assert "racks" not in public
    assert "bag" not in public
    assert len(public["rack"]) == 7
    assert public["players"][1]["rack_count"] == 7
    hidden = {tile["id"] for tile in state["racks"]["p2"]}
    shown = {tile["id"] for tile in public["rack"]}
    assert hidden.isdisjoint(shown)


def test_generator_finds_a_hook():
    from app.games.scrabble.moves import generate_moves

    engine = ScrabbleEngine()
    state = engine.create_initial_state(_players(), {})
    state["board"][7][7] = {"l": "A", "b": False}
    state["board"][7][8] = {"l": "T", "b": False}
    moves = generate_moves(state["board"], [_tile("c", "C")])
    cats = [move for move in moves if any(word["word"] == "CAT" for word in move["words"])]
    assert cats
    assert cats[0]["score"] == 5


def test_ai_opening_is_legal():
    engine = ScrabbleEngine()
    players = _players(ai=True)
    players[0]["is_ai"] = True
    state = engine.create_initial_state(players, {"ai_difficulty": "hard"})
    state["racks"]["p1"] = [
        _tile(letter, letter) for letter in "HELLO"
    ] + [_tile("x", "X"), _tile("q", "Q")]
    state["bag"] = []
    state["current_actor_id"] = "p1"
    action = choose_action(state, "hard")
    assert action["type"] == "play"
    state, events = engine.apply_action(state, action, {"id": "p1"})
    assert events[0]["score"] > 0
    assert state["board"][7][7] is not None


def test_not_your_turn():
    engine = ScrabbleEngine()
    state = engine.create_initial_state(_players(), {})
    try:
        engine.apply_action(state, {"type": "pass"}, {"id": "p2"})
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "turn" in str(exc).lower()
