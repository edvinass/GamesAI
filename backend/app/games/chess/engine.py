"""Chess game plugin — turn-based two-player chess with optional AI."""

from __future__ import annotations

import copy
from typing import Any

from app.games.base import GamePlugin
from app.games.chess import board as chess


class ChessEngine(GamePlugin):
    game_type = "chess"

    def default_settings(self) -> dict:
        return {
            "min_players": 2,
            "max_players": 2,
            "solo_practice": False,
            "ai_difficulty": "medium",  # easy | medium | hard
        }

    def validate_settings(self, settings: dict) -> dict:
        defaults = self.default_settings()
        merged = {**defaults, **(settings or {})}
        merged["min_players"] = 2
        merged["max_players"] = 2
        merged["solo_practice"] = bool(merged.get("solo_practice", False))
        difficulty = str(merged.get("ai_difficulty", "medium")).lower()
        if difficulty not in ("easy", "medium", "hard"):
            difficulty = "medium"
        merged["ai_difficulty"] = difficulty
        return merged

    def validate_lobby(self, players: list[dict], settings: dict) -> str | None:
        settings = self.validate_settings(settings)
        if settings.get("solo_practice"):
            humans = [p for p in players if not p.get("is_ai")]
            if len(humans) != 1:
                return "Solo practice requires exactly one human player"
            return None
        if len(players) != 2:
            return "Chess requires exactly 2 players"
        return None

    def create_initial_state(self, players: list[dict], settings: dict) -> dict:
        settings = self.validate_settings(settings)
        if len(players) != 2:
            raise ValueError("Chess requires exactly 2 players")

        # Human prefers white in solo; otherwise first player is white.
        humans = [p for p in players if not p.get("is_ai")]
        if settings.get("solo_practice") and len(humans) == 1:
            white = humans[0]
            black = next(p for p in players if p["id"] != white["id"])
        else:
            white, black = players[0], players[1]

        position = chess.parse_fen(chess.START_FEN)
        player_map = {
            white["id"]: {
                "id": white["id"],
                "nickname": white["nickname"],
                "is_ai": white.get("is_ai", False),
                "color": "w",
            },
            black["id"]: {
                "id": black["id"],
                "nickname": black["nickname"],
                "is_ai": black.get("is_ai", False),
                "color": "b",
            },
        }

        state = {
            "phase": "playing",
            "position": position,
            "fen": chess.board_to_fen(position),
            "board": chess.board_matrix(position),
            "players": player_map,
            "white_player_id": white["id"],
            "black_player_id": black["id"],
            "current_color": "w",
            "current_actor_id": white["id"],
            "in_check": False,
            "legal_moves": [
                {"from": m["from"], "to": m["to"], "promotion": m.get("promotion")}
                for m in chess.generate_legal_moves(position)
            ],
            "move_history": [],
            "last_move": None,
            "winner": None,
            "winner_color": None,
            "win_reason": None,
            "settings": settings,
            "host_id": settings.get("host_id") or white["id"],
        }
        return state

    def apply_action(
        self, state: dict, action: dict, player: dict
    ) -> tuple[dict, list[dict]]:
        action_type = action.get("type")
        events: list[dict] = []
        player_id = str(player["id"])

        if action_type == "resign":
            if state.get("winner") or state["phase"] != "playing":
                raise ValueError("Game is already over")
            if player_id not in state["players"]:
                raise ValueError("You are not a player in this game")
            color = state["players"][player_id]["color"]
            winner_color = chess.opponent(color)
            winner_id = (
                state["white_player_id"] if winner_color == "w" else state["black_player_id"]
            )
            state["phase"] = "game_over"
            state["winner"] = winner_id
            state["winner_color"] = winner_color
            state["win_reason"] = "resign"
            state["current_actor_id"] = None
            state["legal_moves"] = []
            events.append(
                {
                    "type": "player_resigned",
                    "player_id": player_id,
                    "winner": winner_id,
                }
            )
            return state, events

        if action_type == "offer_draw":
            if state.get("winner") or state["phase"] != "playing":
                raise ValueError("Game is already over")
            if player_id not in state["players"]:
                raise ValueError("You are not a player in this game")
            state["draw_offer_from"] = player_id
            events.append({"type": "draw_offered", "player_id": player_id})
            return state, events

        if action_type == "accept_draw":
            if state.get("winner") or state["phase"] != "playing":
                raise ValueError("Game is already over")
            offer_from = state.get("draw_offer_from")
            if not offer_from or str(offer_from) == player_id:
                raise ValueError("No draw offer to accept")
            if player_id not in state["players"]:
                raise ValueError("You are not a player in this game")
            state["phase"] = "game_over"
            state["winner"] = None
            state["winner_color"] = None
            state["win_reason"] = "draw_agreement"
            state["current_actor_id"] = None
            state["legal_moves"] = []
            state["draw_offer_from"] = None
            events.append({"type": "draw_accepted", "player_id": player_id})
            return state, events

        if action_type == "decline_draw":
            if state.get("draw_offer_from"):
                state["draw_offer_from"] = None
                events.append({"type": "draw_declined", "player_id": player_id})
            return state, events

        if action_type != "move":
            raise ValueError(f"Unknown action type: {action_type}")

        if state.get("winner") or state["phase"] != "playing":
            raise ValueError("Game is already over")

        if player_id != str(state.get("current_actor_id")):
            raise ValueError("Not your turn")

        from_sq = str(action.get("from", "")).lower()
        to_sq = str(action.get("to", "")).lower()
        promotion = action.get("promotion")
        if promotion:
            promotion = str(promotion).lower()
            if promotion not in ("q", "r", "b", "n"):
                raise ValueError("Invalid promotion piece")

        position = state["position"]
        move = chess.find_move(position, from_sq, to_sq, promotion)
        if not move:
            raise ValueError("Illegal move")

        new_position = chess.apply_move_raw(position, move)
        status = chess.status(new_position)

        san_like = f"{move['from']}{move['to']}"
        if move.get("promotion"):
            san_like += f"={move['promotion'].upper()}"

        state["position"] = new_position
        state["fen"] = chess.board_to_fen(new_position)
        state["board"] = chess.board_matrix(new_position)
        state["current_color"] = new_position["turn"]
        state["in_check"] = status["in_check"]
        state["last_move"] = {
            "from": move["from"],
            "to": move["to"],
            "promotion": move.get("promotion"),
            "capture": bool(move.get("capture") or move.get("en_passant")),
            "player_id": player_id,
            "uci": chess.move_uci(move),
        }
        state["move_history"] = list(state.get("move_history") or []) + [state["last_move"]]
        state["draw_offer_from"] = None

        if status["result"] == "checkmate":
            winner_color = status["winner_color"]
            winner_id = (
                state["white_player_id"] if winner_color == "w" else state["black_player_id"]
            )
            state["phase"] = "game_over"
            state["winner"] = winner_id
            state["winner_color"] = winner_color
            state["win_reason"] = "checkmate"
            state["current_actor_id"] = None
            state["legal_moves"] = []
            events.append(
                {
                    "type": "checkmate",
                    "winner": winner_id,
                    "move": state["last_move"],
                }
            )
        elif status["result"] in ("stalemate", "draw"):
            state["phase"] = "game_over"
            state["winner"] = None
            state["winner_color"] = None
            state["win_reason"] = status["result"] if status["result"] == "stalemate" else status.get(
                "draw_reason", "draw"
            )
            state["current_actor_id"] = None
            state["legal_moves"] = []
            events.append({"type": "draw", "reason": state["win_reason"], "move": state["last_move"]})
        else:
            next_actor = (
                state["white_player_id"]
                if new_position["turn"] == "w"
                else state["black_player_id"]
            )
            state["current_actor_id"] = next_actor
            state["legal_moves"] = [
                {"from": m["from"], "to": m["to"], "promotion": m.get("promotion")}
                for m in chess.generate_legal_moves(new_position)
            ]
            events.append({"type": "move_made", "move": state["last_move"], "san": san_like})
            if status["in_check"]:
                events.append({"type": "check", "color": new_position["turn"]})

        return state, events

    def get_public_state(self, state: dict, viewer_player: dict | None) -> dict:
        viewer_id = str(viewer_player["id"]) if viewer_player else None
        players = []
        for pid in (state["white_player_id"], state["black_player_id"]):
            p = state["players"][pid]
            players.append(
                {
                    "id": p["id"],
                    "nickname": p["nickname"],
                    "is_ai": p["is_ai"],
                    "color": p["color"],
                }
            )

        viewer_color = None
        if viewer_id and viewer_id in state["players"]:
            viewer_color = state["players"][viewer_id]["color"]

        return {
            "phase": state["phase"],
            "fen": state["fen"],
            "board": copy.deepcopy(state["board"]),
            "players": players,
            "white_player_id": state["white_player_id"],
            "black_player_id": state["black_player_id"],
            "current_color": state["current_color"],
            "current_actor_id": state.get("current_actor_id"),
            "in_check": state.get("in_check", False),
            "legal_moves": copy.deepcopy(state.get("legal_moves") or []),
            "move_history": copy.deepcopy(state.get("move_history") or []),
            "last_move": copy.deepcopy(state.get("last_move")),
            "winner": state.get("winner"),
            "winner_color": state.get("winner_color"),
            "win_reason": state.get("win_reason"),
            "draw_offer_from": state.get("draw_offer_from"),
            "settings": state.get("settings", {}),
            "host_id": state.get("host_id"),
            "viewer_id": viewer_id,
            "viewer_color": viewer_color,
        }

    def check_winner(self, state: dict) -> str | None:
        return state.get("winner")

    def get_current_actor(self, state: dict) -> dict | None:
        if state.get("winner") or state.get("phase") != "playing":
            return None
        actor_id = state.get("current_actor_id")
        if not actor_id:
            return None
        p = state["players"].get(actor_id)
        if not p or not p.get("is_ai"):
            return None
        return p
