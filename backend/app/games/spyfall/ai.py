import json
import logging
import random
import re
from typing import Any

from app.services.deepseek import deepseek_chat

logger = logging.getLogger(__name__)

AI_TEMPERATURE = 0.7
AI_ATTEMPTS = 3

SPY_ASK_SYSTEM = (
    "You are the SPY in Spyfall. You do NOT know the secret location or your role. "
    "Ask one short, vague question that could plausibly fit many different locations. "
    "Never reference specific equipment, rooms, or activities tied to one place unless "
    "someone already mentioned them in the conversation."
)

RESIDENT_ASK_SYSTEM = (
    "You are a resident in Spyfall. You know the secret location and your role there. "
    "Ask one short question to probe whether someone else really belongs. "
    "Do not name the location. Do not ask something only your exact role would know."
)

SPY_ANSWER_SYSTEM = (
    "You are the SPY in Spyfall. You do NOT know the secret location. "
    "Give a vague, safe answer that could fit many places. "
    "If you can infer details only from the conversation below, you may use them cautiously. "
    "Never sound like you have insider knowledge. Never name a location."
)

RESIDENT_ANSWER_SYSTEM = (
    "You are a resident in Spyfall. You know the location and your role. "
    "Answer in one or two short, natural sentences in character. "
    "Never say the location name. Sound like a normal person, not an encyclopedia."
)

VOTE_SYSTEM = (
    "You are playing Spyfall. Based only on the public question log, "
    "vote for who seems like the spy — vague answers, hesitation, or odd questions are suspicious. "
    "Return the player id of your top suspect."
)

GUESS_SYSTEM = (
    "You are the spy in Spyfall. Based only on the conversation, guess the secret location. "
    "Return null unless the dialogue strongly points to one location."
)

FALLBACK_QUESTIONS = [
    "How long have you been here today?",
    "What's the busiest time around here?",
    "Do you come here often?",
    "What do you usually do on a typical day?",
]

SPY_FALLBACK_QUESTIONS = [
    "How long have you been here today?",
    "Is it always this busy?",
    "Do you work here every day?",
    "What's your usual routine like?",
]

FALLBACK_ANSWERS = [
    "I'm not sure, can you be more specific?",
    "It depends on the day, really.",
    "Pretty routine stuff, nothing unusual.",
    "Just the usual — same as most days.",
]

SPY_FALLBACK_ANSWERS = [
    "Yeah, pretty much the usual routine.",
    "It varies — hard to say really.",
    "Same as most days around here.",
    "Nothing too exciting, honestly.",
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
        f"Location: {location}\n"
        f"Your role there: {role}\n"
        "Only use knowledge that someone in this role at this location would have.\n"
    )


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
            raw = await deepseek_chat(prompt, system, temperature=AI_TEMPERATURE, json_mode=True)
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
        return random.choice(SPY_FALLBACK_ANSWERS if actor_is_spy(state, actor_id) else FALLBACK_ANSWERS)

    is_spy = actor_is_spy(state, actor_id)
    system = SPY_ANSWER_SYSTEM if is_spy else RESIDENT_ANSWER_SYSTEM
    role_brief = build_role_brief(state, actor_id)
    asker = _player_map(state).get(pending["from_id"], {})

    prompt = (
        f"{role_brief}\n"
        f"{asker.get('nickname', 'Someone')} asked you: \"{pending['question']}\"\n\n"
        f"Public conversation so far:\n{_format_log(state)}\n\n"
        "Give a short in-character answer (max 200 chars).\n"
        'Return JSON: {"answer": "..."}'
    )

    fallbacks = SPY_FALLBACK_ANSWERS if is_spy else FALLBACK_ANSWERS

    for attempt in range(AI_ATTEMPTS):
        try:
            raw = await deepseek_chat(prompt, system, temperature=AI_TEMPERATURE, json_mode=True)
            data = _parse_json(raw)
            if data and data.get("answer"):
                return str(data["answer"]).strip()[:200]
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
        "Who is most likely the spy? Return their player id.\n"
        'Return JSON: {"vote_for_player_id": "..."}'
    )

    for attempt in range(AI_ATTEMPTS):
        try:
            raw = await deepseek_chat(prompt, VOTE_SYSTEM, temperature=0.4, json_mode=True)
            data = _parse_json(raw)
            if data:
                vote_for = data.get("vote_for_player_id")
                if vote_for and str(vote_for) in _player_map(state):
                    return str(vote_for)
        except Exception as e:
            logger.warning("AI vote attempt %d failed: %s", attempt + 1, e)

    return str(random.choice(others)["id"])


async def ai_spy_guess(state: dict, actor: dict) -> str | None:
    if not actor_is_spy(state, str(actor["id"])):
        return None

    log_len = len(state.get("question_log", []))
    if log_len < 4:
        return None

    locations = state.get("all_location_names", [])
    prompt = (
        "You are the spy. You do NOT know the location yet.\n\n"
        f"Public conversation:\n{_format_log(state)}\n\n"
        f"Possible locations ({len(locations)} total):\n{', '.join(locations)}\n\n"
        "Only guess if the dialogue strongly suggests one location. Otherwise return null.\n"
        'Return JSON: {"location_name": "..."} or {"location_name": null}'
    )

    for attempt in range(AI_ATTEMPTS):
        try:
            raw = await deepseek_chat(prompt, GUESS_SYSTEM, temperature=0.3, json_mode=True)
            data = _parse_json(raw)
            if not data:
                continue
            guess = data.get("location_name")
            if guess is None:
                return None
            guess_str = str(guess).strip()
            if any(guess_str.lower() == loc.lower() for loc in locations):
                return guess_str
        except Exception as e:
            logger.warning("AI spy guess attempt %d failed: %s", attempt + 1, e)

    return None
