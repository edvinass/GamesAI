import copy
from typing import Any

from app.games.base import GamePlugin
from app.games.poker.ai import normalize_ai_difficulty
from app.games.poker.deck import Deck
from app.games.poker.hand_eval import describe_hand, evaluate_hand
from app.games.poker.opponent_model import capture_to_call, on_hand_started, record_action


class PokerEngine(GamePlugin):
    game_type = "poker"

    BETTING_PHASES = ("preflop", "flop", "turn", "river")

    def default_settings(self) -> dict:
        return {
            "min_players": 2,
            "max_players": 6,
            "starting_chips": 1000,
            "small_blind": 5,
            "big_blind": 10,
            "solo_practice": False,
            "ai_difficulty": "medium",
            "ai_difficulties": {},
            "solo_ai_difficulties": ["medium", "medium"],
            "show_cards_on_fold": False,
        }

    def validate_settings(self, settings: dict) -> dict:
        defaults = self.default_settings()
        merged = {**defaults, **(settings or {})}
        merged["min_players"] = max(2, min(6, int(merged.get("min_players", 2))))
        merged["max_players"] = max(merged["min_players"], min(6, int(merged.get("max_players", 6))))
        merged["starting_chips"] = max(100, int(merged.get("starting_chips", 1000)))
        merged["small_blind"] = max(1, int(merged.get("small_blind", 5)))
        merged["big_blind"] = max(merged["small_blind"] + 1, int(merged.get("big_blind", 10)))
        merged["solo_practice"] = bool(merged.get("solo_practice", False))
        difficulty = str(merged.get("ai_difficulty", "medium")).lower()
        if difficulty == "normal":
            difficulty = "medium"
        if difficulty not in ("easy", "medium", "hard"):
            difficulty = "medium"
        merged["ai_difficulty"] = difficulty
        raw_difficulties = merged.get("ai_difficulties") or {}
        merged["ai_difficulties"] = {
            str(player_id): normalize_ai_difficulty(level)
            for player_id, level in raw_difficulties.items()
        }
        solo_defaults = list(merged.get("solo_ai_difficulties") or ["medium", "medium"])
        while len(solo_defaults) < 2:
            solo_defaults.append("medium")
        merged["solo_ai_difficulties"] = [
            normalize_ai_difficulty(level) for level in solo_defaults[:2]
        ]
        merged["show_cards_on_fold"] = bool(merged.get("show_cards_on_fold", False))
        return merged

    def assign_lobby_roles(self, players: list[dict], settings: dict) -> list[dict]:
        difficulties = settings.get("ai_difficulties") or {}
        default = settings.get("ai_difficulty", "medium")
        for player in players:
            if player.get("is_ai"):
                player["ai_difficulty"] = normalize_ai_difficulty(
                    difficulties.get(player["id"], default)
                )
        return players

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
        seat_order = [p["id"] for p in players]
        player_states = {
            p["id"]: {
                "id": p["id"],
                "nickname": p["nickname"],
                "is_ai": p.get("is_ai", False),
                "ai_difficulty": normalize_ai_difficulty(
                    p.get("ai_difficulty")
                    or (settings.get("ai_difficulties") or {}).get(p["id"])
                    or settings.get("ai_difficulty")
                )
                if p.get("is_ai")
                else None,
                "chips": settings["starting_chips"],
                "hole_cards": [],
                "bet_this_round": 0,
                "total_bet_hand": 0,
                "acted_this_round": False,
                "status": "active",
            }
            for p in players
        }
        state = {
            "phase": "preflop",
            "hand_number": 0,
            "dealer_index": -1,
            "seat_order": seat_order,
            "community_cards": [],
            "deck": [],
            "players": player_states,
            "current_actor_id": None,
            "current_bet": 0,
            "min_raise": settings["big_blind"],
            "last_raise_size": settings["big_blind"],
            "last_action": None,
            "winners": [],
            "winner": None,
            "win_reason": None,
            "settings": settings,
            "host_id": settings.get("host_id") or (players[0]["id"] if players else None),
            "opponent_stats": {},
        }
        return self._start_hand(state)

    def apply_action(
        self, state: dict, action: dict, player: dict
    ) -> tuple[dict, list[dict]]:
        action_type = action.get("type")
        events: list[dict] = []

        if action_type == "next_hand":
            if state["phase"] != "hand_complete":
                raise ValueError("Can only start next hand after hand completes")
            if str(player["id"]) != str(state.get("host_id")):
                raise ValueError("Only host can start next hand")
            if state.get("winner"):
                raise ValueError("Game is over")
            state = self._start_hand(state)
            events.append({"type": "hand_started", "hand_number": state["hand_number"]})
            return state, events

        if state["phase"] not in self.BETTING_PHASES:
            raise ValueError("No betting actions allowed in current phase")

        actor_id = str(player["id"])
        if str(state.get("current_actor_id")) != actor_id:
            raise ValueError("Not your turn")

        pstate = state["players"][actor_id]
        if pstate["status"] != "active":
            raise ValueError("You cannot act")

        to_call_before = capture_to_call(state, actor_id)

        if action_type == "fold":
            pstate["status"] = "folded"
            pstate["acted_this_round"] = True
            state["last_action"] = {"type": "fold", "player_id": actor_id}
            events.append({"type": "player_folded", "player_id": actor_id})
        elif action_type == "check":
            if self._bet_to_call(state, pstate) > 0:
                raise ValueError("Cannot check facing a bet")
            pstate["acted_this_round"] = True
            state["last_action"] = {"type": "check", "player_id": actor_id}
            events.append({"type": "player_checked", "player_id": actor_id})
        elif action_type == "call":
            to_call = self._bet_to_call(state, pstate)
            if to_call <= 0:
                raise ValueError("Nothing to call")
            self._commit_bet(state, actor_id, to_call)
            pstate["acted_this_round"] = True
            state["last_action"] = {"type": "call", "player_id": actor_id, "amount": to_call}
            events.append({"type": "player_called", "player_id": actor_id, "amount": to_call})
        elif action_type == "raise":
            total = int(action.get("amount", 0))
            self._apply_raise(state, actor_id, total)
            self._mark_raise(state, actor_id)
            state["last_action"] = {
                "type": "raise",
                "player_id": actor_id,
                "amount": pstate["bet_this_round"],
            }
            events.append(
                {
                    "type": "player_raised",
                    "player_id": actor_id,
                    "amount": pstate["bet_this_round"],
                }
            )
        elif action_type == "all_in":
            to_call = self._bet_to_call(state, pstate)
            total = pstate["bet_this_round"] + pstate["chips"]
            if total <= state["current_bet"]:
                self._commit_bet(state, actor_id, pstate["chips"])
                pstate["acted_this_round"] = True
                state["last_action"] = {"type": "all_in", "player_id": actor_id, "amount": total}
                events.append({"type": "player_all_in", "player_id": actor_id, "amount": total})
            else:
                self._apply_raise(state, actor_id, total)
                self._mark_raise(state, actor_id)
                state["last_action"] = {
                    "type": "all_in",
                    "player_id": actor_id,
                    "amount": pstate["bet_this_round"],
                }
                events.append(
                    {
                        "type": "player_all_in",
                        "player_id": actor_id,
                        "amount": pstate["bet_this_round"],
                    }
                )
        else:
            raise ValueError(f"Unknown action: {action_type}")

        record_action(state, actor_id, action, to_call_before=to_call_before)

        remaining = self._players_in_hand(state)
        if len(remaining) == 1:
            winner_id = remaining[0]
            state = self._award_uncontested(state, winner_id)
            events.append({"type": "hand_won", "player_id": winner_id, "reason": "fold"})
            return state, events

        if self._betting_round_complete(state):
            state = self._advance_street(state)
            if state["phase"] == "showdown":
                state = self._resolve_showdown(state)
                events.append({"type": "showdown"})
            elif state["phase"] == "hand_complete":
                events.append({"type": "hand_complete"})
            else:
                events.append({"type": "street_dealt", "phase": state["phase"]})
        else:
            self._set_next_actor(state)

        return state, events

    def get_public_state(self, state: dict, viewer_player: dict | None) -> dict:
        viewer_id = str(viewer_player["id"]) if viewer_player else None
        settings = state.get("settings", {})
        show_cards_on_fold = settings.get("show_cards_on_fold", False)
        win_by_fold = state.get("win_by_fold", False)
        reveal_hands = state["phase"] in ("showdown", "hand_complete", "game_over")
        if win_by_fold and not show_cards_on_fold:
            reveal_hands = False
        players = []
        for pid in state["seat_order"]:
            p = state["players"][pid]
            entry = {
                "id": p["id"],
                "nickname": p["nickname"],
                "is_ai": p["is_ai"],
                "chips": p["chips"],
                "bet_this_round": p["bet_this_round"],
                "total_bet_hand": p["total_bet_hand"],
                "status": p["status"],
                "hole_cards": [],
            }
            if reveal_hands and p["status"] != "folded":
                entry["hole_cards"] = copy.deepcopy(p["hole_cards"])
                all_cards = p["hole_cards"] + state["community_cards"]
                if len(all_cards) >= 5:
                    entry["hand_description"] = describe_hand(all_cards)
            elif viewer_id and str(pid) == viewer_id and p["status"] != "folded":
                entry["hole_cards"] = copy.deepcopy(p["hole_cards"])
            players.append(entry)

        return {
            "phase": state["phase"],
            "hand_number": state["hand_number"],
            "dealer_index": state["dealer_index"],
            "dealer_player_id": state["seat_order"][state["dealer_index"]]
            if state["dealer_index"] >= 0
            else None,
            "seat_order": state["seat_order"],
            "community_cards": copy.deepcopy(state["community_cards"]),
            "players": players,
            "pot_total": self._pot_total(state),
            "pots": self._preview_pots(state),
            "current_actor_id": state.get("current_actor_id"),
            "current_bet": state["current_bet"],
            "min_raise": state["min_raise"],
            "last_action": state.get("last_action"),
            "winners": copy.deepcopy(state.get("winners", [])),
            "winner": state.get("winner"),
            "win_reason": state.get("win_reason"),
            "settings": state.get("settings", {}),
            "host_id": state.get("host_id"),
            "viewer_id": viewer_id,
            "bet_to_call": self._bet_to_call_for_viewer(state, viewer_id),
            "can_check": self._can_check_for_viewer(state, viewer_id),
            "min_raise_to": self._min_raise_to_for_viewer(state, viewer_id),
            "max_raise_to": self._max_raise_to_for_viewer(state, viewer_id),
            "raise_options": self._legal_raise_to_amounts(state, viewer_id)
            if viewer_id
            else [],
            "raise_increment": self._raise_increment(state),
            "win_by_fold": state.get("win_by_fold", False),
        }

    def check_winner(self, state: dict) -> str | None:
        return state.get("winner")

    def get_current_actor(self, state: dict) -> dict | None:
        if state.get("winner") or state["phase"] in ("hand_complete", "game_over", "showdown"):
            return None
        actor_id = state.get("current_actor_id")
        if not actor_id:
            return None
        p = state["players"].get(actor_id)
        if not p or not p.get("is_ai"):
            return None
        return p

    def _start_hand(self, state: dict) -> dict:
        settings = state["settings"]
        eligible = [
            pid
            for pid in state["seat_order"]
            if state["players"][pid]["chips"] > 0
        ]
        if len(eligible) < 2:
            state["phase"] = "game_over"
            if len(eligible) == 1:
                state["winner"] = eligible[0]
                state["win_reason"] = "last_player_standing"
            return state

        state["hand_number"] = state.get("hand_number", 0) + 1
        state["dealer_index"] = self._next_dealer_index(state, eligible)
        state["community_cards"] = []
        state["winners"] = []
        state["last_action"] = None
        state["phase"] = "preflop"
        state["win_by_fold"] = False

        for pid in state["seat_order"]:
            p = state["players"][pid]
            p["hole_cards"] = []
            p["bet_this_round"] = 0
            p["total_bet_hand"] = 0
            p["acted_this_round"] = False
            if p["chips"] > 0:
                p["status"] = "active"
            else:
                p["status"] = "eliminated"

        deck = Deck()
        deck.shuffle()
        for pid in eligible:
            state["players"][pid]["hole_cards"] = deck.deal(2)
        state["deck"] = deck.to_list()

        self._post_blinds(state, eligible)
        on_hand_started(state, eligible)
        self._set_first_actor_preflop(state, eligible)
        return state

    def _next_dealer_index(self, state: dict, eligible: list[str]) -> int:
        if state["dealer_index"] < 0:
            return state["seat_order"].index(eligible[0])
        current_dealer = state["seat_order"][state["dealer_index"]]
        start = (state["seat_order"].index(current_dealer) + 1) % len(state["seat_order"])
        for i in range(len(state["seat_order"])):
            idx = (start + i) % len(state["seat_order"])
            pid = state["seat_order"][idx]
            if pid in eligible:
                return idx
        return state["seat_order"].index(eligible[0])

    def _post_blinds(self, state: dict, eligible: list[str]) -> None:
        settings = state["settings"]
        sb_amount = settings["small_blind"]
        bb_amount = settings["big_blind"]
        dealer_idx = state["dealer_index"]
        n = len(eligible)

        if n == 2:
            sb_pid = state["seat_order"][dealer_idx]
            bb_idx = self._next_eligible_index(state, dealer_idx, eligible)
            bb_pid = state["seat_order"][bb_idx]
        else:
            sb_idx = self._next_eligible_index(state, dealer_idx, eligible)
            sb_pid = state["seat_order"][sb_idx]
            bb_idx = self._next_eligible_index(state, sb_idx, eligible)
            bb_pid = state["seat_order"][bb_idx]

        self._commit_bet(state, sb_pid, min(sb_amount, state["players"][sb_pid]["chips"]))
        self._commit_bet(state, bb_pid, min(bb_amount, state["players"][bb_pid]["chips"]))

        state["current_bet"] = state["players"][bb_pid]["bet_this_round"]
        state["min_raise"] = bb_amount
        state["last_raise_size"] = bb_amount

    def _next_eligible_index(self, state: dict, from_index: int, eligible: list[str]) -> int:
        for i in range(1, len(state["seat_order"]) + 1):
            idx = (from_index + i) % len(state["seat_order"])
            if state["seat_order"][idx] in eligible:
                return idx
        raise ValueError("No eligible seat")

    def _set_first_actor_preflop(self, state: dict, eligible: list[str]) -> None:
        dealer_idx = state["dealer_index"]
        if len(eligible) == 2:
            first_idx = dealer_idx
        else:
            bb_idx = None
            for i in range(1, len(state["seat_order"]) + 1):
                idx = (dealer_idx + i) % len(state["seat_order"])
                pid = state["seat_order"][idx]
                if pid in eligible and state["players"][pid]["bet_this_round"] == state["current_bet"]:
                    bb_idx = idx
                    break
            first_idx = self._next_eligible_index(state, bb_idx, eligible) if bb_idx is not None else dealer_idx
        state["current_actor_id"] = state["seat_order"][first_idx]
        if state["players"][state["current_actor_id"]]["status"] != "active":
            self._set_next_actor(state)

    def _set_first_actor_postflop(self, state: dict) -> None:
        eligible = [pid for pid in state["seat_order"] if self._in_hand(state, pid)]
        first_idx = self._next_eligible_index(state, state["dealer_index"], eligible)
        state["current_actor_id"] = state["seat_order"][first_idx]
        if state["players"][state["current_actor_id"]]["status"] != "active":
            self._set_next_actor(state)

    def _set_next_actor(self, state: dict) -> None:
        if not state.get("current_actor_id"):
            return
        current_idx = state["seat_order"].index(state["current_actor_id"])
        for i in range(1, len(state["seat_order"]) + 1):
            idx = (current_idx + i) % len(state["seat_order"])
            pid = state["seat_order"][idx]
            p = state["players"][pid]
            if p["status"] == "active" and (
                self._bet_to_call(state, p) > 0 or p["chips"] > 0
            ):
                state["current_actor_id"] = pid
                return
        state["current_actor_id"] = None

    def _bet_to_call(self, state: dict, pstate: dict) -> int:
        return max(0, state["current_bet"] - pstate["bet_this_round"])

    def _commit_bet(self, state: dict, player_id: str, amount: int) -> None:
        p = state["players"][player_id]
        amount = min(amount, p["chips"])
        p["chips"] -= amount
        p["bet_this_round"] += amount
        p["total_bet_hand"] += amount
        if p["chips"] == 0:
            p["status"] = "all_in"

    def _apply_raise(self, state: dict, player_id: str, total_bet: int) -> None:
        p = state["players"][player_id]
        current = p["bet_this_round"]
        if total_bet <= state["current_bet"]:
            raise ValueError("Raise must exceed current bet")
        needed = total_bet - current
        if needed > p["chips"]:
            raise ValueError("Not enough chips")
        min_total = state["current_bet"] + state["min_raise"]
        if total_bet < min_total and needed < p["chips"]:
            raise ValueError(f"Minimum raise to {min_total}")
        if needed < p["chips"] and total_bet not in self._legal_raise_to_amounts(
            state, player_id
        ):
            legal = self._legal_raise_to_amounts(state, player_id)
            hint = legal[0] if legal else min_total
            raise ValueError(f"Raises must be in {self._raise_increment(state)} chip increments (min {hint})")
        raise_size = total_bet - state["current_bet"]
        self._commit_bet(state, player_id, needed)
        if raise_size >= state["min_raise"]:
            state["last_raise_size"] = raise_size
            state["min_raise"] = raise_size
        state["current_bet"] = p["bet_this_round"]

    def _players_in_hand(self, state: dict) -> list[str]:
        return [
            pid
            for pid in state["seat_order"]
            if state["players"][pid]["status"] in ("active", "all_in")
        ]

    def _in_hand(self, state: dict, player_id: str) -> bool:
        return state["players"][player_id]["status"] in ("active", "all_in")

    def _mark_raise(self, state: dict, raiser_id: str) -> None:
        state["players"][raiser_id]["acted_this_round"] = True
        for pid in state["seat_order"]:
            p = state["players"][pid]
            if p["status"] == "active" and pid != raiser_id:
                p["acted_this_round"] = False

    def _reset_acted_for_street(self, state: dict) -> None:
        for pid in state["seat_order"]:
            p = state["players"][pid]
            if p["status"] == "active":
                p["acted_this_round"] = False

    def _betting_round_complete(self, state: dict) -> bool:
        active = [
            state["players"][pid]
            for pid in state["seat_order"]
            if self._in_hand(state, pid)
        ]
        if len(active) <= 1:
            return True
        can_act = [p for p in active if p["status"] == "active"]
        if not can_act:
            return True
        if not all(p["acted_this_round"] for p in can_act):
            return False
        return all(p["bet_this_round"] == state["current_bet"] for p in can_act)

    def _advance_street(self, state: dict) -> dict:
        for pid in state["seat_order"]:
            state["players"][pid]["bet_this_round"] = 0
        self._reset_acted_for_street(state)
        state["current_bet"] = 0
        state["min_raise"] = state["settings"]["big_blind"]
        state["last_raise_size"] = state["settings"]["big_blind"]

        deck = Deck.from_list(state["deck"])
        phase = state["phase"]
        if phase == "preflop":
            deck.burn()
            state["community_cards"].extend(deck.deal(3))
            state["phase"] = "flop"
        elif phase == "flop":
            deck.burn()
            state["community_cards"].extend(deck.deal(1))
            state["phase"] = "turn"
        elif phase == "turn":
            deck.burn()
            state["community_cards"].extend(deck.deal(1))
            state["phase"] = "river"
        elif phase == "river":
            state["phase"] = "showdown"
            state["deck"] = deck.to_list()
            return state
        state["deck"] = deck.to_list()

        if self._should_run_out(state):
            return self._run_out_board(state)

        self._set_first_actor_postflop(state)
        if self._betting_round_complete(state):
            return self._advance_street(state)
        return state

    def _should_run_out(self, state: dict) -> bool:
        active = [pid for pid in state["seat_order"] if state["players"][pid]["status"] == "active"]
        return len(active) <= 1

    def _run_out_board(self, state: dict) -> dict:
        deck = Deck.from_list(state["deck"])
        while len(state["community_cards"]) < 5:
            deck.burn()
            needed = 5 - len(state["community_cards"])
            if needed >= 3:
                state["community_cards"].extend(deck.deal(3))
            else:
                state["community_cards"].extend(deck.deal(needed))
        state["deck"] = deck.to_list()
        state["phase"] = "showdown"
        return self._resolve_showdown(state)

    def _resolve_showdown(self, state: dict) -> dict:
        pots = self._calculate_side_pots(state)
        winners: list[dict] = []
        for pot in pots:
            contenders = [
                pid for pid in pot["eligible_player_ids"] if self._in_hand(state, pid)
            ]
            if not contenders:
                continue
            best_score = None
            best_ids: list[str] = []
            best_cards: dict[str, list[dict[str, str]]] = {}
            for pid in contenders:
                cards = state["players"][pid]["hole_cards"] + state["community_cards"]
                score = evaluate_hand(cards)
                if best_score is None or score > best_score:
                    best_score = score
                    best_ids = [pid]
                    best_cards = {pid: cards}
                elif score == best_score:
                    best_ids.append(pid)
                    best_cards[pid] = cards
            share = pot["amount"] // len(best_ids)
            remainder = pot["amount"] % len(best_ids)
            for i, pid in enumerate(best_ids):
                award = share + (1 if i < remainder else 0)
                state["players"][pid]["chips"] += award
                winners.append(
                    {
                        "player_id": pid,
                        "amount": award,
                        "hand": describe_hand(best_cards[pid]),
                    }
                )
        state["winners"] = winners
        state["phase"] = "hand_complete"
        state["current_actor_id"] = None
        state["win_by_fold"] = False

        remaining = [pid for pid in state["seat_order"] if state["players"][pid]["chips"] > 0]
        if len(remaining) <= 1:
            state["phase"] = "game_over"
            if len(remaining) == 1:
                state["winner"] = remaining[0]
                state["win_reason"] = "last_player_standing"
        return state

    def _award_uncontested(self, state: dict, winner_id: str) -> dict:
        total = self._pot_total(state)
        state["players"][winner_id]["chips"] += total
        winner_contribution = state["players"][winner_id]["total_bet_hand"]
        contested_winnings = total - winner_contribution
        state["winners"] = [{"player_id": winner_id, "amount": contested_winnings, "hand": None}]
        for pid in state["seat_order"]:
            state["players"][pid]["bet_this_round"] = 0
            state["players"][pid]["total_bet_hand"] = 0
        state["phase"] = "hand_complete"
        state["current_actor_id"] = None
        state["win_by_fold"] = True
        remaining = [pid for pid in state["seat_order"] if state["players"][pid]["chips"] > 0]
        if len(remaining) <= 1:
            state["phase"] = "game_over"
            if len(remaining) == 1:
                state["winner"] = remaining[0]
                state["win_reason"] = "last_player_standing"
        return state

    def _pot_total(self, state: dict) -> int:
        return sum(p["total_bet_hand"] for p in state["players"].values())

    def _preview_pots(self, state: dict) -> list[dict]:
        if state["phase"] in ("showdown", "hand_complete"):
            return self._calculate_side_pots(state)
        total = self._pot_total(state)
        eligible = [pid for pid in state["seat_order"] if self._in_hand(state, pid)]
        return [{"amount": total, "eligible_player_ids": eligible}]

    def _calculate_side_pots(self, state: dict) -> list[dict]:
        contributions = [
            (pid, state["players"][pid]["total_bet_hand"])
            for pid in state["seat_order"]
            if state["players"][pid]["total_bet_hand"] > 0
        ]
        if not contributions:
            return []
        contributions.sort(key=lambda item: item[1])
        pots: list[dict] = []
        prev = 0
        remaining = {pid for pid, _ in contributions}
        levels = sorted(set(amount for _, amount in contributions))
        for level in levels:
            if level <= prev:
                continue
            layer = level - prev
            eligible = [pid for pid, amount in contributions if amount >= level]
            amount = layer * len(eligible)
            if amount > 0:
                pots.append({"amount": amount, "eligible_player_ids": eligible})
            prev = level
        return pots

    def _raise_increment(self, state: dict) -> int:
        return state["settings"]["big_blind"]

    def _legal_raise_to_amounts(self, state: dict, player_id: str | None) -> list[int]:
        if not player_id:
            return []
        p = state["players"].get(player_id)
        if not p or p["status"] != "active":
            return []
        increment = self._raise_increment(state)
        current_bet = state["current_bet"]
        min_raise = state["min_raise"]
        max_to = p["bet_this_round"] + p["chips"]
        min_to = max(current_bet + min_raise, p["bet_this_round"] + 1)
        if min_to > max_to:
            return []

        min_raise_size = min_raise
        if min_raise_size % increment != 0:
            min_raise_size += increment - (min_raise_size % increment)

        first = current_bet + min_raise_size
        if first < min_to:
            steps = (min_to - first + increment - 1) // increment
            first += steps * increment

        amounts: list[int] = []
        target = first
        while target <= max_to:
            amounts.append(target)
            target += increment
        return amounts

    def _bet_to_call_for_viewer(self, state: dict, viewer_id: str | None) -> int:
        if not viewer_id or state["phase"] not in self.BETTING_PHASES:
            return 0
        p = state["players"].get(viewer_id)
        if not p or p["status"] != "active":
            return 0
        return self._bet_to_call(state, p)

    def _can_check_for_viewer(self, state: dict, viewer_id: str | None) -> bool:
        return self._bet_to_call_for_viewer(state, viewer_id) == 0

    def _min_raise_to_for_viewer(self, state: dict, viewer_id: str | None) -> int:
        if not viewer_id:
            return 0
        p = state["players"].get(viewer_id)
        if not p:
            return 0
        return max(state["current_bet"] + state["min_raise"], p["bet_this_round"] + 1)

    def _max_raise_to_for_viewer(self, state: dict, viewer_id: str | None) -> int:
        if not viewer_id:
            return 0
        p = state["players"].get(viewer_id)
        if not p:
            return 0
        return p["bet_this_round"] + p["chips"]
