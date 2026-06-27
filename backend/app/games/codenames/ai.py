import json
import logging
import random
import re
import string
from typing import Any

from app.services.deepseek import deepseek_chat

logger = logging.getLogger(__name__)

SPYMASTER_TEMPERATURE = 0.3
OPERATIVE_TEMPERATURE = 0.5
SPYMASTER_ATTEMPTS = 3
OPERATIVE_ATTEMPTS = 3

SPYMASTER_SYSTEM = (
    "You are an expert Codenames spymaster. "
    "Think carefully about semantic associations before choosing a clue. "
    "Give precise clues that connect only your team's unrevealed words. "
    "Never lead operatives toward opponent, neutral, or assassin words. "
    "List every board word your clue might accidentally suggest in risky_words."
)

OPERATIVE_SYSTEM = (
    "You are a sharp Codenames operative with full memory of every clue given this game. "
    "Use your team's prior clues to find unrevealed words your spymaster already hinted at. "
    "Use opponent clues and revealed outcomes to avoid their words and narrow the board. "
    "Rank guesses by confidence and stop when unsure — wrong guesses end your turn."
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


def _assassin_word(cards: list[dict]) -> str | None:
    for card in cards:
        if card["color"] == "assassin" and not card["revealed"]:
            return card["word"]
    return None


def _revealed_words(cards: list[dict]) -> list[str]:
    return [c["word"] for c in cards if c["revealed"]]


def _board_words_upper(cards: list[dict]) -> set[str]:
    return {c["word"].upper() for c in cards}


def _clue_conflicts_with_board(clue: str, board_words: set[str]) -> bool:
    if clue in board_words:
        return True
    for word in board_words:
        if len(clue) >= 3 and (clue in word or word in clue):
            return True
    return False


def _is_valid_clue_word(clue: str, board_words: set[str]) -> bool:
    return bool(clue) and len(clue.split()) == 1 and not _clue_conflicts_with_board(clue, board_words)


def _game_situation(state: dict, team: str) -> tuple[int, int, str]:
    opponent = _opponent_team(team)
    team_remaining = state["red_remaining"] if team == "red" else state["blue_remaining"]
    opponent_remaining = state["blue_remaining"] if team == "red" else state["red_remaining"]

    if team_remaining <= 2:
        strategy = "Endgame: prioritize safe, precise play. One wrong guess can lose."
    elif team_remaining < opponent_remaining:
        strategy = "Behind: look for safe 2-3 word clues; take measured risks when clearly safe."
    elif team_remaining > opponent_remaining:
        strategy = "Ahead: play conservatively — avoid clues that could touch the assassin."
    else:
        strategy = "Even: balanced play — prefer safe 2-word clues when available."

    return team_remaining, opponent_remaining, strategy


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


def _risky_words_hit_avoid(data: dict[str, Any], avoid_words: list[str]) -> list[str]:
    avoid_upper = {word.upper() for word in avoid_words}
    board_by_upper = {word.upper(): word for word in avoid_words}

    hits: list[str] = []
    for raw in data.get("risky_words") or data.get("danger_words") or []:
        key = str(raw).strip().upper()
        if key in avoid_upper:
            hits.append(board_by_upper.get(key, key))
    return hits


def _validate_spymaster_response(
    data: dict[str, Any],
    valid_targets: list[str],
    board_words: set[str],
    avoid_words: list[str],
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

    if _risky_words_hit_avoid(data, avoid_words):
        return None

    return clue, number


def _build_spymaster_prompt(state: dict, team: str) -> str:
    cards = state["cards"]
    targets = _unrevealed_team_words(cards, team)
    avoid = _avoid_clue_words(cards, team)
    revealed = _revealed_words(cards)
    assassin = _assassin_word(cards)
    team_remaining, opponent_remaining, strategy = _game_situation(state, team)
    opponent = _opponent_team(team)

    target_lines = "\n".join(f"- {word}" for word in targets) or "- (none)"
    avoid_lines = "\n".join(f"- {word}" for word in avoid) or "- (none)"
    revealed_lines = "\n".join(f"- {word}" for word in revealed) or "- (none)"
    assassin_line = f"\nASSASSIN (never lead toward): {assassin}" if assassin else ""

    return f"""You are the {team.upper()} spymaster in Codenames.

GAME STATE:
- Your team ({team.upper()}): {team_remaining} words remaining
- Opponent ({opponent.upper()}): {opponent_remaining} words remaining
- Strategy: {strategy}

YOUR TARGETS — unrevealed {team} words only. Your clue must apply ONLY to words from this list:
{target_lines}

NEVER LEAD TOWARD — if your clue could suggest any of these unrevealed words, choose a different clue:
{avoid_lines}{assassin_line}

ALREADY REVEALED — ignore these when choosing a clue:
{revealed_lines}

Rules:
- clue: exactly ONE word, not on the board, not a substring of any board word
- number: how many of YOUR TARGETS the clue applies to (must match targets list length)
- targets: the specific words from YOUR TARGETS that the clue is meant for
- risky_words: unrevealed board words your clue might accidentally suggest (list all plausible ones)
- prefer safe clues for 2-3 targets when possible; use 1 if no safe multi-word clue exists
- if any risky_words are opponent, neutral, or assassin words, pick a different clue

Think step by step, then respond ONLY with JSON:
{{"reasoning": "brief explanation", "clue": "WORD", "number": N, "targets": ["TARGET1"], "risky_words": ["MAYBE1"]}}"""


def _format_clue_entry(entry: dict, *, current: bool = False) -> str:
    clue = entry.get("clue") or {}
    word = clue.get("word", "?")
    number = clue.get("number", 0)
    guesses = entry.get("guesses") or []
    if current and not entry.get("completed"):
        return f'- "{word}" {number}: (current clue)'
    if guesses:
        guess_desc = ", ".join(f"{g['word']} ({g['color']})" for g in guesses)
        return f'- "{word}" {number}: guessed {guess_desc}'
    return f'- "{word}" {number}: turn ended with no guesses'


def _format_clue_history(state: dict, team: str, *, include_current: bool = True) -> str:
    history = state.get("clue_history", {}).get(team, [])
    if not history:
        return "None yet."

    lines: list[str] = []
    for entry in history:
        if not include_current and not entry.get("completed"):
            continue
        if include_current and not entry.get("completed"):
            lines.append(_format_clue_entry(entry, current=True))
        else:
            lines.append(_format_clue_entry(entry))
    return "\n".join(lines) if lines else "None yet."


def _summarize_unresolved_clues(state: dict, team: str) -> str:
    """Clues whose full target count was not found before the turn ended."""
    history = state.get("clue_history", {}).get(team, [])
    lines: list[str] = []
    for entry in history:
        if not entry.get("completed"):
            continue
        clue = entry.get("clue") or {}
        word = clue.get("word")
        number = clue.get("number", 0)
        if not word or number <= 0:
            continue
        guesses = entry.get("guesses") or []
        team_hits = sum(1 for g in guesses if g.get("color") == team)
        if team_hits < number:
            remaining = number - team_hits
            lines.append(
                f'- "{word}" {number}: only {team_hits} team word(s) found; '
                f"up to {remaining} unrevealed target(s) may still relate to this clue"
            )
    return "\n".join(lines) if lines else "None — focus on the current clue."


def _build_operative_prompt(state: dict, team: str, max_guesses: int) -> str:
    clue = state.get("current_clue") or {}
    clue_word = clue.get("word", "")
    clue_number = clue.get("number", 0)
    team_remaining, opponent_remaining, strategy = _game_situation(state, team)
    guesses_remaining = state.get("guesses_remaining", max_guesses)

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
    opponent = _opponent_team(team)
    team_history = _format_clue_history(state, team, include_current=False)
    opponent_history = _format_clue_history(state, opponent, include_current=False)
    unresolved = _summarize_unresolved_clues(state, team)

    return f"""You are a {team.upper()} operative in Codenames.

GAME STATE:
- Your team: {team_remaining} words left | Opponent: {opponent_remaining} words left
- Guesses remaining this turn: {guesses_remaining} (includes 1 bonus guess beyond clue number)
- Strategy: {strategy}

CURRENT CLUE: "{clue_word}" for {clue_number} word(s)

YOUR TEAM'S PRIOR CLUES (use these to infer unrevealed team words):
{team_history}

UNRESOLVED PRIOR CLUES (may still point at unrevealed cards on the board):
{unresolved}

OPPONENT'S PRIOR CLUES (public — avoid words they were likely targeting):
{opponent_history}

Unrevealed cards (color hidden — only spymasters know colors):
{json.dumps(unrevealed)}

Revealed cards (do not guess these):
{json.dumps(revealed)}

Use prior clues together with the current clue — earlier spymaster hints often still apply to
unrevealed words. Cross-reference revealed guess outcomes (team/opponent/neutral) from past turns.

Pick up to {limit} unrevealed card indices related to "{clue_word}", ordered by confidence.
Stop early if unsure — guessing an opponent, neutral, or assassin word ends your turn.
You may guess at most {clue_number} cards unless very confident about a bonus guess (confidence >= 0.75).

Think step by step, then respond ONLY with JSON:
{{"reasoning": "brief explanation", "guesses": [{{"index": 0, "confidence": 0.9}}, ...]}}
Use card index values 0-24. Only unrevealed cards. Confidence is 0.0-1.0."""


def _random_generic_clue(state: dict) -> str:
    board_words = _board_words_upper(state["cards"])
    options = [word for word in FALLBACK_CLUES if not _clue_conflicts_with_board(word, board_words)]
    if options:
        return random.choice(options)

    while True:
        word = "".join(random.choices(string.ascii_uppercase, k=5))
        if not _clue_conflicts_with_board(word, board_words):
            return word


def _parse_operative_guesses(
    data: dict[str, Any],
    state: dict,
    limit: int,
    clue_number: int,
    team: str,
) -> list[int]:
    team_remaining, opponent_remaining, _ = _game_situation(state, team)
    threshold = 0.45 if team_remaining < opponent_remaining else 0.55
    bonus_threshold = 0.75

    raw = data.get("guesses", [])
    parsed: list[tuple[int, float]] = []
    for item in raw:
        if isinstance(item, dict):
            try:
                idx = int(item.get("index", -1))
                conf = float(item.get("confidence", 0.75))
            except (TypeError, ValueError):
                continue
        else:
            try:
                idx = int(item)
                conf = 0.75
            except (TypeError, ValueError):
                continue
        if 0 <= idx < 25 and not state["cards"][idx]["revealed"]:
            parsed.append((idx, max(0.0, min(1.0, conf))))

    seen: set[int] = set()
    unique: list[tuple[int, float]] = []
    for idx, conf in parsed:
        if idx not in seen:
            seen.add(idx)
            unique.append((idx, conf))

    result: list[int] = []
    for i, (idx, conf) in enumerate(unique[:limit]):
        if i < clue_number:
            if conf >= threshold:
                result.append(idx)
            else:
                break
        elif conf >= bonus_threshold:
            result.append(idx)
        else:
            break
    return result


async def fallback_clue(state: dict, team: str) -> tuple[str, int]:
    targets = _unrevealed_team_words(state["cards"], team)
    if not targets:
        return _random_generic_clue(state), 1

    board_words = _board_words_upper(state["cards"])
    avoid = _avoid_clue_words(state["cards"], team)
    other_board_words = [c["word"] for c in state["cards"] if c["word"] not in targets]

    for target in random.sample(targets, min(len(targets), 5)):
        prompt = f"""Give a Codenames spymaster clue for exactly this one target word:
{target}

Do NOT suggest any of these other board words:
{", ".join(avoid + [word for word in other_board_words if word != target])}

Respond ONLY with JSON:
{{"clue": "WORD", "number": 1, "targets": ["{target}"], "risky_words": []}}"""

        try:
            response = await deepseek_chat(
                prompt,
                system=SPYMASTER_SYSTEM,
                temperature=SPYMASTER_TEMPERATURE,
                json_mode=True,
            )
            data = _parse_json(response)
            validated = _validate_spymaster_response(data, targets, board_words, avoid)
            if validated:
                return validated
        except Exception as e:
            logger.warning("Focused fallback clue failed for %s: %s", target, e)

    return _random_generic_clue(state), 1


async def ai_spymaster_clue(state: dict, team: str) -> tuple[str, int]:
    cards = state["cards"]
    targets = _unrevealed_team_words(cards, team)
    board_words = _board_words_upper(cards)
    avoid = _avoid_clue_words(cards, team)

    if not targets:
        return _random_generic_clue(state), 1

    prompt = _build_spymaster_prompt(state, team)
    feedback = ""

    for attempt in range(SPYMASTER_ATTEMPTS):
        try:
            full_prompt = prompt if not feedback else f"{prompt}\n\nPrevious invalid response:\n{feedback}"
            response = await deepseek_chat(
                full_prompt,
                system=SPYMASTER_SYSTEM,
                temperature=SPYMASTER_TEMPERATURE,
                json_mode=True,
            )
            data = _parse_json(response)
            validated = _validate_spymaster_response(data, targets, board_words, avoid)
            if validated:
                return validated

            risky_hits = _risky_words_hit_avoid(data, avoid)
            if risky_hits:
                feedback = (
                    f"{json.dumps(data)}\n"
                    f"Invalid: clue would suggest dangerous words: {', '.join(risky_hits)}. "
                    "Choose a different clue or different targets."
                )
            else:
                feedback = (
                    f"{json.dumps(data)}\n"
                    "Invalid: clue must be one board-external word (no substring overlap), "
                    f"targets must be unrevealed {team} words only, "
                    "number must equal len(targets), and risky_words must not include danger words."
                )
        except Exception as e:
            logger.warning("AI spymaster attempt %s failed: %s", attempt + 1, e)
            feedback = str(e)

    return await fallback_clue(state, team)


async def ai_operative_guesses(state: dict, team: str, max_guesses: int) -> list[int]:
    clue = state.get("current_clue") or {}
    clue_word = clue.get("word", "")
    clue_number = clue.get("number", 0)

    if not clue_word:
        return []

    limit = max_guesses if clue_number > 0 else min(max_guesses, 3)
    prompt = _build_operative_prompt(state, team, max_guesses)
    feedback = ""

    for attempt in range(OPERATIVE_ATTEMPTS):
        try:
            full_prompt = prompt if not feedback else f"{prompt}\n\nPrevious invalid response:\n{feedback}"
            response = await deepseek_chat(
                full_prompt,
                system=OPERATIVE_SYSTEM,
                temperature=OPERATIVE_TEMPERATURE,
                json_mode=True,
            )
            data = _parse_json(response)
            guesses = _parse_operative_guesses(data, state, limit, clue_number, team)
            if guesses:
                return guesses

            feedback = (
                f"{json.dumps(data)}\n"
                "Invalid: provide guesses as "
                '[{"index": N, "confidence": 0.0-1.0}, ...] using unrevealed card indices only.'
            )
        except Exception as e:
            logger.warning("AI operative attempt %s failed: %s", attempt + 1, e)
            feedback = str(e)

    return []


def _extract_json_objects(text: str) -> list[dict[str, Any]]:
    text = text.strip()
    if not text:
        return []

    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()

    decoder = json.JSONDecoder()
    objects: list[dict[str, Any]] = []
    i = 0
    while i < len(text):
        if text[i] != "{":
            i += 1
            continue
        try:
            obj, end = decoder.raw_decode(text, i)
            if isinstance(obj, dict):
                objects.append(obj)
            i = end if end > i else i + 1
        except json.JSONDecodeError:
            i += 1
    return objects


def _parse_json(text: str) -> dict[str, Any]:
    objects = _extract_json_objects(text)
    if not objects:
        raise json.JSONDecodeError("No JSON object found", text, 0)

    # Models sometimes emit a short preamble object then the real payload.
    preferred_keys = ("clue", "guesses", "targets", "number")
    for key in preferred_keys:
        for obj in reversed(objects):
            if key in obj:
                return obj

    return max(objects, key=len)
