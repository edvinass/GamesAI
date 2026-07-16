import copy

import pytest

from app.games.spyfall.engine import SpyfallEngine


def make_players(count: int = 4) -> list[dict]:
    return [
        {
            "id": f"p{i}",
            "nickname": f"Player {i}",
            "team": None,
            "role": None,
            "is_ai": False,
            "is_connected": True,
        }
        for i in range(count)
    ]


@pytest.fixture
def engine() -> SpyfallEngine:
    return SpyfallEngine()


@pytest.fixture
def state(engine: SpyfallEngine) -> dict:
    players = make_players(4)
    return engine.create_initial_state(players, {"round_timer_sec": 0})


def test_lobby_validation(engine: SpyfallEngine) -> None:
    assert engine.validate_lobby(make_players(2), {}) is not None
    assert engine.validate_lobby(make_players(3), {}) is None
    assert engine.validate_lobby(make_players(9), {}) is not None
    assert engine.validate_lobby(make_players(1), {"solo_practice": True}) is None
    assert engine.validate_lobby(make_players(2), {"solo_practice": True}) is not None


def test_spy_secrecy_in_public_state(engine: SpyfallEngine, state: dict) -> None:
    spy_id = state["spy_id"]
    resident_id = next(p["id"] for p in state["players"] if p["id"] != spy_id)
    spy_player = next(p for p in state["players"] if p["id"] == spy_id)
    resident_player = next(p for p in state["players"] if p["id"] == resident_id)

    spy_view = engine.get_public_state(state, spy_player)
    assert spy_view["is_spy"] is True
    assert spy_view["viewer_location"] is None
    assert spy_view["location_names"] is not None

    resident_view = engine.get_public_state(state, resident_player)
    assert resident_view["is_spy"] is False
    assert resident_view["viewer_location"] == state["location"]["name"]
    assert resident_view["viewer_role"] is not None
    assert resident_view["location_names"] == spy_view["location_names"]


def test_qa_turn_advance(engine: SpyfallEngine, state: dict) -> None:
    asker_id = state["turn_order"][state["current_turn_index"]]
    target_id = next(p["id"] for p in state["players"] if p["id"] != asker_id)
    asker = next(p for p in state["players"] if p["id"] == asker_id)
    target = next(p for p in state["players"] if p["id"] == target_id)

    state, events = engine.apply_action(
        state,
        {"type": "ask_question", "target_player_id": target_id, "question": "How long have you worked here?"},
        asker,
    )
    assert state["pending_question"] is not None
    assert events[0]["type"] == "question_asked"

    actor = engine.get_current_actor(state)
    assert actor["id"] == target_id

    prev_index = state["current_turn_index"]
    state, events = engine.apply_action(
        state,
        {"type": "answer_question", "answer": "About five years."},
        target,
    )
    assert state["pending_question"] is None
    assert len(state["question_log"]) == 1
    assert state["current_turn_index"] == (prev_index + 1) % len(state["players"])


def test_spy_guess_correct(engine: SpyfallEngine, state: dict) -> None:
    spy_id = state["spy_id"]
    spy = next(p for p in state["players"] if p["id"] == spy_id)
    location_name = state["location"]["name"]

    state, events = engine.apply_action(
        state,
        {"type": "spy_guess_location", "location_name": location_name},
        spy,
    )
    assert state["winner"] == "spy"
    assert state["win_reason"] == "location_guessed"
    assert events[0]["type"] == "game_over"


def test_spy_guess_wrong(engine: SpyfallEngine, state: dict) -> None:
    spy_id = state["spy_id"]
    spy = next(p for p in state["players"] if p["id"] == spy_id)
    wrong = next(n for n in state["all_location_names"] if n != state["location"]["name"])

    state, events = engine.apply_action(
        state,
        {"type": "spy_guess_location", "location_name": wrong},
        spy,
    )
    assert state["winner"] == "residents"
    assert state["win_reason"] == "wrong_location_guess"


def test_vote_identifies_spy(engine: SpyfallEngine, state: dict) -> None:
    spy_id = state["spy_id"]
    resident = next(p for p in state["players"] if p["id"] != spy_id)

    state["phase"] = "voting"
    state["votes"] = {}
    for player in state["players"]:
        state, _ = engine.apply_action(
            state,
            {"type": "cast_vote", "vote_for_player_id": spy_id},
            player,
        )
    assert state["winner"] == "residents"
    assert state["win_reason"] == "spy_voted_out"


def test_vote_fails_spy_wins(engine: SpyfallEngine, state: dict) -> None:
    spy_id = state["spy_id"]
    innocent_id = next(p["id"] for p in state["players"] if p["id"] != spy_id)

    state["phase"] = "voting"
    state["votes"] = {}
    for player in state["players"]:
        state, _ = engine.apply_action(
            state,
            {"type": "cast_vote", "vote_for_player_id": innocent_id},
            player,
        )
    assert state["winner"] == "spy"
    assert state["win_reason"] == "vote_failed"


def test_get_current_actor_phases(engine: SpyfallEngine, state: dict) -> None:
    turn_id = state["turn_order"][state["current_turn_index"]]
    assert engine.get_current_actor(state)["id"] == turn_id

    target_id = next(p["id"] for p in state["players"] if p["id"] != turn_id)
    asker = next(p for p in state["players"] if p["id"] == turn_id)
    state, _ = engine.apply_action(
        state,
        {"type": "ask_question", "target_player_id": target_id, "question": "Ready?"},
        asker,
    )
    assert engine.get_current_actor(state)["id"] == target_id

    state["phase"] = "voting"
    state["votes"] = {}
    state["pending_question"] = None
    assert engine.get_current_actor(state)["id"] == state["players"][0]["id"]

    state["votes"][state["players"][0]["id"]] = spy_id if (spy_id := state["spy_id"]) else None
    assert engine.get_current_actor(state)["id"] == state["players"][1]["id"]


def test_same_room_spoken_qa(engine: SpyfallEngine) -> None:
    players = make_players(4)
    state = engine.create_initial_state(players, {"round_timer_sec": 0, "same_room": True})
    assert state["settings"]["same_room"] is True

    asker_id = state["turn_order"][state["current_turn_index"]]
    target_id = next(p["id"] for p in state["players"] if p["id"] != asker_id)
    asker = next(p for p in state["players"] if p["id"] == asker_id)
    target = next(p for p in state["players"] if p["id"] == target_id)

    state, _ = engine.apply_action(
        state,
        {"type": "ask_question", "target_player_id": target_id},
        asker,
    )
    assert state["pending_question"]["spoken"] is True
    assert state["pending_question"]["question"] == SpyfallEngine.SPOKEN_PLACEHOLDER

    prev_index = state["current_turn_index"]
    state, _ = engine.apply_action(state, {"type": "answer_question"}, target)
    assert state["pending_question"] is None
    assert state["question_log"][-1]["spoken"] is True
    assert state["question_log"][-1]["answer"] == SpyfallEngine.SPOKEN_PLACEHOLDER
    assert state["current_turn_index"] == (prev_index + 1) % len(state["players"])

    view = engine.get_public_state(state, asker)
    assert view["same_room"] is True


def test_same_room_disables_solo_practice(engine: SpyfallEngine) -> None:
    settings = engine.validate_settings({"same_room": True, "solo_practice": True})
    assert settings["same_room"] is True
    assert settings["solo_practice"] is False


def test_same_room_rejects_ai_players(engine: SpyfallEngine) -> None:
    players = make_players(3)
    players[2]["is_ai"] = True
    assert engine.validate_lobby(players, {"same_room": True}) is not None
    assert engine.validate_lobby(make_players(3), {"same_room": True}) is None


def test_game_over_reveals_spy(engine: SpyfallEngine, state: dict) -> None:
    spy_id = state["spy_id"]
    spy = next(p for p in state["players"] if p["id"] == spy_id)
    state, _ = engine.apply_action(
        state,
        {"type": "spy_guess_location", "location_name": state["location"]["name"]},
        spy,
    )
    view = engine.get_public_state(state, state["players"][0])
    assert view["revealed_spy_id"] == spy_id
    assert view["revealed_location"] == state["location"]["name"]
    assert view["revealed_assignments"] is not None
