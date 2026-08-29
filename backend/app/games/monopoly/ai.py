"""Heuristic Monopoly AI."""

from __future__ import annotations

import random
from typing import Any

from app.games.monopoly.board import COLOR_SETS, space_by_id
from app.games.monopoly.engine import normalize_ai_difficulty


def choose_monopoly_action(state: dict, player_id: str) -> dict[str, Any]:
    """Return one legal action for the AI player."""
    pid = str(player_id)
    player = state["players"][pid]
    difficulty = normalize_ai_difficulty(player.get("ai_difficulty") or "medium")
    phase = state.get("phase")

    if phase == "auction":
        return _auction_action(state, pid, difficulty)
    if phase == "awaiting_buy":
        return _buy_decision(state, pid, difficulty)
    if phase == "awaiting_payment":
        return _debt_action(state, pid, difficulty)
    if phase == "trade_pending":
        return _trade_response(state, pid, difficulty)
    if phase == "awaiting_roll":
        return _roll_phase(state, pid, difficulty)
    if phase == "awaiting_end":
        return _end_phase(state, pid, difficulty)
    return {"type": "end_turn"}


def _reserve(difficulty: str) -> int:
    return {"easy": 50, "medium": 150, "hard": 250}[difficulty]


def _property_value(space_id: int) -> int:
    space = space_by_id(space_id)
    if space["kind"] == "property":
        return space["price"] + space["rents"][0] * 8
    if space["kind"] == "railroad":
        return 200
    if space["kind"] == "utility":
        return 120
    return 0


def _owned_in_color(state: dict, pid: str, color: str) -> int:
    return sum(
        1
        for sid in COLOR_SETS[color]
        if state["properties"][str(sid)]["owner_id"] == pid
    )


def _completes_set(state: dict, pid: str, space_id: int) -> bool:
    space = space_by_id(space_id)
    if space["kind"] != "property":
        return False
    color = space["color"]
    owned = _owned_in_color(state, pid, color)
    return owned == len(COLOR_SETS[color]) - 1


def _buy_decision(state: dict, pid: str, difficulty: str) -> dict:
    player = state["players"][pid]
    space = space_by_id(player["position"])
    price = space.get("price", 0)
    reserve = _reserve(difficulty)
    if player["cash"] < price + (0 if difficulty == "easy" else reserve // 2):
        return {"type": "decline"}
    value = _property_value(space["id"])
    completes = _completes_set(state, pid, space["id"])
    if difficulty == "easy":
        if random.random() < 0.55 or completes:
            return {"type": "buy"} if player["cash"] >= price else {"type": "decline"}
        return {"type": "decline"}
    if completes or value >= price or space["kind"] in ("railroad", "utility"):
        return {"type": "buy"}
    if difficulty == "hard" and player["cash"] >= price + reserve:
        return {"type": "buy"}
    if player["cash"] >= price + reserve and random.random() < 0.7:
        return {"type": "buy"}
    return {"type": "decline"}


def _auction_action(state: dict, pid: str, difficulty: str) -> dict:
    auction = state["auction"]
    space_id = auction["space_id"]
    space = space_by_id(space_id)
    price = space.get("price", 100)
    high = auction["high_bid"]
    player = state["players"][pid]
    reserve = _reserve(difficulty)
    max_bid = min(player["cash"] - reserve, int(price * {"easy": 0.7, "medium": 1.05, "hard": 1.35}[difficulty]))
    if _completes_set(state, pid, space_id):
        max_bid = min(player["cash"] - 20, int(price * 1.6))
    if auction["high_bidder_id"] == pid:
        return {"type": "pass_auction"}
    if max_bid > high and player["cash"] > high + 1:
        bid = min(max_bid, high + max(10, price // 10))
        if bid > high:
            return {"type": "bid", "amount": bid}
    return {"type": "pass_auction"}


def _roll_phase(state: dict, pid: str, difficulty: str) -> dict:
    player = state["players"][pid]
    if not player["in_jail"]:
        return {"type": "roll"}
    # Jail strategy
    props = sum(1 for p in state["properties"].values() if p["owner_id"] == pid)
    mid_game = props >= 3
    if player["get_out_cards"] > 0 and (mid_game or difficulty == "hard"):
        return {"type": "use_jail_card"}
    if player["cash"] >= 50 + _reserve(difficulty) and mid_game and difficulty != "easy":
        return {"type": "pay_jail"}
    if player["jail_turns"] >= 2 and player["cash"] >= 50:
        return {"type": "pay_jail"}
    return {"type": "roll_jail"}


def _liquidatable(state: dict, pid: str) -> list[dict]:
    """Actions that raise cash."""
    actions: list[dict] = []
    # Sell hotels/houses first (highest first for evenness)
    for color, sids in COLOR_SETS.items():
        props = [(sid, state["properties"][str(sid)]) for sid in sids]
        if any(p["owner_id"] != pid for _, p in props):
            continue
        houses = [state["properties"][str(sid)]["houses"] for sid in sids]
        if max(houses) == 0:
            continue
        mx = max(houses)
        for sid in sids:
            if state["properties"][str(sid)]["houses"] != mx:
                continue
            # Breaking a hotel requires 4 houses in the bank
            if mx == 5 and state.get("houses_remaining", 0) < 4:
                continue
            actions.append({"type": "sell_building", "space_id": sid})
            # Simulate locally for planning — caller applies one at a time
            return actions
    for sid_str, prop in state["properties"].items():
        if prop["owner_id"] != pid or prop["mortgaged"]:
            continue
        space = space_by_id(int(sid_str))
        if space["kind"] == "property" and any(
            state["properties"][str(s)]["houses"] > 0 for s in COLOR_SETS[space["color"]]
        ):
            continue
        actions.append({"type": "mortgage", "space_id": int(sid_str)})
    return actions


def _debt_action(state: dict, pid: str, difficulty: str) -> dict:
    debt = state.get("debt") or {}
    amount = debt.get("amount", 0)
    player = state["players"][pid]
    if player["cash"] >= amount:
        return {"type": "pay_debt"}
    raise_actions = _liquidatable(state, pid)
    if raise_actions:
        return raise_actions[0]
    return {"type": "declare_bankruptcy"}


def _trade_response(state: dict, pid: str, difficulty: str) -> dict:
    trade = state.get("pending_trade") or {}
    # Accept if we gain a set completion and don't give one away cheaply
    request_props = trade.get("request_props") or []
    offer_props = trade.get("offer_props") or []
    we_complete = any(_completes_set(state, pid, sid) for sid in offer_props)
    they_complete = any(_completes_set(state, trade["from_id"], sid) for sid in request_props)
    net_cash = trade.get("offer_cash", 0) - trade.get("request_cash", 0)
    if difficulty == "easy":
        return {"type": "accept_trade"} if random.random() < 0.5 else {"type": "reject_trade"}
    if we_complete and not they_complete:
        return {"type": "accept_trade"}
    if we_complete and they_complete and net_cash >= 100:
        return {"type": "accept_trade"}
    if net_cash >= 150 and not they_complete:
        return {"type": "accept_trade"}
    if difficulty == "hard" and they_complete:
        return {"type": "reject_trade"}
    return {"type": "reject_trade"}


def _build_targets(state: dict, pid: str) -> list[int]:
    targets = []
    for color, sids in COLOR_SETS.items():
        if any(state["properties"][str(sid)]["owner_id"] != pid for sid in sids):
            continue
        if any(state["properties"][str(sid)]["mortgaged"] for sid in sids):
            continue
        houses = [state["properties"][str(sid)]["houses"] for sid in sids]
        mn = min(houses)
        for sid in sids:
            if state["properties"][str(sid)]["houses"] == mn and mn < 5:
                targets.append(sid)
    return targets


def _maybe_propose_trade(state: dict, pid: str, difficulty: str) -> dict | None:
    if difficulty == "easy" or state.get("pending_trade"):
        return None
    if random.random() > (0.15 if difficulty == "hard" else 0.08):
        return None
    # Look for a property that completes our set held by another
    for color, sids in COLOR_SETS.items():
        owners = {state["properties"][str(sid)]["owner_id"] for sid in sids}
        if pid not in owners:
            continue
        mine = [sid for sid in sids if state["properties"][str(sid)]["owner_id"] == pid]
        missing = [
            sid
            for sid in sids
            if state["properties"][str(sid)]["owner_id"] not in (None, pid)
        ]
        if len(mine) != len(sids) - 1 or len(missing) != 1:
            continue
        need = missing[0]
        partner = state["properties"][str(need)]["owner_id"]
        # Offer cash
        space = space_by_id(need)
        offer = min(state["players"][pid]["cash"] // 2, int(space["price"] * 1.2))
        if offer < 50:
            continue
        # Ensure no buildings on either color
        if any(state["properties"][str(s)]["houses"] > 0 for s in sids):
            continue
        return {
            "type": "propose_trade",
            "to_id": partner,
            "offer_cash": offer,
            "request_cash": 0,
            "offer_props": [],
            "request_props": [need],
        }
    return None


def _end_phase(state: dict, pid: str, difficulty: str) -> dict:
    player = state["players"][pid]
    # Build if comfortable
    reserve = _reserve(difficulty)
    if player["cash"] > reserve + 100:
        for sid in _build_targets(state, pid):
            space = space_by_id(sid)
            cost = space["house_cost"]
            if player["cash"] >= cost + reserve:
                # Engine validates evenness
                return {"type": "build", "space_id": sid}
    trade = _maybe_propose_trade(state, pid, difficulty)
    if trade:
        return trade
    return {"type": "end_turn"}
