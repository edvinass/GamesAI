"""Shared Codenames clue validation for human and AI spymasters."""

MIN_SUBSTRING_CLUE_LEN = 3


def normalize_clue_word(clue: str) -> str:
    return clue.strip().upper()


def board_words_upper(cards: list[dict]) -> set[str]:
    return {c["word"].upper() for c in cards}


def conflicting_board_word(clue: str, board_words: set[str]) -> str | None:
    """Return the board word that conflicts with the clue, or None."""
    clue = normalize_clue_word(clue)
    if clue in board_words:
        return clue
    if len(clue) >= MIN_SUBSTRING_CLUE_LEN:
        for word in board_words:
            if clue in word or word in clue:
                return word
    return None


def validate_clue_word(clue: str, board_words: set[str]) -> str | None:
    """Return an error message if the clue word is invalid, else None."""
    normalized = normalize_clue_word(clue)
    if not normalized:
        return "Clue must be a single word"
    if len(normalized.split()) > 1:
        return "Clue must be a single word"

    conflict = conflicting_board_word(normalized, board_words)
    if conflict:
        if normalized == conflict:
            return "Clue cannot match a word on the board"
        return f"Clue is too similar to board word '{conflict.title()}'"
    return None
