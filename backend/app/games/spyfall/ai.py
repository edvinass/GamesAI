import json
import logging
import random
import re
from typing import Any

from app.services.deepseek import deepseek_chat

logger = logging.getLogger(__name__)

AI_TEMPERATURE = 0.7
RESIDENT_ANSWER_TEMPERATURE = 0.9
SPY_GUESS_TEMPERATURE = 0.35
AI_ATTEMPTS = 3
SPY_GUESS_MIN_LOG = 2
RESIDENT_ANSWER_MAX_LEN = 90

SPY_ASK_SYSTEM = (
    "You are the SPY in Spyfall. You do NOT know the secret location or your role. "
    "Ask one short, vague question that could plausibly fit many different locations. "
    "Never reference specific equipment, rooms, or activities tied to one place unless "
    "someone already mentioned them in the conversation."
)

RESIDENT_ASK_SYSTEM = (
    "You are a resident in Spyfall. You know the secret location and your role there. "
    "Ask one casual question to probe whether someone else belongs — like a coworker making small talk. "
    "Do NOT name the location. Do NOT use jargon, equipment names, or niche job duties. "
    "Bad: 'How many beds are in the ICU?' Good: 'Busy day so far?'"
)

SPY_ANSWER_SYSTEM = (
    "You are the SPY in Spyfall. You do NOT know the secret location. "
    "Give a vague, safe answer that could fit many places. "
    "If you can infer details only from the conversation below, you may use them cautiously. "
    "Never sound like you have insider knowledge. Never name a location."
)

RESIDENT_ANSWER_SYSTEM = (
    "You are a resident in Spyfall. You know the location and role internally, "
    "but the spy is listening — your spoken answer must NOT help them deduce the location.\n\n"
    "Rules for your answer:\n"
    "- ONE short sentence, max ~12 words. Be extremely vague.\n"
    "- Answer the question minimally — yes/no vibe, 'depends', 'the usual', 'not really'.\n"
    "- NO job titles, duties, equipment, places, customers, or anything location-specific.\n"
    "- NO proper nouns or niche vocabulary. Sound bored and generic.\n"
    "- The answer should plausibly fit dozens of different locations on a Spyfall list.\n\n"
    "BAD: 'I handle the front desk when the morning rush comes in.'\n"
    "GOOD: 'Yeah, pretty typical.'\n"
    "BAD: 'We prep the operating room before the first patient.'\n"
    "GOOD: 'Same as most mornings, I guess.'\n"
    "BAD: 'The slots are loud on weekends.'\n"
    "GOOD: 'It gets busy sometimes.'"
)

VOTE_SYSTEM = (
    "You are a resident in Spyfall. Based on the public question log, "
    "vote for whoever seems LEAST like they belong — vague answers, deflection, "
    "generic replies, or questions that could fit anywhere are suspicious. "
    "Return the player id of your top suspect."
)

GUESS_SYSTEM = (
    "You are an expert Spyfall spy. Study the conversation carefully and deduce the secret location. "
    "Residents who know the location may slip subtle hints despite trying to be vague — "
    "look for patterns in what they confirm or deny. "
    "Pick the single best location from the list whenever you have a reasonable theory. "
    "Only return null if the conversation gives almost no signal yet."
)

FALLBACK_QUESTIONS = [
    "How long have you been here today?",
    "Is it busy right now?",
    "Do you come here often?",
    "How's your day going so far?",
]

SPY_FALLBACK_QUESTIONS = [
    "How long have you been here today?",
    "Is it always this busy?",
    "Do you work here every day?",
    "What's your usual routine like?",
]

FALLBACK_ANSWERS = [
    "It depends on the day, really.",
    "Pretty routine stuff, nothing unusual.",
    "Just the usual — same as most days.",
    "Could be busier, could be quieter.",
]

SPY_FALLBACK_ANSWERS = [
    "Yeah, pretty much the usual routine.",
    "It varies — hard to say really.",
    "Same as most days around here.",
    "Nothing too exciting, honestly.",
]

RESIDENT_FALLBACK_ANSWERS = [
    "Yeah, pretty much.",
    "More or less.",
    "I'd say so.",
    "Not really, no.",
    "Could be, I guess.",
    "Same as always.",
    "Hard to say.",
    "Depends on the day.",
]


def _player_map(state: dict) -> dict[str, dict]:
    return {p["id"]: p for p in state["players"]}


def actor_is_spy(state: dict, player_id: str) -> bool:
    return str(state["spy_id"]) == str(player_id)


def _format_log(state: dict) -> str:
    lines = []
    for entry in state.get("question_log", []):
        lines.append(
            f"{entry['from_nickname']} asked {entry['to_nickname']}: \"{entry['question']}\"\n"
            f"{entry['to_nickname']} answered: \"{entry['answer']}\""
        )
    return "\n".join(lines) if lines else "(no questions yet)"


def build_role_brief(state: dict, actor_id: str) -> str:
    """Build role context for prompts. Never leaks location to the spy."""
    if actor_is_spy(state, actor_id):
        return (
            "YOUR SECRET ROLE: You are the SPY.\n"
            "You do NOT know the location. You do NOT have a role card.\n"
            "Listen to others and bluff. Stay vague unless the conversation gives you a clue.\n"
        )
    location = state["location"]["name"]
    role = state.get("assignments", {}).get(str(actor_id), "?")
    return (
        "YOUR SECRET ROLE: You are a resident (not the spy).\n"
        f"Location (SECRET — do not reveal): {location}\n"
        f"Your role (SECRET — do not reveal): {role}\n"
        "Use this knowledge only to stay consistent. Your spoken answer must be extremely vague "
        "and must not help the spy narrow down the location.\n"
    )


def _leak_terms_for_state(state: dict, actor_id: str) -> set[str]:
    terms: set[str] = set()
    location = state.get("location", {})
    name = location.get("name", "")
    for text in (name, state.get("assignments", {}).get(str(actor_id), "") or ""):
        for word in re.findall(r"[a-zA-Z]+", text):
            if len(word) > 2:
                terms.add(word.lower())
    for role in location.get("roles", []):
        for word in re.findall(r"[a-zA-Z]+", role):
            if len(word) > 2:
                terms.add(word.lower())
    return terms


def is_answer_too_revealing(answer: str, state: dict, actor_id: str) -> str | None:
    """Return a rejection reason if a resident answer gives away too much."""
    if actor_is_spy(state, actor_id):
        return None

    text = answer.strip()
    if not text:
        return "Answer is empty"
    if len(text) > RESIDENT_ANSWER_MAX_LEN:
        return "Answer is too long — keep it to one short vague sentence"
    if len(text.split()) > 14:
        return "Answer has too many words — be briefer and vaguer"

    lower = text.lower()
    leak_terms = _leak_terms_for_state(state, actor_id)
    for term in leak_terms:
        if re.search(rf"\b{re.escape(term)}\b", lower):
            return f"Answer mentions revealing term '{term}'"

    banned_patterns = (
        r"\b(mri|icu|surgeon|casino|embassy|submarine|pirate|orbit|reactor|autopsy|radiolog|"
        r"slot|dealer|patient|nurse|doctor|captain|pilot|prison|guard|sheriff|bank|teller|"
        r"stage|theater|museum|curator|beach|lifeguard|hospital|clinic|surgery|operating)\b",
        r"\b(as a|my job|i work|my role|we have|there are|there is|i handle|i manage|i operate|"
        r"customers|clients|patients|guests|visitors|inventory|shift|register|counter)\b",
        r"\b(usually|typically|every day|each morning|before we open|after closing)\b",
    )
    for pattern in banned_patterns:
        if re.search(pattern, lower):
            return "Answer is too specific or sounds like a job description"

    return None


def _parse_json(raw: str) -> dict | None:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None
    return None


def _other_players(state: dict, actor_id: str) -> list[dict]:
    return [p for p in state["players"] if str(p["id"]) != str(actor_id)]


async def ai_ask_question(state: dict, actor: dict) -> tuple[str, str]:
    actor_id = str(actor["id"])
    others = _other_players(state, actor_id)
    if not others:
        raise ValueError("No targets available")

    is_spy = actor_is_spy(state, actor_id)
    system = SPY_ASK_SYSTEM if is_spy else RESIDENT_ASK_SYSTEM
    role_brief = build_role_brief(state, actor_id)
    targets_desc = "\n".join(f"- {p['id']}: {p['nickname']}" for p in others)
    prompt = (
        f"{role_brief}\n"
        f"Players you can ask:\n{targets_desc}\n\n"
        f"Public conversation so far:\n{_format_log(state)}\n\n"
        "Pick one target and ask a single question (max 120 chars).\n"
        'Return JSON: {"target_player_id": "...", "question": "..."}'
    )

    fallbacks = SPY_FALLBACK_QUESTIONS if is_spy else FALLBACK_QUESTIONS

    for attempt in range(AI_ATTEMPTS):
        try:
            temp = AI_TEMPERATURE if is_spy else 0.75
            raw = await deepseek_chat(prompt, system, temperature=temp, json_mode=True)
            data = _parse_json(raw)
            if not data:
                continue
            target_id = str(data.get("target_player_id", ""))
            question = str(data.get("question", "")).strip()
            valid_ids = {str(p["id"]) for p in others}
            if target_id in valid_ids and question:
                return target_id, question[:120]
        except Exception as e:
            logger.warning("AI ask attempt %d failed: %s", attempt + 1, e)

    target = random.choice(others)
    return str(target["id"]), random.choice(fallbacks)


async def ai_answer_question(state: dict, actor: dict) -> str:
    actor_id = str(actor["id"])
    pending = state.get("pending_question")
    if not pending:
        if actor_is_spy(state, actor_id):
            return random.choice(SPY_FALLBACK_ANSWERS)
        return random.choice(RESIDENT_FALLBACK_ANSWERS)

    is_spy = actor_is_spy(state, actor_id)
    system = SPY_ANSWER_SYSTEM if is_spy else RESIDENT_ANSWER_SYSTEM
    role_brief = build_role_brief(state, actor_id)
    asker = _player_map(state).get(pending["from_id"], {})
    rejection_note = ""

    prompt_base = (
        f"{role_brief}\n"
        f"{asker.get('nickname', 'Someone')} asked you: \"{pending['question']}\"\n\n"
        f"Public conversation so far:\n{_format_log(state)}\n\n"
    )

    fallbacks = SPY_FALLBACK_ANSWERS if is_spy else RESIDENT_FALLBACK_ANSWERS
    temperature = AI_TEMPERATURE if is_spy else RESIDENT_ANSWER_TEMPERATURE

    for attempt in range(AI_ATTEMPTS):
        try:
            max_len = RESIDENT_ANSWER_MAX_LEN if not is_spy else 140
            prompt = (
                f"{prompt_base}"
                f"{rejection_note}"
                f"Give a short in-character answer (max {max_len} chars).\n"
                'Return JSON: {"answer": "..."}'
            )
            raw = await deepseek_chat(prompt, system, temperature=temperature, json_mode=True)
            data = _parse_json(raw)
            if not data or not data.get("answer"):
                continue
            answer = str(data["answer"]).strip()[:max_len]
            if not is_spy:
                if reason := is_answer_too_revealing(answer, state, actor_id):
                    rejection_note = (
                        f"REJECTED: {reason}. "
                        "Try again with a MUCH vaguer answer — a few words only, "
                        "nothing about your job or this place. Examples: 'Yeah, mostly.' 'Not really.'\n\n"
                    )
                    continue
            return answer
        except Exception as e:
            logger.warning("AI answer attempt %d failed: %s", attempt + 1, e)

    return random.choice(fallbacks)


async def ai_cast_vote(state: dict, actor: dict) -> str | None:
    actor_id = str(actor["id"])
    others = _other_players(state, actor_id)

    if actor_is_spy(state, actor_id):
        innocent = random.choice(others)
        return str(innocent["id"])

    role_brief = build_role_brief(state, actor_id)
    players_desc = "\n".join(f"- {p['id']}: {p['nickname']}" for p in state["players"])
    prompt = (
        f"{role_brief}\n"
        f"Players:\n{players_desc}\n\n"
        f"Public conversation:\n{_format_log(state)}\n\n"
        "Who seems least like they belong? Pick the player with the vaguest or most generic answers.\n"
        'Return JSON: {"vote_for_player_id": "..."}'
    )

    for attempt in range(AI_ATTEMPTS):
        try:
            raw = await deepseek_chat(prompt, VOTE_SYSTEM, temperature=0.35, json_mode=True)
            data = _parse_json(raw)
            if data:
                vote_for = data.get("vote_for_player_id")
                if vote_for and str(vote_for) in _player_map(state):
                    if str(vote_for) != actor_id:
                        return str(vote_for)
        except Exception as e:
            logger.warning("AI vote attempt %d failed: %s", attempt + 1, e)

    suspects = [p for p in others if str(p["id"]) != actor_id]
    return str(random.choice(suspects)["id"]) if suspects else str(random.choice(others)["id"])


async def ai_spy_guess(state: dict, actor: dict) -> str | None:
    if not actor_is_spy(state, str(actor["id"])):
        return None

    if len(state.get("question_log", [])) < SPY_GUESS_MIN_LOG:
        return None

    locations = state.get("all_location_names", [])
    prompt = (
        "You are an expert spy. Deduce the secret location from the conversation.\n\n"
        f"Public conversation:\n{_format_log(state)}\n\n"
        f"Possible locations ({len(locations)} total):\n{', '.join(locations)}\n\n"
        "Return your best guess if you have any reasonable theory. Wrong guesses lose, "
        "but waiting too long lets residents vote you out.\n"
        'Return JSON: {"location_name": "..." or null, "confidence": 1-10}'
    )

    best_guess: str | None = None
    best_confidence = 0

    for attempt in range(AI_ATTEMPTS):
        try:
            raw = await deepseek_chat(
                prompt, GUESS_SYSTEM, temperature=SPY_GUESS_TEMPERATURE, json_mode=True
            )
            data = _parse_json(raw)
            if not data:
                continue
            confidence = int(data.get("confidence", 0))
            guess = data.get("location_name")
            if guess is None:
                continue
            guess_str = str(guess).strip()
            if not any(guess_str.lower() == loc.lower() for loc in locations):
                continue
            if confidence > best_confidence:
                best_confidence = confidence
                best_guess = guess_str
        except Exception as e:
            logger.warning("AI spy guess attempt %d failed: %s", attempt + 1, e)

    if best_guess and best_confidence >= 4:
        return best_guess
    return None
