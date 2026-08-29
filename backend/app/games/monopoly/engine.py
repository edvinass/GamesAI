"""Monopoly game engine — near-classic rules with auctions and trading."""

from __future__ import annotations

import random
from copy import deepcopy
from typing import Any

from app.games.base import GamePlugin
from app.games.monopoly.board import (
    COLOR_SETS,
    RAILROADS,
    SPACES,
    TOKEN_COLORS,
    UTILITIES,
    fresh_decks,
    is_ownable,
    railroad_rent,
    space_by_id,
    utility_rent,
)

DIFFICULTIES = ("easy", "medium", "hard")


def normalize_ai_difficulty(level: Any) -> str:
    value = str(level or "medium").lower()
    if value == "normal":
        value = "medium"
    return value if value in DIFFICULTIES else "medium"


class MonopolyEngine(GamePlugin):
    game_type = "monopoly"

    def default_settings(self) -> dict:
        return {
            "min_players": 2,
            "max_players": 6,
            "starting_cash": 1500,
            "solo_practice": False,
            "ai_difficulty": "medium",
            "ai_difficulties": {},
            "solo_ai_difficulties": ["medium", "medium"],
        }

    def validate_settings(self, settings: dict) -> dict:
        defaults = self.default_settings()
        merged = {**defaults, **(settings or {})}
        merged["min_players"] = max(2, min(6, int(merged.get("min_players", 2))))
        merged["max_players"] = max(
            merged["min_players"], min(6, int(merged.get("max_players", 6)))
        )
        merged["starting_cash"] = max(500, min(5000, int(merged.get("starting_cash", 1500))))
        merged["solo_practice"] = bool(merged.get("solo_practice", False))
        merged["ai_difficulty"] = normalize_ai_difficulty(merged.get("ai_difficulty"))
        raw = merged.get("ai_difficulties") or {}
        merged["ai_difficulties"] = {
            str(pid): normalize_ai_difficulty(level) for pid, level in raw.items()
        }
        solo = list(merged.get("solo_ai_difficulties") or ["medium", "medium"])
        while len(solo) < 2:
            solo.append("medium")
        merged["solo_ai_difficulties"] = [normalize_ai_difficulty(x) for x in solo[:2]]
        if "host_id" in (settings or {}):
            merged["host_id"] = settings["host_id"]
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
        if len(players) < 2:
            raise ValueError("Monopoly requires at least 2 players")
        if len(players) > 6:
            raise ValueError("Monopoly supports at most 6 players")

        seed = settings.get("seed")
        rng = random.Random(seed)

        seat_order = [str(p["id"]) for p in players]
        player_states: dict[str, dict] = {}
        for i, p in enumerate(players):
            pid = str(p["id"])
            player_states[pid] = {
                "id": pid,
                "nickname": p.get("nickname", f"Player {i + 1}"),
                "is_ai": bool(p.get("is_ai", False)),
                "ai_difficulty": (
                    normalize_ai_difficulty(
                        p.get("ai_difficulty")
                        or (settings.get("ai_difficulties") or {}).get(pid)
                        or settings.get("ai_difficulty")
                    )
                    if p.get("is_ai")
                    else None
                ),
                "cash": settings["starting_cash"],
                "position": 0,
                "in_jail": False,
                "jail_turns": 0,
                "get_out_cards": 0,
                "bankrupt": False,
                "token_color": TOKEN_COLORS[i % len(TOKEN_COLORS)],
            }

        properties: dict[str, dict] = {}
        for space in SPACES:
            if is_ownable(space):
                properties[str(space["id"])] = {
                    "owner_id": None,
                    "mortgaged": False,
                    "houses": 0,  # 0-4 houses, 5 = hotel
                }

        chance, community = fresh_decks(rng)

        state = {
            "phase": "awaiting_roll",
            "turn_phase": "awaiting_roll",
            "spaces": [
                {
                    "id": s["id"],
                    "name": s["name"],
                    "kind": s["kind"],
                    "color": s.get("color"),
                    "price": s.get("price"),
                    "house_cost": s.get("house_cost"),
                    "rents": s.get("rents"),
                    "mortgage": s.get("mortgage"),
                }
                for s in SPACES
            ],
            "properties": properties,
            "players": player_states,
            "seat_order": seat_order,
            "current_player_index": 0,
            "current_actor_id": seat_order[0],
            "doubles_count": 0,
            "last_dice": None,
            "can_roll_again": False,
            "auction": None,
            "debt": None,
            "pending_trade": None,
            "chance_deck": chance,
            "community_deck": community,
            "chance_discard": [],
            "community_discard": [],
            "last_card": None,
            "log": [{"type": "game_start", "message": "Game started"}],
            "winner": None,
            "win_reason": None,
            "settings": settings,
            "host_id": settings.get("host_id") or seat_order[0],
            "houses_remaining": 32,
            "hotels_remaining": 12,
        }
        return state

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply_action(
        self, state: dict, action: dict, player: dict
    ) -> tuple[dict, list[dict]]:
        state = deepcopy(state)
        events: list[dict] = []
        pid = str(player["id"])
        action_type = action.get("type")

        if state.get("winner") or state["phase"] == "finished":
            raise ValueError("Game is already over")

        handlers = {
            "roll": self._handle_roll,
            "buy": self._handle_buy,
            "decline": self._handle_decline,
            "bid": self._handle_bid,
            "pass_auction": self._handle_pass_auction,
            "pay_jail": self._handle_pay_jail,
            "use_jail_card": self._handle_use_jail_card,
            "roll_jail": self._handle_roll_jail,
            "build": self._handle_build,
            "sell_building": self._handle_sell_building,
            "mortgage": self._handle_mortgage,
            "unmortgage": self._handle_unmortgage,
            "propose_trade": self._handle_propose_trade,
            "accept_trade": self._handle_accept_trade,
            "reject_trade": self._handle_reject_trade,
            "cancel_trade": self._handle_cancel_trade,
            "pay_debt": self._handle_pay_debt,
            "declare_bankruptcy": self._handle_declare_bankruptcy,
            "end_turn": self._handle_end_turn,
            "resign": self._handle_resign,
        }
        handler = handlers.get(action_type)
        if not handler:
            raise ValueError(f"Unknown action: {action_type}")
        return handler(state, action, pid, events)

    def get_public_state(self, state: dict, viewer_player: dict | None) -> dict:
        public = deepcopy(state)
        # Ensure title-deed fields are present (older in-progress games may lack them)
        by_id = {s["id"]: s for s in SPACES}
        enriched = []
        for space in public.get("spaces") or []:
            src = by_id.get(space.get("id"), {})
            enriched.append(
                {
                    **space,
                    "house_cost": space.get("house_cost", src.get("house_cost")),
                    "rents": space.get("rents") or src.get("rents"),
                    "mortgage": space.get("mortgage", src.get("mortgage")),
                    "price": space.get("price", src.get("price")),
                }
            )
        public["spaces"] = enriched
        # Decks are hidden; expose counts only
        public["chance_remaining"] = len(state.get("chance_deck") or [])
        public["community_remaining"] = len(state.get("community_deck") or [])
        public.pop("chance_deck", None)
        public.pop("community_deck", None)
        public.pop("chance_discard", None)
        public.pop("community_discard", None)
        public["turn_phase"] = state.get("phase")
        return public

    def check_winner(self, state: dict) -> str | None:
        return state.get("winner")

    def get_current_actor(self, state: dict) -> dict | None:
        if state.get("winner") or state.get("phase") == "finished":
            return None
        actor_id = state.get("current_actor_id")
        if not actor_id:
            return None
        player = state["players"].get(str(actor_id))
        if not player or player.get("bankrupt") or not player.get("is_ai"):
            return None
        return player

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _log(self, state: dict, message: str, **extra) -> None:
        entry = {"type": "log", "message": message, **extra}
        state["log"] = (state.get("log") or [])[-40:] + [entry]

    def _active_players(self, state: dict) -> list[str]:
        return [
            pid
            for pid in state["seat_order"]
            if not state["players"][pid]["bankrupt"]
        ]

    def _current_player_id(self, state: dict) -> str:
        return state["seat_order"][state["current_player_index"]]

    def _require_actor(self, state: dict, pid: str) -> None:
        if str(state.get("current_actor_id")) != pid:
            raise ValueError("Not your turn")

    def _require_turn_player(self, state: dict, pid: str) -> None:
        if self._current_player_id(state) != pid:
            raise ValueError("Not your turn")

    def _player(self, state: dict, pid: str) -> dict:
        p = state["players"].get(pid)
        if not p or p["bankrupt"]:
            raise ValueError("Invalid player")
        return p

    def _owns_color_set(self, state: dict, owner_id: str, color: str) -> bool:
        for sid in COLOR_SETS[color]:
            prop = state["properties"][str(sid)]
            if prop["owner_id"] != owner_id or prop["mortgaged"]:
                return False
        return True

    def _count_owned(self, state: dict, owner_id: str, space_ids: list[int]) -> int:
        return sum(
            1
            for sid in space_ids
            if state["properties"][str(sid)]["owner_id"] == owner_id
            and not state["properties"][str(sid)]["mortgaged"]
        )

    def _property_rent(
        self, state: dict, space_id: int, dice_total: int
    ) -> tuple[int, str | None]:
        space = space_by_id(space_id)
        prop = state["properties"][str(space_id)]
        owner_id = prop["owner_id"]
        if not owner_id or prop["mortgaged"]:
            return 0, None
        if space["kind"] == "property":
            houses = prop["houses"]
            rents = space["rents"]
            if houses == 0 and self._owns_color_set(state, owner_id, space["color"]):
                return rents[0] * 2, owner_id
            return rents[min(houses, 5)], owner_id
        if space["kind"] == "railroad":
            count = self._count_owned(state, owner_id, RAILROADS)
            return railroad_rent(count), owner_id
        if space["kind"] == "utility":
            count = self._count_owned(state, owner_id, UTILITIES)
            return utility_rent(count, dice_total), owner_id
        return 0, None

    def _set_phase(self, state: dict, phase: str, actor_id: str | None = None) -> None:
        state["phase"] = phase
        state["turn_phase"] = phase
        if actor_id is not None:
            state["current_actor_id"] = actor_id

    def _advance_to_next_player(self, state: dict) -> None:
        n = len(state["seat_order"])
        idx = state["current_player_index"]
        for _ in range(n):
            idx = (idx + 1) % n
            pid = state["seat_order"][idx]
            if not state["players"][pid]["bankrupt"]:
                state["current_player_index"] = idx
                state["doubles_count"] = 0
                state["can_roll_again"] = False
                state["last_dice"] = None
                state["debt"] = None
                state["auction"] = None
                self._set_phase(state, "awaiting_roll", pid)
                return
        # Should not happen — check win separately
        self._check_last_standing(state)

    def _check_last_standing(self, state: dict) -> None:
        alive = self._active_players(state)
        if len(alive) == 1:
            state["winner"] = alive[0]
            state["win_reason"] = "last_standing"
            self._set_phase(state, "finished", None)
            self._log(state, f"{state['players'][alive[0]]['nickname']} wins!")
        elif len(alive) == 0:
            state["winner"] = None
            state["win_reason"] = "draw"
            self._set_phase(state, "finished", None)

    def _finish_turn_or_roll_again(self, state: dict, events: list[dict]) -> None:
        if state.get("winner"):
            return
        if state.get("can_roll_again") and not state["players"][self._current_player_id(state)][
            "in_jail"
        ]:
            self._set_phase(state, "awaiting_roll", self._current_player_id(state))
            return
        self._set_phase(state, "awaiting_end", self._current_player_id(state))

    def _try_collect(self, state: dict, pid: str, amount: int) -> None:
        if amount:
            state["players"][pid]["cash"] += amount

    def _require_payment(
        self, state: dict, debtor_id: str, amount: int, creditor_id: str | None, reason: str
    ) -> bool:
        """Attempt to pay. Returns True if paid; False if debt pending."""
        if amount <= 0:
            return True
        debtor = state["players"][debtor_id]
        if debtor["cash"] >= amount:
            debtor["cash"] -= amount
            if creditor_id and creditor_id in state["players"]:
                state["players"][creditor_id]["cash"] += amount
            return True
        state["debt"] = {
            "debtor_id": debtor_id,
            "amount": amount,
            "creditor_id": creditor_id,
            "reason": reason,
        }
        self._set_phase(state, "awaiting_payment", debtor_id)
        self._log(
            state,
            f"{debtor['nickname']} owes ${amount} ({reason}) — raise cash or go bankrupt",
        )
        return False

    def _send_to_jail(self, state: dict, pid: str, events: list[dict]) -> None:
        p = state["players"][pid]
        p["position"] = 10
        p["in_jail"] = True
        p["jail_turns"] = 0
        state["doubles_count"] = 0
        state["can_roll_again"] = False
        self._log(state, f"{p['nickname']} goes to Jail")
        events.append({"type": "go_to_jail", "player_id": pid})
        self._set_phase(state, "awaiting_end", pid)

    def _move_player(
        self, state: dict, pid: str, steps: int, events: list[dict], collect_go: bool = True
    ) -> None:
        p = state["players"][pid]
        old = p["position"]
        new = (old + steps) % 40
        if collect_go and steps > 0 and new < old:
            p["cash"] += 200
            self._log(state, f"{p['nickname']} passed GO (+$200)")
        p["position"] = new
        events.append({"type": "moved", "player_id": pid, "from": old, "to": new})

    def _advance_to(
        self, state: dict, pid: str, to: int, events: list[dict], collect_go: bool = True
    ) -> None:
        p = state["players"][pid]
        old = p["position"]
        if collect_go and to < old:
            p["cash"] += 200
            self._log(state, f"{p['nickname']} passed GO (+$200)")
        elif collect_go and to == 0 and old != 0:
            p["cash"] += 200
            self._log(state, f"{p['nickname']} passed GO (+$200)")
        p["position"] = to
        events.append({"type": "moved", "player_id": pid, "from": old, "to": to})

    # ------------------------------------------------------------------
    # Landing resolution
    # ------------------------------------------------------------------

    def _resolve_landing(
        self, state: dict, pid: str, events: list[dict], dice_total: int
    ) -> None:
        p = state["players"][pid]
        space = space_by_id(p["position"])
        kind = space["kind"]

        if kind == "go":
            self._finish_turn_or_roll_again(state, events)
            return
        if kind == "jail" or kind == "free_parking":
            self._finish_turn_or_roll_again(state, events)
            return
        if kind == "go_to_jail":
            self._send_to_jail(state, pid, events)
            return
        if kind == "tax":
            paid = self._require_payment(state, pid, space["tax"], None, "tax")
            if paid:
                self._log(state, f"{p['nickname']} paid ${space['tax']} tax")
                self._finish_turn_or_roll_again(state, events)
            return
        if kind in ("chance", "community_chest"):
            self._draw_card(state, pid, kind, events, dice_total)
            return
        if is_ownable(space):
            prop = state["properties"][str(space["id"])]
            if prop["owner_id"] is None:
                self._set_phase(state, "awaiting_buy", pid)
                self._log(
                    state,
                    f"{p['nickname']} landed on {space['name']} (${space['price']})",
                )
                return
            if prop["owner_id"] == pid:
                self._finish_turn_or_roll_again(state, events)
                return
            rent, owner = self._property_rent(state, space["id"], dice_total)
            if rent <= 0:
                self._finish_turn_or_roll_again(state, events)
                return
            paid = self._require_payment(state, pid, rent, owner, f"rent on {space['name']}")
            if paid:
                self._log(
                    state,
                    f"{p['nickname']} paid ${rent} rent to {state['players'][owner]['nickname']}",
                )
                events.append(
                    {"type": "rent_paid", "from": pid, "to": owner, "amount": rent}
                )
                self._finish_turn_or_roll_again(state, events)
            return
        self._finish_turn_or_roll_again(state, events)

    def _draw_card(
        self, state: dict, pid: str, kind: str, events: list[dict], dice_total: int
    ) -> None:
        deck_key = "chance_deck" if kind == "chance" else "community_deck"
        discard_key = "chance_discard" if kind == "chance" else "community_discard"
        deck = state[deck_key]
        if not deck:
            deck = state[discard_key]
            state[discard_key] = []
            random.shuffle(deck)
            state[deck_key] = deck
        card = deck.pop(0)
        state["last_card"] = card
        self._log(state, f"{state['players'][pid]['nickname']}: {card['text']}")
        events.append({"type": "card", "player_id": pid, "card": card})
        self._apply_card(state, pid, card, events, dice_total)

    def _apply_card(
        self, state: dict, pid: str, card: dict, events: list[dict], dice_total: int
    ) -> None:
        effect = card["effect"]
        p = state["players"][pid]

        if effect == "get_out_of_jail":
            p["get_out_cards"] += 1
            # Card is held — do not discard until used
            self._finish_turn_or_roll_again(state, events)
            return

        # Non-held cards go to discard after resolving
        discard_key = (
            "chance_discard" if card["id"].startswith("chance") else "community_discard"
        )

        if effect == "cash":
            amount = card["amount"]
            if amount >= 0:
                p["cash"] += amount
                state[discard_key].append(card)
                self._finish_turn_or_roll_again(state, events)
            else:
                state[discard_key].append(card)
                paid = self._require_payment(state, pid, -amount, None, card["text"])
                if paid:
                    self._finish_turn_or_roll_again(state, events)
            return

        if effect == "go_to_jail":
            state[discard_key].append(card)
            self._send_to_jail(state, pid, events)
            return

        if effect == "advance":
            state[discard_key].append(card)
            self._advance_to(state, pid, card["to"], events)
            self._resolve_landing(state, pid, events, dice_total)
            return

        if effect == "move_relative":
            state[discard_key].append(card)
            steps = card["steps"]
            if steps < 0:
                p["position"] = (p["position"] + steps) % 40
                events.append(
                    {
                        "type": "moved",
                        "player_id": pid,
                        "from": (p["position"] - steps) % 40,
                        "to": p["position"],
                    }
                )
            else:
                self._move_player(state, pid, steps, events)
            self._resolve_landing(state, pid, events, dice_total)
            return

        if effect == "nearest_utility":
            state[discard_key].append(card)
            pos = p["position"]
            targets = UTILITIES
            dest = min(targets, key=lambda t: (t - pos) % 40)
            self._advance_to(state, pid, dest, events)
            # If owned, pay 10x dice
            prop = state["properties"][str(dest)]
            if prop["owner_id"] and prop["owner_id"] != pid and not prop["mortgaged"]:
                rent = dice_total * 10
                paid = self._require_payment(
                    state, pid, rent, prop["owner_id"], "utility (Chance)"
                )
                if paid:
                    self._finish_turn_or_roll_again(state, events)
            elif prop["owner_id"] is None:
                self._set_phase(state, "awaiting_buy", pid)
            else:
                self._finish_turn_or_roll_again(state, events)
            return

        if effect == "nearest_railroad":
            state[discard_key].append(card)
            pos = p["position"]
            dest = min(RAILROADS, key=lambda t: (t - pos) % 40)
            self._advance_to(state, pid, dest, events)
            prop = state["properties"][str(dest)]
            if prop["owner_id"] and prop["owner_id"] != pid and not prop["mortgaged"]:
                count = self._count_owned(state, prop["owner_id"], RAILROADS)
                rent = railroad_rent(count) * 2
                paid = self._require_payment(
                    state, pid, rent, prop["owner_id"], "railroad (Chance)"
                )
                if paid:
                    self._finish_turn_or_roll_again(state, events)
            elif prop["owner_id"] is None:
                self._set_phase(state, "awaiting_buy", pid)
            else:
                self._finish_turn_or_roll_again(state, events)
            return

        if effect == "repairs":
            state[discard_key].append(card)
            houses = hotels = 0
            for prop in state["properties"].values():
                if prop["owner_id"] != pid:
                    continue
                h = prop["houses"]
                if h == 5:
                    hotels += 1
                else:
                    houses += h
            amount = houses * card["house"] + hotels * card["hotel"]
            paid = self._require_payment(state, pid, amount, None, "repairs")
            if paid:
                self._finish_turn_or_roll_again(state, events)
            return

        if effect == "pay_each":
            state[discard_key].append(card)
            amount = card["amount"]
            others = [oid for oid in self._active_players(state) if oid != pid]
            total = amount * len(others)
            if p["cash"] >= total:
                for oid in others:
                    p["cash"] -= amount
                    state["players"][oid]["cash"] += amount
                self._finish_turn_or_roll_again(state, events)
            else:
                # Simplified: debt to bank for total; redistribute if paid via pay_debt
                state["debt"] = {
                    "debtor_id": pid,
                    "amount": total,
                    "creditor_id": None,
                    "reason": card["text"],
                    "pay_each": {"amount": amount, "recipients": others},
                }
                self._set_phase(state, "awaiting_payment", pid)
            return

        if effect == "collect_each":
            state[discard_key].append(card)
            amount = card["amount"]
            for oid in self._active_players(state):
                if oid == pid:
                    continue
                other = state["players"][oid]
                take = min(amount, other["cash"])
                other["cash"] -= take
                p["cash"] += take
            self._finish_turn_or_roll_again(state, events)
            return

        state[discard_key].append(card)
        self._finish_turn_or_roll_again(state, events)

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _handle_roll(
        self, state: dict, action: dict, pid: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        self._require_turn_player(state, pid)
        if state["phase"] != "awaiting_roll":
            raise ValueError("Cannot roll now")
        p = self._player(state, pid)
        if p["in_jail"]:
            raise ValueError("Use jail actions while in jail")

        d1 = int(action.get("d1") or random.randint(1, 6))
        d2 = int(action.get("d2") or random.randint(1, 6))
        if not (1 <= d1 <= 6 and 1 <= d2 <= 6):
            raise ValueError("Invalid dice")
        total = d1 + d2
        doubles = d1 == d2
        state["last_dice"] = [d1, d2]
        events.append({"type": "dice", "player_id": pid, "dice": [d1, d2]})
        self._log(state, f"{p['nickname']} rolled {d1}+{d2}={total}")

        if doubles:
            state["doubles_count"] += 1
            if state["doubles_count"] >= 3:
                self._send_to_jail(state, pid, events)
                return state, events
            state["can_roll_again"] = True
        else:
            state["doubles_count"] = 0
            state["can_roll_again"] = False

        self._move_player(state, pid, total, events)
        self._resolve_landing(state, pid, events, total)
        return state, events

    def _handle_roll_jail(
        self, state: dict, action: dict, pid: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        self._require_turn_player(state, pid)
        if state["phase"] != "awaiting_roll":
            raise ValueError("Cannot roll now")
        p = self._player(state, pid)
        if not p["in_jail"]:
            raise ValueError("Not in jail")

        d1 = int(action.get("d1") or random.randint(1, 6))
        d2 = int(action.get("d2") or random.randint(1, 6))
        state["last_dice"] = [d1, d2]
        events.append({"type": "dice", "player_id": pid, "dice": [d1, d2]})
        if d1 == d2:
            p["in_jail"] = False
            p["jail_turns"] = 0
            state["can_roll_again"] = False
            state["doubles_count"] = 0
            self._log(state, f"{p['nickname']} rolled doubles and left Jail")
            self._move_player(state, pid, d1 + d2, events)
            self._resolve_landing(state, pid, events, d1 + d2)
            return state, events

        p["jail_turns"] += 1
        if p["jail_turns"] >= 3:
            # Must pay $50 then move
            if p["cash"] < 50:
                state["debt"] = {
                    "debtor_id": pid,
                    "amount": 50,
                    "creditor_id": None,
                    "reason": "leave jail",
                    "after_pay": {"move": d1 + d2},
                }
                self._set_phase(state, "awaiting_payment", pid)
                return state, events
            p["cash"] -= 50
            p["in_jail"] = False
            p["jail_turns"] = 0
            self._log(state, f"{p['nickname']} paid $50 to leave Jail")
            self._move_player(state, pid, d1 + d2, events)
            self._resolve_landing(state, pid, events, d1 + d2)
            return state, events

        self._log(state, f"{p['nickname']} stays in Jail")
        state["can_roll_again"] = False
        self._set_phase(state, "awaiting_end", pid)
        return state, events

    def _handle_pay_jail(
        self, state: dict, action: dict, pid: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        self._require_turn_player(state, pid)
        if state["phase"] != "awaiting_roll":
            raise ValueError("Cannot leave jail now")
        p = self._player(state, pid)
        if not p["in_jail"]:
            raise ValueError("Not in jail")
        if p["cash"] < 50:
            raise ValueError("Not enough cash")
        p["cash"] -= 50
        p["in_jail"] = False
        p["jail_turns"] = 0
        self._log(state, f"{p['nickname']} paid $50 to leave Jail")
        # Stay in awaiting_roll to roll for movement
        return state, events

    def _handle_use_jail_card(
        self, state: dict, action: dict, pid: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        self._require_turn_player(state, pid)
        if state["phase"] != "awaiting_roll":
            raise ValueError("Cannot use card now")
        p = self._player(state, pid)
        if not p["in_jail"]:
            raise ValueError("Not in jail")
        if p["get_out_cards"] < 1:
            raise ValueError("No Get Out of Jail Free card")
        p["get_out_cards"] -= 1
        p["in_jail"] = False
        p["jail_turns"] = 0
        self._log(state, f"{p['nickname']} used Get Out of Jail Free")
        return state, events

    def _handle_buy(
        self, state: dict, action: dict, pid: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        self._require_actor(state, pid)
        if state["phase"] != "awaiting_buy":
            raise ValueError("Nothing to buy")
        p = self._player(state, pid)
        space = space_by_id(p["position"])
        if not is_ownable(space):
            raise ValueError("Not a purchasable space")
        prop = state["properties"][str(space["id"])]
        if prop["owner_id"] is not None:
            raise ValueError("Already owned")
        price = space["price"]
        if p["cash"] < price:
            raise ValueError("Not enough cash")
        p["cash"] -= price
        prop["owner_id"] = pid
        self._log(state, f"{p['nickname']} bought {space['name']} for ${price}")
        events.append({"type": "bought", "player_id": pid, "space_id": space["id"]})
        dice = state.get("last_dice") or [0, 0]
        self._finish_turn_or_roll_again(state, events)
        return state, events

    def _handle_decline(
        self, state: dict, action: dict, pid: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        self._require_actor(state, pid)
        if state["phase"] != "awaiting_buy":
            raise ValueError("Nothing to decline")
        p = self._player(state, pid)
        space = space_by_id(p["position"])
        prop = state["properties"][str(space["id"])]
        if prop["owner_id"] is not None:
            raise ValueError("Already owned")
        self._start_auction(state, space["id"], events)
        return state, events

    def _start_auction(self, state: dict, space_id: int, events: list[dict]) -> None:
        bidders = self._active_players(state)
        state["auction"] = {
            "space_id": space_id,
            "high_bid": 0,
            "high_bidder_id": None,
            "bidder_index": 0,
            "bidders": bidders,
            "passes_in_row": 0,
        }
        actor = bidders[0]
        self._set_phase(state, "auction", actor)
        space = space_by_id(space_id)
        self._log(state, f"Auction started for {space['name']}")
        events.append({"type": "auction_start", "space_id": space_id})

    def _handle_bid(
        self, state: dict, action: dict, pid: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        self._require_actor(state, pid)
        if state["phase"] != "auction" or not state.get("auction"):
            raise ValueError("No auction")
        auction = state["auction"]
        amount = int(action.get("amount", 0))
        high = auction["high_bid"]
        if amount <= high:
            raise ValueError("Bid must be higher than current high bid")
        p = self._player(state, pid)
        if p["cash"] < amount:
            raise ValueError("Not enough cash")
        auction["high_bid"] = amount
        auction["high_bidder_id"] = pid
        auction["passes_in_row"] = 0
        self._log(state, f"{p['nickname']} bids ${amount}")
        events.append({"type": "bid", "player_id": pid, "amount": amount})
        self._advance_auction_bidder(state)
        return state, events

    def _handle_pass_auction(
        self, state: dict, action: dict, pid: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        self._require_actor(state, pid)
        if state["phase"] != "auction" or not state.get("auction"):
            raise ValueError("No auction")
        auction = state["auction"]
        auction["passes_in_row"] += 1
        self._log(state, f"{state['players'][pid]['nickname']} passes")
        needed = len(auction["bidders"])
        if auction["high_bidder_id"] is None and auction["passes_in_row"] >= needed:
            # No bids — property unsold
            self._log(state, "Auction ended with no bids")
            state["auction"] = None
            turn_pid = self._current_player_id(state)
            self._finish_turn_or_roll_again(state, events)
            events.append({"type": "auction_end", "space_id": None})
            return state, events
        if auction["high_bidder_id"] and auction["passes_in_row"] >= needed - 1:
            self._award_auction(state, events)
            return state, events
        self._advance_auction_bidder(state)
        return state, events

    def _advance_auction_bidder(self, state: dict) -> None:
        auction = state["auction"]
        bidders = auction["bidders"]
        # Skip bankrupt / ensure still active
        for _ in range(len(bidders)):
            auction["bidder_index"] = (auction["bidder_index"] + 1) % len(bidders)
            nid = bidders[auction["bidder_index"]]
            if not state["players"][nid]["bankrupt"]:
                # High bidder can be skipped when everyone else passed — handled in pass
                state["current_actor_id"] = nid
                return

    def _award_auction(self, state: dict, events: list[dict]) -> None:
        auction = state["auction"]
        winner_id = auction["high_bidder_id"]
        space_id = auction["space_id"]
        amount = auction["high_bid"]
        space = space_by_id(space_id)
        winner = state["players"][winner_id]
        winner["cash"] -= amount
        state["properties"][str(space_id)]["owner_id"] = winner_id
        self._log(state, f"{winner['nickname']} won {space['name']} for ${amount}")
        events.append(
            {
                "type": "auction_won",
                "player_id": winner_id,
                "space_id": space_id,
                "amount": amount,
            }
        )
        state["auction"] = None
        turn_pid = self._current_player_id(state)
        # Resume turn player's post-landing flow
        if state.get("can_roll_again") and not state["players"][turn_pid]["in_jail"]:
            self._set_phase(state, "awaiting_roll", turn_pid)
        else:
            self._set_phase(state, "awaiting_end", turn_pid)

    def _houses_on_color(self, state: dict, color: str) -> list[int]:
        return [state["properties"][str(sid)]["houses"] for sid in COLOR_SETS[color]]

    def _can_build(self, state: dict, pid: str, space_id: int) -> str | None:
        space = space_by_id(space_id)
        if space["kind"] != "property":
            return "Can only build on properties"
        prop = state["properties"][str(space_id)]
        if prop["owner_id"] != pid:
            return "You do not own this property"
        if prop["mortgaged"]:
            return "Property is mortgaged"
        color = space["color"]
        if not self._owns_color_set(state, pid, color):
            return "Need a complete color set"
        # Even building: can only build on a property if its houses == min of set
        houses = self._houses_on_color(state, color)
        if prop["houses"] > min(houses):
            return "Must build evenly"
        if prop["houses"] >= 5:
            return "Already has a hotel"
        if prop["houses"] == 4:
            if state["hotels_remaining"] < 1:
                return "No hotels left"
        else:
            if state["houses_remaining"] < 1:
                return "No houses left"
        cost = space["house_cost"]
        if state["players"][pid]["cash"] < cost:
            return "Not enough cash"
        return None

    def _handle_build(
        self, state: dict, action: dict, pid: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        if state["phase"] not in ("awaiting_end", "awaiting_payment", "awaiting_roll"):
            raise ValueError("Cannot build now")
        if state["phase"] == "awaiting_roll" and self._current_player_id(state) != pid:
            raise ValueError("Not your turn")
        if state["phase"] in ("awaiting_end", "awaiting_payment"):
            if str(state.get("current_actor_id")) != pid:
                raise ValueError("Not your turn")
        space_id = int(action.get("space_id"))
        err = self._can_build(state, pid, space_id)
        if err:
            raise ValueError(err)
        space = space_by_id(space_id)
        prop = state["properties"][str(space_id)]
        cost = space["house_cost"]
        state["players"][pid]["cash"] -= cost
        if prop["houses"] == 4:
            prop["houses"] = 5
            state["houses_remaining"] += 4
            state["hotels_remaining"] -= 1
            self._log(state, f"{state['players'][pid]['nickname']} built a hotel on {space['name']}")
        else:
            prop["houses"] += 1
            state["houses_remaining"] -= 1
            self._log(state, f"{state['players'][pid]['nickname']} built a house on {space['name']}")
        events.append({"type": "build", "player_id": pid, "space_id": space_id})
        return state, events

    def _handle_sell_building(
        self, state: dict, action: dict, pid: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        if state["phase"] not in ("awaiting_end", "awaiting_payment", "awaiting_roll"):
            raise ValueError("Cannot sell now")
        if str(state.get("current_actor_id")) != pid and self._current_player_id(state) != pid:
            raise ValueError("Not your turn")
        space_id = int(action.get("space_id"))
        space = space_by_id(space_id)
        if space["kind"] != "property":
            raise ValueError("Not a property")
        prop = state["properties"][str(space_id)]
        if prop["owner_id"] != pid:
            raise ValueError("You do not own this")
        if prop["houses"] < 1:
            raise ValueError("No buildings to sell")
        # Even selling
        color = space["color"]
        houses = self._houses_on_color(state, color)
        if prop["houses"] < max(houses):
            raise ValueError("Must sell evenly")
        refund = space["house_cost"] // 2
        if prop["houses"] == 5:
            if state["houses_remaining"] < 4:
                raise ValueError("Not enough houses in bank to break hotel")
            prop["houses"] = 4
            state["hotels_remaining"] += 1
            state["houses_remaining"] -= 4
        else:
            prop["houses"] -= 1
            state["houses_remaining"] += 1
        state["players"][pid]["cash"] += refund
        self._log(
            state,
            f"{state['players'][pid]['nickname']} sold a building on {space['name']} (+${refund})",
        )
        return state, events

    def _any_buildings_on_color(self, state: dict, color: str) -> bool:
        return any(state["properties"][str(sid)]["houses"] > 0 for sid in COLOR_SETS[color])

    def _handle_mortgage(
        self, state: dict, action: dict, pid: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        if state["phase"] not in ("awaiting_end", "awaiting_payment", "awaiting_roll"):
            raise ValueError("Cannot mortgage now")
        if str(state.get("current_actor_id")) != pid and self._current_player_id(state) != pid:
            raise ValueError("Not your turn")
        space_id = int(action.get("space_id"))
        space = space_by_id(space_id)
        if not is_ownable(space):
            raise ValueError("Cannot mortgage")
        prop = state["properties"][str(space_id)]
        if prop["owner_id"] != pid:
            raise ValueError("You do not own this")
        if prop["mortgaged"]:
            raise ValueError("Already mortgaged")
        if space["kind"] == "property" and self._any_buildings_on_color(state, space["color"]):
            raise ValueError("Sell buildings on the color set first")
        prop["mortgaged"] = True
        amount = space["mortgage"]
        state["players"][pid]["cash"] += amount
        self._log(state, f"{state['players'][pid]['nickname']} mortgaged {space['name']} (+${amount})")
        return state, events

    def _handle_unmortgage(
        self, state: dict, action: dict, pid: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        if state["phase"] not in ("awaiting_end", "awaiting_payment", "awaiting_roll"):
            raise ValueError("Cannot unmortgage now")
        if str(state.get("current_actor_id")) != pid and self._current_player_id(state) != pid:
            raise ValueError("Not your turn")
        space_id = int(action.get("space_id"))
        space = space_by_id(space_id)
        prop = state["properties"][str(space_id)]
        if prop["owner_id"] != pid or not prop["mortgaged"]:
            raise ValueError("Cannot unmortgage")
        cost = int(space["mortgage"] * 1.1)
        if state["players"][pid]["cash"] < cost:
            raise ValueError("Not enough cash")
        state["players"][pid]["cash"] -= cost
        prop["mortgaged"] = False
        self._log(
            state, f"{state['players'][pid]['nickname']} unmortgaged {space['name']} (-${cost})"
        )
        return state, events

    def _handle_propose_trade(
        self, state: dict, action: dict, pid: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        if state["phase"] not in ("awaiting_end", "awaiting_roll"):
            raise ValueError("Cannot trade now")
        if self._current_player_id(state) != pid:
            raise ValueError("Not your turn")
        if state.get("debt"):
            raise ValueError("Resolve debt first")
        if state.get("pending_trade"):
            raise ValueError("A trade is already pending")
        to_id = str(action.get("to_id"))
        if to_id == pid or to_id not in state["players"] or state["players"][to_id]["bankrupt"]:
            raise ValueError("Invalid trade partner")
        offer_cash = int(action.get("offer_cash") or 0)
        request_cash = int(action.get("request_cash") or 0)
        offer_props = [int(x) for x in (action.get("offer_props") or [])]
        request_props = [int(x) for x in (action.get("request_props") or [])]
        if offer_cash < 0 or request_cash < 0:
            raise ValueError("Invalid cash")
        if state["players"][pid]["cash"] < offer_cash:
            raise ValueError("Not enough cash to offer")
        for sid in offer_props:
            prop = state["properties"][str(sid)]
            if prop["owner_id"] != pid:
                raise ValueError("You do not own offered property")
            space = space_by_id(sid)
            if space["kind"] == "property" and self._any_buildings_on_color(state, space["color"]):
                raise ValueError("Sell buildings before trading that color")
        for sid in request_props:
            prop = state["properties"][str(sid)]
            if prop["owner_id"] != to_id:
                raise ValueError("Partner does not own requested property")
            space = space_by_id(sid)
            if space["kind"] == "property" and self._any_buildings_on_color(state, space["color"]):
                raise ValueError("Partner must sell buildings first")
        state["pending_trade"] = {
            "from_id": pid,
            "to_id": to_id,
            "offer_cash": offer_cash,
            "request_cash": request_cash,
            "offer_props": offer_props,
            "request_props": request_props,
        }
        # Responder becomes actor temporarily; remember turn actor
        state["trade_resume_actor"] = state["current_actor_id"]
        state["trade_resume_phase"] = state["phase"]
        self._set_phase(state, "trade_pending", to_id)
        self._log(
            state,
            f"{state['players'][pid]['nickname']} proposed a trade to {state['players'][to_id]['nickname']}",
        )
        events.append({"type": "trade_proposed", "from": pid, "to": to_id})
        return state, events

    def _handle_accept_trade(
        self, state: dict, action: dict, pid: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        trade = state.get("pending_trade")
        if not trade or state["phase"] != "trade_pending":
            raise ValueError("No pending trade")
        if pid != trade["to_id"]:
            raise ValueError("Not the trade recipient")
        if state["players"][pid]["cash"] < trade["request_cash"]:
            raise ValueError("Not enough cash")
        if state["players"][trade["from_id"]]["cash"] < trade["offer_cash"]:
            raise ValueError("Proposer cannot fund offer")
        # Transfer
        state["players"][trade["from_id"]]["cash"] -= trade["offer_cash"]
        state["players"][pid]["cash"] += trade["offer_cash"]
        state["players"][pid]["cash"] -= trade["request_cash"]
        state["players"][trade["from_id"]]["cash"] += trade["request_cash"]
        for sid in trade["offer_props"]:
            state["properties"][str(sid)]["owner_id"] = pid
        for sid in trade["request_props"]:
            state["properties"][str(sid)]["owner_id"] = trade["from_id"]
        self._log(state, "Trade accepted")
        events.append({"type": "trade_accepted"})
        state["pending_trade"] = None
        resume_phase = state.pop("trade_resume_phase", "awaiting_end")
        resume_actor = state.pop("trade_resume_actor", self._current_player_id(state))
        self._set_phase(state, resume_phase, resume_actor)
        return state, events

    def _handle_reject_trade(
        self, state: dict, action: dict, pid: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        trade = state.get("pending_trade")
        if not trade or state["phase"] != "trade_pending":
            raise ValueError("No pending trade")
        if pid != trade["to_id"]:
            raise ValueError("Not the trade recipient")
        state["pending_trade"] = None
        resume_phase = state.pop("trade_resume_phase", "awaiting_end")
        resume_actor = state.pop("trade_resume_actor", self._current_player_id(state))
        self._set_phase(state, resume_phase, resume_actor)
        self._log(state, "Trade rejected")
        events.append({"type": "trade_rejected"})
        return state, events

    def _handle_cancel_trade(
        self, state: dict, action: dict, pid: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        trade = state.get("pending_trade")
        if not trade:
            raise ValueError("No pending trade")
        if pid != trade["from_id"]:
            raise ValueError("Only proposer can cancel")
        state["pending_trade"] = None
        resume_phase = state.pop("trade_resume_phase", "awaiting_end")
        resume_actor = state.pop("trade_resume_actor", self._current_player_id(state))
        self._set_phase(state, resume_phase, resume_actor)
        self._log(state, "Trade cancelled")
        return state, events

    def _handle_pay_debt(
        self, state: dict, action: dict, pid: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        self._require_actor(state, pid)
        if state["phase"] != "awaiting_payment" or not state.get("debt"):
            raise ValueError("No debt to pay")
        debt = state["debt"]
        if debt["debtor_id"] != pid:
            raise ValueError("Not your debt")
        amount = debt["amount"]
        p = state["players"][pid]
        if p["cash"] < amount:
            raise ValueError("Still not enough cash")
        p["cash"] -= amount
        creditor = debt.get("creditor_id")
        pay_each = debt.get("pay_each")
        if pay_each:
            for oid in pay_each["recipients"]:
                if not state["players"][oid]["bankrupt"]:
                    state["players"][oid]["cash"] += pay_each["amount"]
        elif creditor and creditor in state["players"]:
            state["players"][creditor]["cash"] += amount

        after = debt.get("after_pay")
        state["debt"] = None
        self._log(state, f"{p['nickname']} paid ${amount}")
        if after and after.get("move"):
            p["in_jail"] = False
            p["jail_turns"] = 0
            self._move_player(state, pid, after["move"], events)
            self._resolve_landing(state, pid, events, after["move"])
            return state, events
        # If debtor is turn player, continue turn; else return to turn player end
        turn_pid = self._current_player_id(state)
        if pid == turn_pid:
            self._finish_turn_or_roll_again(state, events)
        else:
            self._set_phase(state, "awaiting_end", turn_pid)
        return state, events

    def _transfer_assets(
        self, state: dict, from_id: str, to_id: str | None, events: list[dict]
    ) -> None:
        """Give all properties/cash/cards from bankrupt player to creditor or bank."""
        bankrupt = state["players"][from_id]
        if to_id and to_id in state["players"] and not state["players"][to_id]["bankrupt"]:
            state["players"][to_id]["cash"] += bankrupt["cash"]
            state["players"][to_id]["get_out_cards"] += bankrupt["get_out_cards"]
            for prop in state["properties"].values():
                if prop["owner_id"] == from_id:
                    # Clear buildings when transferring to creditor? Classic: houses sold to bank first
                    prop["owner_id"] = to_id
                    prop["houses"] = 0
                    # Keep mortgage status
        else:
            for prop in state["properties"].values():
                if prop["owner_id"] == from_id:
                    prop["owner_id"] = None
                    prop["mortgaged"] = False
                    prop["houses"] = 0
        bankrupt["cash"] = 0
        bankrupt["get_out_cards"] = 0
        bankrupt["bankrupt"] = True
        bankrupt["in_jail"] = False
        events.append({"type": "bankrupt", "player_id": from_id, "to": to_id})

    def _handle_declare_bankruptcy(
        self, state: dict, action: dict, pid: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        if state["phase"] != "awaiting_payment" or not state.get("debt"):
            # Also allow resign-style from awaiting_end
            if state["phase"] not in ("awaiting_end", "awaiting_roll", "awaiting_payment"):
                raise ValueError("Cannot go bankrupt now")
        debt = state.get("debt") or {}
        creditor = debt.get("creditor_id") if debt.get("debtor_id") == pid else None
        # Sell buildings to bank for half before transfer
        for sid_str, prop in state["properties"].items():
            if prop["owner_id"] != pid:
                continue
            space = space_by_id(int(sid_str))
            if space["kind"] == "property" and prop["houses"] > 0:
                if prop["houses"] == 5:
                    state["players"][pid]["cash"] += (space["house_cost"] // 2) * 5
                    state["hotels_remaining"] += 1
                else:
                    state["players"][pid]["cash"] += (space["house_cost"] // 2) * prop["houses"]
                    state["houses_remaining"] += prop["houses"]
                prop["houses"] = 0
        self._log(state, f"{state['players'][pid]['nickname']} went bankrupt")
        self._transfer_assets(state, pid, creditor, events)
        state["debt"] = None
        state["pending_trade"] = None
        self._check_last_standing(state)
        if state.get("winner"):
            return state, events
        # If bankrupt was current turn player, advance
        if self._current_player_id(state) == pid or state["players"][
            self._current_player_id(state)
        ]["bankrupt"]:
            self._advance_to_next_player(state)
        else:
            self._set_phase(state, state["phase"], self._current_player_id(state))
        return state, events

    def _handle_resign(
        self, state: dict, action: dict, pid: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        if state["players"][pid]["bankrupt"]:
            raise ValueError("Already bankrupt")
        state["debt"] = {"debtor_id": pid, "amount": 0, "creditor_id": None, "reason": "resign"}
        return self._handle_declare_bankruptcy(state, action, pid, events)

    def _handle_end_turn(
        self, state: dict, action: dict, pid: str, events: list[dict]
    ) -> tuple[dict, list[dict]]:
        self._require_turn_player(state, pid)
        if state["phase"] != "awaiting_end":
            raise ValueError("Cannot end turn now")
        if state.get("can_roll_again"):
            raise ValueError("You must roll again after doubles")
        self._advance_to_next_player(state)
        events.append({"type": "turn_ended", "player_id": pid})
        return state, events
