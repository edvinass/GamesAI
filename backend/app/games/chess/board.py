"""Minimal chess rules: move generation, legality, checkmate/stalemate."""

from __future__ import annotations

from typing import Any

FILES = "abcdefgh"
RANKS = "12345678"

WHITE_PIECES = set("KQRBNP")
BLACK_PIECES = set("kqrbnp")

PIECE_VALUES = {
    "P": 100,
    "N": 320,
    "B": 330,
    "R": 500,
    "Q": 900,
    "K": 20000,
}

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

KNIGHT_DELTAS = ((1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2))
KING_DELTAS = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))
BISHOP_DIRS = ((1, 1), (1, -1), (-1, 1), (-1, -1))
ROOK_DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def square_to_coords(square: str) -> tuple[int, int]:
    if len(square) != 2 or square[0] not in FILES or square[1] not in RANKS:
        raise ValueError(f"Invalid square: {square}")
    file_i = FILES.index(square[0])
    rank_i = RANKS.index(square[1])
    return file_i, rank_i


def coords_to_square(file_i: int, rank_i: int) -> str:
    return FILES[file_i] + RANKS[rank_i]


def in_bounds(file_i: int, rank_i: int) -> bool:
    return 0 <= file_i < 8 and 0 <= rank_i < 8


def is_white(piece: str) -> bool:
    return piece in WHITE_PIECES


def is_black(piece: str) -> bool:
    return piece in BLACK_PIECES


def color_of(piece: str) -> str:
    return "w" if is_white(piece) else "b"


def opponent(color: str) -> str:
    return "b" if color == "w" else "w"


def empty_board() -> list[list[str | None]]:
    return [[None for _ in range(8)] for _ in range(8)]


def parse_fen(fen: str) -> dict[str, Any]:
    parts = fen.split()
    if len(parts) < 4:
        raise ValueError("Invalid FEN")
    placement, turn, castling, ep = parts[0], parts[1], parts[2], parts[3]
    halfmove = int(parts[4]) if len(parts) > 4 else 0
    fullmove = int(parts[5]) if len(parts) > 5 else 1

    board = empty_board()
    ranks = placement.split("/")
    if len(ranks) != 8:
        raise ValueError("Invalid FEN placement")
    for rank_from_top, rank_str in enumerate(ranks):
        rank_i = 7 - rank_from_top
        file_i = 0
        for ch in rank_str:
            if ch.isdigit():
                file_i += int(ch)
            else:
                if file_i >= 8:
                    raise ValueError("Invalid FEN rank")
                board[rank_i][file_i] = ch
                file_i += 1
        if file_i != 8:
            raise ValueError("Invalid FEN rank width")

    return {
        "board": board,
        "turn": turn,
        "castling": castling if castling != "-" else "",
        "ep": None if ep == "-" else ep,
        "halfmove": halfmove,
        "fullmove": fullmove,
    }


def board_to_fen(state: dict[str, Any]) -> str:
    ranks = []
    for rank_from_top in range(8):
        rank_i = 7 - rank_from_top
        empty = 0
        parts: list[str] = []
        for file_i in range(8):
            piece = state["board"][rank_i][file_i]
            if piece is None:
                empty += 1
            else:
                if empty:
                    parts.append(str(empty))
                    empty = 0
                parts.append(piece)
        if empty:
            parts.append(str(empty))
        ranks.append("".join(parts))
    castling = state["castling"] or "-"
    ep = state["ep"] or "-"
    return f"{'/'.join(ranks)} {state['turn']} {castling} {ep} {state['halfmove']} {state['fullmove']}"


def copy_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "board": [row[:] for row in state["board"]],
        "turn": state["turn"],
        "castling": state["castling"],
        "ep": state["ep"],
        "halfmove": state["halfmove"],
        "fullmove": state["fullmove"],
    }


def piece_at(state: dict[str, Any], square: str) -> str | None:
    file_i, rank_i = square_to_coords(square)
    return state["board"][rank_i][file_i]


def find_king(state: dict[str, Any], color: str) -> tuple[int, int] | None:
    king = "K" if color == "w" else "k"
    for rank_i in range(8):
        for file_i in range(8):
            if state["board"][rank_i][file_i] == king:
                return file_i, rank_i
    return None


def is_square_attacked(state: dict[str, Any], file_i: int, rank_i: int, by_color: str) -> bool:
    # Pawns
    pawn = "P" if by_color == "w" else "p"
    pawn_dir = 1 if by_color == "w" else -1
    for df in (-1, 1):
        pf, pr = file_i + df, rank_i - pawn_dir
        if in_bounds(pf, pr) and state["board"][pr][pf] == pawn:
            return True

    # Knights
    knight = "N" if by_color == "w" else "n"
    for df, dr in KNIGHT_DELTAS:
        nf, nr = file_i + df, rank_i + dr
        if in_bounds(nf, nr) and state["board"][nr][nf] == knight:
            return True

    # King
    king = "K" if by_color == "w" else "k"
    for df, dr in KING_DELTAS:
        nf, nr = file_i + df, rank_i + dr
        if in_bounds(nf, nr) and state["board"][nr][nf] == king:
            return True

    # Sliding pieces
    for dirs, pieces in (
        (BISHOP_DIRS, set("BQ" if by_color == "w" else "bq")),
        (ROOK_DIRS, set("RQ" if by_color == "w" else "rq")),
    ):
        for df, dr in dirs:
            nf, nr = file_i + df, rank_i + dr
            while in_bounds(nf, nr):
                piece = state["board"][nr][nf]
                if piece is None:
                    nf += df
                    nr += dr
                    continue
                if piece in pieces:
                    return True
                break

    return False


def is_in_check(state: dict[str, Any], color: str) -> bool:
    king = find_king(state, color)
    if not king:
        return True
    return is_square_attacked(state, king[0], king[1], opponent(color))


def _pseudo_moves_from(state: dict[str, Any], file_i: int, rank_i: int) -> list[dict[str, Any]]:
    piece = state["board"][rank_i][file_i]
    if not piece:
        return []
    color = color_of(piece)
    moves: list[dict[str, Any]] = []
    from_sq = coords_to_square(file_i, rank_i)

    def add_move(to_f: int, to_r: int, **extra: Any) -> None:
        moves.append(
            {
                "from": from_sq,
                "to": coords_to_square(to_f, to_r),
                "piece": piece,
                **extra,
            }
        )

    def can_capture(target: str | None) -> bool:
        if target is None:
            return False
        return color_of(target) != color

    kind = piece.upper()
    if kind == "P":
        direction = 1 if color == "w" else -1
        start_rank = 1 if color == "w" else 6
        promo_rank = 7 if color == "w" else 0
        one_r = rank_i + direction
        if in_bounds(file_i, one_r) and state["board"][one_r][file_i] is None:
            if one_r == promo_rank:
                for promo in "QRBN":
                    add_move(file_i, one_r, promotion=promo.lower() if color == "b" else promo)
            else:
                add_move(file_i, one_r)
            two_r = rank_i + 2 * direction
            if rank_i == start_rank and state["board"][two_r][file_i] is None:
                add_move(file_i, two_r)
        for df in (-1, 1):
            tf, tr = file_i + df, rank_i + direction
            if not in_bounds(tf, tr):
                continue
            target = state["board"][tr][tf]
            if can_capture(target):
                if tr == promo_rank:
                    for promo in "QRBN":
                        add_move(
                            tf,
                            tr,
                            promotion=promo.lower() if color == "b" else promo,
                            capture=True,
                        )
                else:
                    add_move(tf, tr, capture=True)
            elif state["ep"] and coords_to_square(tf, tr) == state["ep"]:
                add_move(tf, tr, en_passant=True, capture=True)

    elif kind == "N":
        for df, dr in KNIGHT_DELTAS:
            tf, tr = file_i + df, rank_i + dr
            if not in_bounds(tf, tr):
                continue
            target = state["board"][tr][tf]
            if target is None or can_capture(target):
                add_move(tf, tr, capture=bool(target))

    elif kind == "B":
        for df, dr in BISHOP_DIRS:
            tf, tr = file_i + df, rank_i + dr
            while in_bounds(tf, tr):
                target = state["board"][tr][tf]
                if target is None:
                    add_move(tf, tr)
                else:
                    if can_capture(target):
                        add_move(tf, tr, capture=True)
                    break
                tf += df
                tr += dr

    elif kind == "R":
        for df, dr in ROOK_DIRS:
            tf, tr = file_i + df, rank_i + dr
            while in_bounds(tf, tr):
                target = state["board"][tr][tf]
                if target is None:
                    add_move(tf, tr)
                else:
                    if can_capture(target):
                        add_move(tf, tr, capture=True)
                    break
                tf += df
                tr += dr

    elif kind == "Q":
        for df, dr in BISHOP_DIRS + ROOK_DIRS:
            tf, tr = file_i + df, rank_i + dr
            while in_bounds(tf, tr):
                target = state["board"][tr][tf]
                if target is None:
                    add_move(tf, tr)
                else:
                    if can_capture(target):
                        add_move(tf, tr, capture=True)
                    break
                tf += df
                tr += dr

    elif kind == "K":
        for df, dr in KING_DELTAS:
            tf, tr = file_i + df, rank_i + dr
            if not in_bounds(tf, tr):
                continue
            target = state["board"][tr][tf]
            if target is None or can_capture(target):
                add_move(tf, tr, capture=bool(target))

        # Castling
        if color == "w" and rank_i == 0 and file_i == 4:
            if "K" in state["castling"] and state["board"][0][7] == "R":
                if state["board"][0][5] is None and state["board"][0][6] is None:
                    add_move(6, 0, castle="K")
            if "Q" in state["castling"] and state["board"][0][0] == "R":
                if (
                    state["board"][0][1] is None
                    and state["board"][0][2] is None
                    and state["board"][0][3] is None
                ):
                    add_move(2, 0, castle="Q")
        if color == "b" and rank_i == 7 and file_i == 4:
            if "k" in state["castling"] and state["board"][7][7] == "r":
                if state["board"][7][5] is None and state["board"][7][6] is None:
                    add_move(6, 7, castle="k")
            if "q" in state["castling"] and state["board"][7][0] == "r":
                if (
                    state["board"][7][1] is None
                    and state["board"][7][2] is None
                    and state["board"][7][3] is None
                ):
                    add_move(2, 7, castle="q")

    return moves


def apply_move_raw(state: dict[str, Any], move: dict[str, Any]) -> dict[str, Any]:
    new_state = copy_state(state)
    board = new_state["board"]
    from_f, from_r = square_to_coords(move["from"])
    to_f, to_r = square_to_coords(move["to"])
    piece = board[from_r][from_f]
    if not piece:
        raise ValueError("No piece on from-square")

    # En passant capture
    if move.get("en_passant"):
        cap_r = to_r - (1 if is_white(piece) else -1)
        board[cap_r][to_f] = None

    # Castling rook move
    if move.get("castle"):
        if move["castle"] in ("K", "k"):
            rook_from, rook_to = (7, from_r), (5, from_r)
        else:
            rook_from, rook_to = (0, from_r), (3, from_r)
        rook = board[rook_from[1]][rook_from[0]]
        board[rook_from[1]][rook_from[0]] = None
        board[rook_to[1]][rook_to[0]] = rook

    board[from_r][from_f] = None
    board[to_r][to_f] = move.get("promotion") or piece

    # Update castling rights
    castling = set(new_state["castling"])
    if piece == "K":
        castling.discard("K")
        castling.discard("Q")
    elif piece == "k":
        castling.discard("k")
        castling.discard("q")
    elif piece == "R":
        if move["from"] == "a1":
            castling.discard("Q")
        elif move["from"] == "h1":
            castling.discard("K")
    elif piece == "r":
        if move["from"] == "a8":
            castling.discard("q")
        elif move["from"] == "h8":
            castling.discard("k")

    captured = state["board"][to_r][to_f]
    if captured == "R" and move["to"] == "a1":
        castling.discard("Q")
    elif captured == "R" and move["to"] == "h1":
        castling.discard("K")
    elif captured == "r" and move["to"] == "a8":
        castling.discard("q")
    elif captured == "r" and move["to"] == "h8":
        castling.discard("k")

    new_state["castling"] = "".join(c for c in "KQkq" if c in castling)

    # En passant target
    if piece.upper() == "P" and abs(to_r - from_r) == 2:
        mid_r = (from_r + to_r) // 2
        new_state["ep"] = coords_to_square(from_f, mid_r)
    else:
        new_state["ep"] = None

    # Halfmove / fullmove
    if piece.upper() == "P" or move.get("capture") or move.get("en_passant") or captured:
        new_state["halfmove"] = 0
    else:
        new_state["halfmove"] = state["halfmove"] + 1

    if state["turn"] == "b":
        new_state["fullmove"] = state["fullmove"] + 1
    new_state["turn"] = opponent(state["turn"])
    return new_state


def is_legal_move(state: dict[str, Any], move: dict[str, Any]) -> bool:
    color = state["turn"]
    piece = piece_at(state, move["from"])
    if not piece or color_of(piece) != color:
        return False

    # Castling safety: king not in check, path not attacked
    if move.get("castle"):
        if is_in_check(state, color):
            return False
        from_f, from_r = square_to_coords(move["from"])
        to_f, to_r = square_to_coords(move["to"])
        step = 1 if to_f > from_f else -1
        for f in range(from_f, to_f + step, step):
            if is_square_attacked(state, f, from_r, opponent(color)):
                return False

    try:
        next_state = apply_move_raw(state, move)
    except ValueError:
        return False
    return not is_in_check(next_state, color)


def generate_legal_moves(state: dict[str, Any]) -> list[dict[str, Any]]:
    color = state["turn"]
    own = WHITE_PIECES if color == "w" else BLACK_PIECES
    legal: list[dict[str, Any]] = []
    for rank_i in range(8):
        for file_i in range(8):
            piece = state["board"][rank_i][file_i]
            if piece not in own:
                continue
            for move in _pseudo_moves_from(state, file_i, rank_i):
                if is_legal_move(state, move):
                    legal.append(move)
    return legal


def move_uci(move: dict[str, Any]) -> str:
    promo = move.get("promotion")
    return move["from"] + move["to"] + (promo.lower() if promo else "")


def find_move(state: dict[str, Any], from_sq: str, to_sq: str, promotion: str | None = None) -> dict[str, Any] | None:
    for move in generate_legal_moves(state):
        if move["from"] != from_sq or move["to"] != to_sq:
            continue
        if promotion:
            if (move.get("promotion") or "").lower() == promotion.lower():
                return move
        elif not move.get("promotion"):
            return move
        else:
            # Default to queen promotion if unspecified
            if (move.get("promotion") or "").lower() == ("q" if state["turn"] == "b" else "Q").lower():
                return move
    # If promotion needed and none matched with default, try queen explicitly
    if promotion is None:
        for move in generate_legal_moves(state):
            if move["from"] == from_sq and move["to"] == to_sq and move.get("promotion"):
                promo = move["promotion"]
                if promo.lower() == "q":
                    return move
    return None


def board_matrix(state: dict[str, Any]) -> list[list[str | None]]:
    return [row[:] for row in state["board"]]


def evaluate_material(state: dict[str, Any]) -> int:
    score = 0
    for rank_i in range(8):
        for file_i in range(8):
            piece = state["board"][rank_i][file_i]
            if not piece:
                continue
            value = PIECE_VALUES[piece.upper()]
            score += value if is_white(piece) else -value
    return score


def status(state: dict[str, Any]) -> dict[str, Any]:
    moves = generate_legal_moves(state)
    in_check = is_in_check(state, state["turn"])
    if not moves:
        if in_check:
            return {
                "result": "checkmate",
                "winner_color": opponent(state["turn"]),
                "in_check": True,
                "legal_move_count": 0,
            }
        return {
            "result": "stalemate",
            "winner_color": None,
            "in_check": False,
            "legal_move_count": 0,
        }
    if state["halfmove"] >= 100:
        return {
            "result": "draw",
            "winner_color": None,
            "in_check": in_check,
            "legal_move_count": len(moves),
            "draw_reason": "fifty_move",
        }
    return {
        "result": None,
        "winner_color": None,
        "in_check": in_check,
        "legal_move_count": len(moves),
    }
