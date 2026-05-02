import asyncio
import time
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter

from vera_bot.composer.composer import compose
from vera_bot.core.config import settings
from vera_bot.core.logging import log_judge_reply
from vera_bot.filter.router import route_filter
from vera_bot.handlers.auto_reply import is_auto_reply, handle_auto_reply
from vera_bot.handlers.intent import classify_intent
from vera_bot.models.requests import ReplyRequest
from vera_bot.models.responses import ReplyResponse
import vera_bot.core.state as state

router = APIRouter()


async def _log_judge_reply_async(
    conversation_id: str,
    merchant_id: str,
    message: str,
    detected_intent: str,
    bot_action: str,
    bot_body: str,
):
    try:
        await asyncio.to_thread(
            log_judge_reply,
            conversation_id,
            merchant_id,
            message,
            detected_intent,
            bot_action,
            bot_body,
        )
    except Exception as exc:
        print(f"[reply] log_judge_reply error: {exc}")


def _log_judge_reply_bg(
    conversation_id: str,
    merchant_id: str,
    message: str,
    detected_intent: str,
    bot_action: str,
    bot_body: str,
):
    asyncio.create_task(
        _log_judge_reply_async(
            conversation_id,
            merchant_id,
            message,
            detected_intent,
            bot_action,
            bot_body,
        )
    )


@router.post("/v1/reply", response_model=ReplyResponse)
async def reply(body: ReplyRequest):
    start = time.monotonic()
    print(f"[reply] start conv={body.conversation_id} len={len(body.message)}")
    conv = await state.get_conversation(body.conversation_id)
    timestamp = datetime.now(timezone.utc).isoformat()
    merchant_id = body.merchant_id or (conv.get("merchant_id") if conv else None)

    if is_auto_reply(body.message):
        result = await handle_auto_reply(body.conversation_id, merchant_id, state)
        if result.get("action") in ("send", "wait", "end") and conv:
            await state.push_turn(body.conversation_id, {
                "turn_number": body.turn_number,
                "role": "merchant",
                "body": body.message,
                "timestamp": timestamp,
            })
        _log_judge_reply_bg(
            body.conversation_id,
            merchant_id or "",
            body.message,
            "auto_reply",
            result["action"],
            result.get("body", ""),
        )
        print(f"[reply] done t={time.monotonic() - start:.2f}s action={result['action']}")
        return ReplyResponse(**result)

    intent = await classify_intent(body.message)

    if not conv or not merchant_id:
        if intent == "accept":
            response_body = "Great, proceeding now. Next step: confirm the best time to start."
            _log_judge_reply_bg(body.conversation_id, merchant_id or "", body.message, intent, "send", response_body)
            print(f"[reply] done t={time.monotonic() - start:.2f}s action=send")
            return ReplyResponse(
                action="send",
                body=response_body,
                cta="binary_yes_no",
                rationale="No prior context; moving to action after acceptance.",
            )
        if intent == "reject":
            _log_judge_reply_bg(body.conversation_id, merchant_id or "", body.message, intent, "end", "")
            print(f"[reply] done t={time.monotonic() - start:.2f}s action=end")
            return ReplyResponse(action="end", body="", rationale="Merchant opted out.")
        if intent == "offtopic":
            response_body = "Noted. When you're ready, we can continue from where we left off."
            _log_judge_reply_bg(body.conversation_id, merchant_id or "", body.message, intent, "send", response_body)
            print(f"[reply] done t={time.monotonic() - start:.2f}s action=send")
            return ReplyResponse(
                action="send",
                body=response_body,
                cta="open_ended",
                rationale="Off-topic response without context.",
            )
        response_body = "Thanks. Share a bit more so I can proceed."
        _log_judge_reply_bg(body.conversation_id, merchant_id or "", body.message, intent, "send", response_body)
        print(f"[reply] done t={time.monotonic() - start:.2f}s action=send")
        return ReplyResponse(
            action="send",
            body=response_body,
            cta="open_ended",
            rationale="No conversation context found; requesting clarification.",
        )

    if conv:
        await state.push_turn(body.conversation_id, {
            "turn_number": body.turn_number,
            "role": "merchant",
            "body": body.message,
            "timestamp": timestamp,
        })

    if intent == "reject":
        suppress_days = settings["suppression"]["hostile_suppress_days"]
        until = (datetime.now(timezone.utc) + timedelta(days=suppress_days)).isoformat()
        await state.suppress(merchant_id, "merchant", "opted_out", until, timestamp)
        await state.set_conversation_status(body.conversation_id, "ended")
        _log_judge_reply_bg(body.conversation_id, merchant_id or "", body.message, "reject", "end", "")
        print(f"[reply] done t={time.monotonic() - start:.2f}s action=end")
        return ReplyResponse(action="end", body="", rationale="Merchant opted out. Suppressing.")

    if intent == "offtopic":
        response_body = "That's outside what I can help with directly. Coming back to where we left off -- want me to continue?"
        await state.push_turn(body.conversation_id, {
            "turn_number": body.turn_number + 1,
            "role": "bot",
            "body": response_body,
            "action": "send",
            "timestamp": timestamp,
        })
        print(f"[reply] done t={time.monotonic() - start:.2f}s action=send")
        return ReplyResponse(
            action="send",
            body=response_body,
            cta="open_ended",
            rationale="Off-topic ask; redirecting to original thread.",
        )

    trigger_id = conv.get("trigger_id", "")
    trigger = await state.get_context("trigger", trigger_id)
    merchant = await state.get_context("merchant", merchant_id)
    category_slug = (merchant or {}).get("category_slug", "")
    category = await state.get_context("category", category_slug)
    customer_id = conv.get("customer_id")
    customer = await state.get_context("customer", customer_id) if customer_id else None

    filtered = route_filter(category or {}, merchant or {}, trigger or {}, customer)
    history = conv.get("turns", [])

    if intent == "accept":
        filtered["_intent"] = "accept"

    body_text, rationale = await compose(
        filtered=filtered,
        merchant=merchant or {},
        trigger=trigger or {},
        customer=customer,
        history=history,
        voice=(category or {}).get("voice"),
    )

    await state.push_turn(body.conversation_id, {
        "turn_number": body.turn_number + 1,
        "role": "bot",
        "body": body_text,
        "action": "send",
        "timestamp": timestamp,
    })

    _log_judge_reply_bg(body.conversation_id, merchant_id, body.message, intent, "send", body_text)

    print(f"[reply] done t={time.monotonic() - start:.2f}s action=send")

    return ReplyResponse(
        action="send",
        body=body_text,
        cta="open_ended",
        rationale=rationale,
    )
