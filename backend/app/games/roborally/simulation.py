"""Execute program cards and resolve classic RoboRally board phases."""

from __future__ import annotations

import copy
from typing import Any

from app.games.roborally import board as rb
from app.games.roborally import options as opt_lib


def compute_register_order(
    robots: dict[str, dict[str, Any]],
    board: dict[str, Any],
    player_order: list[str],
    start_priorities: dict[str, int],
) -> list[str]:
    """Sort players by distance to antenna; ties broken by start priority."""

    def sort_key(pid: str) -> tuple[int, int, int]:
        robot = robots[pid]
        if robot.get("eliminated"):
            return (9999, 99, 99)
        dist = rb.manhattan_to_antenna(board, robot["x"], robot["y"])
        priority = start_priorities.get(pid, 99)
        seat = player_order.index(pid) if pid in player_order else 99
        return (dist, priority, seat)

    active = [pid for pid in player_order if not robots.get(pid, {}).get("eliminated")]
    return sorted(active, key=sort_key)


def _snapshot_robot(robot: dict[str, Any]) -> dict[str, Any]:
    return {
        "x": robot["x"],
        "y": robot["y"],
        "facing": robot["facing"],
        "damage": robot.get("damage", 0),
        "lives": robot.get("lives", rb.STARTING_LIVES),
        "checkpoints_reached": robot.get("checkpoints_reached", 0),
    }


def _move_distance(card_type: str) -> int:
    if card_type == "move_1":
        return 1
    if card_type == "move_2":
        return 2
    if card_type == "move_3":
        return 3
    return 0


def _active_robots(robots: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {pid: r for pid, r in robots.items() if not r.get("eliminated")}


def _occupant_map(robots: dict[str, dict[str, Any]]) -> dict[tuple[int, int], str]:
    return {
        (r["x"], r["y"]): pid
        for pid, r in robots.items()
        if not r.get("eliminated")
    }


def _try_push_move(
    pid: str,
    direction: str,
    robots: dict[str, dict[str, Any]],
    board: dict[str, Any],
    walls: set[tuple[int, int, str]],
    pits: set[tuple[int, int]],
    *,
    allow_into_pit: bool = True,
    pusher_id: str | None = None,
) -> bool:
    """Attempt to move robot one step in direction, pushing a chain of robots.

    Returns True if the originating robot moved (chain succeeded).
    """
    robot = robots[pid]
    if robot.get("eliminated"):
        return False

    chain: list[str] = [pid]
    cx, cy = robot["x"], robot["y"]
    while True:
        if rb.blocked_step(board, cx, cy, direction, walls):
            return False
        dx, dy = rb.DELTA[direction]
        nx, ny = cx + dx, cy + dy
        if not rb.in_bounds(nx, ny, board["width"], board["height"]):
            # Leaving the board destroys the end of the chain — allow the push.
            break
        if (nx, ny) in pits and not allow_into_pit:
            return False
        occ = _occupant_map(robots)
        other = occ.get((nx, ny))
        if other is None or other in chain:
            break
        chain.append(other)
        cx, cy = nx, ny

    # Apply moves from the far end so cells free up.
    for mover_id in reversed(chain):
        mover = robots[mover_id]
        if rb.blocked_step(board, mover["x"], mover["y"], direction, walls):
            return False
        dx, dy = rb.DELTA[direction]
        nx = mover["x"] + dx
        ny = mover["y"] + dy
        mover["x"] = nx
        mover["y"] = ny
        if pusher_id and mover_id != pusher_id and opt_lib.has_option(robots[pusher_id], "ramming_gear"):
            mover["damage"] = int(mover.get("damage", 0)) + 1

    return True


def check_checkpoint(robot: dict[str, Any], board: dict[str, Any]) -> bool:
    cp = rb.checkpoint_at(board, robot["x"], robot["y"])
    if cp is None:
        return False
    next_cp = robot["checkpoints_reached"] + 1
    if cp == next_cp:
        robot["checkpoints_reached"] = next_cp
        robot["archive"] = {"x": robot["x"], "y": robot["y"]}
        return True
    return False


def _destroy_robot(
    pid: str,
    robots: dict[str, dict[str, Any]],
    board: dict[str, Any],
    reason: str,
    events: list[dict[str, Any]],
) -> None:
    robot = robots[pid]
    if robot.get("eliminated"):
        return
    before = _snapshot_robot(robot)
    lives = int(robot.get("lives", rb.STARTING_LIVES)) - 1
    robot["lives"] = lives
    if lives <= 0:
        robot["eliminated"] = True
        events.append(
            {
                "type": "eliminated",
                "player_id": pid,
                "reason": reason,
                "before": before,
                "after": _snapshot_robot(robot),
            }
        )
        return

    archive = robot.get("archive") or {"x": robot["x"], "y": robot["y"]}
    ax, ay = int(archive["x"]), int(archive["y"])
    # Find free archive cell (prefer archive, else adjacent).
    width, height = board["width"], board["height"]
    pits = rb.pit_set(board)
    candidates = [(ax, ay)] + [
        (ax + dx, ay + dy) for dx, dy in rb.DELTA.values()
    ]
    occ = _occupant_map(robots)
    place = None
    for px, py in candidates:
        if not rb.in_bounds(px, py, width, height):
            continue
        if (px, py) in pits:
            continue
        if (px, py) in occ and occ[(px, py)] != pid:
            continue
        place = (px, py)
        break
    if place is None:
        place = (ax, ay)

    robot["x"], robot["y"] = place
    robot["facing"] = rb.facing_away_from_antenna(board, robot["x"], robot["y"])
    robot["damage"] = rb.REBOOT_DAMAGE
    robot["powered_down"] = False
    events.append(
        {
            "type": "reboot",
            "player_id": pid,
            "reason": reason,
            "before": before,
            "after": _snapshot_robot(robot),
        }
    )


def _apply_damage(
    pid: str,
    amount: int,
    robots: dict[str, dict[str, Any]],
    board: dict[str, Any],
    events: list[dict[str, Any]],
    reason: str,
) -> None:
    robot = robots[pid]
    if robot.get("eliminated") or amount <= 0:
        return
    before = _snapshot_robot(robot)
    robot["damage"] = int(robot.get("damage", 0)) + amount
    events.append(
        {
            "type": "damage",
            "player_id": pid,
            "amount": amount,
            "reason": reason,
            "before": before,
            "after": _snapshot_robot(robot),
        }
    )
    if robot["damage"] > rb.MAX_DAMAGE:
        _destroy_robot(pid, robots, board, reason, events)


def _fall_check(
    robots: dict[str, dict[str, Any]],
    board: dict[str, Any],
    pits: set[tuple[int, int]],
    events: list[dict[str, Any]],
) -> None:
    for pid, robot in list(robots.items()):
        if robot.get("eliminated"):
            continue
        x, y = robot["x"], robot["y"]
        if not rb.in_bounds(x, y, board["width"], board["height"]) or (x, y) in pits:
            _destroy_robot(pid, robots, board, "pit", events)


def _cards_at_step(
    programs: dict[str, list[dict[str, str] | None]],
    register_order: list[str],
    step: int,
) -> dict[str, dict[str, str]]:
    cards: dict[str, dict[str, str]] = {}
    for pid in register_order:
        prog = programs.get(pid)
        if not prog or step >= len(prog):
            continue
        slot = prog[step]
        if slot and slot.get("type"):
            cards[pid] = slot
    return cards


def _execute_move_substeps(
    register_order: list[str],
    cards: dict[str, dict[str, str]],
    robots: dict[str, dict[str, Any]],
    board: dict[str, Any],
    walls: set[tuple[int, int, str]],
    pits: set[tuple[int, int]],
    step: int,
) -> list[dict[str, Any]]:
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
            if robot.get("eliminated") or robot.get("powered_down"):
                continue
            before = _snapshot_robot(robot)
            moved = _try_push_move(
                pid, robot["facing"], robots, board, walls, pits, pusher_id=pid
            )
            if moved:
                _fall_check(robots, board, pits, events)
            cp_hit = False
            if not robots[pid].get("eliminated") and moved:
                cp_hit = check_checkpoint(robots[pid], board)
            events.append(
                {
                    "player_id": pid,
                    "step": step,
                    "sub_step": sub,
                    "card_type": card["type"],
                    "before": before,
                    "after": _snapshot_robot(robots[pid]),
                    "moved": moved,
                    "checkpoint_hit": cp_hit,
                    "checkpoints_reached": robots[pid].get("checkpoints_reached", 0),
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
        if robot.get("eliminated") or robot.get("powered_down"):
            continue
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
    walls: set[tuple[int, int, str]],
    pits: set[tuple[int, int]],
    step: int,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for pid in register_order:
        card = cards.get(pid)
        if not card or card["type"] != "backup":
            continue
        robot = robots[pid]
        if robot.get("eliminated") or robot.get("powered_down"):
            continue
        before = _snapshot_robot(robot)
        direction = rb.OPPOSITE[robot["facing"]]
        moved = _try_push_move(pid, direction, robots, board, walls, pits, pusher_id=pid)
        if moved:
            _fall_check(robots, board, pits, events)
        cp_hit = False
        if not robots[pid].get("eliminated") and moved:
            cp_hit = check_checkpoint(robots[pid], board)
        events.append(
            {
                "player_id": pid,
                "step": step,
                "card_type": "backup",
                "before": before,
                "after": _snapshot_robot(robots[pid]),
                "moved": moved,
                "checkpoint_hit": cp_hit,
                "checkpoints_reached": robots[pid].get("checkpoints_reached", 0),
            }
        )
    return events


def _run_conveyors(
    robots: dict[str, dict[str, Any]],
    board: dict[str, Any],
    walls: set[tuple[int, int, str]],
    pits: set[tuple[int, int]],
    *,
    express_only: bool,
    step: int,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    active = _active_robots(robots)
    intents: dict[str, tuple[int, int, str, dict[str, Any]]] = {}

    for pid, robot in active.items():
        if robot.get("powered_down"):
            continue
        conv = rb.conveyor_at(board, robot["x"], robot["y"])
        if not conv:
            continue
        is_express = bool(conv.get("express"))
        if express_only and not is_express:
            continue
        if opt_lib.has_option(robot, "abort_switch") and robot.get("_abort_used_round") != step:
            # Consume once to skip this conveyor activation.
            robot["_abort_used_round"] = step
            events.append(
                {
                    "type": "option",
                    "player_id": pid,
                    "option": "abort_switch",
                    "step": step,
                }
            )
            continue
        direction = str(conv["dir"])
        dx, dy = rb.DELTA[direction]
        nx, ny = robot["x"] + dx, robot["y"] + dy
        intents[pid] = (nx, ny, direction, conv)

    # Conflicts: two robots intending same cell → neither moves.
    destinations: dict[tuple[int, int], list[str]] = {}
    for pid, (nx, ny, _, _) in intents.items():
        destinations.setdefault((nx, ny), []).append(pid)
    blocked_ids = {pid for dest, pids in destinations.items() if len(pids) > 1 for pid in pids}

    # Also block swap head-ons lightly: if A→B and B→A both on conveyors, both move (classic allows).
    for pid, (nx, ny, direction, conv) in intents.items():
        if pid in blocked_ids:
            continue
        robot = robots[pid]
        if rb.blocked_step(board, robot["x"], robot["y"], direction, walls):
            continue
        before = _snapshot_robot(robot)
        robot["x"], robot["y"] = nx, ny
        rotate = conv.get("rotate", "none")
        # Rotate when leaving a turning belt onto destination — use conveyor rotate on source.
        if rotate == "left":
            robot["facing"] = rb.turn_left(robot["facing"])
        elif rotate == "right":
            robot["facing"] = rb.turn_right(robot["facing"])
        # Also rotate if destination conveyor faces differently (belt turn).
        dest_conv = rb.conveyor_at(board, nx, ny)
        if dest_conv and dest_conv.get("dir") != direction:
            # Face the new belt direction when entering a different-facing belt.
            robot["facing"] = str(dest_conv["dir"])
        events.append(
            {
                "type": "conveyor",
                "player_id": pid,
                "express": bool(conv.get("express")),
                "step": step,
                "before": before,
                "after": _snapshot_robot(robot),
            }
        )

    _fall_check(robots, board, pits, events)
    return events


def _run_pushers(
    robots: dict[str, dict[str, Any]],
    board: dict[str, Any],
    walls: set[tuple[int, int, str]],
    pits: set[tuple[int, int]],
    register_num: int,
    step: int,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for pid, robot in list(_active_robots(robots).items()):
        if robot.get("powered_down"):
            continue
        pusher = rb.pusher_at(board, robot["x"], robot["y"])
        if not pusher:
            continue
        regs = [int(r) for r in pusher.get("registers", [])]
        if register_num not in regs:
            continue
        before = _snapshot_robot(robot)
        direction = str(pusher["dir"])
        moved = _try_push_move(pid, direction, robots, board, walls, pits)
        if moved:
            _fall_check(robots, board, pits, events)
        events.append(
            {
                "type": "pusher",
                "player_id": pid,
                "step": step,
                "before": before,
                "after": _snapshot_robot(robots[pid]),
                "moved": moved,
            }
        )
    return events


def _run_gears(
    robots: dict[str, dict[str, Any]],
    board: dict[str, Any],
    step: int,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for pid, robot in _active_robots(robots).items():
        if robot.get("powered_down"):
            continue
        gear = rb.gear_at(board, robot["x"], robot["y"])
        if not gear:
            continue
        before = _snapshot_robot(robot)
        if gear.get("dir") == "left":
            robot["facing"] = rb.turn_left(robot["facing"])
        else:
            robot["facing"] = rb.turn_right(robot["facing"])
        events.append(
            {
                "type": "gear",
                "player_id": pid,
                "step": step,
                "before": before,
                "after": _snapshot_robot(robot),
            }
        )
    return events


def _run_crushers(
    robots: dict[str, dict[str, Any]],
    board: dict[str, Any],
    register_num: int,
    step: int,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for pid, robot in list(_active_robots(robots).items()):
        crusher = rb.crusher_at(board, robot["x"], robot["y"])
        if not crusher:
            continue
        regs = [int(r) for r in crusher.get("registers", [])]
        if register_num not in regs:
            continue
        events.append({"type": "crusher", "player_id": pid, "step": step})
        _destroy_robot(pid, robots, board, "crusher", events)
    return events


def _laser_ray(
    board: dict[str, Any],
    start_x: int,
    start_y: int,
    direction: str,
    walls: set[tuple[int, int, str]],
    robots: dict[str, dict[str, Any]],
    *,
    include_start: bool = False,
) -> str | None:
    """Return player_id of first robot hit by a ray, or None."""
    x, y = start_x, start_y
    if not include_start:
        if rb.blocked_step(board, x, y, direction, walls):
            return None
        dx, dy = rb.DELTA[direction]
        x, y = x + dx, y + dy
    occ = _occupant_map(robots)
    while rb.in_bounds(x, y, board["width"], board["height"]):
        hit = occ.get((x, y))
        if hit:
            return hit
        if rb.blocked_step(board, x, y, direction, walls):
            return None
        dx, dy = rb.DELTA[direction]
        x, y = x + dx, y + dy
    return None


def _run_board_lasers(
    robots: dict[str, dict[str, Any]],
    board: dict[str, Any],
    walls: set[tuple[int, int, str]],
    step: int,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for laser in board.get("lasers", []):
        lx, ly = int(laser["x"]), int(laser["y"])
        direction = str(laser["dir"])
        strength = int(laser.get("strength", 1))
        # Emitter sits on a cell and fires out of that cell.
        hit = _laser_ray(board, lx, ly, direction, walls, robots, include_start=False)
        if hit:
            events.append(
                {
                    "type": "laser",
                    "source": "board",
                    "player_id": hit,
                    "strength": strength,
                    "step": step,
                    "from": [lx, ly],
                    "dir": direction,
                }
            )
            _apply_damage(hit, strength, robots, board, events, "board_laser")
    return events


def _run_robot_lasers(
    robots: dict[str, dict[str, Any]],
    board: dict[str, Any],
    walls: set[tuple[int, int, str]],
    register_order: list[str],
    step: int,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for pid in register_order:
        robot = robots.get(pid)
        if not robot or robot.get("eliminated") or robot.get("powered_down"):
            continue
        strength = 1 + opt_lib.laser_bonus(robot)
        directions = [robot["facing"]]
        if opt_lib.has_option(robot, "rear_laser"):
            directions.append(rb.OPPOSITE[robot["facing"]])
        for direction in directions:
            hit = _laser_ray(
                board, robot["x"], robot["y"], direction, walls, robots, include_start=False
            )
            if hit and hit != pid:
                events.append(
                    {
                        "type": "laser",
                        "source": "robot",
                        "shooter": pid,
                        "player_id": hit,
                        "strength": strength,
                        "step": step,
                        "dir": direction,
                    }
                )
                _apply_damage(hit, strength, robots, board, events, "robot_laser")
    return events


def _run_sites(
    state: dict[str, Any],
    robots: dict[str, dict[str, Any]],
    board: dict[str, Any],
    step: int,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    option_deck = state.setdefault("option_deck", [])
    option_discard = state.setdefault("option_discard", [])

    for pid, robot in _active_robots(robots).items():
        if robot.get("powered_down"):
            continue
        x, y = robot["x"], robot["y"]
        before = _snapshot_robot(robot)

        cp_hit = check_checkpoint(robot, board)

        healed = False
        gained_option = None
        if rb.is_repair(board, x, y):
            if robot.get("damage", 0) > 0:
                robot["damage"] -= 1
                healed = True
            robot["archive"] = {"x": x, "y": y}
        if rb.is_upgrade(board, x, y):
            if robot.get("damage", 0) > 0:
                robot["damage"] -= 1
                healed = True
            robot["archive"] = {"x": x, "y": y}
            drawn = opt_lib.draw_option(option_deck, option_discard)
            if drawn:
                robot.setdefault("options", []).append(drawn)
                gained_option = drawn

        if cp_hit or healed or gained_option:
            events.append(
                {
                    "type": "site",
                    "player_id": pid,
                    "step": step,
                    "checkpoint_hit": cp_hit,
                    "healed": healed,
                    "option": gained_option,
                    "before": before,
                    "after": _snapshot_robot(robot),
                    "checkpoints_reached": robot["checkpoints_reached"],
                }
            )
    return events


def _board_elements_phase(
    state: dict[str, Any],
    step: int,
    register_order: list[str],
) -> list[dict[str, Any]]:
    board = state["board"]
    robots = state["robots"]
    walls = rb.edge_wall_set(board)
    pits = rb.pit_set(board)
    register_num = step + 1  # 1-based
    events: list[dict[str, Any]] = []

    events.extend(_run_conveyors(robots, board, walls, pits, express_only=True, step=step))
    events.extend(_run_conveyors(robots, board, walls, pits, express_only=False, step=step))
    events.extend(_run_pushers(robots, board, walls, pits, register_num, step))
    events.extend(_run_gears(robots, board, step))
    events.extend(_run_crushers(robots, board, register_num, step))
    events.extend(_run_board_lasers(robots, board, walls, step))
    events.extend(_run_robot_lasers(robots, board, walls, register_order, step))
    events.extend(_run_sites(state, robots, board, step))
    return events


def _execute_register_slot(
    state: dict[str, Any],
    step: int,
    register_order: list[str],
) -> list[dict[str, Any]]:
    board = state["board"]
    robots = state["robots"]
    programs = state["programs"]
    walls = rb.edge_wall_set(board)
    pits = rb.pit_set(board)

    cards = _cards_at_step(programs, register_order, step)
    events: list[dict[str, Any]] = []

    # Powered-down robots skip cards but still take board effects.
    card_events: list[dict[str, Any]] = []
    card_events.extend(
        _execute_move_substeps(register_order, cards, robots, board, walls, pits, step)
    )
    card_events.extend(_execute_turns(register_order, cards, robots, step))
    card_events.extend(
        _execute_backups(register_order, cards, robots, board, walls, pits, step)
    )
    if card_events:
        events.append({"type": "register_step", "step": step, "robots": card_events})

    board_events = _board_elements_phase(state, step, register_order)
    if board_events:
        events.append({"type": "board_step", "step": step, "events": board_events})

    return events


def execute_register(
    state: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run all programmed cards + board phases for the current round."""
    events: list[dict[str, Any]] = []
    register_size = state["settings"]["register_size"]
    robots = state["robots"]
    board = state["board"]
    register_order = [
        pid
        for pid in state["register_order"]
        if pid in robots and not robots[pid].get("eliminated")
    ]

    player_order = state.get("player_order") or list(robots.keys())
    for step in range(register_size):
        # Recompute priority each register from current positions.
        register_order = compute_register_order(
            robots,
            board,
            player_order,
            state.get("start_priorities", {}),
        )
        step_events = _execute_register_slot(state, step, register_order)
        events.extend(step_events)

    # End of a powered-down round: repair all damage and wake for next round.
    for pid, robot in robots.items():
        if robot.get("eliminated"):
            continue
        if robot.get("powered_down"):
            robot["damage"] = 0
            robot["powered_down"] = False
            events.append({"type": "power_down_complete", "player_id": pid})

    winners = []
    total_cps = len(board["checkpoints"])
    for pid, robot in robots.items():
        if robot.get("eliminated"):
            continue
        if robot["checkpoints_reached"] >= total_cps:
            winners.append(pid)

    alive = [pid for pid, r in robots.items() if not r.get("eliminated")]
    if winners:
        state["phase"] = "finished"
        state["winner"] = winners[0]
        state["win_reason"] = "checkpoints"
        events.append({"type": "game_won", "winner": winners[0], "all_finishers": winners})
    elif len(alive) == 1:
        state["phase"] = "finished"
        state["winner"] = alive[0]
        state["win_reason"] = "last_standing"
        events.append({"type": "game_won", "winner": alive[0], "reason": "last_standing"})
    elif len(alive) == 0:
        state["phase"] = "finished"
        state["winner"] = None
        state["win_reason"] = "draw"
        events.append({"type": "game_won", "winner": None, "reason": "draw"})

    return state, events


def apply_card_to_robot(
    robot: dict[str, Any],
    card_type: str,
    board: dict[str, Any],
    occupied: set[tuple[int, int]],
) -> dict[str, Any]:
    """Apply one program card to a single robot in isolation (AI simulation)."""
    before = _snapshot_robot(robot)
    walls = rb.edge_wall_set(board)
    pits = rb.pit_set(board)

    # Build a tiny robots dict for push helper.
    robots = {"_self": robot}
    # Mark occupied cells as phantom blockers (no push in AI approx).
    for ox, oy in occupied:
        if (ox, oy) != (robot["x"], robot["y"]):
            robots[f"block_{ox}_{oy}"] = {
                "x": ox,
                "y": oy,
                "facing": "N",
                "eliminated": False,
                "damage": 0,
                "lives": 1,
                "checkpoints_reached": 0,
            }

    if card_type == "turn_left":
        robot["facing"] = rb.turn_left(robot["facing"])
    elif card_type == "turn_right":
        robot["facing"] = rb.turn_right(robot["facing"])
    elif card_type == "backup":
        _try_push_move("_self", rb.OPPOSITE[robot["facing"]], robots, board, walls, pits)
    elif card_type in ("move_1", "move_2", "move_3"):
        for _ in range(_move_distance(card_type)):
            if not _try_push_move("_self", robot["facing"], robots, board, walls, pits):
                break
            if (robot["x"], robot["y"]) in pits or not rb.in_bounds(
                robot["x"], robot["y"], board["width"], board["height"]
            ):
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
    occupied = {
        (r["x"], r["y"])
        for pid, r in sim_robots.items()
        if pid != player_id and not r.get("eliminated")
    }
    robot = sim_robots[player_id]
    apply_card_to_robot(robot, card_type, board, occupied)
    if (robot["x"], robot["y"]) in rb.pit_set(board):
        # Heavy penalty path for AI: leave on pit coords; scorer will hate it.
        pass
    else:
        check_checkpoint(robot, board)
    return sim_robots[player_id]
