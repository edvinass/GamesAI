import pytest

from app.games.codenames.engine import CodenamesEngine
from app.games.codenames.suggest import (
    active_suggestion_kind,
    build_suggestion,
    codenames_position_key,
)


def _state() -> dict:
    engine = CodenamesEngine()
    return engine.create_initial_state(
        [
            {"id": "s1", "name": "Spy", "team": "red", "role": "spymaster", "is_ai": False},
            {"id": "o1", "name": "Op", "team": "red", "role": "operative", "is_ai": False},
            {"id": "s2", "name": "Spy2", "team": "blue", "role": "spymaster", "is_ai": True},
            {"id": "o2", "name": "Op2", "team": "blue", "role": "operative", "is_ai": True},
        ],
        {},
    )


def test_position_key_changes_when_the_decision_changes() -> None:
    state = _state()
    original = codenames_position_key(state)
    state["phase"] = "guess"
    state["current_clue"] = {"word": "OCEAN", "number": 2}
    state["guesses_remaining"] = 3
    assert codenames_position_key(state) != original
    state["cards"][0]["revealed"] = True
    revealed = codenames_position_key(state)
    assert revealed != original
    assert revealed.endswith("|0") or ",0" in revealed.split("|")[-1]


def test_only_the_current_human_role_is_eligible() -> None:
    state = _state()
    assert state["phase"] == "clue"
    team = state["current_team"]
    assert active_suggestion_kind(state, team, "spymaster") == "clue"
    assert active_suggestion_kind(state, team, "operative") is None
    assert active_suggestion_kind(state, "blue" if team == "red" else "red", "spymaster") is None

    state["phase"] = "guess"
    state["current_clue"] = {"word": "OCEAN", "number": 1}
    assert active_suggestion_kind(state, team, "operative") == "guess"
    assert active_suggestion_kind(state, team, "spymaster") is None

    state["winner"] = team
    assert active_suggestion_kind(state, team, "operative") is None


@pytest.mark.asyncio
async def test_build_suggestion_uses_spymaster_on_clue_turn(monkeypatch) -> None:
    state = _state()
    team = state["current_team"]

    async def fake_clue(snapshot, clue_team):
        assert snapshot is state
        assert clue_team == team
        return "OCEAN", 2, ["SHIP", "WAVE"]

    async def fake_guesses(*_args):
        raise AssertionError("operative model should not run on a clue turn")

    monkeypatch.setattr("app.games.codenames.suggest.ai_spymaster_clue", fake_clue)
    monkeypatch.setattr("app.games.codenames.suggest.ai_operative_guesses", fake_guesses)

    suggestion = await build_suggestion(state, team, "spymaster")
    assert suggestion == {
        "kind": "clue",
        "word": "OCEAN",
        "number": 2,
        "targets": ["SHIP", "WAVE"],
    }


@pytest.mark.asyncio
async def test_build_suggestion_uses_operative_on_guess_turn(monkeypatch) -> None:
    state = _state()
    team = state["current_team"]
    state["phase"] = "guess"
    state["current_clue"] = {"word": "OCEAN", "number": 1}
    state["guesses_remaining"] = 2
    target = next(card for card in state["cards"] if not card["revealed"])

    async def fake_guesses(snapshot, guess_team, max_guesses):
        assert snapshot is state
        assert guess_team == team
        assert max_guesses == 2
        return [target["index"], 99]

    async def fake_clue(*_args):
        raise AssertionError("spymaster model should not run on a guess turn")

    monkeypatch.setattr("app.games.codenames.suggest.ai_spymaster_clue", fake_clue)
    monkeypatch.setattr("app.games.codenames.suggest.ai_operative_guesses", fake_guesses)

    suggestion = await build_suggestion(state, team, "operative")
    assert suggestion == {
        "kind": "guess",
        "guesses": [{"index": target["index"], "word": target["word"]}],
    }


@pytest.mark.asyncio
async def test_idle_viewer_does_not_call_the_model(monkeypatch) -> None:
    state = _state()

    async def fail(*_args):
        raise AssertionError("model should stay idle when it is not this player's turn")

    monkeypatch.setattr("app.games.codenames.suggest.ai_spymaster_clue", fail)
    monkeypatch.setattr("app.games.codenames.suggest.ai_operative_guesses", fail)

    suggestion = await build_suggestion(state, state["current_team"], "operative")
    assert suggestion == {"kind": "none"}
