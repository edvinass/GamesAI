"""RoboRally game plugin — program robots through a factory floor."""

from __future__ import annotations

import copy
import random
from typing import Any

from app.games.base import GamePlugin
from app.games.roborally import board as rb
from app.games.roborally import cards as card_lib
from app.games.roborally.maps import board_for_map, get_map, list_maps
from app.games.roborally.simulation import compute_register_order, execute_register


class RoboRallyEngine(GamePlugin):
    game_type = "roborally"

    def default_settings(self) -> dict:
        return {
            "min_players": 2,
            "max_players": 4,
            "solo_practice": False,
            "register_size": 5,
            "hand_size": 9,
            "map_id": "factory_floor",
            "ai_difficulty": "medium",
        }

    def validate_settings(self, settings: dict) -> dict:
        defaults = self.default_settings()
        merged = {**defaults, **(settings or {})}
        merged["min_players"] = max(2, int(merged.get("min_players", 2)))
        merged["max_players"] = min(4, max(merged["min_players"], int(merged.get("max_players", 4))))
        merged["solo_practice"] = bool(merged.get("solo_practice", False))
        reg = int(merged.get("register_size", 5))
        merged["register_size"] = max(3, min(5, reg))
        hand = int(merged.get("hand_size", 9))
        merged["hand_size"] = max(merged["register_size"], min(12, hand))
        map_id = str(merged.get("map_id", "factory_floor"))
        try:
            get_map(map_id)
        except ValueError:
            map_id = "factory_floor"
        merged["map_id"] = map_id
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
        count = len(players)
        if count < settings["min_players"]:
            return f"Need at least {settings['min_players']} players"
        if count > settings["max_players"]:
            return f"Maximum {settings['max_players']} players allowed"
        return None

    def create_initial_state(self, players: list[dict], settings: dict) -> dict:
        settings = self.validate_settings(settings)
        if len(players) < settings["min_players"] or len(players) > settings["max_players"]:
            raise ValueError("Invalid player count for RoboRally")

        map_id = settings["map_id"]
        map_def = get_map(map_id)
        board = board_for_map(map_id)
        starts = map_def["starts"][: len(players)]

        rng = random.Random()
        deck = card_lib.new_deck(rng)
        hand_size = settings["hand_size"]
        register_size = settings["register_size"]

        player_map: dict[str, dict[str, Any]] = {}
        robots: dict[str, dict[str, Any]] = {}
        hands: dict[str, list[dict[str, str]]] = {}
        programs: dict[str, list[dict[str, str] | None]] = {}
        start_priorities: dict[str, int] = {}

        for i, player in enumerate(players):
            pid = str(player["id"])
            start = starts[i]
            player_map[pid] = {
                "id": pid,
                "nickname": player["nickname"],
                "is_ai": player.get("is_ai", False),
                "color": rb.ROBOT_COLORS[i % len(rb.ROBOT_COLORS)],
                "seat": i,
            }
            robots[pid] = {
                "x": start["x"],
                "y": start["y"],
                "facing": start["facing"],
                "checkpoints_reached": 0,
            }
            start_priorities[pid] = start["priority"]
            hands[pid] = card_lib.draw_cards(deck, hand_size)
            programs[pid] = [None] * register_size

        player_order = [str(p["id"]) for p in players]
        register_order = compute_register_order(robots, board, player_order, start_priorities)

        return {
            "phase": "programming",
            "round": 1,
            "board": board,
            "robots": robots,
            "players": list(player_map.values()),
            "player_order": player_order,
            "register_order": register_order,
            "start_priorities": start_priorities,
            "hands": hands,
            "programs": programs,
            "locked_players": [],
            "deck": deck,
            "execution_log": [],
            "winner": None,
            "win_reason": None,
            "settings": settings,
            "host_id": settings.get("host_id"),
            "available_maps": list_maps(),
        }

    def apply_action(
        self, state: dict, action: dict, player: dict
    ) -> tuple[dict, list[dict]]:
        action_type = action.get("type")
        events: list[dict] = []
        player_id = str(player["id"])

        if action_type == "resign":
            return self._handle_resign(state, player_id, events)

        if state.get("winner") or state.get("phase") == "finished":
            raise ValueError("Game is already over")

        if player_id not in state["robots"]:
            raise ValueError("You are not a player in this game")

        if action_type == "place_card":
            if state["phase"] != "programming":
                raise ValueError("Can only program during programming phase")
            if player_id in state["locked_players"]:
                raise ValueError("Program already locked")
            return self._place_card(state, player_id, action, events)

        if action_type == "clear_slot":
            if state["phase"] != "programming":
                raise ValueError("Can only edit program during programming phase")
            if player_id in state["locked_players"]:
                raise ValueError("Program already locked")
            return self._clear_slot(state, player_id, action, events)

        if action_type == "lock_program":
            if state["phase"] != "programming":
                raise ValueError("Can only lock during programming phase")
            return self._lock_program(state, player_id, events)

        raise ValueError(f"Unknown action type: {action_type}")

    def _handle_resign(
        self, state: dict, player_id: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        if state.get("winner"):
            raise ValueError("Game is already over")
        remaining = [pid for pid in state["player_order"] if pid != player_id]
        if len(remaining) == 1:
            state["phase"] = "finished"
            state["winner"] = remaining[0]
            state["win_reason"] = "resign"
            events.append({"type": "player_resigned", "player_id": player_id})
            events.append({"type": "game_won", "winner": remaining[0], "reason": "resign"})
        else:
            state["player_order"] = remaining
            state["register_order"] = [p for p in state["register_order"] if p in remaining]
            state["players"] = [p for p in state["players"] if p["id"] != player_id]
            state["locked_players"] = [p for p in state["locked_players"] if p != player_id]
            del state["robots"][player_id]
            del state["hands"][player_id]
            del state["programs"][player_id]
            events.append({"type": "player_resigned", "player_id": player_id})
        return state, events

    def _place_card(
        self, state: dict, player_id: str, action: dict, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        slot_index = action.get("slot_index")
        card_id = action.get("card_id")
        if slot_index is None or card_id is None:
            raise ValueError("slot_index and card_id required")
        slot_index = int(slot_index)
        register_size = state["settings"]["register_size"]
        if slot_index < 0 or slot_index >= register_size:
            raise ValueError("Invalid slot index")

        hand = state["hands"][player_id]
        card = card_lib.card_in_hand(hand, str(card_id))
        if not card:
            raise ValueError("Card not in hand")

        programs = state["programs"][player_id]
        existing = programs[slot_index]
        if existing:
            hand.append(existing)
        card_lib.remove_card_from_hand(hand, str(card_id))
        programs[slot_index] = {"id": card["id"], "type": card["type"]}

        events.append(
            {
                "type": "card_placed",
                "player_id": player_id,
                "slot_index": slot_index,
                "card_type": card["type"],
            }
        )
        return state, events

    def _clear_slot(
        self, state: dict, player_id: str, action: dict, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        slot_index = int(action.get("slot_index", -1))
        register_size = state["settings"]["register_size"]
        if slot_index < 0 or slot_index >= register_size:
            raise ValueError("Invalid slot index")

        programs = state["programs"][player_id]
        existing = programs[slot_index]
        if existing:
            state["hands"][player_id].append(existing)
            programs[slot_index] = None
            events.append({"type": "slot_cleared", "player_id": player_id, "slot_index": slot_index})
        return state, events

    def _lock_program(
        self, state: dict, player_id: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        if player_id in state["locked_players"]:
            raise ValueError("Already locked")

        programs = state["programs"][player_id]
        register_size = state["settings"]["register_size"]
        if any(programs[i] is None for i in range(register_size)):
            raise ValueError("Fill all register slots before locking")

        state["locked_players"].append(player_id)
        events.append({"type": "program_locked", "player_id": player_id})

        active_players = state["player_order"]
        if len(state["locked_players"]) >= len(active_players):
            state, exec_events = self._run_execution(state)
            events.extend(exec_events)

        return state, events

    def _run_execution(self, state: dict) -> tuple[dict, list[dict]]:
        events: list[dict] = []
        state["phase"] = "executing"
        events.append({"type": "execution_started", "round": state["round"]})

        state, reg_events = execute_register(state)
        state["execution_log"] = reg_events
        events.extend(reg_events)

        if state.get("phase") == "finished":
            return state, events

        self._start_next_round(state)
        events.append({"type": "round_started", "round": state["round"]})
        return state, events

    def _start_next_round(self, state: dict) -> None:
        register_size = state["settings"]["register_size"]
        hand_size = state["settings"]["hand_size"]
        deck = state["deck"]

        for pid in state["player_order"]:
            state["programs"][pid] = [None] * register_size
            card_lib.refill_hand(state["hands"][pid], deck, hand_size)

        state["locked_players"] = []
        state["phase"] = "programming"
        state["round"] = state["round"] + 1
        state["register_order"] = compute_register_order(
            state["robots"],
            state["board"],
            state["player_order"],
            state["start_priorities"],
        )

    def get_public_state(self, state: dict, viewer_player: dict | None) -> dict:
        viewer_id = str(viewer_player["id"]) if viewer_player else None
        game_over = bool(state.get("winner")) or state.get("phase") == "finished"
        all_locked = len(state.get("locked_players", [])) >= len(state.get("player_order", []))
        reveal_programs = game_over or state.get("phase") == "executing" or all_locked

        hands: dict[str, list[dict[str, str]]] = {}
        for pid, hand in state.get("hands", {}).items():
            if viewer_id == pid or game_over:
                hands[pid] = [dict(c) for c in hand]
            else:
                hands[pid] = [{"id": c["id"], "hidden": True} for c in hand]

        programs: dict[str, list[dict[str, str] | None]] = {}
        for pid, prog in state.get("programs", {}).items():
            if viewer_id == pid or reveal_programs:
                programs[pid] = [dict(s) if s else None for s in prog]
            else:
                programs[pid] = [{"hidden": True} if s else None for s in prog]

        locked = set(state.get("locked_players", []))
        lock_status = {pid: pid in locked for pid in state.get("player_order", [])}

        return {
            "phase": state["phase"],
            "round": state["round"],
            "board": state["board"],
            "robots": copy.deepcopy(state["robots"]),
            "players": state.get("players", []),
            "player_order": state.get("player_order", []),
            "register_order": state.get("register_order", []),
            "hands": hands,
            "programs": programs,
            "lock_status": lock_status,
            "register_size": state["settings"]["register_size"],
            "execution_log": state.get("execution_log", []),
            "winner": state.get("winner"),
            "win_reason": state.get("win_reason"),
            "settings": state.get("settings", {}),
            "available_maps": state.get("available_maps", []),
            "viewer_id": viewer_id,
            "total_checkpoints": len(state["board"]["checkpoints"]),
        }

    def check_winner(self, state: dict) -> str | None:
        return state.get("winner")

    def get_current_actor(self, state: dict) -> dict | None:
        if state.get("winner") or state.get("phase") != "programming":
            return None
        locked = set(state.get("locked_players", []))
        for player in state.get("players", []):
            if player["id"] not in locked and player.get("is_ai"):
                return player
        return None
