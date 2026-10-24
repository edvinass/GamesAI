"""Scrabble board premiums, tile values, and the tile bag."""

from __future__ import annotations

import random

SIZE = 15
CENTER = 7
RACK_SIZE = 7
BINGO_BONUS = 50
# Official end condition: six scoreless turns in a row.
MAX_ZERO_TURNS = 6

# 3 triple word, 2 double word, t triple letter, d double letter.
_LAYOUT = (
    "3..d...3...d..3",
    ".2...t...t...2.",
    "..2...d.d...2..",
    "d..2...d...2..d",
    "....2.....2....",
    ".t...t...t...t.",
    "..d...d.d...d..",
    "3..d...2...d..3",
    "..d...d.d...d..",
    ".t...t...t...t.",
    "....2.....2....",
    "d..2...d...2..d",
    "..2...d.d...2..",
    ".2...t...t...2.",
    "3..d...3...d..3",
)

_CODE = {"3": "tw", "2": "dw", "t": "tl", "d": "dl", ".": ""}

PREMIUMS: list[list[str]] = [
    [_CODE[ch] for ch in row] for row in _LAYOUT
]

LETTER_VALUES: dict[str, int] = {
    "A": 1,
    "B": 3,
    "C": 3,
    "D": 2,
    "E": 1,
    "F": 4,
    "G": 2,
    "H": 4,
    "I": 1,
    "J": 8,
    "K": 5,
    "L": 1,
    "M": 3,
    "N": 1,
    "O": 1,
    "P": 3,
    "Q": 10,
    "R": 1,
    "S": 1,
    "T": 1,
    "U": 1,
    "V": 4,
    "W": 4,
    "X": 8,
    "Y": 4,
    "Z": 10,
}

DISTRIBUTION: dict[str, int] = {
    "A": 9,
    "B": 2,
    "C": 2,
    "D": 4,
    "E": 12,
    "F": 2,
    "G": 3,
    "H": 2,
    "I": 9,
    "J": 1,
    "K": 1,
    "L": 4,
    "M": 2,
    "N": 6,
    "O": 8,
    "P": 2,
    "Q": 1,
    "R": 6,
    "S": 4,
    "T": 6,
    "U": 4,
    "V": 2,
    "W": 2,
    "X": 1,
    "Y": 2,
    "Z": 1,
    "?": 2,
}


def tile_points(tile: dict) -> int:
    if tile.get("b"):
        return 0
    return LETTER_VALUES[tile["l"]]


def new_bag() -> list[dict]:
    tiles: list[dict] = []
    number = 1
    for letter, count in DISTRIBUTION.items():
        blank = letter == "?"
        for _ in range(count):
            tiles.append(
                {
                    "id": f"t{number}",
                    "l": "" if blank else letter,
                    "b": blank,
                }
            )
            number += 1
    random.shuffle(tiles)
    return tiles


def empty_board() -> list[list[dict | None]]:
    return [[None for _ in range(SIZE)] for _ in range(SIZE)]


def board_is_empty(board: list[list]) -> bool:
    return all(cell is None for row in board for cell in row)
