import os


DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"


class GeminiConfigurationError(RuntimeError):
    pass


def get_gemini_api_key() -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise GeminiConfigurationError(
            "GEMINI_API_KEY is required for Gemini interpretation."
        )
    return api_key


def get_gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
