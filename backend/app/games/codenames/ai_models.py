"""Codenames AI model choices exposed in the lobby."""

DEEPSEEK_MODEL = "deepseek-v4-pro"
OPENAI_MODELS = ("gpt-6-astra", "gpt-6.1-sol")
AI_MODELS = (DEEPSEEK_MODEL, *OPENAI_MODELS)
DEFAULT_AI_MODEL = DEEPSEEK_MODEL
REASONING_EFFORTS = ("low", "medium", "high", "xhigh", "max")
DEFAULT_REASONING_EFFORT = "low"

AI_MODEL_LABELS = {
    DEEPSEEK_MODEL: "DeepSeek V4 Pro",
    "gpt-6-astra": "GPT-6 Astra",
    "gpt-6.1-sol": "GPT-6.1 Sol",
}


def is_openai_model(model: str) -> bool:
    return model in OPENAI_MODELS
