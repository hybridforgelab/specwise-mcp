import json

import httpx
import pytest

from specwise_mcp import client


class Recorder:
    """Answers every request with the next queued response and keeps what was sent."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.responses: list[httpx.Response] = []

    def queue(self, status=200, body=None, headers=None):
        self.responses.append(httpx.Response(status, json=body if body is not None else {}, headers=headers or {}))

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responses.pop(0) if self.responses else httpx.Response(200, json={})

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]

    def last_json(self):
        return json.loads(self.last.content)


@pytest.fixture
def api(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(client, "TRANSPORT", httpx.MockTransport(rec))
    for name in ("RAPIDAPI_KEY", "API_MARKET_KEY", "HFL_MARKETPLACE", "HFL_API_URL", "HFL_API_BEARER"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("RAPIDAPI_KEY", "rk")
    return rec
