import asyncio
import os
import re
from datetime import datetime

from groq import AsyncGroq

from composer.context import build_toon_context
from composer.prompts import get_system_prompt
from core.config import settings
from core.logging import log_composition, log_validation_failure

_client = None


def _get_client() -> AsyncGroq:
    global _client
    if _client is not None:
        return _client
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set. Add it to vera_bot/.env or your environment.")
    _client = AsyncGroq(api_key=api_key)
    return _client

VALIDATION_RULES = [
    (lambda b: len(b) < settings["composer"]["min_body_chars"], "too_short"),
    (lambda b: "http://" in b or "https://" in b, "contains_url"),
    (
        lambda b: any(w in b.lower() for w in ["guaranteed", "miracle", "100% safe", "completely cure"]),
        "taboo_word",
    ),
    (lambda b: b.count("?") > 2, "too_many_questions"),
]


def validate(body: str) -> tuple[bool, str]:
    for rule, reason in VALIDATION_RULES:
        if rule(body):
            return False, reason
    return True, ""


async def compose(
    filtered: dict,
    merchant: dict,
    trigger: dict,
    customer: dict | None,
    history: list[dict],
    voice: dict | None = None,
) -> tuple[str, str]:
    """
    Returns (body, rationale).
    Retries up to max_retries if validation fails.
    """

    toon_ctx = build_toon_context(
        filtered=filtered,
        merchant=merchant,
        trigger=trigger,
        customer=customer,
        history=history,
        max_history_turns=settings["context"]["max_history_turns"],
    )

    system_prompt = get_system_prompt(trigger.get("kind", ""))

    voice_note = ""
    if voice:
        taboos = ", ".join(voice.get("vocab_taboo", []))
        voice_note = f"\nVOICE TABOOS: {taboos}" if taboos else ""

    user_prompt = f"""
{toon_ctx}
{voice_note}

Now write the WhatsApp message.
Respond in this exact format:

BODY:
<the message text here>

RATIONALE:
<one sentence explaining why this message fits the context>

CTA_TYPE: open_ended | binary_yes_no | binary_confirm_cancel | multi_choice_slot | none
"""

    max_retries = settings["composer"]["max_retries"]
    last_body = ""
    last_rationale = ""
    last_failure_reason = ""

    for attempt in range(max_retries + 1):
        retry_note = ""
        if attempt > 0:
            retry_note = f"\n\nPREVIOUS ATTEMPT FAILED ({last_failure_reason}). Fix and retry."

        response = await _get_client().chat.completions.create(
            model=settings["llm"]["model"],
            max_completion_tokens=settings["llm"]["max_tokens"],
            temperature=settings["llm"]["temperature"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt + retry_note},
            ],
        )

        raw = response.choices[0].message.content or ""
        body, rationale = parse_output(raw)

        valid, reason = validate(body)

        if valid:
            log_composition(
                trigger_kind=trigger.get("kind", ""),
                merchant_id=merchant.get("merchant_id", ""),
                prompt=user_prompt,
                filtered_context=filtered,
                output=body,
                rationale=rationale,
                model=settings["llm"]["model"],
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
            )
            return body, rationale

        last_failure_reason = reason
        last_body = body
        log_validation_failure(trigger.get("kind", ""), merchant.get("merchant_id", ""), reason, body)

    return last_body, last_rationale


def parse_output(raw: str) -> tuple[str, str]:
    body = ""
    rationale = ""
    body_match = re.search(r"BODY:\s*(.*?)(?=RATIONALE:|CTA_TYPE:|$)", raw, re.DOTALL)
    rationale_match = re.search(r"RATIONALE:\s*(.*?)(?=CTA_TYPE:|$)", raw, re.DOTALL)
    if body_match:
        body = body_match.group(1).strip()
    if rationale_match:
        rationale = rationale_match.group(1).strip()
    return body, rationale


def parse_cta(raw: str) -> str:
    cta_match = re.search(r"CTA_TYPE:\s*(\S+)", raw)
    if cta_match:
        return cta_match.group(1).strip()
    return "open_ended"
