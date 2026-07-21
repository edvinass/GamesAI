"""Klondike solitaire move chooser for Hint / Watch learn mode."""

from __future__ import annotations

from typing import Any

from app.games.solitaire.cards import (
    can_stack_on_foundation,
    can_stack_on_tableau,
    is_valid_tableau_run,
)

# How many recent transfers to check for reverse cycles.
_HISTORY_BLOCK_WINDOW = 8
# Mid-game coaching solvability budget (deal filter uses a larger budget).
_SOLVE_MAX_NODES = 40_000

_UNWINNABLE_REASON = "This position looks unwinnable — try a new game"
_STUCK_REASON = "No useful moves — try a new game"


def choose_action(
    state: dict, *, use_history: bool = True
) -> tuple[dict[str, Any] | None, str]:
    """
    Pick the next coaching move.

    Returns (action, reason) or (None, reason) when stuck / unwinnable.

    use_history: when False (Hint), ignore Watch cycle memory so we always
    report a currently legal suggestion if one exists. Still blocks reversing
    the player's last tableau transfer and still detects unwinnable positions.
    """
    if state.get("phase") != "playing":
        return None, "Game is not in progress"

    if state.get("unwinnable"):
        return None, _UNWINNABLE_REASON

    history = list(state.get("autoplay_history") or []) if use_history else []
    revisiting = False
    if use_history:
        revisiting = _note_board_visit(state)

    # 1. Ace / Two to foundation
    move = _first_allowed(state, history, _foundation_moves(state, ranks={"A", "2"}))
    if move:
        return move, "Move Aces and Twos to the foundations"

    # 2. Tableau move that exposes a face-down card
    move = _first_allowed(state, history, _expose_tableau_moves(state))
    if move:
        return move, "Expose a face-down card"

    # 3. Other foundation moves
    move = _first_allowed(state, history, _foundation_moves(state, ranks=None))
    if move:
        return move, "Build up the foundation"

    # 4. Waste / productive tableau builds
    # When we've returned to a board already seen this Watch session, skip
    # tableau reshuffles — they are what create loops.
    if not revisiting:
        move = _first_allowed(state, history, _productive_tableau_moves(state))
        if move:
            return move, "Build the tableau"

        # 5. Other legal tableau rearrangements
        move = _first_allowed(state, history, _rearrange_tableau_moves(state))
        if move:
            return move, "Build the tableau"
    else:
        # Still allow waste → tableau (progress from stock cycle)
        move = _first_allowed(state, history, _waste_to_tableau_moves(state))
        if move:
            return move, "Build the tableau"

    # 6. Draw from stock — always allowed while cards remain (not history-blocked)
    if state["stock"]:
        return {"type": "draw"}, "Draw from the stock"

    # 7. Recycle waste; allow a couple of empty passes before giving up
    if state["waste"] and not state["stock"]:
        if int(state.get("autoplay_stock_passes") or 0) < 2 or not use_history:
            return {"type": "reset_stock"}, "Recycle the waste pile"

    return _stuck_result(state)


def action_signature(action: dict[str, Any]) -> str:
    """Stable id for cycle detection."""
    return "|".join(
        str(action.get(k, ""))
        for k in ("type", "source", "source_index", "card_index", "target_col")
    )


def board_fingerprint(state: dict) -> str:
    """Compact id of the full deal position for Watch loop detection."""
    tab_parts: list[str] = []
    for col in state["tableau"]:
        tab_parts.append(
            ",".join(
                f"{c['rank']}{c['suit'][0]}{'U' if c['face_up'] else 'D'}" for c in col
            )
        )
    found = ",".join(
        str(len(state["foundations"][s]))
        for s in ("hearts", "diamonds", "clubs", "spades")
    )
    waste = ",".join(f"{c['rank']}{c['suit'][0]}" for c in state["waste"])
    stock = ",".join(f"{c['rank']}{c['suit'][0]}" for c in state["stock"])
    return ";".join(("|".join(tab_parts), found, waste, stock))


def record_autoplay_action(state: dict, action: dict[str, Any]) -> None:
    """Append move to history (mutates state)."""
    history = list(state.get("autoplay_history") or [])
    # Don't record draws — every draw has the same signature and would block the stock
    if action.get("type") == "draw":
        return
    history.append(action_signature(action))
    state["autoplay_history"] = history[-24:]

    if action.get("type") in ("move_to_tableau", "move_to_foundation"):
        state["autoplay_stock_passes"] = 0
    elif action.get("type") == "reset_stock":
        state["autoplay_stock_passes"] = int(state.get("autoplay_stock_passes") or 0) + 1


def clear_autoplay_memory(state: dict) -> None:
    state["autoplay_history"] = []
    state["autoplay_stock_passes"] = 0
    state["autoplay_seen"] = []


def _note_board_visit(state: dict) -> bool:
    """
    Record the current board. Returns True if Watch has been here before
    (a cycle), in which case tableau reshuffles should be skipped.
    """
    fp = board_fingerprint(state)
    seen = list(state.get("autoplay_seen") or [])
    if fp in seen:
        return True
    seen.append(fp)
    state["autoplay_seen"] = seen[-64:]
    return False


def _stuck_result(state: dict) -> tuple[None, str]:
    """When heuristics find nothing, check whether the position is unwinnable."""
    if state.get("unwinnable"):
        return None, _UNWINNABLE_REASON
    from app.games.solitaire.solver import is_solvable

    if not is_solvable(state, max_nodes=_SOLVE_MAX_NODES):
        state["unwinnable"] = True
        return None, _UNWINNABLE_REASON
    return None, _STUCK_REASON


def _first_allowed(
    state: dict, history: list[str], moves: list[dict[str, Any]]
) -> dict[str, Any] | None:
    for move in moves:
        if not _is_blocked(move, history) and not _is_blocked_by_last_action(move, state):
            return move
    return None


def _is_blocked(action: dict[str, Any], history: list[str]) -> bool:
    """Block recent reverses / last identical card transfer — never draws."""
    if not history:
        return False
    if action.get("type") in ("draw", "reset_stock"):
        return False

    sig = action_signature(action)
    # Exact repeat of the last card move only (waste→same column can repeat
    # legitimately with different cards after draws).
    if history[-1] == sig:
        return True

    window = history[-_HISTORY_BLOCK_WINDOW:]
    # Reverse of any recent tableau transfer (catches A→B … B→A with gaps)
    if action.get("type") == "move_to_tableau" and action.get("source") == "tableau":
        for prev in window:
            if _is_reverse_of(action, prev):
                return True
    elif _is_reverse_of(action, history[-1]):
        return True

    return False


def _is_blocked_by_last_action(action: dict[str, Any], state: dict) -> bool:
    """
    Block reversing the most recent applied transfer.

    Used for Hint (no Watch history) so suggesting A→B then B→A is avoided
    after the player follows the previous hint / makes that move.
    """
    if action.get("type") in ("draw", "reset_stock"):
        return False
    last = state.get("last_action") or {}
    if last.get("type") not in ("move_to_tableau", "move_to_foundation"):
        return False
    return _is_reverse_of(action, action_signature(last))


def _is_reverse_of(action: dict[str, Any], prev_sig: str) -> bool:
    parts = prev_sig.split("|")
    if len(parts) < 5:
        return False
    prev_type, prev_source, prev_src_idx, _prev_card_idx, prev_tgt = parts

    # Tableau A→B then B→A
    if (
        action.get("type") == "move_to_tableau"
        and prev_type == "move_to_tableau"
        and action.get("source") == "tableau"
        and prev_source == "tableau"
        and str(action.get("source_index", "")) == prev_tgt
        and str(action.get("target_col", "")) == prev_src_idx
    ):
        return True

    # Just put on foundation, don't pull same suit back to tableau immediately
    if prev_type == "move_to_foundation" and action.get("type") == "move_to_tableau":
        if action.get("source") == "foundation":
            return True

    return False


def _foundation_moves(state: dict, ranks: set[str] | None) -> list[dict[str, Any]]:
    moves: list[dict[str, Any]] = []
    if state["waste"]:
        card = state["waste"][-1]
        if ranks is None or card["rank"] in ranks:
            if can_stack_on_foundation(card, state["foundations"][card["suit"]]):
                moves.append({"type": "move_to_foundation", "source": "waste"})

    for col_idx, col in enumerate(state["tableau"]):
        if not col or not col[-1]["face_up"]:
            continue
        card = col[-1]
        if ranks is not None and card["rank"] not in ranks:
            continue
        if can_stack_on_foundation(card, state["foundations"][card["suit"]]):
            moves.append(
                {
                    "type": "move_to_foundation",
                    "source": "tableau",
                    "source_index": col_idx,
                }
            )
    return moves


def _exposes_face_down(col: list, card_index: int) -> bool:
    if card_index <= 0:
        return False
    return not col[card_index - 1]["face_up"]


def _can_place_on_tableau(state: dict, first_card: dict, target_col: int) -> bool:
    target = state["tableau"][target_col]
    if not target:
        return first_card["rank"] == "K"
    top = target[-1]
    if not top["face_up"]:
        return False
    return can_stack_on_tableau(first_card, top)


def _expose_tableau_moves(state: dict) -> list[dict[str, Any]]:
    moves: list[dict[str, Any]] = []
    for src_idx, col in enumerate(state["tableau"]):
        for card_index, card in enumerate(col):
            if not card["face_up"]:
                continue
            run = col[card_index:]
            if not is_valid_tableau_run(run):
                continue
            if not _exposes_face_down(col, card_index):
                continue
            for tgt_idx in range(7):
                if tgt_idx == src_idx:
                    continue
                if _can_place_on_tableau(state, card, tgt_idx):
                    moves.append(
                        {
                            "type": "move_to_tableau",
                            "source": "tableau",
                            "source_index": src_idx,
                            "card_index": card_index,
                            "target_col": tgt_idx,
                        }
                    )
    return moves


def _waste_to_tableau_moves(state: dict) -> list[dict[str, Any]]:
    moves: list[dict[str, Any]] = []
    if not state["waste"]:
        return moves
    card = state["waste"][-1]
    for tgt_idx in range(7):
        if _can_place_on_tableau(state, card, tgt_idx):
            moves.append(
                {
                    "type": "move_to_tableau",
                    "source": "waste",
                    "source_index": None,
                    "card_index": 0,
                    "target_col": tgt_idx,
                }
            )
    return moves


def _productive_tableau_moves(state: dict) -> list[dict[str, Any]]:
    """Waste plays and moves that empty a column / place King usefully."""
    moves: list[dict[str, Any]] = []
    moves.extend(_waste_to_tableau_moves(state))

    for src_idx, col in enumerate(state["tableau"]):
        for card_index, card in enumerate(col):
            if not card["face_up"]:
                continue
            run = col[card_index:]
            if not is_valid_tableau_run(run):
                continue

            empties_column = card_index == 0
            exposes = _exposes_face_down(col, card_index)
            if not empties_column and not exposes:
                continue

            for tgt_idx in range(7):
                if tgt_idx == src_idx:
                    continue
                if not _can_place_on_tableau(state, card, tgt_idx):
                    continue
                target = state["tableau"][tgt_idx]
                if not target:
                    # Don't shuffle a whole King pile between empty columns
                    if card["rank"] != "K" or empties_column:
                        continue
                moves.append(
                    {
                        "type": "move_to_tableau",
                        "source": "tableau",
                        "source_index": src_idx,
                        "card_index": card_index,
                        "target_col": tgt_idx,
                    }
                )

    return moves


def _rearrange_tableau_moves(state: dict) -> list[dict[str, Any]]:
    """
    Remaining legal tableau→tableau slides (e.g. 5♥ between two 6s).
    Needed when they unlock later play; Watch history / board fingerprints
    block bouncing back.
    """
    moves: list[dict[str, Any]] = []
    for src_idx, col in enumerate(state["tableau"]):
        for card_index, card in enumerate(col):
            if not card["face_up"]:
                continue
            run = col[card_index:]
            if not is_valid_tableau_run(run):
                continue
            # Skip ones already covered as expose / empty-column
            if _exposes_face_down(col, card_index) or card_index == 0:
                continue
            for tgt_idx in range(7):
                if tgt_idx == src_idx:
                    continue
                if not _can_place_on_tableau(state, card, tgt_idx):
                    continue
                # Never use rearrange for empty-column King parking
                if not state["tableau"][tgt_idx]:
                    continue
                moves.append(
                    {
                        "type": "move_to_tableau",
                        "source": "tableau",
                        "source_index": src_idx,
                        "card_index": card_index,
                        "target_col": tgt_idx,
                    }
                )
    return moves
