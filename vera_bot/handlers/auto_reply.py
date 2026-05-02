AUTO_REPLY_PHRASES = [
    "thank you for contacting",
    "our team will respond shortly",
    "we will get back to you",
    "this is an automated response",
    "currently unavailable",
    "office hours",
]


def is_auto_reply(message: str) -> bool:
    msg = message.lower()
    return any(phrase in msg for phrase in AUTO_REPLY_PHRASES)


async def handle_auto_reply(
    conversation_id: str,
    merchant_id: str,
    db_module,
) -> dict:
    """
    State machine for auto-replies.
    Returns the appropriate action dict.
    """
    from vera_bot.core.config import settings

    if merchant_id:
        count = await db_module.increment_auto_reply_for_merchant(merchant_id)
    else:
        count = await db_module.increment_auto_reply(conversation_id)

    if count == 1:
        return {
            "action": "send",
            "body": "Looks like an auto-reply :) When you see this, just reply YES to continue.",
            "cta": "binary_yes_no",
            "rationale": "Detected auto-reply on turn 1; nudging owner to respond.",
        }
    elif count == 2:
        wait = settings["suppression"]["auto_reply_wait_long_seconds"]
        return {
            "action": "wait",
            "wait_seconds": wait,
            "rationale": f"Auto-reply second time; backing off {wait}s.",
        }
    else:
        from datetime import datetime, timedelta

        suppress_until = (
            datetime.utcnow() + timedelta(seconds=settings["suppression"]["auto_reply_wait_long_seconds"])
        ).isoformat()
        await db_module.suppress(
            merchant_id,
            "merchant",
            "auto_reply",
            suppress_until,
            datetime.utcnow().isoformat(),
        )
        await db_module.set_conversation_status(conversation_id, "ended")
        return {
            "action": "end",
            "rationale": "Auto-reply 3x in a row. Closing and suppressing temporarily.",
        }
