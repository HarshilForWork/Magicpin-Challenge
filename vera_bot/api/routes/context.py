from datetime import datetime, timezone

from fastapi import APIRouter

from vera_bot.models.requests import ContextRequest
from vera_bot.models.responses import ContextAccepted
import vera_bot.core.state as state

router = APIRouter()


@router.post("/v1/context", response_model=ContextAccepted)
async def push_context(body: ContextRequest):
    current_version = await state.get_context_version(body.scope, body.context_id)
    if current_version > body.version:
        return ContextAccepted(
            accepted=False,
            reason="stale_version",
            current_version=current_version,
        )
    if current_version == body.version:
        existing = await state.get_context(body.scope, body.context_id)
        if existing == body.payload:
            return ContextAccepted(
                accepted=True,
                ack_id=f"ack_{body.context_id}_v{body.version}",
            )
        return ContextAccepted(
            accepted=False,
            reason="stale_version",
            current_version=current_version,
        )

    stored_at = datetime.now(timezone.utc).isoformat()
    await state.save_context(body.scope, body.context_id, body.version, body.payload, stored_at)

    return ContextAccepted(
        accepted=True,
        ack_id=f"ack_{body.context_id}_v{body.version}",
        stored_at=stored_at,
    )
