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


def _wrap_pos(x: int, y: int, grid_width: int, grid_height: int) -> tuple[int, int]:
    return wrap_pos(x, y, grid_width, grid_height)


def _is_reverse(direction: str, facing: str) -> bool:
    return direction == OPPOSITE.get(facing)


class SnakeEngine(GamePlugin):
    game_type = "snake"

    def default_settings(self) -> dict:
        return {
            "min_players": 2,
            "max_players": 8,
            "grid_width": 30,
            "grid_height": 20,
            "tick_ms": 150,
            "countdown_sec": 3,
            "solo_practice": False,
        }

    def validate_settings(self, settings: dict) -> dict:
        defaults = self.default_settings()
        merged = {**defaults, **(settings or {})}
        merged["min_players"] = max(2, min(8, int(merged.get("min_players", 2))))
        merged["max_players"] = max(merged["min_players"], min(8, int(merged.get("max_players", 8))))
        merged["grid_width"] = max(10, min(50, int(merged.get("grid_width", 30))))
        merged["grid_height"] = max(10, min(40, int(merged.get("grid_height", 20))))
        merged["tick_ms"] = max(100, min(300, int(merged.get("tick_ms", 150))))
        merged["countdown_sec"] = max(1, min(10, int(merged.get("countdown_sec", 3))))
        merged["solo_practice"] = bool(merged.get("solo_practice", False))
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

    def _place_food(self, state: dict) -> list[int] | None:
        grid_width = state["grid_width"]
        grid_height = state["grid_height"]
        occupied = self._occupied_cells(state["snakes"])
        empty = [
            [x, y]
            for x in range(grid_width)
            for y in range(grid_height)
            if (x, y) not in occupied
        ]
        if not empty:
            return None
        return random.choice(empty)

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
            }

        countdown_sec = settings["countdown_sec"]
        countdown_ends_at = (
            datetime.now(timezone.utc) + timedelta(seconds=countdown_sec)
        ).isoformat()

        state = {
            "phase": "countdown",
            "countdown_ends_at": countdown_ends_at,
            "tick": 0,
            "grid_width": grid_width,
            "grid_height": grid_height,
            "food": None,
            "snakes": snakes,
            "players": players,
            "settings": settings,
            "winner": None,
            "win_reason": None,
            "last_action": None,
        }
        state["food"] = self._place_food(state)
        return state

    def _player_by_id(self, state: dict, player_id: str) -> dict | None:
        return next((p for p in state["players"] if p["id"] == player_id), None)

    def apply_action(
        self, state: dict, action: dict, player: dict
    ) -> tuple[dict, list[dict]]:
        action_type = action.get("type")
        events: list[dict] = []

        if action_type != "set_direction":
            return state, events

        if state["phase"] != "playing":
            return state, events

        player_id = player["id"]
        snake = state["snakes"].get(player_id)
        if not snake or not snake.get("alive"):
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

    def _apply_ai_directions(self, state: dict) -> None:
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

    def _alive_snakes(self, state: dict) -> list[str]:
        return [pid for pid, s in state["snakes"].items() if s.get("alive")]

    def _resolve_winner(self, state: dict) -> None:
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

        self._apply_ai_directions(state)

        grid_width = state["grid_width"]
        grid_height = state["grid_height"]
        snakes = state["snakes"]

        new_heads: dict[str, list[int]] = {}
        for pid, snake in snakes.items():
            if not snake.get("alive"):
                continue
            direction = snake["next_direction"]
            if not _is_reverse(direction, snake["direction"]):
                snake["direction"] = direction
            dx, dy = DIRECTIONS[snake["direction"]]
            head = snake["body"][0]
            nx, ny = _wrap_pos(head[0] + dx, head[1] + dy, grid_width, grid_height)
            new_heads[pid] = [nx, ny]

        food = state.get("food")
        will_eat: set[str] = set()
        for pid, new_head in new_heads.items():
            if food and new_head[0] == food[0] and new_head[1] == food[1]:
                will_eat.add(pid)

        body_cells: set[tuple[int, int]] = set()
        for pid, snake in snakes.items():
            if not snake.get("alive"):
                continue
            body = snake["body"]
            limit = len(body) if pid in will_eat else len(body) - 1
            for i in range(limit):
                body_cells.add((body[i][0], body[i][1]))

        died: set[str] = set()
        head_positions: dict[tuple[int, int], list[str]] = {}
        for pid, new_head in new_heads.items():
            key = (new_head[0], new_head[1])
            head_positions.setdefault(key, []).append(pid)

        for pid, new_head in new_heads.items():
            snake = snakes[pid]
            x, y = new_head
            if len(head_positions.get((x, y), [])) > 1:
                snake["alive"] = False
                died.add(pid)
                events.append({"type": "player_died", "player_id": pid, "reason": "head_on"})
                continue
            if (x, y) in body_cells:
                snake["alive"] = False
                died.add(pid)
                events.append({"type": "player_died", "player_id": pid, "reason": "collision"})

        for pid, new_head in new_heads.items():
            snake = snakes[pid]
            if not snake.get("alive"):
                continue
            snake["body"].insert(0, new_head)
            if pid not in will_eat:
                snake["body"].pop()
            else:
                snake["score"] += 1
                events.append({"type": "food_eaten", "player_id": pid})
                state["food"] = self._place_food(state)

        alive = self._alive_snakes(state)
        if len(alive) <= 1:
            self._resolve_winner(state)
            if state.get("winner"):
                events.append({"type": "game_over", "winner": state["winner"]})

        state["tick"] += 1
        return state, events

    def get_public_state(self, state: dict, viewer_player: dict | None) -> dict:
        return {
            "phase": state["phase"],
            "countdown_ends_at": state.get("countdown_ends_at"),
            "tick": state["tick"],
            "grid_width": state["grid_width"],
            "grid_height": state["grid_height"],
            "food": state.get("food"),
            "snakes": state["snakes"],
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
