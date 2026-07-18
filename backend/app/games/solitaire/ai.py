"""Klondike solitaire move chooser for Hint / Watch learn mode."""

from __future__ import annotations

from typing import Any

from app.games.solitaire.cards import (
    can_stack_on_foundation,
    can_stack_on_tableau,
    is_valid_tableau_run,
)


def choose_action(
    state: dict, *, use_history: bool = True
) -> tuple[dict[str, Any] | None, str]:
    """
    Pick the next coaching move.

    Returns (action, reason) or (None, reason) when stuck.

    use_history: when False (Hint), ignore Watch cycle memory so we always
    report a currently legal suggestion if one exists.
    """
    if state.get("phase") != "playing":
        return None, "Game is not in progress"

    history = list(state.get("autoplay_history") or []) if use_history else []

    # 1. Ace / Two to foundation
    move = _first_allowed(history, _foundation_moves(state, ranks={"A", "2"}))
    if move:
        return move, "Move Aces and Twos to the foundations"

    # 2. Tableau move that exposes a face-down card
    move = _first_allowed(history, _expose_tableau_moves(state))
    if move:
        return move, "Expose a face-down card"

    # 3. Other foundation moves
    move = _first_allowed(history, _foundation_moves(state, ranks=None))
    if move:
        return move, "Build up the foundation"

    # 4. Waste / productive tableau builds
    move = _first_allowed(history, _productive_tableau_moves(state))
    if move:
        return move, "Build the tableau"

    # 5. Other legal tableau rearrangements (still block immediate reverse when watching)
    move = _first_allowed(history, _rearrange_tableau_moves(state))
    if move:
        return move, "Build the tableau"

    # 6. Draw from stock — always allowed while cards remain (not history-blocked)
    if state["stock"]:
        return {"type": "draw"}, "Draw from the stock"

    # 7. Recycle waste; allow a couple of empty passes before giving up
    if state["waste"] and not state["stock"]:
        if int(state.get("autoplay_stock_passes") or 0) < 2 or not use_history:
            return {"type": "reset_stock"}, "Recycle the waste pile"

    return None, "No useful moves — try a new game"


def action_signature(action: dict[str, Any]) -> str:
    """Stable id for cycle detection."""
    return "|".join(
        str(action.get(k, ""))
        for k in ("type", "source", "source_index", "card_index", "target_col")
    )


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


def _first_allowed(
    history: list[str], moves: list[dict[str, Any]]
) -> dict[str, Any] | None:
    for move in moves:
        if not _is_blocked(move, history):
            return move
    return None


def _is_blocked(action: dict[str, Any], history: list[str]) -> bool:
    """Block only immediate reverses / last identical card transfer — never draws."""
    if not history:
        return False
    if action.get("type") in ("draw", "reset_stock"):
        return False

    sig = action_signature(action)
    # Exact repeat of the last card move
    if history[-1] == sig:
        return True
    # Immediate reverse of the last transfer
    if _is_reverse_of(action, history[-1]):
        return True
    return False


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
            # Moving from foundation right after any foundation move — only block
            # if it's undoing the same pile we just built
            return True

    # Just moved onto tableau, don't immediately send that same source top to foundation
    # (too aggressive for waste→tableau→foundation which is good). Only block
    # tableau→tableau then foundation from the destination column's new top when
    # it reverses a foundation pull — handled above.

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


def _productive_tableau_moves(state: dict) -> list[dict[str, Any]]:
    """Waste plays and moves that empty a column / place King usefully."""
    moves: list[dict[str, Any]] = []

    if state["waste"]:
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
    Needed when they unlock later play; Watch history blocks bouncing back.
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
