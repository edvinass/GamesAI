from __future__ import annotations

import random
from copy import deepcopy

from app.games.base import GamePlugin
from app.games.scrabble.board import (
    MAX_ZERO_TURNS,
    PREMIUMS,
    RACK_SIZE,
    empty_board,
    new_bag,
    tile_points,
)
from app.games.scrabble.scoring import score_placements


class ScrabbleEngine(GamePlugin):
    """Classic English Scrabble for 2 to 4 players."""

    game_type = "scrabble"

    def default_settings(self) -> dict:
        return {
            "ai_difficulty": "medium",
            "solo_practice": False,
            "max_players": 4,
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
            humans = [player for player in players if not player.get("is_ai")]
            if len(humans) != 1:
                return "Solo play needs exactly one human"
            return None
        count = len(players)
        if count < 2:
            return "Need 2 to 4 players"
        if count > 4:
            return "Scrabble allows at most 4 players"
        return None

    def create_initial_state(self, players: list[dict], settings: dict) -> dict:
        settings = self.validate_settings(settings)
        if settings.get("solo_practice"):
            humans = [player for player in players if not player.get("is_ai")]
            bots = [player for player in players if player.get("is_ai")]
            if len(humans) != 1:
                raise ValueError("Solo play needs exactly one human")
            ordered = humans + bots
        else:
            ordered = list(players)
        if not 2 <= len(ordered) <= 4:
            raise ValueError("Scrabble requires 2 to 4 players")

        difficulty = settings.get("ai_difficulty", "medium")
        seats = []
        for index, player in enumerate(ordered):
            seats.append(
                {
                    "id": player["id"],
                    "nickname": player.get("nickname") or f"Player {index + 1}",
                    "is_ai": bool(player.get("is_ai")),
                    "ai_difficulty": player.get("ai_difficulty") or difficulty,
                    "score": 0,
                }
            )

        bag = new_bag()
        racks = {seat["id"]: [] for seat in seats}
        state = {
            "phase": "playing",
            "board": empty_board(),
            "premiums": PREMIUMS,
            "bag": bag,
            "racks": racks,
            "players": seats,
            "current_actor_id": seats[0]["id"],
            "turn_index": 0,
            "zero_turns": 0,
            "last_move": None,
            "move_log": [],
            "winner": None,
            "winner_ids": [],
            "win_reason": None,
            "end_adjustments": None,
            "settings": settings,
        }
        for seat in seats:
            self._draw_up(state, seat["id"])
        return state

    def apply_action(self, state: dict, action: dict, player: dict) -> tuple[dict, list[dict]]:
        state = deepcopy(state)
        if state.get("phase") != "playing":
            raise ValueError("Game is already over")

        action_type = action.get("type")
        if action_type == "resign":
            return self._resign(state, player)
        if player["id"] != state["current_actor_id"]:
            raise ValueError("Not your turn")
        if action_type == "play":
            return self._play(state, action, player)
        if action_type == "pass":
            return self._pass(state, player)
        if action_type == "exchange":
            return self._exchange(state, action, player)
        raise ValueError("Unknown action")

    def get_public_state(self, state: dict, viewer_player: dict | None) -> dict:
        viewer_id = viewer_player["id"] if viewer_player else None
        rack = []
        if viewer_id and viewer_id in state["racks"]:
            rack = [self._public_tile(tile) for tile in state["racks"][viewer_id]]

        board = []
        for row in state["board"]:
            public_row = []
            for cell in row:
                if cell is None:
                    public_row.append(None)
                else:
                    public_row.append({"letter": cell["l"], "blank": bool(cell["b"])})
            board.append(public_row)

        players = []
        for seat in state["players"]:
            players.append(
                {
                    "id": seat["id"],
                    "nickname": seat["nickname"],
                    "is_ai": seat["is_ai"],
                    "score": seat["score"],
                    "rack_count": len(state["racks"].get(seat["id"], [])),
                }
            )

        return {
            "game": "scrabble",
            "phase": state["phase"],
            "board": board,
            "premiums": state["premiums"],
            "bag_count": len(state["bag"]),
            "players": players,
            "current_actor_id": state["current_actor_id"],
            "turn_index": state["turn_index"],
            "zero_turns": state["zero_turns"],
            "last_move": state["last_move"],
            "move_log": state["move_log"][-20:],
            "rack": rack,
            "winner": state["winner"],
            "winner_ids": state["winner_ids"],
            "win_reason": state["win_reason"],
            "end_adjustments": state["end_adjustments"],
            "viewer_id": viewer_id,
            "settings": state.get("settings", {}),
        }

    def check_winner(self, state: dict) -> str | None:
        return state.get("winner")

    def get_current_actor(self, state: dict) -> dict | None:
        if state.get("phase") != "playing":
            return None
        actor_id = state.get("current_actor_id")
        seat = next((player for player in state["players"] if player["id"] == actor_id), None)
        if not seat or not seat.get("is_ai"):
            return None
        return seat

    def _play(self, state: dict, action: dict, player: dict) -> tuple[dict, list[dict]]:
        raw = action.get("placements")
        if not isinstance(raw, list) or not raw:
            raise ValueError("Choose squares for your tiles")

        rack = state["racks"][player["id"]]
        by_id = {tile["id"]: tile for tile in rack}
        resolved = []
        used: set[str] = set()
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("Invalid tile placement")
            tile_id = item.get("tile_id")
            tile = by_id.get(tile_id)
            if tile is None or tile_id in used:
                raise ValueError("That tile is not on your rack")
            used.add(tile_id)
            if tile["b"]:
                letter = str(item.get("letter") or "").strip().upper()
                if len(letter) != 1 or letter not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                    raise ValueError("Choose a letter for the blank")
                blank = True
            else:
                letter = tile["l"]
                blank = False
            resolved.append(
                {
                    "row": item.get("row"),
                    "col": item.get("col"),
                    "letter": letter,
                    "blank": blank,
                    "tile_id": tile_id,
                }
            )

        total, words, bingo = score_placements(state["board"], resolved)
        for item in resolved:
            state["board"][item["row"]][item["col"]] = {"l": item["letter"], "b": item["blank"]}
        state["racks"][player["id"]] = [tile for tile in rack if tile["id"] not in used]

        seat = self._seat(state, player["id"])
        seat["score"] += total
        went_out = not state["racks"][player["id"]] and not state["bag"]
        if not went_out:
            self._draw_up(state, player["id"])

        entry = self._log(
            state,
            player["id"],
            "play",
            total,
            [{"word": word["word"], "score": word["score"]} for word in words],
            bingo,
            [
                {
                    "row": item["row"],
                    "col": item["col"],
                    "letter": item["letter"],
                    "blank": item["blank"],
                }
                for item in resolved
            ],
        )
        state["zero_turns"] = 0 if total > 0 else state["zero_turns"] + 1
        events = [{"type": "play", "player_id": player["id"], "score": total, "words": entry["words"]}]
        if went_out or state["zero_turns"] >= MAX_ZERO_TURNS:
            self._finish(state, went_out_id=player["id"] if went_out else None)
            events.append(
                {"type": "game_over", "winner": state["winner"], "reason": state["win_reason"]}
            )
        else:
            self._advance(state)
        return state, events

    def _pass(self, state: dict, player: dict) -> tuple[dict, list[dict]]:
        self._log(state, player["id"], "pass", 0, [], False, [])
        state["zero_turns"] += 1
        events: list[dict] = [{"type": "pass", "player_id": player["id"]}]
        if state["zero_turns"] >= MAX_ZERO_TURNS:
            self._finish(state, went_out_id=None)
            events.append(
                {"type": "game_over", "winner": state["winner"], "reason": state["win_reason"]}
            )
        else:
            self._advance(state)
        return state, events

    def _exchange(self, state: dict, action: dict, player: dict) -> tuple[dict, list[dict]]:
        tile_ids = action.get("tile_ids")
        if not isinstance(tile_ids, list) or not tile_ids:
            raise ValueError("Choose tiles to exchange")
        if len(state["bag"]) < 7:
            raise ValueError("You can exchange only when the bag has at least 7 tiles")
        unique = list(dict.fromkeys(tile_ids))
        rack = state["racks"][player["id"]]
        by_id = {tile["id"]: tile for tile in rack}
        returning = []
        for tile_id in unique:
            tile = by_id.get(tile_id)
            if tile is None:
                raise ValueError("That tile is not on your rack")
            returning.append(tile)
        keep = [tile for tile in rack if tile["id"] not in set(unique)]
        state["bag"].extend(returning)
        random.shuffle(state["bag"])
        state["racks"][player["id"]] = keep
        self._draw_up(state, player["id"])
        self._log(state, player["id"], "exchange", 0, [], False, [])
        state["zero_turns"] += 1
        events: list[dict] = [{"type": "exchange", "player_id": player["id"], "count": len(returning)}]
        if state["zero_turns"] >= MAX_ZERO_TURNS:
            self._finish(state, went_out_id=None)
            events.append(
                {"type": "game_over", "winner": state["winner"], "reason": state["win_reason"]}
            )
        else:
            self._advance(state)
        return state, events

    def _resign(self, state: dict, player: dict) -> tuple[dict, list[dict]]:
        seat = self._seat(state, player["id"])
        if seat is None:
            raise ValueError("You are not in this game")
        self._log(state, player["id"], "resign", 0, [], False, [])
        others = [item for item in state["players"] if item["id"] != player["id"]]
        top = max(item["score"] for item in others)
        leaders = [item["id"] for item in others if item["score"] == top]
        state["phase"] = "game_over"
        state["winner_ids"] = leaders
        state["winner"] = leaders[0] if len(leaders) == 1 else None
        state["win_reason"] = "resign"
        state["end_adjustments"] = {}
        return state, [{"type": "game_over", "winner": state["winner"], "reason": "resign"}]

    def _finish(self, state: dict, went_out_id: str | None) -> None:
        leftovers = {
            seat["id"]: sum(tile_points(tile) for tile in state["racks"].get(seat["id"], []))
            for seat in state["players"]
        }
        adjustments: dict[str, int] = {}
        bonus = sum(value for pid, value in leftovers.items() if pid != went_out_id) if went_out_id else 0
        for seat in state["players"]:
            delta = -leftovers[seat["id"]]
            if went_out_id and seat["id"] == went_out_id:
                delta += bonus
            seat["score"] += delta
            adjustments[seat["id"]] = delta
        top = max(seat["score"] for seat in state["players"])
        leaders = [seat["id"] for seat in state["players"] if seat["score"] == top]
        state["phase"] = "game_over"
        state["end_adjustments"] = adjustments
        state["winner_ids"] = leaders
        state["winner"] = leaders[0] if len(leaders) == 1 else None
        state["win_reason"] = "out" if went_out_id else "passes"
        state["current_actor_id"] = None

    def _advance(self, state: dict) -> None:
        order = [seat["id"] for seat in state["players"]]
        index = order.index(state["current_actor_id"])
        state["current_actor_id"] = order[(index + 1) % len(order)]
        state["turn_index"] += 1

    def _draw_up(self, state: dict, player_id: str) -> None:
        rack = state["racks"][player_id]
        while len(rack) < RACK_SIZE and state["bag"]:
            rack.append(state["bag"].pop())

    def _seat(self, state: dict, player_id: str) -> dict | None:
        return next((seat for seat in state["players"] if seat["id"] == player_id), None)

    def _log(
        self,
        state: dict,
        player_id: str,
        kind: str,
        score: int,
        formed: list[dict],
        bingo: bool,
        placements: list[dict],
    ) -> dict:
        seat = self._seat(state, player_id)
        entry = {
            "player_id": player_id,
            "nickname": seat["nickname"] if seat else "Player",
            "kind": kind,
            "score": score,
            "words": formed,
            "bingo": bingo,
            "placements": placements,
        }
        state["last_move"] = entry
        state["move_log"] = state["move_log"] + [entry]
        return entry

    @staticmethod
    def _public_tile(tile: dict) -> dict:
        letter = tile["l"]
        blank = bool(tile["b"])
        return {
            "id": tile["id"],
            "letter": letter,
            "blank": blank,
            "value": 0 if blank else tile_points(tile),
        }
