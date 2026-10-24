"""Score a set of newly placed tiles against the current board."""

from __future__ import annotations

from app.games.scrabble.board import BINGO_BONUS, CENTER, LETTER_VALUES, PREMIUMS, SIZE, board_is_empty
from app.games.scrabble.dictionary import is_word

_DIRS = ((0, 1), (1, 0), (0, -1), (-1, 0))


def _on_board(row: int, col: int) -> bool:
    return 0 <= row < SIZE and 0 <= col < SIZE


def _lookup(board: list[list], placed: dict, row: int, col: int):
    pending = placed.get((row, col))
    if pending is not None:
        return pending["letter"], True, pending["blank"]
    cell = board[row][col]
    if cell is None:
        return None
    return cell["l"], False, bool(cell["b"])


def _run(board, placed, row: int, col: int, dr: int, dc: int) -> dict | None:
    if _lookup(board, placed, row, col) is None:
        return None
    while True:
        prev_r, prev_c = row - dr, col - dc
        if not _on_board(prev_r, prev_c) or _lookup(board, placed, prev_r, prev_c) is None:
            break
        row, col = prev_r, prev_c

    chars: list[str] = []
    face = 0
    word_mult = 1
    new_tiles = 0
    start_r, start_c = row, col
    while _on_board(row, col):
        found = _lookup(board, placed, row, col)
        if found is None:
            break
        letter, is_new, is_blank = found
        chars.append(letter)
        value = 0 if is_blank else LETTER_VALUES[letter]
        if is_new:
            new_tiles += 1
            premium = PREMIUMS[row][col]
            if premium == "dl":
                value *= 2
            elif premium == "tl":
                value *= 3
            elif premium == "dw":
                word_mult *= 2
            elif premium == "tw":
                word_mult *= 3
        face += value
        row += dr
        col += dc

    if len(chars) < 2 or new_tiles == 0:
        return None
    word = "".join(chars)
    if not is_word(word):
        raise ValueError(f"{word} is not in the dictionary")
    return {
        "word": word,
        "score": face * word_mult,
        "row": start_r,
        "col": start_c,
        "dir": "h" if dc == 1 else "v",
    }


def check_geometry(board: list[list], placements: list[dict]) -> None:
    if not placements:
        raise ValueError("Place at least one tile")
    if len(placements) > 7:
        raise ValueError("You can play at most 7 tiles")

    squares: list[tuple[int, int]] = []
    for placement in placements:
        row, col = placement["row"], placement["col"]
        if type(row) is not int or type(col) is not int or not _on_board(row, col):
            raise ValueError("That square is off the board")
        if board[row][col] is not None:
            raise ValueError("That square is already taken")
        squares.append((row, col))
    if len(set(squares)) != len(squares):
        raise ValueError("Two tiles cannot share a square")

    rows = {row for row, _ in squares}
    cols = {col for _, col in squares}
    if len(rows) > 1 and len(cols) > 1:
        raise ValueError("Tiles must sit in one row or one column")

    covered = set(squares)
    if len(rows) == 1:
        row = squares[0][0]
        for col in range(min(cols), max(cols) + 1):
            if board[row][col] is None and (row, col) not in covered:
                raise ValueError("The word has a gap")
    else:
        col = squares[0][1]
        for row in range(min(rows), max(rows) + 1):
            if board[row][col] is None and (row, col) not in covered:
                raise ValueError("The word has a gap")

    if board_is_empty(board):
        if (CENTER, CENTER) not in covered:
            raise ValueError("The first word must cover the center star")
        return

    for row, col in squares:
        for dr, dc in _DIRS:
            other_r, other_c = row + dr, col + dc
            if _on_board(other_r, other_c) and board[other_r][other_c] is not None:
                return
    raise ValueError("The word has to touch a tile already on the board")


def score_placements(board: list[list], placements: list[dict]) -> tuple[int, list[dict], bool]:
    """Return total score, word breakdown, and whether this play bingos."""
    check_geometry(board, placements)
    placed = {(item["row"], item["col"]): item for item in placements}
    words: list[dict] = []

    if len(placements) == 1:
        only = placements[0]
        for dr, dc in ((0, 1), (1, 0)):
            formed = _run(board, placed, only["row"], only["col"], dr, dc)
            if formed:
                words.append(formed)
    else:
        horizontal = len({item["row"] for item in placements}) == 1
        dr, dc = (0, 1) if horizontal else (1, 0)
        start = placements[0]
        main = _run(board, placed, start["row"], start["col"], dr, dc)
        if main is None:
            raise ValueError("That play does not form a word")
        words.append(main)
        for item in placements:
            cross = _run(board, placed, item["row"], item["col"], dc, dr)
            if cross:
                words.append(cross)

    if not words:
        raise ValueError("That play does not form a word")

    total = sum(item["score"] for item in words)
    bingo = len(placements) == 7
    if bingo:
        total += BINGO_BONUS
    return total, words, bingo
