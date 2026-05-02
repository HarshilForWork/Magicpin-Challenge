import vera_bot.core.db as db
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# In-memory context cache -- keyed by "scope:context_id"
# Cleared on each server restart; persists across requests within a process.
# MongoDB is the source of truth; this is a read-through cache only.
# ---------------------------------------------------------------------------
_context_cache: dict[str, dict] = {}
_suppression_cache: dict[str, bool] = {}


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------

async def get_context(scope: str, context_id: str) -> dict | None:
    """
    Returns the context payload for the given scope and id.
    Checks in-memory cache first; falls back to MongoDB on miss.
    """
    if not context_id:
        return None
    key = f"{scope}:{context_id}"
    if key in _context_cache:
        return _context_cache[key]
    payload = await db.get_context(scope, context_id)
    if payload is not None:
        _context_cache[key] = payload
    return payload


async def save_context(scope: str, context_id: str, version: int, payload: dict, stored_at: str) -> None:
    """
    Writes through: updates MongoDB and replaces the cache entry atomically.
    """
    await db.save_context(scope, context_id, version, payload, stored_at)
    key = f"{scope}:{context_id}"
    _context_cache[key] = payload


async def get_context_version(scope: str, context_id: str) -> int:
    """Delegates to db; version tracking does not benefit from caching."""
    return await db.get_context_version(scope, context_id)


async def count_contexts() -> dict:
    """Live count from MongoDB -- not cached."""
    return await db.count_contexts()


def invalidate_context(scope: str, context_id: str) -> None:
    """Force-evict a single entry from the cache (e.g. after a stale-version reject)."""
    _context_cache.pop(f"{scope}:{context_id}", None)


def clear_context_cache() -> None:
    """Wipe the entire context cache. Call at startup or during testing."""
    _context_cache.clear()


# ---------------------------------------------------------------------------
# Conversation helpers -- thin pass-through wrappers over db
# Kept here so routes have a single import for all state operations.
# ---------------------------------------------------------------------------

async def get_conversation(conversation_id: str) -> dict | None:
    return await db.get_conversation(conversation_id)


async def save_conversation(conv: dict) -> None:
    await db.save_conversation(conv)


async def push_turn(conversation_id: str, turn: dict) -> None:
    await db.push_turn(conversation_id, turn)


async def set_conversation_status(conversation_id: str, status: str) -> None:
    await db.set_conversation_status(conversation_id, status)


async def increment_auto_reply(conversation_id: str) -> int:
    return await db.increment_auto_reply(conversation_id)


async def increment_auto_reply_for_merchant(merchant_id: str) -> int:
    return await db.increment_auto_reply_for_merchant(merchant_id)


# ---------------------------------------------------------------------------
# Suppression helpers -- cached per process tick
# ---------------------------------------------------------------------------

async def is_suppressed(merchant_id: str, now: str) -> bool:
    """
    Returns True if the merchant is currently suppressed.
    Result is cached for the duration of the process to avoid repeated DB hits
    within a single tick loop. Cache is cleared by clear_suppression_cache().
    """
    if merchant_id in _suppression_cache:
        return _suppression_cache[merchant_id]
    result = await db.is_suppressed(merchant_id, now)
    _suppression_cache[merchant_id] = result
    return result


async def suppress(id: str, type: str, reason: str, until: str | None, created_at: str) -> None:
    """
    Writes suppression to MongoDB and updates the cache immediately so subsequent
    checks within the same tick see the new suppression without a DB round-trip.
    """
    await db.suppress(id, type, reason, until, created_at)
    _suppression_cache[id] = True


def clear_suppression_cache() -> None:
    """Clear suppression cache. Call at the start of each /v1/tick handler."""
    _suppression_cache.clear()
