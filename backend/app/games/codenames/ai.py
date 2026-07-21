import itertools
import json
import logging
import random
import re
import string
from typing import Any

from app.games.codenames.clue_validation import (
    board_words_upper,
    conflicting_board_word,
    validate_clue_word,
)
from app.services.deepseek import deepseek_chat

logger = logging.getLogger(__name__)

SPYMASTER_TEMPERATURE = 0.3
OPERATIVE_TEMPERATURE = 0.5
OPERATIVE_ATTEMPTS = 3
SELF_CHECK_ATTEMPTS = 2
SELF_CHECK_ATTEMPTS_MULTI = 3
SELF_CHECK_CONFIDENCE = 0.35
MIN_MULTI_TARGETS = 2

SPYMASTER_SYSTEM = (
    "You are an expert Codenames spymaster with full memory of every clue given this game. "
    "Track what your operatives found, missed, and guessed wrong — build on prior clues when "
    "targets remain unrevealed, and avoid repeating associations that led to mistakes. "
    "Default to linking 2-3 team words with one clue — single-word clues are a last resort. "
    "Never lead operatives toward opponent, neutral, or assassin words. "
    "List every board word your clue might accidentally suggest in risky_words."
)

OPERATIVE_SYSTEM = (
    "You are a sharp Codenames operative with full memory of every clue given this game. "
    "Use your team's prior clues to find unrevealed words your spymaster already hinted at. "
    "Use opponent clues and revealed outcomes to avoid their words and narrow the board. "
    "The bonus guess is only for words missed from earlier clues — never for the current clue."
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


def _game_situation(state: dict, team: str) -> tuple[int, int, str]:
    opponent = _opponent_team(team)
    team_remaining = state["red_remaining"] if team == "red" else state["blue_remaining"]
    opponent_remaining = state["blue_remaining"] if team == "red" else state["red_remaining"]

    if team_remaining <= 2:
        strategy = (
            "Endgame: prioritize safe, precise play. One wrong guess can lose. "
            "1-word clues are OK here."
        )
    elif team_remaining < opponent_remaining:
        strategy = (
            "Behind: give a safe 2-3 word clue whenever possible — "
            "avoid falling back to 1-word clues."
        )
    elif team_remaining > opponent_remaining:
        strategy = (
            "Ahead: still prefer safe 2-word clues; only go to 1 if a multi-word clue "
            "would risk the assassin."
        )
    else:
        strategy = (
            "Even: prefer safe 2-3 word clues. Single-word clues make the game slow — avoid them."
        )

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
) -> tuple[str, int, list[str]] | None:
    clue = str(data.get("clue", "")).strip().upper()
    if validate_clue_word(clue, board_words) is not None:
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

    return clue, number, targets


def _build_spymaster_prompt(state: dict, team: str) -> str:
    cards = state["cards"]
    targets = _unrevealed_team_words(cards, team)
    avoid = _avoid_clue_words(cards, team)
    assassin = _assassin_word(cards)
    team_remaining, opponent_remaining, strategy = _game_situation(state, team)
    opponent = _opponent_team(team)

    target_lines = "\n".join(f"- {word}" for word in targets) or "- (none)"
    avoid_lines = "\n".join(f"- {word}" for word in avoid) or "- (none)"
    assassin_line = f"\nASSASSIN (never lead toward): {assassin}" if assassin else ""

    team_history = _format_clue_history(state, team, include_current=False)
    opponent_history = _format_clue_history(state, opponent, include_current=False)
    unresolved = _summarize_unresolved_clues_for_spymaster(state, team)
    mistakes = _summarize_operative_mistakes(state, team)
    revealed_intel = _format_revealed_intel(state, team)
    used_clues = _used_clue_words(state, team)

    return f"""You are the {team.upper()} spymaster in Codenames.

GAME STATE:
- Your team ({team.upper()}): {team_remaining} words remaining
- Opponent ({opponent.upper()}): {opponent_remaining} words remaining
- Strategy: {strategy}

YOUR TARGETS — unrevealed {team} words only. Your clue must apply ONLY to words from this list:
{target_lines}

NEVER LEAD TOWARD — if your clue could suggest any of these unrevealed words, choose a different clue:
{avoid_lines}{assassin_line}

REVEALED BOARD (what operatives know):
{revealed_intel}

YOUR PRIOR CLUES AND OPERATIVE RESULTS:
{team_history}

UNRESOLVED TARGETS (prior clues whose words operatives have not fully found):
{unresolved}

OPERATIVE MISTAKES (wrong guesses — avoid similar associations):
{mistakes}

CLUE WORDS ALREADY USED BY YOUR TEAM (prefer fresh associations):
{used_clues}

OPPONENT'S PRIOR CLUES (avoid overlapping their semantic space):
{opponent_history}

Rules:
- clue: exactly ONE word, not on the board, not a substring of any board word
- number: how many of YOUR TARGETS the clue applies to (must match targets list length)
- targets: the specific words from YOUR TARGETS that the clue is meant for
- risky_words: unrevealed board words your clue might accidentally suggest (list all plausible ones)
- REQUIRED when 3+ team words remain: aim for 2-3 targets. Use number=1 only in endgame or when no safe pair exists
- if unresolved targets remain from a prior clue, consider a follow-up clue for those words
- if any risky_words are opponent, neutral, or assassin words, pick a different clue

Respond ONLY with compact JSON (no extra keys):
{{"clue": "WORD", "number": 2, "targets": ["TARGET1", "TARGET2"], "risky_words": ["MAYBE1"]}}"""


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


def _guesses_made_this_turn(state: dict, team: str) -> int:
    history = state.get("clue_history", {}).get(team, [])
    if history and not history[-1].get("completed"):
        return len(history[-1].get("guesses") or [])
    return 0


def _has_unresolved_prior_clues(state: dict, team: str) -> bool:
    return _summarize_unresolved_clues(state, team) != "None — focus on the current clue."


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


def _summarize_unresolved_clues_for_spymaster(state: dict, team: str) -> str:
    """Prior clues with unrevealed intended targets, when recorded."""
    history = state.get("clue_history", {}).get(team, [])
    unrevealed_team = set(_unrevealed_team_words(state["cards"], team))
    lines: list[str] = []
    for entry in history:
        if not entry.get("completed"):
            continue
        clue = entry.get("clue") or {}
        word = clue.get("word")
        number = clue.get("number", 0)
        if not word:
            continue
        intended = entry.get("targets") or []
        still_unfound = [t for t in intended if t in unrevealed_team]
        if still_unfound:
            lines.append(
                f'- "{word}" {number}: intended {", ".join(intended)}; '
                f"still unrevealed: {', '.join(still_unfound)}"
            )
            continue
        if intended:
            continue
        guesses = entry.get("guesses") or []
        team_hits = sum(1 for g in guesses if g.get("color") == team)
        if number > 0 and team_hits < number:
            remaining = number - team_hits
            lines.append(
                f'- "{word}" {number}: operatives found {team_hits} team word(s); '
                f"up to {remaining} target(s) likely still unrevealed"
            )
    return "\n".join(lines) if lines else "None — all prior targets found or no prior clues."


def _summarize_operative_mistakes(state: dict, team: str) -> str:
    history = state.get("clue_history", {}).get(team, [])
    lines: list[str] = []
    for entry in history:
        if not entry.get("completed"):
            continue
        clue_word = (entry.get("clue") or {}).get("word", "?")
        for guess in entry.get("guesses") or []:
            color = guess.get("color")
            if color and color != team:
                lines.append(
                    f'- On "{clue_word}": guessed {guess["word"]} ({color}) — '
                    "avoid clues that could suggest this word"
                )
    return "\n".join(lines) if lines else "None."


def _format_revealed_intel(state: dict, team: str) -> str:
    opponent = _opponent_team(team)
    by_color: dict[str, list[str]] = {"red": [], "blue": [], "neutral": [], "assassin": []}
    for card in state["cards"]:
        if card["revealed"]:
            by_color[card["color"]].append(card["word"])

    lines = [
        f"- Your team ({team}): {', '.join(by_color[team]) or 'none'}",
        f"- Opponent ({opponent}): {', '.join(by_color[opponent]) or 'none'}",
        f"- Neutral: {', '.join(by_color['neutral']) or 'none'}",
    ]
    if by_color["assassin"]:
        lines.append(f"- Assassin (revealed): {', '.join(by_color['assassin'])}")
    return "\n".join(lines)


def _used_clue_words(state: dict, team: str) -> str:
    words = [
        (entry.get("clue") or {}).get("word")
        for entry in state.get("clue_history", {}).get(team, [])
        if (entry.get("clue") or {}).get("word")
    ]
    return ", ".join(words) if words else "None"


def _parse_guess_item(item: Any, state: dict) -> tuple[int, float] | None:
    if isinstance(item, dict):
        try:
            idx = int(item.get("index", -1))
            conf = float(item.get("confidence", 0.75))
        except (TypeError, ValueError):
            return None
    else:
        try:
            idx = int(item)
            conf = 0.75
        except (TypeError, ValueError):
            return None
    if 0 <= idx < 25 and not state["cards"][idx]["revealed"]:
        return idx, max(0.0, min(1.0, conf))
    return None


def _parse_guess_list(raw: Any, state: dict) -> list[tuple[int, float]]:
    if not isinstance(raw, list):
        return []

    parsed: list[tuple[int, float]] = []
    seen: set[int] = set()
    for item in raw:
        guess = _parse_guess_item(item, state)
        if guess and guess[0] not in seen:
            seen.add(guess[0])
            parsed.append(guess)
    return parsed


def _build_operative_prompt(state: dict, team: str, max_guesses: int) -> str:
    clue = state.get("current_clue") or {}
    clue_word = clue.get("word", "")
    clue_number = clue.get("number", 0)
    team_remaining, opponent_remaining, strategy = _game_situation(state, team)
    guesses_remaining = state.get("guesses_remaining", max_guesses)
    guesses_made = _guesses_made_this_turn(state, team)
    has_unresolved = _has_unresolved_prior_clues(state, team)
    regular_slots_left = max(0, clue_number - guesses_made)
    bonus_only = clue_number > 0 and guesses_made >= clue_number

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

    if bonus_only:
        guess_section = f"""This is your bonus guess only. Do NOT guess a word for the current clue "{clue_word}".
Review UNRESOLVED PRIOR CLUES and pick one unrevealed word likely related to an earlier clue.

Respond ONLY with compact JSON (no extra keys):
{{"bonus_guess": {{"index": 0, "confidence": 0.9}}}}"""
    else:
        bonus_lines = ""
        if has_unresolved and guesses_made + regular_slots_left < clue_number + 1:
            bonus_lines = (
                f"\nAfter up to {regular_slots_left} current-clue guess(es), include bonus_guess "
                "for one word from UNRESOLVED PRIOR CLUES only — never for the current clue. "
                "Set bonus_guess to null if no prior clue word is worth trying."
            )
        elif has_unresolved:
            bonus_lines = (
                "\nNo bonus guess this call — use remaining guesses for the current clue first."
            )
        else:
            bonus_lines = (
                "\nDo not include bonus_guess — there are no unresolved prior clues to revisit."
            )

        guess_section = f"""Pick up to {min(regular_slots_left, limit)} unrevealed card indices for the CURRENT clue only,
ordered by confidence. Stop early if unsure — wrong guesses end your turn.{bonus_lines}

Respond ONLY with compact JSON (no extra keys):
{{"current_guesses": [{{"index": 0, "confidence": 0.9}}], "bonus_guess": null}}"""

    return f"""You are a {team.upper()} operative in Codenames.

GAME STATE:
- Your team: {team_remaining} words left | Opponent: {opponent_remaining} words left
- Guesses remaining this turn: {guesses_remaining} (includes 1 bonus guess beyond clue number)
- Guesses already made this turn: {guesses_made}
- Strategy: {strategy}

CURRENT CLUE: "{clue_word}" for {clue_number} word(s)

YOUR TEAM'S PRIOR CLUES (use these to infer unrevealed team words):
{team_history}

UNRESOLVED PRIOR CLUES (bonus guess targets — not the current clue):
{unresolved}

OPPONENT'S PRIOR CLUES (public — avoid words they were likely targeting):
{opponent_history}

Unrevealed cards (color hidden — only spymasters know colors):
{json.dumps(unrevealed)}

Revealed cards (do not guess these):
{json.dumps(revealed)}

Use prior clues together with the current clue — earlier spymaster hints often still apply to
unrevealed words. Cross-reference revealed guess outcomes (team/opponent/neutral) from past turns.

{guess_section}
Use card index values 0-24. Only unrevealed cards. Confidence is 0.0-1.0."""


def _random_generic_clue(state: dict) -> str:
    board_words = board_words_upper(state["cards"])
    options = [word for word in FALLBACK_CLUES if conflicting_board_word(word, board_words) is None]
    if options:
        return random.choice(options)

    while True:
        word = "".join(random.choices(string.ascii_uppercase, k=5))
        if conflicting_board_word(word, board_words) is None:
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
    has_unresolved = _has_unresolved_prior_clues(state, team)
    guesses_made = _guesses_made_this_turn(state, team)
    regular_slots_left = max(0, clue_number - guesses_made)
    bonus_only = clue_number > 0 and guesses_made >= clue_number

    if bonus_only:
        if not has_unresolved:
            return []
        bonus = _parse_guess_item(data.get("bonus_guess"), state)
        if bonus and bonus[1] >= threshold:
            return [bonus[0]][:limit]
        return []

    current_candidates = _parse_guess_list(data.get("current_guesses"), state)
    if not current_candidates and isinstance(data.get("guesses"), list):
        current_candidates = _parse_guess_list(data.get("guesses"), state)

    result: list[int] = []
    for idx, conf in current_candidates:
        if len(result) >= regular_slots_left or len(result) >= limit:
            break
        if conf >= threshold:
            result.append(idx)
        else:
            break

    bonus_available = (
        clue_number > 0
        and has_unresolved
        and guesses_made + len(result) < clue_number + 1
        and len(result) < limit
    )
    if bonus_available:
        bonus = _parse_guess_item(data.get("bonus_guess"), state)
        if bonus and bonus[0] not in result and bonus[1] >= threshold:
            result.append(bonus[0])

    return result[:limit]


def _fallback_target_groups(targets: list[str]) -> list[list[str]]:
    """Ordered fallback target sets: prefer triples, then pairs, then singles."""
    words = list(targets)
    random.shuffle(words)
    groups: list[list[str]] = []

    for size, limit in ((3, 2), (2, 3), (1, 3)):
        if len(words) < size:
            continue
        if size == 1:
            groups.extend([[word] for word in words[:limit]])
            continue
        combos = list(itertools.combinations(words, size))
        random.shuffle(combos)
        for combo in combos[:limit]:
            groups.append(list(combo))

    return groups


def _build_focused_fallback_prompt(
    group: list[str],
    avoid: list[str],
    other_board_words: list[str],
) -> str:
    n = len(group)
    avoid_list = ", ".join(
        avoid + [word for word in other_board_words if word not in group]
    )
    targets_json = json.dumps(group)

    if n == 1:
        intro = (
            "Give a Codenames spymaster clue for exactly this one target word:\n"
            f"{group[0]}"
        )
    else:
        target_lines = "\n".join(f"- {word}" for word in group)
        intro = (
            f"Give a Codenames spymaster clue that connects ALL of these {n} "
            f"target words (and only these):\n{target_lines}"
        )

    return f"""{intro}

Do NOT suggest any of these other board words:
{avoid_list}

The clue must apply to every listed target. number must be {n}.
Respond ONLY with JSON:
{{"clue": "WORD", "number": {n}, "targets": {targets_json}, "risky_words": []}}"""


def _accept_focused_fallback(
    validated: tuple[str, int, list[str]],
    group: list[str],
) -> bool:
    """Accept multi-target fallback only when the model kept a multi-word link."""
    _, number, chosen = validated
    if not set(chosen).issubset(set(group)):
        return False
    if len(group) >= 2 and number < 2:
        return False
    return True


def _cards_by_index(state: dict) -> dict[int, dict]:
    return {int(c.get("index", i)): c for i, c in enumerate(state["cards"])}


def _state_for_clue_self_check(state: dict, team: str, clue: str, number: int) -> dict:
    """Fresh guess turn with the candidate clue, no in-progress guesses."""
    sim = dict(state)
    sim["current_clue"] = {"word": clue, "number": number}
    sim["guesses_remaining"] = number + 1

    history = state.get("clue_history") or {}
    team_hist = list(history.get(team, []))
    if team_hist and not team_hist[-1].get("completed"):
        team_hist = team_hist[:-1]
    sim["clue_history"] = {**{k: list(v) for k, v in history.items()}, team: team_hist}
    return sim


def _guessed_words_for_feedback(state: dict, guess_indices: list[int]) -> list[str]:
    by_index = _cards_by_index(state)
    words: list[str] = []
    for idx in guess_indices:
        card = by_index.get(idx)
        if card:
            words.append(str(card["word"]))
        else:
            words.append(f"#{idx}")
    return words


def _min_acceptable_targets(state: dict, team: str) -> int:
    team_remaining, _, _ = _game_situation(state, team)
    if team_remaining <= 2 or len(_unrevealed_team_words(state["cards"], team)) < 2:
        return 1
    return MIN_MULTI_TARGETS


def _safe_recovered_targets(
    state: dict,
    team: str,
    targets: list[str],
    guess_indices: list[int],
) -> list[str] | None:
    """
    Targets recovered safely from operative guesses.

    Returns None if any guess is opponent/assassin (hard fail).
    Otherwise returns intended targets that appear in the guess window,
    preserving intended order.
    """
    if not targets or not guess_indices:
        return []

    opponent = _opponent_team(team)
    by_index = _cards_by_index(state)
    intended_by_upper = {word.upper(): word for word in targets}
    recovered: list[str] = []

    for idx in guess_indices[: len(targets)]:
        card = by_index.get(idx)
        if not card or card.get("revealed"):
            continue
        color = card.get("color")
        if color in (opponent, "assassin"):
            return None
        key = str(card["word"]).upper()
        word = intended_by_upper.get(key)
        if word and word not in recovered:
            recovered.append(word)

    return recovered


def _clue_self_check_passes(
    state: dict,
    team: str,
    targets: list[str],
    guess_indices: list[int],
) -> bool:
    """True if guesses cover all targets and never hit opponent/assassin."""
    recovered = _safe_recovered_targets(state, team, targets, guess_indices)
    if recovered is None:
        return False
    return len(recovered) == len(targets) and set(recovered) == set(targets)


def _resolve_self_check_targets(
    state: dict,
    team: str,
    targets: list[str],
    guess_indices: list[int],
) -> list[str] | None:
    """Full match or safe partial multi-target recovery worth keeping."""
    recovered = _safe_recovered_targets(state, team, targets, guess_indices)
    if recovered is None:
        return None
    min_keep = _min_acceptable_targets(state, team)
    if len(recovered) == len(targets):
        return list(targets)
    if len(recovered) >= min_keep:
        return recovered
    return None


async def _simulate_operative_guesses(
    state: dict,
    team: str,
    clue: str,
    number: int,
) -> list[int]:
    """One-shot operative simulation for self-check (current-clue guesses only)."""
    if number <= 0:
        return []

    sim = _state_for_clue_self_check(state, team, clue, number)
    prompt = _build_operative_prompt(sim, team, number)

    try:
        response = await deepseek_chat(
            prompt,
            system=OPERATIVE_SYSTEM,
            temperature=OPERATIVE_TEMPERATURE,
            json_mode=True,
        )
        data = _parse_json(response)
    except Exception as e:
        logger.warning("Clue self-check operative simulation failed: %s", e)
        return []

    current_candidates = _parse_guess_list(data.get("current_guesses"), sim)
    if not current_candidates and isinstance(data.get("guesses"), list):
        current_candidates = _parse_guess_list(data.get("guesses"), sim)

    result: list[int] = []
    for idx, conf in current_candidates:
        if len(result) >= number:
            break
        if conf >= SELF_CHECK_CONFIDENCE:
            result.append(idx)
        else:
            break
    return result


async def _self_check_clue(
    state: dict,
    team: str,
    clue: str,
    number: int,
    targets: list[str],
) -> tuple[list[str] | None, list[int]]:
    """Return accepted targets (full or partial) and raw guess indices."""
    guesses = await _simulate_operative_guesses(state, team, clue, number)
    accepted = _resolve_self_check_targets(state, team, targets, guesses)
    return accepted, guesses


def _spymaster_size_feedback(
    preferred_n: int,
    *,
    rejected_clues: list[str],
    failed_check: str | None = None,
) -> str:
    if preferred_n >= MIN_MULTI_TARGETS:
        lines = [
            f"Give a multi-word clue for exactly {preferred_n} targets "
            f"(number={preferred_n}, len(targets)={preferred_n}). "
            f"Do not use number=1."
        ]
    else:
        lines = [
            f"Your clue must target exactly {preferred_n} word(s) "
            f"(number={preferred_n}, len(targets)={preferred_n})."
        ]
    if rejected_clues:
        lines.append(f"Do not reuse these failed clues: {', '.join(rejected_clues)}.")
    if failed_check:
        lines.append(failed_check)
    return "\n".join(lines)


def _size_attempts(preferred_n: int) -> int:
    if preferred_n >= MIN_MULTI_TARGETS:
        return SELF_CHECK_ATTEMPTS_MULTI
    return SELF_CHECK_ATTEMPTS


async def fallback_clue(state: dict, team: str) -> tuple[str, int, list[str]]:
    targets = _unrevealed_team_words(state["cards"], team)
    if not targets:
        return _random_generic_clue(state), 1, []

    board_words = board_words_upper(state["cards"])
    avoid = _avoid_clue_words(state["cards"], team)
    other_board_words = [c["word"] for c in state["cards"] if c["word"] not in targets]
    min_keep = _min_acceptable_targets(state, team)

    for group in _fallback_target_groups(targets):
        if len(group) < min_keep:
            continue
        prompt = _build_focused_fallback_prompt(group, avoid, other_board_words)
        try:
            response = await deepseek_chat(
                prompt,
                system=SPYMASTER_SYSTEM,
                temperature=SPYMASTER_TEMPERATURE,
                json_mode=True,
            )
            data = _parse_json(response)
            validated = _validate_spymaster_response(data, targets, board_words, avoid)
            if not validated or not _accept_focused_fallback(validated, group):
                continue
            clue, number, chosen = validated
            accepted, _guesses = await _self_check_clue(
                state, team, clue, number, chosen
            )
            if accepted:
                return clue, len(accepted), accepted
            logger.info(
                "Fallback clue %s %s failed self-check for targets %s",
                clue,
                number,
                chosen,
            )
        except Exception as e:
            logger.warning("Focused fallback clue failed for %s: %s", group, e)

    # Midgame: keep trying single-target focused clues only as absolute last resort
    if min_keep > 1:
        for group in _fallback_target_groups(targets):
            if len(group) != 1:
                continue
            prompt = _build_focused_fallback_prompt(group, avoid, other_board_words)
            try:
                response = await deepseek_chat(
                    prompt,
                    system=SPYMASTER_SYSTEM,
                    temperature=SPYMASTER_TEMPERATURE,
                    json_mode=True,
                )
                data = _parse_json(response)
                validated = _validate_spymaster_response(data, targets, board_words, avoid)
                if not validated or not _accept_focused_fallback(validated, group):
                    continue
                clue, number, chosen = validated
                accepted, _guesses = await _self_check_clue(
                    state, team, clue, number, chosen
                )
                if accepted:
                    return clue, len(accepted), accepted
            except Exception as e:
                logger.warning("Single-target fallback clue failed for %s: %s", group, e)

    return _random_generic_clue(state), 1, [targets[0]] if targets else []


async def ai_spymaster_clue(state: dict, team: str) -> tuple[str, int, list[str]]:
    cards = state["cards"]
    targets = _unrevealed_team_words(cards, team)
    board_words = board_words_upper(cards)
    avoid = _avoid_clue_words(cards, team)

    if not targets:
        return _random_generic_clue(state), 1, []

    base_prompt = _build_spymaster_prompt(state, team)
    rejected_clues: list[str] = []
    max_n = min(3, len(targets))
    min_n = _min_acceptable_targets(state, team)

    for preferred_n in range(max_n, min_n - 1, -1):
        feedback = _spymaster_size_feedback(preferred_n, rejected_clues=rejected_clues)

        for attempt in range(_size_attempts(preferred_n)):
            try:
                full_prompt = f"{base_prompt}\n\n{feedback}"
                response = await deepseek_chat(
                    full_prompt,
                    system=SPYMASTER_SYSTEM,
                    temperature=SPYMASTER_TEMPERATURE,
                    json_mode=True,
                )
                data = _parse_json(response)
                validated = _validate_spymaster_response(data, targets, board_words, avoid)
                if not validated:
                    risky_hits = _risky_words_hit_avoid(data, avoid)
                    if risky_hits:
                        feedback = (
                            f"{json.dumps(data)}\n"
                            f"Invalid: clue would suggest dangerous words: {', '.join(risky_hits)}. "
                            "Choose a different clue or different targets.\n"
                            + _spymaster_size_feedback(
                                preferred_n, rejected_clues=rejected_clues
                            )
                        )
                    else:
                        feedback = (
                            f"{json.dumps(data)}\n"
                            "Invalid: clue must be one board-external word (no substring overlap), "
                            f"targets must be unrevealed {team} words only, "
                            "number must equal len(targets), and risky_words must not include "
                            "danger words.\n"
                            + _spymaster_size_feedback(
                                preferred_n, rejected_clues=rejected_clues
                            )
                        )
                    continue

                clue, number, chosen = validated
                # Accept smaller multi-word clues early (e.g. asked for 3, got a solid 2).
                if number > preferred_n or number < min_n:
                    feedback = (
                        f"{json.dumps(data)}\n"
                        f"Invalid for this step: need {preferred_n} target(s) "
                        f"(or at least {min_n}), got {number}.\n"
                        + _spymaster_size_feedback(
                            preferred_n, rejected_clues=rejected_clues
                        )
                    )
                    continue
                if number < preferred_n and number < MIN_MULTI_TARGETS and min_n > 1:
                    feedback = (
                        f"{json.dumps(data)}\n"
                        f"Invalid: midgame clues must cover at least {MIN_MULTI_TARGETS} "
                        f"targets; got {number}.\n"
                        + _spymaster_size_feedback(
                            preferred_n, rejected_clues=rejected_clues
                        )
                    )
                    continue

                accepted, guesses = await _self_check_clue(
                    state, team, clue, number, chosen
                )
                if accepted:
                    return clue, len(accepted), accepted

                if clue not in rejected_clues:
                    rejected_clues.append(clue)
                guessed = _guessed_words_for_feedback(state, guesses)
                failed = (
                    f"Clue '{clue}' failed operative self-check. "
                    f"Operative guessed: {', '.join(guessed) or '(none)'}. "
                    f"Intended targets: {', '.join(chosen)}. "
                    "Choose a DIFFERENT clue that more clearly points only at the targets."
                )
                feedback = _spymaster_size_feedback(
                    preferred_n,
                    rejected_clues=rejected_clues,
                    failed_check=failed,
                )
                logger.info(
                    "Spymaster clue %s %s failed self-check (attempt %s, n=%s)",
                    clue,
                    number,
                    attempt + 1,
                    preferred_n,
                )
            except Exception as e:
                logger.warning(
                    "AI spymaster self-check attempt %s (n=%s) failed: %s",
                    attempt + 1,
                    preferred_n,
                    e,
                )
                feedback = (
                    f"{e}\n"
                    + _spymaster_size_feedback(
                        preferred_n, rejected_clues=rejected_clues
                    )
                )

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
                "Invalid: provide current_guesses and optional bonus_guess as "
                '{"current_guesses": [{"index": N, "confidence": 0.0-1.0}], '
                '"bonus_guess": {"index": N, "confidence": 0.0-1.0} or null} '
                "using unrevealed card indices only. bonus_guess is only for prior clues."
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
