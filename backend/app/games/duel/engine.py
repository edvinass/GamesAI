import random
from datetime import datetime, timedelta, timezone
from typing import Any

from app.games.base import GamePlugin
from app.games.duel.ai import choose_ai_actions

FIGHTER_COLORS = ["#3b82f6", "#ef4444"]

FIGHTER_HEIGHT = 3

MOVE_DIRECTIONS = {"up", "down", "stop"}

POWERUP_TYPES = (
    "rapid_fire",
    "shield",
    "wide_shot",
    "ghost",
    "freeze",
    "laser",
    "homing",
    "heal",
    "mirror",
    "overdrive",
)

POWERUP_ACTIVATION_TICKS = 12

CLIENT_PROGRESS_LAG_TICKS = 2

MUTATOR_PRESETS: dict[str, dict[str, Any]] = {
    "classic": {
        "bullet_speed": 2,
        "shoot_cooldown_ticks": 10,
        "ricochet_bounces": 0,
        "fog": False,
        "max_bullets_per_player": 12,
    },
    "chaos": {
        "bullet_speed": 3,
        "shoot_cooldown_ticks": 5,
        "ricochet_bounces": 0,
        "fog": False,
        "max_bullets_per_player": 6,
    },
    "sniper": {
        "bullet_speed": 2,
        "shoot_cooldown_ticks": 20,
        "ricochet_bounces": 0,
        "fog": False,
        "max_bullets_per_player": 4,
        "instant_kill": True,
    },
    "bounce_house": {
        "bullet_speed": 2,
        "shoot_cooldown_ticks": 10,
        "ricochet_bounces": 1,
        "fog": False,
        "max_bullets_per_player": 8,
        "obstacles_enabled": True,
    },
    "fog": {
        "bullet_speed": 2,
        "shoot_cooldown_ticks": 10,
        "ricochet_bounces": 0,
        "fog": True,
        "max_bullets_per_player": 10,
    },
}

MATCH_FORMAT_PRESETS: dict[str, dict[str, Any]] = {
    "quick_duel": {
        "best_of": 1,
        "fighter_hp": 1,
        "powerups_enabled": False,
        "shrinking_arena": False,
        "obstacles_enabled": False,
        "charge_shot_enabled": False,
        "round_countdown_sec": 2,
    },
    "best_of_3": {
        "best_of": 3,
        "fighter_hp": 3,
        "powerups_enabled": True,
        "shrinking_arena": True,
        "obstacles_enabled": True,
        "charge_shot_enabled": True,
        "round_countdown_sec": 3,
    },
    "best_of_5": {
        "best_of": 5,
        "fighter_hp": 3,
        "powerups_enabled": True,
        "shrinking_arena": True,
        "obstacles_enabled": True,
        "charge_shot_enabled": True,
        "round_countdown_sec": 3,
    },
}


class DuelEngine(GamePlugin):
    game_type = "duel"

    def default_settings(self) -> dict:
        return {
            "min_players": 2,
            "max_players": 2,
            "grid_width": 48,
            "grid_height": 24,
            "tick_ms": 75,
            "countdown_sec": 3,
            "shoot_cooldown_ticks": 10,
            "fighter_height": FIGHTER_HEIGHT,
            "ai_move_interval_ticks": 2,
            "ai_reaction_interval_ticks": 2,
            "solo_practice": False,
            "match_format": "best_of_5",
            "mutator": "classic",
            "obstacle_count": 3,
            "powerup_interval_ticks": 160,
            "powerup_lifetime_ticks": 120,
            "powerup_spawn_jitter_ticks": 40,
            "shrink_start_tick": 240,
            "shrink_interval_ticks": 80,
            "charge_max_ticks": 15,
            "effect_duration_ticks": 80,
        }

    def validate_settings(self, settings: dict) -> dict:
        defaults = self.default_settings()
        merged = {**defaults, **(settings or {})}
        merged["min_players"] = 2
        merged["max_players"] = 2
        merged["grid_width"] = max(20, min(80, int(merged.get("grid_width", 48))))
        merged["grid_height"] = max(12, min(40, int(merged.get("grid_height", 24))))
        merged["tick_ms"] = max(50, min(200, int(merged.get("tick_ms", 75))))
        merged["countdown_sec"] = max(1, min(10, int(merged.get("countdown_sec", 3))))
        merged["shoot_cooldown_ticks"] = max(4, min(30, int(merged.get("shoot_cooldown_ticks", 10))))
        merged["fighter_height"] = max(1, min(5, int(merged.get("fighter_height", FIGHTER_HEIGHT))))
        merged["ai_move_interval_ticks"] = max(1, min(4, int(merged.get("ai_move_interval_ticks", 2))))
        merged["ai_reaction_interval_ticks"] = max(1, min(4, int(merged.get("ai_reaction_interval_ticks", 2))))
        merged["solo_practice"] = bool(merged.get("solo_practice", False))

        match_format = merged.get("match_format", "best_of_5")
        if match_format not in MATCH_FORMAT_PRESETS:
            match_format = "best_of_5"
        merged["match_format"] = match_format

        mutator = merged.get("mutator", "classic")
        if mutator not in MUTATOR_PRESETS:
            mutator = "classic"
        merged["mutator"] = mutator

        merged["obstacle_count"] = max(0, min(6, int(merged.get("obstacle_count", 3))))
        merged["powerup_interval_ticks"] = max(80, min(400, int(merged.get("powerup_interval_ticks", 160))))
        merged["powerup_lifetime_ticks"] = max(40, min(300, int(merged.get("powerup_lifetime_ticks", 120))))
        merged["powerup_spawn_jitter_ticks"] = max(
            0, min(120, int(merged.get("powerup_spawn_jitter_ticks", 40)))
        )
        merged["shrink_start_tick"] = max(120, min(600, int(merged.get("shrink_start_tick", 240))))
        merged["shrink_interval_ticks"] = max(40, min(200, int(merged.get("shrink_interval_ticks", 80))))
        merged["charge_max_ticks"] = max(8, min(30, int(merged.get("charge_max_ticks", 15))))
        merged["effect_duration_ticks"] = max(40, min(200, int(merged.get("effect_duration_ticks", 80))))

        format_preset = MATCH_FORMAT_PRESETS[match_format]
        mutator_preset = MUTATOR_PRESETS[mutator]
        merged["best_of"] = format_preset["best_of"]
        merged["fighter_hp"] = format_preset["fighter_hp"]
        merged["powerups_enabled"] = format_preset["powerups_enabled"]
        merged["shrinking_arena"] = format_preset["shrinking_arena"]
        merged["obstacles_enabled"] = format_preset.get(
            "obstacles_enabled", mutator_preset.get("obstacles_enabled", True)
        )
        merged["charge_shot_enabled"] = format_preset["charge_shot_enabled"]
        merged["round_countdown_sec"] = format_preset["round_countdown_sec"]
        merged["bullet_speed"] = mutator_preset["bullet_speed"]
        merged["ricochet_bounces"] = mutator_preset["ricochet_bounces"]
        merged["fog"] = mutator_preset["fog"]
        merged["max_bullets_per_player"] = mutator_preset["max_bullets_per_player"]
        merged["instant_kill"] = mutator_preset.get("instant_kill", False)

        if mutator == "chaos":
            merged["shoot_cooldown_ticks"] = mutator_preset["shoot_cooldown_ticks"]
        elif mutator == "sniper":
            merged["shoot_cooldown_ticks"] = mutator_preset["shoot_cooldown_ticks"]
        elif mutator == "bounce_house":
            merged["obstacles_enabled"] = True

        return merged

    def tick_interval_ms(self) -> int:
        return 75

    def validate_lobby(self, players: list[dict], settings: dict) -> str | None:
        settings = self.validate_settings(settings)
        if settings.get("solo_practice"):
            humans = [p for p in players if not p.get("is_ai")]
            if len(humans) != 1:
                return "Solo practice requires exactly one human player"
            return None

        if len(players) != 2:
            return "Side Duel requires exactly 2 players"
        return None

    def _fighter_height(self, state: dict) -> int:
        return int(state["settings"].get("fighter_height", FIGHTER_HEIGHT))

    def _fighter_hp(self, state: dict) -> int:
        return int(state["settings"].get("fighter_hp", 3))

    def _clamp_client_progress(
        self, server_ticks: int, client_ticks: int | None, max_ticks: int
    ) -> int:
        """Use server progress; allow a small client lead for network latency."""
        server = max(0, min(max_ticks, int(server_ticks)))
        if client_ticks is None:
            return server
        client = max(0, min(max_ticks, int(client_ticks)))
        if client < server:
            return server
        return min(max_ticks, min(client, server + CLIENT_PROGRESS_LAG_TICKS))

    def _rounds_to_win(self, state: dict) -> int:
        return (int(state["settings"].get("best_of", 5)) + 1) // 2

    def _generate_obstacles(self, grid_width: int, grid_height: int, count: int, fighter_height: int) -> list[dict]:
        if count <= 0:
            return []
        obstacles: list[dict] = []
        center_x = grid_width // 2
        attempts = 0
        while len(obstacles) < count and attempts < 80:
            attempts += 1
            w = random.choice([1, 2])
            h = random.choice([1, 2])
            x = random.randint(center_x - 4, center_x + 2)
            y = random.randint(2, grid_height - h - 2)
            if x <= 3 or x >= grid_width - 5:
                continue
            candidate = {"x": x, "y": y, "w": w, "h": h}
            if any(self._obstacles_overlap(candidate, existing) for existing in obstacles):
                continue
            spawn_clear = True
            mid_y = (grid_height - fighter_height) // 2
            for side_x in (1, grid_width - 2):
                for row in range(mid_y, mid_y + fighter_height):
                    if self._cell_in_obstacle(side_x, row, candidate):
                        spawn_clear = False
                        break
            if spawn_clear:
                obstacles.append(candidate)
        return obstacles

    def _obstacles_overlap(self, a: dict, b: dict) -> bool:
        return not (
            a["x"] + a["w"] <= b["x"]
            or b["x"] + b["w"] <= a["x"]
            or a["y"] + a["h"] <= b["y"]
            or b["y"] + b["h"] <= a["y"]
        )

    def _cell_in_obstacle(self, x: int, y: int, obstacle: dict) -> bool:
        return (
            obstacle["x"] <= x < obstacle["x"] + obstacle["w"]
            and obstacle["y"] <= y < obstacle["y"] + obstacle["h"]
        )

    def _cell_blocked(self, x: int, y: int, obstacles: list[dict]) -> bool:
        return any(self._cell_in_obstacle(x, y, obs) for obs in obstacles)

    def _fighter_cells(self, fighter: dict, fighter_height: int) -> list[tuple[int, int]]:
        return [(fighter["x"], fighter["y"] + i) for i in range(fighter_height)]

    def _fighter_overlaps_obstacle(self, fighter: dict, fighter_height: int, obstacles: list[dict]) -> bool:
        return any(self._cell_blocked(x, y, obstacles) for x, y in self._fighter_cells(fighter, fighter_height))

    def _spawn_side(
        self,
        index: int,
        grid_width: int,
        grid_height: int,
        fighter_height: int,
        fighter_hp: int,
        obstacles: list[dict],
        playable_y_min: int,
        playable_y_max: int,
    ) -> dict[str, Any]:
        side = "left" if index == 0 else "right"
        x = 1 if side == "left" else grid_width - 2
        max_y = grid_height - fighter_height
        y = max(playable_y_min, min(max_y, (grid_height - fighter_height) // 2))
        while y <= min(max_y, playable_y_max - fighter_height + 1):
            candidate = {
                "x": x,
                "y": y,
                "side": side,
                "alive": True,
                "hp": fighter_hp,
                "max_hp": fighter_hp,
                "move_direction": "stop",
                "pending_shoot": False,
                "charging": False,
                "charge_ticks": 0,
                "cooldown_until_tick": 0,
                "color": FIGHTER_COLORS[index % len(FIGHTER_COLORS)],
                "stored_powerup": None,
                "activating_powerup": False,
                "powerup_activation_ticks": 0,
                "effects": {
                    "rapid_fire_until": 0,
                    "shield_until": 0,
                    "wide_shot_until": 0,
                    "ghost_until": 0,
                    "homing_until": 0,
                    "mirror_until": 0,
                    "overdrive_until": 0,
                },
            }
            if not self._fighter_overlaps_obstacle(candidate, fighter_height, obstacles):
                return candidate
            y += 1
        return {
            "x": x,
            "y": max(playable_y_min, min(max_y, (grid_height - fighter_height) // 2)),
            "side": side,
            "alive": True,
            "hp": fighter_hp,
            "max_hp": fighter_hp,
            "move_direction": "stop",
            "pending_shoot": False,
            "charging": False,
            "charge_ticks": 0,
            "cooldown_until_tick": 0,
            "color": FIGHTER_COLORS[index % len(FIGHTER_COLORS)],
            "stored_powerup": None,
            "activating_powerup": False,
            "powerup_activation_ticks": 0,
            "effects": {
                "rapid_fire_until": 0,
                "shield_until": 0,
                "wide_shot_until": 0,
                "ghost_until": 0,
                "homing_until": 0,
                "mirror_until": 0,
                "overdrive_until": 0,
            },
        }

    def _initial_round_scores(self, players: list[dict]) -> dict[str, int]:
        return {player["id"]: 0 for player in players}

    def create_initial_state(self, players: list[dict], settings: dict) -> dict:
        settings = self.validate_settings(settings)
        grid_width = settings["grid_width"]
        grid_height = settings["grid_height"]
        fighter_height = settings["fighter_height"]
        fighter_hp = settings["fighter_hp"]

        obstacle_count = settings["obstacle_count"] if settings["obstacles_enabled"] else 0
        obstacles = self._generate_obstacles(grid_width, grid_height, obstacle_count, fighter_height)

        playable_y_min = 0
        playable_y_max = grid_height - 1

        fighters: dict[str, dict] = {}
        for i, player in enumerate(players):
            fighters[player["id"]] = self._spawn_side(
                i,
                grid_width,
                grid_height,
                fighter_height,
                fighter_hp,
                obstacles,
                playable_y_min,
                playable_y_max,
            )

        countdown_sec = settings["countdown_sec"]
        countdown_ends_at = (
            datetime.now(timezone.utc) + timedelta(seconds=countdown_sec)
        ).isoformat()

        return {
            "phase": "countdown",
            "countdown_ends_at": countdown_ends_at,
            "tick": 0,
            "round": 1,
            "round_scores": self._initial_round_scores(players),
            "round_winner": None,
            "grid_width": grid_width,
            "grid_height": grid_height,
            "playable_y_min": playable_y_min,
            "playable_y_max": playable_y_max,
            "obstacles": obstacles,
            "fighters": fighters,
            "bullets": [],
            "powerup": None,
            "next_powerup_at_tick": self._schedule_next_powerup_spawn_tick(settings, 0),
            "next_bullet_id": 0,
            "players": players,
            "settings": settings,
            "winner": None,
            "win_reason": None,
            "last_action": None,
            "last_hit": None,
        }

    def apply_action(
        self, state: dict, action: dict, player: dict
    ) -> tuple[dict, list[dict]]:
        action_type = action.get("type")
        events: list[dict] = []

        if state["phase"] != "playing":
            return state, events

        player_id = player["id"]
        fighter = state["fighters"].get(player_id)
        if not fighter or not fighter.get("alive"):
            return state, events

        if action_type == "set_move":
            direction = action.get("direction")
            if direction not in MOVE_DIRECTIONS:
                return state, events
            fighter["move_direction"] = direction
            state["last_action"] = {
                "type": "set_move",
                "player_id": player_id,
                "direction": direction,
            }
            return state, events

        if action_type == "charge_start":
            if not state["settings"].get("charge_shot_enabled"):
                return state, events
            if state["tick"] < fighter.get("cooldown_until_tick", 0):
                return state, events
            fighter["charging"] = True
            fighter["charge_ticks"] = 0
            state["last_action"] = {"type": "charge_start", "player_id": player_id}
            return state, events

        if action_type == "powerup_hold_start":
            if not state["settings"].get("powerups_enabled"):
                return state, events
            if not fighter.get("stored_powerup"):
                return state, events
            fighter["activating_powerup"] = True
            fighter["powerup_activation_ticks"] = 0
            state["last_action"] = {"type": "powerup_hold_start", "player_id": player_id}
            return state, events

        if action_type == "powerup_hold_release":
            if not state["settings"].get("powerups_enabled"):
                return state, events
            if not fighter.get("stored_powerup"):
                return state, events
            was_activating = bool(fighter.get("activating_powerup"))
            fighter["activating_powerup"] = False
            server_ticks = int(fighter.get("powerup_activation_ticks", 0))
            client_ticks = action.get("powerup_activation_ticks")
            ticks = (
                self._clamp_client_progress(
                    server_ticks,
                    int(client_ticks) if client_ticks is not None else None,
                    POWERUP_ACTIVATION_TICKS + CLIENT_PROGRESS_LAG_TICKS,
                )
                if was_activating
                else 0
            )
            activated = was_activating and ticks >= POWERUP_ACTIVATION_TICKS
            if activated:
                self._activate_stored_powerup(state, fighter, player_id, events)
            fighter["powerup_activation_ticks"] = 0
            state["last_action"] = {
                "type": "powerup_hold_release",
                "player_id": player_id,
                "activated": activated,
                "powerup_activation_ticks": ticks,
            }
            return state, events

        if action_type == "release_charge":
            charge_max = int(state["settings"].get("charge_max_ticks", 15))
            if state["settings"].get("charge_shot_enabled"):
                server_ticks = int(fighter.get("charge_ticks", 0))
                client_ticks = action.get("charge_ticks")
                fighter["charge_ticks"] = self._clamp_client_progress(
                    server_ticks,
                    int(client_ticks) if client_ticks is not None else None,
                    charge_max,
                )
                fighter["charging"] = False
            else:
                fighter["charge_ticks"] = 0
                fighter["charging"] = False
            fighter["pending_shoot"] = True
            state["last_action"] = {
                "type": "release_charge",
                "player_id": player_id,
                "charge_ticks": fighter.get("charge_ticks", 0),
            }
            return state, events

        if action_type == "shoot":
            fighter["pending_shoot"] = True
            fighter["charge_ticks"] = 0
            fighter["charging"] = False
            state["last_action"] = {"type": "shoot", "player_id": player_id}
            return state, events

        return state, events

    def _player_by_id(self, state: dict, player_id: str) -> dict | None:
        return next((p for p in state["players"] if p["id"] == player_id), None)

    def _apply_ai_inputs(self, state: dict) -> None:
        reaction_interval = int(state["settings"].get("ai_reaction_interval_ticks", 2))
        rethink = reaction_interval <= 1 or state["tick"] % reaction_interval == 0

        for player in state["players"]:
            if not player.get("is_ai"):
                continue
            pid = player["id"]
            fighter = state["fighters"].get(pid)
            if not fighter or not fighter.get("alive"):
                continue
            if not rethink:
                continue
            move, shoot, charge_start, charge_release, charge_ticks, pu_start, pu_release = choose_ai_actions(
                state, pid, fighter
            )
            fighter["move_direction"] = move
            if pu_start:
                fighter["activating_powerup"] = True
                fighter["powerup_activation_ticks"] = 0
            elif pu_release:
                fighter["activating_powerup"] = False
                if fighter.get("powerup_activation_ticks", 0) >= POWERUP_ACTIVATION_TICKS:
                    self._activate_stored_powerup(state, fighter, pid, [])
                fighter["powerup_activation_ticks"] = 0
            elif charge_start:
                fighter["charging"] = True
                fighter["charge_ticks"] = 0
            elif charge_release:
                fighter["pending_shoot"] = True
                fighter["charge_ticks"] = charge_ticks
                fighter["charging"] = False
            elif shoot:
                fighter["pending_shoot"] = True
                fighter["charge_ticks"] = 0
                fighter["charging"] = False

    def _is_frozen(self, fighter: dict, tick: int) -> bool:
        return tick < fighter.get("effects", {}).get("freeze_until", 0)

    def _move_fighter(
        self,
        fighter: dict,
        grid_height: int,
        fighter_height: int,
        obstacles: list[dict],
        playable_y_min: int,
        playable_y_max: int,
        tick: int = 0,
    ) -> None:
        if self._is_frozen(fighter, tick):
            return
        direction = fighter.get("move_direction", "stop")
        max_y = grid_height - fighter_height
        min_y = max(0, playable_y_min)
        max_allowed = min(max_y, playable_y_max - fighter_height + 1)

        if direction == "up":
            new_y = max(min_y, fighter["y"] - 1)
        elif direction == "down":
            new_y = min(max_allowed, fighter["y"] + 1)
        else:
            return

        candidate = {**fighter, "y": new_y}
        if not self._fighter_overlaps_obstacle(candidate, fighter_height, obstacles):
            fighter["y"] = new_y

    def _shoot_row(self, fighter: dict, fighter_height: int) -> int:
        return fighter["y"] + fighter_height // 2

    def _bullet_rows(self, center_row: int, width: int, grid_height: int) -> list[int]:
        rows = []
        half = width // 2
        for offset in range(-half, half + 1):
            row = center_row + offset
            if 0 <= row < grid_height:
                rows.append(row)
        return rows or [max(0, min(grid_height - 1, center_row))]

    def _cooldown_ticks(self, state: dict, fighter: dict) -> int:
        settings = state["settings"]
        base = int(settings.get("shoot_cooldown_ticks", 10))
        tick = state["tick"]
        if tick < fighter.get("effects", {}).get("rapid_fire_until", 0):
            return max(4, base // 2)
        return base

    def _spawn_bullet(
        self,
        state: dict,
        fighter: dict,
        owner_id: str,
        row: int,
        damage: int,
        bounces: int,
        speed: int,
        homing: bool = False,
    ) -> None:
        side = fighter["side"]
        vx = speed if side == "left" else -speed
        spawn_x = fighter["x"] + vx
        if spawn_x < 0 or spawn_x >= state["grid_width"]:
            return

        bullet_id = state["next_bullet_id"]
        state["next_bullet_id"] = bullet_id + 1
        state["bullets"].append(
            {
                "id": bullet_id,
                "x": spawn_x,
                "y": row,
                "vx": vx,
                "vy": 0,
                "owner_id": owner_id,
                "damage": damage,
                "bounces_remaining": bounces,
                "homing": homing,
            }
        )

    def _living_bullets_for_player(self, state: dict, player_id: str) -> int:
        return sum(1 for bullet in state["bullets"] if bullet["owner_id"] == player_id)

    def _charge_damage_and_width(self, state: dict, charge_ticks: int) -> tuple[int, int]:
        if state["settings"].get("instant_kill"):
            return 99, 1
        if charge_ticks >= 11:
            return 2, 3
        if charge_ticks >= 6:
            return 2, 1
        return 1, 1

    def _try_shoot(self, state: dict, fighter: dict, owner_id: str) -> None:
        if not fighter.get("pending_shoot"):
            return
        tick = state["tick"]
        if tick < fighter.get("cooldown_until_tick", 0):
            fighter["pending_shoot"] = False
            return

        settings = state["settings"]
        max_bullets = int(settings.get("max_bullets_per_player", 12))
        if self._living_bullets_for_player(state, owner_id) >= max_bullets:
            fighter["pending_shoot"] = False
            return

        fighter["pending_shoot"] = False
        fighter_height = self._fighter_height(state)
        charge_ticks = int(fighter.get("charge_ticks", 0))
        damage, width = self._charge_damage_and_width(state, charge_ticks)
        speed = int(settings.get("bullet_speed", 1))
        bounces = int(settings.get("ricochet_bounces", 0))
        effects = fighter.get("effects", {})

        if tick < effects.get("wide_shot_until", 0):
            width = max(width, 3)

        if tick < effects.get("overdrive_until", 0):
            width = max(width, 3)

        center_row = self._shoot_row(fighter, fighter_height)
        rows = self._bullet_rows(center_row, width, state["grid_height"])
        shot_speed = speed * 3 if width >= 3 else speed
        homing = tick < effects.get("homing_until", 0)
        for row in rows:
            self._spawn_bullet(
                state, fighter, owner_id, row, damage, bounces, shot_speed, homing=homing
            )

        fighter["cooldown_until_tick"] = tick + self._cooldown_ticks(state, fighter)
        fighter["charge_ticks"] = 0
        fighter["charging"] = False

    def _bullet_hits_fighter_row(self, bullet: dict, fighter: dict, fighter_height: int) -> bool:
        if bullet["x"] != fighter["x"]:
            return False
        top = fighter["y"]
        return top <= bullet["y"] < top + fighter_height

    def _hit_damage(self, state: dict, bullet: dict, fighter: dict, fighter_height: int) -> tuple[int, bool]:
        settings = state["settings"]
        if settings.get("instant_kill"):
            return fighter.get("hp", 1), False
        center_row = fighter["y"] + fighter_height // 2
        crit = bullet["y"] == center_row
        damage = int(bullet.get("damage", 1))
        if crit:
            damage += 1
        return damage, crit

    def _apply_damage(
        self,
        state: dict,
        fighter: dict,
        owner_id: str,
        target_id: str,
        damage: int,
        crit: bool,
        events: list[dict],
    ) -> bool:
        tick = state["tick"]
        effects = fighter.get("effects", {})
        if tick < effects.get("shield_until", 0):
            events.append({"type": "shield_blocked", "player_id": target_id, "shooter_id": owner_id})
            state["last_hit"] = {"player_id": target_id, "damage": 0, "crit": False, "blocked": True}
            return False

        fighter["hp"] = max(0, fighter.get("hp", 1) - damage)
        state["last_hit"] = {"player_id": target_id, "damage": damage, "crit": crit, "blocked": False}
        events.append(
            {
                "type": "player_hit",
                "player_id": target_id,
                "shooter_id": owner_id,
                "damage": damage,
                "crit": crit,
                "hp_remaining": fighter["hp"],
            }
        )
        if fighter["hp"] <= 0:
            fighter["alive"] = False
            return True
        return False

    def _collect_powerup(self, state: dict, fighter: dict, owner_id: str, events: list[dict]) -> None:
        powerup = state.get("powerup")
        if not powerup:
            return
        if fighter.get("stored_powerup"):
            return
        ptype = powerup["type"]
        fighter["stored_powerup"] = ptype
        events.append({"type": "powerup_collected", "player_id": owner_id, "powerup_type": ptype})
        state["powerup"] = None
        state["next_powerup_at_tick"] = self._schedule_next_powerup_spawn_tick(state["settings"], state["tick"])

    def _schedule_next_powerup_spawn_tick(self, settings: dict, from_tick: int) -> int:
        base = int(settings.get("powerup_interval_ticks", 160))
        jitter = int(settings.get("powerup_spawn_jitter_ticks", 40))
        delay = base + random.randint(-jitter, jitter)
        return from_tick + max(40, delay)

    def _powerup_in_red_zone(self, y: int, state: dict) -> bool:
        y_min = state.get("playable_y_min", 0)
        y_max = state.get("playable_y_max", state["grid_height"] - 1)
        return y < y_min or y > y_max

    def _is_valid_powerup_cell(self, x: int, y: int, state: dict) -> bool:
        if self._powerup_in_red_zone(y, state):
            return False
        if self._cell_blocked(x, y, state.get("obstacles", [])):
            return False
        grid_width = state["grid_width"]
        if x <= 2 or x >= grid_width - 3:
            return False
        return True

    def _random_powerup_location(self, state: dict) -> dict | None:
        grid_width = state["grid_width"]
        y_min = state.get("playable_y_min", 0)
        y_max = state.get("playable_y_max", state["grid_height"] - 1)
        if y_max < y_min:
            return None

        lifetime = int(state["settings"].get("powerup_lifetime_ticks", 120))
        despawn_at = state["tick"] + lifetime

        for _ in range(60):
            x = random.randint(3, grid_width - 4)
            y = random.randint(y_min, y_max)
            if self._is_valid_powerup_cell(x, y, state):
                return {
                    "x": x,
                    "y": y,
                    "type": random.choice(POWERUP_TYPES),
                    "despawn_at_tick": despawn_at,
                }
        return None

    def _update_powerups(self, state: dict, events: list[dict]) -> None:
        settings = state["settings"]
        if not settings.get("powerups_enabled"):
            return

        tick = state["tick"]
        powerup = state.get("powerup")

        if powerup is not None:
            despawn_at = powerup.get("despawn_at_tick")
            if despawn_at is not None and tick >= int(despawn_at):
                state["powerup"] = None
                state["next_powerup_at_tick"] = self._schedule_next_powerup_spawn_tick(settings, tick)
                events.append({"type": "powerup_despawned"})
            return

        if tick < state.get("next_powerup_at_tick", 0):
            return

        location = self._random_powerup_location(state)
        if location:
            state["powerup"] = location
            events.append(
                {
                    "type": "powerup_spawned",
                    "powerup_type": location["type"],
                    "x": location["x"],
                    "y": location["y"],
                }
            )
        else:
            state["next_powerup_at_tick"] = tick + max(
                20, int(settings.get("powerup_interval_ticks", 160)) // 4
            )

    def _activate_stored_powerup(
        self, state: dict, fighter: dict, owner_id: str, events: list[dict]
    ) -> None:
        ptype = fighter.get("stored_powerup")
        if not ptype:
            return
        tick = state["tick"]
        duration = int(state["settings"].get("effect_duration_ticks", 80))
        effects = fighter.setdefault("effects", {})
        fighter["stored_powerup"] = None

        if ptype == "rapid_fire":
            effects["rapid_fire_until"] = tick + duration
        elif ptype == "shield":
            effects["shield_until"] = tick + duration
        elif ptype == "wide_shot":
            effects["wide_shot_until"] = tick + duration
        elif ptype == "ghost":
            effects["ghost_until"] = tick + duration
        elif ptype == "homing":
            effects["homing_until"] = tick + duration
        elif ptype == "mirror":
            effects["mirror_until"] = tick + duration
        elif ptype == "overdrive":
            effects["overdrive_until"] = tick + duration
        elif ptype == "heal":
            fighter["hp"] = min(fighter.get("max_hp", 3), fighter.get("hp", 1) + 1)
        elif ptype == "freeze":
            for pid, target in state["fighters"].items():
                if pid != owner_id and target.get("alive"):
                    target.setdefault("effects", {})["freeze_until"] = tick + duration
        elif ptype == "laser":
            self._fire_laser(state, fighter, owner_id, events)

        events.append({"type": "powerup_activated", "player_id": owner_id, "powerup_type": ptype})

    def _fire_laser(self, state: dict, fighter: dict, owner_id: str, events: list[dict]) -> None:
        fighter_height = self._fighter_height(state)
        center_row = self._shoot_row(fighter, fighter_height)
        grid_width = state["grid_width"]
        obstacles = state.get("obstacles", [])
        side = fighter["side"]
        x_start = fighter["x"] + (1 if side == "left" else -1)
        x_end = grid_width - 1 if side == "left" else 0
        step = 1 if side == "left" else -1

        for x in range(x_start, x_end + step, step):
            if self._cell_blocked(x, center_row, obstacles):
                break
            for pid, target in state["fighters"].items():
                if pid == owner_id or not target.get("alive"):
                    continue
                if target["x"] == x and target["y"] <= center_row < target["y"] + fighter_height:
                    damage, crit = self._hit_damage(
                        state,
                        {"y": center_row, "damage": 2},
                        target,
                        fighter_height,
                    )
                    self._apply_damage(state, target, owner_id, pid, damage, crit, events)
                    return

    def _maybe_spawn_powerup(self, state: dict, events: list[dict]) -> None:
        self._update_powerups(state, events)

    def _trace_bullet_path(self, bullet: dict) -> list[tuple[int, int]]:
        vx = bullet["vx"]
        vy = bullet.get("vy", 0)
        cells: list[tuple[int, int]] = []
        rem_x, rem_y = abs(vx), abs(vy)
        sx = 0 if vx == 0 else (1 if vx > 0 else -1)
        sy = 0 if vy == 0 else (1 if vy > 0 else -1)
        cx, cy = bullet["x"], bullet["y"]
        while rem_x > 0 or rem_y > 0:
            if rem_x > 0:
                cx += sx
                rem_x -= 1
            if rem_y > 0:
                cy += sy
                rem_y -= 1
            cells.append((cx, cy))
        return cells

    def _process_bullet(
        self,
        state: dict,
        bullet: dict,
        fighters: dict,
        fighter_height: int,
        obstacles: list[dict],
        events: list[dict],
    ) -> bool:
        """Advance bullet along its path, resolving collisions. Returns True to keep the bullet."""
        grid_width = state["grid_width"]
        grid_height = state["grid_height"]

        self._steer_homing_bullet(state, bullet)
        path = self._trace_bullet_path(bullet)
        if not path:
            return True

        for cx, cy in path:
            if cx < 0 or cx >= grid_width:
                return False

            if cy < 0 or cy >= grid_height:
                if bullet.get("bounces_remaining", 0) > 0 and bullet.get("vy", 0) == 0:
                    bullet["vy"] = -1 if cy < 0 else 1
                    bullet["bounces_remaining"] -= 1
                    bullet["x"] = cx
                    bullet["y"] = max(0, min(grid_height - 1, cy))
                    return True
                return False

            bullet["x"] = cx
            bullet["y"] = cy

            if self._bullet_hits_obstacle(bullet, obstacles):
                if bullet.get("bounces_remaining", 0) > 0:
                    bullet["vx"] *= -1
                    bullet["bounces_remaining"] -= 1
                    return True
                return False

            powerup = state.get("powerup")
            if powerup and cx == powerup["x"] and cy == powerup["y"]:
                owner = fighters.get(bullet["owner_id"])
                if owner:
                    self._collect_powerup(state, owner, bullet["owner_id"], events)

            for pid, fighter in fighters.items():
                if pid == bullet["owner_id"] or not fighter.get("alive"):
                    continue
                if cx != fighter["x"]:
                    continue
                top = fighter["y"]
                if not (top <= cy < top + fighter_height):
                    continue

                effects = fighter.get("effects", {})
                if state["tick"] < effects.get("mirror_until", 0):
                    shooter_id = bullet["owner_id"]
                    bullet["vx"] *= -1
                    bullet["owner_id"] = pid
                    events.append(
                        {
                            "type": "bullet_reflected",
                            "player_id": pid,
                            "shooter_id": shooter_id,
                        }
                    )
                    return True

                damage, crit = self._hit_damage(state, bullet, fighter, fighter_height)
                eliminated = self._apply_damage(
                    state, fighter, bullet["owner_id"], pid, damage, crit, events
                )
                if eliminated:
                    return False
                return False

        return True

    def _bullet_hits_obstacle(self, bullet: dict, obstacles: list[dict]) -> dict | None:
        for obstacle in obstacles:
            if self._cell_in_obstacle(bullet["x"], bullet["y"], obstacle):
                return obstacle
        return None

    def _advance_bullet(self, bullet: dict, grid_width: int, grid_height: int) -> bool:
        next_x = bullet["x"] + bullet["vx"]
        next_y = bullet["y"] + bullet.get("vy", 0)
        if next_y < 0 or next_y >= grid_height:
            if bullet.get("bounces_remaining", 0) > 0 and bullet.get("vy", 0) == 0:
                bullet["vy"] = -1 if next_y < 0 else 1
                bullet["bounces_remaining"] -= 1
                return True
            return False
        if next_x < 0 or next_x >= grid_width:
            return False
        bullet["x"] = next_x
        bullet["y"] = next_y
        return True

    def _maybe_shrink_arena(self, state: dict, events: list[dict]) -> None:
        settings = state["settings"]
        if not settings.get("shrinking_arena"):
            return
        start = int(settings.get("shrink_start_tick", 240))
        interval = int(settings.get("shrink_interval_ticks", 80))
        if state["tick"] < start:
            return
        if (state["tick"] - start) % interval != 0:
            return

        min_y = state.get("playable_y_min", 0)
        max_y = state.get("playable_y_max", state["grid_height"] - 1)
        if max_y - min_y <= state["settings"]["fighter_height"] + 2:
            return

        state["playable_y_min"] = min_y + 1
        state["playable_y_max"] = max_y - 1
        events.append(
            {
                "type": "arena_shrunk",
                "playable_y_min": state["playable_y_min"],
                "playable_y_max": state["playable_y_max"],
            }
        )

    def _clamp_fighters_to_playable(self, state: dict) -> None:
        fighter_height = self._fighter_height(state)
        min_y = state.get("playable_y_min", 0)
        max_y = state.get("playable_y_max", state["grid_height"] - 1)
        max_top = min(state["grid_height"] - fighter_height, max_y - fighter_height + 1)
        for fighter in state["fighters"].values():
            if not fighter.get("alive"):
                continue
            if fighter["y"] < min_y:
                fighter["y"] = min_y
            if fighter["y"] > max_top:
                fighter["y"] = max_top

    def _increment_powerup_activation(self, state: dict) -> None:
        for fighter in state["fighters"].values():
            if fighter.get("alive") and fighter.get("activating_powerup"):
                fighter["powerup_activation_ticks"] = fighter.get("powerup_activation_ticks", 0) + 1

    def _steer_homing_bullet(self, state: dict, bullet: dict) -> None:
        if not bullet.get("homing"):
            return
        owner = state["fighters"].get(bullet["owner_id"])
        if not owner:
            return
        for pid, fighter in state["fighters"].items():
            if pid == bullet["owner_id"] or not fighter.get("alive"):
                continue
            target_row = fighter["y"] + self._fighter_height(state) // 2
            if bullet["y"] < target_row:
                bullet["vy"] = 1
            elif bullet["y"] > target_row:
                bullet["vy"] = -1
            else:
                bullet["vy"] = 0
            return

    def _increment_charging(self, state: dict) -> None:
        max_charge = int(state["settings"].get("charge_max_ticks", 15))
        for fighter in state["fighters"].values():
            if fighter.get("alive") and fighter.get("charging"):
                fighter["charge_ticks"] = min(max_charge, fighter.get("charge_ticks", 0) + 1)

    def _start_round_countdown(self, state: dict) -> None:
        sec = int(state["settings"].get("round_countdown_sec", 3))
        state["countdown_ends_at"] = (
            datetime.now(timezone.utc) + timedelta(seconds=sec)
        ).isoformat()

    def _reset_round(self, state: dict) -> None:
        settings = state["settings"]
        grid_width = state["grid_width"]
        grid_height = state["grid_height"]
        fighter_height = self._fighter_height(state)
        fighter_hp = self._fighter_hp(state)

        obstacle_count = settings["obstacle_count"] if settings["obstacles_enabled"] else 0
        state["obstacles"] = self._generate_obstacles(grid_width, grid_height, obstacle_count, fighter_height)
        state["playable_y_min"] = 0
        state["playable_y_max"] = grid_height - 1
        state["bullets"] = []
        state["powerup"] = None
        state["next_powerup_at_tick"] = self._schedule_next_powerup_spawn_tick(settings, state["tick"])
        state["last_hit"] = None
        state["round_winner"] = None

        for i, player in enumerate(state["players"]):
            pid = player["id"]
            state["fighters"][pid] = self._spawn_side(
                i,
                grid_width,
                grid_height,
                fighter_height,
                fighter_hp,
                state["obstacles"],
                state["playable_y_min"],
                state["playable_y_max"],
            )

    def _end_round(self, state: dict, round_winner: str | None, events: list[dict]) -> None:
        state["round_winner"] = round_winner
        state["last_hit"] = None
        state["last_action"] = None
        scores = state.setdefault("round_scores", {})
        if round_winner:
            scores[round_winner] = scores.get(round_winner, 0) + 1
            events.append(
                {
                    "type": "round_over",
                    "winner": round_winner,
                    "round_scores": dict(scores),
                    "round": state.get("round", 1),
                }
            )

            if scores[round_winner] >= self._rounds_to_win(state):
                state["winner"] = round_winner
                state["win_reason"] = "match_won"
                state["phase"] = "finished"
                events.append({"type": "game_over", "winner": round_winner})
                return
        else:
            events.append(
                {
                    "type": "round_over",
                    "winner": None,
                    "round_scores": dict(scores),
                    "round": state.get("round", 1),
                }
            )

        state["phase"] = "round_over"
        state["round"] = int(state.get("round", 1)) + 1
        self._start_round_countdown(state)

    def tick(self, state: dict) -> tuple[dict, list[dict]]:
        events: list[dict] = []

        if state["phase"] == "finished":
            return state, events

        if state["phase"] == "countdown":
            ends_at = state.get("countdown_ends_at")
            if ends_at:
                end = datetime.fromisoformat(ends_at)
                if datetime.now(timezone.utc) >= end:
                    state["phase"] = "playing"
                    events.append({"type": "game_started"})
            state["tick"] += 1
            return state, events

        if state["phase"] == "round_over":
            ends_at = state.get("countdown_ends_at")
            if ends_at:
                end = datetime.fromisoformat(ends_at)
                if datetime.now(timezone.utc) >= end:
                    self._reset_round(state)
                    state["phase"] = "playing"
                    events.append({"type": "round_started", "round": state["round"]})
            state["tick"] += 1
            return state, events

        self._apply_ai_inputs(state)
        self._increment_charging(state)
        self._increment_powerup_activation(state)
        self._maybe_shrink_arena(state, events)
        self._maybe_spawn_powerup(state, events)

        grid_width = state["grid_width"]
        grid_height = state["grid_height"]
        fighters = state["fighters"]
        fighter_height = self._fighter_height(state)
        obstacles = state.get("obstacles", [])
        move_interval = int(state["settings"].get("ai_move_interval_ticks", 2))

        for pid, fighter in fighters.items():
            if not fighter.get("alive"):
                continue
            player = self._player_by_id(state, pid)
            is_ai = player.get("is_ai") if player else False
            can_move = (
                not is_ai
                or move_interval <= 1
                or state["tick"] % move_interval == 0
            )
            if can_move:
                self._move_fighter(
                    fighter,
                    grid_height,
                    fighter_height,
                    obstacles,
                    state.get("playable_y_min", 0),
                    state.get("playable_y_max", grid_height - 1),
                    state["tick"],
                )
            self._try_shoot(state, fighter, pid)

        self._clamp_fighters_to_playable(state)

        remaining_bullets: list[dict] = []
        for bullet in state["bullets"]:
            if self._process_bullet(state, bullet, fighters, fighter_height, obstacles, events):
                remaining_bullets.append(bullet)

        state["bullets"] = remaining_bullets

        alive = [pid for pid, f in fighters.items() if f.get("alive")]
        if len(alive) == 1:
            self._end_round(state, alive[0], events)
        elif len(alive) == 0:
            self._end_round(state, None, events)

        state["tick"] += 1
        return state, events

    def _fog_offset(self, viewer_id: str | None, fighter_id: str, tick: int) -> int:
        if not viewer_id or viewer_id == fighter_id:
            return 0
        seed = hash((fighter_id, tick // 4)) % 3
        return seed - 1

    def get_public_state(self, state: dict, viewer_player: dict | None) -> dict:
        viewer_id = viewer_player["id"] if viewer_player else None
        fog = bool(state["settings"].get("fog"))
        tick = state.get("tick", 0)

        fighters: dict[str, dict] = {}
        for pid, fighter in state["fighters"].items():
            public = dict(fighter)
            effects = dict(public.get("effects", {}))
            if tick >= effects.get("ghost_until", 0):
                effects["ghost_active"] = False
            else:
                effects["ghost_active"] = pid != viewer_id
            effects["freeze_active"] = tick < effects.get("freeze_until", 0)
            effects["mirror_active"] = tick < effects.get("mirror_until", 0)
            effects["homing_active"] = tick < effects.get("homing_until", 0)
            effects["rapid_fire_active"] = tick < effects.get("rapid_fire_until", 0)
            effects["shield_active"] = tick < effects.get("shield_until", 0)
            effects["wide_shot_active"] = tick < effects.get("wide_shot_until", 0)
            effects["overdrive_active"] = tick < effects.get("overdrive_until", 0)
            public["effects"] = effects
            public["stored_powerup"] = fighter.get("stored_powerup")
            public["activating_powerup"] = fighter.get("activating_powerup", False)
            public["powerup_activation_ticks"] = fighter.get("powerup_activation_ticks", 0)

            if fog and viewer_id and pid != viewer_id and not effects.get("ghost_active"):
                offset = self._fog_offset(viewer_id, pid, tick)
                public["display_y"] = max(0, fighter["y"] + offset)
            else:
                public["display_y"] = fighter["y"]
            fighters[pid] = public

        return {
            "phase": state["phase"],
            "countdown_ends_at": state.get("countdown_ends_at"),
            "tick": state["tick"],
            "round": state.get("round", 1),
            "round_scores": state.get("round_scores", {}),
            "round_winner": state.get("round_winner"),
            "best_of": state["settings"].get("best_of", 5),
            "match_format": state["settings"].get("match_format", "best_of_5"),
            "mutator": state["settings"].get("mutator", "classic"),
            "bullet_speed": int(state["settings"].get("bullet_speed", 2)),
            "tick_ms": int(state["settings"].get("tick_ms", 75)),
            "charge_max_ticks": int(state["settings"].get("charge_max_ticks", 15)),
            "grid_width": state["grid_width"],
            "grid_height": state["grid_height"],
            "playable_y_min": state.get("playable_y_min", 0),
            "playable_y_max": state.get("playable_y_max", state["grid_height"] - 1),
            "fighter_height": self._fighter_height(state),
            "obstacles": state.get("obstacles", []),
            "fighters": fighters,
            "bullets": state["bullets"],
            "powerup": state.get("powerup"),
            "players": state["players"],
            "winner": state.get("winner"),
            "win_reason": state.get("win_reason"),
            "last_action": state.get("last_action"),
            "last_hit": state.get("last_hit"),
            "viewer_id": viewer_id,
        }

    def check_winner(self, state: dict) -> str | None:
        if state.get("phase") == "finished":
            return state.get("winner")
        return None
