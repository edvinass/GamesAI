import random
from typing import Any

POWERUP_ACTIVATION_TICKS = 8

FULL_CHARGE_TICKS = 11
MID_CHARGE_TICKS = 8

INSTANT_POWERUP_TYPES = frozenset(
    {"heal", "laser", "railgun", "bomb", "cluster", "burst", "decoy"}
)

POWERUP_CHANNEL_TICKS: dict[str, int] = {
    "rapid_fire": 6,
    "machine_gun": 6,
    "shield": 8,
    "wide_shot": 6,
    "homing": 7,
    "pierce": 7,
    "ghost": 7,
    "freeze": 8,
    "mirror": 8,
    "overdrive": 7,
    "phase_shift": 7,
}

OFFENSIVE_BUFF_TYPES = frozenset(
    {"rapid_fire", "machine_gun", "homing", "overdrive", "pierce", "wide_shot", "phase_shift"}
)

DEFENSIVE_BUFF_TYPES = frozenset({"shield", "ghost", "mirror"})

MOVE_OPTIONS = ("up", "down", "stop")

AI_DIFFICULTIES = ("easy", "medium", "hard", "pro")

DIFFICULTY_CONFIG: dict[str, dict[str, float | int]] = {
    "easy": {
        "reaction_interval": 3,
        "move_interval": 3,
        "mistake_rate": 0.2,
        "dodge_weight": 0.55,
        "charge_rate": 0.35,
    },
    "medium": {
        "reaction_interval": 2,
        "move_interval": 2,
        "mistake_rate": 0.06,
        "dodge_weight": 1.0,
        "charge_rate": 0.65,
    },
    "hard": {
        "reaction_interval": 1,
        "move_interval": 1,
        "mistake_rate": 0.0,
        "dodge_weight": 1.25,
        "charge_rate": 0.85,
    },
    "pro": {
        "reaction_interval": 1,
        "move_interval": 1,
        "mistake_rate": 0.0,
        "dodge_weight": 1.4,
        "charge_rate": 0.95,
    },
}

PERSONALITY_MODIFIERS: dict[str, dict[str, float]] = {
    "balanced": {"dodge_weight": 1.0, "charge_rate": 1.0, "offense_bias": 0.5},
    "aggressive": {"dodge_weight": 0.75, "charge_rate": 1.2, "offense_bias": 0.85},
    "turtle": {"dodge_weight": 1.35, "charge_rate": 0.7, "offense_bias": 0.25},
    "trickster": {"dodge_weight": 1.0, "charge_rate": 0.9, "offense_bias": 0.6},
}


def normalize_ai_difficulty(value: str | None) -> str:
    aliases = {"normal": "medium"}
    normalized = aliases.get(str(value or "").lower(), str(value or "").lower())
    if normalized in DIFFICULTY_CONFIG:
        return normalized
    return "medium"


def get_ai_config(difficulty: str | None, state: dict | None = None) -> dict[str, float | int]:
    cfg = dict(DIFFICULTY_CONFIG[normalize_ai_difficulty(difficulty)])
    if state:
        personality = str(state.get("settings", {}).get("ai_personality", "balanced")).lower()
        mods = PERSONALITY_MODIFIERS.get(personality, PERSONALITY_MODIFIERS["balanced"])
        cfg["dodge_weight"] = float(cfg["dodge_weight"]) * float(mods["dodge_weight"])
        cfg["charge_rate"] = min(1.0, float(cfg["charge_rate"]) * float(mods["charge_rate"]))
        cfg["offense_bias"] = float(mods["offense_bias"])
        settings = state.get("settings", {})
        if "ai_move_interval_ticks" in settings:
            cfg["move_interval"] = int(settings["ai_move_interval_ticks"])
        if "ai_reaction_interval_ticks" in settings:
            cfg["reaction_interval"] = int(settings["ai_reaction_interval_ticks"])
    return cfg


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


def _effect_active(fighter: dict[str, Any], tick: int, until_key: str) -> bool:
    return tick < fighter.get("effects", {}).get(until_key, 0)


def _has_offensive_buff(fighter: dict[str, Any], tick: int) -> bool:
    effects = fighter.get("effects", {})
    return any(
        tick < effects.get(f"{name}_until", 0)
        for name in OFFENSIVE_BUFF_TYPES
    )


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


def _row_gap_to_enemy(shoot_row: int, enemy_top: int, height: int) -> int:
    enemy_rows = _fighter_rows(enemy_top, height)
    if shoot_row in enemy_rows:
        return 0
    return min(abs(shoot_row - row) for row in enemy_rows)


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


def _immediate_bullet_threat(
    fighter: dict[str, Any],
    height: int,
    bullets: list[dict],
    max_ticks: int = 10,
) -> bool:
    rows = _fighter_rows(fighter["y"], height)
    for bullet in bullets:
        if not _bullet_heading_toward(bullet, fighter["x"], fighter["side"]):
            continue
        if bullet["y"] in rows and _ticks_until_column(bullet, fighter["x"]) <= max_ticks:
            return True
    return False


def _count_incoming_bullets(fighter: dict[str, Any], height: int, bullets: list[dict]) -> int:
    count = 0
    center = _fighter_center(fighter["y"], height)
    for bullet in bullets:
        if not _bullet_heading_toward(bullet, fighter["x"], fighter["side"]):
            continue
        if _ticks_until_column(bullet, fighter["x"]) <= 18:
            if bullet["y"] in _fighter_rows(fighter["y"], height) or abs(bullet["y"] - center) <= height + 1:
                count += 1
    return count


def _powerup_urgency(state: dict, powerup: dict | None) -> float:
    if not powerup:
        return 0.0
    despawn = powerup.get("despawn_at_tick")
    if despawn is None:
        return 0.2
    remaining = int(despawn) - state["tick"]
    if remaining <= 20:
        return 1.0
    if remaining <= 40:
        return 0.65
    return 0.25


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
    state: dict,
    dodge_weight: float = 1.0,
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
            score -= (2000.0 + max(0, 24 - ticks) * 80.0) * dodge_weight
            immediate_danger = True
            continue

        score += 20.0 + min(ticks, 20)

        old_gap = abs(bullet_y - old_center)
        new_gap = abs(bullet_y - new_center)

        if abs(bullet_y - old_center) <= height + 2 and ticks <= 14:
            score += (new_gap - old_gap) * 35.0 * dodge_weight
            if ticks <= 8:
                immediate_danger = True

    if incoming and direction == "stop":
        score -= 120.0 * dodge_weight

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

    if powerup and not fighter.get("stored_powerup"):
        urgency = _powerup_urgency(state, powerup)
        center_row = _fighter_center(new_top, height)
        dist = abs(center_row - powerup["y"])
        pickup_weight = 280.0 + urgency * 220.0
        if dist == 0:
            score += pickup_weight
        elif dist <= 1:
            score += pickup_weight * 0.72
        elif dist <= 2:
            score += pickup_weight * 0.42
        elif dist <= 3 and urgency >= 0.6:
            score += pickup_weight * 0.25

        if not immediate_danger and dist <= 2:
            if center_row < powerup["y"] and direction == "down":
                score += 40.0
            elif center_row > powerup["y"] and direction == "up":
                score += 40.0

    return score


def _choose_move(
    fighter: dict[str, Any],
    state: dict,
    height: int,
    bullets: list[dict],
    enemy: dict[str, Any] | None,
    cfg: dict[str, float | int] | None = None,
) -> str:
    ai_cfg = cfg or get_ai_config("medium")
    dodge_weight = float(ai_cfg.get("dodge_weight", 1.0))
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
            state,
            dodge_weight=dodge_weight,
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

        if powerup and not fighter.get("stored_powerup"):
            pursuit_target = powerup["y"]

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
        move = best_direction
    else:
        move = max(scored, key=lambda item: item[1])[0]

    mistake_rate = float(ai_cfg.get("mistake_rate", 0.0))
    if mistake_rate > 0 and random.random() < mistake_rate:
        return random.choice(MOVE_OPTIONS)
    return move


def _aim_row_after_move(
    fighter: dict[str, Any],
    height: int,
    move_direction: str,
    state: dict,
) -> int:
    min_y, max_y = _playable_bounds(state, height)
    shoot_top = _top_after_move(fighter["y"], move_direction, min_y, max_y)
    return _fighter_center(shoot_top, height)


def _predicted_enemy_top(
    state: dict,
    fighter: dict[str, Any],
    enemy: dict[str, Any],
    height: int,
) -> int:
    min_y, max_y = _playable_bounds(state, height)
    speed = int(state["settings"].get("bullet_speed", 1))
    travel = _travel_ticks_to_enemy(fighter, enemy, speed)
    return _predict_enemy_top(enemy, height, state["grid_height"], travel, min_y, max_y)


def _should_shoot(
    state: dict,
    fighter: dict[str, Any],
    enemy: dict[str, Any],
    height: int,
    move_direction: str,
    cfg: dict[str, float | int] | None = None,
) -> bool:
    ai_cfg = cfg or get_ai_config(state["settings"].get("ai_difficulty"), state)
    offense_bias = float(ai_cfg.get("offense_bias", 0.5))
    difficulty = normalize_ai_difficulty(state["settings"].get("ai_difficulty"))
    tick = state["tick"]
    if tick < fighter.get("cooldown_until_tick", 0):
        return False

    shoot_row = _aim_row_after_move(fighter, height, move_direction, state)
    min_y, max_y = _playable_bounds(state, height)
    speed = int(state["settings"].get("bullet_speed", 1))

    if _effect_active(fighter, tick, "machine_gun_until"):
        return True

    if _effect_active(fighter, tick, "homing_until"):
        gap = _row_gap_to_enemy(shoot_row, enemy["y"], height)
        if gap <= height + 1:
            return True

    if _effect_active(fighter, tick, "rapid_fire_until"):
        gap = _row_gap_to_enemy(shoot_row, _predicted_enemy_top(state, fighter, enemy, height), height)
        if gap <= 1:
            return True

    travel = _travel_ticks_to_enemy(fighter, enemy, speed)
    predicted_top = _predict_enemy_top(
        enemy, height, state["grid_height"], travel, min_y, max_y
    )
    if _shot_aligns_with_enemy(shoot_row, predicted_top, height):
        return True

    if _shot_aligns_with_enemy(shoot_row, enemy["y"], height):
        return True

    direction = enemy.get("move_direction", "stop")
    if direction in ("up", "down"):
        next_top = _predict_enemy_top(enemy, height, state["grid_height"], 1, min_y, max_y)
        if _shot_aligns_with_enemy(shoot_row, next_top, height):
            return True

    if travel <= 20:
        if _shot_aligns_with_enemy(shoot_row, predicted_top, height):
            return True
    if difficulty == "pro" and travel <= 28:
        lead_top = _predict_enemy_top(enemy, height, state["grid_height"], 2, min_y, max_y)
        if _shot_aligns_with_enemy(shoot_row, lead_top, height):
            return True

    gap = _row_gap_to_enemy(shoot_row, enemy["y"], height)
    if gap <= 1:
        return True
    if gap <= 2 and offense_bias >= 0.55:
        return True
    if difficulty == "pro" and gap <= 2 and travel <= 18:
        return True

    if _has_offensive_buff(fighter, tick) and gap <= 2:
        return True

    powerup = state.get("powerup")
    if powerup and not fighter.get("stored_powerup"):
        if abs(shoot_row - powerup["y"]) <= 2:
            return True
        if abs(shoot_row - powerup["y"]) <= 4 and random.random() < 0.75:
            return True

    return False


def _should_charge(
    state: dict,
    fighter: dict[str, Any],
    enemy: dict[str, Any],
    height: int,
    move_direction: str,
    bullets: list[dict],
    cfg: dict[str, float | int] | None = None,
) -> tuple[bool, int]:
    ai_cfg = cfg or get_ai_config("medium")
    charge_rate = float(ai_cfg.get("charge_rate", 0.65))
    offense_bias = float(ai_cfg.get("offense_bias", 0.5))
    difficulty = normalize_ai_difficulty(state["settings"].get("ai_difficulty"))
    if not state["settings"].get("charge_shot_enabled"):
        return False, 0
    tick = state["tick"]
    if tick < fighter.get("cooldown_until_tick", 0):
        return False, 0
    if fighter.get("stored_powerup"):
        return False, 0
    if _effect_active(fighter, tick, "machine_gun_until"):
        return False, 0
    if _immediate_bullet_threat(fighter, height, bullets, max_ticks=12):
        return False, 0

    shoot_row = _aim_row_after_move(fighter, height, move_direction, state)
    predicted_top = _predicted_enemy_top(state, fighter, enemy, height)
    gap = _row_gap_to_enemy(shoot_row, predicted_top, height)
    relaxed_safe = not _immediate_bullet_threat(fighter, height, bullets, max_ticks=18)
    enemy_low_hp = enemy.get("hp", 3) <= 2

    if gap == 0:
        if difficulty == "pro" and enemy.get("hp", 3) <= 1:
            return True, FULL_CHARGE_TICKS
        if offense_bias >= 0.7:
            return True, FULL_CHARGE_TICKS
        return True, FULL_CHARGE_TICKS
    if gap <= 1:
        if relaxed_safe and (enemy_low_hp or random.random() < charge_rate):
            return True, FULL_CHARGE_TICKS
        return True, MID_CHARGE_TICKS
    if difficulty == "pro" and gap <= 2 and relaxed_safe and offense_bias >= 0.5:
        return True, MID_CHARGE_TICKS
    if _should_shoot(state, fighter, enemy, height, move_direction, cfg) and gap <= 2:
        if relaxed_safe and random.random() < charge_rate * 0.55:
            return True, FULL_CHARGE_TICKS
        return True, MID_CHARGE_TICKS
    return False, 0


def _charge_release_ticks(
    state: dict,
    fighter: dict[str, Any],
    enemy: dict[str, Any],
    height: int,
    move_direction: str,
    charge_ticks: int,
    bullets: list[dict],
) -> int:
    if _immediate_bullet_threat(fighter, height, bullets, max_ticks=8):
        return max(charge_ticks, 1)

    shoot_row = _aim_row_after_move(fighter, height, move_direction, state)
    predicted_top = _predicted_enemy_top(state, fighter, enemy, height)
    gap = _row_gap_to_enemy(shoot_row, predicted_top, height)

    if gap == 0:
        if charge_ticks >= FULL_CHARGE_TICKS:
            return charge_ticks
        return 0
    if gap <= 1 and charge_ticks >= MID_CHARGE_TICKS:
        return charge_ticks
    if _should_shoot(state, fighter, enemy, height, move_direction) and charge_ticks >= MID_CHARGE_TICKS:
        return charge_ticks
    if charge_ticks >= FULL_CHARGE_TICKS + 2:
        return FULL_CHARGE_TICKS
    return 0


def _should_activate_powerup(
    state: dict,
    fighter: dict[str, Any],
    enemy: dict[str, Any] | None,
    height: int,
    bullets: list[dict],
) -> tuple[bool, bool]:
    """Returns powerup_hold_start, powerup_hold_release."""
    if not state["settings"].get("powerups_enabled"):
        return False, False
    stored = fighter.get("stored_powerup")
    if not stored or stored in INSTANT_POWERUP_TYPES:
        return False, False

    if fighter.get("activating_powerup"):
        ticks = fighter.get("powerup_activation_ticks", 0) + 1
        required = POWERUP_CHANNEL_TICKS.get(stored, POWERUP_ACTIVATION_TICKS)
        if ticks >= required:
            return False, True
        return False, False

    tick = state["tick"]
    incoming = _count_incoming_bullets(fighter, height, bullets)
    shoot_row = _fighter_center(fighter["y"], height)

    if stored == "shield":
        if fighter.get("hp", 1) <= 2:
            return True, False
        if incoming >= 2:
            return True, False
        if fighter.get("hp", 1) < fighter.get("max_hp", 3) and incoming >= 1:
            return True, False
    elif stored == "freeze" and enemy is not None:
        travel = _travel_ticks_to_enemy(fighter, enemy, int(state["settings"].get("bullet_speed", 1)))
        if travel <= 35:
            return True, False
    elif stored == "ghost":
        if incoming >= 2:
            return True, False
        if incoming >= 1 and random.random() < 0.5:
            return True, False
    elif stored == "mirror":
        if incoming >= 1:
            return True, False
    elif stored in OFFENSIVE_BUFF_TYPES:
        offense_bias = float(
            get_ai_config(state["settings"].get("ai_difficulty"), state).get("offense_bias", 0.5)
        )
        if enemy is not None:
            enemy_center = _fighter_center(enemy["y"], height)
            if abs(shoot_row - enemy_center) <= 2:
                return True, False
            travel = _travel_ticks_to_enemy(fighter, enemy, int(state["settings"].get("bullet_speed", 1)))
            if travel <= 25:
                return True, False
        if stored == "phase_shift" and incoming >= 1:
            return True, False
        if random.random() < 0.15 + offense_bias * 0.2:
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

    hp = fighter.get("hp", 1)
    max_hp = fighter.get("max_hp", 3)

    if stored == "heal":
        return hp < max_hp

    if enemy is None:
        return False

    shoot_row = _fighter_center(fighter["y"], height)
    predicted_top = _predicted_enemy_top(state, fighter, enemy, height)
    gap = _row_gap_to_enemy(shoot_row, predicted_top, height)
    travel = _travel_ticks_to_enemy(fighter, enemy, int(state["settings"].get("bullet_speed", 1)))

    if stored in ("laser", "railgun"):
        return gap <= 1

    if stored in ("bomb", "cluster"):
        if stored == "bomb" and enemy is not None:
            enemy_effects = enemy.get("effects", {})
            if state["tick"] < enemy_effects.get("freeze_until", 0):
                return True
        return gap <= 1 or (gap <= 2 and travel <= 18)

    if stored == "decoy":
        return random.random() < 0.45

    if stored == "burst":
        return gap <= 2 or (gap <= 3 and travel <= 22)

    return False


def choose_ai_actions(
    state: dict,
    player_id: str,
    fighter: dict[str, Any],
    difficulty: str | None = None,
) -> tuple[str, bool, bool, bool, int, bool, bool, bool]:
    """Returns move, shoot, charge_start, charge_release, charge_ticks, pu_start, pu_release, pu_instant."""
    cfg = get_ai_config(difficulty, state)
    height = _fighter_height(state)
    bullets = _incoming_bullets(state, player_id, fighter)
    enemy = _enemy_fighter(state, player_id)

    move = _choose_move(fighter, state, height, bullets, enemy, cfg)

    shoot = False
    charge_start = False
    charge_release = False
    charge_ticks = 0
    pu_start = False
    pu_release = False
    pu_instant = False

    if _should_use_instant_powerup(state, fighter, enemy, height):
        return move, shoot, charge_start, charge_release, charge_ticks, pu_start, pu_release, True

    pu_start, pu_release = _should_activate_powerup(state, fighter, enemy, height, bullets)
    if pu_start or pu_release:
        return move, shoot, charge_start, charge_release, charge_ticks, pu_start, pu_release, pu_instant

    if enemy is not None:
        tick = state["tick"]
        if fighter.get("charging"):
            charge_ticks = fighter.get("charge_ticks", 0) + 1
            release_ticks = _charge_release_ticks(
                state, fighter, enemy, height, move, charge_ticks, bullets
            )
            if release_ticks:
                charge_release = True
                charge_ticks = release_ticks
        else:
            want_charge, ticks = _should_charge(state, fighter, enemy, height, move, bullets, cfg)
            if want_charge:
                charge_start = True
                charge_ticks = ticks
            elif _should_shoot(state, fighter, enemy, height, move, cfg):
                shoot = True
            elif _effect_active(fighter, tick, "machine_gun_until"):
                shoot = True

    return move, shoot, charge_start, charge_release, charge_ticks, pu_start, pu_release, pu_instant
