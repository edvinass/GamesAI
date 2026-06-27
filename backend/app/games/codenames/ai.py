import json
import logging
import random
import re
import string
from typing import Any

from app.services.deepseek import deepseek_chat

logger = logging.getLogger(__name__)

SPYMASTER_SYSTEM = (
    "You are an expert Codenames spymaster. "
    "Give precise clues that connect only your team's unrevealed words. "
    "Never lead operatives toward opponent, neutral, or assassin words."
)

OPERATIVE_SYSTEM = (
    "You are a careful Codenames operative. "
    "Guess only when the clue clearly applies. Wrong guesses end your turn."
)

FALLBACK_CLUES = [
    "LINK", "GROUP", "SET", "TYPE", "KIND", "THEME", "IDEA", "FIELD",
    "ORDER", "POINT", "SPACE", "WORLD", "STORY", "MOTION", "VISION",
]


def _opponent_team(team: str) -> str:
    return "blue" if team == "red" else "red"


def _unrevealed_team_words(cards: list[dict], team: str) -> list[str]:
    return [c["word"] for c in cards if c["color"] == team and not c["revealed"]]


def _avoid_clue_words(cards: list[dict], team: str) -> list[str]:
    opponent = _opponent_team(team)
    avoid: list[str] = []
    for card in cards:
        if card["revealed"]:
            continue
        if card["color"] in (opponent, "assassin", "neutral"):
            avoid.append(card["word"])
    return avoid


def _revealed_words(cards: list[dict]) -> list[str]:
    return [c["word"] for c in cards if c["revealed"]]


def _board_words_upper(cards: list[dict]) -> set[str]:
    return {c["word"].upper() for c in cards}


def _is_valid_clue_word(clue: str, board_words: set[str]) -> bool:
    return bool(clue) and clue not in board_words and len(clue.split()) == 1


def _normalize_target_words(raw_targets: Any, valid_targets: list[str]) -> list[str] | None:
    if not isinstance(raw_targets, list) or not raw_targets:
        return None

    valid_by_upper = {word.upper(): word for word in valid_targets}
    normalized: list[str] = []
    for raw in raw_targets:
        key = str(raw).strip().upper()
        if key not in valid_by_upper:
            return None
        word = valid_by_upper[key]
        if word not in normalized:
            normalized.append(word)
    return normalized or None


def _validate_spymaster_response(
    data: dict[str, Any],
    valid_targets: list[str],
    board_words: set[str],
) -> tuple[str, int] | None:
    clue = str(data.get("clue", "")).strip().upper()
    if not _is_valid_clue_word(clue, board_words):
        return None

    try:
        number = int(data.get("number", 0))
    except (TypeError, ValueError):
        return None

    targets = _normalize_target_words(data.get("targets"), valid_targets)
    if not targets or number != len(targets):
        return None

    return clue, number


def _build_spymaster_prompt(state: dict, team: str) -> str:
    cards = state["cards"]
    targets = _unrevealed_team_words(cards, team)
    avoid = _avoid_clue_words(cards, team)
    revealed = _revealed_words(cards)
    team_remaining = state["red_remaining"] if team == "red" else state["blue_remaining"]

    target_lines = "\n".join(f"- {word}" for word in targets) or "- (none)"
    avoid_lines = "\n".join(f"- {word}" for word in avoid) or "- (none)"
    revealed_lines = "\n".join(f"- {word}" for word in revealed) or "- (none)"

    return f"""You are the {team.upper()} spymaster in Codenames.

YOUR TARGETS — unrevealed {team} words only. Your clue must apply ONLY to words from this list:
{target_lines}

NEVER LEAD TOWARD — if your clue could suggest any of these unrevealed words, choose a different clue:
{avoid_lines}

ALREADY REVEALED — ignore these when choosing a clue:
{revealed_lines}

Your team has {team_remaining} words left to find.

Rules:
- clue: exactly ONE word, not on the board, not a substring of any board word
- number: how many of YOUR TARGETS the clue applies to (must match targets list length)
- targets: the specific words from YOUR TARGETS that the clue is meant for
- prefer safe clues for 2-3 targets when possible; use 1 if no safe multi-word clue exists
- never include opponent, neutral, or assassin words in targets

Respond ONLY with JSON:
{{"clue": "WORD", "number": N, "targets": ["TARGET1", "TARGET2"]}}"""


def _random_generic_clue(state: dict) -> str:
    board_words = _board_words_upper(state["cards"])
    options = [word for word in FALLBACK_CLUES if word not in board_words]
    if options:
        return random.choice(options)

    while True:
        word = "".join(random.choices(string.ascii_uppercase, k=5))
        if word not in board_words:
            return word


async def fallback_clue(state: dict, team: str) -> tuple[str, int]:
    targets = _unrevealed_team_words(state["cards"], team)
    if not targets:
        return _random_generic_clue(state), 1

    board_words = _board_words_upper(state["cards"])
    avoid = _avoid_clue_words(state["cards"], team)
    other_board_words = [c["word"] for c in state["cards"] if c["word"] not in targets]

    for target in random.sample(targets, min(len(targets), 3)):
        prompt = f"""Give a Codenames spymaster clue for exactly this one target word:
{target}

Do NOT suggest any of these other board words:
{", ".join(avoid + [word for word in other_board_words if word != target])}

Respond ONLY with JSON:
{{"clue": "WORD", "number": 1, "targets": ["{target}"]}}"""

        try:
            response = await deepseek_chat(prompt, system=SPYMASTER_SYSTEM)
            data = _parse_json(response)
            validated = _validate_spymaster_response(data, targets, board_words)
            if validated:
                return validated
        except Exception as e:
            logger.warning("Focused fallback clue failed for %s: %s", target, e)

    return _random_generic_clue(state), 1


async def ai_spymaster_clue(state: dict, team: str) -> tuple[str, int]:
    cards = state["cards"]
    targets = _unrevealed_team_words(cards, team)
    board_words = _board_words_upper(cards)

    if not targets:
        return _random_generic_clue(state), 1

    prompt = _build_spymaster_prompt(state, team)
    feedback = ""

    for attempt in range(3):
        try:
            full_prompt = prompt if not feedback else f"{prompt}\n\nPrevious invalid response:\n{feedback}"
            response = await deepseek_chat(full_prompt, system=SPYMASTER_SYSTEM)
            data = _parse_json(response)
            validated = _validate_spymaster_response(data, targets, board_words)
            if validated:
                return validated

            feedback = (
                f"{json.dumps(data)}\n"
                "Invalid: clue must be one board-external word, targets must be unrevealed "
                f"{team} words only, and number must equal len(targets)."
            )
        except Exception as e:
            logger.warning("AI spymaster attempt %s failed: %s", attempt + 1, e)
            feedback = str(e)

    return await fallback_clue(state, team)


async def ai_operative_guesses(state: dict, team: str, max_guesses: int) -> list[int]:
    clue = state.get("current_clue") or {}
    clue_word = clue.get("word", "")
    clue_number = clue.get("number", 0)

    unrevealed = []
    revealed = []
    for card in state["cards"]:
        if card["revealed"]:
            revealed.append(
                {"index": card["index"], "word": card["word"], "color": card["color"]}
            )
        else:
            unrevealed.append({"index": card["index"], "word": card["word"]})

    limit = max_guesses if clue_number > 0 else min(max_guesses, 3)

    prompt = f"""You are a {team.upper()} operative in Codenames.
Your spymaster gave clue "{clue_word}" for {clue_number} word(s).

Unrevealed cards (color hidden — only spymasters know colors):
{json.dumps(unrevealed)}

Revealed cards (do not guess these):
{json.dumps(revealed)}

Pick up to {limit} unrevealed card indices related to "{clue_word}", in confidence order.
Stop early if unsure — guessing an opponent, neutral, or assassin word ends your turn.
You may guess at most {clue_number} cards unless you are very confident about a bonus guess.

Respond ONLY with JSON: {{"guesses": [index1, index2, ...]}}
Use card index values 0-24. Only unrevealed cards."""

    try:
        response = await deepseek_chat(prompt, system=OPERATIVE_SYSTEM)
        data = _parse_json(response)
        guesses = data.get("guesses", [])
        valid = []
        for guess in guesses[:limit]:
            idx = int(guess)
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
