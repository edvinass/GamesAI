"""Equity-based poker AI with position, sizing, difficulty, and opponent modeling."""

from __future__ import annotations

import random
from typing import Any

from app.games.poker.equity import estimate_equity_from_state
from app.games.poker.opponent_model import aggregate_opponent_profile

AI_DIFFICULTIES = ("easy", "medium", "hard")

DIFFICULTY_CONFIG: dict[str, dict[str, float | int]] = {
    "easy": {
        "mc_iterations": 200,
        "call_margin": -0.05,
        "raise_threshold": 0.62,
        "value_raise_threshold": 0.72,
        "bluff_rate": 0.18,
        "mistake_rate": 0.22,
        "open_equity": 0.42,
    },
    "medium": {
        "mc_iterations": 400,
        "call_margin": 0.03,
        "raise_threshold": 0.58,
        "value_raise_threshold": 0.68,
        "bluff_rate": 0.10,
        "mistake_rate": 0.08,
        "open_equity": 0.48,
    },
    "hard": {
        "mc_iterations": 700,
        "call_margin": 0.06,
        "raise_threshold": 0.55,
        "value_raise_threshold": 0.64,
        "bluff_rate": 0.06,
        "mistake_rate": 0.02,
        "open_equity": 0.52,
    },
}


def normalize_ai_difficulty(value: str | None) -> str:
    if value in DIFFICULTY_CONFIG:
        return value
    # chess uses "medium"; tetris uses "normal" — accept both aliases
    aliases = {"normal": "medium"}
    normalized = aliases.get(str(value or "").lower(), str(value or "").lower())
    if normalized in DIFFICULTY_CONFIG:
        return normalized
    return "medium"


def get_ai_config(difficulty: str | None) -> dict[str, float | int]:
    return DIFFICULTY_CONFIG[normalize_ai_difficulty(difficulty)]


def _bet_to_call(state: dict, player_id: str) -> int:
    p = state["players"][player_id]
    return max(0, state["current_bet"] - p["bet_this_round"])


def _pot_total(state: dict) -> int:
    return sum(p["total_bet_hand"] for p in state["players"].values())


def _pot_odds(state: dict, to_call: int) -> float:
    if to_call <= 0:
        return 0.0
    return to_call / max(1, _pot_total(state) + to_call)


def _legal_raise_targets(state: dict, player_id: str) -> list[int]:
    from app.games.poker.engine import PokerEngine

    return PokerEngine()._legal_raise_to_amounts(state, player_id)


def _stack_bb(state: dict, player_id: str) -> float:
    bb = state["settings"]["big_blind"]
    return state["players"][player_id]["chips"] / max(1, bb)


def _active_in_hand(state: dict) -> list[str]:
    return [
        pid
        for pid in state["seat_order"]
        if state["players"][pid]["status"] in ("active", "all_in")
    ]


def _position_score(state: dict, player_id: str) -> float:
    """0.0 = earliest position, 1.0 = button (best)."""
    seat_order = state["seat_order"]
    dealer_idx = state["dealer_index"]
    if dealer_idx < 0 or player_id not in seat_order:
        return 0.5

    active = _active_in_hand(state)
    if len(active) <= 1:
        return 1.0

    player_idx = seat_order.index(player_id)
    seats_from_btn = (player_idx - dealer_idx) % len(seat_order)

    active_distances = []
    for pid in active:
        idx = seat_order.index(pid)
        active_distances.append((idx - dealer_idx) % len(seat_order))

    if not active_distances:
        return 0.5

    max_dist = max(active_distances)
    if max_dist == 0:
        return 1.0
    return 1.0 - (seats_from_btn / max_dist)


def _closest_legal_raise(legal_raises: list[int], target: int) -> int | None:
    if not legal_raises:
        return None
    return min(legal_raises, key=lambda amount: abs(amount - target))


def _facing_raise(state: dict, to_call: int) -> bool:
    bb = state["settings"]["big_blind"]
    return to_call > 0 and state["current_bet"] > bb


def _facing_3bet_plus(state: dict, to_call: int) -> bool:
    bb = state["settings"]["big_blind"]
    return to_call > 0 and state["current_bet"] > bb * 3


def _re_raise_equity_threshold(
    state: dict,
    to_call: int,
    cfg: dict[str, float | int],
) -> float:
    """Minimum equity required to re-raise rather than call."""
    base = float(cfg["value_raise_threshold"])
    if _facing_3bet_plus(state, to_call):
        return base + 0.08
    if _facing_raise(state, to_call):
        return base
    return float(cfg["raise_threshold"])


def _raise_commitment_fraction(state: dict, player_id: str, raise_to: int) -> float:
    p = state["players"][player_id]
    cost = raise_to - p["bet_this_round"]
    return cost / max(1, p["chips"])


def _pick_raise_amount(
    state: dict,
    player_id: str,
    *,
    equity: float,
    to_call: int,
    is_bluff: bool,
    position: float,
    cfg: dict[str, float | int],
) -> int | None:
    p = state["players"][player_id]
    legal_raises = _legal_raise_targets(state, player_id)
    if not legal_raises:
        return None

    pot = _pot_total(state)
    bb = state["settings"]["big_blind"]
    stack_bb = _stack_bb(state, player_id)

    if stack_bb <= 12:
        if equity >= float(cfg["value_raise_threshold"]) + 0.03:
            return legal_raises[-1]
        return None

    if to_call == 0:
        if state["phase"] == "preflop":
            open_size = bb * (2.2 + position * 1.8)
            target = p["bet_this_round"] + int(open_size)
        elif is_bluff:
            target = p["bet_this_round"] + int(pot * (0.55 + position * 0.1))
        elif equity >= float(cfg["value_raise_threshold"]):
            target = p["bet_this_round"] + int(pot * 0.7)
        else:
            target = p["bet_this_round"] + int(pot * 0.5)
    elif state["phase"] == "preflop" and _facing_raise(state, to_call):
        # Preflop re-raises: use multiples of the facing bet to avoid runaway pots.
        multiplier = 3.0 if equity >= float(cfg["value_raise_threshold"]) else 2.5
        target = p["bet_this_round"] + to_call + int(to_call * multiplier)
    else:
        if is_bluff:
            target = p["bet_this_round"] + to_call + int((pot + to_call) * 0.55)
        elif equity >= float(cfg["value_raise_threshold"]):
            target = p["bet_this_round"] + to_call + int((pot + to_call) * 0.55)
        else:
            return None

    chosen = _closest_legal_raise(legal_raises, target)
    if chosen is None or chosen <= p["bet_this_round"]:
        return None
    if _raise_commitment_fraction(state, player_id, chosen) > 0.35:
        if equity < float(cfg["value_raise_threshold"]) + 0.05:
            return None
    return chosen


def _should_bluff(
    state: dict,
    player_id: str,
    equity: float,
    to_call: int,
    position: float,
    cfg: dict[str, float | int],
    opponents: dict[str, float],
) -> bool:
    if to_call > 0:
        return False
    if equity > 0.35:
        return False
    if opponents.get("is_station"):
        return False

    bluff_rate = float(cfg["bluff_rate"])
    if opponents.get("fold_to_bet_rate", 0.45) > 0.55:
        bluff_rate += 0.08
    if opponents.get("is_nit"):
        bluff_rate += 0.05
    if position >= 0.7:
        bluff_rate += 0.06
    if state["phase"] == "river":
        bluff_rate *= 0.7

    return random.random() < bluff_rate


def _adjusted_open_equity(cfg: dict[str, float | int], position: float) -> float:
    base = float(cfg["open_equity"])
    return base - position * 0.12


def choose_poker_action(
    state: dict,
    player_id: str,
    difficulty: str | None = None,
) -> dict[str, Any]:
    difficulty = difficulty or state.get("settings", {}).get("ai_difficulty")
    cfg = get_ai_config(difficulty)

    p = state["players"][player_id]
    to_call = _bet_to_call(state, player_id)
    pot_odds = _pot_odds(state, to_call)
    position = _position_score(state, player_id)
    opponents = aggregate_opponent_profile(state, player_id)

    equity = estimate_equity_from_state(
        state,
        player_id,
        iterations=int(cfg["mc_iterations"]),
    )

    position_equity = min(1.0, equity + position * 0.04)
    call_threshold = pot_odds + float(cfg["call_margin"])
    is_bluff = _should_bluff(state, player_id, equity, to_call, position, cfg, opponents)

    if random.random() < float(cfg["mistake_rate"]):
        if to_call == 0:
            return {"type": "check"}
        if to_call <= state["settings"]["big_blind"]:
            return {"type": "call"}
        return {"type": "fold"}

    stack_bb = _stack_bb(state, player_id)
    if stack_bb <= 10 and to_call > 0:
        push_threshold = float(cfg["value_raise_threshold"]) - position * 0.04
        if _facing_3bet_plus(state, to_call):
            push_threshold += 0.06
        if position_equity >= push_threshold:
            return {"type": "all_in"}
        if to_call <= state["settings"]["big_blind"] and position_equity >= call_threshold:
            return {"type": "call"}
        return {"type": "fold"}

    if to_call == 0:
        open_equity = _adjusted_open_equity(cfg, position)
        if opponents.get("is_nit") and position >= 0.6:
            open_equity -= 0.04
        if opponents.get("is_station"):
            open_equity += 0.05

        if position_equity >= open_equity or is_bluff:
            raise_amount = _pick_raise_amount(
                state,
                player_id,
                equity=position_equity,
                to_call=0,
                is_bluff=is_bluff,
                position=position,
                cfg=cfg,
            )
            if raise_amount is not None:
                if raise_amount >= p["bet_this_round"] + p["chips"]:
                    return {"type": "all_in"}
                return {"type": "raise", "amount": raise_amount}
        return {"type": "check"}

    if position_equity < call_threshold and not is_bluff:
        if to_call <= state["settings"]["big_blind"] and position_equity >= call_threshold - 0.08:
            pass
        else:
            if p["chips"] <= to_call:
                return {"type": "fold"}
            return {"type": "fold"}

    re_raise_threshold = _re_raise_equity_threshold(state, to_call, cfg)
    can_bluff_raise = (
        is_bluff
        and opponents.get("fold_to_bet_rate", 0.45) > 0.5
        and not _facing_3bet_plus(state, to_call)
    )
    if position_equity >= re_raise_threshold or can_bluff_raise:
        raise_amount = _pick_raise_amount(
            state,
            player_id,
            equity=position_equity,
            to_call=to_call,
            is_bluff=can_bluff_raise,
            position=position,
            cfg=cfg,
        )
        if raise_amount is not None:
            if raise_amount >= p["bet_this_round"] + p["chips"]:
                return {"type": "all_in"}
            return {"type": "raise", "amount": raise_amount}

    if to_call >= p["chips"]:
        return {"type": "all_in"}
    return {"type": "call"}
