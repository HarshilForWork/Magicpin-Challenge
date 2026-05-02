import os
import json
import time

from groq import AsyncGroq

from vera_bot.core.config import settings
from vera_bot.utils.tokenizer import count_completion_tokens, count_prompt_tokens, estimate_total_cost

_client = None

INTENT_SYSTEM = """Classify the merchant's WhatsApp message into exactly one intent.
Return only the label, nothing else.

Labels:
- accept       (yes, let's do it, go ahead, haan, kar do, send it, confirm)
- reject       (no, not interested, stop, band karo, nahi chahiye)
- question     (asking for more info, what is, how does, kya hai)
- offtopic     (completely unrelated topic like GST, delivery, other business)
- unclear      (cannot determine)
"""


def _get_client() -> AsyncGroq:
    global _client
    if _client is not None:
        return _client
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set. Add it to vera_bot/.env or your environment.")
    _client = AsyncGroq(api_key=api_key)
    return _client


async def classify_intent(message: str) -> str:
    start = time.monotonic()
    print(f"[intent] start len={len(message)}")
    try:
        response = await _get_client().chat.completions.create(
            model=settings["llm"]["model"],
            max_completion_tokens=10,
            temperature=0,
            messages=[
                {"role": "system", "content": INTENT_SYSTEM},
                {"role": "user", "content": message},
            ],
        )
    except Exception as exc:
        duration = time.monotonic() - start
        print(f"[intent] error after {duration:.2f}s: {exc}")
        raise
    duration = time.monotonic() - start
    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
    completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
    print(
        "[intent] done "
        f"t={duration:.2f}s "
        f"prompt_tokens={prompt_tokens} completion_tokens={completion_tokens}"
    )

    content = response.choices[0].message.content if response.choices else None
    if not content:
        # Debug: log raw response shape when the model returns no content.
        try:
            dump = response.model_dump() if hasattr(response, "model_dump") else str(response)
            print("[intent] Empty LLM content. Raw response:", json.dumps(dump, default=str)[:2000])
        except Exception as exc:
            print(f"[intent] Empty LLM content. Failed to dump response: {exc}")
        return "unclear"
    label = content.strip().lower()
    if label not in ("accept", "reject", "question", "offtopic", "unclear"):
        return "unclear"
    
    # Log intent classification with token metrics
    if settings["mlflow"]["log_prompts"] and not settings.get("app", {}).get("production", False):
        import mlflow
        from datetime import datetime
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
        completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
        if prompt_tokens is None:
            prompt_tokens = count_prompt_tokens(INTENT_SYSTEM, message)
        if completion_tokens is None:
            completion_tokens = count_completion_tokens(content)
        cost_breakdown = estimate_total_cost(prompt_tokens, completion_tokens)
        with mlflow.start_run(run_name=f"intent_{label}_{datetime.utcnow().isoformat()}"):
            mlflow.log_param("intent_label", label)
            mlflow.log_param("model", settings["llm"]["model"])
            mlflow.log_text(message, "merchant_message.txt")
            mlflow.log_metric("prompt_tokens", prompt_tokens)
            mlflow.log_metric("completion_tokens", completion_tokens)
            mlflow.log_metric("total_tokens", cost_breakdown["total_tokens"])
            mlflow.log_metric("total_cost_usd", cost_breakdown["total_cost"])
    
    return label
