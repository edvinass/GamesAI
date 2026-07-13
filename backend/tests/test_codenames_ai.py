import pytest

from app.games.codenames.ai import _parse_operative_guesses


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


def test_bonus_targets_unresolved_prior_clues_at_regular_threshold() -> None:
    state = _base_state()
    data = {
        "guesses": [
            {"index": 1, "confidence": 0.9},
            {"index": 2, "confidence": 0.9},
            {"index": 3, "confidence": 0.9},
            {"index": 4, "confidence": 0.5},
        ]
    }

    result = _parse_operative_guesses(data, state, limit=4, clue_number=3, team="red")

    assert result == [1, 2, 3, 4]


def test_bonus_skipped_without_unresolved_prior_clues() -> None:
    state = _base_state()
    state["clue_history"]["red"] = [state["clue_history"]["red"][-1]]
    data = {
        "guesses": [
            {"index": 1, "confidence": 0.9},
            {"index": 2, "confidence": 0.9},
            {"index": 3, "confidence": 0.9},
            {"index": 4, "confidence": 0.5},
        ]
    }

    result = _parse_operative_guesses(data, state, limit=4, clue_number=3, team="red")

    assert result == [1, 2, 3]


def test_bonus_taken_without_unresolved_when_very_confident() -> None:
    state = _base_state()
    state["red_remaining"] = 5
    state["blue_remaining"] = 5
    state["clue_history"]["red"] = [state["clue_history"]["red"][-1]]
    data = {
        "guesses": [
            {"index": 1, "confidence": 0.9},
            {"index": 2, "confidence": 0.9},
            {"index": 3, "confidence": 0.9},
            {"index": 4, "confidence": 0.8},
        ]
    }

    result = _parse_operative_guesses(data, state, limit=4, clue_number=3, team="red")

    assert result == [1, 2, 3, 4]


def test_low_confidence_regular_guess_does_not_block_bonus() -> None:
    state = _base_state()
    data = {
        "guesses": [
            {"index": 1, "confidence": 0.9},
            {"index": 2, "confidence": 0.9},
            {"index": 3, "confidence": 0.2},
            {"index": 4, "confidence": 0.5},
        ]
    }

    result = _parse_operative_guesses(data, state, limit=4, clue_number=3, team="red")

    assert result == [1, 2, 4]


def test_mid_turn_bonus_uses_turn_slot_not_batch_index() -> None:
    state = _base_state(guesses_made=3)
    data = {"guesses": [{"index": 4, "confidence": 0.5}]}

    result = _parse_operative_guesses(data, state, limit=1, clue_number=3, team="red")

    assert result == [4]


def test_mid_turn_regular_guess_when_slots_remain() -> None:
    state = _base_state(guesses_made=2)
    data = {"guesses": [{"index": 3, "confidence": 0.6}]}

    result = _parse_operative_guesses(data, state, limit=2, clue_number=3, team="red")

    assert result == [3]
