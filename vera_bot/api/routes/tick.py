from datetime import datetime, timezone

from fastapi import APIRouter

from composer.composer import compose, parse_cta
from core.logging import log_filter_result
from filter.router import route_filter
from models.requests import TickRequest
from models.responses import Action, TickResponse
import core.db as db
import core.state as state

router = APIRouter()


@router.post("/v1/tick", response_model=TickResponse)
async def tick(body: TickRequest):
    actions = []
    now = body.now

    state.clear_suppression_cache()

    for trigger_id in body.available_triggers:
        trigger_payload = await state.get_context("trigger", trigger_id)
        if not trigger_payload:
            continue

        merchant_id = trigger_payload.get("merchant_id")
        if not merchant_id:
            continue

        if await state.is_suppressed(merchant_id, now):
            continue

        suppression_key = trigger_payload.get("suppression_key", "")
        existing_conv = await db.db.conversations.find_one({
            "suppression_key": suppression_key,
            "merchant_id": merchant_id,
        })
        if existing_conv:
            continue

        merchant = await state.get_context("merchant", merchant_id)
        if not merchant:
            continue

        category_slug = merchant.get("category_slug")
        category = await state.get_context("category", category_slug)
        if not category:
            continue

        customer_id = trigger_payload.get("customer_id")
        customer = None
        if customer_id:
            customer = await state.get_context("customer", customer_id)

        filtered = route_filter(category, merchant, trigger_payload, customer)
        log_filter_result(trigger_payload.get("kind", ""), merchant_id, filtered)

        body_text, rationale = await compose(
            filtered=filtered,
            merchant=merchant,
            trigger=trigger_payload,
            customer=customer,
            history=[],
            voice=category.get("voice"),
        )

        if not body_text:
            continue

        send_as = "merchant_on_behalf" if customer_id else "vera"

        conv_id = f"conv_{merchant_id}_{trigger_id}"
        timestamp = datetime.now(timezone.utc).isoformat()

        await state.save_conversation({
            "_id": conv_id,
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "trigger_id": trigger_id,
            "turns": [{
                "turn_number": 1,
                "role": "bot",
                "body": body_text,
                "action": "send",
                "timestamp": timestamp,
            }],
            "auto_reply_count": 0,
            "status": "active",
            "suppression_key": suppression_key,
            "last_updated": timestamp,
        })

        merchant_name = merchant.get("identity", {}).get("name", "")

        actions.append(Action(
            conversation_id=conv_id,
            merchant_id=merchant_id,
            customer_id=customer_id,
            send_as=send_as,
            trigger_id=trigger_id,
            template_name=f"vera_{trigger_payload.get('kind', 'generic')}_v1",
            template_params=[merchant_name, body_text[:100], ""],
            body=body_text,
            cta="open_ended",
            suppression_key=suppression_key,
            rationale=rationale,
        ))

    return TickResponse(actions=actions)
