"""Klondike solitaire move chooser for Hint / Watch learn mode."""

from __future__ import annotations

from typing import Any

from app.games.solitaire.cards import (
    SUITS,
    can_stack_on_foundation,
    can_stack_on_tableau,
    is_valid_tableau_run,
)


def choose_action(state: dict) -> tuple[dict[str, Any] | None, str]:
    """
    Pick the next coaching move.

    Returns (action, reason) or (None, reason) when stuck.
    """
    if state.get("phase") != "playing":
        return None, "Game is not in progress"

    # 1. Ace / Two to foundation
    move = _find_foundation_move(state, ranks={"A", "2"})
    if move:
        return move, "Move Aces and Twos to the foundations"

    # 2. Tableau move that exposes a face-down card
    move = _find_expose_tableau_move(state)
    if move:
        return move, "Expose a face-down card"

    # 3. Other foundation moves
    move = _find_foundation_move(state, ranks=None)
    if move:
        return move, "Build up the foundation"

    # 4. Tableau builds / King onto empty column
    move = _find_tableau_build_move(state)
    if move:
        return move, "Build the tableau"

    # 5. Draw from stock
    if state["stock"]:
        return {"type": "draw"}, "Draw from the stock"

    # 6. Recycle waste into stock
    if state["waste"]:
        return {"type": "reset_stock"}, "Recycle the waste pile"

    return None, "No useful moves — try a new game"


def _find_foundation_move(
    state: dict, ranks: set[str] | None
) -> dict[str, Any] | None:
    # Prefer waste, then tableau tops
    if state["waste"]:
        card = state["waste"][-1]
        if ranks is None or card["rank"] in ranks:
            if can_stack_on_foundation(card, state["foundations"][card["suit"]]):
                return {"type": "move_to_foundation", "source": "waste"}

    for col_idx, col in enumerate(state["tableau"]):
        if not col or not col[-1]["face_up"]:
            continue
        card = col[-1]
        if ranks is not None and card["rank"] not in ranks:
            continue
        if can_stack_on_foundation(card, state["foundations"][card["suit"]]):
            return {
                "type": "move_to_foundation",
                "source": "tableau",
                "source_index": col_idx,
            }
    return None


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


def _find_expose_tableau_move(state: dict) -> dict[str, Any] | None:
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
                    return {
                        "type": "move_to_tableau",
                        "source": "tableau",
                        "source_index": src_idx,
                        "card_index": card_index,
                        "target_col": tgt_idx,
                    }
    return None


def _find_tableau_build_move(state: dict) -> dict[str, Any] | None:
    # Waste onto tableau
    if state["waste"]:
        card = state["waste"][-1]
        for tgt_idx in range(7):
            if _can_place_on_tableau(state, card, tgt_idx):
                return {
                    "type": "move_to_tableau",
                    "source": "waste",
                    "source_index": None,
                    "card_index": 0,
                    "target_col": tgt_idx,
                }

    # Tableau to tableau (prefer moving onto non-empty; kings to empty)
    king_to_empty: dict[str, Any] | None = None
    for src_idx, col in enumerate(state["tableau"]):
        for card_index, card in enumerate(col):
            if not card["face_up"]:
                continue
            run = col[card_index:]
            if not is_valid_tableau_run(run):
                continue
            # Skip no-op single-card slides that don't change structure usefully:
            # moving an entire face-up column onto empty as King is allowed below.
            for tgt_idx in range(7):
                if tgt_idx == src_idx:
                    continue
                if not _can_place_on_tableau(state, card, tgt_idx):
                    continue
                action = {
                    "type": "move_to_tableau",
                    "source": "tableau",
                    "source_index": src_idx,
                    "card_index": card_index,
                    "target_col": tgt_idx,
                }
                target = state["tableau"][tgt_idx]
                if not target:
                    # Only park a King on empty; prefer ones that free a column
                    if card["rank"] == "K" and card_index > 0:
                        return action
                    if card["rank"] == "K" and king_to_empty is None:
                        king_to_empty = action
                    continue
                return action

    if king_to_empty:
        return king_to_empty

    # Foundation back to tableau only if it enables a build (rare coaching move)
    for suit_idx, suit in enumerate(SUITS):
        foundation = state["foundations"][suit]
        if not foundation:
            continue
        card = foundation[-1]
        for tgt_idx in range(7):
            if _can_place_on_tableau(state, card, tgt_idx):
                # Only if target has cards (don't pull King from foundation to empty)
                if state["tableau"][tgt_idx]:
                    return {
                        "type": "move_to_tableau",
                        "source": "foundation",
                        "source_index": suit_idx,
                        "card_index": 0,
                        "target_col": tgt_idx,
                    }
    return None
