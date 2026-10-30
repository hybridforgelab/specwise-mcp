"""HTTP client: picks the marketplace from the environment and turns API errors into
messages an agent (and its user) can act on."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx
from mcp.server.mcpserver.exceptions import ToolError

RAPIDAPI_LISTING = "https://rapidapi.com/hybrid-forge-lab-hybrid-forge-lab-default/api/"
APIMARKET_BASE = "https://prod.api.market/api/v1/hybrid-forge-lab/"
APIMARKET_STORE = "https://api.market/store/hybrid-forge-lab/"
USER_AGENT = "specwise-mcp/0.1 (+https://specwise.hybridforgelab.com)"
TIMEOUT = httpx.Timeout(60.0, connect=10.0)

# Tests swap this for an httpx.MockTransport.
TRANSPORT: httpx.AsyncBaseTransport | None = None


@dataclass(frozen=True)
class Product:
    slug: str
    name: str
    rapidapi: str  # RapidAPI listing slug; the host is "<slug>.p.rapidapi.com"
    apimarket: bool  # sold on api.market too

    @property
    def rapidapi_host(self) -> str:
        return f"{self.rapidapi}.p.rapidapi.com"

    @property
    def plans(self) -> str:
        return RAPIDAPI_LISTING + self.rapidapi + "/pricing"


PRODUCTS = {
    "specwise": Product("specwise", "Specwise", "specwise-openapi-validator-and-diff-api", apimarket=True),
}


@dataclass(frozen=True)
class Target:
    base: str
    headers: dict[str, str]
    market: str  # "rapidapi", "apimarket" or "direct"


def target(product: Product, env: dict[str, str] | None = None) -> Target:
    """Where to send requests, from the environment. Read on every call, so the server starts without a key and
    the first tool call explains how to get one."""
    env = dict(os.environ if env is None else env)
    # Maintainers only: call our own host directly with an internal bearer key.
    if env.get("HFL_API_URL") and env.get("HFL_API_BEARER"):
        return Target(env["HFL_API_URL"].rstrip("/"), {"Authorization": f"Bearer {env['HFL_API_BEARER']}"}, "direct")
    rapid, market = env.get("RAPIDAPI_KEY", ""), env.get("API_MARKET_KEY", "")
    choice = env.get("HFL_MARKETPLACE", "").lower()
    if choice == "apimarket" or (market and not rapid and choice != "rapidapi"):
        if not market:
            raise ToolError("HFL_MARKETPLACE is apimarket but API_MARKET_KEY is not set.")
        return Target(APIMARKET_BASE + product.slug, {"x-api-market-key": market}, "apimarket")
    if not rapid:
        where = f" or API_MARKET_KEY ({APIMARKET_STORE}{product.slug})" if product.apimarket else ""
        raise ToolError(f"No API key. Set RAPIDAPI_KEY (free Basic plan: {product.plans}){where} in this MCP "
                        "server's environment, then restart it.")
    return Target(f"https://{product.rapidapi_host}",
                  {"X-RapidAPI-Key": rapid, "X-RapidAPI-Host": product.rapidapi_host}, "rapidapi")


def _detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:300]
    if isinstance(body, dict):
        detail = body.get("detail", body.get("message", body))
        return detail if isinstance(detail, str) else str(detail)[:500]
    return str(body)[:300]


async def call(product: Product, method: str, path: str, *, json: Any = None, params: dict | None = None,
               files: dict | None = None, data: dict | None = None) -> dict:
    """One API request. Returns the JSON body, plus `quota_remaining` when the marketplace reports it."""
    t = target(product)
    url = t.base + path
    headers = {"User-Agent": USER_AGENT, **t.headers}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, transport=TRANSPORT) as client:
            r = await client.request(method, url, headers=headers, json=json, params=params, files=files, data=data)
    except httpx.HTTPError as exc:
        raise ToolError(f"The {product.name} API could not be reached ({type(exc).__name__}). Try again later.")
    if r.status_code in (401, 403):
        how = f"{APIMARKET_STORE}{product.slug}" if t.market == "apimarket" else product.plans
        raise ToolError(f"The {product.name} API refused the key (HTTP {r.status_code}: {_detail(r)}). "
                        f"Check the key and the subscription: {how}")
    if r.status_code == 429:
        raise ToolError(f"{product.name} rate or monthly quota limit reached ({_detail(r)}). Plans: {product.plans}")
    if r.status_code == 413:
        raise ToolError(f"The input is too large for {product.name} ({_detail(r)}).")
    if r.status_code == 422:
        raise ToolError(f"{product.name} could not process the input: {_detail(r)}")
    if r.status_code >= 400:
        raise ToolError(f"The {product.name} API answered HTTP {r.status_code}: {_detail(r)}. Try again later.")
    body = r.json()
    quota = r.headers.get("x-ratelimit-requests-remaining")
    if quota is not None and isinstance(body, dict):
        body["quota_remaining"] = int(quota) if quota.isdigit() else quota
    return body
