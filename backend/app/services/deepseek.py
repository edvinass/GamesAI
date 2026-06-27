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
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
        payload["max_tokens"] = 2048

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    return data["choices"][0]["message"]["content"]
