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

        # Only dodge away from bullets that are actually near our line
        if abs(bullet_y - old_center) <= height + 2 and ticks <= 14:
            score += (new_gap - old_gap) * 35.0
            if ticks <= 8:
                immediate_danger = True

    if incoming and direction == "stop":
        score -= 120.0

    # Prefer having room to maneuver — avoid hugging top/bottom walls
    edge_clearance = min(new_top, max_y - new_top)
    score += edge_clearance * 22.0

    if new_top == 0 or new_top == max_y:
        wall_penalty = 140.0 if immediate_danger else 220.0
        score -= wall_penalty

    # When not in immediate danger, drift back toward arena center
    if not immediate_danger:
        score -= abs(new_center - arena_center) * 16.0
        if y == 0 and direction == "down":
            score += 90.0
        if y == max_y and direction == "up":
            score += 90.0
        if edge_clearance <= 1 and direction != "stop":
            toward_center = "down" if new_center < arena_center else "up"
            if direction == toward_center:
                score += 70.0

    if enemy is not None and not immediate_danger:
        travel = _travel_ticks_to_enemy(fighter, enemy)
        target_top = _predict_enemy_top(enemy, height, grid_height, min(travel, 12))
        target_center = _fighter_center(target_top, height)
        score -= abs(new_center - target_center) * 6.0
    elif enemy is not None and not immediate_danger and incoming == 0:
        target_center = _fighter_center(enemy["y"], height)
        score -= abs(new_center - target_center) * 4.0

    return score


def _choose_move(
    fighter: dict[str, Any],
    height: int,
    grid_height: int,
    bullets: list[dict],
    enemy: dict[str, Any] | None,
) -> str:
    arena_center = _arena_center_row(grid_height, height)
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
        candidates = [(d, s) for d, s in scored if d in safe_moves]
        best_center_dist = float("inf")
        best_direction = safe_moves[0]
        best_score = float("-inf")

        for direction, score in candidates:
            new_top = _top_after_move(fighter["y"], direction, max_y)
            center_dist = abs(_fighter_center(new_top, height) - arena_center)
            # Among similarly safe options, prefer center and higher score
            if score > best_score or (score >= best_score - 30 and center_dist < best_center_dist):
                best_score = score
                best_center_dist = center_dist
                best_direction = direction
        return best_direction

    return max(scored, key=lambda item: item[1])[0]


def _should_shoot(
    state: dict,
    fighter: dict[str, Any],
    enemy: dict[str, Any],
    height: int,
) -> bool:
    tick = state["tick"]
    if tick < fighter.get("cooldown_until_tick", 0):
        return False

    grid_height = state["grid_height"]
    travel = _travel_ticks_to_enemy(fighter, enemy)
    shoot_row = _fighter_center(fighter["y"], height)

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

    if travel <= 15:
        predicted_top = _predict_enemy_top(enemy, height, grid_height, travel)
        if _shot_aligns_with_enemy(shoot_row, predicted_top, height):
            return True

    enemy_center = _fighter_center(current_top, height)
    if abs(shoot_row - enemy_center) <= 1 and random.random() < 0.5:
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
        shoot = _should_shoot(state, fighter, enemy, height)

    return move, shoot
