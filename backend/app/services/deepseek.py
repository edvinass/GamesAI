import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def deepseek_chat(
    prompt: str,
    system: str = "You are a helpful game AI. Respond concisely.",
    *,
    temperature: float = 0.7,
    json_mode: bool = False,
) -> str:
    if not settings.deepseek_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")

    url = f"{settings.deepseek_base_url.rstrip('/')}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    payload: dict = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }
    # JSON mode needs the final answer in `content`. deepseek-v4-pro defaults to thinking
    # on, and reasoning tokens can consume the entire budget leaving content empty.
    use_thinking = settings.deepseek_thinking and not json_mode
    if use_thinking:
        payload["reasoning_effort"] = settings.deepseek_reasoning_effort
        payload["thinking"] = {"type": "enabled"}
    else:
        payload["temperature"] = temperature
        if json_mode:
            payload["thinking"] = {"type": "disabled"}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
        payload["max_tokens"] = 1024

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    choice = data["choices"][0]
    content = (choice["message"].get("content") or "").strip()
    finish_reason = choice.get("finish_reason", "unknown")
    if not content:
        logger.warning(
            "DeepSeek returned empty content (finish_reason=%s, json_mode=%s, thinking=%s)",
            finish_reason,
            json_mode,
            use_thinking,
        )
        raise RuntimeError(f"DeepSeek returned empty content (finish_reason={finish_reason})")
    if finish_reason == "length":
        logger.warning(
            "DeepSeek response truncated (json_mode=%s, content_len=%s)",
            json_mode,
            len(content),
        )
        raise RuntimeError("DeepSeek response truncated (finish_reason=length)")
    return content
