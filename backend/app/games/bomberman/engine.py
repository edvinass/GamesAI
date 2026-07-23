"""Classic Bomberman — shared arena, bombs, soft blocks, last bomber standing."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from app.games.base import GamePlugin
from app.games.bomberman.ai import choose_ai_action
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


class BombermanEngine(GamePlugin):
    game_type = "bomberman"

    def default_settings(self) -> dict:
        return {
            "min_players": 2,
            "max_players": 8,
            "map_id": "classic",
            "available_maps": list_maps(),
            "grid_width": 15,
            "grid_height": 13,
            "tick_ms": 150,
            "countdown_sec": 3,
            "solo_practice": False,
            "soft_fill": SOFT_FILL,
        }

    def validate_settings(self, settings: dict) -> dict:
        defaults = self.default_settings()
        merged = {**defaults, **(settings or {})}
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
        if "soft_fill" in (settings or {}):
            merged["soft_fill"] = max(0.2, min(0.85, float(merged.get("soft_fill", default_fill))))
        else:
            merged["soft_fill"] = default_fill
        return merged

    def tick_interval_ms(self) -> int:
        return 150

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
        return None

    def create_initial_state(self, players: list[dict], settings: dict) -> dict:
        settings = self.validate_settings(settings)
        grid, spawn_pool, map_meta = build_map_grid(
            settings["map_id"], soft_fill=settings["soft_fill"]
        )
        width = len(grid[0])
        height = len(grid)
        spawns = spawn_pool[: len(players)]

        bombers: dict[str, dict] = {}
        for i, player in enumerate(players):
            sx, sy = spawns[i]
            is_ai = bool(player.get("is_ai"))
            bombers[player["id"]] = {
                "x": sx,
                "y": sy,
                "direction": "stop",
                "next_direction": "stop",
                "facing": "down",
                "alive": True,
                "color": BOMBER_COLORS[i % len(BOMBER_COLORS)],
                # AI seats get a mild head start so they stay competitive.
                "max_bombs": 2 if is_ai else 1,
                "bomb_range": 2 if is_ai else 1,
                "speed_level": 1 if is_ai else 0,
                "can_throw": False,
                "can_kick": False,
                "carrying_bomb_id": None,
                "move_credit": 0.0,
                "kills": 0,
                "passable_bomb_ids": [],
                "disease": None,
                "disease_ticks": 0,
            }

        countdown_sec = settings["countdown_sec"]
        countdown_ends_at = (
            datetime.now(timezone.utc) + timedelta(seconds=countdown_sec)
        ).isoformat()

        return {
            "phase": "countdown",
            "countdown_ends_at": countdown_ends_at,
            "tick": 0,
            "tick_ms": settings["tick_ms"],
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
            "winner": None,
            "win_reason": None,
            "last_action": None,
            "_bomb_seq": 0,
        }

    def _next_bomb_id(self, state: dict) -> str:
        nid = int(state.get("_bomb_seq", 0)) + 1
        state["_bomb_seq"] = nid
        return f"bomb-{nid}"

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
        if not bomber.get("alive"):
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
        if not bomber or not bomber.get("alive"):
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
            if b.get("alive")
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
        for player in state["players"]:
            if not player.get("is_ai"):
                continue
            pid = player["id"]
            bomber = state["bombers"].get(pid)
            if not bomber or not bomber.get("alive"):
                continue
            direction, place = choose_ai_action(state, pid, bomber)
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
                state["grid"][y][x] = TILE_EMPTY
                destroyed_soft.append((x, y))
                events.append({"type": "soft_destroyed", "x": x, "y": y})

        state["powerups"] = [
            p
            for p in state.get("powerups") or []
            if (p["x"], p["y"]) not in blast_cells
        ]
        for x, y in destroyed_soft:
            if random.random() < POWERUP_CHANCE:
                ptype = random.choices(POWERUP_TYPES, weights=POWERUP_WEIGHTS, k=1)[0]
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
            self._drop_carried_bomb(state, bomber)
            bomber["alive"] = False
            killer = cell_owners.get(pos)
            if killer == pid:
                killer = None
            if killer and killer in state["bombers"]:
                state["bombers"][killer]["kills"] = int(
                    state["bombers"][killer].get("kills", 0)
                ) + 1
            events.append(
                {
                    "type": "player_died",
                    "player_id": pid,
                    "reason": "explosion",
                    "by": killer,
                }
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
                self._drop_carried_bomb(state, bomber)
                bomber["alive"] = False
                events.append(
                    {
                        "type": "player_died",
                        "player_id": pid,
                        "reason": "explosion",
                        "by": None,
                    }
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

    def _alive_ids(self, state: dict) -> list[str]:
        return [pid for pid, b in state["bombers"].items() if b.get("alive")]

    def _resolve_winner(self, state: dict) -> None:
        alive = self._alive_ids(state)
        if len(alive) == 1:
            state["winner"] = alive[0]
            state["win_reason"] = "last_standing"
            state["phase"] = "finished"
            return
        if len(alive) == 0:
            # Most kills, then arbitrary
            scores = {
                pid: int(b.get("kills", 0)) for pid, b in state["bombers"].items()
            }
            max_kills = max(scores.values()) if scores else 0
            winners = [pid for pid, k in scores.items() if k == max_kills]
            state["winner"] = winners[0] if len(winners) == 1 else random.choice(winners)
            state["win_reason"] = "most_kills"
            state["phase"] = "finished"

    def _maybe_finish(self, state: dict) -> bool:
        if state.get("phase") == "finished":
            return True
        if len(self._alive_ids(state)) <= 1:
            self._resolve_winner(state)
            return state.get("phase") == "finished"
        return False

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

        events.extend(self._apply_ai_actions(state))
        events.extend(self._tick_diseases(state))

        # Bombs/explosions first so players can flee this tick's new blasts next frame.
        # Actually classic order: move then bomb tick, or bomb tick then move.
        # We tick bombs first (fuse countdown / explode), then move (so you can walk into fire).
        events.extend(self._tick_bombs_and_explosions(state))

        if state.get("phase") != "finished":
            bombers = state["bombers"]
            for bomber in bombers.values():
                if not bomber.get("alive"):
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
                    if bomber.get("alive")
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
                        self._drop_carried_bomb(state, bomber)
                        bomber["alive"] = False
                        events.append(
                            {
                                "type": "player_died",
                                "player_id": pid,
                                "reason": "explosion",
                                "by": None,
                            }
                        )

            events.extend(self._spread_diseases(state))

        if self._maybe_finish(state):
            events.append({"type": "game_over", "winner": state["winner"]})

        state["tick"] += 1
        return state, events

    def get_public_state(self, state: dict, viewer_player: dict | None) -> dict:
        settings = state.get("settings") or {}
        return {
            "phase": state["phase"],
            "countdown_ends_at": state.get("countdown_ends_at"),
            "tick": state["tick"],
            "tick_ms": state.get("tick_ms", settings.get("tick_ms", 150)),
            "grid_width": state["grid_width"],
            "grid_height": state["grid_height"],
            "grid": state["grid"],
            "map_id": state.get("map_id", settings.get("map_id", "classic")),
            "map_name": state.get("map_name", "Classic"),
            "bombers": state["bombers"],
            "bombs": state.get("bombs") or [],
            "explosions": state.get("explosions") or [],
            "powerups": state.get("powerups") or [],
            "players": state["players"],
            "winner": state.get("winner"),
            "win_reason": state.get("win_reason"),
            "last_action": state.get("last_action"),
            "viewer_id": viewer_player["id"] if viewer_player else None,
        }

    def check_winner(self, state: dict) -> str | None:
        if state.get("phase") == "finished":
            return state.get("winner")
        return None
