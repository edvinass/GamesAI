"""RoboRally game plugin — program robots through a factory floor."""

from __future__ import annotations

import copy
import random
from typing import Any

from app.games.base import GamePlugin
from app.games.roborally import board as rb
from app.games.roborally import cards as card_lib
from app.games.roborally import options as opt_lib
from app.games.roborally.maps import board_for_map, get_map, list_maps
from app.games.roborally.simulation import (
    compute_register_order,
    execute_register,
    respawn_pending_robots,
)


class RoboRallyEngine(GamePlugin):
    game_type = "roborally"

    def default_settings(self) -> dict:
        return {
            "min_players": 2,
            "max_players": 4,
            "solo_practice": False,
            "register_size": 5,
            "hand_size": rb.BASE_HAND_SIZE,
            "map_id": "factory_floor",
            "ai_difficulty": "medium",
            "available_maps": list_maps(),
        }

    def validate_settings(self, settings: dict) -> dict:
        defaults = self.default_settings()
        merged = {**defaults, **(settings or {})}
        merged["min_players"] = max(2, int(merged.get("min_players", 2)))
        merged["max_players"] = min(4, max(merged["min_players"], int(merged.get("max_players", 4))))
        merged["solo_practice"] = bool(merged.get("solo_practice", False))
        reg = int(merged.get("register_size", 5))
        merged["register_size"] = max(3, min(5, reg))
        # Base hand size is classic 9; per-robot draw uses 9 - damage.
        merged["hand_size"] = rb.BASE_HAND_SIZE
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
        merged["available_maps"] = list_maps()
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
        option_deck = opt_lib.new_option_deck(rng)
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
                "damage": 0,
                "lives": rb.STARTING_LIVES,
                "archive": {"x": start["x"], "y": start["y"]},
                "options": [],
                "powered_down": False,
                "pending_power_down": False,
                "pending_reboot": False,
                "eliminated": False,
            }
            start_priorities[pid] = start["priority"]
            draw = rb.hand_size_for_damage(0)
            if opt_lib.has_option(robots[pid], "extra_memory"):
                draw += 1
            hands[pid] = card_lib.draw_cards(deck, draw)
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
            "discard": [],
            "option_deck": option_deck,
            "option_discard": [],
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

        robot = state["robots"][player_id]
        if robot.get("eliminated"):
            raise ValueError("You have been eliminated")

        if action_type == "place_card":
            if state["phase"] != "programming":
                raise ValueError("Can only program during programming phase")
            if player_id in state["locked_players"]:
                raise ValueError("Program already locked")
            if robot.get("powered_down"):
                raise ValueError("Powered down — no programming this round")
            return self._place_card(state, player_id, action, events)

        if action_type == "clear_slot":
            if state["phase"] != "programming":
                raise ValueError("Can only edit program during programming phase")
            if player_id in state["locked_players"]:
                raise ValueError("Program already locked")
            if robot.get("powered_down"):
                raise ValueError("Powered down — no programming this round")
            return self._clear_slot(state, player_id, action, events)

        if action_type == "swap_slots":
            if state["phase"] != "programming":
                raise ValueError("Can only edit program during programming phase")
            if player_id in state["locked_players"]:
                raise ValueError("Program already locked")
            if robot.get("powered_down"):
                raise ValueError("Powered down — no programming this round")
            return self._swap_slots(state, player_id, action, events)

        if action_type == "lock_program":
            if state["phase"] != "programming":
                raise ValueError("Can only lock during programming phase")
            return self._lock_program(state, player_id, action, events)

        raise ValueError(f"Unknown action type: {action_type}")

    def _locked_slots(self, state: dict, player_id: str) -> set[int]:
        robot = state["robots"][player_id]
        register_size = state["settings"]["register_size"]
        return rb.locked_slot_indices(int(robot.get("damage", 0)), register_size)

    def _handle_resign(
        self, state: dict, player_id: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        if state.get("winner"):
            raise ValueError("Game is already over")
        state["robots"][player_id]["eliminated"] = True
        state["robots"][player_id]["lives"] = 0
        remaining = [
            pid
            for pid in state["player_order"]
            if pid != player_id and not state["robots"].get(pid, {}).get("eliminated")
        ]
        events.append({"type": "player_resigned", "player_id": player_id})
        if len(remaining) == 1:
            state["phase"] = "finished"
            state["winner"] = remaining[0]
            state["win_reason"] = "resign"
            events.append({"type": "game_won", "winner": remaining[0], "reason": "resign"})
        elif len(remaining) == 0:
            state["phase"] = "finished"
            state["winner"] = None
            state["win_reason"] = "draw"
        else:
            state["locked_players"] = [p for p in state["locked_players"] if p != player_id]
            state["register_order"] = [p for p in state["register_order"] if p in remaining]
            # Auto-continue if everyone left has locked.
            active = [
                pid
                for pid in state["player_order"]
                if not state["robots"].get(pid, {}).get("eliminated")
            ]
            if active and len(state["locked_players"]) >= len(active) and state["phase"] == "programming":
                state, exec_events = self._run_execution(state)
                events.extend(exec_events)
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
        if slot_index in self._locked_slots(state, player_id):
            raise ValueError("That register is locked by damage")

        hand = state["hands"][player_id]
        card = card_lib.card_in_hand(hand, str(card_id))
        if not card:
            raise ValueError("Card not in hand")

        programs = state["programs"][player_id]
        existing = programs[slot_index]
        if existing:
            hand.append(existing)
        card_lib.remove_card_from_hand(hand, str(card_id))
        programs[slot_index] = {
            "id": card["id"],
            "type": card["type"],
            "priority": int(card.get("priority", 0)),
        }

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
        if slot_index in self._locked_slots(state, player_id):
            raise ValueError("That register is locked by damage")

        programs = state["programs"][player_id]
        existing = programs[slot_index]
        if existing:
            state["hands"][player_id].append(existing)
            programs[slot_index] = None
            events.append({"type": "slot_cleared", "player_id": player_id, "slot_index": slot_index})
        return state, events

    def _swap_slots(
        self, state: dict, player_id: str, action: dict, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        from_index = action.get("from_index")
        to_index = action.get("to_index")
        if from_index is None or to_index is None:
            raise ValueError("from_index and to_index required")
        from_index = int(from_index)
        to_index = int(to_index)
        register_size = state["settings"]["register_size"]
        if (
            from_index < 0
            or from_index >= register_size
            or to_index < 0
            or to_index >= register_size
        ):
            raise ValueError("Invalid slot index")
        locked = self._locked_slots(state, player_id)
        if from_index in locked or to_index in locked:
            raise ValueError("Cannot swap a locked register")
        if from_index == to_index:
            return state, events

        programs = state["programs"][player_id]
        programs[from_index], programs[to_index] = programs[to_index], programs[from_index]
        events.append(
            {
                "type": "slots_swapped",
                "player_id": player_id,
                "from_index": from_index,
                "to_index": to_index,
            }
        )
        return state, events

    def _lock_program(
        self, state: dict, player_id: str, action: dict, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        if player_id in state["locked_players"]:
            raise ValueError("Already locked")

        robot = state["robots"][player_id]
        programs = state["programs"][player_id]
        register_size = state["settings"]["register_size"]
        locked_slots = self._locked_slots(state, player_id)

        if robot.get("powered_down"):
            # Powered-down robots auto-lock with empty/skipped cards.
            state["locked_players"].append(player_id)
            events.append({"type": "program_locked", "player_id": player_id, "powered_down": True})
        else:
            for i in range(register_size):
                if i in locked_slots:
                    if programs[i] is None:
                        raise ValueError("Locked register missing card")
                    continue
                if programs[i] is None:
                    raise ValueError("Fill all unlocked register slots before locking")

            if action.get("power_down"):
                robot["pending_power_down"] = True

            state["locked_players"].append(player_id)
            events.append(
                {
                    "type": "program_locked",
                    "player_id": player_id,
                    "power_down_next": bool(robot.get("pending_power_down")),
                }
            )

        active_players = [
            pid
            for pid in state["player_order"]
            if not state["robots"].get(pid, {}).get("eliminated")
        ]
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
        deck = state["deck"]
        discard = state.setdefault("discard", [])

        # Classic: clones return at the start of the next turn.
        respawn_events = respawn_pending_robots(state["robots"], state["board"])
        if respawn_events:
            state.setdefault("execution_log", []).extend(respawn_events)

        for pid in state["player_order"]:
            robot = state["robots"][pid]
            if robot.get("eliminated"):
                continue

            # Begin a declared power-down round.
            if robot.get("pending_power_down"):
                robot["powered_down"] = True
                robot["pending_power_down"] = False

            locked_slots = rb.locked_slot_indices(int(robot.get("damage", 0)), register_size)
            old_program = state["programs"][pid]
            new_program: list[dict[str, str] | None] = [None] * register_size
            for i in range(register_size):
                if i in locked_slots and old_program[i]:
                    new_program[i] = dict(old_program[i])
                elif old_program[i]:
                    discard.append(dict(old_program[i]))
            state["programs"][pid] = new_program

            # Unused hand cards return to the shared discard.
            for card in state["hands"].get(pid, []):
                discard.append(dict(card))
            state["hands"][pid] = []

            if robot.get("powered_down"):
                continue

            draw = rb.hand_size_for_damage(int(robot.get("damage", 0)))
            if opt_lib.has_option(robot, "extra_memory"):
                draw += 1
            state["hands"][pid] = card_lib.draw_cards_reshuffling(deck, discard, draw)
            # Keep a healthy draw pile for multi-player games.
            if len(deck) < 10 and discard:
                card_lib.reshuffle_discard_into_deck(deck, discard)

        state["locked_players"] = []
        for pid in state["player_order"]:
            robot = state["robots"][pid]
            if robot.get("eliminated"):
                continue
            if robot.get("powered_down"):
                state["locked_players"].append(pid)

        state["phase"] = "programming"
        state["round"] = state["round"] + 1
        state["register_order"] = compute_register_order(
            state["robots"],
            state["board"],
            state["player_order"],
            state["start_priorities"],
        )

        active = [
            pid
            for pid in state["player_order"]
            if not state["robots"].get(pid, {}).get("eliminated")
        ]
        # Only auto-execute when every survivor is powered down (no human input needed).
        if active and all(state["robots"][pid].get("powered_down") for pid in active):
            self._run_execution(state)

    def get_public_state(self, state: dict, viewer_player: dict | None) -> dict:
        viewer_id = str(viewer_player["id"]) if viewer_player else None
        game_over = bool(state.get("winner")) or state.get("phase") == "finished"
        active = [
            pid
            for pid in state.get("player_order", [])
            if not state["robots"].get(pid, {}).get("eliminated")
        ]
        all_locked = len(state.get("locked_players", [])) >= len(active) if active else False
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

        register_locks: dict[str, list[bool]] = {}
        for pid in state.get("player_order", []):
            robot = state["robots"].get(pid, {})
            locked_idxs = rb.locked_slot_indices(
                int(robot.get("damage", 0)), state["settings"]["register_size"]
            )
            register_locks[pid] = [
                i in locked_idxs for i in range(state["settings"]["register_size"])
            ]

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
            "register_locks": register_locks,
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
            pid = player["id"]
            robot = state["robots"].get(pid, {})
            if robot.get("eliminated"):
                continue
            if pid not in locked and player.get("is_ai"):
                return player
        return None
