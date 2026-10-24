import json
from datetime import datetime, timedelta, timezone

from app.games.registry import get_game, list_games
from app.games.scribble.doodles import DOODLES
from app.games.scribble.engine import ScribbleEngine, normalize_guess
from app.games.scribble.words import WORDS


def _players(count: int = 3) -> list[dict]:
    return [
        {"id": f"p{i}", "nickname": f"Player {i}", "is_ai": i == count - 1}
        for i in range(count)
    ]


def _engine() -> ScribbleEngine:
    return ScribbleEngine()


def test_registered():
    ids = {game["id"] for game in list_games()}
    assert "scribble" in ids
    assert get_game("scribble").game_type == "scribble"


def test_every_word_has_a_doodle():
    missing = [word["text"] for word in WORDS if word["text"] not in DOODLES]
    assert missing == []


def test_lobby_needs_two_players():
    engine = _engine()
    assert engine.validate_lobby(_players(1), {}) == "Need at least 2 players"
    assert engine.validate_lobby(_players(2), {}) is None
    human = [{"id": "p0", "nickname": "Player 0", "is_ai": False}]
    assert engine.validate_lobby(human, {"solo_practice": True}) is None


def test_guesser_cannot_see_word_choices():
    engine = _engine()
    state = engine.create_initial_state(_players(), {})
    drawer_id = state["drawer_id"]
    guesser_id = next(player["id"] for player in state["players"] if player["id"] != drawer_id)
    public = engine.get_public_state(state, {"id": guesser_id})
    blob = json.dumps(public)
    assert public["word"] is None
    assert public["word_options"] is None
    assert public["phase"] == "choosing"
    for option in state["word_options"]:
        assert option["text"] not in blob


def test_draw_guess_and_hide_word_from_other_guesser():
    engine = _engine()
    state = engine.create_initial_state(_players(), {"draw_seconds": 60})
    drawer_id = state["drawer_id"]
    others = [player["id"] for player in state["players"] if player["id"] != drawer_id]
    state, _ = engine.apply_action(state, {"type": "choose_word", "index": 0}, {"id": drawer_id})
    word = state["word"]
    assert state["phase"] == "drawing"
    assert word

    state, _ = engine.apply_action(
        state,
        {"type": "stroke", "color": "#1c1917", "size": 16, "points": [[10, 10], [40, 40]]},
        {"id": drawer_id},
    )
    assert len(state["strokes"]) == 1

    try:
        engine.apply_action(
            state,
            {"type": "stroke", "color": "#1c1917", "size": 16, "points": [[1, 1], [2, 2]]},
            {"id": others[0]},
        )
        assert False, "guesser should not draw"
    except ValueError as exc:
        assert "drawer" in str(exc).lower()

    state, _ = engine.apply_action(state, {"type": "guess", "text": word.upper()}, {"id": others[0]})
    guesser = next(player for player in state["players"] if player["id"] == others[0])
    assert guesser["score"] > 0
    hidden = engine.get_public_state(state, {"id": others[1]})
    assert hidden["word"] is None
    assert word not in json.dumps(hidden["messages"])
    revealed = engine.get_public_state(state, {"id": others[0]})
    assert revealed["word"] == word
    assert revealed["viewer_has_guessed"] is True


def test_close_guess_and_exact_match_ignores_spaces():
    assert normalize_guess(" Ice-Cream ") == "icecream"
    engine = _engine()
    state = engine.create_initial_state(_players(2), {})
    drawer_id = state["drawer_id"]
    guesser_id = next(player["id"] for player in state["players"] if player["id"] != drawer_id)
    state["word_options"] = [{"text": "castle", "difficulty": "hard"}]
    state, _ = engine.apply_action(state, {"type": "choose_word", "index": 0}, {"id": drawer_id})
    state, _ = engine.apply_action(state, {"type": "guess", "text": "castke"}, {"id": guesser_id})
    assert state["messages"][-1]["kind"] == "close"
    assert state["phase"] == "drawing"
    state, _ = engine.apply_action(state, {"type": "guess", "text": "castle"}, {"id": guesser_id})
    assert state["phase"] == "reveal"


def test_timer_picks_a_word_then_reveals():
    engine = _engine()
    state = engine.create_initial_state(_players(2), {"draw_seconds": 30, "reveal_seconds": 3})
    past = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    state["phase_ends_at"] = past
    state["ai_choose_at"] = None
    state, events = engine.tick(state)
    assert state["phase"] == "drawing"
    assert events[0]["type"] == "drawing_started"
    state["phase_ends_at"] = past
    state["drawing_started_at"] = (datetime.now(timezone.utc) - timedelta(seconds=40)).isoformat()
    state, events = engine.tick(state)
    assert state["phase"] == "reveal"
    assert any(event["type"] == "reveal" for event in events)
    assert state["word"]
    public = engine.get_public_state(state, {"id": state["players"][0]["id"]})
    assert public["word"] == state["word"]


def test_ai_draws_a_stroke():
    engine = _engine()
    players = _players(2)
    players[0]["is_ai"] = True
    players[1]["is_ai"] = False
    state = engine.create_initial_state(players, {})
    state["drawer_id"] = players[0]["id"]
    state["phase"] = "drawing"
    state["word"] = "sun"
    state["ai_strokes"] = [
        {"color": "#eab308", "size": 16, "points": [[100, 100], [120, 140], [160, 100]]}
    ]
    state["ai_stroke_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    state["phase_ends_at"] = (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()
    state["drawing_started_at"] = datetime.now(timezone.utc).isoformat()
    state["ai_guesses"] = []
    state, _ = engine.tick(state)
    assert len(state["strokes"]) == 1
    assert state["ai_strokes"] == []


def test_rounds_end_with_a_winner():
    engine = _engine()
    state = engine.create_initial_state(_players(2), {"rounds": 1})
    state["turn_index"] = state["total_turns"]
    state["phase"] = "reveal"
    state["phase_ends_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    state["players"][0]["score"] = 50
    state["players"][1]["score"] = 10
    state, _ = engine.tick(state)
    assert state["phase"] == "finished"
    assert engine.check_winner(state) == state["players"][0]["id"]


def test_tick_interval():
    assert _engine().tick_interval_ms() == 1000
