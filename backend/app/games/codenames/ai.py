import json
import logging
import re
from typing import Any

from app.config import settings
from app.services.deepseek import deepseek_chat

logger = logging.getLogger(__name__)


async def ai_spymaster_clue(state: dict, team: str) -> tuple[str, int]:
    cards = state["cards"]
    board_lines = []
    for c in cards:
        status = "REVEALED" if c["revealed"] else "HIDDEN"
        board_lines.append(f"- {c['word']}: {c['color']} ({status})")

    team_remaining = state["red_remaining"] if team == "red" else state["blue_remaining"]

    prompt = f"""You are the {team.upper()} spymaster in Codenames.
Give a one-word clue and a number indicating how many words on the board relate to your clue.
Only target unrevealed {team} words. Never clue toward assassin or opponent words.

Board:
{chr(10).join(board_lines)}

Your team has {team_remaining} words remaining.

Respond ONLY with JSON: {{"clue": "WORD", "number": N}}
Rules: clue is ONE word (not on board), number >= 0 (0 means unlimited guesses)."""

    try:
        response = await deepseek_chat(prompt)
        data = _parse_json(response)
        clue = str(data.get("clue", "")).strip().upper()
        number = int(data.get("number", 1))
        if clue and number >= 0:
            return clue, number
    except Exception as e:
        logger.warning("AI spymaster failed: %s", e)

    return "THING", 1


async def ai_operative_guesses(state: dict, team: str, max_guesses: int) -> list[int]:
    clue = state.get("current_clue") or {}
    clue_word = clue.get("word", "")
    clue_number = clue.get("number", 0)

    visible = []
    for c in state["cards"]:
        entry = {"index": c["index"], "word": c["word"], "revealed": c["revealed"]}
        if c["revealed"]:
            entry["color"] = c["color"]
        visible.append(entry)

    limit = max_guesses if clue_number > 0 else min(max_guesses, 3)

    prompt = f"""You are a {team.upper()} operative in Codenames.
Your spymaster gave clue "{clue_word}" with number {clue_number}.
Pick up to {limit} unrevealed card indices to guess, in order. Stop early if unsure.

Visible board (JSON):
{json.dumps(visible)}

Respond ONLY with JSON: {{"guesses": [index1, index2, ...]}}
Use card index values 0-24. Only unrevealed cards."""

    try:
        response = await deepseek_chat(prompt)
        data = _parse_json(response)
        guesses = data.get("guesses", [])
        valid = []
        for g in guesses[:limit]:
            idx = int(g)
            if 0 <= idx < 25 and not state["cards"][idx]["revealed"]:
                valid.append(idx)
        if valid:
            return valid
    except Exception as e:
        logger.warning("AI operative failed: %s", e)

    return []


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return json.loads(text)
