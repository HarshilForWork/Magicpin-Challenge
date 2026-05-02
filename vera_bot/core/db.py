import motor.motor_asyncio
from pymongo import ReturnDocument
from core.config import settings

client = None
db = None


async def connect_db():
    global client, db
    client = motor.motor_asyncio.AsyncIOMotorClient(settings["mongodb"]["uri"])
    db = client[settings["mongodb"]["database"]]


async def close_db():
    if client:
        client.close()


async def get_context(scope: str, context_id: str) -> dict | None:
    key = f"{scope}:{context_id}"
    doc = await db.contexts.find_one({"_id": key})
    return doc["payload"] if doc else None


async def get_context_version(scope: str, context_id: str) -> int:
    key = f"{scope}:{context_id}"
    doc = await db.contexts.find_one({"_id": key}, {"version": 1})
    return doc["version"] if doc else 0


async def save_context(scope: str, context_id: str, version: int, payload: dict, stored_at: str):
    key = f"{scope}:{context_id}"
    await db.contexts.replace_one(
        {"_id": key},
        {
            "_id": key,
            "scope": scope,
            "context_id": context_id,
            "version": version,
            "payload": payload,
            "stored_at": stored_at,
        },
        upsert=True,
    )


async def count_contexts() -> dict:
    counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
    for scope in counts:
        counts[scope] = await db.contexts.count_documents({"scope": scope})
    return counts


async def get_conversation(conversation_id: str) -> dict | None:
    return await db.conversations.find_one({"_id": conversation_id})


async def save_conversation(conv: dict):
    await db.conversations.replace_one(
        {"_id": conv["_id"]},
        conv,
        upsert=True,
    )


async def push_turn(conversation_id: str, turn: dict):
    await db.conversations.update_one(
        {"_id": conversation_id},
        {"$push": {"turns": turn}, "$set": {"last_updated": turn["timestamp"]}},
    )


async def increment_auto_reply(conversation_id: str) -> int:
    result = await db.conversations.find_one_and_update(
        {"_id": conversation_id},
        {"$inc": {"auto_reply_count": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return result["auto_reply_count"] if result else 1


async def increment_auto_reply_for_merchant(merchant_id: str) -> int:
    result = await db.auto_reply_counters.find_one_and_update(
        {"_id": merchant_id},
        {"$inc": {"count": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return result["count"] if result else 1


async def set_conversation_status(conversation_id: str, status: str):
    await db.conversations.update_one(
        {"_id": conversation_id},
        {"$set": {"status": status}},
    )


async def is_suppressed(merchant_id: str, now: str) -> bool:
    doc = await db.suppressed.find_one(
        {
            "_id": merchant_id,
            "$or": [
                {"until": None},
                {"until": {"$gt": now}},
            ],
        }
    )
    return doc is not None


async def suppress(id: str, type: str, reason: str, until: str | None, created_at: str):
    await db.suppressed.replace_one(
        {"_id": id},
        {"_id": id, "type": type, "reason": reason, "until": until, "created_at": created_at},
        upsert=True,
    )
