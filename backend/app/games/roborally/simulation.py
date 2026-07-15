"""Execute program cards and resolve robot movement."""

from __future__ import annotations

import copy
from typing import Any

from app.games.roborally import board as rb


def compute_register_order(
    robots: dict[str, dict[str, Any]],
    board: dict[str, Any],
    player_order: list[str],
    start_priorities: dict[str, int],
) -> list[str]:
    """Sort players by distance to antenna; ties broken by start priority."""

    def sort_key(pid: str) -> tuple[int, int, int]:
        robot = robots[pid]
        dist = rb.manhattan_to_antenna(board, robot["x"], robot["y"])
        priority = start_priorities.get(pid, 99)
        seat = player_order.index(pid) if pid in player_order else 99
        return (dist, priority, seat)

    return sorted(player_order, key=sort_key)


def _snapshot_robot(robot: dict[str, Any]) -> dict[str, Any]:
    return {"x": robot["x"], "y": robot["y"], "facing": robot["facing"]}


def _try_step(
    robot: dict[str, Any],
    board: dict[str, Any],
    occupied: set[tuple[int, int]],
    direction: int,
) -> bool:
    """Move robot one step forward (direction=1) or backward (direction=-1). Returns True if moved."""
    dx, dy = rb.DELTA[robot["facing"]]
    nx = robot["x"] + dx * direction
    ny = robot["y"] + dy * direction
    if rb.is_wall(board, nx, ny):
        return False
    if (nx, ny) in occupied:
        return False
    occupied.discard((robot["x"], robot["y"]))
    robot["x"] = nx
    robot["y"] = ny
    occupied.add((nx, ny))
    return True


def apply_card_to_robot(
    robot: dict[str, Any],
    card_type: str,
    board: dict[str, Any],
    occupied: set[tuple[int, int]],
) -> dict[str, Any]:
    """Apply one program card to a robot. Returns movement event data."""
    before = _snapshot_robot(robot)

    if card_type == "turn_left":
        robot["facing"] = rb.turn_left(robot["facing"])
    elif card_type == "turn_right":
        robot["facing"] = rb.turn_right(robot["facing"])
    elif card_type == "backup":
        _try_step(robot, board, occupied, direction=-1)
    elif card_type == "move_1":
        _try_step(robot, board, occupied, direction=1)
    elif card_type == "move_2":
        _try_step(robot, board, occupied, direction=1)
        _try_step(robot, board, occupied, direction=1)
    elif card_type == "move_3":
        for _ in range(3):
            if not _try_step(robot, board, occupied, direction=1):
                break

    return {
        "before": before,
        "after": _snapshot_robot(robot),
        "card_type": card_type,
    }


def check_checkpoint(robot: dict[str, Any], board: dict[str, Any]) -> bool:
    """Advance checkpoint index if robot is on the next required checkpoint."""
    cp = rb.checkpoint_at(board, robot["x"], robot["y"])
    if cp is None:
        return False
    next_cp = robot["checkpoints_reached"] + 1
    total = len(board["checkpoints"])
    if cp == next_cp:
        robot["checkpoints_reached"] = next_cp
        return True
    if cp == total and robot["checkpoints_reached"] == total - 1:
        robot["checkpoints_reached"] = total
        return True
    return False


def execute_register(
    state: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run all programmed cards for the current round. Mutates state in place."""
    events: list[dict[str, Any]] = []
    register_size = state["settings"]["register_size"]
    board = state["board"]
    robots = state["robots"]
    register_order = state["register_order"]
    programs = state["programs"]

    occupied: set[tuple[int, int]] = {(r["x"], r["y"]) for r in robots.values()}

    for step in range(register_size):
        step_events: list[dict[str, Any]] = []
        for pid in register_order:
            slot = programs[pid][step]
            if not slot:
                continue
            robot = robots[pid]
            move_event = apply_card_to_robot(robot, slot["type"], board, occupied)
            cp_hit = check_checkpoint(robot, board)
            step_events.append(
                {
                    "player_id": pid,
                    "step": step,
                    **move_event,
                    "checkpoint_hit": cp_hit,
                    "checkpoints_reached": robot["checkpoints_reached"],
                }
            )
        events.append({"type": "register_step", "step": step, "robots": step_events})

    winners = []
    total_cps = len(board["checkpoints"])
    for pid, robot in robots.items():
        if robot["checkpoints_reached"] >= total_cps:
            winners.append(pid)

    if winners:
        state["phase"] = "finished"
        state["winner"] = winners[0]
        state["win_reason"] = "checkpoints"
        events.append({"type": "game_won", "winner": winners[0], "all_finishers": winners})

    return state, events


def simulate_card(
    robots: dict[str, dict[str, Any]],
    board: dict[str, Any],
    player_id: str,
    card_type: str,
    register_order: list[str],
) -> dict[str, Any]:
    """Simulate one card for AI heuristics without mutating original state."""
    sim_robots = copy.deepcopy(robots)
    occupied = {(r["x"], r["y"]) for r in sim_robots.values()}
    robot = sim_robots[player_id]
    apply_card_to_robot(robot, card_type, board, occupied)
    check_checkpoint(robot, board)
    return sim_robots[player_id]
