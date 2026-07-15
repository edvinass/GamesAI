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


def _move_distance(card_type: str) -> int:
    if card_type == "move_1":
        return 1
    if card_type == "move_2":
        return 2
    if card_type == "move_3":
        return 3
    return 0


def _wall_lookup(board: dict[str, Any]) -> set[tuple[int, int]]:
    return {tuple(w) for w in board.get("walls", [])}


def _is_blocked(board: dict[str, Any], x: int, y: int, walls: set[tuple[int, int]]) -> bool:
    if not rb.in_bounds(x, y, board["width"], board["height"]):
        return True
    return (x, y) in walls


def _try_step(
    robot: dict[str, Any],
    board: dict[str, Any],
    walls: set[tuple[int, int]],
    occupied: set[tuple[int, int]],
    direction: int,
) -> bool:
    """Move robot one step forward (direction=1) or backward (direction=-1). Returns True if moved."""
    dx, dy = rb.DELTA[robot["facing"]]
    nx = robot["x"] + dx * direction
    ny = robot["y"] + dy * direction
    if _is_blocked(board, nx, ny, walls):
        return False
    if (nx, ny) in occupied:
        return False
    occupied.discard((robot["x"], robot["y"]))
    robot["x"] = nx
    robot["y"] = ny
    occupied.add((nx, ny))
    return True


def check_checkpoint(robot: dict[str, Any], board: dict[str, Any]) -> bool:
    """Advance checkpoint index if robot is on the next required checkpoint."""
    cp = rb.checkpoint_at(board, robot["x"], robot["y"])
    if cp is None:
        return False
    next_cp = robot["checkpoints_reached"] + 1
    if cp == next_cp:
        robot["checkpoints_reached"] = next_cp
        return True
    return False


def _cards_at_step(
    programs: dict[str, list[dict[str, str] | None]],
    register_order: list[str],
    step: int,
) -> dict[str, dict[str, str]]:
    cards: dict[str, dict[str, str]] = {}
    for pid in register_order:
        slot = programs[pid][step]
        if slot and slot.get("type"):
            cards[pid] = slot
    return cards


def _execute_move_substeps(
    register_order: list[str],
    cards: dict[str, dict[str, str]],
    robots: dict[str, dict[str, Any]],
    board: dict[str, Any],
    walls: set[tuple[int, int]],
    occupied: set[tuple[int, int]],
    step: int,
) -> list[dict[str, Any]]:
    """Move cards resolve one square at a time in priority order (RoboRally rules)."""
    move_cards = {pid: card for pid, card in cards.items() if _move_distance(card["type"]) > 0}
    if not move_cards:
        return []

    max_steps = max(_move_distance(card["type"]) for card in move_cards.values())
    events: list[dict[str, Any]] = []

    for sub in range(max_steps):
        for pid in register_order:
            card = move_cards.get(pid)
            if not card or sub >= _move_distance(card["type"]):
                continue

            robot = robots[pid]
            before = _snapshot_robot(robot)
            moved = _try_step(robot, board, walls, occupied, direction=1)
            cp_hit = check_checkpoint(robot, board) if moved else False
            events.append(
                {
                    "player_id": pid,
                    "step": step,
                    "sub_step": sub,
                    "card_type": card["type"],
                    "before": before,
                    "after": _snapshot_robot(robot),
                    "moved": moved,
                    "checkpoint_hit": cp_hit,
                    "checkpoints_reached": robot["checkpoints_reached"],
                }
            )

    return events


def _execute_turns(
    register_order: list[str],
    cards: dict[str, dict[str, str]],
    robots: dict[str, dict[str, Any]],
    step: int,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for pid in register_order:
        card = cards.get(pid)
        if not card or card["type"] not in ("turn_left", "turn_right"):
            continue
        robot = robots[pid]
        before = _snapshot_robot(robot)
        if card["type"] == "turn_left":
            robot["facing"] = rb.turn_left(robot["facing"])
        else:
            robot["facing"] = rb.turn_right(robot["facing"])
        events.append(
            {
                "player_id": pid,
                "step": step,
                "card_type": card["type"],
                "before": before,
                "after": _snapshot_robot(robot),
                "moved": False,
                "checkpoint_hit": False,
                "checkpoints_reached": robot["checkpoints_reached"],
            }
        )
    return events


def _execute_backups(
    register_order: list[str],
    cards: dict[str, dict[str, str]],
    robots: dict[str, dict[str, Any]],
    board: dict[str, Any],
    walls: set[tuple[int, int]],
    occupied: set[tuple[int, int]],
    step: int,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for pid in register_order:
        card = cards.get(pid)
        if not card or card["type"] != "backup":
            continue
        robot = robots[pid]
        before = _snapshot_robot(robot)
        moved = _try_step(robot, board, walls, occupied, direction=-1)
        cp_hit = check_checkpoint(robot, board) if moved else False
        events.append(
            {
                "player_id": pid,
                "step": step,
                "card_type": "backup",
                "before": before,
                "after": _snapshot_robot(robot),
                "moved": moved,
                "checkpoint_hit": cp_hit,
                "checkpoints_reached": robot["checkpoints_reached"],
            }
        )
    return events


def _execute_register_slot(
    step: int,
    register_order: list[str],
    programs: dict[str, list[dict[str, str] | None]],
    robots: dict[str, dict[str, Any]],
    board: dict[str, Any],
    walls: set[tuple[int, int]],
    occupied: set[tuple[int, int]],
) -> list[dict[str, Any]]:
    cards = _cards_at_step(programs, register_order, step)
    if not cards:
        return []

    events: list[dict[str, Any]] = []
    events.extend(_execute_move_substeps(register_order, cards, robots, board, walls, occupied, step))
    events.extend(_execute_turns(register_order, cards, robots, step))
    events.extend(_execute_backups(register_order, cards, robots, board, walls, occupied, step))
    return events


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
    walls = _wall_lookup(board)

    occupied: set[tuple[int, int]] = {(r["x"], r["y"]) for r in robots.values()}

    for step in range(register_size):
        step_events = _execute_register_slot(
            step, register_order, programs, robots, board, walls, occupied
        )
        if step_events:
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


def apply_card_to_robot(
    robot: dict[str, Any],
    card_type: str,
    board: dict[str, Any],
    occupied: set[tuple[int, int]],
) -> dict[str, Any]:
    """Apply one program card to a single robot in isolation (AI simulation)."""
    before = _snapshot_robot(robot)
    walls = _wall_lookup(board)

    if card_type == "turn_left":
        robot["facing"] = rb.turn_left(robot["facing"])
    elif card_type == "turn_right":
        robot["facing"] = rb.turn_right(robot["facing"])
    elif card_type == "backup":
        _try_step(robot, board, walls, occupied, direction=-1)
    elif card_type == "move_1":
        _try_step(robot, board, walls, occupied, direction=1)
    elif card_type == "move_2":
        _try_step(robot, board, walls, occupied, direction=1)
        _try_step(robot, board, walls, occupied, direction=1)
    elif card_type == "move_3":
        for _ in range(3):
            if not _try_step(robot, board, walls, occupied, direction=1):
                break

    return {
        "before": before,
        "after": _snapshot_robot(robot),
        "card_type": card_type,
    }


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
