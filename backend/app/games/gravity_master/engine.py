from typing import Any

from app.games.base import GamePlugin
from app.games.gravity_master.levels import LEVELS


class GravityMasterEngine(GamePlugin):
    game_type = "gravity_master"

    def default_settings(self) -> dict:
        return {
            "min_players": 1,
            "max_players": 1,
            "single_player": True,
            "world_width": 800,
            "world_height": 600,
        }

    def validate_settings(self, settings: dict) -> dict:
        defaults = self.default_settings()
        merged = {**defaults, **(settings or {})}
        merged["min_players"] = 1
        merged["max_players"] = 1
        merged["single_player"] = True
        merged["world_width"] = max(640, min(960, int(merged.get("world_width", 800))))
        merged["world_height"] = max(480, min(720, int(merged.get("world_height", 600))))
        return merged

    def validate_lobby(self, players: list[dict], settings: dict) -> str | None:
        humans = [p for p in players if not p.get("is_ai")]
        if len(humans) != 1:
            return "Gravity Master requires exactly one human player"
        if any(p.get("is_ai") for p in players):
            return "Gravity Master is single-player only — remove AI players"
        return None

    def _level_for_index(self, index: int) -> dict:
        safe_index = max(0, min(index, len(LEVELS) - 1))
        return dict(LEVELS[safe_index])

    def create_initial_state(self, players: list[dict], settings: dict) -> dict:
        settings = self.validate_settings(settings)
        return {
            "phase": "drawing",
            "level_index": 0,
            "levels_total": len(LEVELS),
            "level": self._level_for_index(0),
            "ink_used": 0,
            "players": players,
            "settings": settings,
            "winner": None,
            "win_reason": None,
            "last_action": None,
        }

    def apply_action(
        self, state: dict, action: dict, player: dict
    ) -> tuple[dict, list[dict]]:
        action_type = action.get("type")
        events: list[dict] = []

        if action_type == "start_simulation":
            if state["phase"] != "drawing":
                return state, events
            state = {**state, "phase": "simulating", "last_action": action}
            events.append({"type": "simulation_started"})
            return state, events

        if action_type == "level_complete":
            if state["phase"] != "simulating":
                return state, events
            next_index = state["level_index"] + 1
            if next_index >= state["levels_total"]:
                state = {
                    **state,
                    "phase": "finished",
                    "winner": player["id"],
                    "win_reason": "all_levels_complete",
                    "last_action": action,
                }
                events.append({"type": "game_won", "player_id": player["id"]})
            else:
                state = {
                    **state,
                    "phase": "drawing",
                    "level_index": next_index,
                    "level": self._level_for_index(next_index),
                    "ink_used": 0,
                    "last_action": action,
                }
                events.append({"type": "level_advanced", "level_index": next_index})
            return state, events

        if action_type == "retry_level":
            state = {
                **state,
                "phase": "drawing",
                "ink_used": 0,
                "last_action": action,
            }
            events.append({"type": "level_retried"})
            return state, events

        if action_type == "restart_game":
            state = {
                **self.create_initial_state(state["players"], state["settings"]),
                "last_action": action,
            }
            events.append({"type": "game_restarted"})
            return state, events

        return state, events

    def get_public_state(self, state: dict, viewer_player: dict | None) -> dict:
        public = {**state}
        public["viewer_id"] = viewer_player["id"] if viewer_player else None
        return public

    def check_winner(self, state: dict) -> str | None:
        if state.get("phase") == "finished":
            return state.get("winner")
        return None
