import time

from fastapi import APIRouter

import vera_bot.core.state as state

router = APIRouter()
START = time.time()


@router.get("/v1/healthz")
async def healthz():
    counts = await state.count_contexts()
    return {
        "status": "ok",
        "uptime_seconds": int(time.time() - START),
        "contexts_loaded": counts,
    }
