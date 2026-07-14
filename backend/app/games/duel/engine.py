import random
from datetime import datetime, timedelta, timezone
from typing import Any

from app.games.base import GamePlugin
from app.games.duel.ai import choose_ai_actions, get_ai_config, normalize_ai_difficulty

FIGHTER_COLORS = ["#3b82f6", "#ef4444"]

FIGHTER_HEIGHT = 3

BOMB_BLAST_RADIUS = 1
BOMB_WALL_INWARD_RADIUS = 5
BOMB_WALL_VERTICAL_RADIUS = 4

MOVE_DIRECTIONS = {"up", "down", "stop"}

POWERUP_TYPES = (
    "rapid_fire",
    "machine_gun",
    "shield",
    "wide_shot",
    "pierce",
    "ghost",
    "freeze",
    "laser",
    "railgun",
    "homing",
    "heal",
    "mirror",
    "overdrive",
    "bomb",
    "cluster",
    "burst",
    "phase_shift",
    "decoy",
)

POWERUP_ACTIVATION_TICKS = 8

# Per-power-up effect length (ticks) and channel time before release (ticks).
POWERUP_EFFECT_DURATIONS: dict[str, int] = {
    "rapid_fire": 70,
    "machine_gun": 90,
    "shield": 100,
    "wide_shot": 75,
    "pierce": 70,
    "ghost": 85,
    "freeze": 55,
    "homing": 80,
    "mirror": 75,
    "overdrive": 65,
    "phase_shift": 60,
    "decoy": 70,
}

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

INSTANT_POWERUP_TYPES = frozenset(
    {
        "heal",
        "laser",
        "railgun",
        "bomb",
        "cluster",
        "burst",
        "decoy",
    }
)

# Weighted spawn — rarer power-ups appear less often
POWERUP_SPAWN_WEIGHTS: dict[str, int] = {
    "rapid_fire": 12,
    "machine_gun": 10,
    "shield": 11,
    "wide_shot": 10,
    "homing": 10,
    "heal": 9,
    "pierce": 7,
    "ghost": 7,
    "freeze": 7,
    "mirror": 6,
    "overdrive": 6,
    "bomb": 7,
    "burst": 6,
    "laser": 4,
    "railgun": 3,
    "cluster": 4,
    "phase_shift": 4,
    "decoy": 5,
}

STACKABLE_SECONDARY_MUTATORS = frozenset({"fog", "chaos"})
QUICK_DUEL_LOADOUTS = frozenset(POWERUP_TYPES)
TRAINING_DRILLS = frozenset({"none", "dodge_only", "aim_trainer", "powerup_sandbox"})
AI_PERSONALITIES = frozenset({"balanced", "aggressive", "turtle", "trickster"})
ARENA_THEMES = frozenset({"classic", "neon", "asteroid", "crt"})

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
    "best_of_7": {
        "best_of": 7,
        "fighter_hp": 3,
        "powerups_enabled": True,
        "shrinking_arena": True,
        "obstacles_enabled": True,
        "charge_shot_enabled": True,
        "round_countdown_sec": 3,
        "side_swap_every_n_rounds": 2,
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
            "powerup_interval_ticks": 50,
            "powerup_lifetime_ticks": 120,
            "powerup_spawn_jitter_ticks": 15,
            "shrink_start_tick": 240,
            "shrink_interval_ticks": 80,
            "hazard_damage": 1,
            "hazard_damage_interval_ticks": 20,
            "charge_max_ticks": 15,
            "effect_duration_ticks": 80,
            "ai_difficulty": "medium",
            "ai_personality": "balanced",
            "mutator_secondary": "none",
            "quick_duel_loadout": "none",
            "obstacle_rotation": False,
            "bounce_self_damage": False,
            "layout_seed": None,
            "training_drill": "none",
            "tutorial_mode": False,
            "arena_theme": "classic",
            "powerup_draft_enabled": True,
            "sudden_death_after_round": 3,
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
        merged["powerup_interval_ticks"] = max(28, min(400, int(merged.get("powerup_interval_ticks", 50))))
        merged["powerup_lifetime_ticks"] = max(40, min(300, int(merged.get("powerup_lifetime_ticks", 120))))
        merged["powerup_spawn_jitter_ticks"] = max(
            0, min(120, int(merged.get("powerup_spawn_jitter_ticks", 20)))
        )
        merged["shrink_start_tick"] = max(120, min(600, int(merged.get("shrink_start_tick", 240))))
        merged["shrink_interval_ticks"] = max(40, min(200, int(merged.get("shrink_interval_ticks", 80))))
        merged["hazard_damage"] = max(0, min(3, int(merged.get("hazard_damage", 1))))
        merged["hazard_damage_interval_ticks"] = max(
            8, min(80, int(merged.get("hazard_damage_interval_ticks", 20)))
        )
        merged["charge_max_ticks"] = max(8, min(30, int(merged.get("charge_max_ticks", 15))))
        merged["effect_duration_ticks"] = max(40, min(200, int(merged.get("effect_duration_ticks", 80))))
        difficulty = str(merged.get("ai_difficulty", "medium")).lower()
        if difficulty == "normal":
            difficulty = "medium"
        if difficulty not in ("easy", "medium", "hard", "pro"):
            difficulty = "medium"
        merged["ai_difficulty"] = difficulty

        personality = str(merged.get("ai_personality", "balanced")).lower()
        if personality not in AI_PERSONALITIES:
            personality = "balanced"
        merged["ai_personality"] = personality

        secondary = str(merged.get("mutator_secondary", "none")).lower()
        if secondary == "none" or secondary not in STACKABLE_SECONDARY_MUTATORS:
            secondary = "none"
        merged["mutator_secondary"] = secondary

        loadout = str(merged.get("quick_duel_loadout", "none")).lower()
        if loadout == "none" or loadout not in QUICK_DUEL_LOADOUTS:
            loadout = "none"
        merged["quick_duel_loadout"] = loadout

        merged["obstacle_rotation"] = bool(merged.get("obstacle_rotation", False))
        merged["bounce_self_damage"] = bool(merged.get("bounce_self_damage", False))
        merged["tutorial_mode"] = bool(merged.get("tutorial_mode", False))

        theme = str(merged.get("arena_theme", "classic")).lower()
        if theme not in ARENA_THEMES:
            theme = "classic"
        merged["arena_theme"] = theme

        drill = str(merged.get("training_drill", "none")).lower()
        if drill not in TRAINING_DRILLS:
            drill = "none"
        merged["training_drill"] = drill

        seed = merged.get("layout_seed")
        if seed is not None and seed != "":
            try:
                merged["layout_seed"] = int(seed)
            except (TypeError, ValueError):
                merged["layout_seed"] = None
        else:
            merged["layout_seed"] = None

        merged["ai_move_interval_ticks"] = max(
            1, min(4, int(merged.get("ai_move_interval_ticks", 2)))
        )
        merged["ai_reaction_interval_ticks"] = max(
            1, min(4, int(merged.get("ai_reaction_interval_ticks", 2)))
        )

        merged["powerup_draft_enabled"] = bool(merged.get("powerup_draft_enabled", True))
        merged["sudden_death_after_round"] = max(
            2, min(6, int(merged.get("sudden_death_after_round", 3)))
        )

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
        merged["side_swap_every_n_rounds"] = int(
            format_preset.get("side_swap_every_n_rounds", 0)
        )
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
            merged["bounce_self_damage"] = merged.get("bounce_self_damage", True)

        if secondary == "fog":
            merged["fog"] = True
        elif secondary == "chaos":
            merged["bullet_speed"] = min(3, int(merged["bullet_speed"]) + 1)
            merged["shoot_cooldown_ticks"] = max(
                4, int(merged.get("shoot_cooldown_ticks", 10)) - 2
            )
            merged["max_bullets_per_player"] = min(
                8, int(merged["max_bullets_per_player"]) + 2
            )

        if loadout != "none" and match_format == "quick_duel":
            merged["powerups_enabled"] = True

        if drill == "powerup_sandbox":
            merged["powerups_enabled"] = True
            merged["powerup_interval_ticks"] = 28
            merged["shrinking_arena"] = False
        elif drill == "dodge_only":
            merged["powerups_enabled"] = False
            merged["charge_shot_enabled"] = False
        elif drill == "aim_trainer":
            merged["powerups_enabled"] = False
            merged["shrinking_arena"] = False

        return merged

    def tick_interval_ms(self) -> int:
        # Signals tick-based simulation; actual sleep uses settings.tick_ms in game_loop.
        return int(self.validate_settings({}).get("tick_ms", 75))

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

    def _powerup_channel_ticks(self, ptype: str) -> int:
        return POWERUP_CHANNEL_TICKS.get(ptype, POWERUP_ACTIVATION_TICKS)

    def _powerup_effect_duration(self, ptype: str, state: dict) -> int:
        return POWERUP_EFFECT_DURATIONS.get(
            ptype, int(state["settings"].get("effect_duration_ticks", 80))
        )

    def _extend_timed_effect(self, effects: dict, key: str, tick: int, duration: int) -> None:
        effects[key] = max(int(effects.get(key, 0)), tick + duration)

    def _powerup_activation_succeeds(
        self,
        was_activating: bool,
        server_ticks: int,
        client_ticks: int | None,
        required_ticks: int,
    ) -> bool:
        if not was_activating:
            return False
        if server_ticks >= required_ticks:
            return True
        if client_ticks is None:
            return False
        clamped = self._clamp_client_progress(server_ticks, client_ticks, required_ticks)
        return clamped >= required_ticks

    def _effective_shrink_interval(self, state: dict) -> int:
        settings = state["settings"]
        interval = int(settings.get("shrink_interval_ticks", 80))
        sudden_after = int(settings.get("sudden_death_after_round", 3))
        if int(state.get("round", 1)) >= sudden_after:
            interval = max(20, interval // 2)
        return interval

    def _should_enter_powerup_draft(self, settings: dict) -> bool:
        return (
            settings.get("powerup_draft_enabled")
            and settings.get("powerups_enabled")
            and int(settings.get("best_of", 1)) > 1
        )

    def _begin_powerup_draft(self, state: dict) -> None:
        state["powerup_bans"] = {}
        state["phase"] = "powerup_draft"
        state["countdown_ends_at"] = None

    def _rounds_to_win(self, state: dict) -> int:
        return (int(state["settings"].get("best_of", 5)) + 1) // 2

    def _layout_rng(self, settings: dict, salt: int = 0) -> random.Random:
        seed = settings.get("layout_seed")
        if seed is None:
            return random.Random()
        return random.Random(int(seed) + int(salt))

    def _generate_obstacles(
        self,
        grid_width: int,
        grid_height: int,
        count: int,
        fighter_height: int,
        settings: dict | None = None,
        salt: int = 0,
    ) -> list[dict]:
        if count <= 0:
            return []
        rng = self._layout_rng(settings or {}, salt)
        obstacles: list[dict] = []
        center_x = grid_width // 2
        attempts = 0
        while len(obstacles) < count and attempts < 80:
            attempts += 1
            w = rng.choice([1, 2])
            h = rng.choice([1, 2])
            x = rng.randint(center_x - 4, center_x + 2)
            y = rng.randint(2, grid_height - h - 2)
            if x <= 3 or x >= grid_width - 5:
                continue
            candidate = {"x": x, "y": y, "w": w, "h": h, "vy": 0}
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
                    "machine_gun_until": 0,
                    "shield_until": 0,
                    "wide_shot_until": 0,
                    "pierce_until": 0,
                    "ghost_until": 0,
                    "homing_until": 0,
                    "mirror_until": 0,
                    "overdrive_until": 0,
                    "phase_shift_until": 0,
                },
                "burst_shots_remaining": 0,
                "burst_next_at_tick": 0,
            }
            if not self._fighter_overlaps_obstacle(candidate, fighter_height, obstacles):
                return candidate
            y += 1
        for fallback_y in range(playable_y_min, min(max_y, playable_y_max - fighter_height + 1) + 1):
            candidate = {
                "x": x,
                "y": fallback_y,
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
                    "machine_gun_until": 0,
                    "shield_until": 0,
                    "wide_shot_until": 0,
                    "pierce_until": 0,
                    "ghost_until": 0,
                    "homing_until": 0,
                    "mirror_until": 0,
                    "overdrive_until": 0,
                    "phase_shift_until": 0,
                },
                "burst_shots_remaining": 0,
                "burst_next_at_tick": 0,
            }
            if not self._fighter_overlaps_obstacle(candidate, fighter_height, obstacles):
                return candidate
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
                "machine_gun_until": 0,
                "shield_until": 0,
                "wide_shot_until": 0,
                "pierce_until": 0,
                "ghost_until": 0,
                "homing_until": 0,
                "mirror_until": 0,
                "overdrive_until": 0,
                "phase_shift_until": 0,
            },
            "burst_shots_remaining": 0,
            "burst_next_at_tick": 0,
        }

    def _initial_round_scores(self, players: list[dict]) -> dict[str, int]:
        return {player["id"]: 0 for player in players}

    def _empty_match_stats(self, players: list[dict]) -> dict[str, dict[str, int]]:
        template = {
            "damage_dealt": 0,
            "damage_taken": 0,
            "crits": 0,
            "powerups_used": 0,
            "hazard_ticks": 0,
            "perfect_rounds": 0,
            "clutch_heals": 0,
            "railgun_kills": 0,
        }
        return {player["id"]: dict(template) for player in players}

    def _empty_round_stats(self, players: list[dict]) -> dict[str, dict[str, int]]:
        template = {
            "damage_dealt": 0,
            "damage_taken": 0,
            "crits": 0,
            "powerups_used": 0,
            "hazard_ticks": 0,
        }
        return {player["id"]: dict(template) for player in players}

    def _append_event_log(self, state: dict, message: str, *, kind: str = "info") -> None:
        log = state.setdefault("event_log", [])
        log.append({"tick": state.get("tick", 0), "message": message, "kind": kind})
        if len(log) > 30:
            del log[:-30]

    def _banned_powerup_types(self, state: dict) -> set[str]:
        bans = state.get("powerup_bans", {})
        return {ptype for ptype in bans.values() if ptype}

    def _start_countdown(self, state: dict, seconds: int | None = None) -> None:
        sec = seconds if seconds is not None else int(state["settings"].get("countdown_sec", 3))
        state["countdown_ends_at"] = (
            datetime.now(timezone.utc) + timedelta(seconds=sec)
        ).isoformat()

    def _update_match_stats(
        self,
        state: dict,
        actor_id: str,
        target_id: str,
        *,
        damage: int = 0,
        crit: bool = False,
        kind: str = "hit",
    ) -> None:
        round_stats = state.setdefault(
            "round_stats", self._empty_round_stats(state.get("players", []))
        )
        match_stats = state.setdefault(
            "match_stats", self._empty_match_stats(state.get("players", []))
        )
        for bucket in (round_stats, match_stats):
            if actor_id in bucket and kind == "hit" and damage > 0:
                bucket[actor_id]["damage_dealt"] += damage
            if target_id in bucket and kind == "hit" and damage > 0:
                bucket[target_id]["damage_taken"] += damage
            if actor_id in bucket and crit:
                bucket[actor_id]["crits"] += 1
            if actor_id in bucket and kind == "powerup":
                bucket[actor_id]["powerups_used"] += 1
            if target_id in bucket and kind == "hazard":
                bucket[target_id]["hazard_ticks"] += 1

    def create_initial_state(self, players: list[dict], settings: dict) -> dict:
        settings = self.validate_settings(settings)
        if settings.get("layout_seed") is None:
            settings["layout_seed"] = random.randint(1, 2_000_000_000)
        grid_width = settings["grid_width"]
        grid_height = settings["grid_height"]
        fighter_height = settings["fighter_height"]
        fighter_hp = settings["fighter_hp"]

        obstacle_count = settings["obstacle_count"] if settings["obstacles_enabled"] else 0
        obstacles = self._generate_obstacles(
            grid_width, grid_height, obstacle_count, fighter_height, settings, salt=1
        )

        playable_y_min = 0
        playable_y_max = grid_height - 1

        fighters: dict[str, dict] = {}
        normalized_players: list[dict] = []
        for i, player in enumerate(players):
            pdata = dict(player)
            if pdata.get("is_ai"):
                pdata["ai_difficulty"] = normalize_ai_difficulty(
                    pdata.get("ai_difficulty")
                    or (settings.get("ai_difficulties") or {}).get(pdata["id"])
                    or settings.get("ai_difficulty")
                )
            normalized_players.append(pdata)
            fighters[pdata["id"]] = self._spawn_side(
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
        use_draft = self._should_enter_powerup_draft(settings)
        initial_phase = "powerup_draft" if use_draft else "countdown"
        countdown_ends_at = None
        if not use_draft:
            countdown_ends_at = (
                datetime.now(timezone.utc) + timedelta(seconds=countdown_sec)
            ).isoformat()

        loadout = settings.get("quick_duel_loadout", "none")
        if loadout and loadout != "none":
            for fighter in fighters.values():
                fighter["stored_powerup"] = loadout

        drill = settings.get("training_drill", "none")
        if drill == "aim_trainer":
            for fighter in fighters.values():
                fighter["move_direction"] = "stop"

        return {
            "phase": initial_phase,
            "countdown_ends_at": countdown_ends_at,
            "tick": 0,
            "round": 1,
            "round_scores": self._initial_round_scores(normalized_players),
            "round_winner": None,
            "match_stats": self._empty_match_stats(normalized_players),
            "powerup_bans": {},
            "decoys": [],
            "event_log": [],
            "grid_width": grid_width,
            "grid_height": grid_height,
            "playable_y_min": playable_y_min,
            "playable_y_max": playable_y_max,
            "obstacles": obstacles,
            "fighters": fighters,
            "bullets": [],
            "powerup": None,
            "next_powerup_at_tick": self._schedule_next_powerup_spawn_tick(settings, 0, initial=True),
            "next_bullet_id": 0,
            "players": normalized_players,
            "settings": settings,
            "winner": None,
            "win_reason": None,
            "last_action": None,
            "last_hit": None,
            "round_stats": self._empty_round_stats(normalized_players),
        }

    def _reject_action(
        self, state: dict, player: dict, action: dict, reason: str
    ) -> tuple[dict, list[dict]]:
        state["last_action"] = {
            "type": "action_rejected",
            "player_id": player["id"],
            "reason": reason,
            "attempted": action.get("type"),
        }
        return state, []

    def _complete_powerup_draft(self, state: dict) -> None:
        state["phase"] = "countdown"
        self._start_countdown(state)

    def handle_disconnect_forfeit(
        self, state: dict, player_id: str, events: list[dict]
    ) -> bool:
        if state.get("phase") != "playing":
            return False
        fighter = state["fighters"].get(player_id)
        if not fighter or not fighter.get("alive"):
            return False
        for pid, opponent in state["fighters"].items():
            if pid != player_id and opponent.get("alive"):
                self._end_round(state, pid, events)
                if state.get("phase") == "finished":
                    state["win_reason"] = "opponent_disconnect"
                return True
        return False

    def apply_action(
        self, state: dict, action: dict, player: dict
    ) -> tuple[dict, list[dict]]:
        action_type = action.get("type")
        events: list[dict] = []

        if state["phase"] == "powerup_draft":
            if action_type == "ban_powerup":
                ptype = action.get("powerup_type")
                if ptype not in POWERUP_TYPES:
                    return self._reject_action(state, player, action, "invalid_powerup")
                player_id = player["id"]
                bans = state.setdefault("powerup_bans", {})
                if player_id in bans:
                    return self._reject_action(state, player, action, "already_banned")
                bans[player_id] = ptype
                state["last_action"] = {
                    "type": "powerup_banned",
                    "player_id": player_id,
                    "powerup_type": ptype,
                }
                nickname = player.get("nickname", "Player")
                self._append_event_log(state, f"{nickname} banned {ptype.replace('_', ' ')}")
                if len(bans) >= len(state["players"]):
                    self._complete_powerup_draft(state)
                return state, events
            return self._reject_action(state, player, action, "wrong_phase")

        if state["phase"] != "playing":
            return self._reject_action(state, player, action, "wrong_phase")

        player_id = player["id"]
        fighter = state["fighters"].get(player_id)
        if not fighter or not fighter.get("alive"):
            return self._reject_action(state, player, action, "not_alive")

        if action_type == "set_move":
            direction = action.get("direction")
            if direction not in MOVE_DIRECTIONS:
                return state, events
            drill = state["settings"].get("training_drill", "none")
            if drill == "aim_trainer" and not player.get("is_ai"):
                return state, events
            fighter["move_direction"] = direction
            state["last_action"] = {
                "type": "set_move",
                "player_id": player_id,
                "direction": direction,
            }
            return state, events

        if action_type == "charge_start":
            if state["settings"].get("training_drill") == "dodge_only":
                return state, events
            if not state["settings"].get("charge_shot_enabled"):
                return state, events
            if state["tick"] < fighter.get("cooldown_until_tick", 0):
                return state, events
            fighter["charging"] = True
            fighter["charge_ticks"] = 0
            state["last_action"] = {"type": "charge_start", "player_id": player_id}
            return state, events

        if action_type == "powerup_activate":
            if not state["settings"].get("powerups_enabled"):
                return state, events
            ptype = fighter.get("stored_powerup")
            if not ptype:
                return state, events
            if ptype == "heal" and fighter.get("hp", 1) >= fighter.get("max_hp", 3):
                state["last_action"] = {
                    "type": "powerup_blocked",
                    "player_id": player_id,
                    "powerup_type": ptype,
                    "reason": "max_hp",
                }
                return state, events
            self._activate_stored_powerup(state, fighter, player_id, events)
            state["last_action"] = {
                "type": "powerup_activated",
                "player_id": player_id,
                "powerup_type": ptype,
            }
            return state, events

        if action_type == "powerup_hold_start":
            if not state["settings"].get("powerups_enabled"):
                return state, events
            ptype = fighter.get("stored_powerup")
            if not ptype or ptype in INSTANT_POWERUP_TYPES:
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
            ptype = fighter.get("stored_powerup") or ""
            required_ticks = self._powerup_channel_ticks(ptype)
            server_ticks = int(fighter.get("powerup_activation_ticks", 0))
            client_ticks = action.get("powerup_activation_ticks")
            activated = self._powerup_activation_succeeds(
                was_activating,
                server_ticks,
                int(client_ticks) if client_ticks is not None else None,
                required_ticks,
            )
            ticks = max(
                server_ticks,
                int(client_ticks) if client_ticks is not None else 0,
            ) if was_activating else 0
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
            if state["settings"].get("training_drill") == "dodge_only":
                return state, events
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
            if state["settings"].get("training_drill") == "dodge_only":
                return state, events
            fighter["pending_shoot"] = True
            fighter["charge_ticks"] = 0
            fighter["charging"] = False
            state["last_action"] = {"type": "shoot", "player_id": player_id}
            return state, events

        return state, events

    def _player_by_id(self, state: dict, player_id: str) -> dict | None:
        return next((p for p in state["players"] if p["id"] == player_id), None)

    def _apply_ai_inputs(self, state: dict, events: list[dict] | None = None) -> None:
        ai_events = events if events is not None else []

        for player in state["players"]:
            if not player.get("is_ai"):
                continue
            pid = player["id"]
            fighter = state["fighters"].get(pid)
            if not fighter or not fighter.get("alive"):
                continue

            difficulty = normalize_ai_difficulty(
                player.get("ai_difficulty") or state["settings"].get("ai_difficulty")
            )
            cfg = get_ai_config(difficulty, state)
            reaction_interval = int(cfg["reaction_interval"])
            rethink = reaction_interval <= 1 or state["tick"] % reaction_interval == 0

            if not rethink:
                continue

            move, shoot, charge_start, charge_release, charge_ticks, pu_use = choose_ai_actions(
                state, pid, fighter, difficulty
            )
            fighter["move_direction"] = move
            if pu_use and fighter.get("stored_powerup"):
                self._activate_stored_powerup(state, fighter, pid, ai_events)
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

    def _is_phase_shifted(self, fighter: dict, tick: int) -> bool:
        return tick < fighter.get("effects", {}).get("phase_shift_until", 0)

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
        ignore_obstacles = self._is_phase_shifted(fighter, tick)
        if ignore_obstacles or not self._fighter_overlaps_obstacle(candidate, fighter_height, obstacles):
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
        effects = fighter.get("effects", {})
        if tick < effects.get("machine_gun_until", 0):
            return max(2, base // 4)
        if tick < effects.get("rapid_fire_until", 0):
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
        kind: str = "normal",
        pierce_obstacles: bool = False,
    ) -> None:
        side = fighter["side"]
        vx = speed if side == "left" else -speed
        spawn_x = fighter["x"] + (1 if side == "left" else -1)
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
                "kind": kind,
                "pierce_obstacles": pierce_obstacles,
            }
        )

    def _spawn_bomb(
        self, state: dict, fighter: dict, owner_id: str, row: int, speed: int = 1
    ) -> None:
        self._spawn_bullet(
            state, fighter, owner_id, row, damage=0, bounces=0, speed=speed, kind="bomb"
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
        if state["settings"].get("training_drill") == "dodge_only":
            fighter["pending_shoot"] = False
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

        overdrive = tick < effects.get("overdrive_until", 0)
        if overdrive:
            width = max(width, 3)
            damage = max(damage, 2)

        machine_gun = tick < effects.get("machine_gun_until", 0)
        if machine_gun:
            damage = 1
            width = 1

        center_row = self._shoot_row(fighter, fighter_height)
        if width >= fighter_height:
            rows = [fighter["y"] + i for i in range(fighter_height)]
        else:
            rows = self._bullet_rows(center_row, width, state["grid_height"])
        spread_shot = width >= 3
        shot_speed = speed * 3 if spread_shot else speed
        if machine_gun:
            shot_speed = max(shot_speed, speed * 2)
        homing = tick < effects.get("homing_until", 0)
        pierce_obstacles = spread_shot and not machine_gun
        for row in rows:
            self._spawn_bullet(
                state,
                fighter,
                owner_id,
                row,
                damage,
                bounces,
                shot_speed,
                homing=homing,
                pierce_obstacles=pierce_obstacles,
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

    def _record_hit(
        self,
        state: dict,
        player_id: str,
        damage: int,
        crit: bool,
        blocked: bool,
        hit_y: int | None = None,
    ) -> None:
        hit: dict[str, Any] = {
            "player_id": player_id,
            "damage": damage,
            "crit": crit,
            "blocked": blocked,
        }
        if hit_y is not None:
            hit["y"] = hit_y
        state["last_hit"] = hit
        state.setdefault("tick_hits", []).append(hit)

    def _apply_damage(
        self,
        state: dict,
        fighter: dict,
        owner_id: str,
        target_id: str,
        damage: int,
        crit: bool,
        events: list[dict],
        hit_y: int | None = None,
    ) -> bool:
        tick = state["tick"]
        effects = fighter.get("effects", {})
        if tick < effects.get("shield_until", 0):
            events.append({"type": "shield_blocked", "player_id": target_id, "shooter_id": owner_id})
            self._record_hit(state, target_id, 0, False, True, hit_y)
            return False

        fighter["hp"] = max(0, fighter.get("hp", 1) - damage)
        self._record_hit(state, target_id, damage, crit, False, hit_y)
        self._update_match_stats(
            state, owner_id, target_id, damage=damage, crit=crit, kind="hit"
        )
        shooter = next((p for p in state["players"] if p["id"] == owner_id), None)
        target = next((p for p in state["players"] if p["id"] == target_id), None)
        if damage > 0 and shooter and target:
            label = f"{crit and 'Crit! ' or ''}{damage} dmg"
            self._append_event_log(
                state,
                f"{shooter.get('nickname', 'Player')} → {target.get('nickname', 'Player')} ({label})",
                kind="warn" if crit else "info",
            )
        events.append(
            {
                "type": "player_hit",
                "player_id": target_id,
                "shooter_id": owner_id,
                "damage": damage,
                "crit": crit,
                "hp_remaining": fighter["hp"],
                "y": hit_y,
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
        state["last_action"] = {
            "type": "powerup_collected",
            "player_id": owner_id,
            "powerup_type": ptype,
        }
        state["powerup"] = None
        state["next_powerup_at_tick"] = self._schedule_next_powerup_spawn_tick(state["settings"], state["tick"])

    def _schedule_next_powerup_spawn_tick(
        self, settings: dict, from_tick: int, *, initial: bool = False
    ) -> int:
        base = int(settings.get("powerup_interval_ticks", 50))
        jitter = int(settings.get("powerup_spawn_jitter_ticks", 15))
        if initial:
            delay = max(15, base // 4 + random.randint(-jitter // 2, jitter // 2))
        else:
            delay = base + random.randint(-jitter, jitter)
        return from_tick + max(15, delay)

    def _try_fighter_pickup_powerups(self, state: dict, events: list[dict]) -> None:
        powerup = state.get("powerup")
        if not powerup:
            return
        px, py = powerup["x"], powerup["y"]
        fighter_height = self._fighter_height(state)
        for pid, fighter in state["fighters"].items():
            if not fighter.get("alive") or fighter.get("stored_powerup"):
                continue
            if fighter["x"] != px:
                continue
            top = fighter["y"]
            if top <= py < top + fighter_height:
                self._collect_powerup(state, fighter, pid, events)
                return

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

    def _random_powerup_type(self, state: dict) -> str:
        banned = self._banned_powerup_types(state)
        types = [t for t in POWERUP_TYPES if t not in banned]
        if not types:
            types = list(POWERUP_TYPES)
        weights = [POWERUP_SPAWN_WEIGHTS.get(t, 8) for t in types]
        settings = state.get("settings", {})
        if settings.get("layout_seed") is not None:
            rng = self._layout_rng(settings, salt=state.get("tick", 0) + len(types))
            return rng.choices(types, weights=weights, k=1)[0]
        return random.choices(types, weights=weights, k=1)[0]

    def _trailing_player_id(self, state: dict) -> str | None:
        fighters = state.get("fighters", {})
        scores = state.get("round_scores", {})
        if not fighters:
            return None
        ranked = []
        for pid, fighter in fighters.items():
            ranked.append((scores.get(pid, 0), fighter.get("hp", 0), pid))
        ranked.sort()
        return ranked[0][2] if ranked else None

    def _random_powerup_location(self, state: dict) -> dict | None:
        settings = state["settings"]
        grid_width = state["grid_width"]
        y_min = state.get("playable_y_min", 0)
        y_max = state.get("playable_y_max", state["grid_height"] - 1)
        if y_max < y_min:
            return None

        lifetime = int(settings.get("powerup_lifetime_ticks", 120))
        despawn_at = state["tick"] + lifetime
        trailing = self._trailing_player_id(state)
        trailing_fighter = state["fighters"].get(trailing) if trailing else None
        bias_x = trailing_fighter["x"] if trailing_fighter else grid_width // 2
        use_seed = settings.get("layout_seed") is not None
        rng = self._layout_rng(settings, salt=state["tick"]) if use_seed else None

        for attempt in range(60):
            if trailing_fighter and (rng.random() if rng else random.random()) < 0.55:
                spread = max(4, grid_width // 6)
                offset = rng.randint(-spread, spread) if rng else random.randint(-spread, spread)
                x = int(bias_x + offset)
                x = max(3, min(grid_width - 4, x))
            else:
                x = rng.randint(3, grid_width - 4) if rng else random.randint(3, grid_width - 4)
            y = rng.randint(y_min, y_max) if rng else random.randint(y_min, y_max)
            if self._is_valid_powerup_cell(x, y, state):
                return {
                    "x": x,
                    "y": y,
                    "type": self._random_powerup_type(state),
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
                self._append_event_log(state, "Power-up despawned", kind="warn")
            return

        sandbox = settings.get("training_drill") == "powerup_sandbox"
        if tick < state.get("next_powerup_at_tick", 0) and not sandbox:
            return

        location = self._random_powerup_location(state)
        if location:
            state["powerup"] = location
            state["last_action"] = {
                "type": "powerup_spawned",
                "powerup_type": location["type"],
                "x": location["x"],
                "y": location["y"],
            }
            if not sandbox:
                state["next_powerup_at_tick"] = self._schedule_next_powerup_spawn_tick(settings, tick)
            else:
                state["next_powerup_at_tick"] = tick + 30
            label = location["type"].replace("_", " ").title()
            self._append_event_log(state, f"{label} spawned", kind="info")
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
                15, int(settings.get("powerup_interval_ticks", 50)) // 5
            )

    def _activate_stored_powerup(
        self, state: dict, fighter: dict, owner_id: str, events: list[dict]
    ) -> None:
        ptype = fighter.get("stored_powerup")
        if not ptype:
            return
        tick = state["tick"]
        duration = self._powerup_effect_duration(ptype, state)
        effects = fighter.setdefault("effects", {})
        fighter["stored_powerup"] = None

        if ptype == "rapid_fire":
            self._extend_timed_effect(effects, "rapid_fire_until", tick, duration)
        elif ptype == "machine_gun":
            self._extend_timed_effect(effects, "machine_gun_until", tick, duration)
        elif ptype == "shield":
            self._extend_timed_effect(effects, "shield_until", tick, duration)
        elif ptype == "wide_shot":
            self._extend_timed_effect(effects, "wide_shot_until", tick, duration)
        elif ptype == "pierce":
            self._extend_timed_effect(effects, "pierce_until", tick, duration)
        elif ptype == "ghost":
            self._extend_timed_effect(effects, "ghost_until", tick, duration)
        elif ptype == "homing":
            self._extend_timed_effect(effects, "homing_until", tick, duration)
        elif ptype == "mirror":
            self._extend_timed_effect(effects, "mirror_until", tick, duration)
        elif ptype == "overdrive":
            self._extend_timed_effect(effects, "overdrive_until", tick, duration)
        elif ptype == "heal":
            hp_before = fighter.get("hp", 1)
            fighter["hp"] = min(fighter.get("max_hp", 3), hp_before + 1)
            if hp_before <= 1:
                match_stats = state.setdefault(
                    "match_stats", self._empty_match_stats(state.get("players", []))
                )
                if owner_id in match_stats:
                    match_stats[owner_id]["clutch_heals"] += 1
        elif ptype == "freeze":
            caster_effects = fighter.setdefault("effects", {})
            self._extend_timed_effect(caster_effects, "freeze_cast_until", tick, duration)
            for pid, target in state["fighters"].items():
                if pid != owner_id and target.get("alive"):
                    target_effects = target.setdefault("effects", {})
                    self._extend_timed_effect(target_effects, "freeze_until", tick, duration)
        elif ptype == "laser":
            self._fire_laser(state, fighter, owner_id, events)
        elif ptype == "railgun":
            self._fire_railgun(state, fighter, owner_id, events)
        elif ptype == "bomb":
            self._fire_bomb(state, fighter, owner_id)
        elif ptype == "cluster":
            self._fire_cluster_bombs(state, fighter, owner_id)
        elif ptype == "burst":
            fighter["burst_shots_remaining"] = 6
            fighter["burst_next_at_tick"] = tick
        elif ptype == "phase_shift":
            self._extend_timed_effect(effects, "phase_shift_until", tick, duration)
        elif ptype == "decoy":
            grid_height = state["grid_height"]
            fighter_height = self._fighter_height(state)
            settings = state["settings"]
            y_min = state.get("playable_y_min", 0)
            y_max = max(
                y_min,
                state.get("playable_y_max", grid_height - 1) - fighter_height,
            )
            if settings.get("layout_seed") is not None:
                rng = self._layout_rng(settings, salt=tick + len(state.get("decoys", [])))
                decoy_y = rng.randint(y_min, y_max)
            else:
                decoy_y = random.randint(y_min, y_max)
            decoy_duration = self._powerup_effect_duration("decoy", state)
            state.setdefault("decoys", []).append(
                {
                    "player_id": owner_id,
                    "y": decoy_y,
                    "until_tick": tick + decoy_duration,
                    "side": fighter.get("side"),
                }
            )

        self._update_match_stats(state, owner_id, owner_id, kind="powerup")
        nickname = next(
            (p.get("nickname", "Player") for p in state["players"] if p["id"] == owner_id),
            "Player",
        )
        self._append_event_log(
            state, f"{nickname} activated {ptype.replace('_', ' ')}", kind="success"
        )
        events.append({"type": "powerup_activated", "player_id": owner_id, "powerup_type": ptype})

    def _fire_bomb(self, state: dict, fighter: dict, owner_id: str) -> None:
        fighter_height = self._fighter_height(state)
        center_row = self._shoot_row(fighter, fighter_height)
        speed = max(2, int(state["settings"].get("bullet_speed", 2)))
        self._spawn_bomb(state, fighter, owner_id, center_row, speed=speed)

    def _fire_cluster_bombs(self, state: dict, fighter: dict, owner_id: str) -> None:
        fighter_height = self._fighter_height(state)
        center_row = self._shoot_row(fighter, fighter_height)
        grid_height = state["grid_height"]
        speed = max(2, int(state["settings"].get("bullet_speed", 2)))
        for offset in (-1, 0, 1):
            row = center_row + offset
            if 0 <= row < grid_height:
                self._spawn_bomb(state, fighter, owner_id, row, speed=speed)

    def _process_burst_shots(self, state: dict) -> None:
        tick = state["tick"]
        settings = state["settings"]
        base_speed = int(settings.get("bullet_speed", 2))
        for pid, fighter in state["fighters"].items():
            if not fighter.get("alive"):
                continue
            remaining = int(fighter.get("burst_shots_remaining", 0))
            if remaining <= 0:
                continue
            if tick < int(fighter.get("burst_next_at_tick", 0)):
                continue
            max_bullets = int(settings.get("max_bullets_per_player", 12))
            if self._living_bullets_for_player(state, pid) >= max_bullets:
                continue
            fighter["burst_shots_remaining"] = remaining - 1
            fighter["burst_next_at_tick"] = tick + 3
            fighter_height = self._fighter_height(state)
            center_row = self._shoot_row(fighter, fighter_height)
            self._spawn_bullet(
                state,
                fighter,
                pid,
                center_row,
                damage=1,
                bounces=0,
                speed=max(2, base_speed * 2),
            )

    def _owner_has_pierce(self, state: dict, bullet: dict) -> bool:
        owner = state["fighters"].get(bullet["owner_id"])
        if not owner:
            return False
        return state["tick"] < owner.get("effects", {}).get("pierce_until", 0)

    def _detonate_bomb(
        self,
        state: dict,
        cx: int,
        cy: int,
        owner_id: str,
        events: list[dict],
        *,
        wall_side: str | None = None,
    ) -> None:
        fighter_height = self._fighter_height(state)
        grid_width = state["grid_width"]
        grid_height = state["grid_height"]
        cy = max(0, min(grid_height - 1, cy))
        blast_cells: list[tuple[int, int, int]] = []

        if wall_side == "right":
            cx = grid_width - 1
            for dx in range(-BOMB_WALL_INWARD_RADIUS, 1):
                for dy in range(-BOMB_WALL_VERTICAL_RADIUS, BOMB_WALL_VERTICAL_RADIUS + 1):
                    ex, ey = cx + dx, cy + dy
                    if 0 <= ex < grid_width and 0 <= ey < grid_height:
                        splash = 2 if dx >= -1 and abs(dy) <= 1 else 1
                        blast_cells.append((ex, ey, splash))
        elif wall_side == "left":
            cx = 0
            for dx in range(0, BOMB_WALL_INWARD_RADIUS + 1):
                for dy in range(-BOMB_WALL_VERTICAL_RADIUS, BOMB_WALL_VERTICAL_RADIUS + 1):
                    ex, ey = cx + dx, cy + dy
                    if 0 <= ex < grid_width and 0 <= ey < grid_height:
                        splash = 2 if dx <= 1 and abs(dy) <= 1 else 1
                        blast_cells.append((ex, ey, splash))
        elif wall_side == "top":
            cy = 0
            for dy in range(0, BOMB_WALL_INWARD_RADIUS + 1):
                for dx in range(-BOMB_WALL_VERTICAL_RADIUS, BOMB_WALL_VERTICAL_RADIUS + 1):
                    ex, ey = cx + dx, cy + dy
                    if 0 <= ex < grid_width and 0 <= ey < grid_height:
                        splash = 2 if dy <= 1 and abs(dx) <= 1 else 1
                        blast_cells.append((ex, ey, splash))
        elif wall_side == "bottom":
            cy = grid_height - 1
            for dy in range(-BOMB_WALL_INWARD_RADIUS, 1):
                for dx in range(-BOMB_WALL_VERTICAL_RADIUS, BOMB_WALL_VERTICAL_RADIUS + 1):
                    ex, ey = cx + dx, cy + dy
                    if 0 <= ex < grid_width and 0 <= ey < grid_height:
                        splash = 2 if dy >= -1 and abs(dx) <= 1 else 1
                        blast_cells.append((ex, ey, splash))
        else:
            for dx in range(-BOMB_BLAST_RADIUS, BOMB_BLAST_RADIUS + 1):
                for dy in range(-BOMB_BLAST_RADIUS, BOMB_BLAST_RADIUS + 1):
                    ex, ey = cx + dx, cy + dy
                    if 0 <= ex < grid_width and 0 <= ey < grid_height:
                        splash = 2 if dx == 0 and dy == 0 else 1
                        blast_cells.append((ex, ey, splash))

        events.append(
            {
                "type": "bomb_detonated",
                "x": cx,
                "y": cy,
                "owner_id": owner_id,
                "wall_hit": wall_side is not None,
            }
        )
        state["last_action"] = {
            "type": "bomb_detonated",
            "player_id": owner_id,
            "x": cx,
            "y": cy,
            "wall_hit": wall_side is not None,
        }

        pending_hits: dict[str, tuple[int, int]] = {}

        for ex, ey, splash in blast_cells:
            for pid, target in state["fighters"].items():
                if pid == owner_id or not target.get("alive"):
                    continue
                if target["x"] != ex:
                    continue
                top = target["y"]
                if not (top <= ey < top + fighter_height):
                    continue
                pending = pending_hits.get(pid)
                if pending is None or splash > pending[0]:
                    pending_hits[pid] = (splash, ey)

        for pid, (splash, ey) in pending_hits.items():
            target = state["fighters"][pid]
            damage, crit = self._hit_damage(
                state,
                {"y": ey, "damage": splash},
                target,
                fighter_height,
            )
            self._apply_damage(state, target, owner_id, pid, damage, crit, events, hit_y=ey)

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
                    self._apply_damage(state, target, owner_id, pid, damage, crit, events, hit_y=center_row)
                    return

    def _fire_railgun(self, state: dict, fighter: dict, owner_id: str, events: list[dict]) -> None:
        """Piercing beam that cuts through cover for heavy damage."""
        fighter_height = self._fighter_height(state)
        center_row = self._shoot_row(fighter, fighter_height)
        grid_width = state["grid_width"]
        side = fighter["side"]
        x_start = fighter["x"] + (1 if side == "left" else -1)
        x_end = grid_width - 1 if side == "left" else 0
        step = 1 if side == "left" else -1

        for x in range(x_start, x_end + step, step):
            for pid, target in state["fighters"].items():
                if pid == owner_id or not target.get("alive"):
                    continue
                if target["x"] == x and target["y"] <= center_row < target["y"] + fighter_height:
                    damage, crit = self._hit_damage(
                        state,
                        {"y": center_row, "damage": 3},
                        target,
                        fighter_height,
                    )
                    eliminated = self._apply_damage(
                        state, target, owner_id, pid, damage, crit, events, hit_y=center_row
                    )
                    if eliminated:
                        match_stats = state.setdefault(
                            "match_stats", self._empty_match_stats(state.get("players", []))
                        )
                        if owner_id in match_stats:
                            match_stats[owner_id]["railgun_kills"] += 1
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
                if bullet.get("kind") == "bomb":
                    wall_side = "left" if cx < 0 else "right"
                    self._detonate_bomb(
                        state,
                        cx,
                        cy,
                        bullet["owner_id"],
                        events,
                        wall_side=wall_side,
                    )
                return False

            if cy < 0 or cy >= grid_height:
                if bullet.get("kind") == "bomb":
                    wall_side = "top" if cy < 0 else "bottom"
                    self._detonate_bomb(
                        state,
                        cx,
                        cy,
                        bullet["owner_id"],
                        events,
                        wall_side=wall_side,
                    )
                    return False
                if bullet.get("bounces_remaining", 0) > 0 and bullet.get("vy", 0) == 0:
                    bullet["vy"] = -1 if cy < 0 else 1
                    bullet["bounces_remaining"] -= 1
                    if state["settings"].get("bounce_self_damage"):
                        bullet["can_hit_owner"] = True
                    bullet["x"] = cx
                    bullet["y"] = max(0, min(grid_height - 1, cy))
                    return True
                return False

            bullet["x"] = cx
            bullet["y"] = cy

            if bullet.get("kind") == "bomb":
                if self._bullet_hits_obstacle(bullet, obstacles):
                    self._detonate_bomb(state, cx, cy, bullet["owner_id"], events)
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
                    self._detonate_bomb(state, cx, cy, bullet["owner_id"], events)
                    return False
                continue

            pierce = self._owner_has_pierce(state, bullet)
            if (
                not pierce
                and not bullet.get("pierce_obstacles")
                and self._bullet_hits_obstacle(bullet, obstacles)
            ):
                if bullet.get("bounces_remaining", 0) > 0:
                    bullet["vx"] *= -1
                    bullet["bounces_remaining"] -= 1
                    if state["settings"].get("bounce_self_damage"):
                        bullet["can_hit_owner"] = True
                    return True
                return False

            powerup = state.get("powerup")
            if powerup and cx == powerup["x"] and cy == powerup["y"]:
                owner = fighters.get(bullet["owner_id"])
                if owner:
                    self._collect_powerup(state, owner, bullet["owner_id"], events)

            can_hit_owner = bullet.get("can_hit_owner", False)
            for pid, fighter in fighters.items():
                if pid == bullet["owner_id"] and not can_hit_owner:
                    continue
                if not fighter.get("alive"):
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
                    state, fighter, bullet["owner_id"], pid, damage, crit, events, hit_y=cy
                )
                if eliminated or not pierce:
                    return False
                continue

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
        interval = self._effective_shrink_interval(state)
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

    def _fighter_in_hazard(self, fighter: dict, state: dict) -> bool:
        if not state["settings"].get("shrinking_arena"):
            return False
        min_y = state.get("playable_y_min", 0)
        max_y = state.get("playable_y_max", state["grid_height"] - 1)
        height = self._fighter_height(state)
        top = fighter["y"]
        bottom = top + height - 1
        return top < min_y or bottom > max_y

    def _apply_hazard_damage(self, state: dict, events: list[dict]) -> None:
        settings = state["settings"]
        if not settings.get("shrinking_arena"):
            return
        damage = int(settings.get("hazard_damage", 1))
        if damage <= 0:
            return
        interval = max(1, int(settings.get("hazard_damage_interval_ticks", 20)))
        if state["tick"] % interval != 0:
            return

        for pid, fighter in state["fighters"].items():
            if not fighter.get("alive") or not self._fighter_in_hazard(fighter, state):
                continue
            tick = state["tick"]
            effects = fighter.get("effects", {})
            if tick < effects.get("shield_until", 0):
                continue
            hp_before = fighter.get("hp", 1)
            eliminated = self._apply_damage(
                state,
                fighter,
                pid,
                pid,
                damage,
                False,
                events,
                hit_y=fighter["y"],
            )
            if fighter.get("hp", 0) >= hp_before:
                continue
            events.append(
                {
                    "type": "hazard_damage",
                    "player_id": pid,
                    "damage": damage,
                    "hp_remaining": fighter.get("hp", 0),
                }
            )
            if eliminated:
                events.append({"type": "player_eliminated", "player_id": pid, "reason": "hazard"})
            self._update_match_stats(state, pid, pid, kind="hazard")

    def _rotate_obstacles(self, state: dict) -> None:
        settings = state["settings"]
        if not settings.get("obstacle_rotation"):
            return
        if state["tick"] % 120 != 0:
            return
        grid_height = state["grid_height"]
        min_y = state.get("playable_y_min", 0)
        max_y = state.get("playable_y_max", grid_height - 1)
        fighter_height = self._fighter_height(state)
        obstacles = state.get("obstacles", [])
        for obstacle in obstacles:
            vy = int(obstacle.get("vy", 0))
            if vy == 0:
                settings = state["settings"]
                if settings.get("layout_seed") is not None:
                    rng = self._layout_rng(
                        settings,
                        salt=state["tick"] // 120 + int(obstacle.get("x", 0)),
                    )
                    vy = rng.choice([-1, 1])
                else:
                    vy = random.choice([-1, 1])
            next_y = obstacle["y"] + vy
            if next_y < min_y or next_y + obstacle["h"] - 1 > max_y:
                vy *= -1
                next_y = obstacle["y"] + vy
            candidate = {**obstacle, "y": max(min_y, min(max_y - obstacle["h"] + 1, next_y))}
            blocked = False
            for fighter in state["fighters"].values():
                if fighter.get("alive") and self._fighter_overlaps_obstacle(
                    {**fighter, "y": fighter["y"]}, fighter_height, [candidate]
                ):
                    blocked = True
                    break
            if blocked:
                continue
            obstacle["y"] = candidate["y"]
            obstacle["vy"] = vy

    def _cleanup_decoys(self, state: dict) -> None:
        tick = state["tick"]
        state["decoys"] = [
            decoy for decoy in state.get("decoys", []) if int(decoy.get("until_tick", 0)) > tick
        ]

    def _steer_homing_bullet(self, state: dict, bullet: dict) -> None:
        if not bullet.get("homing"):
            return
        owner = state["fighters"].get(bullet["owner_id"])
        if not owner:
            return
        tick = state["tick"]
        target_center: int | None = None
        for pid, fighter in state["fighters"].items():
            if pid == bullet["owner_id"] or not fighter.get("alive"):
                continue
            target_center = fighter["y"] + self._fighter_height(state) // 2
            effects = fighter.get("effects", {})
            if tick < effects.get("ghost_until", 0):
                offset = (hash((pid, tick // 3)) % 5) - 2
                target_center += offset
            break
        if target_center is None:
            for decoy in state.get("decoys", []):
                if decoy.get("player_id") == bullet["owner_id"]:
                    continue
                if decoy.get("side") == owner.get("side"):
                    continue
                target_center = int(decoy["y"]) + 1
                break
        if target_center is None:
            return
        if bullet["y"] < target_center:
            bullet["vy"] = 1
        elif bullet["y"] > target_center:
            bullet["vy"] = -1
        else:
            bullet["vy"] = 0

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
        round_num = int(state.get("round", 1))

        obstacle_count = settings["obstacle_count"] if settings["obstacles_enabled"] else 0
        state["obstacles"] = self._generate_obstacles(
            grid_width,
            grid_height,
            obstacle_count,
            fighter_height,
            settings,
            salt=round_num,
        )
        state["playable_y_min"] = 0
        state["playable_y_max"] = grid_height - 1
        state["bullets"] = []
        state["powerup"] = None
        state["decoys"] = []
        state["next_powerup_at_tick"] = self._schedule_next_powerup_spawn_tick(settings, state["tick"])
        state["last_hit"] = None
        state["round_winner"] = None
        state["round_stats"] = self._empty_round_stats(state.get("players", []))

        players = list(state["players"])
        swap_every = int(settings.get("side_swap_every_n_rounds", 0))
        if swap_every > 0 and round_num > 1 and round_num % swap_every == 0:
            players.reverse()

        for i, player in enumerate(players):
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

        loadout = settings.get("quick_duel_loadout", "none")
        if loadout and loadout != "none":
            for fighter in state["fighters"].values():
                fighter["stored_powerup"] = loadout

        if settings.get("training_drill") == "aim_trainer":
            for fighter in state["fighters"].values():
                fighter["move_direction"] = "stop"

    def _end_round(self, state: dict, round_winner: str | None, events: list[dict]) -> None:
        state["round_winner"] = round_winner
        state["last_hit"] = None
        state["last_action"] = None
        scores = state.setdefault("round_scores", {})
        round_stats = dict(state.get("round_stats", {}))
        if round_winner:
            winner_stats = round_stats.get(round_winner, {})
            if winner_stats.get("damage_taken", 0) == 0:
                match_stats = state.setdefault(
                    "match_stats", self._empty_match_stats(state.get("players", []))
                )
                if round_winner in match_stats:
                    match_stats[round_winner]["perfect_rounds"] += 1
            scores[round_winner] = scores.get(round_winner, 0) + 1
            events.append(
                {
                    "type": "round_over",
                    "winner": round_winner,
                    "round_scores": dict(scores),
                    "round": state.get("round", 1),
                    "round_stats": round_stats,
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
                    "round_stats": round_stats,
                }
            )

        state["round"] = int(state.get("round", 1)) + 1

        if self._should_enter_powerup_draft(state["settings"]):
            self._reset_round(state)
            self._begin_powerup_draft(state)
            return

        state["phase"] = "round_over"
        self._start_round_countdown(state)

    def tick(self, state: dict) -> tuple[dict, list[dict]]:
        events: list[dict] = []

        if state["phase"] == "finished":
            return state, events

        if state["phase"] == "powerup_draft":
            bans = state.setdefault("powerup_bans", {})
            for player in state["players"]:
                pid = player["id"]
                if pid in bans:
                    continue
                if player.get("is_ai"):
                    banned = set(bans.values())
                    available = [ptype for ptype in POWERUP_TYPES if ptype not in banned]
                    choice = random.choice(available or list(POWERUP_TYPES))
                    bans[pid] = choice
                    self._append_event_log(
                        state,
                        f"{player.get('nickname', 'AI')} banned {choice.replace('_', ' ')}",
                    )
            if len(bans) >= len(state["players"]):
                self._complete_powerup_draft(state)
            state["tick"] += 1
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

        state["tick_hits"] = []
        state["last_hit"] = None

        self._apply_ai_inputs(state, events)
        self._increment_charging(state)
        self._increment_powerup_activation(state)
        self._rotate_obstacles(state)
        self._cleanup_decoys(state)
        self._maybe_shrink_arena(state, events)
        self._apply_hazard_damage(state, events)
        self._maybe_spawn_powerup(state, events)
        self._process_burst_shots(state)

        grid_width = state["grid_width"]
        grid_height = state["grid_height"]
        fighters = state["fighters"]
        fighter_height = self._fighter_height(state)
        obstacles = state.get("obstacles", [])

        for pid, fighter in fighters.items():
            if not fighter.get("alive"):
                continue
            player = self._player_by_id(state, pid)
            is_ai = player.get("is_ai") if player else False
            if state["settings"].get("training_drill") == "aim_trainer" and is_ai:
                fighter["move_direction"] = "stop"
            if is_ai:
                difficulty = normalize_ai_difficulty(
                    (player or {}).get("ai_difficulty") or state["settings"].get("ai_difficulty")
                )
                move_interval = int(get_ai_config(difficulty, state)["move_interval"])
            else:
                move_interval = 1
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
        self._try_fighter_pickup_powerups(state, events)

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
            effects["freeze_cast_active"] = tick < effects.get("freeze_cast_until", 0)
            effects["mirror_active"] = tick < effects.get("mirror_until", 0)
            effects["homing_active"] = tick < effects.get("homing_until", 0)
            effects["rapid_fire_active"] = tick < effects.get("rapid_fire_until", 0)
            effects["machine_gun_active"] = tick < effects.get("machine_gun_until", 0)
            effects["shield_active"] = tick < effects.get("shield_until", 0)
            effects["wide_shot_active"] = tick < effects.get("wide_shot_until", 0)
            effects["pierce_active"] = tick < effects.get("pierce_until", 0)
            effects["overdrive_active"] = tick < effects.get("overdrive_until", 0)
            effects["phase_shift_active"] = tick < effects.get("phase_shift_until", 0)
            public["effects"] = effects
            public["charging"] = bool(fighter.get("charging"))
            public["charge_ticks"] = int(fighter.get("charge_ticks", 0))
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
            "mutator_secondary": state["settings"].get("mutator_secondary", "none"),
            "arena_theme": state["settings"].get("arena_theme", "classic"),
            "training_drill": state["settings"].get("training_drill", "none"),
            "tutorial_mode": bool(state["settings"].get("tutorial_mode")),
            "powerups_enabled": bool(state["settings"].get("powerups_enabled")),
            "effect_duration_ticks": int(state["settings"].get("effect_duration_ticks", 80)),
            "powerup_lifetime_ticks": int(state["settings"].get("powerup_lifetime_ticks", 120)),
            "bullet_speed": int(state["settings"].get("bullet_speed", 2)),
            "tick_ms": int(state["settings"].get("tick_ms", 75)),
            "charge_max_ticks": int(state["settings"].get("charge_max_ticks", 15)),
            "grid_width": state["grid_width"],
            "grid_height": state["grid_height"],
            "playable_y_min": state.get("playable_y_min", 0),
            "playable_y_max": state.get("playable_y_max", state["grid_height"] - 1),
            "shrinking_arena": bool(state["settings"].get("shrinking_arena")),
            "shrink_start_tick": int(state["settings"].get("shrink_start_tick", 240)),
            "shrink_interval_ticks": self._effective_shrink_interval(state),
            "layout_seed": state["settings"].get("layout_seed"),
            "fog": bool(state["settings"].get("fog")),
            "hazard_damage": int(state["settings"].get("hazard_damage", 1)),
            "hazard_damage_interval_ticks": int(
                state["settings"].get("hazard_damage_interval_ticks", 20)
            ),
            "fighter_height": self._fighter_height(state),
            "obstacles": state.get("obstacles", []),
            "fighters": fighters,
            "bullets": state["bullets"],
            "powerup": state.get("powerup"),
            "decoys": state.get("decoys", []),
            "event_log": state.get("event_log", []),
            "round_stats": state.get("round_stats", {}),
            "match_stats": state.get("match_stats", {}),
            "powerup_bans": state.get("powerup_bans", {}),
            "players": state["players"],
            "winner": state.get("winner"),
            "win_reason": state.get("win_reason"),
            "last_action": state.get("last_action"),
            "last_hit": state.get("last_hit"),
            "tick_hits": state.get("tick_hits", []),
            "viewer_id": viewer_id,
        }

    def check_winner(self, state: dict) -> str | None:
        if state.get("phase") == "finished":
            return state.get("winner")
        return None
