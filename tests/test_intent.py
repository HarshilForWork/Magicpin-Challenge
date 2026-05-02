import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from vera_bot.handlers import intent as intent_handler


class DummyClientEmpty:
    class Chat:
        class Completions:
            async def create(self, *args, **kwargs):
                return SimpleNamespace(choices=[])
        completions = Completions()
    chat = Chat()


class DummyClientAccept:
    class Chat:
        class Completions:
            async def create(self, *args, **kwargs):
                msg = SimpleNamespace(content="accept")
                choice = SimpleNamespace(message=msg)
                return SimpleNamespace(choices=[choice])
        completions = Completions()
    chat = Chat()


def test_classify_intent_empty_response_returns_unclear():
    async def run():
        with patch("vera_bot.handlers.intent._get_client", return_value=DummyClientEmpty()):
            return await intent_handler.classify_intent("ok")

    label = asyncio.run(run())
    assert label == "unclear"


def test_classify_intent_accept_label():
    async def run():
        with patch("vera_bot.handlers.intent._get_client", return_value=DummyClientAccept()):
            return await intent_handler.classify_intent("ok")

    label = asyncio.run(run())
    assert label == "accept"
