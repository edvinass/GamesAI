"""When Scribble AI players pick, draw, and guess."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any

from app.games.scribble.doodles import doodle_for
from app.games.scribble.words import WORDS


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.isoformat()


def choose_word_index(state: dict) -> int:
    options = state.get("word_options") or []
    if not options:
        return 0
    difficulty = _drawer_difficulty(state)
    prefer = {"easy": "easy", "hard": "hard"}.get(difficulty, "medium")
    for index, option in enumerate(options):
        if option.get("difficulty") == prefer:
            return index
    return min(1, len(options) - 1)


def _drawer_difficulty(state: dict) -> str:
    drawer_id = state.get("drawer_id")
    for player in state.get("players") or []:
        if player.get("id") == drawer_id:
            return str(player.get("ai_difficulty") or "medium")
    return str((state.get("settings") or {}).get("ai_difficulty") or "medium")


def queue_strokes(word: str) -> list[dict[str, Any]]:
    return doodle_for(word)


def plan_guesses(state: dict, started: datetime) -> list[dict[str, Any]]:
    word = str(state.get("word") or "")
    if not word:
        return []
    draw_seconds = int((state.get("settings") or {}).get("draw_seconds") or 70)
    drawer_id = state.get("drawer_id")
    decoys = [item["text"] for item in WORDS if item["text"] != word]
    plans: list[dict[str, Any]] = []
    for player in state.get("players") or []:
        if player.get("id") == drawer_id or not player.get("is_ai"):
            continue
        difficulty = str(player.get("ai_difficulty") or (state.get("settings") or {}).get("ai_difficulty") or "medium")
        if difficulty == "easy":
            delay = random.uniform(0.5, 0.82) * draw_seconds
            wrong_chance = 0.65
        elif difficulty == "hard":
            delay = random.uniform(0.16, 0.38) * draw_seconds
            wrong_chance = 0.12
        else:
            delay = random.uniform(0.3, 0.58) * draw_seconds
            wrong_chance = 0.35
        delay = max(5.0, delay)
        moment = started + timedelta(seconds=delay)
        if random.random() < wrong_chance and decoys:
            plans.append(
                {
                    "player_id": player["id"],
                    "at": _iso(moment),
                    "text": random.choice(decoys),
                }
            )
            follow = moment + timedelta(seconds=random.uniform(6.0, 12.0))
            if (follow - started).total_seconds() < draw_seconds - 2:
                plans.append({"player_id": player["id"], "at": _iso(follow), "text": word})
        else:
            plans.append({"player_id": player["id"], "at": _iso(moment), "text": word})
    plans.sort(key=lambda item: item["at"])
    return plans


def due_guesses(state: dict, now: datetime | None = None) -> list[dict[str, str]]:
    moment = now or _now()
    ready: list[dict[str, str]] = []
    for plan in state.get("ai_guesses") or []:
        if plan.get("done"):
            continue
        when = datetime.fromisoformat(plan["at"])
        if moment >= when:
            plan["done"] = True
            ready.append({"player_id": plan["player_id"], "text": plan["text"]})
    return ready
