from __future__ import annotations

from app.games.base import GamePlugin


class Connect4Engine(GamePlugin):
    """Connect Four (Four in a Row) game engine."""

    game_type = "connect4"
    ROWS = 6
    COLS = 7
    WIN_LENGTH = 4

    def default_settings(self) -> dict:
        return {
            "ai_difficulty": "medium",
            "solo_practice": False,
            "max_players": 2,
        }

    def validate_settings(self, settings: dict) -> dict:
        valid = self.default_settings()
        if settings.get("ai_difficulty") in ("easy", "medium", "hard"):
            valid["ai_difficulty"] = settings["ai_difficulty"]
        if isinstance(settings.get("solo_practice"), bool):
            valid["solo_practice"] = settings["solo_practice"]
        return valid

    def validate_lobby(self, players: list[dict], settings: dict) -> str | None:
        if settings.get("solo_practice"):
            humans = [p for p in players if not p.get("is_ai")]
            if len(humans) != 1:
                return "Solo practice requires exactly one human player"
            return None

        if len(players) < 2:
            return "Need exactly 2 players"
        if len(players) > 2:
            return "Connect Four supports only 2 players"
        return None

    def create_initial_state(self, players: list[dict], settings: dict) -> dict:
        settings = self.validate_settings(settings)
        if len(players) != 2:
            raise ValueError("Connect Four requires exactly 2 players")

        # Human prefers red in solo; otherwise first player is red.
        humans = [p for p in players if not p.get("is_ai")]
        if settings.get("solo_practice") and len(humans) == 1:
            red = humans[0]
            yellow = next(p for p in players if p["id"] != red["id"])
        else:
            red, yellow = players[0], players[1]

        difficulty = settings.get("ai_difficulty", "medium")
        player_list = [
            {
                "id": red["id"],
                "nickname": red.get("nickname", "Player 1"),
                "is_ai": red.get("is_ai", False),
                "ai_difficulty": red.get("ai_difficulty", difficulty),
                "color": "red",
            },
            {
                "id": yellow["id"],
                "nickname": yellow.get("nickname", "Player 2"),
                "is_ai": yellow.get("is_ai", False),
                "ai_difficulty": yellow.get("ai_difficulty", difficulty),
                "color": "yellow",
            },
        ]

        board = [[None for _ in range(self.COLS)] for _ in range(self.ROWS)]

        return {
            "phase": "playing",
            "board": board,
            "rows": self.ROWS,
            "cols": self.COLS,
            "players": player_list,
            "red_player_id": player_list[0]["id"],
            "yellow_player_id": player_list[1]["id"],
            "current_color": "red",
            "current_actor_id": player_list[0]["id"],
            "move_history": [],
            "last_move": None,
            "winner": None,
            "winner_color": None,
            "win_reason": None,
            "winning_cells": None,
            "settings": settings,
        }

    def apply_action(
        self, state: dict, action: dict, player: dict
    ) -> tuple[dict, list[dict]]:
        events: list[dict] = []
        action_type = action.get("type")

        if action_type == "drop":
            return self._handle_drop(state, action, player, events)
        elif action_type == "resign":
            return self._handle_resign(state, player, events)

        return state, events

    def _handle_drop(
        self, state: dict, action: dict, player: dict, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        if state["phase"] != "playing":
            raise ValueError("Game is already over")

        if player["id"] != state["current_actor_id"]:
            raise ValueError("Not your turn")

        col = action.get("col")
        if col is None or not isinstance(col, int):
            raise ValueError("Invalid column")

        if col < 0 or col >= self.COLS:
            raise ValueError("Invalid column")

        board = [row[:] for row in state["board"]]
        row = self._find_drop_row(board, col)

        if row is None:
            raise ValueError("Column is full")

        current_color = state["current_color"]
        board[row][col] = current_color

        move = {
            "col": col,
            "row": row,
            "color": current_color,
            "player_id": player["id"],
        }

        move_history = state["move_history"] + [move]

        winning_cells = self._check_win_at(board, row, col, current_color)
        is_draw = winning_cells is None and self._is_board_full(board)

        if winning_cells:
            state = {
                **state,
                "board": board,
                "move_history": move_history,
                "last_move": move,
                "phase": "game_over",
                "winner": player["id"],
                "winner_color": current_color,
                "win_reason": "connect4",
                "winning_cells": winning_cells,
            }
            events.append(
                {
                    "type": "game_over",
                    "winner": player["id"],
                    "reason": "connect4",
                }
            )
        elif is_draw:
            state = {
                **state,
                "board": board,
                "move_history": move_history,
                "last_move": move,
                "phase": "game_over",
                "winner": None,
                "winner_color": None,
                "win_reason": "draw",
                "winning_cells": None,
            }
            events.append({"type": "game_over", "winner": None, "reason": "draw"})
        else:
            next_color = "yellow" if current_color == "red" else "red"
            next_player_id = (
                state["yellow_player_id"]
                if next_color == "yellow"
                else state["red_player_id"]
            )
            state = {
                **state,
                "board": board,
                "move_history": move_history,
                "last_move": move,
                "current_color": next_color,
                "current_actor_id": next_player_id,
            }

        return state, events

    def _handle_resign(
        self, state: dict, player: dict, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        if state["phase"] != "playing":
            return state, events

        player_info = next((p for p in state["players"] if p["id"] == player["id"]), None)
        if not player_info:
            return state, events

        opponent = next(
            (p for p in state["players"] if p["id"] != player["id"]), None
        )
        if not opponent:
            return state, events

        state = {
            **state,
            "phase": "game_over",
            "winner": opponent["id"],
            "winner_color": opponent["color"],
            "win_reason": "resign",
        }
        events.append(
            {"type": "game_over", "winner": opponent["id"], "reason": "resign"}
        )

        return state, events

    def _find_drop_row(self, board: list[list], col: int) -> int | None:
        for row in range(self.ROWS - 1, -1, -1):
            if board[row][col] is None:
                return row
        return None

    def _check_win_at(
        self, board: list[list], row: int, col: int, color: str
    ) -> list[list[int]] | None:
        directions = [
            (0, 1),
            (1, 0),
            (1, 1),
            (1, -1),
        ]

        for dr, dc in directions:
            cells = [(row, col)]

            for sign in [1, -1]:
                r, c = row + dr * sign, col + dc * sign
                while (
                    0 <= r < self.ROWS
                    and 0 <= c < self.COLS
                    and board[r][c] == color
                ):
                    cells.append((r, c))
                    r += dr * sign
                    c += dc * sign

            if len(cells) >= self.WIN_LENGTH:
                return [[r, c] for r, c in sorted(cells)]

        return None

    def _is_board_full(self, board: list[list]) -> bool:
        return all(board[0][c] is not None for c in range(self.COLS))

    def get_public_state(self, state: dict, viewer_player: dict | None) -> dict:
        viewer_color = None
        if viewer_player:
            p = next(
                (p for p in state["players"] if p["id"] == viewer_player["id"]), None
            )
            if p:
                viewer_color = p["color"]

        legal_moves = []
        if state["phase"] == "playing" and viewer_player:
            if viewer_player["id"] == state["current_actor_id"]:
                board = state["board"]
                for col in range(self.COLS):
                    if board[0][col] is None:
                        legal_moves.append({"col": col})

        return {
            "phase": state["phase"],
            "board": state["board"],
            "rows": state["rows"],
            "cols": state["cols"],
            "players": state["players"],
            "red_player_id": state["red_player_id"],
            "yellow_player_id": state["yellow_player_id"],
            "current_color": state["current_color"],
            "current_actor_id": state["current_actor_id"],
            "move_history": state["move_history"],
            "last_move": state["last_move"],
            "winner": state["winner"],
            "winner_color": state["winner_color"],
            "win_reason": state["win_reason"],
            "winning_cells": state.get("winning_cells"),
            "viewer_id": viewer_player["id"] if viewer_player else None,
            "viewer_color": viewer_color,
            "legal_moves": legal_moves,
            "settings": state.get("settings", {}),
        }

    def check_winner(self, state: dict) -> str | None:
        return state.get("winner")

    def get_current_actor(self, state: dict) -> dict | None:
        if state.get("winner") or state.get("phase") != "playing":
            return None
        actor_id = state.get("current_actor_id")
        if not actor_id:
            return None
        player = next((p for p in state["players"] if p["id"] == actor_id), None)
        if not player or not player.get("is_ai"):
            return None
        return player
