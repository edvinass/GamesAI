import random
from typing import Any


def _fighter_height(state: dict) -> int:
    return int(state["settings"].get("fighter_height", 3))


def _fighter_rows(fighter: dict[str, Any], height: int) -> range:
    top = fighter["y"]
    return range(top, top + height)


def _incoming_bullets(state: dict, player_id: str, fighter: dict[str, Any]) -> list[dict]:
    bullets = []
    for bullet in state.get("bullets", []):
        if bullet["owner_id"] == player_id:
            continue
        if fighter["side"] == "left" and bullet["vx"] > 0:
            bullets.append(bullet)
        elif fighter["side"] == "right" and bullet["vx"] < 0:
            bullets.append(bullet)
    return bullets


def _bullet_threatens_rows(bullet: dict, rows: range) -> bool:
    return bullet["y"] in rows


def _rows_after_move(top: int, height: int, direction: str) -> range:
    if direction == "up":
        return range(top - 1, top - 1 + height)
    if direction == "down":
        return range(top + 1, top + 1 + height)
    return range(top, top + height)


def choose_ai_actions(
    state: dict,
    player_id: str,
    fighter: dict[str, Any],
) -> tuple[str, bool]:
    grid_height = state["grid_height"]
    height = _fighter_height(state)
    y = fighter["y"]
    threats = _incoming_bullets(state, player_id, fighter)
    occupied_rows = _fighter_rows(fighter, height)

    threatened = any(_bullet_threatens_rows(b, occupied_rows) for b in threats)
    safe_up = y > 0 and not any(
        _bullet_threatens_rows(b, _rows_after_move(y, height, "up")) for b in threats
    )
    safe_down = y + height < grid_height and not any(
        _bullet_threatens_rows(b, _rows_after_move(y, height, "down")) for b in threats
    )

    move = "stop"
    if threatened:
        if safe_up and safe_down:
            move = random.choice(["up", "down"])
        elif safe_up:
            move = "up"
        elif safe_down:
            move = "down"
    elif random.random() < 0.35:
        max_y = grid_height - height
        if y > 0 and y < max_y:
            move = random.choice(["up", "down", "stop"])
        elif y == 0:
            move = random.choice(["down", "stop"])
        else:
            move = random.choice(["up", "stop"])

    tick = state["tick"]
    can_shoot = tick >= fighter.get("cooldown_until_tick", 0)
    shoot_row = y + height // 2
    enemy_rows: range | None = None
    for pid, other in state["fighters"].items():
        if pid != player_id and other.get("alive"):
            enemy_rows = _fighter_rows(other, height)
            break

    shoot = False
    if can_shoot:
        if enemy_rows is not None and shoot_row in enemy_rows:
            shoot = True
        elif random.random() < 0.12:
            shoot = True

    return move, shoot
