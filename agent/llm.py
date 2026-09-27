import ollama

from config.llm import OLLAMA_MODEL


def ask_local_llm(prompt: str, format_schema=None) -> str:
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {
                "role": "user",
                "content": f"/no_think\n{prompt}",
            }
        ],
        format=format_schema,
    )

    return response.message.content