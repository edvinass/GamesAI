"""Go game plugin — 9×9 Go with area scoring, pass/resign, and MCTS AI."""

from __future__ import annotations

import copy
from typing import Any

from app.games.base import GamePlugin
from app.games.go import board as go


class GoEngine(GamePlugin):
    game_type = "go"

    def default_settings(self) -> dict:
        return {
            "min_players": 2,
            "max_players": 2,
            "solo_practice": False,
            "client_side_ai": False,
            "ai_difficulty": "medium",  # easy | medium | hard
            "board_size": 9,
            "komi": go.DEFAULT_KOMI,
        }

    def validate_settings(self, settings: dict) -> dict:
        defaults = self.default_settings()
        merged = {**defaults, **(settings or {})}
        merged["min_players"] = 2
        merged["max_players"] = 2
        merged["solo_practice"] = bool(merged.get("solo_practice", False))
        if merged["solo_practice"]:
            merged["client_side_ai"] = bool(
                (settings or {}).get("client_side_ai", True)
            )
        else:
            merged["client_side_ai"] = False
        merged["board_size"] = 9
        difficulty = str(merged.get("ai_difficulty", "medium")).lower()
        if difficulty not in ("easy", "medium", "hard"):
            difficulty = "medium"
        merged["ai_difficulty"] = difficulty
        try:
            komi = float(merged.get("komi", go.DEFAULT_KOMI))
        except (TypeError, ValueError):
            komi = go.DEFAULT_KOMI
        merged["komi"] = komi
        return merged

    def validate_lobby(self, players: list[dict], settings: dict) -> str | None:
        settings = self.validate_settings(settings)
        if settings.get("solo_practice"):
            humans = [p for p in players if not p.get("is_ai")]
            if len(humans) != 1:
                return "Solo practice requires exactly one human player"
            return None
        if len(players) != 2:
            return "Go requires exactly 2 players"
        return None

    def create_initial_state(self, players: list[dict], settings: dict) -> dict:
        settings = self.validate_settings(settings)
        if len(players) != 2:
            raise ValueError("Go requires exactly 2 players")

        humans = [p for p in players if not p.get("is_ai")]
        if settings.get("solo_practice") and len(humans) == 1:
            black = humans[0]
            white = next(p for p in players if p["id"] != black["id"])
        else:
            black, white = players[0], players[1]

        position = go.create_position(turn="B")
        player_map = {
            black["id"]: {
                "id": black["id"],
                "nickname": black["nickname"],
                "is_ai": black.get("is_ai", False),
                "color": "B",
            },
            white["id"]: {
                "id": white["id"],
                "nickname": white["nickname"],
                "is_ai": white.get("is_ai", False),
                "color": "W",
            },
        }

        return {
            "phase": "playing",
            "position": position,
            "board": go.board_matrix(position),
            "board_size": go.BOARD_SIZE,
            "players": player_map,
            "black_player_id": black["id"],
            "white_player_id": white["id"],
            "current_color": "B",
            "current_actor_id": black["id"],
            "legal_plays": go.generate_legal_plays(position),
            "move_history": [],
            "last_move": None,
            "consecutive_passes": 0,
            "winner": None,
            "winner_color": None,
            "win_reason": None,
            "score": None,
            "settings": settings,
            "host_id": settings.get("host_id") or black["id"],
        }

    def _finish_by_score(self, state: dict) -> None:
        komi = float(state.get("settings", {}).get("komi", go.DEFAULT_KOMI))
        score = go.score_position(state["position"], komi=komi)
        state["score"] = score
        state["phase"] = "game_over"
        state["current_actor_id"] = None
        state["legal_plays"] = []
        winner_color = score["winner_color"]
        state["winner_color"] = winner_color
        if winner_color == "B":
            state["winner"] = state["black_player_id"]
            state["win_reason"] = "score"
        elif winner_color == "W":
            state["winner"] = state["white_player_id"]
            state["win_reason"] = "score"
        else:
            state["winner"] = None
            state["win_reason"] = "score_draw"

    def apply_action(
        self, state: dict, action: dict, player: dict
    ) -> tuple[dict, list[dict]]:
        action_type = action.get("type")
        events: list[dict] = []
        player_id = str(player["id"])

        if action_type == "client_ai_move":
            settings = state.get("settings") or {}
            if not settings.get("solo_practice") or not settings.get("client_side_ai"):
                raise ValueError("Client AI moves are only allowed in solo practice")
            if player.get("is_ai"):
                raise ValueError("AI players act automatically")
            actor_id = str(state.get("current_actor_id") or "")
            actor = state["players"].get(actor_id)
            if not actor or not actor.get("is_ai"):
                raise ValueError("Not AI turn")
            move = action.get("move") or {}
            move_type = move.get("type")
            if move_type == "pass":
                return self.apply_action(state, {"type": "pass"}, {"id": actor_id, **actor})
            if move_type == "play":
                coord = str(move.get("coord", "")).lower()
                return self.apply_action(
                    state, {"type": "play", "coord": coord}, {"id": actor_id, **actor}
                )
            raise ValueError("Invalid client AI move")

        if action_type == "resign":
            if state.get("winner") or state["phase"] != "playing":
                raise ValueError("Game is already over")
            if player_id not in state["players"]:
                raise ValueError("You are not a player in this game")
            color = state["players"][player_id]["color"]
            winner_color = "W" if color == "B" else "B"
            winner_id = (
                state["white_player_id"] if winner_color == "W" else state["black_player_id"]
            )
            state["phase"] = "game_over"
            state["winner"] = winner_id
            state["winner_color"] = winner_color
            state["win_reason"] = "resign"
            state["current_actor_id"] = None
            state["legal_plays"] = []
            events.append(
                {
                    "type": "player_resigned",
                    "player_id": player_id,
                    "winner": winner_id,
                }
            )
            return state, events

        if action_type == "pass":
            if state.get("winner") or state["phase"] != "playing":
                raise ValueError("Game is already over")
            if player_id != str(state.get("current_actor_id")):
                raise ValueError("Not your turn")

            new_position = go.apply_pass_raw(state["position"])
            state["position"] = new_position
            state["board"] = go.board_matrix(new_position)
            state["current_color"] = new_position["turn"]
            state["consecutive_passes"] = new_position["consecutive_passes"]
            state["last_move"] = {"type": "pass", "player_id": player_id, "color": state["players"][player_id]["color"]}
            state["move_history"] = list(state.get("move_history") or []) + [state["last_move"]]

            events.append({"type": "pass", "player_id": player_id})

            if go.game_over_by_passes(new_position):
                self._finish_by_score(state)
                events.append({"type": "game_scored", "score": state["score"]})
            else:
                next_actor = (
                    state["black_player_id"]
                    if new_position["turn"] == "B"
                    else state["white_player_id"]
                )
                state["current_actor_id"] = next_actor
                state["legal_plays"] = go.generate_legal_plays(new_position)

            return state, events

        if action_type != "play":
            raise ValueError(f"Unknown action type: {action_type}")

        if state.get("winner") or state["phase"] != "playing":
            raise ValueError("Game is already over")
        if player_id != str(state.get("current_actor_id")):
            raise ValueError("Not your turn")

        coord = str(action.get("coord", "")).lower()
        play = go.find_play(state["position"], coord)
        if not play:
            raise ValueError("Illegal play")

        color = state["players"][player_id]["color"]
        new_position = go.apply_play_raw(state["position"], play["row"], play["col"])
        state["position"] = new_position
        state["board"] = go.board_matrix(new_position)
        state["current_color"] = new_position["turn"]
        state["consecutive_passes"] = 0
        state["last_move"] = {
            "type": "play",
            "coord": play["coord"],
            "row": play["row"],
            "col": play["col"],
            "player_id": player_id,
            "color": color,
            "captured": dict(new_position["captured"]),
        }
        state["move_history"] = list(state.get("move_history") or []) + [state["last_move"]]

        next_actor = (
            state["black_player_id"]
            if new_position["turn"] == "B"
            else state["white_player_id"]
        )
        state["current_actor_id"] = next_actor
        state["legal_plays"] = go.generate_legal_plays(new_position)

        events.append({"type": "play_made", "move": state["last_move"]})
        return state, events

    def get_public_state(self, state: dict, viewer_player: dict | None) -> dict:
        viewer_id = str(viewer_player["id"]) if viewer_player else None
        players = []
        for pid in (state["black_player_id"], state["white_player_id"]):
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
            "board": copy.deepcopy(state["board"]),
            "board_size": state.get("board_size", go.BOARD_SIZE),
            "players": players,
            "black_player_id": state["black_player_id"],
            "white_player_id": state["white_player_id"],
            "current_color": state["current_color"],
            "current_actor_id": state.get("current_actor_id"),
            "legal_plays": copy.deepcopy(state.get("legal_plays") or []),
            "move_history": copy.deepcopy(state.get("move_history") or []),
            "last_move": copy.deepcopy(state.get("last_move")),
            "consecutive_passes": state.get("consecutive_passes", 0),
            "captured": copy.deepcopy(state["position"].get("captured", {"B": 0, "W": 0})),
            "ko_point": copy.deepcopy(state["position"].get("ko_point")),
            "winner": state.get("winner"),
            "winner_color": state.get("winner_color"),
            "win_reason": state.get("win_reason"),
            "score": copy.deepcopy(state.get("score")),
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
