"""Go rules engine for 9×9 boards — liberties, capture, ko, and area scoring."""

from __future__ import annotations

import copy
from typing import Any

BOARD_SIZE = 9
FILES = "abcdefghi"
EMPTY = 0
BLACK = 1
WHITE = 2
COLOR_CHAR = {BLACK: "B", WHITE: "W", EMPTY: "."}
CHAR_COLOR = {"B": BLACK, "W": WHITE, ".": EMPTY}
OPPONENT = {BLACK: WHITE, WHITE: BLACK}
DEFAULT_KOMI = 5.5


def empty_board() -> list[list[int]]:
    return [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]


def coord_to_rc(coord: str) -> tuple[int, int]:
    coord = coord.strip().lower()
    if len(coord) != 2:
        raise ValueError(f"Invalid coordinate: {coord}")
    col = FILES.index(coord[0])
    row = int(coord[1]) - 1
    if row < 0 or row >= BOARD_SIZE:
        raise ValueError(f"Invalid coordinate: {coord}")
    return row, col


def rc_to_coord(row: int, col: int) -> str:
    if not (0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE):
        raise ValueError(f"Out of bounds: ({row}, {col})")
    return f"{FILES[col]}{row + 1}"


def create_position(turn: str = "B") -> dict[str, Any]:
    return {
        "board": empty_board(),
        "turn": turn,
        "ko_point": None,
        "consecutive_passes": 0,
        "captured": {"B": 0, "W": 0},
    }


def board_matrix(position: dict[str, Any]) -> list[list[str | None]]:
    matrix: list[list[str | None]] = []
    for row in position["board"]:
        matrix.append([COLOR_CHAR[c] if c != EMPTY else None for c in row])
    return matrix


def board_hash(board: list[list[int]]) -> str:
    return "".join(str(c) for row in board for c in row)


def neighbors(row: int, col: int) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nr, nc = row + dr, col + dc
        if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE:
            result.append((nr, nc))
    return result


def get_group(board: list[list[int]], row: int, col: int) -> set[tuple[int, int]]:
    color = board[row][col]
    if color == EMPTY:
        return set()
    stack = [(row, col)]
    group: set[tuple[int, int]] = set()
    while stack:
        r, c = stack.pop()
        if (r, c) in group:
            continue
        if board[r][c] != color:
            continue
        group.add((r, c))
        for nr, nc in neighbors(r, c):
            if (nr, nc) not in group and board[nr][nc] == color:
                stack.append((nr, nc))
    return group


def group_liberties(board: list[list[int]], group: set[tuple[int, int]]) -> set[tuple[int, int]]:
    libs: set[tuple[int, int]] = set()
    for r, c in group:
        for nr, nc in neighbors(r, c):
            if board[nr][nc] == EMPTY:
                libs.add((nr, nc))
    return libs


def _remove_group(board: list[list[int]], group: set[tuple[int, int]]) -> int:
    for r, c in group:
        board[r][c] = EMPTY
    return len(group)


def _captures_if_played(
    board: list[list[int]], row: int, col: int, color: int
) -> list[set[tuple[int, int]]]:
    captured: list[set[tuple[int, int]]] = []
    opponent = OPPONENT[color]
    for nr, nc in neighbors(row, col):
        if board[nr][nc] != opponent:
            continue
        group = get_group(board, nr, nc)
        if not group_liberties(board, group):
            captured.append(group)
    return captured


def _self_liberties_after_play(
    board: list[list[int]], row: int, col: int, color: int
) -> int:
    temp = copy.deepcopy(board)
    temp[row][col] = color
    for group in _captures_if_played(temp, row, col, color):
        _remove_group(temp, group)
    own_group = get_group(temp, row, col)
    return len(group_liberties(temp, own_group))


def is_legal_play(position: dict[str, Any], row: int, col: int) -> bool:
    board = position["board"]
    if board[row][col] != EMPTY:
        return False

    color = CHAR_COLOR[position["turn"]]
    ko = position.get("ko_point")
    if ko and (row, col) == tuple(ko):
        return False

    temp = copy.deepcopy(board)
    temp[row][col] = color
    captured_groups = _captures_if_played(temp, row, col, color)
    for group in captured_groups:
        _remove_group(temp, group)

    own_group = get_group(temp, row, col)
    if not group_liberties(temp, own_group):
        return False

    return True


def generate_legal_plays(position: dict[str, Any]) -> list[dict[str, Any]]:
    plays: list[dict[str, Any]] = []
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if is_legal_play(position, row, col):
                plays.append({"row": row, "col": col, "coord": rc_to_coord(row, col)})
    return plays


def apply_play_raw(position: dict[str, Any], row: int, col: int) -> dict[str, Any]:
    if not is_legal_play(position, row, col):
        raise ValueError("Illegal play")

    new_pos = copy.deepcopy(position)
    board = new_pos["board"]
    color = CHAR_COLOR[new_pos["turn"]]
    color_char = COLOR_CHAR[color]
    opponent_char = COLOR_CHAR[OPPONENT[color]]

    board[row][col] = color
    captured_stones = 0
    ko_point = None

    for nr, nc in neighbors(row, col):
        if board[nr][nc] != OPPONENT[color]:
            continue
        group = get_group(board, nr, nc)
        if not group_liberties(board, group):
            size = _remove_group(board, group)
            captured_stones += size
            if size == 1 and len(group_liberties(board, get_group(board, row, col))) == 1:
                # Potential ko: single stone captured, replanting may recreate ko
                ko_point = next(iter(group))

    new_pos["captured"][opponent_char] += captured_stones
    new_pos["ko_point"] = ko_point
    new_pos["consecutive_passes"] = 0
    new_pos["turn"] = opponent_char
    return new_pos


def apply_pass_raw(position: dict[str, Any]) -> dict[str, Any]:
    new_pos = copy.deepcopy(position)
    new_pos["ko_point"] = None
    new_pos["consecutive_passes"] = int(new_pos.get("consecutive_passes", 0)) + 1
    new_pos["turn"] = "W" if new_pos["turn"] == "B" else "B"
    return new_pos


def game_over_by_passes(position: dict[str, Any]) -> bool:
    return int(position.get("consecutive_passes", 0)) >= 2


def _empty_regions(board: list[list[int]]) -> list[set[tuple[int, int]]]:
    seen: set[tuple[int, int]] = set()
    regions: list[set[tuple[int, int]]] = []
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if board[row][col] != EMPTY or (row, col) in seen:
                continue
            stack = [(row, col)]
            region: set[tuple[int, int]] = set()
            while stack:
                r, c = stack.pop()
                if (r, c) in region:
                    continue
                if board[r][c] != EMPTY:
                    continue
                region.add((r, c))
                for nr, nc in neighbors(r, c):
                    if (nr, nc) not in region:
                        stack.append((nr, nc))
            seen |= region
            regions.append(region)
    return regions


def _region_owner(board: list[list[int]], region: set[tuple[int, int]]) -> int | None:
    adjacent_colors: set[int] = set()
    for r, c in region:
        for nr, nc in neighbors(r, c):
            stone = board[nr][nc]
            if stone != EMPTY:
                adjacent_colors.add(stone)
    if adjacent_colors == {BLACK}:
        return BLACK
    if adjacent_colors == {WHITE}:
        return WHITE
    return None


def score_position(position: dict[str, Any], komi: float = DEFAULT_KOMI) -> dict[str, Any]:
    board = position["board"]
    black_stones = sum(1 for row in board for c in row if c == BLACK)
    white_stones = sum(1 for row in board for c in row if c == WHITE)
    black_territory = 0
    white_territory = 0

    for region in _empty_regions(board):
        owner = _region_owner(board, region)
        if owner == BLACK:
            black_territory += len(region)
        elif owner == WHITE:
            white_territory += len(region)

    black_score = black_stones + black_territory
    white_score = white_stones + white_territory + komi

    if black_score > white_score:
        winner_color = "B"
    elif white_score > black_score:
        winner_color = "W"
    else:
        winner_color = None

    return {
        "black_stones": black_stones,
        "white_stones": white_stones,
        "black_territory": black_territory,
        "white_territory": white_territory,
        "black_score": black_score,
        "white_score": white_score,
        "komi": komi,
        "winner_color": winner_color,
    }


def find_play(position: dict[str, Any], coord: str) -> dict[str, Any] | None:
    row, col = coord_to_rc(coord)
    for play in generate_legal_plays(position):
        if play["row"] == row and play["col"] == col:
            return play
    return None
