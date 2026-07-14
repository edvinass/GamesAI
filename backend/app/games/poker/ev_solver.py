"""EV-based action selection for hard poker AI."""

from __future__ import annotations

import random
from typing import Any

from app.games.poker.equity import estimate_equity_from_state
from app.games.poker.opponent_model import aggregate_opponent_profile
from app.games.poker.postflop_strategy import (
    board_texture,
    candidate_pot_fractions,
    spr,
)
from app.games.poker.preflop_strategy import (
    preflop_open_size_bb,
    preflop_reraise_multiplier,
)
from app.games.poker.ranges import preflop_hand_strength

Action = dict[str, Any]


def _bet_to_call(state: dict, player_id: str) -> int:
    p = state["players"][player_id]
    return max(0, state["current_bet"] - p["bet_this_round"])


def _pot_total(state: dict) -> int:
    return sum(p["total_bet_hand"] for p in state["players"].values())


def _stack_bb(state: dict, player_id: str) -> float:
    bb = state["settings"]["big_blind"]
    return state["players"][player_id]["chips"] / max(1, bb)


def _legal_raise_targets(state: dict, player_id: str) -> list[int]:
    from app.games.poker.engine import PokerEngine

    return PokerEngine()._legal_raise_to_amounts(state, player_id)


def _active_in_hand(state: dict) -> list[str]:
    return [
        pid
        for pid in state["seat_order"]
        if state["players"][pid]["status"] in ("active", "all_in")
    ]


def _position_score(state: dict, player_id: str) -> float:
    seat_order = state["seat_order"]
    dealer_idx = state["dealer_index"]
    if dealer_idx < 0 or player_id not in seat_order:
        return 0.5

    active = _active_in_hand(state)
    if len(active) <= 1:
        return 1.0

    player_idx = seat_order.index(player_id)
    seats_from_btn = (player_idx - dealer_idx) % len(seat_order)
    active_distances = [
        (seat_order.index(pid) - dealer_idx) % len(seat_order) for pid in active
    ]
    if not active_distances:
        return 0.5
    max_dist = max(active_distances)
    if max_dist == 0:
        return 1.0
    return 1.0 - (seats_from_btn / max_dist)


def _facing_raise(state: dict, to_call: int) -> bool:
    bb = state["settings"]["big_blind"]
    return to_call > 0 and state["current_bet"] > bb


def _facing_3bet_plus(state: dict, to_call: int) -> bool:
    bb = state["settings"]["big_blind"]
    return to_call > 0 and state["current_bet"] > bb * 3


def _deterministic_rng(state: dict, player_id: str) -> random.Random:
    """Seed RNG from game state for reproducible hard-mode decisions."""
    seed = (
        state.get("hand_number", 0) * 997
        + hash(player_id) % 10000
        + len(state.get("community_cards", [])) * 31
        + state.get("current_bet", 0)
        + sum(p["total_bet_hand"] for p in state["players"].values())
    )
    return random.Random(seed & 0xFFFFFFFF)


def _closest_legal_raise(legal_raises: list[int], target: int) -> int | None:
    if not legal_raises:
        return None
    return min(legal_raises, key=lambda amount: abs(amount - target))


def _estimate_fold_probability(
    opponents: dict[str, float],
    *,
    bet_fraction: float,
    equity: float,
    is_bluff: bool,
    facing_3bet: bool,
) -> float:
    base = opponents.get("fold_to_bet_rate", 0.45)
    if is_bluff:
        base += 0.08
    if bet_fraction >= 0.75:
        base += 0.06
    elif bet_fraction >= 0.55:
        base += 0.03
    if opponents.get("is_nit"):
        base += 0.1
    if opponents.get("is_station"):
        base -= 0.15
    if facing_3bet:
        base -= 0.12
    if equity > 0.7 and not is_bluff:
        base -= 0.05
    return max(0.05, min(0.85, base))


def _action_to_raise_amount(
    state: dict,
    player_id: str,
    action: Action,
) -> int | None:
    p = state["players"][player_id]
    if action["type"] == "raise":
        return int(action["amount"])
    if action["type"] == "all_in":
        return p["bet_this_round"] + p["chips"]
    return None


def _ev_of_action(
    state: dict,
    player_id: str,
    action: Action,
    *,
    equity: float,
    to_call: int,
    opponents: dict[str, float],
    position: float,
    cfg: dict[str, float | int],
) -> float:
    p = state["players"][player_id]
    pot = _pot_total(state)
    bb = state["settings"]["big_blind"]

    if action["type"] == "fold":
        return 0.0

    if action["type"] in ("check", "call"):
        cost = to_call
        win_pot = pot + cost
        return equity * win_pot - (1.0 - equity) * cost

    raise_to = _action_to_raise_amount(state, player_id, action)
    if raise_to is None:
        return -1.0

    raise_cost = raise_to - p["bet_this_round"]
    if raise_cost <= 0:
        return -1.0

    bet_fraction = raise_cost / max(1, pot + to_call)
    is_bluff = equity < 0.42
    fold_prob = _estimate_fold_probability(
        opponents,
        bet_fraction=bet_fraction,
        equity=equity,
        is_bluff=is_bluff,
        facing_3bet=_facing_3bet_plus(state, to_call),
    )

    pot_if_fold = pot + to_call
    pot_if_call = pot + to_call + raise_cost + to_call
    ev_when_called = equity * pot_if_call - (1.0 - equity) * raise_cost
    return fold_prob * pot_if_fold + (1.0 - fold_prob) * ev_when_called


def _candidate_actions(
    state: dict,
    player_id: str,
    *,
    equity: float,
    to_call: int,
    position: float,
    opponents: dict[str, float],
    cfg: dict[str, float | int],
) -> list[Action]:
    p = state["players"][player_id]
    legal_raises = _legal_raise_targets(state, player_id)
    pot = _pot_total(state)
    bb = state["settings"]["big_blind"]
    stack_bb = _stack_bb(state, player_id)
    community = state.get("community_cards", [])
    texture = board_texture(community)
    hole = p["hole_cards"]

    candidates: list[Action] = []

    if to_call > 0:
        candidates.append({"type": "fold"})
    else:
        candidates.append({"type": "check"})

    if to_call > 0 and to_call < p["chips"]:
        candidates.append({"type": "call"})

    # Facing a bet with very weak equity: no bluff-raises.
    can_raise = to_call == 0 or equity >= 0.45
    raise_targets: set[int] = set()

    if can_raise and state["phase"] == "preflop":
        if to_call == 0:
            open_bb = preflop_open_size_bb(position, stack_bb=stack_bb)
            target = p["bet_this_round"] + int(bb * open_bb)
            chosen = _closest_legal_raise(legal_raises, target)
            if chosen:
                raise_targets.add(chosen)
        elif _facing_raise(state, to_call):
            strength = preflop_hand_strength(hole)
            mult = preflop_reraise_multiplier(
                hand_strength=strength,
                facing_3bet=_facing_3bet_plus(state, to_call),
                value_threshold=0.72,
            )
            if mult > 0 and strength >= 0.65:
                target = p["bet_this_round"] + to_call + int(to_call * mult)
                chosen = _closest_legal_raise(legal_raises, target)
                if chosen:
                    raise_targets.add(chosen)
    elif can_raise:
        is_bluff = equity < 0.30 and to_call == 0 and opponents.get("fold_to_bet_rate", 0.45) > 0.52
        fractions = candidate_pot_fractions(
            equity=equity,
            texture=texture,
            position=position,
            to_call=to_call,
            is_bluff=is_bluff,
        )
        for frac in fractions:
            if to_call == 0:
                target = p["bet_this_round"] + int(pot * frac)
            else:
                target = p["bet_this_round"] + to_call + int((pot + to_call) * frac)
            chosen = _closest_legal_raise(legal_raises, target)
            if chosen and chosen > p["bet_this_round"]:
                raise_targets.add(chosen)

    if stack_bb <= 12 and equity >= 0.75:
        max_raise = p["bet_this_round"] + p["chips"]
        if legal_raises:
            raise_targets.add(legal_raises[-1])
        elif max_raise > state["current_bet"]:
            raise_targets.add(max_raise)

    if spr(state, player_id) <= 1.5 and equity >= 0.65:
        max_raise = p["bet_this_round"] + p["chips"]
        if legal_raises:
            raise_targets.add(legal_raises[-1])

    for amount in sorted(raise_targets):
        if amount >= p["bet_this_round"] + p["chips"]:
            candidates.append({"type": "all_in"})
        else:
            candidates.append({"type": "raise", "amount": amount})

    if legal_raises and equity >= 0.8 and to_call == 0:
        candidates.append({"type": "raise", "amount": legal_raises[-1]})

    return candidates


def choose_ev_action(
    state: dict,
    player_id: str,
    cfg: dict[str, float | int],
) -> Action:
    """Pick the highest-EV legal action using range-weighted equity."""
    p = state["players"][player_id]
    to_call = _bet_to_call(state, player_id)
    position = _position_score(state, player_id)
    opponents = aggregate_opponent_profile(state, player_id)
    rng = _deterministic_rng(state, player_id)

    iterations = int(cfg.get("ev_iterations", 800))
    equity = estimate_equity_from_state(
        state,
        player_id,
        iterations=iterations,
        rng=rng,
        use_ranges=True,
        opponents=opponents,
    )
    position_equity = min(1.0, equity + position * 0.03)

    stack_bb = _stack_bb(state, player_id)
    pot_odds = to_call / max(1, _pot_total(state) + to_call) if to_call > 0 else 0.0
    call_margin = float(cfg.get("call_margin", 0.04))

    if to_call > 0 and position_equity < pot_odds + call_margin - 0.02:
        if to_call >= p["chips"]:
            return {"type": "all_in"}
        return {"type": "fold"}

    if stack_bb <= 8 and to_call > 0:
        strength = preflop_hand_strength(p["hole_cards"]) if state["phase"] == "preflop" else position_equity
        if strength >= 0.78 or position_equity >= 0.70:
            return {"type": "all_in"}
        if to_call <= state["settings"]["big_blind"] and position_equity >= pot_odds:
            return {"type": "call"}
        return {"type": "fold"}

    candidates = _candidate_actions(
        state,
        player_id,
        equity=position_equity,
        to_call=to_call,
        position=position,
        opponents=opponents,
        cfg=cfg,
    )

    best_action = candidates[0]
    best_ev = float("-inf")

    for action in candidates:
        ev = _ev_of_action(
            state,
            player_id,
            action,
            equity=position_equity,
            to_call=to_call,
            opponents=opponents,
            position=position,
            cfg=cfg,
        )
        if ev > best_ev:
            best_ev = ev
            best_action = action

    if to_call > 0 and best_action["type"] == "fold":
        if position_equity < pot_odds + call_margin:
            return {"type": "fold"}
        call_ev = _ev_of_action(
            state,
            player_id,
            {"type": "call"},
            equity=position_equity,
            to_call=to_call,
            opponents=opponents,
            position=position,
            cfg=cfg,
        )
        if call_ev > 0:
            return {"type": "call"}
        if to_call >= p["chips"]:
            return {"type": "all_in"}
        return {"type": "fold"}

    if best_action["type"] == "check" and to_call == 0:
        strength = preflop_hand_strength(p["hole_cards"])
        if state["phase"] == "preflop" and strength >= 0.62 and position >= 0.6:
            legal = _legal_raise_targets(state, player_id)
            if legal:
                bb = state["settings"]["big_blind"]
                target = p["bet_this_round"] + int(bb * preflop_open_size_bb(position, stack_bb=stack_bb))
                chosen = _closest_legal_raise(legal, target)
                if chosen:
                    return {"type": "raise", "amount": chosen}

    return best_action
