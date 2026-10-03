import pytest

from app.games.codenames.ai_models import DEFAULT_AI_MODEL
from app.services.llm import llm_chat
from app.services.openai_chat import build_openai_payload, extract_response_text


def test_openai_payload_uses_responses_api_without_temperature() -> None:
    payload = build_openai_payload(
        "gpt-6-astra",
        "Give a clue.",
        "You are a spymaster.",
        json_mode=True,
        reasoning_effort="high",
        json_schema={"type": "object"},
        schema_name="spymaster_clue",
    )

    assert payload["model"] == "gpt-6-astra"
    assert payload["reasoning"] == {"effort": "high"}
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["name"] == "spymaster_clue"
    assert "temperature" not in payload
    assert "messages" not in payload
    assert payload["max_output_tokens"] >= 1024


def test_extract_response_text_skips_reasoning_items() -> None:
    data = {
        "output": [
            {"type": "reasoning", "summary": [{"type": "summary_text", "text": "thinking"}]},
            {
                "type": "message",
                "content": [{"type": "output_text", "text": '{"current_guesses": []}'}],
            },
        ]
    }

    assert extract_response_text(data) == '{"current_guesses": []}'


@pytest.mark.asyncio
async def test_llm_chat_routes_openai_models(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def fake_openai(prompt: str, system: str, **kwargs: object) -> str:
        calls.append(str(kwargs["model"]))
        assert prompt == "clue"
        assert system == "system"
        return "{}"

    async def fake_deepseek(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("DeepSeek should not be called")

    monkeypatch.setattr("app.services.llm.openai_chat", fake_openai)
    monkeypatch.setattr("app.services.llm.deepseek_chat", fake_deepseek)

    result = await llm_chat("clue", "system", json_mode=True, model="gpt-6.1-sol")

    assert result == "{}"
    assert calls == ["gpt-6.1-sol"]


@pytest.mark.asyncio
async def test_llm_chat_routes_default_to_deepseek(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_openai(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("OpenAI should not be called")

    async def fake_deepseek(prompt: str, *_args: object, **_kwargs: object) -> str:
        assert prompt == "guess"
        return "{}"

    monkeypatch.setattr("app.services.llm.openai_chat", fake_openai)
    monkeypatch.setattr("app.services.llm.deepseek_chat", fake_deepseek)

    result = await llm_chat("guess", model=DEFAULT_AI_MODEL)

    assert result == "{}"
