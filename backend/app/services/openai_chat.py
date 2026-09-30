import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Reasoning tokens count against this budget. Codenames only needs a short JSON answer,
# but a tight cap can leave content empty after the model thinks.
JSON_MAX_COMPLETION_TOKENS = 8192


def build_openai_payload(
    model: str,
    prompt: str,
    system: str,
    *,
    json_mode: bool,
    reasoning_effort: str,
) -> dict:
    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        # GPT-6 rejects temperature unless reasoning effort is "none", which Astra and Sol do not support.
        "reasoning_effort": reasoning_effort,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
        payload["max_completion_tokens"] = JSON_MAX_COMPLETION_TOKENS
    return payload


async def openai_chat(
    prompt: str,
    system: str = "You are a helpful game AI. Respond concisely.",
    *,
    temperature: float = 0.7,
    json_mode: bool = False,
    model: str,
) -> str:
    del temperature  # Unsupported while reasoning is enabled.
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    url = f"{settings.openai_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = build_openai_payload(
        model,
        prompt,
        system,
        json_mode=json_mode,
        reasoning_effort=settings.openai_reasoning_effort,
    )

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    choice = data["choices"][0]
    content = (choice["message"].get("content") or "").strip()
    finish_reason = choice.get("finish_reason", "unknown")
    if not content:
        logger.warning(
            "OpenAI returned empty content (model=%s, finish_reason=%s, json_mode=%s)",
            model,
            finish_reason,
            json_mode,
        )
        raise RuntimeError(f"OpenAI returned empty content (finish_reason={finish_reason})")
    if finish_reason == "length":
        logger.warning(
            "OpenAI response truncated (model=%s, json_mode=%s, content_len=%s)",
            model,
            json_mode,
            len(content),
        )
        raise RuntimeError("OpenAI response truncated (finish_reason=length)")
    return content
