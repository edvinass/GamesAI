from app.games.base import GamePlugin

DEFAULT_BALLS = 3


class PinballEngine(GamePlugin):
    game_type = "pinball"

    def default_settings(self) -> dict:
        return {
            "min_players": 1,
            "max_players": 1,
            "single_player": True,
            "starting_balls": DEFAULT_BALLS,
        }

    def validate_settings(self, settings: dict) -> dict:
        defaults = self.default_settings()
        merged = {**defaults, **(settings or {})}
        merged["min_players"] = 1
        merged["max_players"] = 1
        merged["single_player"] = True
        balls = int(merged.get("starting_balls", DEFAULT_BALLS))
        merged["starting_balls"] = max(1, min(5, balls))
        return merged

    def validate_lobby(self, players: list[dict], settings: dict) -> str | None:
        humans = [p for p in players if not p.get("is_ai")]
        if len(humans) != 1:
            return "Pinball requires exactly one human player"
        if any(p.get("is_ai") for p in players):
            return "Pinball is single-player only — remove AI players"
        return None

    def create_initial_state(self, players: list[dict], settings: dict) -> dict:
        settings = self.validate_settings(settings)
        return {
            "phase": "playing",
            "score": 0,
            "balls_remaining": settings["starting_balls"],
            "high_score": 0,
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

        if action_type == "update_score":
            if state["phase"] != "playing":
                return state, events
            score = max(0, int(action.get("score", state["score"])))
            balls = max(0, int(action.get("balls_remaining", state["balls_remaining"])))
            high_score = max(int(state.get("high_score", 0)), score)
            state = {
                **state,
                "score": score,
                "balls_remaining": balls,
                "high_score": high_score,
                "last_action": action,
            }
            events.append({"type": "score_updated", "score": score, "balls_remaining": balls})
            return state, events

        if action_type == "game_over":
            if state["phase"] != "playing":
                return state, events
            score = max(0, int(action.get("score", state["score"])))
            high_score = max(int(state.get("high_score", 0)), score)
            state = {
                **state,
                "phase": "finished",
                "score": score,
                "balls_remaining": 0,
                "high_score": high_score,
                "winner": player["id"],
                "win_reason": "balls_exhausted",
                "last_action": action,
            }
            events.append({"type": "game_over", "player_id": player["id"], "score": score})
            return state, events

        if action_type == "restart_game":
            state = {
                **self.create_initial_state(state["players"], state["settings"]),
                "high_score": max(
                    int(state.get("high_score", 0)),
                    int(state.get("score", 0)),
                ),
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
