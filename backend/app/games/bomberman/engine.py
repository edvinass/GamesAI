"""Classic Bomberman — shared arena, bombs, soft blocks, last bomber standing."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from app.games.base import GamePlugin
from app.games.bomberman.ai import choose_ai_action, _danger_times
from app.games.bomberman.maps import (
    TILE_EMPTY,
    TILE_HARD,
    TILE_SOFT,
    build_map_grid,
    get_map,
    list_maps,
)

DIRECTIONS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}

BOMBER_COLORS = [
    "#ef4444",
    "#3b82f6",
    "#22c55e",
    "#f59e0b",
    "#a855f7",
    "#06b6d4",
    "#ec4899",
    "#84cc16",
]

DEFAULT_FUSE = 14  # ~2.1s at 150ms
SHORT_FUSE = 5  # ~0.75s — skull "short fuse" disease
EXPLOSION_TTL = 4
POWERUP_CHANCE = 0.35
SOFT_FILL = 0.62
BASE_MOVE_RATE = 1.0
SPEED_BONUS = 0.28
SLOW_MOVE_RATE = 0.32  # skull "slow" — crawl below base speed
MAX_BOMBS_CAP = 8
MAX_RANGE_CAP = 8
MAX_SPEED_LEVEL = 5
THROW_LAND_DISTANCE = 3
# AI re-plans every N ticks (~450ms at 150ms) unless fleeing / throwing.
AI_THINK_INTERVAL = 3
POWERUP_TYPES = ("bomb", "range", "speed", "throw", "kick", "skull")
POWERUP_WEIGHTS = (24, 24, 20, 12, 12, 8)
DISEASE_TYPES = (
    "slow",
    "constipation",
    "diarrhea",
    "reverse",
    "short_fuse",
    "perpetual",
)
DISEASE_DURATION_TICKS = 100  # ~15s at 150ms
REVERSE_DIRS = {
    "up": "down",
    "down": "up",
    "left": "right",
    "right": "left",
    "stop": "stop",
}

GAME_MODES = ("classic", "team", "kill_race")
TEAMS = ("red", "blue")
TEAM_COLORS = {"red": "#ef4444", "blue": "#3b82f6"}
RESPAWN_TICKS = 18  # ~2.7s at 150ms
INVULN_TICKS = 20  # brief protection after spawn
SUDDEN_DEATH_INTERVAL_TICKS = 24  # shrink one ring about every 3.6s
MIN_PLAYABLE_SPAN = 5  # stop shrinking when arena would be too small

# Frontend / host presets expand into concrete settings before validate_settings.
RULE_PRESETS: dict[str, dict] = {
    "classic": {
        "game_mode": "classic",
        "lives": 1,
        "kill_target": 5,
        "match_time_sec": 0,
        "sudden_death_sec": 0,
        "allow_skulls": True,
        "starting_bombs": 1,
        "starting_range": 1,
        "starting_kick": False,
        "starting_throw": False,
    },
    "team_battle": {
        "game_mode": "team",
        "lives": 1,
        "kill_target": 5,
        "match_time_sec": 0,
        "sudden_death_sec": 0,
        "allow_skulls": True,
        "starting_bombs": 1,
        "starting_range": 1,
        "starting_kick": False,
        "starting_throw": False,
    },
    "kill_race": {
        "game_mode": "kill_race",
        "lives": 1,
        "kill_target": 5,
        "match_time_sec": 180,
        "sudden_death_sec": 120,
        "allow_skulls": True,
        "starting_bombs": 1,
        "starting_range": 1,
        "starting_kick": False,
        "starting_throw": False,
    },
    "stock_lives": {
        "game_mode": "classic",
        "lives": 3,
        "kill_target": 5,
        "match_time_sec": 0,
        "sudden_death_sec": 150,
        "allow_skulls": True,
        "starting_bombs": 1,
        "starting_range": 1,
        "starting_kick": False,
        "starting_throw": False,
    },
    "sudden_chaos": {
        "game_mode": "classic",
        "lives": 1,
        "kill_target": 5,
        "match_time_sec": 0,
        "sudden_death_sec": 90,
        "allow_skulls": True,
        "starting_bombs": 2,
        "starting_range": 2,
        "starting_kick": True,
        "starting_throw": False,
        "tick_ms": 120,
    },
}


class BombermanEngine(GamePlugin):
    game_type = "bomberman"

    def default_settings(self) -> dict:
        return {
            "min_players": 2,
            "max_players": 8,
            "map_id": "classic",
            "available_maps": list_maps(),
            "grid_width": 23,
            "grid_height": 19,
            "tick_ms": 150,
            "countdown_sec": 3,
            "solo_practice": False,
            "soft_fill": SOFT_FILL,
            "rule_preset": "classic",
            "game_mode": "classic",
            "lives": 1,
            "kill_target": 5,
            "match_time_sec": 0,
            "sudden_death_sec": 0,
            "allow_skulls": True,
            "starting_bombs": 1,
            "starting_range": 1,
            "starting_kick": False,
            "starting_throw": False,
        }

    def validate_settings(self, settings: dict) -> dict:
        defaults = self.default_settings()
        raw = dict(settings or {})
        # Presets are applied by the lobby (full settings blob). Do not re-expand
        # RULE_PRESETS here — that would reset host tweaks on partial updates.
        merged = {**defaults, **raw}
        preset_id = str(merged.get("rule_preset", "classic"))
        if preset_id not in RULE_PRESETS and preset_id != "custom":
            preset_id = "classic"
        merged["rule_preset"] = preset_id

        merged["min_players"] = max(2, min(8, int(merged.get("min_players", 2))))
        merged["max_players"] = max(
            merged["min_players"], min(8, int(merged.get("max_players", 8)))
        )
        map_id = str(merged.get("map_id", "classic"))
        try:
            meta = get_map(map_id)
        except ValueError:
            map_id = "classic"
            meta = get_map(map_id)
        merged["map_id"] = map_id
        merged["available_maps"] = list_maps()
        # Map owns arena size; keep odd dimensions for clean patterns.
        w = int(meta["width"])
        h = int(meta["height"])
        if w % 2 == 0:
            w += 1
        if h % 2 == 0:
            h += 1
        merged["grid_width"] = w
        merged["grid_height"] = h
        merged["tick_ms"] = max(80, min(300, int(merged.get("tick_ms", 150))))
        merged["countdown_sec"] = max(1, min(10, int(merged.get("countdown_sec", 3))))
        merged["solo_practice"] = bool(merged.get("solo_practice", False))
        default_fill = float(meta.get("soft_fill", SOFT_FILL))
        # Allow host override, but default to the map's intended density.
        if "soft_fill" in raw:
            merged["soft_fill"] = max(0.2, min(0.85, float(merged.get("soft_fill", default_fill))))
        else:
            merged["soft_fill"] = default_fill

        mode = str(merged.get("game_mode", "classic"))
        if mode not in GAME_MODES:
            mode = "classic"
        merged["game_mode"] = mode
        merged["lives"] = max(1, min(5, int(merged.get("lives", 1))))
        merged["kill_target"] = max(1, min(20, int(merged.get("kill_target", 5))))
        merged["match_time_sec"] = max(0, min(600, int(merged.get("match_time_sec", 0))))
        merged["sudden_death_sec"] = max(0, min(600, int(merged.get("sudden_death_sec", 0))))
        merged["allow_skulls"] = bool(merged.get("allow_skulls", True))
        merged["starting_bombs"] = max(1, min(MAX_BOMBS_CAP, int(merged.get("starting_bombs", 1))))
        merged["starting_range"] = max(1, min(MAX_RANGE_CAP, int(merged.get("starting_range", 1))))
        merged["starting_kick"] = bool(merged.get("starting_kick", False))
        merged["starting_throw"] = bool(merged.get("starting_throw", False))
        return merged

    def tick_interval_ms(self) -> int:
        return 150

    def clone_tick_state(self, state: dict) -> dict:
        """Shallow structural copy — avoids deepcopy of the full arena dict."""
        bombers: dict[str, dict] = {}
        for pid, bomber in (state.get("bombers") or {}).items():
            nb = dict(bomber)
            ids = nb.get("passable_bomb_ids")
            if ids is not None:
                nb["passable_bomb_ids"] = list(ids)
            bombers[pid] = nb
        out = {
            **state,
            "grid": [row[:] for row in state["grid"]],
            "bombers": bombers,
            "bombs": [dict(b) for b in state.get("bombs") or []],
            "explosions": [dict(e) for e in state.get("explosions") or []],
            "powerups": [dict(p) for p in state.get("powerups") or []],
            # players / settings are not mutated during tick
            "players": state.get("players") or [],
            "settings": state.get("settings") or {},
        }
        # Per-broadcast caches must not leak across ticks.
        out.pop("_public_bundle", None)
        out["_grid_changes"] = []
        return out

    def validate_lobby(self, players: list[dict], settings: dict) -> str | None:
        settings = self.validate_settings(settings)
        if settings.get("solo_practice"):
            humans = [p for p in players if not p.get("is_ai")]
            if len(humans) != 1:
                return "Solo practice requires exactly one human player"
            return None

        count = len(players)
        if count < settings["min_players"]:
            return f"Need at least {settings['min_players']} players"
        if count > settings["max_players"]:
            return f"Maximum {settings['max_players']} players allowed"
        if settings.get("game_mode") == "team":
            if count < 2:
                return "Team battle needs at least 2 players"
            assigned = self._assign_teams(players, settings)
            sides = {t for t in assigned.values() if t in TEAMS}
            if sides != {"red", "blue"}:
                return "Need at least one player on Red and one on Blue"
        return None

    def create_initial_state(self, players: list[dict], settings: dict) -> dict:
        settings = self.validate_settings(settings)
        grid, spawn_pool, map_meta = build_map_grid(
            settings["map_id"], soft_fill=settings["soft_fill"]
        )
        width = len(grid[0])
        height = len(grid)
        spawns = spawn_pool[: len(players)]
        team_of = self._assign_teams(players, settings)

        start_bombs = int(settings["starting_bombs"])
        start_range = int(settings["starting_range"])
        start_kick = bool(settings["starting_kick"])
        start_throw = bool(settings["starting_throw"])
        lives = int(settings["lives"])

        bombers: dict[str, dict] = {}
        for i, player in enumerate(players):
            sx, sy = spawns[i]
            is_ai = bool(player.get("is_ai"))
            team = team_of.get(player["id"])
            color = (
                TEAM_COLORS.get(team, BOMBER_COLORS[i % len(BOMBER_COLORS)])
                if settings["game_mode"] == "team" and team
                else BOMBER_COLORS[i % len(BOMBER_COLORS)]
            )
            # AI seats get a mild bomb/range head start; no free speed (acts slower).
            bombs = max(start_bombs, 2 if is_ai else start_bombs)
            brange = max(start_range, 2 if is_ai else start_range)
            bombers[player["id"]] = {
                "x": sx,
                "y": sy,
                "spawn_x": sx,
                "spawn_y": sy,
                "direction": "stop",
                "next_direction": "stop",
                "facing": "down",
                "alive": True,
                "color": color,
                "team": team,
                "lives": lives,
                "max_bombs": bombs,
                "bomb_range": brange,
                "speed_level": 0,
                "can_throw": start_throw,
                "can_kick": start_kick,
                "carrying_bomb_id": None,
                "move_credit": 0.0,
                "kills": 0,
                "passable_bomb_ids": [],
                "disease": None,
                "disease_ticks": 0,
                "respawn_ticks": 0,
                "invuln_ticks": 0,
            }

        countdown_sec = settings["countdown_sec"]
        countdown_ends_at = (
            datetime.now(timezone.utc) + timedelta(seconds=countdown_sec)
        ).isoformat()

        tick_ms = int(settings["tick_ms"])
        match_time_sec = int(settings["match_time_sec"])
        sudden_death_sec = int(settings["sudden_death_sec"])
        match_ticks = (match_time_sec * 1000) // tick_ms if match_time_sec > 0 else 0
        sudden_death_ticks = (
            (sudden_death_sec * 1000) // tick_ms if sudden_death_sec > 0 else 0
        )

        return {
            "phase": "countdown",
            "countdown_ends_at": countdown_ends_at,
            "tick": 0,
            "playing_tick": 0,
            "tick_ms": tick_ms,
            "grid_width": width,
            "grid_height": height,
            "grid": grid,
            "map_id": settings["map_id"],
            "map_name": map_meta["name"],
            "bombers": bombers,
            "bombs": [],
            "explosions": [],
            "powerups": [],
            "players": players,
            "settings": settings,
            "game_mode": settings["game_mode"],
            "kill_target": settings["kill_target"],
            "match_ticks": match_ticks,
            "sudden_death_ticks": sudden_death_ticks,
            "shrink_level": 0,
            "sudden_death_active": False,
            "winner": None,
            "winning_team": None,
            "win_reason": None,
            "last_action": None,
            "_bomb_seq": 0,
        }

    def _assign_teams(self, players: list[dict], settings: dict) -> dict[str, str | None]:
        if settings.get("game_mode") != "team":
            return {p["id"]: None for p in players}

        teams: dict[str, str | None] = {}
        red_count = 0
        blue_count = 0
        unassigned: list[str] = []

        for player in players:
            raw = player.get("team")
            team = raw if raw in TEAMS else None
            if team == "red":
                teams[player["id"]] = "red"
                red_count += 1
            elif team == "blue":
                teams[player["id"]] = "blue"
                blue_count += 1
            else:
                unassigned.append(player["id"])

        # Fill empty seats onto the smaller side so both colors can start.
        for pid in unassigned:
            if red_count <= blue_count:
                teams[pid] = "red"
                red_count += 1
            else:
                teams[pid] = "blue"
                blue_count += 1
        return teams

    def _next_bomb_id(self, state: dict) -> str:
        nid = int(state.get("_bomb_seq", 0)) + 1
        state["_bomb_seq"] = nid
        return f"bomb-{nid}"

    def _set_tile(self, state: dict, x: int, y: int, tile: int) -> None:
        """Mutate a grid cell and record it for WS delta broadcasts."""
        if state["grid"][y][x] == tile:
            return
        state["grid"][y][x] = tile
        state.setdefault("_grid_changes", []).append({"x": x, "y": y, "t": tile})

    def _active_bomb_count(self, state: dict, player_id: str) -> int:
        return sum(1 for b in state.get("bombs") or [] if b.get("owner_id") == player_id)

    def _bomb_at(
        self, state: dict, x: int, y: int, *, grounded_only: bool = False
    ) -> dict | None:
        for bomb in state.get("bombs") or []:
            if bomb["x"] != x or bomb["y"] != y:
                continue
            # Thrown / carried bombs are not on the floor.
            if grounded_only and bomb.get("flight") in ("throw", "carried"):
                continue
            return bomb
        return None

    def _is_bomb_moving(self, bomb: dict) -> bool:
        return bomb.get("flight") in ("throw", "kick") or (
            bool(bomb.get("sliding")) and bomb.get("flight") not in (None, "carried")
        )

    def _clear_bomb_motion(self, bomb: dict) -> None:
        bomb["flight"] = None
        bomb["sliding"] = False
        bomb["slide_dir"] = None
        bomb["land_x"] = None
        bomb["land_y"] = None

    def _find_bomb(self, state: dict, bomb_id: str | None) -> dict | None:
        if not bomb_id:
            return None
        return next((b for b in state.get("bombs") or [] if b["id"] == bomb_id), None)

    def _sync_carried_bomb(self, state: dict, bomber: dict) -> None:
        bomb = self._find_bomb(state, bomber.get("carrying_bomb_id"))
        if bomb is None:
            bomber["carrying_bomb_id"] = None
            return
        bomb["flight"] = "carried"
        bomb["sliding"] = False
        bomb["slide_dir"] = None
        bomb["land_x"] = None
        bomb["land_y"] = None
        bomb["x"] = bomber["x"]
        bomb["y"] = bomber["y"]

    def _drop_carried_bomb(self, state: dict, bomber: dict) -> None:
        bomb = self._find_bomb(state, bomber.get("carrying_bomb_id"))
        bomber["carrying_bomb_id"] = None
        if bomb is None:
            return
        bomb["x"] = bomber["x"]
        bomb["y"] = bomber["y"]
        self._clear_bomb_motion(bomb)
        self._grant_passable_on_cell(state, bomb["id"], bomb["x"], bomb["y"])

    def _pick_up_bomb(
        self, state: dict, player_id: str, bomber: dict, bomb: dict
    ) -> list[dict]:
        """Classic Power Glove: lift a grounded bomb and carry it."""
        events: list[dict] = []
        if not bomber.get("can_throw"):
            return events
        if bomber.get("carrying_bomb_id"):
            return events
        if bomb.get("flight") in ("throw", "kick", "carried"):
            return events

        bomber["carrying_bomb_id"] = bomb["id"]
        bomb["flight"] = "carried"
        bomb["sliding"] = False
        bomb["slide_dir"] = None
        bomb["land_x"] = None
        bomb["land_y"] = None
        bomb["x"] = bomber["x"]
        bomb["y"] = bomber["y"]
        bomber["passable_bomb_ids"] = [
            bid
            for bid in (bomber.get("passable_bomb_ids") or [])
            if bid != bomb["id"]
        ]

        state["last_action"] = {
            "type": "bomb_picked_up",
            "player_id": player_id,
            "bomb_id": bomb["id"],
            "x": bomb["x"],
            "y": bomb["y"],
        }
        events.append(
            {
                "type": "bomb_picked_up",
                "player_id": player_id,
                "bomb_id": bomb["id"],
                "x": bomb["x"],
                "y": bomb["y"],
            }
        )
        return events

    def _powerup_at(self, state: dict, x: int, y: int) -> dict | None:
        for p in state.get("powerups") or []:
            if p["x"] == x and p["y"] == y:
                return p
        return None

    def _is_walkable(self, state: dict, bomber: dict, x: int, y: int) -> bool:
        width = state["grid_width"]
        height = state["grid_height"]
        if not (0 <= x < width and 0 <= y < height):
            return False
        tile = state["grid"][y][x]
        if tile != TILE_EMPTY:
            return False
        bomb = self._bomb_at(state, x, y, grounded_only=True)
        if bomb is not None:
            passable = set(bomber.get("passable_bomb_ids") or [])
            if bomb["id"] not in passable:
                return False
        return True

    def _kick_blocked(self, state: dict, x: int, y: int) -> bool:
        width = state["grid_width"]
        height = state["grid_height"]
        if not (0 <= x < width and 0 <= y < height):
            return True
        if state["grid"][y][x] != TILE_EMPTY:
            return True
        if self._bomb_at(state, x, y, grounded_only=True) is not None:
            return True
        return False

    def _can_kick_bomb(self, state: dict, bomb: dict, direction: str) -> bool:
        if direction not in DIRECTIONS:
            return False
        if bomb.get("flight") in ("throw", "kick", "carried") or bomb.get("sliding"):
            return False
        dx, dy = DIRECTIONS[direction]
        return not self._kick_blocked(state, bomb["x"] + dx, bomb["y"] + dy)

    def _place_bomb(self, state: dict, player_id: str, bomber: dict) -> list[dict]:
        events: list[dict] = []
        if not self._bomber_controllable(bomber):
            return events

        # Classic glove: Space while carrying throws.
        if bomber.get("can_throw") and bomber.get("carrying_bomb_id"):
            bomb = self._find_bomb(state, bomber.get("carrying_bomb_id"))
            if bomb is not None:
                return self._throw_bomb(state, player_id, bomber, bomb)
            bomber["carrying_bomb_id"] = None

        x, y = bomber["x"], bomber["y"]
        bomb_here = self._bomb_at(state, x, y, grounded_only=True)
        if bomb_here is not None:
            # Power Glove: Space while standing on a bomb picks it up.
            if bomber.get("can_throw") and not bomber.get("carrying_bomb_id"):
                return self._pick_up_bomb(state, player_id, bomber, bomb_here)
            return events

        # Power Glove: Space while facing an adjacent bomb picks it up.
        if bomber.get("can_throw") and not bomber.get("carrying_bomb_id"):
            facing = self._throw_facing(bomber)
            if facing in DIRECTIONS:
                dx, dy = DIRECTIONS[facing]
                adjacent = self._bomb_at(state, x + dx, y + dy, grounded_only=True)
                if adjacent is not None:
                    return self._pick_up_bomb(state, player_id, bomber, adjacent)

        if bomber.get("carrying_bomb_id"):
            return events

        # Constipation: cannot plant new bombs (pick-up / throw still allowed above).
        if bomber.get("disease") == "constipation":
            return events

        if self._active_bomb_count(state, player_id) >= int(bomber.get("max_bombs", 1)):
            return events

        fuse = (
            SHORT_FUSE
            if bomber.get("disease") == "short_fuse"
            else DEFAULT_FUSE
        )
        bomb = {
            "id": self._next_bomb_id(state),
            "x": x,
            "y": y,
            "owner_id": player_id,
            "range": int(bomber.get("bomb_range", 1)),
            "fuse": fuse,
            "flight": None,
            "sliding": False,
            "slide_dir": None,
            "land_x": None,
            "land_y": None,
        }
        state.setdefault("bombs", []).append(bomb)
        passable = list(bomber.get("passable_bomb_ids") or [])
        if bomb["id"] not in passable:
            passable.append(bomb["id"])
        bomber["passable_bomb_ids"] = passable
        state["last_action"] = {"type": "place_bomb", "player_id": player_id, "x": x, "y": y}
        events.append(
            {
                "type": "bomb_placed",
                "player_id": player_id,
                "bomb_id": bomb["id"],
                "x": x,
                "y": y,
            }
        )
        return events

    def _throw_facing(self, bomber: dict) -> str:
        for key in ("direction", "next_direction", "facing"):
            value = bomber.get(key)
            if value in DIRECTIONS:
                return value
        return "right"

    def _throw_cell_landable(
        self,
        state: dict,
        x: int,
        y: int,
        *,
        ignore_bomb_id: str | None = None,
    ) -> bool:
        """Empty floor tile with no other bomb on it (carried bombs do not occupy the floor)."""
        width = state["grid_width"]
        height = state["grid_height"]
        if not (0 <= x < width and 0 <= y < height):
            return False
        if state["grid"][y][x] != TILE_EMPTY:
            return False
        for other in state.get("bombs") or []:
            if ignore_bomb_id and other.get("id") == ignore_bomb_id:
                continue
            if other.get("x") != x or other.get("y") != y:
                continue
            # Held above a bomber — not a floor obstacle.
            if other.get("flight") == "carried":
                continue
            # Grounded, kicked, or mid-throw bombs all block landing on this cell.
            return False
        return True

    def _find_throw_landing(
        self,
        state: dict,
        start_x: int,
        start_y: int,
        direction: str,
        *,
        ignore_bomb_id: str | None = None,
    ) -> tuple[int, int] | None:
        """Land 3 tiles away; if blocked, continue to the next empty tile in throw direction."""
        if direction not in DIRECTIONS:
            return None
        dx, dy = DIRECTIONS[direction]
        width = state["grid_width"]
        height = state["grid_height"]
        short_empty: tuple[int, int] | None = None
        x, y = start_x, start_y
        for dist in range(1, max(width, height) + 1):
            x, y = x + dx, y + dy
            if not (0 <= x < width and 0 <= y < height):
                break
            if not self._throw_cell_landable(
                state, x, y, ignore_bomb_id=ignore_bomb_id
            ):
                # Obstacle / bomb: keep flying and look further for an empty tile.
                continue
            if dist < THROW_LAND_DISTANCE:
                short_empty = (x, y)
                continue
            # First empty tile at or beyond the preferred throw distance.
            return (x, y)
        # Near the map edge with no room for a full throw — land on the farthest empty.
        return short_empty

    def _next_throw_landing_from(
        self,
        state: dict,
        x: int,
        y: int,
        direction: str,
        *,
        ignore_bomb_id: str | None = None,
    ) -> tuple[int, int] | None:
        """Find the next landable tile at or beyond (x, y) in throw direction."""
        if direction not in DIRECTIONS:
            return None
        dx, dy = DIRECTIONS[direction]
        width = state["grid_width"]
        height = state["grid_height"]
        cx, cy = x, y
        for _ in range(max(width, height) + 1):
            if not (0 <= cx < width and 0 <= cy < height):
                return None
            if self._throw_cell_landable(
                state, cx, cy, ignore_bomb_id=ignore_bomb_id
            ):
                return (cx, cy)
            cx, cy = cx + dx, cy + dy
        return None

    def _grant_passable_on_cell(self, state: dict, bomb_id: str, x: int, y: int) -> None:
        for bomber in state["bombers"].values():
            if not bomber.get("alive"):
                continue
            if bomber["x"] == x and bomber["y"] == y:
                passable = list(bomber.get("passable_bomb_ids") or [])
                if bomb_id not in passable:
                    passable.append(bomb_id)
                bomber["passable_bomb_ids"] = passable

    def _kick_bomb(
        self, state: dict, player_id: str, direction: str, bomb: dict
    ) -> list[dict]:
        events: list[dict] = []
        if not self._can_kick_bomb(state, bomb, direction):
            return events

        dx, dy = DIRECTIONS[direction]
        nx, ny = bomb["x"] + dx, bomb["y"] + dy
        bomb["flight"] = "kick"
        bomb["sliding"] = True
        bomb["slide_dir"] = direction
        bomb["land_x"] = None
        bomb["land_y"] = None
        bomb["x"], bomb["y"] = nx, ny
        # Last player to move the bomb owns the kill credit (and bomb slot).
        bomb["owner_id"] = player_id
        self._grant_passable_on_cell(state, bomb["id"], nx, ny)

        state["last_action"] = {
            "type": "bomb_kicked",
            "player_id": player_id,
            "bomb_id": bomb["id"],
            "direction": direction,
            "x": nx,
            "y": ny,
        }
        events.append(
            {
                "type": "bomb_kicked",
                "player_id": player_id,
                "bomb_id": bomb["id"],
                "direction": direction,
                "x": nx,
                "y": ny,
            }
        )
        return events

    def _throw_bomb(
        self, state: dict, player_id: str, bomber: dict, bomb: dict
    ) -> list[dict]:
        events: list[dict] = []
        if bomb.get("flight") in ("throw", "kick"):
            return events

        facing = self._throw_facing(bomber)
        bomber["facing"] = facing
        start_x, start_y = bomber["x"], bomber["y"]
        bomb["x"], bomb["y"] = start_x, start_y
        landing = self._find_throw_landing(
            state, start_x, start_y, facing, ignore_bomb_id=bomb.get("id")
        )
        if landing is None:
            if bomber.get("carrying_bomb_id") == bomb["id"]:
                self._sync_carried_bomb(state, bomber)
            return events

        land_x, land_y = landing
        dx, dy = DIRECTIONS[facing]
        nx, ny = start_x + dx, start_y + dy
        if not (0 <= nx < state["grid_width"] and 0 <= ny < state["grid_height"]):
            return events

        bomber["carrying_bomb_id"] = None
        bomb["flight"] = "throw"
        bomb["sliding"] = True
        bomb["slide_dir"] = facing
        bomb["land_x"] = land_x
        bomb["land_y"] = land_y
        bomb["x"], bomb["y"] = nx, ny
        # Last player to throw the bomb owns the kill credit (and bomb slot).
        bomb["owner_id"] = player_id
        if state["grid"][ny][nx] == TILE_EMPTY:
            self._grant_passable_on_cell(state, bomb["id"], nx, ny)
        if (nx, ny) == (land_x, land_y):
            # If the landing tile became blocked, bounce further before settling.
            if not self._throw_cell_landable(
                state, nx, ny, ignore_bomb_id=bomb.get("id")
            ):
                bounced = self._next_throw_landing_from(
                    state, nx + dx, ny + dy, facing, ignore_bomb_id=bomb.get("id")
                )
                if bounced is not None:
                    bomb["land_x"], bomb["land_y"] = bounced
                else:
                    self._clear_bomb_motion(bomb)
            else:
                self._clear_bomb_motion(bomb)

        land_x = bomb.get("land_x", land_x)
        land_y = bomb.get("land_y", land_y)
        state["last_action"] = {
            "type": "bomb_thrown",
            "player_id": player_id,
            "bomb_id": bomb["id"],
            "direction": facing,
            "x": bomb["x"],
            "y": bomb["y"],
            "land_x": land_x,
            "land_y": land_y,
        }
        events.append(
            {
                "type": "bomb_thrown",
                "player_id": player_id,
                "bomb_id": bomb["id"],
                "direction": facing,
                "x": bomb["x"],
                "y": bomb["y"],
                "land_x": land_x,
                "land_y": land_y,
            }
        )
        return events

    def _tick_sliding_bombs(self, state: dict) -> list[dict]:
        events: list[dict] = []
        width = state["grid_width"]
        height = state["grid_height"]
        for bomb in state.get("bombs") or []:
            flight = bomb.get("flight")
            if flight == "carried":
                continue
            if not flight and not bomb.get("sliding"):
                continue
            # Legacy / fallback: sliding with landing coords => throw
            if not flight:
                flight = "throw" if bomb.get("land_x") is not None else "kick"
                bomb["flight"] = flight

            direction = bomb.get("slide_dir")
            if direction not in DIRECTIONS:
                self._clear_bomb_motion(bomb)
                continue

            if flight == "throw":
                events.extend(self._tick_throw_bomb(state, bomb, direction, width, height))
            elif flight == "kick":
                events.extend(self._tick_kick_bomb(state, bomb, direction))
        return events

    def _tick_throw_bomb(
        self,
        state: dict,
        bomb: dict,
        direction: str,
        width: int,
        height: int,
    ) -> list[dict]:
        events: list[dict] = []
        land_x = bomb.get("land_x")
        land_y = bomb.get("land_y")
        if land_x is None or land_y is None:
            self._clear_bomb_motion(bomb)
            return events

        dx, dy = DIRECTIONS[direction]
        # If the planned landing is (now) blocked by a bomb/obstacle, bounce further.
        if not self._throw_cell_landable(
            state, int(land_x), int(land_y), ignore_bomb_id=bomb.get("id")
        ):
            bounced = self._next_throw_landing_from(
                state,
                int(land_x) + dx,
                int(land_y) + dy,
                direction,
                ignore_bomb_id=bomb.get("id"),
            )
            if bounced is None:
                # No further tile — keep current planned cell; settle when we arrive.
                pass
            else:
                land_x, land_y = bounced
                bomb["land_x"], bomb["land_y"] = land_x, land_y

        if (bomb["x"], bomb["y"]) == (land_x, land_y):
            if not self._throw_cell_landable(
                state, bomb["x"], bomb["y"], ignore_bomb_id=bomb.get("id")
            ):
                bounced = self._next_throw_landing_from(
                    state,
                    bomb["x"] + dx,
                    bomb["y"] + dy,
                    direction,
                    ignore_bomb_id=bomb.get("id"),
                )
                if bounced is not None:
                    bomb["land_x"], bomb["land_y"] = bounced
                    land_x, land_y = bounced
                else:
                    self._clear_bomb_motion(bomb)
                    events.append(
                        {
                            "type": "bomb_stopped",
                            "bomb_id": bomb["id"],
                            "x": bomb["x"],
                            "y": bomb["y"],
                        }
                    )
                    return events
            else:
                self._clear_bomb_motion(bomb)
                events.append(
                    {
                        "type": "bomb_stopped",
                        "bomb_id": bomb["id"],
                        "x": bomb["x"],
                        "y": bomb["y"],
                    }
                )
                return events

        nx, ny = bomb["x"] + dx, bomb["y"] + dy
        if not (0 <= nx < width and 0 <= ny < height):
            self._clear_bomb_motion(bomb)
            return events

        bomb["x"], bomb["y"] = nx, ny
        if state["grid"][ny][nx] == TILE_EMPTY:
            self._grant_passable_on_cell(state, bomb["id"], nx, ny)
        events.append(
            {
                "type": "bomb_slid",
                "bomb_id": bomb["id"],
                "x": nx,
                "y": ny,
                "direction": direction,
                "flight": "throw",
            }
        )
        if (nx, ny) == (land_x, land_y):
            if not self._throw_cell_landable(
                state, nx, ny, ignore_bomb_id=bomb.get("id")
            ):
                bounced = self._next_throw_landing_from(
                    state, nx + dx, ny + dy, direction, ignore_bomb_id=bomb.get("id")
                )
                if bounced is not None:
                    bomb["land_x"], bomb["land_y"] = bounced
                    return events
            self._clear_bomb_motion(bomb)
            events.append(
                {
                    "type": "bomb_stopped",
                    "bomb_id": bomb["id"],
                    "x": nx,
                    "y": ny,
                }
            )
        return events

    def _tick_kick_bomb(self, state: dict, bomb: dict, direction: str) -> list[dict]:
        events: list[dict] = []
        dx, dy = DIRECTIONS[direction]
        nx, ny = bomb["x"] + dx, bomb["y"] + dy
        if self._kick_blocked(state, nx, ny):
            self._clear_bomb_motion(bomb)
            events.append(
                {
                    "type": "bomb_stopped",
                    "bomb_id": bomb["id"],
                    "x": bomb["x"],
                    "y": bomb["y"],
                }
            )
            return events

        bomb["x"], bomb["y"] = nx, ny
        self._grant_passable_on_cell(state, bomb["id"], nx, ny)
        events.append(
            {
                "type": "bomb_slid",
                "bomb_id": bomb["id"],
                "x": nx,
                "y": ny,
                "direction": direction,
                "flight": "kick",
            }
        )
        return events

    def apply_action(
        self, state: dict, action: dict, player: dict
    ) -> tuple[dict, list[dict]]:
        events: list[dict] = []
        if state["phase"] != "playing":
            return state, events

        player_id = player["id"]
        bomber = state["bombers"].get(player_id)
        if not bomber or not self._bomber_controllable(bomber):
            return state, events

        action_type = action.get("type")
        if action_type == "place_bomb":
            events.extend(self._place_bomb(state, player_id, bomber))
            return state, events

        if action_type != "set_direction":
            return state, events

        direction = action.get("direction")
        if direction not in DIRECTIONS and direction != "stop":
            return state, events

        direction = self._apply_reverse(bomber, direction)
        bomber["next_direction"] = direction
        if direction in DIRECTIONS:
            bomber["facing"] = direction
        state["last_action"] = {
            "type": "set_direction",
            "player_id": player_id,
            "direction": direction,
        }
        return state, events

    def _apply_reverse(self, bomber: dict, direction: str) -> str:
        if bomber.get("disease") != "reverse":
            return direction
        return REVERSE_DIRS.get(direction, direction)

    def _bomber_pid(self, state: dict, bomber: dict) -> str | None:
        return next((pid for pid, b in state["bombers"].items() if b is bomber), None)

    def _infect(
        self,
        bomber: dict,
        disease: str | None = None,
        *,
        ticks: int | None = None,
    ) -> str:
        chosen = disease if disease in DISEASE_TYPES else random.choice(DISEASE_TYPES)
        bomber["disease"] = chosen
        bomber["disease_ticks"] = (
            DISEASE_DURATION_TICKS if ticks is None else max(1, int(ticks))
        )
        return chosen

    def _clear_disease(self, bomber: dict) -> None:
        bomber["disease"] = None
        bomber["disease_ticks"] = 0

    def _tick_diseases(self, state: dict) -> list[dict]:
        events: list[dict] = []
        for pid, bomber in state["bombers"].items():
            if not bomber.get("disease"):
                continue
            if not bomber.get("alive"):
                self._clear_disease(bomber)
                continue
            ticks = int(bomber.get("disease_ticks", 0)) - 1
            if ticks <= 0:
                self._clear_disease(bomber)
                events.append({"type": "disease_cleared", "player_id": pid})
            else:
                bomber["disease_ticks"] = ticks
        return events

    def _spread_diseases(self, state: dict) -> list[dict]:
        """Transfer skull disease on contact (same tile). Passing it cures the giver."""
        events: list[dict] = []
        alive = [
            (pid, b)
            for pid, b in state["bombers"].items()
            if self._bomber_controllable(b)
        ]
        by_cell: dict[tuple[int, int], list[tuple[str, dict]]] = {}
        for pid, bomber in alive:
            by_cell.setdefault((bomber["x"], bomber["y"]), []).append((pid, bomber))

        for occupants in by_cell.values():
            if len(occupants) < 2:
                continue
            infected = [(pid, b) for pid, b in occupants if b.get("disease")]
            clean = [(pid, b) for pid, b in occupants if not b.get("disease")]
            # Infected + healthy: each infected tags one clean player and is cured.
            if infected and clean:
                random.shuffle(clean)
                for i, (src_pid, src) in enumerate(infected):
                    if i >= len(clean):
                        break
                    dst_pid, dst = clean[i]
                    disease = src.get("disease")
                    ticks = int(src.get("disease_ticks", DISEASE_DURATION_TICKS))
                    self._clear_disease(src)
                    events.append(
                        {
                            "type": "disease_cleared",
                            "player_id": src_pid,
                            "reason": "transferred",
                        }
                    )
                    self._infect(dst, disease, ticks=ticks)
                    events.append(
                        {
                            "type": "disease_infected",
                            "player_id": dst_pid,
                            "disease": disease,
                            "from": src_pid,
                        }
                    )
                continue
            # Two infected players: swap diseases.
            if len(infected) >= 2:
                a_pid, a = infected[0]
                b_pid, b = infected[1]
                a_dis, a_ticks = a.get("disease"), int(a.get("disease_ticks", 0))
                b_dis, b_ticks = b.get("disease"), int(b.get("disease_ticks", 0))
                if a_dis == b_dis:
                    continue
                self._infect(a, b_dis, ticks=b_ticks)
                self._infect(b, a_dis, ticks=a_ticks)
                events.append(
                    {
                        "type": "disease_swapped",
                        "a": a_pid,
                        "b": b_pid,
                        "a_disease": b_dis,
                        "b_disease": a_dis,
                    }
                )
        return events

    def _desired_move_direction(self, bomber: dict) -> str:
        """Direction the bomber wants to walk this tick (perpetual overrides stop)."""
        desired = bomber.get("next_direction", "stop")
        if bomber.get("disease") == "perpetual":
            if desired in DIRECTIONS:
                return desired
            for key in ("facing", "direction"):
                value = bomber.get(key)
                if value in DIRECTIONS:
                    return value
            return "down"
        return desired if desired in DIRECTIONS or desired == "stop" else "stop"

    def _apply_ai_actions(self, state: dict) -> list[dict]:
        events: list[dict] = []
        ai_seats: list[tuple[str, dict]] = []
        for player in state["players"]:
            if not player.get("is_ai"):
                continue
            pid = player["id"]
            bomber = state["bombers"].get(pid)
            if not bomber or not self._bomber_controllable(bomber):
                continue
            ai_seats.append((pid, bomber))
        if not ai_seats:
            return events

        # Shared danger map; AIs commit to a plan between think ticks.
        danger = _danger_times(state)
        playing_tick = int(state.get("playing_tick", 0))
        for i, (pid, bomber) in enumerate(ai_seats):
            pos = (int(bomber["x"]), int(bomber["y"]))
            in_danger = danger.get(pos) is not None
            # Always react when threatened, carrying, or standing on a bomb.
            urgent = (
                in_danger
                or bool(bomber.get("carrying_bomb_id"))
                or any(
                    b.get("x") == pos[0]
                    and b.get("y") == pos[1]
                    and b.get("flight") not in ("throw", "carried")
                    for b in (state.get("bombs") or [])
                )
            )
            due = (playing_tick + i) % AI_THINK_INTERVAL == 0
            if not urgent and not due:
                continue
            direction, place = choose_ai_action(
                state,
                pid,
                bomber,
                danger=danger,
                heavy_think=True,
            )
            if direction in DIRECTIONS or direction == "stop":
                bomber["next_direction"] = self._apply_reverse(bomber, direction)
            if place:
                events.extend(self._place_bomb(state, pid, bomber))
        return events

    def _move_rate(self, bomber: dict) -> float:
        if bomber.get("disease") == "slow":
            return SLOW_MOVE_RATE
        level = max(0, min(MAX_SPEED_LEVEL, int(bomber.get("speed_level", 0))))
        return BASE_MOVE_RATE + SPEED_BONUS * level

    def _pickup_powerup(self, state: dict, bomber: dict, x: int, y: int) -> list[dict]:
        events: list[dict] = []
        powerup = self._powerup_at(state, x, y)
        if powerup is None:
            return events
        ptype = powerup.get("type")
        pid = self._bomber_pid(state, bomber)
        if ptype == "bomb":
            bomber["max_bombs"] = min(MAX_BOMBS_CAP, int(bomber.get("max_bombs", 1)) + 1)
        elif ptype == "range":
            bomber["bomb_range"] = min(MAX_RANGE_CAP, int(bomber.get("bomb_range", 1)) + 1)
        elif ptype == "speed":
            bomber["speed_level"] = min(
                MAX_SPEED_LEVEL, int(bomber.get("speed_level", 0)) + 1
            )
        elif ptype == "throw":
            bomber["can_throw"] = True
        elif ptype == "kick":
            bomber["can_kick"] = True
        elif ptype == "skull":
            disease = self._infect(bomber)
            events.append(
                {
                    "type": "disease_infected",
                    "player_id": pid,
                    "disease": disease,
                    "from": "skull",
                }
            )
        else:
            return events

        state["powerups"] = [
            p for p in state.get("powerups") or [] if not (p["x"] == x and p["y"] == y)
        ]
        events.append(
            {
                "type": "powerup_taken",
                "player_id": pid,
                "powerup_type": ptype,
                "x": x,
                "y": y,
            }
        )
        return events

    def _clear_passable_bombs(self, state: dict) -> None:
        for bomber in state["bombers"].values():
            if not bomber.get("alive"):
                continue
            passable = list(bomber.get("passable_bomb_ids") or [])
            if not passable:
                continue
            kept: list[str] = []
            for bid in passable:
                bomb = next((b for b in state.get("bombs") or [] if b["id"] == bid), None)
                if bomb and bomb["x"] == bomber["x"] and bomb["y"] == bomber["y"]:
                    kept.append(bid)
            bomber["passable_bomb_ids"] = kept

    def _resolve_step_direction(self, state: dict, bomber: dict) -> str | None:
        """Move only in the held direction.

        A blocked turn faces the wall and stops — no sliding past on prior momentum.
        Perpetual disease still falls back to momentum so the curse cannot pin you
        forever against a single brick.
        """
        desired = self._desired_move_direction(bomber)
        candidates: list[str] = []
        if desired in DIRECTIONS:
            candidates.append(desired)
        if bomber.get("disease") == "perpetual":
            momentum = bomber.get("direction", "stop")
            if momentum in DIRECTIONS and momentum != desired:
                candidates.append(momentum)
        for direction in candidates:
            dx, dy = DIRECTIONS[direction]
            nx, ny = bomber["x"] + dx, bomber["y"] + dy
            bomb = self._bomb_at(state, nx, ny, grounded_only=True)
            if (
                bomb is not None
                and bomber.get("can_kick")
                and self._can_kick_bomb(state, bomb, direction)
            ):
                return direction
            if self._is_walkable(state, bomber, nx, ny):
                return direction
        return None

    def _step_movement(self, state: dict, moving: set[str]) -> tuple[list[dict], set[str]]:
        """Advance bombers one cell. Returns (events, pids that actually moved)."""
        events: list[dict] = []
        moved: set[str] = set()
        bombers = state["bombers"]
        self._clear_passable_bombs(state)

        for pid in moving:
            bomber = bombers.get(pid)
            if not bomber or not bomber.get("alive"):
                continue
            direction = self._resolve_step_direction(state, bomber)
            if direction is None:
                # Face the held direction even when blocked, but do not consume credit.
                desired = self._desired_move_direction(bomber)
                if desired in DIRECTIONS:
                    bomber["direction"] = desired
                    bomber["facing"] = desired
                elif desired == "stop":
                    bomber["direction"] = "stop"
                continue
            dx, dy = DIRECTIONS[direction]
            nx, ny = bomber["x"] + dx, bomber["y"] + dy

            bomb = self._bomb_at(state, nx, ny, grounded_only=True)
            if (
                bomb is not None
                and bomber.get("can_kick")
                and self._can_kick_bomb(state, bomb, direction)
            ):
                events.extend(self._kick_bomb(state, pid, direction, bomb))

            # After a kick the cell should be free; otherwise require walkable.
            if not self._is_walkable(state, bomber, nx, ny):
                continue

            bomber["direction"] = direction
            bomber["x"] = nx
            bomber["y"] = ny
            bomber["facing"] = direction
            # Keep next_direction in sync for perpetual so walls don't strand a "stop".
            if bomber.get("disease") == "perpetual":
                bomber["next_direction"] = direction
            moved.add(pid)
            events.extend(self._pickup_powerup(state, bomber, nx, ny))

            if bomber.get("disease") == "diarrhea":
                events.extend(self._place_bomb(state, pid, bomber))

            if bomber.get("carrying_bomb_id"):
                self._sync_carried_bomb(state, bomber)

        return events, moved

    def _blast_cells_for_bomb(self, state: dict, bomb: dict) -> list[tuple[int, int]]:
        cells = [(bomb["x"], bomb["y"])]
        width = state["grid_width"]
        height = state["grid_height"]
        brange = int(bomb.get("range", 1))
        for dx, dy in DIRECTIONS.values():
            for step in range(1, brange + 1):
                x = bomb["x"] + dx * step
                y = bomb["y"] + dy * step
                if not (0 <= x < width and 0 <= y < height):
                    break
                tile = state["grid"][y][x]
                if tile == TILE_HARD:
                    break
                cells.append((x, y))
                if tile == TILE_SOFT:
                    break
        return cells

    def _detonate(self, state: dict, bomb_ids: set[str]) -> list[dict]:
        """Detonate bombs (with chain reactions). Returns events."""
        events: list[dict] = []
        if not bomb_ids:
            return events

        pending = set(bomb_ids)
        exploded_ids: set[str] = set()
        blast_cells: set[tuple[int, int]] = set()

        while pending:
            bid = pending.pop()
            if bid in exploded_ids:
                continue
            bomb = next((b for b in state.get("bombs") or [] if b["id"] == bid), None)
            if bomb is None:
                continue
            exploded_ids.add(bid)
            cells = self._blast_cells_for_bomb(state, bomb)
            blast_cells.update(cells)
            events.append(
                {
                    "type": "bomb_exploded",
                    "bomb_id": bid,
                    "owner_id": bomb.get("owner_id"),
                    "cells": [{"x": x, "y": y} for x, y in cells],
                }
            )
            # Chain: other bombs in the blast
            for other in state.get("bombs") or []:
                if other["id"] in exploded_ids:
                    continue
                if (other["x"], other["y"]) in blast_cells:
                    pending.add(other["id"])

        # Remove detonated bombs
        state["bombs"] = [
            b for b in state.get("bombs") or [] if b["id"] not in exploded_ids
        ]
        for bomber in state["bombers"].values():
            if bomber.get("carrying_bomb_id") in exploded_ids:
                bomber["carrying_bomb_id"] = None

        # Destroy soft blocks + spawn powerups; wipe powerups in blast
        destroyed_soft: list[tuple[int, int]] = []
        for x, y in blast_cells:
            if state["grid"][y][x] == TILE_SOFT:
                self._set_tile(state, x, y, TILE_EMPTY)
                destroyed_soft.append((x, y))
                events.append({"type": "soft_destroyed", "x": x, "y": y})

        state["powerups"] = [
            p
            for p in state.get("powerups") or []
            if (p["x"], p["y"]) not in blast_cells
        ]
        for x, y in destroyed_soft:
            if random.random() < POWERUP_CHANCE:
                ptype = self._roll_powerup(state)
                state.setdefault("powerups", []).append({"x": x, "y": y, "type": ptype})
                events.append({"type": "powerup_spawned", "x": x, "y": y, "powerup_type": ptype})

        # Add / refresh explosion visuals
        existing = {(e["x"], e["y"]): e for e in state.get("explosions") or []}
        for x, y in blast_cells:
            existing[(x, y)] = {"x": x, "y": y, "ttl": EXPLOSION_TTL}
        state["explosions"] = list(existing.values())

        # Kill bombers standing in blast; attribute to covering bomb owner.
        cell_owners: dict[tuple[int, int], str] = {}
        for ev in events:
            if ev.get("type") != "bomb_exploded":
                continue
            owner = ev.get("owner_id")
            if not owner:
                continue
            for c in ev.get("cells") or []:
                cell_owners.setdefault((c["x"], c["y"]), owner)

        for pid, bomber in state["bombers"].items():
            if not bomber.get("alive"):
                continue
            pos = (bomber["x"], bomber["y"])
            if pos not in blast_cells:
                continue
            killer = cell_owners.get(pos)
            if killer == pid:
                killer = None
            events.extend(
                self._hurt_bomber(state, pid, reason="explosion", by=killer)
            )

        return events

    def _tick_bombs_and_explosions(self, state: dict) -> list[dict]:
        events: list[dict] = []

        # Decay active explosions; kill anyone walking into them
        remaining_explosions: list[dict] = []
        blast_now: set[tuple[int, int]] = set()
        for cell in state.get("explosions") or []:
            ttl = int(cell.get("ttl", 0)) - 1
            if ttl > 0:
                cell = {**cell, "ttl": ttl}
                remaining_explosions.append(cell)
                blast_now.add((cell["x"], cell["y"]))
        state["explosions"] = remaining_explosions

        for pid, bomber in state["bombers"].items():
            if not bomber.get("alive"):
                continue
            if (bomber["x"], bomber["y"]) in blast_now:
                events.extend(
                    self._hurt_bomber(state, pid, reason="explosion", by=None)
                )

        # Keep carried bombs locked to their carriers between moves.
        for bomber in state["bombers"].values():
            if bomber.get("alive") and bomber.get("carrying_bomb_id"):
                self._sync_carried_bomb(state, bomber)

        # Thrown bombs fly toward their landing cell (over walls).
        events.extend(self._tick_sliding_bombs(state))

        # Tick fuses
        to_detonate: set[str] = set()
        for bomb in state.get("bombs") or []:
            bomb["fuse"] = int(bomb.get("fuse", 1)) - 1
            if bomb["fuse"] <= 0:
                to_detonate.add(bomb["id"])

        if to_detonate:
            events.extend(self._detonate(state, to_detonate))

        return events

    def _roll_powerup(self, state: dict) -> str:
        settings = state.get("settings") or {}
        if settings.get("allow_skulls", True):
            return random.choices(POWERUP_TYPES, weights=POWERUP_WEIGHTS, k=1)[0]
        types = [t for t in POWERUP_TYPES if t != "skull"]
        weights = [w for t, w in zip(POWERUP_TYPES, POWERUP_WEIGHTS) if t != "skull"]
        return random.choices(types, weights=weights, k=1)[0]

    def _bomber_controllable(self, bomber: dict) -> bool:
        return (
            bool(bomber.get("alive"))
            and int(bomber.get("respawn_ticks", 0)) <= 0
        )

    def _hurt_bomber(
        self,
        state: dict,
        pid: str,
        *,
        reason: str,
        by: str | None,
    ) -> list[dict]:
        events: list[dict] = []
        bomber = state["bombers"].get(pid)
        if not bomber or not bomber.get("alive"):
            return events
        if int(bomber.get("respawn_ticks", 0)) > 0:
            return events
        if int(bomber.get("invuln_ticks", 0)) > 0:
            return events

        settings = state.get("settings") or {}
        mode = settings.get("game_mode", "classic")

        killer = by
        if killer == pid:
            killer = None
        if killer and killer in state["bombers"]:
            victim_team = bomber.get("team")
            killer_team = state["bombers"][killer].get("team")
            if mode == "team" and victim_team and victim_team == killer_team:
                killer = None
            else:
                state["bombers"][killer]["kills"] = int(
                    state["bombers"][killer].get("kills", 0)
                ) + 1

        self._drop_carried_bomb(state, bomber)
        self._clear_disease(bomber)

        # Kill race: always respawn. Stock/classic: spend a life.
        if mode == "kill_race":
            events.append(
                {
                    "type": "life_lost",
                    "player_id": pid,
                    "reason": reason,
                    "by": killer,
                    "lives": int(bomber.get("lives", 1)),
                }
            )
            events.extend(self._respawn_bomber(state, pid, bomber))
            return events

        lives = int(bomber.get("lives", 1)) - 1
        bomber["lives"] = max(0, lives)
        events.append(
            {
                "type": "life_lost",
                "player_id": pid,
                "reason": reason,
                "by": killer,
                "lives": bomber["lives"],
            }
        )

        if bomber["lives"] <= 0:
            bomber["alive"] = False
            bomber["direction"] = "stop"
            bomber["next_direction"] = "stop"
            events.append(
                {
                    "type": "player_died",
                    "player_id": pid,
                    "reason": reason,
                    "by": killer,
                }
            )
        else:
            events.extend(self._respawn_bomber(state, pid, bomber))
        return events

    def _respawn_bomber(self, state: dict, pid: str, bomber: dict) -> list[dict]:
        sx = int(bomber.get("spawn_x", bomber["x"]))
        sy = int(bomber.get("spawn_y", bomber["y"]))
        bomber["x"] = sx
        bomber["y"] = sy
        bomber["direction"] = "stop"
        bomber["next_direction"] = "stop"
        bomber["facing"] = "down"
        bomber["move_credit"] = 0.0
        bomber["carrying_bomb_id"] = None
        bomber["passable_bomb_ids"] = []
        bomber["respawn_ticks"] = RESPAWN_TICKS
        bomber["invuln_ticks"] = 0
        bomber["alive"] = True
        return [
            {
                "type": "player_respawn",
                "player_id": pid,
                "x": sx,
                "y": sy,
                "delay_ticks": RESPAWN_TICKS,
            }
        ]

    def _tick_respawns(self, state: dict) -> list[dict]:
        events: list[dict] = []
        for pid, bomber in state["bombers"].items():
            if not bomber.get("alive"):
                continue
            respawn = int(bomber.get("respawn_ticks", 0))
            if respawn > 0:
                bomber["respawn_ticks"] = respawn - 1
                if bomber["respawn_ticks"] <= 0:
                    bomber["invuln_ticks"] = INVULN_TICKS
                    events.append(
                        {
                            "type": "player_active",
                            "player_id": pid,
                            "x": bomber["x"],
                            "y": bomber["y"],
                        }
                    )
                continue
            invuln = int(bomber.get("invuln_ticks", 0))
            if invuln > 0:
                bomber["invuln_ticks"] = invuln - 1
        return events

    def _ring_cells(self, width: int, height: int, margin: int) -> list[tuple[int, int]]:
        cells: list[tuple[int, int]] = []
        if margin < 0 or width - 2 * margin < MIN_PLAYABLE_SPAN:
            return cells
        if height - 2 * margin < MIN_PLAYABLE_SPAN:
            return cells
        y0, y1 = margin, height - 1 - margin
        x0, x1 = margin, width - 1 - margin
        for x in range(x0, x1 + 1):
            cells.append((x, y0))
            cells.append((x, y1))
        for y in range(y0 + 1, y1):
            cells.append((x0, y))
            cells.append((x1, y))
        return cells

    def _apply_sudden_death(self, state: dict) -> list[dict]:
        events: list[dict] = []
        start_tick = int(state.get("sudden_death_ticks", 0))
        if start_tick <= 0:
            return events
        playing_tick = int(state.get("playing_tick", 0))
        if playing_tick < start_tick:
            return events

        if not state.get("sudden_death_active"):
            state["sudden_death_active"] = True
            events.append({"type": "sudden_death_started"})

        elapsed = playing_tick - start_tick
        target_level = 1 + elapsed // SUDDEN_DEATH_INTERVAL_TICKS
        current = int(state.get("shrink_level", 0))
        width = int(state["grid_width"])
        height = int(state["grid_height"])

        while current < target_level:
            ring = self._ring_cells(width, height, current)
            if not ring:
                break
            current += 1
            hardened: list[dict] = []
            for x, y in ring:
                if state["grid"][y][x] == TILE_HARD:
                    continue
                self._set_tile(state, x, y, TILE_HARD)
                hardened.append({"x": x, "y": y})
            # Wipe soft drops / bombs / powerups on the new walls.
            hard_set = {(c["x"], c["y"]) for c in hardened}
            if hard_set:
                state["powerups"] = [
                    p
                    for p in state.get("powerups") or []
                    if (p["x"], p["y"]) not in hard_set
                ]
                state["bombs"] = [
                    b
                    for b in state.get("bombs") or []
                    if (b["x"], b["y"]) not in hard_set
                    or b.get("flight") in ("throw", "carried")
                ]
                for pid, bomber in state["bombers"].items():
                    if not bomber.get("alive"):
                        continue
                    if (bomber["x"], bomber["y"]) in hard_set:
                        events.extend(
                            self._hurt_bomber(
                                state, pid, reason="sudden_death", by=None
                            )
                        )
                events.append(
                    {
                        "type": "arena_shrunk",
                        "level": current,
                        "cells": hardened,
                    }
                )
            state["shrink_level"] = current
            if width - 2 * current < MIN_PLAYABLE_SPAN or height - 2 * current < MIN_PLAYABLE_SPAN:
                break
        return events

    def _alive_ids(self, state: dict) -> list[str]:
        return [pid for pid, b in state["bombers"].items() if b.get("alive")]

    def _teams_alive(self, state: dict) -> set[str]:
        teams: set[str] = set()
        for bomber in state["bombers"].values():
            if bomber.get("alive") and bomber.get("team") in TEAMS:
                teams.add(bomber["team"])
        return teams

    def _pick_most_kills(self, state: dict, candidates: list[str] | None = None) -> str:
        pool = candidates if candidates is not None else list(state["bombers"].keys())
        if not pool:
            return next(iter(state["bombers"]))
        scores = {
            pid: int(state["bombers"][pid].get("kills", 0))
            for pid in pool
            if pid in state["bombers"]
        }
        max_kills = max(scores.values()) if scores else 0
        winners = [pid for pid, k in scores.items() if k == max_kills]
        return winners[0] if len(winners) == 1 else random.choice(winners)

    def _finish(
        self,
        state: dict,
        *,
        winner: str | None,
        win_reason: str,
        winning_team: str | None = None,
    ) -> None:
        state["winner"] = winner
        state["winning_team"] = winning_team
        state["win_reason"] = win_reason
        state["phase"] = "finished"

    def _resolve_winner(self, state: dict) -> None:
        settings = state.get("settings") or {}
        mode = settings.get("game_mode", state.get("game_mode", "classic"))

        if mode == "team":
            teams = self._teams_alive(state)
            if len(teams) == 1:
                team = next(iter(teams))
                members = [
                    pid
                    for pid, b in state["bombers"].items()
                    if b.get("team") == team
                ]
                self._finish(
                    state,
                    winner=self._pick_most_kills(state, members),
                    win_reason="team_eliminated",
                    winning_team=team,
                )
                return
            if len(teams) == 0:
                # Everyone wiped — most kills overall, report their team if any.
                winner = self._pick_most_kills(state)
                team = state["bombers"][winner].get("team")
                self._finish(
                    state,
                    winner=winner,
                    win_reason="most_kills",
                    winning_team=team if team in TEAMS else None,
                )
            return

        alive = self._alive_ids(state)
        if len(alive) == 1:
            self._finish(state, winner=alive[0], win_reason="last_standing")
            return
        if len(alive) == 0:
            self._finish(
                state,
                winner=self._pick_most_kills(state),
                win_reason="most_kills",
            )

    def _maybe_finish(self, state: dict) -> bool:
        if state.get("phase") == "finished":
            return True

        settings = state.get("settings") or {}
        mode = settings.get("game_mode", state.get("game_mode", "classic"))
        kill_target = int(state.get("kill_target", settings.get("kill_target", 5)))
        match_ticks = int(state.get("match_ticks", 0))
        playing_tick = int(state.get("playing_tick", 0))

        if mode == "kill_race":
            for pid, bomber in state["bombers"].items():
                if int(bomber.get("kills", 0)) >= kill_target:
                    self._finish(state, winner=pid, win_reason="kill_race")
                    return True
            if match_ticks > 0 and playing_tick >= match_ticks:
                self._finish(
                    state,
                    winner=self._pick_most_kills(state),
                    win_reason="time_up",
                )
                return True
            return False

        if mode == "team":
            if len(self._teams_alive(state)) <= 1:
                self._resolve_winner(state)
                return state.get("phase") == "finished"
            if match_ticks > 0 and playing_tick >= match_ticks:
                # Team with most combined kills (alive preferred).
                team_kills = {"red": 0, "blue": 0}
                for bomber in state["bombers"].values():
                    team = bomber.get("team")
                    if team in team_kills:
                        team_kills[team] += int(bomber.get("kills", 0))
                if team_kills["red"] == team_kills["blue"]:
                    winner = self._pick_most_kills(state)
                    team = state["bombers"][winner].get("team")
                else:
                    team = "red" if team_kills["red"] > team_kills["blue"] else "blue"
                    members = [
                        pid
                        for pid, b in state["bombers"].items()
                        if b.get("team") == team
                    ]
                    winner = self._pick_most_kills(state, members)
                self._finish(
                    state,
                    winner=winner,
                    win_reason="time_up",
                    winning_team=team if team in TEAMS else None,
                )
                return True
            return False

        # Classic / stock (lives baked into alive flag).
        if len(self._alive_ids(state)) <= 1:
            self._resolve_winner(state)
            return state.get("phase") == "finished"

        if match_ticks > 0 and playing_tick >= match_ticks:
            alive = self._alive_ids(state)
            self._finish(
                state,
                winner=self._pick_most_kills(state, alive or None),
                win_reason="time_up",
            )
            return True
        return False

    def tick(self, state: dict) -> tuple[dict, list[dict]]:
        events: list[dict] = []
        # Fresh delta list for this tick's WS payload.
        state["_grid_changes"] = []
        state.pop("_public_bundle", None)

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

        events.extend(self._tick_respawns(state))
        events.extend(self._apply_ai_actions(state))
        events.extend(self._tick_diseases(state))

        # Bombs/explosions first so players can flee this tick's new blasts next frame.
        # Actually classic order: move then bomb tick, or bomb tick then move.
        # We tick bombs first (fuse countdown / explode), then move (so you can walk into fire).
        events.extend(self._tick_bombs_and_explosions(state))

        if state.get("phase") != "finished":
            bombers = state["bombers"]
            for bomber in bombers.values():
                if not self._bomber_controllable(bomber):
                    continue
                bomber["move_credit"] = float(bomber.get("move_credit", 0.0)) + self._move_rate(
                    bomber
                )
                # Cap banking so bumping a wall doesn't store up a multi-cell lunge.
                bomber["move_credit"] = min(float(bomber["move_credit"]), 1.5)

            for _ in range(3):
                moving = {
                    pid
                    for pid, bomber in bombers.items()
                    if self._bomber_controllable(bomber)
                    and float(bomber.get("move_credit", 0.0)) >= 1.0 - 1e-9
                    and self._desired_move_direction(bomber) in DIRECTIONS
                }
                if not moving:
                    break
                step_events, moved = self._step_movement(state, moving)
                events.extend(step_events)
                for pid in moving:
                    if pid in moved:
                        bombers[pid]["move_credit"] = (
                            float(bombers[pid].get("move_credit", 0.0)) - 1.0
                        )
                    else:
                        # Ready to step the instant a path opens — no sticky delay.
                        bombers[pid]["move_credit"] = min(
                            float(bombers[pid].get("move_credit", 0.0)),
                            1.0 - 1e-6,
                        )
                if not moved:
                    break
                # Walking into lingering explosions
                blast_now = {
                    (e["x"], e["y"]) for e in state.get("explosions") or [] if e.get("ttl", 0) > 0
                }
                for pid in moved:
                    bomber = bombers.get(pid)
                    if not bomber or not bomber.get("alive"):
                        continue
                    if (bomber["x"], bomber["y"]) in blast_now:
                        events.extend(
                            self._hurt_bomber(state, pid, reason="explosion", by=None)
                        )

            events.extend(self._spread_diseases(state))
            events.extend(self._apply_sudden_death(state))

        state["playing_tick"] = int(state.get("playing_tick", 0)) + 1

        if self._maybe_finish(state):
            events.append(
                {
                    "type": "game_over",
                    "winner": state["winner"],
                    "winning_team": state.get("winning_team"),
                    "win_reason": state.get("win_reason"),
                }
            )

        state["tick"] += 1
        return state, events

    def get_public_state(self, state: dict, viewer_player: dict | None) -> dict:
        settings = state.get("settings") or {}
        match_ticks = int(state.get("match_ticks", 0))
        playing_tick = int(state.get("playing_tick", 0))
        tick_ms = int(state.get("tick_ms", settings.get("tick_ms", 150)))
        time_remaining_sec = None
        if match_ticks > 0 and state.get("phase") == "playing":
            left = max(0, match_ticks - playing_tick)
            time_remaining_sec = (left * tick_ms) // 1000

        # Full grid on countdown / early ticks / periodic resync; deltas otherwise.
        # Bundle is shared across viewers for the same tick.
        tick = int(state.get("tick", 0))
        need_full = (
            state.get("phase") != "playing"
            or tick <= 1
            or playing_tick % 60 == 0
        )
        bundle = state.get("_public_bundle")
        if not (isinstance(bundle, dict) and bundle.get("tick") == tick and bundle.get("full") == need_full):
            if need_full:
                grid_part = {"grid": state["grid"], "grid_full": True}
            else:
                grid_part = {
                    "grid_delta": list(state.get("_grid_changes") or []),
                    "grid_full": False,
                }
            bundle = {"tick": tick, "full": need_full, "grid_part": grid_part}
            state["_public_bundle"] = bundle
        grid_part = bundle["grid_part"]

        return {
            "phase": state["phase"],
            "countdown_ends_at": state.get("countdown_ends_at"),
            "tick": state["tick"],
            "playing_tick": playing_tick,
            "tick_ms": tick_ms,
            "grid_width": state["grid_width"],
            "grid_height": state["grid_height"],
            **grid_part,
            "map_id": state.get("map_id", settings.get("map_id", "classic")),
            "map_name": state.get("map_name", "Classic"),
            "game_mode": state.get("game_mode", settings.get("game_mode", "classic")),
            "kill_target": int(state.get("kill_target", settings.get("kill_target", 5))),
            "match_ticks": match_ticks,
            "time_remaining_sec": time_remaining_sec,
            "sudden_death_active": bool(state.get("sudden_death_active")),
            "shrink_level": int(state.get("shrink_level", 0)),
            "bombers": state["bombers"],
            "bombs": state.get("bombs") or [],
            "explosions": state.get("explosions") or [],
            "powerups": state.get("powerups") or [],
            "players": state["players"],
            "winner": state.get("winner"),
            "winning_team": state.get("winning_team"),
            "win_reason": state.get("win_reason"),
            "last_action": state.get("last_action"),
            "viewer_id": viewer_player["id"] if viewer_player else None,
        }

    def check_winner(self, state: dict) -> str | None:
        if state.get("phase") == "finished":
            return state.get("winner")
        return None
