import json

import pytest

from app.games.codenames import ai as codenames_ai
from app.games.codenames.ai import (
    _accept_focused_fallback,
    _build_focused_fallback_prompt,
    _fallback_target_groups,
    _parse_operative_guesses,
    fallback_clue,
)


def _base_state(*, team: str = "red", clue_number: int = 3, guesses_made: int = 0) -> dict:
    cards = [{"index": i, "word": f"W{i}", "color": "red", "revealed": False} for i in range(25)]
    history_entry: dict = {
        "clue": {"word": "OCEAN", "number": clue_number},
        "guesses": [{"index": i, "word": f"W{i}", "color": team} for i in range(guesses_made)],
        "completed": False,
    }
    prior_entry = {
        "clue": {"word": "FRUIT", "number": 2},
        "guesses": [{"index": 0, "word": "W0", "color": team}],
        "completed": True,
    }
    return {
        "cards": cards,
        "red_remaining": 3,
        "blue_remaining": 5,
        "current_clue": {"word": "OCEAN", "number": clue_number},
        "clue_history": {"red": [prior_entry, history_entry], "blue": []},
    }


def test_bonus_uses_explicit_bonus_guess_for_prior_clues() -> None:
    state = _base_state()
    data = {
        "current_guesses": [
            {"index": 1, "confidence": 0.9},
            {"index": 2, "confidence": 0.9},
            {"index": 3, "confidence": 0.9},
        ],
        "bonus_guess": {"index": 4, "confidence": 0.5},
    }

    result = _parse_operative_guesses(data, state, limit=4, clue_number=3, team="red")

    assert result == [1, 2, 3, 4]


def test_bonus_not_taken_from_extra_current_guess_candidates() -> None:
    state = _base_state(clue_number=2)
    data = {
        "current_guesses": [
            {"index": 1, "confidence": 0.9},
            {"index": 2, "confidence": 0.9},
            {"index": 3, "confidence": 0.95},
        ],
        "bonus_guess": {"index": 4, "confidence": 0.5},
    }

    result = _parse_operative_guesses(data, state, limit=3, clue_number=2, team="red")

    assert result == [1, 2, 4]


def test_bonus_skipped_without_unresolved_prior_clues() -> None:
    state = _base_state()
    state["clue_history"]["red"] = [state["clue_history"]["red"][-1]]
    data = {
        "current_guesses": [
            {"index": 1, "confidence": 0.9},
            {"index": 2, "confidence": 0.9},
            {"index": 3, "confidence": 0.9},
        ],
        "bonus_guess": {"index": 4, "confidence": 0.9},
    }

    result = _parse_operative_guesses(data, state, limit=4, clue_number=3, team="red")

    assert result == [1, 2, 3]


def test_bonus_not_used_for_current_clue_even_when_very_confident() -> None:
    state = _base_state()
    state["red_remaining"] = 5
    state["blue_remaining"] = 5
    state["clue_history"]["red"] = [state["clue_history"]["red"][-1]]
    data = {
        "current_guesses": [
            {"index": 1, "confidence": 0.9},
            {"index": 2, "confidence": 0.9},
            {"index": 3, "confidence": 0.9},
        ],
        "bonus_guess": {"index": 4, "confidence": 0.95},
    }

    result = _parse_operative_guesses(data, state, limit=4, clue_number=3, team="red")

    assert result == [1, 2, 3]


def test_low_confidence_current_guess_does_not_block_bonus() -> None:
    state = _base_state(clue_number=2)
    data = {
        "current_guesses": [
            {"index": 1, "confidence": 0.9},
            {"index": 2, "confidence": 0.2},
        ],
        "bonus_guess": {"index": 4, "confidence": 0.5},
    }

    result = _parse_operative_guesses(data, state, limit=3, clue_number=2, team="red")

    assert result == [1, 4]


def test_mid_turn_bonus_only_uses_bonus_guess_field() -> None:
    state = _base_state(guesses_made=2, clue_number=2)
    data = {
        "current_guesses": [{"index": 3, "confidence": 0.95}],
        "bonus_guess": {"index": 4, "confidence": 0.5},
    }

    result = _parse_operative_guesses(data, state, limit=1, clue_number=2, team="red")

    assert result == [4]


def test_mid_turn_regular_guess_when_slots_remain() -> None:
    state = _base_state(guesses_made=1, clue_number=2)
    data = {
        "current_guesses": [{"index": 3, "confidence": 0.6}],
        "bonus_guess": {"index": 4, "confidence": 0.5},
    }

    result = _parse_operative_guesses(data, state, limit=1, clue_number=2, team="red")

    assert result == [3]


def test_after_current_clue_filled_bonus_targets_prior_clues() -> None:
    state = _base_state(guesses_made=1, clue_number=2)
    data = {
        "current_guesses": [{"index": 3, "confidence": 0.6}],
        "bonus_guess": {"index": 4, "confidence": 0.5},
    }

    result = _parse_operative_guesses(data, state, limit=2, clue_number=2, team="red")

    assert result == [3, 4]


def test_legacy_guesses_array_still_parses_current_only() -> None:
    state = _base_state(clue_number=2)
    data = {
        "guesses": [
            {"index": 1, "confidence": 0.9},
            {"index": 2, "confidence": 0.9},
            {"index": 3, "confidence": 0.95},
        ]
    }

    result = _parse_operative_guesses(data, state, limit=3, clue_number=2, team="red")

    assert result == [1, 2]


def test_fallback_target_groups_prefers_multi_word() -> None:
    groups = _fallback_target_groups(["A", "B", "C", "D"])

    assert groups
    assert len(groups[0]) == 3
    assert any(len(g) == 2 for g in groups)
    assert any(len(g) == 1 for g in groups)
    assert all(set(g).issubset({"A", "B", "C", "D"}) for g in groups)


def test_fallback_target_groups_handles_few_words() -> None:
    assert _fallback_target_groups([]) == []
    pairs_and_singles = _fallback_target_groups(["A", "B"])
    assert all(len(g) <= 2 for g in pairs_and_singles)
    assert any(len(g) == 2 for g in pairs_and_singles)


def test_focused_fallback_prompt_requires_all_targets() -> None:
    prompt = _build_focused_fallback_prompt(
        ["APPLE", "ORANGE"],
        avoid=["KNIFE"],
        other_board_words=["TABLE"],
    )

    assert "APPLE" in prompt and "ORANGE" in prompt
    assert "number must be 2" in prompt
    assert '"number": 2' in prompt
    assert "KNIFE" in prompt and "TABLE" in prompt


def test_accept_focused_fallback_rejects_single_when_multi_requested() -> None:
    assert _accept_focused_fallback(("FRUIT", 1, ["APPLE"]), ["APPLE", "ORANGE"]) is False
    assert _accept_focused_fallback(("FRUIT", 2, ["APPLE", "ORANGE"]), ["APPLE", "ORANGE"]) is True
    assert _accept_focused_fallback(("FRUIT", 2, ["APPLE", "PEAR"]), ["APPLE", "ORANGE"]) is False
    assert _accept_focused_fallback(("WATER", 1, ["APPLE"]), ["APPLE"]) is True


@pytest.mark.asyncio
async def test_fallback_clue_accepts_multi_target_before_singles(monkeypatch) -> None:
    state = {
        "cards": [
            {"word": "APPLE", "color": "red", "revealed": False},
            {"word": "ORANGE", "color": "red", "revealed": False},
            {"word": "BANANA", "color": "red", "revealed": False},
            {"word": "KNIFE", "color": "blue", "revealed": False},
            {"word": "TABLE", "color": "neutral", "revealed": False},
        ]
    }
    calls: list[str] = []

    async def fake_chat(prompt: str, **_kwargs: object) -> str:
        calls.append(prompt)
        if "number must be 3" in prompt or "number must be 2" in prompt:
            return json.dumps(
                {
                    "clue": "FRUIT",
                    "number": 2,
                    "targets": ["APPLE", "ORANGE"],
                    "risky_words": [],
                }
            )
        return json.dumps(
            {
                "clue": "PRODUCE",
                "number": 1,
                "targets": ["APPLE"],
                "risky_words": [],
            }
        )

    monkeypatch.setattr(codenames_ai, "deepseek_chat", fake_chat)
    monkeypatch.setattr(
        codenames_ai,
        "_fallback_target_groups",
        lambda _targets: [["APPLE", "ORANGE", "BANANA"], ["APPLE"]],
    )

    clue, number, targets = await fallback_clue(state, "red")

    assert clue == "FRUIT"
    assert number == 2
    assert set(targets) == {"APPLE", "ORANGE"}
    assert len(calls) == 1
