"""Battleship game plugin — place ships, take turns firing, sink the fleet."""

from __future__ import annotations

import copy
import random
from typing import Any

from app.games.base import GamePlugin
from app.games.battleship.ai import SHIP_DEFS, generate_random_fleet

BOARD_SIZE = 10


class BattleshipEngine(GamePlugin):
    game_type = "battleship"

    def default_settings(self) -> dict:
        return {
            "min_players": 2,
            "max_players": 2,
            "solo_practice": False,
            "ai_difficulty": "medium",
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
            return "Battleship requires exactly 2 players"
        return None

    def create_initial_state(self, players: list[dict], settings: dict) -> dict:
        settings = self.validate_settings(settings)
        if len(players) != 2:
            raise ValueError("Battleship requires exactly 2 players")

        humans = [p for p in players if not p.get("is_ai")]
        if settings.get("solo_practice") and len(humans) == 1:
            first = humans[0]
            second = next(p for p in players if p["id"] != first["id"])
        else:
            first, second = players[0], players[1]

        player_map: dict[str, dict] = {}
        fleets: dict[str, dict] = {}
        for p in (first, second):
            pid = str(p["id"])
            player_map[pid] = {
                "id": pid,
                "nickname": p["nickname"],
                "is_ai": bool(p.get("is_ai", False)),
                "ai_difficulty": settings.get("ai_difficulty", "medium"),
                "ready": False,
            }
            fleets[pid] = {
                "ships": [],
                "shots": {},
                "cells": {},
            }

        return {
            "phase": "placing",
            "size": BOARD_SIZE,
            "ship_defs": copy.deepcopy(SHIP_DEFS),
            "players": player_map,
            "player_order": [str(first["id"]), str(second["id"])],
            "fleets": fleets,
            "current_actor_id": None,
            "shot_history": [],
            "last_shot": None,
            "winner": None,
            "win_reason": None,
            "settings": settings,
            "host_id": settings.get("host_id") or str(first["id"]),
        }

    def apply_action(
        self, state: dict, action: dict, player: dict
    ) -> tuple[dict, list[dict]]:
        action_type = action.get("type")
        player_id = str(player["id"])
        events: list[dict] = []

        if player_id not in state["players"]:
            raise ValueError("You are not a player in this game")

        if action_type == "resign":
            return self._handle_resign(state, player_id, events)

        if state.get("winner") or state["phase"] == "game_over":
            raise ValueError("Game is already over")

        if action_type == "place_ship":
            return self._handle_place_ship(state, action, player_id, events)
        if action_type == "remove_ship":
            return self._handle_remove_ship(state, action, player_id, events)
        if action_type == "auto_place":
            return self._handle_auto_place(state, player_id, events)
        if action_type == "ready":
            return self._handle_ready(state, player_id, events)
        if action_type == "fire":
            return self._handle_fire(state, action, player_id, events)

        raise ValueError(f"Unknown action type: {action_type}")

    def _handle_resign(
        self, state: dict, player_id: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        if state.get("winner") or state["phase"] == "game_over":
            raise ValueError("Game is already over")
        opponent_id = self._opponent_id(state, player_id)
        state["phase"] = "game_over"
        state["winner"] = opponent_id
        state["win_reason"] = "resign"
        state["current_actor_id"] = None
        events.append(
            {
                "type": "player_resigned",
                "player_id": player_id,
                "winner": opponent_id,
            }
        )
        return state, events

    def _handle_place_ship(
        self, state: dict, action: dict, player_id: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        if state["phase"] != "placing":
            raise ValueError("Ship placement is over")
        fleet = state["fleets"][player_id]
        if fleet.get("ready") or state["players"][player_id].get("ready"):
            raise ValueError("Fleet is already locked in")

        ship_id = str(action.get("ship_id", ""))
        ship_def = next((s for s in SHIP_DEFS if s["id"] == ship_id), None)
        if not ship_def:
            raise ValueError("Unknown ship")

        if any(s["id"] == ship_id for s in fleet["ships"]):
            raise ValueError("Ship already placed")

        row = action.get("row")
        col = action.get("col")
        horizontal = bool(action.get("horizontal", True))
        if not isinstance(row, int) or not isinstance(col, int):
            raise ValueError("Invalid coordinates")

        cells = self._ship_cells(row, col, ship_def["length"], horizontal)
        self._validate_cells(cells, fleet["cells"])

        ship = {
            "id": ship_def["id"],
            "name": ship_def["name"],
            "length": ship_def["length"],
            "cells": [[r, c] for r, c in cells],
            "hits": 0,
            "sunk": False,
        }
        fleet["ships"].append(ship)
        for r, c in cells:
            fleet["cells"][f"{r},{c}"] = ship_id

        events.append({"type": "ship_placed", "player_id": player_id, "ship_id": ship_id})
        return state, events

    def _handle_remove_ship(
        self, state: dict, action: dict, player_id: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        if state["phase"] != "placing":
            raise ValueError("Ship placement is over")
        fleet = state["fleets"][player_id]
        if fleet.get("ready") or state["players"][player_id].get("ready"):
            raise ValueError("Fleet is already locked in")

        ship_id = str(action.get("ship_id", ""))
        ship = next((s for s in fleet["ships"] if s["id"] == ship_id), None)
        if not ship:
            raise ValueError("Ship not placed")

        fleet["ships"] = [s for s in fleet["ships"] if s["id"] != ship_id]
        fleet["cells"] = {
            k: v for k, v in fleet["cells"].items() if v != ship_id
        }
        events.append({"type": "ship_removed", "player_id": player_id, "ship_id": ship_id})
        return state, events

    def _handle_auto_place(
        self, state: dict, player_id: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        if state["phase"] != "placing":
            raise ValueError("Ship placement is over")
        fleet = state["fleets"][player_id]
        if fleet.get("ready") or state["players"][player_id].get("ready"):
            raise ValueError("Fleet is already locked in")

        ships = generate_random_fleet(random.Random())
        cells: dict[str, str] = {}
        for ship in ships:
            for r, c in ship["cells"]:
                cells[f"{r},{c}"] = ship["id"]
        fleet["ships"] = ships
        fleet["cells"] = cells
        events.append({"type": "fleet_auto_placed", "player_id": player_id})
        return state, events

    def _handle_ready(
        self, state: dict, player_id: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        if state["phase"] != "placing":
            raise ValueError("Ship placement is over")
        fleet = state["fleets"][player_id]
        if len(fleet["ships"]) != len(SHIP_DEFS):
            raise ValueError("Place all ships before ready")

        state["players"][player_id]["ready"] = True
        fleet["ready"] = True
        events.append({"type": "player_ready", "player_id": player_id})

        if all(state["players"][pid].get("ready") for pid in state["player_order"]):
            state["phase"] = "playing"
            state["current_actor_id"] = state["player_order"][0]
            events.append(
                {
                    "type": "battle_started",
                    "current_actor_id": state["current_actor_id"],
                }
            )
        return state, events

    def _handle_fire(
        self, state: dict, action: dict, player_id: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        if state["phase"] != "playing":
            raise ValueError("Battle has not started")
        if player_id != str(state.get("current_actor_id")):
            raise ValueError("Not your turn")

        row = action.get("row")
        col = action.get("col")
        if not isinstance(row, int) or not isinstance(col, int):
            raise ValueError("Invalid coordinates")
        if not (0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE):
            raise ValueError("Shot out of bounds")

        fleet = state["fleets"][player_id]
        key = f"{row},{col}"
        if key in fleet["shots"]:
            raise ValueError("Already fired at that cell")

        opponent_id = self._opponent_id(state, player_id)
        opp_fleet = state["fleets"][opponent_id]
        ship_id = opp_fleet["cells"].get(key)
        result = "miss"
        sunk_ship = None

        if ship_id:
            result = "hit"
            ship = next(s for s in opp_fleet["ships"] if s["id"] == ship_id)
            ship["hits"] = int(ship.get("hits") or 0) + 1
            if ship["hits"] >= ship["length"]:
                ship["sunk"] = True
                result = "sunk"
                sunk_ship = {
                    "id": ship["id"],
                    "name": ship["name"],
                    "cells": copy.deepcopy(ship["cells"]),
                }

        fleet["shots"][key] = "hit" if result in ("hit", "sunk") else "miss"
        shot = {
            "row": row,
            "col": col,
            "result": result,
            "player_id": player_id,
            "target_player_id": opponent_id,
            "ship_id": ship_id,
            "sunk_ship": sunk_ship,
        }
        state["last_shot"] = shot
        state["shot_history"] = list(state.get("shot_history") or []) + [shot]
        events.append({"type": "shot_fired", "shot": shot})

        if all(s.get("sunk") for s in opp_fleet["ships"]):
            state["phase"] = "game_over"
            state["winner"] = player_id
            state["win_reason"] = "fleet_sunk"
            state["current_actor_id"] = None
            events.append(
                {
                    "type": "game_over",
                    "winner": player_id,
                    "reason": "fleet_sunk",
                }
            )
        else:
            # Classic rules: alternate turns even after a hit.
            state["current_actor_id"] = opponent_id

        return state, events

    def _ship_cells(
        self, row: int, col: int, length: int, horizontal: bool
    ) -> list[tuple[int, int]]:
        if horizontal:
            cells = [(row, col + i) for i in range(length)]
        else:
            cells = [(row + i, col) for i in range(length)]
        for r, c in cells:
            if not (0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE):
                raise ValueError("Ship does not fit on the board")
        return cells

    def _validate_cells(self, cells: list[tuple[int, int]], occupied: dict[str, str]) -> None:
        for r, c in cells:
            if f"{r},{c}" in occupied:
                raise ValueError("Ships cannot overlap")

    def _opponent_id(self, state: dict, player_id: str) -> str:
        for pid in state["player_order"]:
            if pid != player_id:
                return pid
        raise ValueError("Opponent not found")

    def get_public_state(self, state: dict, viewer_player: dict | None) -> dict:
        viewer_id = str(viewer_player["id"]) if viewer_player else None
        players = []
        for pid in state["player_order"]:
            p = state["players"][pid]
            players.append(
                {
                    "id": p["id"],
                    "nickname": p["nickname"],
                    "is_ai": p["is_ai"],
                    "ready": bool(p.get("ready")),
                }
            )

        public_fleets: dict[str, dict] = {}
        for pid in state["player_order"]:
            fleet = state["fleets"][pid]
            is_own = viewer_id == pid
            reveal_all = state["phase"] == "game_over" or is_own

            ships_public = []
            for ship in fleet["ships"]:
                if reveal_all or ship.get("sunk"):
                    ships_public.append(
                        {
                            "id": ship["id"],
                            "name": ship["name"],
                            "length": ship["length"],
                            "cells": copy.deepcopy(ship["cells"]) if (reveal_all or ship.get("sunk")) else None,
                            "hits": ship["hits"] if reveal_all else (ship["length"] if ship.get("sunk") else 0),
                            "sunk": bool(ship.get("sunk")),
                            "placed": True,
                        }
                    )
                else:
                    ships_public.append(
                        {
                            "id": ship["id"],
                            "name": ship["name"],
                            "length": ship["length"],
                            "cells": None,
                            "hits": 0,
                            "sunk": False,
                            "placed": True,
                        }
                    )

            # Include unplaced ship defs for own view during placing.
            if is_own and state["phase"] == "placing":
                placed_ids = {s["id"] for s in fleet["ships"]}
                for ship_def in SHIP_DEFS:
                    if ship_def["id"] not in placed_ids:
                        ships_public.append(
                            {
                                "id": ship_def["id"],
                                "name": ship_def["name"],
                                "length": ship_def["length"],
                                "cells": None,
                                "hits": 0,
                                "sunk": False,
                                "placed": False,
                            }
                        )

            # Shots fired BY this player (shown on opponent board from viewer's perspective).
            public_fleets[pid] = {
                "ready": bool(fleet.get("ready") or state["players"][pid].get("ready")),
                "ships": ships_public,
                "shots": copy.deepcopy(fleet.get("shots") or {}),
                "ships_remaining": sum(1 for s in fleet["ships"] if not s.get("sunk")),
            }

        # Incoming shots on each board = opponent's shots.
        boards: dict[str, dict] = {}
        for pid in state["player_order"]:
            opp = self._opponent_id(state, pid)
            incoming = state["fleets"][opp].get("shots") or {}
            own_cells = state["fleets"][pid].get("cells") or {}
            grid = []
            for r in range(BOARD_SIZE):
                row_cells = []
                for c in range(BOARD_SIZE):
                    key = f"{r},{c}"
                    cell: dict[str, Any] = {"row": r, "col": c, "state": "empty"}
                    is_own = viewer_id == pid
                    reveal = state["phase"] == "game_over" or is_own
                    if key in own_cells and reveal:
                        cell["ship_id"] = own_cells[key]
                        cell["state"] = "ship"
                    if key in incoming:
                        result = incoming[key]
                        if result == "hit":
                            cell["state"] = "hit"
                        else:
                            cell["state"] = "miss"
                    row_cells.append(cell)
                grid.append(row_cells)
            boards[pid] = {"grid": grid}

        legal_shots: list[dict] = []
        if (
            state["phase"] == "playing"
            and viewer_id
            and viewer_id == state.get("current_actor_id")
        ):
            my_shots = state["fleets"][viewer_id].get("shots") or {}
            for r in range(BOARD_SIZE):
                for c in range(BOARD_SIZE):
                    if f"{r},{c}" not in my_shots:
                        legal_shots.append({"row": r, "col": c})

        return {
            "phase": state["phase"],
            "size": state["size"],
            "ship_defs": copy.deepcopy(state.get("ship_defs") or SHIP_DEFS),
            "players": players,
            "player_order": list(state["player_order"]),
            "fleets": public_fleets,
            "boards": boards,
            "current_actor_id": state.get("current_actor_id"),
            "shot_history": copy.deepcopy(state.get("shot_history") or []),
            "last_shot": copy.deepcopy(state.get("last_shot")),
            "winner": state.get("winner"),
            "win_reason": state.get("win_reason"),
            "legal_shots": legal_shots,
            "settings": state.get("settings", {}),
            "host_id": state.get("host_id"),
            "viewer_id": viewer_id,
            "opponent_id": self._opponent_id(state, viewer_id) if viewer_id else None,
        }

    def check_winner(self, state: dict) -> str | None:
        return state.get("winner")

    def get_current_actor(self, state: dict) -> dict | None:
        if state.get("winner") or state.get("phase") == "game_over":
            return None

        if state.get("phase") == "placing":
            for pid in state["player_order"]:
                p = state["players"][pid]
                if p.get("is_ai") and not p.get("ready"):
                    return p
            return None

        if state.get("phase") != "playing":
            return None
        actor_id = state.get("current_actor_id")
        if not actor_id:
            return None
        p = state["players"].get(actor_id)
        if not p or not p.get("is_ai"):
            return None
        return p
