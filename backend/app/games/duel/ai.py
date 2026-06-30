import random
from typing import Any

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
    return abs(bullet["x"] - fighter_x)


def _top_after_move(top: int, direction: str, max_y: int) -> int:
    if direction == "up":
        return max(0, top - 1)
    if direction == "down":
        return min(max_y, top + 1)
    return top


def _predict_enemy_top(
    enemy: dict[str, Any],
    height: int,
    grid_height: int,
    ticks: int,
) -> int:
    y = enemy["y"]
    direction = enemy.get("move_direction", "stop")
    max_y = grid_height - height
    for _ in range(max(0, ticks)):
        y = _top_after_move(y, direction, max_y)
    return y


def _travel_ticks_to_enemy(fighter: dict[str, Any], enemy: dict[str, Any]) -> int:
    return max(0, abs(enemy["x"] - fighter["x"]) - 1)


def _shot_aligns_with_enemy(shoot_row: int, enemy_top: int, height: int) -> bool:
    return shoot_row in _fighter_rows(enemy_top, height)


def _enemy_aim_centers(
    enemy: dict[str, Any],
    fighter: dict[str, Any],
    height: int,
    grid_height: int,
) -> tuple[int, int]:
    travel = _travel_ticks_to_enemy(fighter, enemy)
    lead_ticks = min(max(travel, 1), 24)
    predicted_top = _predict_enemy_top(enemy, height, grid_height, lead_ticks)
    current_center = _fighter_center(enemy["y"], height)
    lead_center = _fighter_center(predicted_top, height)
    return current_center, lead_center


def _bullet_threatens_move(
    bullet: dict,
    fighter: dict[str, Any],
    height: int,
    new_top: int,
    old_center: int,
) -> bool:
    if not _bullet_heading_toward(bullet, fighter["x"], fighter["side"]):
        return False
    bullet_y = bullet["y"]
    new_rows = _fighter_rows(new_top, height)
    ticks = _ticks_until_column(bullet, fighter["x"])
    if bullet_y in new_rows:
        return True
    if ticks <= 10 and abs(bullet_y - old_center) <= height + 1:
        return True
    return False


def _move_is_safe_from_bullets(
    direction: str,
    fighter: dict[str, Any],
    height: int,
    grid_height: int,
    bullets: list[dict],
) -> bool:
    max_y = grid_height - height
    new_top = _top_after_move(fighter["y"], direction, max_y)
    old_center = _fighter_center(fighter["y"], height)
    for bullet in bullets:
        if _bullet_threatens_move(bullet, fighter, height, new_top, old_center):
            if bullet["y"] in _fighter_rows(new_top, height):
                return False
    return True


def _score_move(
    direction: str,
    fighter: dict[str, Any],
    height: int,
    grid_height: int,
    bullets: list[dict],
    enemy: dict[str, Any] | None,
) -> float:
    y = fighter["y"]
    max_y = grid_height - height
    new_top = _top_after_move(y, direction, max_y)
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

    edge_clearance = min(new_top, max_y - new_top)
    score += edge_clearance * 12.0

    if new_top == 0 or new_top == max_y:
        wall_penalty = 140.0 if immediate_danger else 180.0
        score -= wall_penalty

    if enemy is not None and not immediate_danger:
        current_center, lead_center = _enemy_aim_centers(enemy, fighter, height, grid_height)
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
        if y == 0 and direction == "down":
            score += 90.0
        if y == max_y and direction == "up":
            score += 90.0

    return score


def _choose_move(
    fighter: dict[str, Any],
    height: int,
    grid_height: int,
    bullets: list[dict],
    enemy: dict[str, Any] | None,
) -> str:
    max_y = grid_height - height

    scored: list[tuple[str, float]] = []
    for direction in MOVE_OPTIONS:
        score = _score_move(direction, fighter, height, grid_height, bullets, enemy)
        scored.append((direction, score))

    safe_moves = [
        d for d, _ in scored
        if _move_is_safe_from_bullets(d, fighter, height, grid_height, bullets)
    ]

    if safe_moves:
        if enemy is not None:
            _, lead_center = _enemy_aim_centers(enemy, fighter, height, grid_height)
            pursuit_target = lead_center
        else:
            pursuit_target = _arena_center_row(grid_height, height)

        best_direction = safe_moves[0]
        best_score = float("-inf")
        best_target_dist = float("inf")

        for direction, score in scored:
            if direction not in safe_moves:
                continue
            new_top = _top_after_move(fighter["y"], direction, max_y)
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

    grid_height = state["grid_height"]
    max_y = grid_height - height
    shoot_top = _top_after_move(fighter["y"], move_direction, max_y)
    shoot_row = _fighter_center(shoot_top, height)

    travel = _travel_ticks_to_enemy(fighter, enemy)
    predicted_top = _predict_enemy_top(enemy, height, grid_height, travel)
    if _shot_aligns_with_enemy(shoot_row, predicted_top, height):
        return True

    current_top = enemy["y"]
    if _shot_aligns_with_enemy(shoot_row, current_top, height):
        return True

    direction = enemy.get("move_direction", "stop")
    if direction in ("up", "down"):
        next_top = _predict_enemy_top(enemy, height, grid_height, 1)
        if _shot_aligns_with_enemy(shoot_row, next_top, height):
            return True

    if travel <= 20:
        predicted_top = _predict_enemy_top(enemy, height, grid_height, travel)
        if _shot_aligns_with_enemy(shoot_row, predicted_top, height):
            return True

    enemy_center = _fighter_center(current_top, height)
    if abs(shoot_row - enemy_center) <= 1:
        return True

    return False


def choose_ai_actions(
    state: dict,
    player_id: str,
    fighter: dict[str, Any],
) -> tuple[str, bool]:
    height = _fighter_height(state)
    grid_height = state["grid_height"]
    bullets = _incoming_bullets(state, player_id, fighter)
    enemy = _enemy_fighter(state, player_id)

    move = _choose_move(fighter, height, grid_height, bullets, enemy)

    shoot = False
    if enemy is not None:
        shoot = _should_shoot(state, fighter, enemy, height, move)

    return move, shoot
