import random
from typing import Any

POWERUP_ACTIVATION_TICKS = 8

INSTANT_POWERUP_TYPES = frozenset(
    {"heal", "laser", "railgun", "bomb", "cluster", "burst"}
)

MOVE_OPTIONS = ("up", "down", "stop")


def _fighter_height(state: dict) -> int:
    return int(state["settings"].get("fighter_height", 3))


def _fighter_rows(top: int, height: int) -> set[int]:
    return set(range(top, top + height))


def _fighter_center(top: int, height: int) -> int:
    return top + height // 2


def _arena_center_row(grid_height: int, height: int) -> int:
    return _fighter_center((grid_height - height) // 2, height)


def _enemy_fighter(state: dict, player_id: str) -> dict[str, Any] | None:
    for pid, fighter in state["fighters"].items():
        if pid != player_id and fighter.get("alive"):
            return fighter
    return None


def _incoming_bullets(state: dict, player_id: str, fighter: dict[str, Any]) -> list[dict]:
    bullets = []
    for bullet in state.get("bullets", []):
        if bullet["owner_id"] == player_id:
            continue
        if fighter["side"] == "left" and bullet["vx"] < 0:
            bullets.append(bullet)
        elif fighter["side"] == "right" and bullet["vx"] > 0:
            bullets.append(bullet)
    return bullets


def _bullet_heading_toward(bullet: dict, fighter_x: int, side: str) -> bool:
    if side == "left":
        return bullet["vx"] < 0 and bullet["x"] >= fighter_x
    return bullet["vx"] > 0 and bullet["x"] <= fighter_x


def _ticks_until_column(bullet: dict, fighter_x: int) -> int:
    speed = abs(bullet.get("vx", 1)) or 1
    return max(0, abs(bullet["x"] - fighter_x) // speed)


def _top_after_move(top: int, direction: str, min_y: int, max_y: int) -> int:
    if direction == "up":
        return max(min_y, top - 1)
    if direction == "down":
        return min(max_y, top + 1)
    return top


def _playable_bounds(state: dict, fighter_height: int) -> tuple[int, int]:
    min_y = state.get("playable_y_min", 0)
    max_top = min(
        state["grid_height"] - fighter_height,
        state.get("playable_y_max", state["grid_height"] - 1) - fighter_height + 1,
    )
    return min_y, max_top


def _cell_in_obstacle(x: int, y: int, obstacle: dict) -> bool:
    return (
        obstacle["x"] <= x < obstacle["x"] + obstacle["w"]
        and obstacle["y"] <= y < obstacle["y"] + obstacle["h"]
    )


def _fighter_overlaps_obstacle(
    fighter: dict[str, Any], fighter_height: int, obstacles: list[dict]
) -> bool:
    for i in range(fighter_height):
        y = fighter["y"] + i
        if any(_cell_in_obstacle(fighter["x"], y, obs) for obs in obstacles):
            return True
    return False


def _predict_enemy_top(
    enemy: dict[str, Any],
    height: int,
    grid_height: int,
    ticks: int,
    min_y: int,
    max_y: int,
) -> int:
    y = enemy["y"]
    direction = enemy.get("move_direction", "stop")
    for _ in range(max(0, ticks)):
        y = _top_after_move(y, direction, min_y, max_y)
    return y


def _travel_ticks_to_enemy(fighter: dict[str, Any], enemy: dict[str, Any], speed: int) -> int:
    distance = max(0, abs(enemy["x"] - fighter["x"]) - 1)
    return max(0, distance // max(1, speed))


def _shot_aligns_with_enemy(shoot_row: int, enemy_top: int, height: int) -> bool:
    return shoot_row in _fighter_rows(enemy_top, height)


def _enemy_aim_centers(
    enemy: dict[str, Any],
    fighter: dict[str, Any],
    height: int,
    grid_height: int,
    min_y: int,
    max_y: int,
    speed: int,
) -> tuple[int, int]:
    travel = _travel_ticks_to_enemy(fighter, enemy, speed)
    lead_ticks = min(max(travel, 1), 24)
    predicted_top = _predict_enemy_top(enemy, height, grid_height, lead_ticks, min_y, max_y)
    current_center = _fighter_center(enemy["y"], height)
    lead_center = _fighter_center(predicted_top, height)
    return current_center, lead_center


def _bullet_threatens_move(
    bullet: dict,
    fighter: dict[str, Any],
    height: int,
    new_top: int,
    old_center: int,
    speed: int,
) -> bool:
    if not _bullet_heading_toward(bullet, fighter["x"], fighter["side"]):
        return False
    bullet_y = bullet["y"]
    new_rows = _fighter_rows(new_top, height)
    ticks = _ticks_until_column(bullet, fighter["x"])
    if bullet_y in new_rows:
        return True
    if ticks <= 12 and abs(bullet_y - old_center) <= height + 1:
        return True
    if bullet.get("damage", 1) >= 2 and abs(bullet_y - old_center) <= height + 2:
        return True
    return False


def _move_is_safe_from_bullets(
    direction: str,
    fighter: dict[str, Any],
    height: int,
    min_y: int,
    max_y: int,
    bullets: list[dict],
    obstacles: list[dict],
    speed: int,
) -> bool:
    new_top = _top_after_move(fighter["y"], direction, min_y, max_y)
    candidate = {**fighter, "y": new_top}
    if _fighter_overlaps_obstacle(candidate, height, obstacles):
        return False
    old_center = _fighter_center(fighter["y"], height)
    for bullet in bullets:
        if _bullet_threatens_move(bullet, fighter, height, new_top, old_center, speed):
            if bullet["y"] in _fighter_rows(new_top, height):
                return False
    return True


def _score_move(
    direction: str,
    fighter: dict[str, Any],
    height: int,
    grid_height: int,
    min_y: int,
    max_y: int,
    bullets: list[dict],
    enemy: dict[str, Any] | None,
    obstacles: list[dict],
    powerup: dict | None,
    speed: int,
) -> float:
    y = fighter["y"]
    new_top = _top_after_move(y, direction, min_y, max_y)
    candidate = {**fighter, "y": new_top}
    if _fighter_overlaps_obstacle(candidate, height, obstacles):
        return float("-inf")

    new_rows = _fighter_rows(new_top, height)
    old_center = _fighter_center(y, height)
    new_center = _fighter_center(new_top, height)
    arena_center = _arena_center_row(grid_height, height)

    score = 0.0
    incoming = 0
    immediate_danger = False

    for bullet in bullets:
        if not _bullet_heading_toward(bullet, fighter["x"], fighter["side"]):
            continue
        incoming += 1
        ticks = _ticks_until_column(bullet, fighter["x"])
        bullet_y = bullet["y"]

        if bullet_y in new_rows:
            score -= 2000.0 + max(0, 24 - ticks) * 80.0
            immediate_danger = True
            continue

        score += 20.0 + min(ticks, 20)

        old_gap = abs(bullet_y - old_center)
        new_gap = abs(bullet_y - new_center)

        if abs(bullet_y - old_center) <= height + 2 and ticks <= 14:
            score += (new_gap - old_gap) * 35.0
            if ticks <= 8:
                immediate_danger = True

    if incoming and direction == "stop":
        score -= 120.0

    edge_clearance = min(new_top - min_y, max_y - new_top)
    score += edge_clearance * 12.0

    if new_top == min_y or new_top == max_y:
        wall_penalty = 140.0 if immediate_danger else 180.0
        score -= wall_penalty

    if enemy is not None and not immediate_danger:
        current_center, lead_center = _enemy_aim_centers(
            enemy, fighter, height, grid_height, min_y, max_y, speed
        )
        primary_target = lead_center

        score -= abs(new_center - primary_target) * 55.0
        score -= abs(new_center - current_center) * 30.0

        if new_center < primary_target and direction == "down":
            score += 55.0
        elif new_center > primary_target and direction == "up":
            score += 55.0

        if _shot_aligns_with_enemy(new_center, enemy["y"], height):
            score += 80.0

        if edge_clearance <= 1 and direction != "stop":
            if (direction == "down" and current_center > new_center) or (
                direction == "up" and current_center < new_center
            ):
                score += 60.0
    elif not immediate_danger:
        score -= abs(new_center - arena_center) * 14.0
        if y == min_y and direction == "down":
            score += 90.0
        if y == max_y and direction == "up":
            score += 90.0

    if powerup and not fighter.get("stored_powerup") and not immediate_danger:
        center_row = _fighter_center(new_top, height)
        dist = abs(center_row - powerup["y"])
        if dist == 0:
            score += 280.0
        elif dist <= 1:
            score += 180.0
        elif dist <= 2:
            score += 90.0

    return score


def _choose_move(
    fighter: dict[str, Any],
    state: dict,
    height: int,
    bullets: list[dict],
    enemy: dict[str, Any] | None,
) -> str:
    min_y, max_y = _playable_bounds(state, height)
    obstacles = state.get("obstacles", [])
    powerup = state.get("powerup")
    speed = int(state["settings"].get("bullet_speed", 1))

    scored: list[tuple[str, float]] = []
    for direction in MOVE_OPTIONS:
        score = _score_move(
            direction,
            fighter,
            height,
            state["grid_height"],
            min_y,
            max_y,
            bullets,
            enemy,
            obstacles,
            powerup,
            speed,
        )
        scored.append((direction, score))

    safe_moves = [
        d
        for d, _ in scored
        if _move_is_safe_from_bullets(
            d, fighter, height, min_y, max_y, bullets, obstacles, speed
        )
    ]

    if safe_moves:
        if enemy is not None:
            _, lead_center = _enemy_aim_centers(
                enemy, fighter, height, state["grid_height"], min_y, max_y, speed
            )
            pursuit_target = lead_center
        else:
            pursuit_target = _arena_center_row(state["grid_height"], height)

        best_direction = safe_moves[0]
        best_score = float("-inf")
        best_target_dist = float("inf")

        for direction, score in scored:
            if direction not in safe_moves:
                continue
            new_top = _top_after_move(fighter["y"], direction, min_y, max_y)
            target_dist = abs(_fighter_center(new_top, height) - pursuit_target)
            if score > best_score or (score >= best_score - 25 and target_dist < best_target_dist):
                best_score = score
                best_target_dist = target_dist
                best_direction = direction
        return best_direction

    return max(scored, key=lambda item: item[1])[0]


def _should_shoot(
    state: dict,
    fighter: dict[str, Any],
    enemy: dict[str, Any],
    height: int,
    move_direction: str,
) -> bool:
    tick = state["tick"]
    if tick < fighter.get("cooldown_until_tick", 0):
        return False

    min_y, max_y = _playable_bounds(state, height)
    speed = int(state["settings"].get("bullet_speed", 1))
    shoot_top = _top_after_move(fighter["y"], move_direction, min_y, max_y)
    shoot_row = _fighter_center(shoot_top, height)

    travel = _travel_ticks_to_enemy(fighter, enemy, speed)
    predicted_top = _predict_enemy_top(
        enemy, height, state["grid_height"], travel, min_y, max_y
    )
    if _shot_aligns_with_enemy(shoot_row, predicted_top, height):
        return True

    current_top = enemy["y"]
    if _shot_aligns_with_enemy(shoot_row, current_top, height):
        return True

    direction = enemy.get("move_direction", "stop")
    if direction in ("up", "down"):
        next_top = _predict_enemy_top(enemy, height, state["grid_height"], 1, min_y, max_y)
        if _shot_aligns_with_enemy(shoot_row, next_top, height):
            return True

    if travel <= 20:
        predicted_top = _predict_enemy_top(
            enemy, height, state["grid_height"], travel, min_y, max_y
        )
        if _shot_aligns_with_enemy(shoot_row, predicted_top, height):
            return True

    enemy_center = _fighter_center(current_top, height)
    if abs(shoot_row - enemy_center) <= 1:
        return True

    powerup = state.get("powerup")
    if powerup and not fighter.get("stored_powerup"):
        if abs(shoot_row - powerup["y"]) <= 2:
            return True
        if abs(shoot_row - powerup["y"]) <= 4 and random.random() < 0.65:
            return True

    return False


def _should_charge(
    state: dict,
    fighter: dict[str, Any],
    enemy: dict[str, Any],
    height: int,
    move_direction: str,
) -> tuple[bool, int]:
    if not state["settings"].get("charge_shot_enabled"):
        return False, 0
    tick = state["tick"]
    if tick < fighter.get("cooldown_until_tick", 0):
        return False, 0

    min_y, max_y = _playable_bounds(state, height)
    speed = int(state["settings"].get("bullet_speed", 1))
    shoot_top = _top_after_move(fighter["y"], move_direction, min_y, max_y)
    shoot_row = _fighter_center(shoot_top, height)
    enemy_center = _fighter_center(enemy["y"], height)

    if abs(shoot_row - enemy_center) <= 1:
        return True, 12
    if _should_shoot(state, fighter, enemy, height, move_direction):
        return True, 8
    return False, 0


def _should_activate_powerup(
    state: dict,
    fighter: dict[str, Any],
    enemy: dict[str, Any] | None,
    height: int,
) -> tuple[bool, bool]:
    """Returns powerup_hold_start, powerup_hold_release."""
    if not state["settings"].get("powerups_enabled"):
        return False, False
    stored = fighter.get("stored_powerup")
    if not stored or stored in INSTANT_POWERUP_TYPES:
        return False, False

    if fighter.get("activating_powerup"):
        ticks = fighter.get("powerup_activation_ticks", 0) + 1
        if ticks >= POWERUP_ACTIVATION_TICKS:
            return False, True
        return False, False

    if stored == "shield":
        if fighter.get("hp", 1) <= 2:
            return True, False
        if random.random() < 0.35:
            return True, False
    elif stored == "freeze" and enemy is not None:
        if random.random() < 0.55:
            return True, False
    elif stored in ("rapid_fire", "machine_gun", "homing", "overdrive", "pierce", "wide_shot", "ghost", "mirror"):
        if enemy is not None:
            shoot_row = _fighter_center(fighter["y"], height)
            enemy_center = _fighter_center(enemy["y"], height)
            if abs(shoot_row - enemy_center) <= 2:
                return True, False
        if random.random() < 0.4:
            return True, False
    return False, False


def _should_use_instant_powerup(
    state: dict,
    fighter: dict[str, Any],
    enemy: dict[str, Any] | None,
    height: int,
) -> bool:
    if not state["settings"].get("powerups_enabled"):
        return False
    stored = fighter.get("stored_powerup")
    if not stored or stored not in INSTANT_POWERUP_TYPES:
        return False
    if stored == "heal":
        return fighter.get("hp", 1) < fighter.get("max_hp", 3)
    if enemy is None:
        return stored in ("heal",)
    shoot_row = _fighter_center(fighter["y"], height)
    enemy_center = _fighter_center(enemy["y"], height)
    aligned = abs(shoot_row - enemy_center) <= 2
    if stored in ("laser", "railgun", "bomb", "cluster"):
        return aligned or random.random() < 0.35
    if stored == "burst":
        return aligned or random.random() < 0.5
    return random.random() < 0.25


def choose_ai_actions(
    state: dict,
    player_id: str,
    fighter: dict[str, Any],
) -> tuple[str, bool, bool, bool, int, bool, bool, bool]:
    """Returns move, shoot, charge_start, charge_release, charge_ticks, pu_start, pu_release, pu_instant."""
    height = _fighter_height(state)
    bullets = _incoming_bullets(state, player_id, fighter)
    enemy = _enemy_fighter(state, player_id)

    move = _choose_move(fighter, state, height, bullets, enemy)

    shoot = False
    charge_start = False
    charge_release = False
    charge_ticks = 0
    pu_start = False
    pu_release = False
    pu_instant = False

    if _should_use_instant_powerup(state, fighter, enemy, height):
        return move, shoot, charge_start, charge_release, charge_ticks, pu_start, pu_release, True

    pu_start, pu_release = _should_activate_powerup(state, fighter, enemy, height)
    if pu_start or pu_release:
        return move, shoot, charge_start, charge_release, charge_ticks, pu_start, pu_release, pu_instant

    if enemy is not None:
        if fighter.get("charging"):
            charge_ticks = fighter.get("charge_ticks", 0) + 1
            if charge_ticks >= 8 or _should_shoot(state, fighter, enemy, height, move):
                charge_release = True
            else:
                charge_start = True
        else:
            want_charge, ticks = _should_charge(state, fighter, enemy, height, move)
            if want_charge and random.random() < 0.55 and not fighter.get("stored_powerup"):
                charge_start = True
                charge_ticks = ticks
            elif _should_shoot(state, fighter, enemy, height, move):
                shoot = True

    return move, shoot, charge_start, charge_release, charge_ticks, pu_start, pu_release, pu_instant
