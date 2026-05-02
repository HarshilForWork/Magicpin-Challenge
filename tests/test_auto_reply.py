import asyncio

from vera_bot.handlers.auto_reply import handle_auto_reply, is_auto_reply


class FakeDB:
    def __init__(self):
        self.counts = {}
        self.suppressed = []
        self.ended = []

    async def increment_auto_reply_for_merchant(self, merchant_id: str) -> int:
        self.counts[merchant_id] = self.counts.get(merchant_id, 0) + 1
        return self.counts[merchant_id]

    async def increment_auto_reply(self, conversation_id: str) -> int:
        self.counts[conversation_id] = self.counts.get(conversation_id, 0) + 1
        return self.counts[conversation_id]

    async def suppress(self, merchant_id, type, reason, until, created_at):
        self.suppressed.append((merchant_id, type, reason))

    async def set_conversation_status(self, conversation_id, status):
        self.ended.append((conversation_id, status))


def test_is_auto_reply_matches_known_phrases():
    assert is_auto_reply("Thank you for contacting us! Our team will respond shortly.")
    assert not is_auto_reply("Hey, can we chat about offers?")


def test_handle_auto_reply_progresses_and_ends():
    db = FakeDB()

    async def run():
        res1 = await handle_auto_reply("c1", "m1", db)
        res2 = await handle_auto_reply("c2", "m1", db)
        res3 = await handle_auto_reply("c3", "m1", db)
        return res1, res2, res3

    res1, res2, res3 = asyncio.run(run())

    assert res1["action"] == "send"
    assert res2["action"] == "wait"
    assert res3["action"] == "end"
