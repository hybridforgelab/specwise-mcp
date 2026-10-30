import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from specwise_mcp import client
from specwise_mcp.client import PRODUCTS, call, target

P = PRODUCTS["specwise"]
HOST = "specwise-openapi-validator-and-diff-api.p.rapidapi.com"


def test_rapidapi_by_default():
    t = target(P, {"RAPIDAPI_KEY": "rk"})
    assert t.market == "rapidapi" and t.base == f"https://{HOST}"
    assert t.headers == {"X-RapidAPI-Key": "rk", "X-RapidAPI-Host": HOST}


def test_direct_for_maintainers():
    t = target(P, {"HFL_API_URL": "https://api.example/", "HFL_API_BEARER": "b", "RAPIDAPI_KEY": "rk"})
    assert t.market == "direct" and t.base == "https://api.example" and t.headers == {"Authorization": "Bearer b"}


def test_env_is_read_from_os_by_default(monkeypatch):
    monkeypatch.setenv("RAPIDAPI_KEY", "from-os")
    monkeypatch.delenv("HFL_API_URL", raising=False)
    monkeypatch.delenv("HFL_MARKETPLACE", raising=False)
    assert target(P).headers["X-RapidAPI-Key"] == "from-os"


def test_apimarket_when_only_its_key_is_set_or_chosen():
    t = target(P, {"API_MARKET_KEY": "mk"})
    assert t.market == "apimarket" and t.base == "https://prod.api.market/api/v1/hybrid-forge-lab/specwise"
    assert t.headers == {"x-api-market-key": "mk"}
    assert target(P, {"RAPIDAPI_KEY": "rk", "API_MARKET_KEY": "mk", "HFL_MARKETPLACE": "apimarket"}).market == "apimarket"
    assert target(P, {"RAPIDAPI_KEY": "rk", "API_MARKET_KEY": "mk"}).market == "rapidapi"
    assert target(P, {"RAPIDAPI_KEY": "rk", "API_MARKET_KEY": "mk", "HFL_MARKETPLACE": "rapidapi"}).market == "rapidapi"


def test_key_errors_explain_what_to_do():
    with pytest.raises(ToolError, match="No API key. Set RAPIDAPI_KEY .*api.market"):
        target(P, {})
    with pytest.raises(ToolError, match="API_MARKET_KEY is not set"):
        target(P, {"RAPIDAPI_KEY": "rk", "HFL_MARKETPLACE": "apimarket"})


async def test_apimarket_refusal_points_to_the_store(api, monkeypatch):
    monkeypatch.delenv("RAPIDAPI_KEY")
    monkeypatch.setenv("API_MARKET_KEY", "mk")
    api.queue(403, {"message": "no"})
    with pytest.raises(ToolError, match="api.market/store/hybrid-forge-lab/specwise"):
        await call(P, "GET", "/x")


async def test_success_adds_quota_and_user_agent(api):
    api.queue(200, {"status": "ok"}, {"x-ratelimit-requests-remaining": "12"})
    r = await call(P, "POST", "/v1/x", json={"a": 1})
    assert r == {"status": "ok", "quota_remaining": 12}
    assert api.last.headers["user-agent"].startswith("specwise-mcp/")
    api.queue(200, {"a": 1}, {"x-ratelimit-requests-remaining": "n/a"})
    assert (await call(P, "GET", "/x"))["quota_remaining"] == "n/a"
    api.queue(200, [1, 2], {"x-ratelimit-requests-remaining": "3"})
    assert await call(P, "GET", "/x") == [1, 2]


@pytest.mark.parametrize("status,body,match", [
    (401, {"message": "Invalid API key"}, "refused the key .*401: Invalid API key.*specwise-openapi-validator-and-diff-api/pricing"),
    (403, {"message": "You are not subscribed"}, "refused the key"),
    (429, {"message": "quota"}, "quota limit reached"),
    (413, {"detail": "body too large"}, "too large"),
    (422, {"detail": [{"loc": ["x"], "msg": "bad"}]}, "could not process the input: .*bad"),
    (500, {"detail": "boom"}, "HTTP 500: boom"),
])
async def test_errors(api, status, body, match):
    api.queue(status, body)
    with pytest.raises(ToolError, match=match):
        await call(P, "GET", "/x")


async def test_non_json_and_non_dict_error_bodies(monkeypatch):
    def handler(request):
        return httpx.Response(502, text="<html>bad gateway</html>") if "a" in request.url.path \
            else httpx.Response(503, json=["down"])
    monkeypatch.setattr(client, "TRANSPORT", httpx.MockTransport(handler))
    monkeypatch.setenv("RAPIDAPI_KEY", "rk")
    monkeypatch.delenv("HFL_API_URL", raising=False)
    with pytest.raises(ToolError, match="502: <html>bad gateway"):
        await call(P, "GET", "/a")
    with pytest.raises(ToolError, match=r"503: \['down'\]"):
        await call(P, "GET", "/b")


async def test_network_failure(monkeypatch):
    def handler(request):
        raise httpx.ConnectTimeout("slow")
    monkeypatch.setattr(client, "TRANSPORT", httpx.MockTransport(handler))
    monkeypatch.setenv("RAPIDAPI_KEY", "rk")
    monkeypatch.delenv("HFL_API_URL", raising=False)
    with pytest.raises(ToolError, match="could not be reached \\(ConnectTimeout\\)"):
        await call(P, "GET", "/x")
