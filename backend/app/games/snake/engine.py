import random
from datetime import datetime, timedelta, timezone
from typing import Any

from app.games.base import GamePlugin
from app.games.snake.ai import choose_ai_direction, wrap_pos

DIRECTIONS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}

OPPOSITE = {
    "up": "down",
    "down": "up",
    "left": "right",
    "right": "left",
}

SNAKE_COLORS = [
    "#22c55e",
    "#3b82f6",
    "#f59e0b",
    "#ef4444",
    "#a855f7",
    "#06b6d4",
    "#ec4899",
    "#84cc16",
]

INITIAL_LENGTH = 3
FOOD_COUNT = 3
SHOT_TTL = 28  # cells of travel before expiring
SHOT_SPEED = 3  # cells advanced per game tick
SHOT_SCORE_DAMAGE = 1  # score removed from a hit opponent
SHOT_KILL_BONUS = 2
SCORE_TO_WIN = 50
SPEED_TICKS = 45
SPEED_RATES = {
    "normal": 1.0,
    "fast": 2.0,
    "slow": 0.5,
}

# score / grow / ghost_ticks / ammo / spawn weight / optional speed effect
FOOD_DEFS: dict[str, dict] = {
    "apple": {"score": 1, "grow": 1, "ghost_ticks": 0, "ammo": 0, "weight": 32},
    "golden": {"score": 3, "grow": 2, "ghost_ticks": 0, "ammo": 0, "weight": 12},
    "poison": {"score": 1, "grow": -2, "ghost_ticks": 0, "ammo": 0, "weight": 12},
    "ghost": {"score": 1, "grow": 1, "ghost_ticks": 30, "ammo": 0, "weight": 10},
    "ammo": {"score": 1, "grow": 0, "ghost_ticks": 0, "ammo": 2, "weight": 14},
    "turbo": {
        "score": 1,
        "grow": 0,
        "ghost_ticks": 0,
        "ammo": 0,
        "weight": 12,
        "speed_mode": "fast",
        "speed_ticks": SPEED_TICKS,
    },
    "slow": {
        "score": 1,
        "grow": 0,
        "ghost_ticks": 0,
        "ammo": 0,
        "weight": 12,
        "speed_mode": "slow",
        "speed_ticks": SPEED_TICKS,
    },
}

FOOD_TYPES = tuple(FOOD_DEFS.keys())
_FOOD_WEIGHTS = [FOOD_DEFS[t]["weight"] for t in FOOD_TYPES]


def _wrap_pos(x: int, y: int, grid_width: int, grid_height: int) -> tuple[int, int]:
    return wrap_pos(x, y, grid_width, grid_height)


def _is_reverse(direction: str, facing: str) -> bool:
    return direction == OPPOSITE.get(facing)


def _pick_food_type() -> str:
    return random.choices(FOOD_TYPES, weights=_FOOD_WEIGHTS, k=1)[0]


def _food_cells(foods: list[dict] | None) -> set[tuple[int, int]]:
    return {(f["x"], f["y"]) for f in foods or []}


class SnakeEngine(GamePlugin):
    game_type = "snake"

    def default_settings(self) -> dict:
        return {
            "min_players": 2,
            "max_players": 8,
            "grid_width": 48,
            "grid_height": 32,
            "tick_ms": 130,
            "countdown_sec": 3,
            "solo_practice": False,
            "score_to_win": SCORE_TO_WIN,
        }

    def validate_settings(self, settings: dict) -> dict:
        defaults = self.default_settings()
        merged = {**defaults, **(settings or {})}
        merged["min_players"] = max(2, min(8, int(merged.get("min_players", 2))))
        merged["max_players"] = max(merged["min_players"], min(8, int(merged.get("max_players", 8))))
        merged["grid_width"] = max(20, min(64, int(merged.get("grid_width", 48))))
        merged["grid_height"] = max(16, min(48, int(merged.get("grid_height", 32))))
        merged["tick_ms"] = max(80, min(300, int(merged.get("tick_ms", 130))))
        merged["countdown_sec"] = max(1, min(10, int(merged.get("countdown_sec", 3))))
        merged["solo_practice"] = bool(merged.get("solo_practice", False))
        merged["score_to_win"] = max(5, min(200, int(merged.get("score_to_win", SCORE_TO_WIN))))
        return merged

    def tick_interval_ms(self) -> int:
        return 130

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

    def _spawn_configs(self, count: int, grid_width: int, grid_height: int) -> list[dict]:
        """Corner/edge spawns facing inward."""
        corners = [
            {"x": 2, "y": 2, "direction": "right"},
            {"x": grid_width - 3, "y": 2, "direction": "left"},
            {"x": 2, "y": grid_height - 3, "direction": "right"},
            {"x": grid_width - 3, "y": grid_height - 3, "direction": "left"},
            {"x": grid_width // 2, "y": 2, "direction": "down"},
            {"x": grid_width // 2, "y": grid_height - 3, "direction": "up"},
            {"x": 2, "y": grid_height // 2, "direction": "right"},
            {"x": grid_width - 3, "y": grid_height // 2, "direction": "left"},
        ]
        return corners[:count]

    def _build_body(self, x: int, y: int, direction: str, length: int) -> list[list[int]]:
        dx, dy = DIRECTIONS[direction]
        body = []
        for i in range(length):
            body.append([x - dx * i, y - dy * i])
        return body

    def _occupied_cells(self, snakes: dict) -> set[tuple[int, int]]:
        occupied: set[tuple[int, int]] = set()
        for snake in snakes.values():
            for seg in snake["body"]:
                occupied.add((seg[0], seg[1]))
        return occupied

    def _place_one_food(self, state: dict) -> dict | None:
        grid_width = state["grid_width"]
        grid_height = state["grid_height"]
        occupied = self._occupied_cells(state["snakes"])
        occupied |= _food_cells(state.get("foods"))
        empty = [
            (x, y)
            for x in range(grid_width)
            for y in range(grid_height)
            if (x, y) not in occupied
        ]
        if not empty:
            return None
        x, y = random.choice(empty)
        return {"x": x, "y": y, "type": _pick_food_type()}

    def _ensure_foods(self, state: dict, count: int = FOOD_COUNT) -> None:
        foods = list(state.get("foods") or [])
        while len(foods) < count:
            placed = self._place_one_food({**state, "foods": foods})
            if placed is None:
                break
            foods.append(placed)
        state["foods"] = foods

    def create_initial_state(self, players: list[dict], settings: dict) -> dict:
        settings = self.validate_settings(settings)
        grid_width = settings["grid_width"]
        grid_height = settings["grid_height"]
        spawns = self._spawn_configs(len(players), grid_width, grid_height)

        snakes: dict[str, dict] = {}
        for i, player in enumerate(players):
            spawn = spawns[i]
            direction = spawn["direction"]
            body = self._build_body(spawn["x"], spawn["y"], direction, INITIAL_LENGTH)
            snakes[player["id"]] = {
                "body": body,
                "direction": direction,
                "next_direction": direction,
                "alive": True,
                "score": 0,
                "color": SNAKE_COLORS[i % len(SNAKE_COLORS)],
                "pending_grow": 0,
                "ghost_until_tick": -1,
                "ammo": 0,
                "speed_mode": "normal",
                "speed_until_tick": -1,
                "move_credit": 0.0,
            }

        countdown_sec = settings["countdown_sec"]
        countdown_ends_at = (
            datetime.now(timezone.utc) + timedelta(seconds=countdown_sec)
        ).isoformat()

        state = {
            "phase": "countdown",
            "countdown_ends_at": countdown_ends_at,
            "tick": 0,
            "tick_ms": settings["tick_ms"],
            "grid_width": grid_width,
            "grid_height": grid_height,
            "foods": [],
            "projectiles": [],
            "snakes": snakes,
            "players": players,
            "settings": settings,
            "winner": None,
            "win_reason": None,
            "score_to_win": settings["score_to_win"],
            "last_action": None,
        }
        self._ensure_foods(state)
        return state

    def _player_by_id(self, state: dict, player_id: str) -> dict | None:
        return next((p for p in state["players"] if p["id"] == player_id), None)

    def _next_projectile_id(self, state: dict) -> str:
        nid = int(state.get("_projectile_seq", 0)) + 1
        state["_projectile_seq"] = nid
        return f"shot-{nid}"

    def _fire_shot(self, state: dict, player_id: str, snake: dict) -> list[dict]:
        events: list[dict] = []
        if int(snake.get("ammo", 0)) <= 0:
            return events
        direction = snake.get("next_direction", snake["direction"])
        if direction not in DIRECTIONS:
            return events
        head = snake["body"][0]
        dx, dy = DIRECTIONS[direction]
        x, y = _wrap_pos(
            head[0] + dx,
            head[1] + dy,
            state["grid_width"],
            state["grid_height"],
        )
        snake["ammo"] = int(snake["ammo"]) - 1
        projectile = {
            "id": self._next_projectile_id(state),
            "x": x,
            "y": y,
            "direction": direction,
            "owner_id": player_id,
            "ttl": SHOT_TTL,
            "color": snake.get("color", "#fff"),
        }
        state.setdefault("projectiles", []).append(projectile)
        state["last_action"] = {"type": "shoot", "player_id": player_id}
        events.append(
            {
                "type": "shot_fired",
                "player_id": player_id,
                "projectile_id": projectile["id"],
                "x": x,
                "y": y,
                "direction": direction,
            }
        )
        # Immediate hit if something already occupies the spawn cell.
        hit_events = self._apply_projectile_hits(state, only_ids={projectile["id"]})
        events.extend(hit_events)
        return events

    def _damage_snake_score(
        self, state: dict, target_id: str, amount: int, shooter_id: str | None
    ) -> list[dict]:
        events: list[dict] = []
        snake = state["snakes"].get(target_id)
        if not snake or not snake.get("alive"):
            return events

        snake["score"] = int(snake.get("score", 0)) - max(0, amount)
        events.append(
            {
                "type": "snake_hit",
                "player_id": target_id,
                "by": shooter_id,
                "score": snake["score"],
                "damage": amount,
            }
        )

        if snake["score"] < 0:
            snake["alive"] = False
            events.append(
                {
                    "type": "player_died",
                    "player_id": target_id,
                    "reason": "shot",
                    "by": shooter_id,
                }
            )
            if shooter_id and shooter_id in state["snakes"]:
                state["snakes"][shooter_id]["score"] = (
                    state["snakes"][shooter_id].get("score", 0) + SHOT_KILL_BONUS
                )
        return events

    def _segment_owner_at(self, state: dict, x: int, y: int) -> str | None:
        for pid, snake in state["snakes"].items():
            if not snake.get("alive"):
                continue
            for seg in snake["body"]:
                if seg[0] == x and seg[1] == y:
                    return pid
        return None

    def _apply_projectile_hits(
        self, state: dict, only_ids: set[str] | None = None
    ) -> list[dict]:
        events: list[dict] = []
        remaining: list[dict] = []
        for proj in state.get("projectiles") or []:
            if only_ids is not None and proj["id"] not in only_ids:
                remaining.append(proj)
                continue
            owner = proj.get("owner_id")
            victim = self._segment_owner_at(state, proj["x"], proj["y"])
            if victim is not None and victim != owner:
                events.extend(
                    self._damage_snake_score(state, victim, SHOT_SCORE_DAMAGE, owner)
                )
                events.append(
                    {
                        "type": "projectile_hit",
                        "projectile_id": proj["id"],
                        "player_id": victim,
                        "by": owner,
                        "x": proj["x"],
                        "y": proj["y"],
                    }
                )
                continue
            remaining.append(proj)
        state["projectiles"] = remaining
        return events

    def _advance_projectiles(self, state: dict) -> list[dict]:
        events: list[dict] = []
        grid_width = state["grid_width"]
        grid_height = state["grid_height"]
        surviving: list[dict] = []

        for proj in state.get("projectiles") or []:
            direction = proj.get("direction")
            if direction not in DIRECTIONS:
                continue
            dx, dy = DIRECTIONS[direction]
            hit = False
            for _ in range(SHOT_SPEED):
                proj["x"], proj["y"] = _wrap_pos(
                    proj["x"] + dx, proj["y"] + dy, grid_width, grid_height
                )
                proj["ttl"] = int(proj.get("ttl", 1)) - 1
                if proj["ttl"] <= 0:
                    events.append(
                        {
                            "type": "projectile_expired",
                            "projectile_id": proj["id"],
                        }
                    )
                    hit = True
                    break

                owner = proj.get("owner_id")
                victim = self._segment_owner_at(state, proj["x"], proj["y"])
                if victim is not None and victim != owner:
                    events.extend(
                        self._damage_snake_score(
                            state, victim, SHOT_SCORE_DAMAGE, owner
                        )
                    )
                    events.append(
                        {
                            "type": "projectile_hit",
                            "projectile_id": proj["id"],
                            "player_id": victim,
                            "by": owner,
                            "x": proj["x"],
                            "y": proj["y"],
                        }
                    )
                    hit = True
                    break

            if not hit:
                surviving.append(proj)

        state["projectiles"] = surviving
        return events

    def apply_action(
        self, state: dict, action: dict, player: dict
    ) -> tuple[dict, list[dict]]:
        action_type = action.get("type")
        events: list[dict] = []

        if state["phase"] != "playing":
            return state, events

        player_id = player["id"]
        snake = state["snakes"].get(player_id)
        if not snake or not snake.get("alive"):
            return state, events

        if action_type == "shoot":
            events.extend(self._fire_shot(state, player_id, snake))
            if self._maybe_finish(state):
                events.append({"type": "game_over", "winner": state["winner"]})
            return state, events

        if action_type != "set_direction":
            return state, events

        direction = action.get("direction")
        if direction not in DIRECTIONS:
            return state, events

        facing = snake.get("next_direction", snake["direction"])
        if _is_reverse(direction, facing):
            return state, events

        snake["next_direction"] = direction
        state["last_action"] = {"type": "set_direction", "player_id": player_id, "direction": direction}
        return state, events

    def _apply_ai_actions(self, state: dict) -> list[dict]:
        from app.games.snake.ai import choose_ai_shoot

        events: list[dict] = []
        for player in state["players"]:
            if not player.get("is_ai"):
                continue
            pid = player["id"]
            snake = state["snakes"].get(pid)
            if not snake or not snake.get("alive"):
                continue
            direction = choose_ai_direction(state, pid, snake)
            facing = snake.get("next_direction", snake["direction"])
            if not _is_reverse(direction, facing):
                snake["next_direction"] = direction
            if choose_ai_shoot(state, pid, snake):
                events.extend(self._fire_shot(state, pid, snake))
        return events

    def _alive_snakes(self, state: dict) -> list[str]:
        return [pid for pid, s in state["snakes"].items() if s.get("alive")]

    def _score_to_win(self, state: dict) -> int:
        settings = state.get("settings") or {}
        return int(state.get("score_to_win") or settings.get("score_to_win") or SCORE_TO_WIN)

    def _check_score_victory(self, state: dict) -> bool:
        """First alive snake to reach score_to_win wins."""
        target = self._score_to_win(state)
        contenders = [
            (pid, int(s.get("score", 0)))
            for pid, s in state["snakes"].items()
            if s.get("alive") and int(s.get("score", 0)) >= target
        ]
        if not contenders:
            return False
        max_score = max(sc for _, sc in contenders)
        winners = [pid for pid, sc in contenders if sc == max_score]
        state["winner"] = winners[0] if len(winners) == 1 else random.choice(winners)
        state["win_reason"] = "score_limit"
        state["phase"] = "finished"
        return True

    def _resolve_winner(self, state: dict) -> None:
        if self._check_score_victory(state):
            return

        alive = self._alive_snakes(state)
        if len(alive) == 1:
            state["winner"] = alive[0]
            state["win_reason"] = "last_standing"
            state["phase"] = "finished"
            return

        if len(alive) == 0:
            scores = {pid: state["snakes"][pid]["score"] for pid in state["snakes"]}
            max_score = max(scores.values())
            winners = [pid for pid, sc in scores.items() if sc == max_score]
            state["winner"] = winners[0] if len(winners) == 1 else random.choice(winners)
            state["win_reason"] = "highest_score"
            state["phase"] = "finished"

    def _maybe_finish(self, state: dict) -> bool:
        """End the match on score limit or last standing. Returns True if finished."""
        if state.get("phase") == "finished":
            return True
        if self._check_score_victory(state):
            return True
        alive = self._alive_snakes(state)
        if len(alive) <= 1:
            self._resolve_winner(state)
            return state.get("phase") == "finished"
        return False

    def _active_speed_mode(self, snake: dict, tick_now: int) -> str:
        until = int(snake.get("speed_until_tick", -1))
        mode = snake.get("speed_mode") or "normal"
        if until >= tick_now and mode in SPEED_RATES:
            return mode
        return "normal"

    def _apply_food_effects(
        self, snake: dict, food_item: dict, tick_now: int
    ) -> tuple[int, str]:
        """Apply non-growth food effects. Returns (grow, food_type)."""
        ftype = food_item.get("type", "apple")
        defs = FOOD_DEFS.get(ftype, FOOD_DEFS["apple"])
        grow = int(defs["grow"])
        snake["score"] = max(0, int(snake.get("score", 0)) + int(defs["score"]))
        ghost_ticks = int(defs.get("ghost_ticks", 0))
        if ghost_ticks > 0:
            snake["ghost_until_tick"] = max(
                snake.get("ghost_until_tick", -1),
                tick_now + ghost_ticks,
            )
        ammo_gain = int(defs.get("ammo", 0))
        if ammo_gain > 0:
            snake["ammo"] = int(snake.get("ammo", 0)) + ammo_gain
        speed_mode = defs.get("speed_mode")
        speed_ticks = int(defs.get("speed_ticks", 0))
        if speed_mode in SPEED_RATES and speed_ticks > 0:
            snake["speed_mode"] = speed_mode
            snake["speed_until_tick"] = tick_now + speed_ticks
        return grow, ftype

    def _step_movement(self, state: dict, moving: set[str]) -> list[dict]:
        """Advance the given snakes by one cell and resolve collisions/food."""
        events: list[dict] = []
        if not moving:
            return events

        grid_width = state["grid_width"]
        grid_height = state["grid_height"]
        snakes = state["snakes"]
        tick_now = state["tick"]

        new_heads: dict[str, list[int]] = {}
        for pid in moving:
            snake = snakes.get(pid)
            if not snake or not snake.get("alive"):
                continue
            direction = snake["next_direction"]
            if not _is_reverse(direction, snake["direction"]):
                snake["direction"] = direction
            dx, dy = DIRECTIONS[snake["direction"]]
            head = snake["body"][0]
            nx, ny = _wrap_pos(head[0] + dx, head[1] + dy, grid_width, grid_height)
            new_heads[pid] = [nx, ny]

        if not new_heads:
            return events

        food_by_cell: dict[tuple[int, int], dict] = {
            (f["x"], f["y"]): f for f in state.get("foods") or []
        }
        will_eat: dict[str, dict] = {}
        for pid, new_head in new_heads.items():
            food_item = food_by_cell.get((new_head[0], new_head[1]))
            if food_item is not None:
                will_eat[pid] = food_item

        body_cells_by_owner: dict[str, set[tuple[int, int]]] = {}
        all_body_cells: set[tuple[int, int]] = set()
        for pid, snake in snakes.items():
            if not snake.get("alive"):
                continue
            body = snake["body"]
            keeps_tail = True
            if pid in new_heads:
                keeps_tail = snake.get("pending_grow", 0) > 0
                if pid in will_eat:
                    ftype = will_eat[pid].get("type", "apple")
                    if FOOD_DEFS.get(ftype, {}).get("grow", 1) > 0:
                        keeps_tail = True
            limit = len(body) if keeps_tail else len(body) - 1
            cells = {(body[i][0], body[i][1]) for i in range(max(0, limit))}
            body_cells_by_owner[pid] = cells
            all_body_cells |= cells

        head_positions: dict[tuple[int, int], list[str]] = {}
        for pid, new_head in new_heads.items():
            key = (new_head[0], new_head[1])
            head_positions.setdefault(key, []).append(pid)

        for pid, new_head in new_heads.items():
            snake = snakes[pid]
            x, y = new_head
            if len(head_positions.get((x, y), [])) > 1:
                snake["alive"] = False
                events.append({"type": "player_died", "player_id": pid, "reason": "head_on"})
                continue

            is_ghost = snake.get("ghost_until_tick", -1) >= tick_now
            if is_ghost:
                foreign = all_body_cells - body_cells_by_owner.get(pid, set())
                hit = (x, y) in foreign
            else:
                hit = (x, y) in all_body_cells
            if hit:
                snake["alive"] = False
                events.append({"type": "player_died", "player_id": pid, "reason": "collision"})

        eaten_keys: set[tuple[int, int]] = set()
        for pid, new_head in new_heads.items():
            snake = snakes[pid]
            if not snake.get("alive"):
                continue
            snake["body"].insert(0, new_head)

            grow = 0
            food_item = will_eat.get(pid)
            if food_item is not None:
                grow, ftype = self._apply_food_effects(snake, food_item, tick_now)
                eaten_keys.add((food_item["x"], food_item["y"]))
                events.append(
                    {
                        "type": "food_eaten",
                        "player_id": pid,
                        "food_type": ftype,
                        "x": food_item["x"],
                        "y": food_item["y"],
                    }
                )

            if grow > 0:
                snake["pending_grow"] = snake.get("pending_grow", 0) + grow

            if snake.get("pending_grow", 0) > 0:
                snake["pending_grow"] -= 1
            else:
                snake["body"].pop()
                if grow < 0:
                    for _ in range(-grow):
                        if len(snake["body"]) > INITIAL_LENGTH:
                            snake["body"].pop()

        if eaten_keys:
            state["foods"] = [
                f
                for f in (state.get("foods") or [])
                if (f["x"], f["y"]) not in eaten_keys
            ]
            self._ensure_foods(state)

        return events

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

        if state["phase"] == "finished":
            state["tick"] += 1
            return state, events

        tick_now = state["tick"]
        snakes = state["snakes"]

        for snake in snakes.values():
            if not snake.get("alive"):
                continue
            mode = self._active_speed_mode(snake, tick_now)
            rate = SPEED_RATES.get(mode, 1.0)
            snake["move_credit"] = float(snake.get("move_credit", 0.0)) + rate
            if int(snake.get("speed_until_tick", -1)) < tick_now:
                snake["speed_mode"] = "normal"

        # Up to 2 substeps so fast snakes can move twice; slow snakes bank credit.
        for _ in range(2):
            moving = {
                pid
                for pid, snake in snakes.items()
                if snake.get("alive")
                and float(snake.get("move_credit", 0.0)) >= 1.0 - 1e-9
            }
            if not moving:
                break
            for pid in moving:
                snakes[pid]["move_credit"] = (
                    float(snakes[pid].get("move_credit", 0.0)) - 1.0
                )
            events.extend(self._step_movement(state, moving))
            if state.get("phase") == "finished":
                break

        if state.get("phase") != "finished":
            events.extend(self._advance_projectiles(state))

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
            "tick_ms": state.get("tick_ms", settings.get("tick_ms", 130)),
            "grid_width": state["grid_width"],
            "grid_height": state["grid_height"],
            "foods": state.get("foods") or [],
            "projectiles": state.get("projectiles") or [],
            "snakes": state["snakes"],
            "players": state["players"],
            "winner": state.get("winner"),
            "win_reason": state.get("win_reason"),
            "score_to_win": self._score_to_win(state),
            "last_action": state.get("last_action"),
            "viewer_id": viewer_player["id"] if viewer_player else None,
        }

    def check_winner(self, state: dict) -> str | None:
        if state.get("phase") == "finished":
            return state.get("winner")
        return None
