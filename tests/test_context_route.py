import asyncio
from unittest.mock import AsyncMock, patch

from vera_bot.api.routes import context as context_route
from vera_bot.models.requests import ContextRequest


def _make_request(payload, version=1):
    return ContextRequest(
        scope="category",
        context_id="gyms",
        version=version,
        payload=payload,
        delivered_at="2024-01-01T00:00:00Z",
    )


def test_push_context_accepts_new_version():
    payload = {"slug": "gyms"}
    body = _make_request(payload, version=1)

    save_mock = AsyncMock()

    with patch("api.routes.context.state.get_context_version", new=AsyncMock(return_value=0)), \
         patch("api.routes.context.state.save_context", new=save_mock):
        result = asyncio.run(context_route.push_context(body))

    assert result.accepted is True
    save_mock.assert_awaited_once()


def test_push_context_idempotent_same_payload():
    payload = {"slug": "gyms"}
    body = _make_request(payload, version=1)

    save_mock = AsyncMock()

    with patch("api.routes.context.state.get_context_version", new=AsyncMock(return_value=1)), \
         patch("api.routes.context.state.get_context", new=AsyncMock(return_value=payload)), \
         patch("api.routes.context.state.save_context", new=save_mock):
        result = asyncio.run(context_route.push_context(body))

    assert result.accepted is True
    save_mock.assert_not_awaited()


def test_push_context_rejects_stale_version():
    payload = {"slug": "gyms"}
    body = _make_request(payload, version=1)

    with patch("api.routes.context.state.get_context_version", new=AsyncMock(return_value=2)):
        result = asyncio.run(context_route.push_context(body))

    assert result.accepted is False
    assert result.reason == "stale_version"
