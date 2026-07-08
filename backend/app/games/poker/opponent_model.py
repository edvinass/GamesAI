"""Lightweight opponent tendency tracking for poker AI."""

from __future__ import annotations

from typing import Any

DEFAULT_STATS: dict[str, int] = {
    "faced_bet": 0,
    "fold_to_bet": 0,
    "calls": 0,
    "raises": 0,
    "checks": 0,
    "preflop_hands": 0,
    "preflop_voluntary": 0,
    "preflop_raises": 0,
}


def empty_stats() -> dict[str, int]:
    return dict(DEFAULT_STATS)


def ensure_opponent_stats(state: dict[str, Any]) -> dict[str, dict[str, int]]:
    if "opponent_stats" not in state:
        state["opponent_stats"] = {}
    return state["opponent_stats"]


def get_player_stats(state: dict[str, Any], player_id: str) -> dict[str, int]:
    stats_map = ensure_opponent_stats(state)
    if player_id not in stats_map:
        stats_map[player_id] = empty_stats()
    return stats_map[player_id]


def _bet_to_call(state: dict[str, Any], player_id: str) -> int:
    p = state["players"][player_id]
    return max(0, state["current_bet"] - p["bet_this_round"])


def record_action(
    state: dict[str, Any],
    player_id: str,
    action: dict[str, Any],
    *,
    to_call_before: int,
) -> None:
    """Update cumulative opponent stats after a player acts."""
    stats = get_player_stats(state, player_id)
    action_type = action.get("type")
    phase = state.get("phase", "preflop")

    if action_type == "fold":
        if to_call_before > 0:
            stats["faced_bet"] += 1
            stats["fold_to_bet"] += 1
    elif action_type == "call":
        stats["calls"] += 1
        if to_call_before > 0:
            stats["faced_bet"] += 1
        if phase == "preflop":
            stats["preflop_voluntary"] += 1
    elif action_type in ("raise", "all_in"):
        stats["raises"] += 1
        if phase == "preflop":
            stats["preflop_voluntary"] += 1
            stats["preflop_raises"] += 1
    elif action_type == "check":
        stats["checks"] += 1


def on_hand_started(state: dict[str, Any], eligible: list[str]) -> None:
    """Mark preflop hand participation for eligible players."""
    for pid in eligible:
        stats = get_player_stats(state, pid)
        stats["preflop_hands"] += 1


def get_opponent_profile(state: dict[str, Any], opponent_id: str) -> dict[str, float]:
    """Derive readable tendencies from raw stats."""
    stats = get_player_stats(state, opponent_id)
    faced = stats["faced_bet"]
    hands = max(1, stats["preflop_hands"])
    calls = stats["calls"]
    raises = stats["raises"]

    return {
        "fold_to_bet_rate": stats["fold_to_bet"] / max(1, faced),
        "vpip_rate": stats["preflop_voluntary"] / hands,
        "pfr_rate": stats["preflop_raises"] / hands,
        "aggression_factor": raises / max(1, calls),
        "is_station": calls > raises * 2 and stats["preflop_voluntary"] / hands > 0.35,
        "is_nit": stats["preflop_voluntary"] / hands < 0.18 and raises / hands < 0.08,
    }


def aggregate_opponent_profile(state: dict[str, Any], hero_id: str) -> dict[str, float]:
    """Blend profiles of all non-hero opponents still relevant at the table."""
    profiles: list[dict[str, float]] = []
    for pid, p in state["players"].items():
        if pid == hero_id or p.get("is_ai"):
            continue
        stats = get_player_stats(state, pid)
        if stats["preflop_hands"] < 2 and stats["faced_bet"] < 2:
            continue
        profiles.append(get_opponent_profile(state, pid))

    if not profiles:
        return {
            "fold_to_bet_rate": 0.45,
            "vpip_rate": 0.28,
            "pfr_rate": 0.12,
            "aggression_factor": 1.0,
            "is_station": False,
            "is_nit": False,
        }

    keys = profiles[0].keys()
    blended: dict[str, float] = {}
    for key in keys:
        if key.startswith("is_"):
            blended[key] = any(p[key] for p in profiles)
        else:
            blended[key] = sum(p[key] for p in profiles) / len(profiles)
    return blended


def capture_to_call(state: dict[str, Any], player_id: str) -> int:
    """Snapshot bet-to-call before an action is applied."""
    return _bet_to_call(state, player_id)
