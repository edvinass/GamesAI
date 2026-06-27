import pytest

from app.games.codenames.clue_validation import (
    conflicting_board_word,
    validate_clue_word,
)


@pytest.fixture
def board_words() -> set[str]:
    return {"BUG", "OCEAN", "CAR", "NIGHT"}


def test_rejects_exact_board_match(board_words: set[str]) -> None:
    assert validate_clue_word("BUG", board_words) == "Clue cannot match a word on the board"


def test_rejects_plural_form(board_words: set[str]) -> None:
    assert validate_clue_word("BUGS", board_words) == "Clue is too similar to board word 'Bug'"


def test_rejects_suffix_form(board_words: set[str]) -> None:
    assert validate_clue_word("BUGGY", board_words) == "Clue is too similar to board word 'Bug'"


def test_rejects_clue_contained_in_board_word(board_words: set[str]) -> None:
    board = {"BUGGY", "OCEAN"}
    assert validate_clue_word("BUG", board) == "Clue is too similar to board word 'Buggy'"


def test_allows_unrelated_clue(board_words: set[str]) -> None:
    assert validate_clue_word("OCEAN", {"BUG", "CAR"}) is None
    assert validate_clue_word("WATER", board_words) is None


def test_allows_short_clue_without_substring_match() -> None:
    assert conflicting_board_word("AT", {"CAT"}) is None
    assert validate_clue_word("AT", {"CAT"}) is None


def test_rejects_multi_word_clue(board_words: set[str]) -> None:
    assert validate_clue_word("BIG CAT", board_words) == "Clue must be a single word"


def test_rejects_empty_clue(board_words: set[str]) -> None:
    assert validate_clue_word("", board_words) == "Clue must be a single word"
    assert validate_clue_word("   ", board_words) == "Clue must be a single word"


def test_normalizes_case_and_whitespace(board_words: set[str]) -> None:
    assert validate_clue_word("  bugs  ", board_words) == "Clue is too similar to board word 'Bug'"
