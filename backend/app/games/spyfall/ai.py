import json
import logging
import random
import re
from typing import Any

from app.services.deepseek import deepseek_chat

logger = logging.getLogger(__name__)

AI_TEMPERATURE = 0.7
AI_ATTEMPTS = 3

ASK_SYSTEM = (
    "You are playing Spyfall, a social deduction game. Players share a secret location except one spy. "
    "Ask one short, natural question to probe whether someone knows the location. "
    "If you are the spy, ask vague questions that could fit many locations without revealing ignorance."
)

ANSWER_SYSTEM = (
    "You are playing Spyfall. Answer in one or two short sentences, in character. "
    "If you know the location and role, answer consistently without naming the location directly. "
    "If you are the spy, bluff convincingly as if you belong."
)

VOTE_SYSTEM = (
    "You are playing Spyfall. Based on the question log, vote for who you think is the spy. "
    "Return the player id of your top suspect."
)

GUESS_SYSTEM = (
    "You are the spy in Spyfall. Based on questions and answers, guess the secret location. "
    "Return null if you are not confident enough to guess yet."
)

FALLBACK_QUESTIONS = [
    "How long have you been here today?",
    "What's the busiest time around here?",
    "Do you enjoy working here?",
    "What do you usually do on a typical day?",
]

FALLBACK_ANSWERS = [
    "I'm not sure, can you be more specific?",
    "It depends on the day, really.",
    "Pretty routine stuff, nothing unusual.",
    "Just the usual — same as most days.",
]


def _player_map(state: dict) -> dict[str, dict]:
    return {p["id"]: p for p in state["players"]}


def _is_spy(state: dict, player_id: str) -> bool:
    return state["spy_id"] == player_id


def _format_log(state: dict) -> str:
    lines = []
    for entry in state.get("question_log", []):
        lines.append(
            f"{entry['from_nickname']} asked {entry['to_nickname']}: \"{entry['question']}\"\n"
            f"{entry['to_nickname']} answered: \"{entry['answer']}\""
        )
    return "\n".join(lines) if lines else "(no questions yet)"


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
    return [p for p in state["players"] if p["id"] != actor_id]


async def ai_ask_question(state: dict, actor: dict) -> tuple[str, str]:
    actor_id = actor["id"]
    others = _other_players(state, actor_id)
    if not others:
        raise ValueError("No targets available")

    is_spy = _is_spy(state, actor_id)
    role_info = ""
    if not is_spy:
        role = state.get("assignments", {}).get(actor_id, "?")
        location = state["location"]["name"]
        role_info = f"You are at: {location}. Your role: {role}.\n"

    targets_desc = "\n".join(f"- {p['id']}: {p['nickname']}" for p in others)
    prompt = (
        f"{role_info}"
        f"Players you can ask:\n{targets_desc}\n\n"
        f"Question log so far:\n{_format_log(state)}\n\n"
        "Pick one target and ask a single question (max 120 chars).\n"
        'Return JSON: {"target_player_id": "...", "question": "..."}'
    )

    for attempt in range(AI_ATTEMPTS):
        try:
            raw = await deepseek_chat(prompt, ASK_SYSTEM, temperature=AI_TEMPERATURE, json_mode=True)
            data = _parse_json(raw)
            if not data:
                continue
            target_id = str(data.get("target_player_id", ""))
            question = str(data.get("question", "")).strip()
            valid_ids = {p["id"] for p in others}
            if target_id in valid_ids and question:
                return target_id, question[:120]
        except Exception as e:
            logger.warning("AI ask attempt %d failed: %s", attempt + 1, e)

    target = random.choice(others)
    return target["id"], random.choice(FALLBACK_QUESTIONS)


async def ai_answer_question(state: dict, actor: dict) -> str:
    actor_id = actor["id"]
    pending = state.get("pending_question")
    if not pending:
        return random.choice(FALLBACK_ANSWERS)

    is_spy = _is_spy(state, actor_id)
    asker = _player_map(state).get(pending["from_id"], {})
    role_info = ""
    if not is_spy:
        role = state.get("assignments", {}).get(actor_id, "?")
        location = state["location"]["name"]
        role_info = f"You are at: {location}. Your role: {role}.\n"
    else:
        role_info = "You are the SPY. You do not know the location. Bluff convincingly.\n"
        role_info += f"Possible locations: {', '.join(state.get('all_location_names', [])[:10])}...\n"

    prompt = (
        f"{role_info}"
        f"{asker.get('nickname', 'Someone')} asked you: \"{pending['question']}\"\n\n"
        f"Prior conversation:\n{_format_log(state)}\n\n"
        "Give a short in-character answer (max 200 chars).\n"
        'Return JSON: {"answer": "..."}'
    )

    for attempt in range(AI_ATTEMPTS):
        try:
            raw = await deepseek_chat(prompt, ANSWER_SYSTEM, temperature=AI_TEMPERATURE, json_mode=True)
            data = _parse_json(raw)
            if data and data.get("answer"):
                return str(data["answer"]).strip()[:200]
        except Exception as e:
            logger.warning("AI answer attempt %d failed: %s", attempt + 1, e)

    return random.choice(FALLBACK_ANSWERS)


async def ai_cast_vote(state: dict, actor: dict) -> str | None:
    actor_id = actor["id"]
    others = _other_players(state, actor_id)
    is_spy = _is_spy(state, actor_id)

    if is_spy:
        innocent = random.choice(others)
        return innocent["id"]

    players_desc = "\n".join(f"- {p['id']}: {p['nickname']}" for p in state["players"])
    prompt = (
        f"Players:\n{players_desc}\n\n"
        f"Question log:\n{_format_log(state)}\n\n"
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

    return random.choice(others)["id"]


async def ai_spy_guess(state: dict, actor: dict) -> str | None:
    if not _is_spy(state, actor["id"]):
        return None

    if len(state.get("question_log", [])) < 2:
        return None

    locations = state.get("all_location_names", [])
    prompt = (
        f"Question log:\n{_format_log(state)}\n\n"
        f"Possible locations ({len(locations)} total):\n{', '.join(locations)}\n\n"
        "If confident, guess the location. Otherwise return null.\n"
        'Return JSON: {"location_name": "..." or null}'
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
