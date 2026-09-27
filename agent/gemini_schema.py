GEMINI_UNSUPPORTED_SCHEMA_KEYS = frozenset(
    {
        "const", "default", "examples", "exclusiveMaximum",
        "exclusiveMinimum", "maxLength", "minLength", "multipleOf",
        "pattern", "uniqueItems",
    }
)


def _sanitize_schema_value(value):
    if isinstance(value, dict):
        return {
            key: _sanitize_schema_value(child)
            for key, child in value.items()
            if key not in GEMINI_UNSUPPORTED_SCHEMA_KEYS
        }
    if isinstance(value, list):
        return [_sanitize_schema_value(item) for item in value]
    return value


def sanitize_schema_for_gemini(schema: dict) -> dict:
    """Reduce provider schema keywords without weakening application models."""
    return _sanitize_schema_value(schema)
