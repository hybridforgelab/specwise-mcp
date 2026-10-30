# Specwise MCP server

Let your coding agent check an API contract: validate an OpenAPI document, find the breaking changes between two versions (also against git), and validate JSON Schemas and data.

The server is open source (MIT). It calls the [Specwise API](https://specwise.hybridforgelab.com), which is paid, with a free plan.

- You use **your own key, from RapidAPI or api.market**.
- Every tool call is one request on your plan.
- The free Basic plan has 15 requests a month, with a hard limit, so it never runs up a bill.

## 1. Get a key

| marketplace | |
|---|---|
| RapidAPI | [plans](https://rapidapi.com/hybrid-forge-lab-hybrid-forge-lab-default/api/specwise-openapi-validator-and-diff-api/pricing) |
| api.market | [store](https://api.market/store/hybrid-forge-lab/specwise) |

## 2. Add the server to your MCP client

The server runs locally over stdio with [uv](https://docs.astral.sh/uv/). Put your key in its environment.

**JSON configuration** (Claude Desktop, Cursor, VS Code and most clients):

```json
{
  "mcpServers": {
    "specwise": {
      "command": "uvx",
      "args": ["--from", "hybridforgelab-specwise-mcp", "specwise-mcp"],
      "env": { "RAPIDAPI_KEY": "your-rapidapi-key" }
    }
  }
}
```

**Claude Code:**

```bash
claude mcp add specwise --env RAPIDAPI_KEY=your-rapidapi-key -- uvx --from hybridforgelab-specwise-mcp specwise-mcp
```

### Environment

| variable | meaning |
|---|---|
| `RAPIDAPI_KEY` | your RapidAPI key |
| `API_MARKET_KEY` | your api.market key, used when `RAPIDAPI_KEY` is not set |
| `HFL_MARKETPLACE` | `rapidapi` or `apimarket`, when both keys are set |

Without a key the server still starts. The first tool call then explains where to get one.

## 3. Tools

| tool | what it does |
|---|---|
| `validate_openapi(spec=… \| spec_path=…)` | every error with its JSON Pointer, line and column, plus lint warnings (OpenAPI 3.x and Swagger 2.0) |
| `diff_openapi(...)` | each change between two OpenAPI 3.x versions is breaking, warning, non-breaking or info, with a semver suggestion |
| `validate_json_schema(schema=… \| schema_path=…, instance=… \| instance_path=…, draft=None)` | checks the schema against its meta-schema and, if given, the data against the schema |

`diff_openapi` takes the two versions in one of three ways:

- `base` and `revision` as text;
- `base_path` and `revision_path` as files;
- `revision_path` with `base_git_ref`. For example, after editing a spec: `revision_path="openapi.yaml", base_git_ref="main"`.

Every tool returns the API's JSON response.

- When the marketplace reports it, `quota_remaining` is added: the requests left on your plan this month.
- Errors are explained in plain words, with what to do next:
  - key refused, with the link to subscribe;
  - quota reached, with the plans;
  - input the API couldn't process, with the API's reason.

## Privacy

- Local files are read only when a tool is given their path. They are sent to the API for that one request.
- The API processes inputs in memory and doesn't store them. See the [privacy policy](https://specwise.hybridforgelab.com/privacy.html).
- Your key is only sent to the marketplace you chose.

## Limits

- Documents up to about 900 KiB each.
- External `$ref`s are not fetched. Bundle multi-file specs first (`redocly bundle`).
- The diff needs OpenAPI 3.x; Swagger 2.0 can be validated, not diffed.
- The server needs Python 3.10+ (uv installs it for you).

## Development

```bash
uv venv && uv pip install -e ".[dev]"
.venv/bin/pytest            # unit tests, no network; 100% coverage required
.venv/bin/ruff check src tests scripts
```

`scripts/e2e_stdio.py specwise` runs the server over stdio, as a client would, and calls its tools against the real API. It needs `RAPIDAPI_KEY` or `API_MARKET_KEY`.

## Licence

MIT. Specwise itself is a paid API with a free plan, run by [Hybrid Forge Lab](https://hybridforgelab.com).
