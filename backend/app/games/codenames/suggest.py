"""On-demand clue and guess suggestions for Codenames cheat mode.

These calls are independent of the room AI lock and of the game action path.
The caller must pass a snapshot and must not hold a database session while this runs.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.games.codenames.ai import ai_operative_guesses, ai_spymaster_clue
from app.games.codenames.ai_models import AI_MODEL_LABELS, DEFAULT_AI_MODEL

logger = logging.getLogger(__name__)

# One suggestion at a time per player. A newer request cancels the previous one
# so abandoned hints never pile up beside the live AI turn.
_inflight: dict[str, asyncio.Task] = {}
_inflight_guard = asyncio.Lock()


def codenames_position_key(state: dict) -> str:
    """Identity of the decision the viewer is looking at. Kept in sync with the client."""
    revealed = ",".join(
        str(card["index"])
        for card in sorted(state.get("cards") or [], key=lambda card: card["index"])
        if card.get("revealed")
    )
    clue = state.get("current_clue") or {}
    number = clue.get("number")
    number_text = "" if number is None else str(number)
    return "|".join(
        [
            str(state.get("phase") or ""),
            str(state.get("current_team") or ""),
            str(clue.get("word") or ""),
            number_text,
            str(state.get("guesses_remaining") or 0),
            revealed,
        ]
    )


def model_for_state(state: dict) -> tuple[str, str]:
    settings = state.get("settings") or {}
    model = str(settings.get("ai_model") or DEFAULT_AI_MODEL)
    return model, AI_MODEL_LABELS.get(model, model)


def active_suggestion_kind(state: dict, team: str | None, role: str | None) -> str | None:
    if not team or not role or state.get("winner"):
        return None
    if state.get("current_team") != team:
        return None
    phase = state.get("phase")
    if phase == "clue" and role == "spymaster":
        return "clue"
    if phase == "guess" and role == "operative":
        return "guess"
    return None


async def build_suggestion(state: dict, team: str | None, role: str | None) -> dict[str, Any]:
    kind = active_suggestion_kind(state, team, role)
    if kind == "clue" and team:
        clue, number, targets = await ai_spymaster_clue(state, team)
        return {
            "kind": "clue",
            "word": clue,
            "number": number,
            "targets": list(targets),
        }
    if kind == "guess" and team:
        guesses = await ai_operative_guesses(
            state, team, int(state.get("guesses_remaining") or 1)
        )
        by_index = {int(card["index"]): card for card in state.get("cards") or []}
        items: list[dict[str, Any]] = []
        for index in guesses:
            card = by_index.get(int(index))
            if not card or card.get("revealed"):
                continue
            items.append({"index": int(index), "word": card["word"]})
        return {"kind": "guess", "guesses": items}
    return {"kind": "none"}


async def run_suggestion(
    player_key: str,
    state: dict,
    team: str | None,
    role: str | None,
    *,
    disconnected,
) -> dict[str, Any]:
    """Run a suggestion, cancelling any older one for this player.

    `disconnected` is an async callable that reports whether the client has gone.
    """
    task: asyncio.Task
    async with _inflight_guard:
        previous = _inflight.get(player_key)
        if previous is not None and not previous.done():
            previous.cancel()
        task = asyncio.create_task(build_suggestion(state, team, role))
        _inflight[player_key] = task

    async def watch_disconnect() -> None:
        try:
            while not task.done():
                if await disconnected():
                    task.cancel()
                    return
                await asyncio.sleep(0.3)
        except asyncio.CancelledError:
            return

    watcher = asyncio.create_task(watch_disconnect())
    try:
        return await task
    finally:
        watcher.cancel()
        async with _inflight_guard:
            if _inflight.get(player_key) is task:
                _inflight.pop(player_key, None)
