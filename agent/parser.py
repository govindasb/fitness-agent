from agent.llm import ask_local_llm
from models.parsed_input import ParsedInput


def parse_user_input(text: str) -> ParsedInput:
    prompt = f"""
You are a fitness data parser.

/no_think

Convert the user input into JSON matching this structure:

{{
  "body_metrics": [],
  "food_entries": [
    {{
      "meal_type": null,
      "consumed_at": null,
      "items": [
        {{
          "food_name": "",
          "quantity": null,
          "unit": null,
          "estimated_calories": null,
          "protein_g": null,
          "carbs_g": null,
          "fat_g": null,
          "fiber_g": null,
          "is_estimated": true
        }}
      ]
    }}
  ],
  "workouts": [],
  "activities": [],
  "sleep_entries": []
}}

Rules:
- A single user message may contain MULTIPLE event types.
- Extract EVERY event explicitly present in the text.
- Never choose only one category when multiple categories are present.

- Body measurements go in body_metrics.
- Food goes in food_entries.
- Workouts go in workouts.
- Steps, walking, distance, and general activity go in activities.
- Sleep information goes in sleep_entries.

STRICT EXTRACTION RULES:
- Use ONLY values explicitly written by the user.
- NEVER estimate, infer, calculate, or guess missing values.
- Any field not explicitly stated MUST be null.
- Do not invent timestamps or dates.
- Do not infer calories burned from steps.
- Do not infer active minutes from walking or steps.
- Do not convert steps into distance.
- If the user says "8500 steps", steps MUST be 8500.
- Preserve numeric values exactly as stated.
- Do not estimate food calories or macros yet.
- If a food quantity is not stated, quantity must be null.
- Return JSON only.

User input:
{text}
"""

    response = ask_local_llm(
    prompt,
    ParsedInput.model_json_schema(),
    )

    return ParsedInput.model_validate_json(response)