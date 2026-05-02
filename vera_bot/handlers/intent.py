import os
import json

from groq import AsyncGroq

from core.config import settings

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
    response = await _get_client().chat.completions.create(
        model=settings["llm"]["model"],
        max_completion_tokens=10,
        temperature=0,
        messages=[
            {"role": "system", "content": INTENT_SYSTEM},
            {"role": "user", "content": message},
        ],
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
    return label
