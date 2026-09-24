import os
import json
import time
from pathlib import Path
from openai import OpenAI


#MODEL = "llama-3.3-70b"  # cambia al modelo real disponible en tu cuenta
#PROVIDER = "cerebras"

# Ajusta cuando tengas pricing real o déjalo en None si es free tier
INPUT_PRICE_PER_M = 0.0
OUTPUT_PRICE_PER_M = 0.0

PROMPT_PATH = Path("prompts/conceptual_interpretation.md")
PAYLOAD_PATH = Path("ai_conceptual_payload.json")
OUTPUT_PATH = Path("outputs/ai_initial_note_cerebras.json")


def main():
    api_key = os.environ.get("CEREBRAS_API_KEY")
    if not api_key:
        raise RuntimeError("Falta CEREBRAS_API_KEY")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    with open(PAYLOAD_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    user_message = (
        "Contexto para generar la nota inicial:\n\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.cerebras.ai/v1"
    )

    start = time.time()

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=0.25,
        max_tokens=700,
        response_format={"type": "json_object"}
    )

    latency_s = round(time.time() - start, 3)

    content = response.choices[0].message.content
    usage = getattr(response, "usage", None)

    token_usage = {
        "provider": PROVIDER,
        "model": MODEL,
        "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
        "completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
        "total_tokens": getattr(usage, "total_tokens", None) if usage else None,
        "estimated_cost_usd_uncached": None,
        "latency_s": latency_s
    }

    if usage and token_usage["prompt_tokens"] is not None:
        token_usage["estimated_cost_usd_uncached"] = (
            (token_usage["prompt_tokens"] / 1_000_000) * INPUT_PRICE_PER_M
            + (token_usage["completion_tokens"] / 1_000_000) * OUTPUT_PRICE_PER_M
        )

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = {"parse_error": True, "raw_output": content}

    result = {
        "output": parsed,
        "token_usage": token_usage
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Guardado {OUTPUT_PATH}")
    print(json.dumps(token_usage, ensure_ascii=False, indent=2))
    print(json.dumps(parsed, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()