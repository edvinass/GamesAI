import random
from datetime import datetime, timedelta, timezone
from typing import Any

from app.games.base import GamePlugin
from app.games.duel.ai import choose_ai_actions

FIGHTER_COLORS = ["#3b82f6", "#ef4444"]

FIGHTER_HEIGHT = 3

MOVE_DIRECTIONS = {"up", "down", "stop"}


class DuelEngine(GamePlugin):
    game_type = "duel"

    def default_settings(self) -> dict:
        return {
            "min_players": 2,
            "max_players": 2,
            "grid_width": 48,
            "grid_height": 24,
            "tick_ms": 75,
            "countdown_sec": 3,
            "shoot_cooldown_ticks": 10,
            "fighter_height": FIGHTER_HEIGHT,
            "solo_practice": False,
        }

    def validate_settings(self, settings: dict) -> dict:
        defaults = self.default_settings()
        merged = {**defaults, **(settings or {})}
        merged["min_players"] = 2
        merged["max_players"] = 2
        merged["grid_width"] = max(20, min(80, int(merged.get("grid_width", 48))))
        merged["grid_height"] = max(12, min(40, int(merged.get("grid_height", 24))))
        merged["tick_ms"] = max(50, min(200, int(merged.get("tick_ms", 75))))
        merged["countdown_sec"] = max(1, min(10, int(merged.get("countdown_sec", 3))))
        merged["shoot_cooldown_ticks"] = max(4, min(30, int(merged.get("shoot_cooldown_ticks", 10))))
        merged["fighter_height"] = max(1, min(5, int(merged.get("fighter_height", FIGHTER_HEIGHT))))
        merged["solo_practice"] = bool(merged.get("solo_practice", False))
        return merged

    def tick_interval_ms(self) -> int:
        return 75

    def validate_lobby(self, players: list[dict], settings: dict) -> str | None:
        settings = self.validate_settings(settings)
        if settings.get("solo_practice"):
            humans = [p for p in players if not p.get("is_ai")]
            if len(humans) != 1:
                return "Solo practice requires exactly one human player"
            return None

        if len(players) != 2:
            return "Side Duel requires exactly 2 players"
        return None

    def _spawn_side(self, index: int, grid_width: int, grid_height: int) -> dict[str, Any]:
        side = "left" if index == 0 else "right"
        x = 1 if side == "left" else grid_width - 2
        return {
            "x": x,
            "y": (grid_height - FIGHTER_HEIGHT) // 2,
            "side": side,
            "alive": True,
            "move_direction": "stop",
            "pending_shoot": False,
            "cooldown_until_tick": 0,
            "color": FIGHTER_COLORS[index % len(FIGHTER_COLORS)],
        }

    def create_initial_state(self, players: list[dict], settings: dict) -> dict:
        settings = self.validate_settings(settings)
        grid_width = settings["grid_width"]
        grid_height = settings["grid_height"]

        fighters: dict[str, dict] = {}
        for i, player in enumerate(players):
            fighters[player["id"]] = self._spawn_side(i, grid_width, grid_height)

        countdown_sec = settings["countdown_sec"]
        countdown_ends_at = (
            datetime.now(timezone.utc) + timedelta(seconds=countdown_sec)
        ).isoformat()

        return {
            "phase": "countdown",
            "countdown_ends_at": countdown_ends_at,
            "tick": 0,
            "grid_width": grid_width,
            "grid_height": grid_height,
            "fighters": fighters,
            "bullets": [],
            "next_bullet_id": 0,
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

        if state["phase"] != "playing":
            return state, events

        player_id = player["id"]
        fighter = state["fighters"].get(player_id)
        if not fighter or not fighter.get("alive"):
            return state, events

        if action_type == "set_move":
            direction = action.get("direction")
            if direction not in MOVE_DIRECTIONS:
                return state, events
            fighter["move_direction"] = direction
            state["last_action"] = {
                "type": "set_move",
                "player_id": player_id,
                "direction": direction,
            }
            return state, events

        if action_type == "shoot":
            fighter["pending_shoot"] = True
            state["last_action"] = {"type": "shoot", "player_id": player_id}
            return state, events

        return state, events

    def _apply_ai_inputs(self, state: dict) -> None:
        for player in state["players"]:
            if not player.get("is_ai"):
                continue
            pid = player["id"]
            fighter = state["fighters"].get(pid)
            if not fighter or not fighter.get("alive"):
                continue
            move, shoot = choose_ai_actions(state, pid, fighter)
            fighter["move_direction"] = move
            if shoot:
                fighter["pending_shoot"] = True

    def _fighter_height(self, state: dict) -> int:
        return int(state["settings"].get("fighter_height", FIGHTER_HEIGHT))

    def _move_fighter(self, fighter: dict, grid_height: int, fighter_height: int) -> None:
        direction = fighter.get("move_direction", "stop")
        max_y = grid_height - fighter_height
        if direction == "up":
            fighter["y"] = max(0, fighter["y"] - 1)
        elif direction == "down":
            fighter["y"] = min(max_y, fighter["y"] + 1)

    def _shoot_row(self, fighter: dict, fighter_height: int) -> int:
        return fighter["y"] + fighter_height // 2

    def _try_shoot(self, state: dict, fighter: dict, owner_id: str) -> None:
        if not fighter.get("pending_shoot"):
            return
        tick = state["tick"]
        if tick < fighter.get("cooldown_until_tick", 0):
            return

        fighter["pending_shoot"] = False
        settings = state["settings"]
        side = fighter["side"]
        vx = 1 if side == "left" else -1
        spawn_x = fighter["x"] + vx
        if spawn_x < 0 or spawn_x >= state["grid_width"]:
            return

        bullet_id = state["next_bullet_id"]
        state["next_bullet_id"] = bullet_id + 1
        state["bullets"].append(
            {
                "id": bullet_id,
                "x": spawn_x,
                "y": self._shoot_row(fighter, self._fighter_height(state)),
                "vx": vx,
                "owner_id": owner_id,
            }
        )
        fighter["cooldown_until_tick"] = tick + settings["shoot_cooldown_ticks"]

    def _bullet_hits_fighter(self, bullet: dict, fighter: dict, fighter_height: int) -> bool:
        if bullet["x"] != fighter["x"]:
            return False
        top = fighter["y"]
        return top <= bullet["y"] < top + fighter_height

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

        self._apply_ai_inputs(state)

        grid_width = state["grid_width"]
        grid_height = state["grid_height"]
        fighters = state["fighters"]
        fighter_height = self._fighter_height(state)

        for pid, fighter in fighters.items():
            if fighter.get("alive"):
                self._move_fighter(fighter, grid_height, fighter_height)
                self._try_shoot(state, fighter, pid)

        remaining_bullets: list[dict] = []
        for bullet in state["bullets"]:
            bullet["x"] += bullet["vx"]
            if bullet["x"] < 0 or bullet["x"] >= grid_width:
                continue

            hit = False
            for pid, fighter in fighters.items():
                if pid == bullet["owner_id"] or not fighter.get("alive"):
                    continue
                if self._bullet_hits_fighter(bullet, fighter, fighter_height):
                    fighter["alive"] = False
                    hit = True
                    events.append({"type": "player_hit", "player_id": pid, "shooter_id": bullet["owner_id"]})
                    break

            if not hit:
                remaining_bullets.append(bullet)

        state["bullets"] = remaining_bullets

        alive = [pid for pid, f in fighters.items() if f.get("alive")]
        if len(alive) == 1:
            state["winner"] = alive[0]
            state["win_reason"] = "direct_hit"
            state["phase"] = "finished"
            events.append({"type": "game_over", "winner": state["winner"]})
        elif len(alive) == 0:
            state["winner"] = None
            state["win_reason"] = "mutual_destruction"
            state["phase"] = "finished"
            events.append({"type": "game_over", "winner": None})

        state["tick"] += 1
        return state, events

    def get_public_state(self, state: dict, viewer_player: dict | None) -> dict:
        return {
            "phase": state["phase"],
            "countdown_ends_at": state.get("countdown_ends_at"),
            "tick": state["tick"],
            "grid_width": state["grid_width"],
            "grid_height": state["grid_height"],
            "fighter_height": self._fighter_height(state),
            "fighters": state["fighters"],
            "bullets": state["bullets"],
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
