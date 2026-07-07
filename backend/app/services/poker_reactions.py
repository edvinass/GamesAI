"""Broadcast poker emoji reactions for AI players."""

import asyncio
import logging
import random
import uuid

from app.games.poker.reactions import (
    choose_action_reaction,
    choose_game_winner_reaction,
    choose_loser_reaction,
    choose_winner_reaction,
)
from app.models import Room

logger = logging.getLogger(__name__)


def _hand_ended(state: dict, events: list[dict]) -> bool:
    if state.get("phase") in ("hand_complete", "game_over"):
        return True
    return any(e.get("type") in ("hand_won", "hand_complete", "showdown") for e in events)


async def _broadcast_reaction(room_id: str, player_id: str, nickname: str, emoji: str) -> None:
    from app.websocket.handlers import manager

    await manager.broadcast(room_id, {
        "type": "reaction",
        "player_id": player_id,
        "nickname": nickname,
        "emoji": emoji,
    })


async def send_poker_reactions(
    room_id: uuid.UUID,
    room: Room,
    state: dict,
    events: list[dict],
    actor_id: str | None,
    action: dict | None,
) -> None:
    players_by_id = {str(p.id): p for p in room.players}
    hand_ended = _hand_ended(state, events)
    game_over = state.get("phase") == "game_over" or bool(state.get("winner"))

    if actor_id and action and not hand_ended:
        player = players_by_id.get(str(actor_id))
        if player and player.is_ai:
            emoji = choose_action_reaction(state, str(actor_id), action)
            if emoji:
                await asyncio.sleep(0.7)
                await _broadcast_reaction(str(room_id), str(actor_id), player.nickname, emoji)

    if hand_ended:
        winners = state.get("winners") or []
        won_by_fold = any(
            e.get("type") == "hand_won" and e.get("reason") == "fold" for e in events
        )

        ai_winners = [
            w
            for w in winners
            if state["players"].get(str(w["player_id"]), {}).get("is_ai")
        ]
        if ai_winners:
            best = max(ai_winners, key=lambda w: int(w.get("amount", 0)))
            winner_id = str(best["player_id"])
            player = players_by_id.get(winner_id)
            if player:
                emoji = choose_winner_reaction(state, best)
                await asyncio.sleep(1.0)
                await _broadcast_reaction(str(room_id), winner_id, player.nickname, emoji)

        if not won_by_fold and random.random() < 0.65:
            winner_ids = {str(w["player_id"]) for w in winners}
            ai_losers = [
                str(pid)
                for pid in state["seat_order"]
                if str(pid) not in winner_ids
                and state["players"].get(str(pid), {}).get("is_ai")
                and state["players"][str(pid)].get("status") != "folded"
            ]
            if ai_losers:
                loser_id = random.choice(ai_losers)
                player = players_by_id.get(loser_id)
                if player:
                    emoji = choose_loser_reaction()
                    await asyncio.sleep(1.6)
                    await _broadcast_reaction(str(room_id), loser_id, player.nickname, emoji)

    if game_over and state.get("winner"):
        winner_id = str(state["winner"])
        if state["players"].get(winner_id, {}).get("is_ai"):
            player = players_by_id.get(winner_id)
            if player:
                await asyncio.sleep(1.2)
                await _broadcast_reaction(
                    str(room_id),
                    winner_id,
                    player.nickname,
                    choose_game_winner_reaction(),
                )


def schedule_poker_reactions(
    room_id: uuid.UUID,
    room: Room,
    state: dict,
    events: list[dict],
    actor_id: str | None,
    action: dict | None,
) -> None:
    async def _run() -> None:
        try:
            await send_poker_reactions(room_id, room, state, events, actor_id, action)
        except Exception:
            logger.exception("Failed to send poker AI reactions")

    asyncio.create_task(_run())
