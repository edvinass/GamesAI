import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.games.base import GamePlugin

LOCATION_DIR = Path(__file__).parent / "locations"


class SpyfallEngine(GamePlugin):
    game_type = "spyfall"

    SPOKEN_PLACEHOLDER = "(spoken)"

    def default_settings(self) -> dict:
        return {
            "min_players": 3,
            "max_players": 8,
            "round_timer_sec": 480,
            "location_pack": "classic",
            "solo_practice": False,
            "same_room": False,
        }

    def validate_settings(self, settings: dict) -> dict:
        defaults = self.default_settings()
        merged = {**defaults, **(settings or {})}
        merged["min_players"] = max(3, min(8, int(merged.get("min_players", 3))))
        merged["max_players"] = max(merged["min_players"], min(8, int(merged.get("max_players", 8))))
        merged["round_timer_sec"] = max(0, int(merged.get("round_timer_sec", 480)))
        if merged["location_pack"] not in ("classic",):
            merged["location_pack"] = "classic"
        merged["solo_practice"] = bool(merged.get("solo_practice", False))
        merged["same_room"] = bool(merged.get("same_room", False))
        # Same-room voice play doesn't mix with solo AI practice.
        if merged["same_room"] and merged["solo_practice"]:
            merged["solo_practice"] = False
        return merged

    def _is_same_room(self, state: dict) -> bool:
        return bool((state.get("settings") or {}).get("same_room"))

    def _load_locations(self, pack: str) -> list[dict]:
        path = LOCATION_DIR / f"{pack}.json"
        with open(path) as f:
            return json.load(f)

    def _location_names(self, pack: str) -> list[str]:
        return [loc["name"] for loc in self._load_locations(pack)]

    def validate_lobby(self, players: list[dict], settings: dict) -> str | None:
        settings = self.validate_settings(settings)
        if settings.get("solo_practice"):
            humans = [p for p in players if not p.get("is_ai")]
            if len(humans) != 1:
                return "Solo practice requires exactly one human player"
            return None

        if settings.get("same_room") and any(p.get("is_ai") for p in players):
            return "Same-room mode does not allow AI players — remove them first"

        count = len(players)
        if count < settings["min_players"]:
            return f"Need at least {settings['min_players']} players"
        if count > settings["max_players"]:
            return f"Maximum {settings['max_players']} players allowed"
        return None

    def create_initial_state(self, players: list[dict], settings: dict) -> dict:
        settings = self.validate_settings(settings)
        pack = settings["location_pack"]
        locations = self._load_locations(pack)
        location = random.choice(locations)

        player_ids = [p["id"] for p in players]
        spy_id = random.choice(player_ids)
        residents = [p for p in players if p["id"] != spy_id]

        roles = list(location["roles"])
        random.shuffle(roles)
        assignments: dict[str, str | None] = {spy_id: None}
        for i, player in enumerate(residents):
            assignments[player["id"]] = roles[i % len(roles)]

        turn_order = player_ids[:]
        random.shuffle(turn_order)

        timer_ends_at = None
        if settings["round_timer_sec"] > 0:
            timer_ends_at = (
                datetime.now(timezone.utc) + timedelta(seconds=settings["round_timer_sec"])
            ).isoformat()

        return {
            "players": players,
            "settings": settings,
            "round_id": str(uuid.uuid4()),
            "phase": "questioning",
            "location": {"name": location["name"], "roles": location["roles"]},
            "spy_id": spy_id,
            "assignments": assignments,
            "turn_order": turn_order,
            "current_turn_index": 0,
            "pending_question": None,
            "question_log": [],
            "votes": {},
            "accused_player_id": None,
            "accusation_caller_id": None,
            "timer_ends_at": timer_ends_at,
            "all_location_names": self._location_names(pack),
            "winner": None,
            "win_reason": None,
            "last_action": None,
        }

    def _player_by_id(self, state: dict, player_id: str) -> dict | None:
        return next((p for p in state["players"] if p["id"] == player_id), None)

    def _current_turn_player_id(self, state: dict) -> str:
        return state["turn_order"][state["current_turn_index"]]

    def _advance_turn(self, state: dict) -> None:
        state["current_turn_index"] = (state["current_turn_index"] + 1) % len(state["turn_order"])

    def _is_spy(self, state: dict, player_id: str) -> bool:
        return str(state["spy_id"]) == str(player_id)

    def _check_timer_expired(self, state: dict) -> bool:
        timer_ends_at = state.get("timer_ends_at")
        if not timer_ends_at or state.get("phase") != "questioning":
            return False
        ends = datetime.fromisoformat(timer_ends_at)
        return datetime.now(timezone.utc) >= ends

    def _force_voting(self, state: dict, reason: str) -> list[dict]:
        state["phase"] = "voting"
        state["votes"] = {}
        state["pending_question"] = None
        state["last_action"] = {"type": "timer_expired", "reason": reason}
        return [{"type": "phase_changed", "phase": "voting", "reason": reason}]

    def _finish_game(self, state: dict, winner: str, reason: str) -> list[dict]:
        state["phase"] = "finished"
        state["winner"] = winner
        state["win_reason"] = reason
        state["pending_question"] = None
        return [{"type": "game_over", "winner": winner, "reason": reason}]

    def _resolve_votes(self, state: dict) -> list[dict]:
        vote_counts: dict[str, int] = {}
        for vote_for in state["votes"].values():
            if vote_for:
                vote_counts[vote_for] = vote_counts.get(vote_for, 0) + 1

        spy_id = state["spy_id"]
        spy_votes = vote_counts.get(spy_id, 0)
        total = len(state["votes"])
        if spy_votes > total / 2:
            return self._finish_game(state, "residents", "spy_voted_out")
        return self._finish_game(state, "spy", "vote_failed")

    def apply_action(self, state: dict, action: dict, player: dict) -> tuple[dict, list[dict]]:
        if state.get("winner"):
            raise ValueError("Game is already over")

        if self._check_timer_expired(state):
            events = self._force_voting(state, "timer_expired")
            if state.get("winner"):
                return state, events
            # Timer forced voting; if this action isn't cast_vote, reject unless it's still questioning transition
            if action.get("type") != "cast_vote":
                return state, events

        action_type = action.get("type")
        events: list[dict] = []
        player_id = player["id"]

        if action_type == "ask_question":
            if state["phase"] != "questioning":
                raise ValueError("Can only ask questions during questioning phase")
            if state.get("pending_question"):
                raise ValueError("Waiting for an answer first")
            if player_id != self._current_turn_player_id(state):
                raise ValueError("Not your turn to ask")

            target_id = str(action["target_player_id"])
            same_room = self._is_same_room(state)
            question = str(action.get("question") or "").strip()
            if same_room:
                question = self.SPOKEN_PLACEHOLDER
            elif not question:
                raise ValueError("Question cannot be empty")
            if target_id == player_id:
                raise ValueError("Cannot ask yourself a question")
            if not self._player_by_id(state, target_id):
                raise ValueError("Target player not found")

            state["pending_question"] = {
                "from_id": player_id,
                "to_id": target_id,
                "question": question,
                "spoken": same_room,
            }
            state["last_action"] = {
                "type": "ask_question",
                "from_id": player_id,
                "to_id": target_id,
                "question": question,
                "spoken": same_room,
            }
            events.append({"type": "question_asked", "from_id": player_id, "to_id": target_id})

        elif action_type == "answer_question":
            if state["phase"] != "questioning":
                raise ValueError("Can only answer during questioning phase")
            pending = state.get("pending_question")
            if not pending:
                raise ValueError("No pending question to answer")
            if player_id != pending["to_id"]:
                raise ValueError("You were not asked this question")

            same_room = self._is_same_room(state) or bool(pending.get("spoken"))
            answer = str(action.get("answer") or "").strip()
            if same_room:
                answer = self.SPOKEN_PLACEHOLDER
            elif not answer:
                raise ValueError("Answer cannot be empty")

            from_player = self._player_by_id(state, pending["from_id"])
            to_player = self._player_by_id(state, pending["to_id"])
            state["question_log"].append({
                "from_id": pending["from_id"],
                "to_id": pending["to_id"],
                "from_nickname": from_player["nickname"] if from_player else "?",
                "to_nickname": to_player["nickname"] if to_player else "?",
                "question": pending["question"],
                "answer": answer,
                "spoken": same_room,
            })
            state["pending_question"] = None
            self._advance_turn(state)
            state["last_action"] = {
                "type": "answer_question",
                "from_id": pending["from_id"],
                "to_id": pending["to_id"],
                "answer": answer,
                "spoken": same_room,
            }
            events.append({"type": "question_answered", "from_id": pending["from_id"], "to_id": pending["to_id"]})

        elif action_type == "call_accusation":
            if state["phase"] != "questioning":
                raise ValueError("Can only accuse during questioning phase")
            accused_id = str(action["accused_player_id"])
            if not self._player_by_id(state, accused_id):
                raise ValueError("Accused player not found")

            state["phase"] = "voting"
            state["votes"] = {}
            state["accused_player_id"] = accused_id
            state["accusation_caller_id"] = player_id
            state["pending_question"] = None
            state["last_action"] = {
                "type": "call_accusation",
                "caller_id": player_id,
                "accused_id": accused_id,
            }
            events.append({"type": "phase_changed", "phase": "voting", "accused_id": accused_id})

        elif action_type == "cast_vote":
            if state["phase"] != "voting":
                raise ValueError("Not in voting phase")
            if any(str(k) == str(player_id) for k in state["votes"]):
                raise ValueError("You already voted")

            vote_for = action.get("vote_for_player_id")
            if vote_for is not None:
                vote_for = str(vote_for)
                if not self._player_by_id(state, vote_for):
                    raise ValueError("Vote target not found")

            state["votes"][str(player_id)] = vote_for
            state["last_action"] = {"type": "cast_vote", "voter_id": str(player_id), "vote_for": vote_for}
            events.append({"type": "vote_cast", "voter_id": str(player_id)})

            if len(state["votes"]) >= len(state["players"]):
                events.extend(self._resolve_votes(state))

        elif action_type == "spy_guess_location":
            if state["phase"] != "questioning":
                raise ValueError("Can only guess location during questioning phase")
            if not self._is_spy(state, player_id):
                raise ValueError("Only the spy can guess the location")

            location_name = str(action["location_name"]).strip()
            valid_names = {name.lower() for name in state["all_location_names"]}
            if location_name.lower() not in valid_names:
                raise ValueError("Invalid location name")

            actual = state["location"]["name"]
            if location_name.lower() == actual.lower():
                events.extend(self._finish_game(state, "spy", "location_guessed"))
            else:
                events.extend(self._finish_game(state, "residents", "wrong_location_guess"))
            state["last_action"] = {
                "type": "spy_guess_location",
                "player_id": player_id,
                "guessed": location_name,
                "correct": location_name.lower() == actual.lower(),
            }

        else:
            raise ValueError(f"Unknown action: {action_type}")

        return state, events

    def get_public_state(self, state: dict, viewer_player: dict | None) -> dict:
        viewer_id = viewer_player["id"] if viewer_player else None
        game_over = state.get("phase") == "finished" or bool(state.get("winner"))
        is_spy = str(viewer_id) == str(state["spy_id"]) if viewer_id else False

        viewer_location = None
        viewer_role = None
        if viewer_id and not game_over:
            if is_spy:
                pass
            else:
                viewer_location = state["location"]["name"]
                viewer_role = state.get("assignments", {}).get(str(viewer_id))

        all_voted = len(state.get("votes", {})) >= len(state.get("players", []))
        votes_visible = game_over or all_voted

        raw_votes = state.get("votes", {})
        public_votes: dict[str, str | None] = {}
        if votes_visible:
            public_votes = {str(k): v for k, v in raw_votes.items()}
        elif viewer_id:
            # Reveal only the viewer's own vote so the UI can show "waiting for others"
            # without leaking everyone else's choice mid-vote.
            for key, value in raw_votes.items():
                if str(key) == str(viewer_id):
                    public_votes[str(viewer_id)] = value
                    break

        reveal_assignments = None
        if game_over:
            reveal_assignments = {
                pid: {"role": role, "is_spy": pid == state["spy_id"]}
                for pid, role in state.get("assignments", {}).items()
            }

        return {
            "phase": state["phase"],
            "round_id": state.get("round_id"),
            "question_log": state.get("question_log", []),
            "pending_question": state.get("pending_question"),
            "turn_order": state.get("turn_order", []),
            "current_turn_index": state.get("current_turn_index", 0),
            "current_turn_player_id": self._current_turn_player_id(state)
            if state.get("turn_order")
            else None,
            "timer_ends_at": state.get("timer_ends_at"),
            "votes": public_votes,
            "votes_cast_count": len(raw_votes),
            "votes_total": len(state.get("players", [])),
            "accused_player_id": state.get("accused_player_id"),
            "accusation_caller_id": state.get("accusation_caller_id"),
            "viewer_has_voted": bool(viewer_id)
            and any(str(k) == str(viewer_id) for k in raw_votes),
            "winner": state.get("winner"),
            "win_reason": state.get("win_reason"),
            "last_action": state.get("last_action"),
            "players": state.get("players", []),
            "is_spy": is_spy if viewer_id and not game_over else None,
            "viewer_location": viewer_location,
            "viewer_role": viewer_role,
            "location_names": state.get("all_location_names", []) if viewer_id and not game_over else None,
            "same_room": self._is_same_room(state),
            "revealed_location": state["location"]["name"] if game_over else None,
            "revealed_spy_id": state["spy_id"] if game_over else None,
            "revealed_assignments": reveal_assignments,
            "viewer_id": viewer_id,
        }

    def check_winner(self, state: dict) -> str | None:
        return state.get("winner")

    def get_current_actor(self, state: dict) -> dict | None:
        if state.get("winner") or state.get("phase") == "finished":
            return None

        if self._check_timer_expired(state):
            return None

        pending = state.get("pending_question")
        if pending:
            return self._player_by_id(state, pending["to_id"])

        phase = state.get("phase")
        if phase == "questioning":
            turn_id = self._current_turn_player_id(state)
            return self._player_by_id(state, turn_id)

        if phase == "voting":
            voted_ids = {str(pid) for pid in state.get("votes", {})}
            for player in state["players"]:
                if str(player["id"]) not in voted_ids:
                    return player
            return None

        return None
