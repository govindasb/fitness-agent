import os


DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"


class OpenAIConfigurationError(RuntimeError):
    pass


def get_openai_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise OpenAIConfigurationError(
            "OPENAI_API_KEY is required for OpenAI interpretation."
        )
    return api_key


def get_openai_model() -> str:
    return os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
