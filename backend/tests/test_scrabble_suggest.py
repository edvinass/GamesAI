from app.games.scrabble.engine import ScrabbleEngine
from app.games.scrabble.suggest import scrabble_position_key, suggest_moves


def _tile(tile_id, letter, blank=False):
    return {"id": tile_id, "l": "" if blank else letter, "b": blank}


def _state():
    players = [
        {"id": "p1", "nickname": "Ada", "is_ai": False},
        {"id": "p2", "nickname": "Bot", "is_ai": True},
    ]
    return ScrabbleEngine().create_initial_state(players, {})


def test_suggestions_are_sorted_and_playable():
    engine = ScrabbleEngine()
    state = _state()
    state["racks"]["p1"] = [_tile(f"r{i}", letter) for i, letter in enumerate("CATSDOG")]
    moves = suggest_moves(state, "p1")
    assert 1 <= len(moves) <= 5
    scores = [move["score"] for move in moves]
    assert scores == sorted(scores, reverse=True)

    best = moves[0]
    rack_ids = {tile["id"] for tile in state["racks"]["p1"]}
    assert all(item["tile_id"] in rack_ids for item in best["placements"])
    action = {"type": "play", "placements": best["placements"]}
    after, events = engine.apply_action(state, action, {"id": "p1"})
    assert events[0]["score"] == best["score"]
    assert after["players"][0]["score"] == best["score"]


def test_blank_suggestion_carries_letter():
    engine = ScrabbleEngine()
    state = _state()
    state["racks"]["p1"] = [_tile("q", "Q"), _tile("b", "", blank=True)]
    moves = suggest_moves(state, "p1")
    assert moves, "QI with a blank I should be found"
    best = moves[0]
    blanks = [item for item in best["placements"] if item["blank"]]
    assert blanks and all(len(item["letter"]) == 1 for item in blanks)
    engine.apply_action(state, {"type": "play", "placements": best["placements"]}, {"id": "p1"})


def test_suggestions_only_use_own_rack():
    state = _state()
    state["racks"]["p1"] = [_tile("x1", "Q"), _tile("x2", "Q")]
    state["racks"]["p2"] = [_tile(f"o{i}", letter) for i, letter in enumerate("CATSDOG")]
    assert suggest_moves(state, "p1") == []
    assert suggest_moves(state, "nobody") == []


def test_position_key_tracks_turn_and_rack():
    state = _state()
    key = scrabble_position_key(state, "p1")
    state["turn_index"] += 1
    assert scrabble_position_key(state, "p1") != key


def test_suggestions_list_distinct_words():
    state = _state()
    state["racks"]["p1"] = [_tile(f"r{i}", letter) for i, letter in enumerate("EDIIYOA")]
    moves = suggest_moves(state, "p1")
    keys = [tuple(sorted(word["word"] for word in move["words"])) for move in moves]
    assert len(keys) == len(set(keys))
