"""Find legal rack plays. Uses a forward trie from each anchor."""

from __future__ import annotations

from collections import Counter

from app.games.scrabble.board import CENTER, SIZE, board_is_empty
from app.games.scrabble.dictionary import trie, words
from app.games.scrabble.scoring import score_placements

_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _cell(board, across: int, along: int, horizontal: bool):
    if horizontal:
        return board[across][along]
    return board[along][across]


def _pos(across: int, along: int, horizontal: bool) -> tuple[int, int]:
    if horizontal:
        return across, along
    return along, across


def _cross_checks(board, horizontal: bool) -> list[list[set[str] | None]]:
    """Letters that keep the perpendicular word legal. None means no cross word."""
    lexicon = words()
    checks: list[list[set[str] | None]] = [[None for _ in range(SIZE)] for _ in range(SIZE)]
    dr, dc = (0, 1) if horizontal else (1, 0)
    for row in range(SIZE):
        for col in range(SIZE):
            if board[row][col] is not None:
                continue
            before: list[str] = []
            r, c = row - dr, col - dc
            while 0 <= r < SIZE and 0 <= c < SIZE and board[r][c] is not None:
                before.append(board[r][c]["l"])
                r -= dr
                c -= dc
            before.reverse()
            after: list[str] = []
            r, c = row + dr, col + dc
            while 0 <= r < SIZE and 0 <= c < SIZE and board[r][c] is not None:
                after.append(board[r][c]["l"])
                r += dr
                c += dc
            if not before and not after:
                continue
            prefix = "".join(before)
            suffix = "".join(after)
            allowed: set[str] = set()
            for letter in _ALPHABET:
                if prefix + letter + suffix in lexicon:
                    allowed.add(letter)
            checks[row][col] = allowed
    return checks


def _anchors(board, across: int, horizontal: bool, opening: bool) -> list[int]:
    if opening:
        return [CENTER] if across == CENTER else []
    found: list[int] = []
    for along in range(SIZE):
        row, col = _pos(across, along, horizontal)
        if board[row][col] is not None:
            continue
        for dr, dc in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            other_r, other_c = row + dr, col + dc
            if 0 <= other_r < SIZE and 0 <= other_c < SIZE and board[other_r][other_c] is not None:
                found.append(along)
                break
    return found


def _is_anchor_square(board, row: int, col: int, opening: bool) -> bool:
    if board[row][col] is not None:
        return False
    if opening:
        return row == CENTER and col == CENTER
    for dr, dc in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        other_r, other_c = row + dr, col + dc
        if 0 <= other_r < SIZE and 0 <= other_c < SIZE and board[other_r][other_c] is not None:
            return True
    return False


def generate_moves(board, rack_tiles: list[dict]) -> list[dict]:
    if not rack_tiles:
        return []
    root = trie()
    counts: Counter[str] = Counter()
    for tile in rack_tiles:
        counts["?" if tile["b"] else tile["l"]] += 1

    opening = board_is_empty(board)
    found: dict[tuple, dict] = {}
    placements: list[dict] = []

    def remember() -> None:
        if not placements:
            return
        snapshot = [dict(item) for item in placements]
        try:
            total, formed, bingo = score_placements(board, snapshot)
        except ValueError:
            return
        key = tuple(sorted((item["row"], item["col"], item["letter"], item["blank"]) for item in snapshot))
        current = found.get(key)
        if current is None or total > current["score"]:
            found[key] = {
                "placements": snapshot,
                "score": total,
                "words": [{"word": item["word"], "score": item["score"]} for item in formed],
                "bingo": bingo,
            }

    def search_anchor(across: int, anchor: int, horizontal: bool, checks) -> None:
        left = anchor - 1
        starts: list[int]
        if left >= 0 and _cell(board, across, left, horizontal) is not None:
            start = left
            while start - 1 >= 0 and _cell(board, across, start - 1, horizontal) is not None:
                start -= 1
            starts = [start]
        else:
            limit = 0
            cursor = left
            while cursor >= 0 and _cell(board, across, cursor, horizontal) is None:
                row, col = _pos(across, cursor, horizontal)
                if _is_anchor_square(board, row, col, opening):
                    break
                limit += 1
                cursor -= 1
            starts = list(range(anchor - limit, anchor + 1))

        def can_end(node, partial: str) -> bool:
            if node.end and len(partial) >= 2:
                return True
            if len(partial) == 1 and len(placements) == 1:
                only = placements[0]
                return checks[only["row"]][only["col"]] is not None
            return False

        def extend(node, partial: str, along: int) -> None:
            if along >= SIZE:
                if along > anchor and can_end(node, partial):
                    remember()
                return
            row, col = _pos(across, along, horizontal)
            cell = board[row][col]
            if cell is not None:
                child = node.children.get(cell["l"])
                if child is not None:
                    extend(child, partial + cell["l"], along + 1)
                return
            if along > anchor and can_end(node, partial):
                remember()
            allowed = checks[row][col]
            for letter, child in node.children.items():
                if allowed is not None and letter not in allowed:
                    continue
                if counts[letter] > 0:
                    counts[letter] -= 1
                    placements.append(
                        {"row": row, "col": col, "letter": letter, "blank": False}
                    )
                    extend(child, partial + letter, along + 1)
                    placements.pop()
                    counts[letter] += 1
                elif counts["?"] > 0:
                    counts["?"] -= 1
                    placements.append(
                        {"row": row, "col": col, "letter": letter, "blank": True}
                    )
                    extend(child, partial + letter, along + 1)
                    placements.pop()
                    counts["?"] += 1

        for start in starts:
            extend(root, "", start)

    for horizontal in (True, False):
        # Perpendicular checks: a horizontal play is tested against vertical words.
        checks = _cross_checks(board, horizontal=not horizontal)
        for across in range(SIZE):
            for anchor in _anchors(board, across, horizontal, opening):
                search_anchor(across, anchor, horizontal, checks)

    return list(found.values())
