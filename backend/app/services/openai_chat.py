import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Reasoning tokens count against this budget. A short cap leaves the visible JSON empty.
MAX_OUTPUT_TOKENS = 16384


def build_openai_payload(
    model: str,
    prompt: str,
    system: str,
    *,
    json_mode: bool,
    reasoning_effort: str,
    json_schema: dict | None = None,
    schema_name: str = "response",
) -> dict:
    payload: dict = {
        "model": model,
        "input": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        # GPT-6 rejects temperature unless reasoning effort is "none", which Astra and Sol do not support.
        "reasoning": {"effort": reasoning_effort},
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    }
    if json_schema:
        payload["text"] = {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": json_schema,
            }
        }
    elif json_mode:
        payload["text"] = {"format": {"type": "json_object"}}
    return payload


def extract_response_text(data: dict) -> str:
    """Visible answer from a Responses API payload, ignoring reasoning items."""
    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    parts: list[str] = []
    for item in data.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for block in item.get("content") or []:
            if isinstance(block, str):
                parts.append(block)
                continue
            if isinstance(block, dict):
                text = block.get("text") or ""
                if text:
                    parts.append(str(text))
    return "".join(parts).strip()


async def openai_chat(
    prompt: str,
    system: str = "You are a helpful game AI. Respond concisely.",
    *,
    temperature: float = 0.7,
    json_mode: bool = False,
    model: str,
    json_schema: dict | None = None,
    schema_name: str = "response",
) -> str:
    del temperature  # Unsupported while reasoning is enabled.
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    url = f"{settings.openai_base_url.rstrip('/')}/responses"
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
        json_schema=json_schema,
        schema_name=schema_name,
    )

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        if response.is_error:
            body = response.text[:500]
            logger.warning("OpenAI HTTP %s: %s", response.status_code, body)
            raise RuntimeError(f"OpenAI request failed ({response.status_code})")
        data = response.json()

    content = extract_response_text(data)
    status = data.get("status", "unknown")
    if not content:
        logger.warning(
            "OpenAI returned empty output (model=%s, status=%s, json_mode=%s)",
            model,
            status,
            json_mode,
        )
        raise RuntimeError(f"OpenAI returned empty output (status={status})")
    if status == "incomplete":
        logger.warning(
            "OpenAI response incomplete (model=%s, content_len=%s)",
            model,
            len(content),
        )
    return content
