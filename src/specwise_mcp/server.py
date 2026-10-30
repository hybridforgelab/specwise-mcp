"""Specwise MCP server: OpenAPI and JSON Schema validation, and OpenAPI breaking-change diffs."""
from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from . import files
from .client import PRODUCTS, call

PRODUCT = PRODUCTS["specwise"]
MAX_FILE = 900 * 1024  # two documents must fit in the API's 2 MB request

server = MCPServer(
    "specwise",
    title="Specwise: OpenAPI validation and breaking changes",
    instructions=(
        "Validate an OpenAPI (3.x or Swagger 2.0) document and get every error with its JSON Pointer, line and "
        "column. Compare two OpenAPI 3.x versions and get each change classified as breaking, warning, "
        "non-breaking or info, with a semver suggestion; use it after editing a spec, against the git version. "
        "Validate JSON Schemas and data. Documents are processed in memory and not stored, and external $refs are "
        "never fetched. Each call is one request on the user's Specwise plan."
    ),
    website_url="https://specwise.hybridforgelab.com",
)

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)


# MCP clients may send JSON documents as objects, and the SDK parses JSON-looking strings into objects too.
# The API takes both: text keeps line numbers, objects are validated as they are.
Doc = str | dict | list | bool | int | float


def _one(value: Doc | None, path: str | None, what: str) -> Doc:
    given = value is not None and value != ""
    if given == bool(path):
        raise ToolError(f"Give exactly one of {what} or {what}_path.")
    return value if given else files.read_text(path, MAX_FILE)


@server.tool(annotations=READ_ONLY)
async def validate_openapi(
    spec: Annotated[Doc | None, Field(description="The document as YAML or JSON text (or a JSON object).")] = None,
    spec_path: Annotated[str | None, Field(description="A local file instead of `spec`.")] = None,
) -> dict:
    """Validate an OpenAPI 3.0/3.1/3.2 or Swagger 2.0 document. Returns every error (not just the first) with its
    JSON Pointer, line and column, plus lint warnings."""
    return await call(PRODUCT, "POST", "/v1/openapi/validate", json={"spec": _one(spec, spec_path, "spec")})


@server.tool(annotations=READ_ONLY)
async def diff_openapi(
    base: Annotated[Doc | None, Field(description="The old version, as YAML or JSON text (or a JSON object).")] = None,
    base_path: Annotated[str | None, Field(description="The old version as a local file.")] = None,
    revision: Annotated[Doc | None, Field(description="The new version, as YAML or JSON text (or a JSON object).")] = None,
    revision_path: Annotated[str | None, Field(description="The new version as a local file.")] = None,
    base_git_ref: Annotated[str | None, Field(
        description="Use revision_path as it is at this git ref (e.g. main, HEAD) as the base.")] = None,
) -> dict:
    """Compare two OpenAPI 3.x documents. Each change is breaking, warning, non-breaking or info; `breaking` says
    whether any is breaking, and `semver` suggests the version bump.

    Typical use after editing a spec: revision_path="openapi.yaml", base_git_ref="main"."""
    new = _one(revision, revision_path, "revision")
    if base_git_ref:
        if base or base_path:
            raise ToolError("Give base_git_ref or base/base_path, not both.")
        if not revision_path:
            raise ToolError("base_git_ref needs revision_path.")
        old = files.git_show(revision_path, base_git_ref)
    else:
        old = _one(base, base_path, "base")
    return await call(PRODUCT, "POST", "/v1/openapi/diff", json={"base": old, "revision": new})


@server.tool(annotations=READ_ONLY)
async def validate_json_schema(
    schema: Annotated[Doc | None, Field(description="The JSON Schema, as JSON or YAML text (or a JSON object).")] = None,
    schema_path: Annotated[str | None, Field(description="A local file instead of `schema`.")] = None,
    instance: Annotated[Any, Field(description="Data to validate: JSON or YAML text, or the value itself. Optional.")] = None,
    instance_path: Annotated[str | None, Field(description="Data to validate, from a local file.")] = None,
    draft: Annotated[Literal["4", "6", "7", "2019-09", "2020-12"] | None,
                     Field(description="Force a draft; by default from $schema, else 2020-12.")] = None,
) -> dict:
    """Check a JSON Schema against its meta-schema and, if given, validate data against it. Every error has the
    instance path, the schema path and, for text input, the line."""
    body: dict = {"schema": _one(schema, schema_path, "schema")}
    if instance is not None or instance_path:
        value = _one(instance, instance_path, "instance")
        body["instance"] = value
        # Text is parsed as YAML (a superset of JSON) and gives line numbers; anything else is the value itself.
        body["instance_format"] = "yaml" if isinstance(value, str) else "value"
    if draft:
        body["draft"] = draft
    return await call(PRODUCT, "POST", "/v1/jsonschema/validate", json=body)


def main() -> None:  # pragma: no cover - stdio entry point
    server.run("stdio")

if __name__ == "__main__":  # pragma: no cover
    main()
