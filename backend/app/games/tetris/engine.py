import random
from datetime import datetime, timedelta, timezone
from typing import Any

from app.games.base import GamePlugin
from app.games.tetris.ai import choose_ai_actions, get_ai_config, normalize_ai_difficulty
from app.games.tetris.pieces import (
    PIECE_COLORS,
    PIECE_SHAPES,
    SPAWN_X,
    SPAWN_Y,
    piece_cells,
)

PLAYER_COLORS = [
    "#22c55e",
    "#3b82f6",
    "#f59e0b",
    "#ef4444",
]

LOCK_DELAY_TICKS = 10
LINES_PER_LEVEL = 10


def _empty_grid(width: int, height: int) -> list[list[str | None]]:
    return [[None for _ in range(width)] for _ in range(height)]


def _level_from_lines(lines: int) -> int:
    return 1 + lines // LINES_PER_LEVEL


def _drop_interval_ticks(level: int, base: int) -> int:
    """NES-style acceleration: faster drop each level."""
    return max(2, int(base * (0.85 ** (level - 1))))


class TetrisEngine(GamePlugin):
    game_type = "tetris"

    def default_settings(self) -> dict:
        return {
            "min_players": 2,
            "max_players": 4,
            "board_width": 10,
            "board_height": 20,
            "tick_ms": 50,
            "base_drop_ticks": 20,
            "countdown_sec": 3,
            "solo_practice": False,
            "single_player": False,
            "ai_difficulties": {},
            "solo_ai_difficulties": ["normal", "normal"],
        }

    def validate_settings(self, settings: dict) -> dict:
        defaults = self.default_settings()
        merged = {**defaults, **(settings or {})}
        merged["min_players"] = max(2, min(4, int(merged.get("min_players", 2))))
        merged["max_players"] = max(merged["min_players"], min(4, int(merged.get("max_players", 4))))
        merged["board_width"] = 10
        merged["board_height"] = 20
        merged["tick_ms"] = max(40, min(100, int(merged.get("tick_ms", 50))))
        merged["base_drop_ticks"] = max(10, min(40, int(merged.get("base_drop_ticks", 20))))
        merged["countdown_sec"] = max(1, min(10, int(merged.get("countdown_sec", 3))))
        merged["solo_practice"] = bool(merged.get("solo_practice", False))
        merged["single_player"] = bool(merged.get("single_player", False))
        if merged["single_player"]:
            merged["solo_practice"] = False
        raw_difficulties = merged.get("ai_difficulties") or {}
        merged["ai_difficulties"] = {
            str(player_id): normalize_ai_difficulty(level)
            for player_id, level in raw_difficulties.items()
        }
        solo_defaults = list(merged.get("solo_ai_difficulties") or ["normal", "normal"])
        while len(solo_defaults) < 2:
            solo_defaults.append("normal")
        merged["solo_ai_difficulties"] = [
            normalize_ai_difficulty(level) for level in solo_defaults[:2]
        ]
        return merged

    def assign_lobby_roles(self, players: list[dict], settings: dict) -> list[dict]:
        difficulties = settings.get("ai_difficulties") or {}
        for player in players:
            if player.get("is_ai"):
                player["ai_difficulty"] = difficulties.get(player["id"], "normal")
        return players

    def tick_interval_ms(self) -> int:
        return 50

    def validate_lobby(self, players: list[dict], settings: dict) -> str | None:
        settings = self.validate_settings(settings)
        if settings.get("single_player"):
            humans = [p for p in players if not p.get("is_ai")]
            if len(humans) != 1:
                return "Single player requires exactly one human player"
            if any(p.get("is_ai") for p in players):
                return "Remove AI players for single player mode"
            return None

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

    def _next_piece(self, board: dict) -> str:
        if not board.get("bag"):
            board["bag"] = []
        if not board["bag"]:
            bag = list(PIECE_SHAPES.keys())
            random.shuffle(bag)
            board["bag"] = bag
        return board["bag"].pop()

    def _take_next_piece(self, board: dict) -> str:
        queue = board.setdefault("next_queue", [])
        if not queue:
            queue.append(self._next_piece(board))
        piece_type = queue.pop(0)
        queue.append(self._next_piece(board))
        return piece_type

    def _spawn_piece(self, board: dict, width: int, height: int) -> dict | None:
        piece_type = self._take_next_piece(board)
        active = {
            "type": piece_type,
            "rotation": 0,
            "x": SPAWN_X,
            "y": SPAWN_Y,
        }
        cells = piece_cells(piece_type, 0, SPAWN_X, SPAWN_Y)
        if not self._cells_valid(board, cells, width, height):
            return None
        board["active"] = active
        board["ai_has_plan"] = False
        board["ai_next_action_tick"] = 0
        return active

    def _create_board(self, player_index: int, width: int, height: int) -> dict:
        return {
            "grid": _empty_grid(width, height),
            "active": None,
            "next_queue": [],
            "bag": [],
            "width": width,
            "height": height,
            "alive": True,
            "lines_cleared": 0,
            "level": 1,
            "drop_counter": 0,
            "lock_counter": 0,
            "input_queue": [],
            "ai_last_plan_tick": -999,
            "ai_next_action_tick": 0,
            "ai_has_plan": False,
            "color": PLAYER_COLORS[player_index % len(PLAYER_COLORS)],
        }

    def create_initial_state(self, players: list[dict], settings: dict) -> dict:
        settings = self.validate_settings(settings)
        width = settings["board_width"]
        height = settings["board_height"]

        boards: dict[str, dict] = {}
        for i, player in enumerate(players):
            board = self._create_board(i, width, height)
            board["next_queue"] = [self._next_piece(board), self._next_piece(board)]
            self._spawn_piece(board, width, height)
            boards[player["id"]] = board

        countdown_sec = settings["countdown_sec"]
        countdown_ends_at = (
            datetime.now(timezone.utc) + timedelta(seconds=countdown_sec)
        ).isoformat()

        return {
            "phase": "countdown",
            "countdown_ends_at": countdown_ends_at,
            "tick": 0,
            "board_width": width,
            "board_height": height,
            "boards": boards,
            "players": players,
            "settings": settings,
            "winner": None,
            "win_reason": None,
            "last_action": None,
            "game_started_at_tick": None,
        }

    def _cells_valid(
        self,
        board: dict,
        cells: list[tuple[int, int]],
        width: int,
        height: int,
    ) -> bool:
        grid = board["grid"]
        for x, y in cells:
            if x < 0 or x >= width or y >= height:
                return False
            if y >= 0 and grid[y][x] is not None:
                return False
        return True

    def _active_cells(self, board: dict) -> list[tuple[int, int]]:
        active = board.get("active")
        if not active:
            return []
        return piece_cells(active["type"], active["rotation"], active["x"], active["y"])

    def _try_move(self, board: dict, dx: int, dy: int, width: int, height: int) -> bool:
        active = board.get("active")
        if not active:
            return False
        cells = piece_cells(active["type"], active["rotation"], active["x"] + dx, active["y"] + dy)
        if self._cells_valid(board, cells, width, height):
            active["x"] += dx
            active["y"] += dy
            return True
        return False

    def _try_rotate(self, board: dict, direction: str, width: int, height: int) -> bool:
        active = board.get("active")
        if not active:
            return False
        delta = 1 if direction == "cw" else -1
        new_rot = (active["rotation"] + delta) % 4
        for kick_x in (0, -1, 1, -2, 2):
            cells = piece_cells(active["type"], new_rot, active["x"] + kick_x, active["y"])
            if self._cells_valid(board, cells, width, height):
                active["rotation"] = new_rot
                active["x"] += kick_x
                return True
        return False

    def _lock_piece(self, board: dict, width: int, height: int) -> int:
        active = board["active"]
        if not active:
            return 0

        piece_type = active["type"]
        color = PIECE_COLORS[piece_type]
        cells = self._active_cells(board)
        grid = board["grid"]
        for x, y in cells:
            if y >= 0:
                grid[y][x] = color

        cleared_rows = []
        for y in range(height):
            if all(grid[y][x] is not None for x in range(width)):
                cleared_rows.append(y)

        for y in sorted(cleared_rows, reverse=True):
            del grid[y]
            grid.insert(0, [None] * width)

        lines = len(cleared_rows)
        board["lines_cleared"] += lines
        board["level"] = _level_from_lines(board["lines_cleared"])
        board["active"] = None
        board["lock_counter"] = 0
        return lines

    def _spawn_or_eliminate(self, board: dict, width: int, height: int) -> bool:
        if not board.get("alive"):
            return False
        if board.get("active"):
            return True
        spawned = self._spawn_piece(board, width, height)
        if spawned is None:
            board["alive"] = False
            return False
        return True

    def apply_action(
        self, state: dict, action: dict, player: dict
    ) -> tuple[dict, list[dict]]:
        events: list[dict] = []
        action_type = action.get("type")

        if state["phase"] != "playing":
            return state, events

        player_id = player["id"]
        board = state["boards"].get(player_id)
        if not board or not board.get("alive"):
            return state, events

        if action_type in ("move", "rotate", "hard_drop"):
            board["input_queue"].append(action)
            state["last_action"] = {"type": action_type, "player_id": player_id, **action}
        return state, events

    def _process_input(self, board: dict, action: dict, width: int, height: int) -> bool:
        """Process one queued input. Returns True if lock delay should reset."""
        action_type = action.get("type")
        if action_type == "move":
            direction = action.get("direction")
            dx, dy = {"left": (-1, 0), "right": (1, 0), "down": (0, 1)}.get(direction, (0, 0))
            return self._try_move(board, dx, dy, width, height)
        if action_type == "rotate":
            return self._try_rotate(board, action.get("direction", "cw"), width, height)
        if action_type == "hard_drop":
            while self._try_move(board, 0, 1, width, height):
                pass
            return False
        return False

    def _apply_ai_inputs(self, state: dict) -> None:
        width = state["board_width"]
        height = state["board_height"]
        tick = state["tick"]
        for player in state["players"]:
            if not player.get("is_ai"):
                continue
            board = state["boards"].get(player["id"])
            if not board or not board.get("alive") or not board.get("active"):
                continue
            if board["input_queue"]:
                continue
            if board.get("ai_has_plan"):
                continue

            difficulty = player.get("ai_difficulty", "normal")
            cfg = get_ai_config(difficulty)
            think_ticks = int(cfg["think_ticks"])
            if tick - board.get("ai_last_plan_tick", -999) < think_ticks:
                continue

            board["ai_last_plan_tick"] = tick
            board["ai_has_plan"] = True
            for action in choose_ai_actions(board, width, height, difficulty):
                board["input_queue"].append(action)

    def _tick_board(
        self,
        board: dict,
        width: int,
        height: int,
        base_drop: int,
        tick: int = 0,
        max_inputs_per_tick: int | None = None,
        action_delay_ticks: int | None = None,
    ) -> list[dict]:
        events: list[dict] = []
        if not board.get("alive"):
            return events

        if not board.get("active"):
            if not self._spawn_or_eliminate(board, width, height):
                events.append({"type": "player_eliminated", "reason": "topped_out"})
            return events

        can_process_ai = (
            action_delay_ticks is None or tick >= board.get("ai_next_action_tick", 0)
        )
        inputs_processed = 0
        input_limit = max_inputs_per_tick if max_inputs_per_tick is not None else 999

        while board["input_queue"] and can_process_ai and inputs_processed < input_limit:
            action = board["input_queue"].pop(0)
            inputs_processed += 1
            moved = self._process_input(board, action, width, height)
            if action_delay_ticks is not None:
                board["ai_next_action_tick"] = tick + action_delay_ticks
            if action.get("type") == "hard_drop":
                lines = self._lock_piece(board, width, height)
                board["ai_has_plan"] = False
                if lines:
                    events.append({"type": "lines_cleared", "lines": lines})
                self._spawn_or_eliminate(board, width, height)
                board["drop_counter"] = 0
                break
            if moved:
                board["lock_counter"] = 0
            if action_delay_ticks is not None:
                break

        active = board.get("active")
        if not active or not board.get("alive"):
            return events

        drop_interval = _drop_interval_ticks(board["level"], base_drop)
        board["drop_counter"] += 1
        gravity_step = board["drop_counter"] >= drop_interval

        if gravity_step:
            board["drop_counter"] = 0
            if not self._try_move(board, 0, 1, width, height):
                board["lock_counter"] += 1
                if board["lock_counter"] >= LOCK_DELAY_TICKS:
                    lines = self._lock_piece(board, width, height)
                    board["ai_has_plan"] = False
                    if lines:
                        events.append({"type": "lines_cleared", "lines": lines})
                    if not self._spawn_or_eliminate(board, width, height):
                        events.append({"type": "player_eliminated", "reason": "topped_out"})
            else:
                board["lock_counter"] = 0

        return events

    def _alive_boards(self, state: dict) -> list[str]:
        return [pid for pid, b in state["boards"].items() if b.get("alive")]

    def _resolve_winner(self, state: dict) -> None:
        if state["settings"].get("single_player"):
            for pid, board in state["boards"].items():
                state["winner"] = pid
                state["final_score"] = board.get("lines_cleared", 0)
                state["win_reason"] = "high_score"
                state["phase"] = "finished"
            return

        alive = self._alive_boards(state)
        if len(alive) == 1:
            state["winner"] = alive[0]
            state["win_reason"] = "last_standing"
            state["phase"] = "finished"
            return

        if len(alive) == 0:
            scores = {pid: state["boards"][pid]["lines_cleared"] for pid in state["boards"]}
            max_lines = max(scores.values())
            winners = [pid for pid, sc in scores.items() if sc == max_lines]
            state["winner"] = winners[0] if len(winners) == 1 else random.choice(winners)
            state["win_reason"] = "most_lines"
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
                    state["game_started_at_tick"] = state["tick"]
                    events.append({"type": "game_started"})
            state["tick"] += 1
            return state, events

        self._apply_ai_inputs(state)

        width = state["board_width"]
        height = state["board_height"]
        base_drop = int(state["settings"]["base_drop_ticks"])

        for player in state["players"]:
            pid = player["id"]
            max_inputs: int | None = None
            action_delay: int | None = None
            if player.get("is_ai"):
                cfg = get_ai_config(player.get("ai_difficulty"))
                max_inputs = 1
                action_delay = int(cfg["action_delay_ticks"])
            board_events = self._tick_board(
                state["boards"][pid],
                width,
                height,
                base_drop,
                tick=state["tick"],
                max_inputs_per_tick=max_inputs,
                action_delay_ticks=action_delay,
            )
            for ev in board_events:
                events.append({**ev, "player_id": pid})

        alive = self._alive_boards(state)
        single_player = state["settings"].get("single_player")
        if single_player and len(alive) == 0:
            self._resolve_winner(state)
            if state.get("winner"):
                events.append({
                    "type": "game_over",
                    "winner": state["winner"],
                    "final_score": state.get("final_score"),
                })
        elif not single_player and len(alive) <= 1:
            self._resolve_winner(state)
            if state.get("winner"):
                events.append({"type": "game_over", "winner": state["winner"]})

        state["tick"] += 1
        return state, events

    def _public_board(self, board: dict) -> dict:
        active = board.get("active")
        piece_type = active["type"] if active else None
        return {
            "grid": board["grid"],
            "active": active,
            "active_color": PIECE_COLORS.get(piece_type) if piece_type else None,
            "next_queue": board.get("next_queue", [])[:3],
            "next_colors": [PIECE_COLORS[t] for t in board.get("next_queue", [])[:3]],
            "alive": board.get("alive", False),
            "lines_cleared": board.get("lines_cleared", 0),
            "level": board.get("level", 1),
            "color": board.get("color"),
        }

    def get_public_state(self, state: dict, viewer_player: dict | None) -> dict:
        base_drop = int(state["settings"]["base_drop_ticks"])

        return {
            "phase": state["phase"],
            "countdown_ends_at": state.get("countdown_ends_at"),
            "tick": state["tick"],
            "board_width": state["board_width"],
            "board_height": state["board_height"],
            "boards": {
                pid: {
                    **self._public_board(b),
                    "drop_interval_ticks": _drop_interval_ticks(b.get("level", 1), base_drop),
                }
                for pid, b in state["boards"].items()
            },
            "players": state["players"],
            "settings": state["settings"],
            "winner": state.get("winner"),
            "win_reason": state.get("win_reason"),
            "final_score": state.get("final_score"),
            "last_action": state.get("last_action"),
            "viewer_id": viewer_player["id"] if viewer_player else None,
        }

    def check_winner(self, state: dict) -> str | None:
        if state.get("phase") == "finished":
            return state.get("winner")
        return None
