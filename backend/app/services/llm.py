from app.config import settings
from app.games.codenames.ai_models import is_openai_model
from app.services.deepseek import deepseek_chat
from app.services.openai_chat import openai_chat


async def llm_chat(
    prompt: str,
    system: str = "You are a helpful game AI. Respond concisely.",
    *,
    temperature: float = 0.7,
    json_mode: bool = False,
    model: str | None = None,
    json_schema: dict | None = None,
    schema_name: str = "response",
) -> str:
    chosen = (model or "").strip() or settings.deepseek_model
    if is_openai_model(chosen):
        return await openai_chat(
            prompt,
            system,
            temperature=temperature,
            json_mode=json_mode,
            model=chosen,
            json_schema=json_schema,
            schema_name=schema_name,
        )
    return await deepseek_chat(
        prompt,
        system,
        temperature=temperature,
        json_mode=json_mode,
    )
