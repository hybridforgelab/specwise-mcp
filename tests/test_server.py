import subprocess

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from specwise_mcp import files
from specwise_mcp import server as specwise

SPEC_V1 = "openapi: 3.0.3\ninfo: {title: t, version: '1'}\npaths: {}\n"
SPEC_V2 = "openapi: 3.0.3\ninfo: {title: t, version: '2'}\npaths: {}\n"


async def test_server_lists_its_tools():
    listed = await specwise.server.list_tools()
    assert {t.name for t in listed} == {"validate_openapi", "diff_openapi", "validate_json_schema"}
    for t in listed:
        assert t.description and t.annotations.read_only_hint is True and t.annotations.open_world_hint is True


async def test_validate_openapi(api, tmp_path):
    await specwise.validate_openapi(spec=SPEC_V1)
    assert api.last.url.path == "/v1/openapi/validate" and api.last_json() == {"spec": SPEC_V1}
    f = tmp_path / "openapi.yaml"
    f.write_text(SPEC_V2)
    await specwise.validate_openapi(spec_path=str(f))
    assert api.last_json() == {"spec": SPEC_V2}
    with pytest.raises(ToolError, match="exactly one of spec or spec_path"):
        await specwise.validate_openapi()


async def test_diff_openapi_text_and_files(api, tmp_path):
    await specwise.diff_openapi(base=SPEC_V1, revision=SPEC_V2)
    assert api.last.url.path == "/v1/openapi/diff" and api.last_json() == {"base": SPEC_V1, "revision": SPEC_V2}
    a, b = tmp_path / "a.yaml", tmp_path / "b.yaml"
    a.write_text(SPEC_V1)
    b.write_text(SPEC_V2)
    await specwise.diff_openapi(base_path=str(a), revision_path=str(b))
    assert api.last_json() == {"base": SPEC_V1, "revision": SPEC_V2}


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args], check=True,
                   capture_output=True)


async def test_diff_against_a_git_ref(api, tmp_path):
    repo = tmp_path / "repo"
    (repo / "api").mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    spec = repo / "api" / "openapi.yaml"
    spec.write_text(SPEC_V1)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "v1")
    spec.write_text(SPEC_V2)  # uncommitted edit
    await specwise.diff_openapi(revision_path=str(spec), base_git_ref="HEAD")
    assert api.last_json() == {"base": SPEC_V1, "revision": SPEC_V2}
    with pytest.raises(ToolError, match="Could not read api/openapi.yaml at 'nope'"):
        await specwise.diff_openapi(revision_path=str(spec), base_git_ref="nope")
    with pytest.raises(ToolError, match="not both"):
        await specwise.diff_openapi(base=SPEC_V1, revision_path=str(spec), base_git_ref="HEAD")
    with pytest.raises(ToolError, match="needs revision_path"):
        await specwise.diff_openapi(revision=SPEC_V2, base_git_ref="HEAD")
    outside = tmp_path / "outside.yaml"
    outside.write_text(SPEC_V2)
    with pytest.raises(ToolError, match="not in a git repository"):
        await specwise.diff_openapi(revision_path=str(outside), base_git_ref="HEAD")


async def test_validate_json_schema(api, tmp_path):
    await specwise.validate_json_schema(schema='{"type": "object"}')
    assert api.last.url.path == "/v1/jsonschema/validate" and api.last_json() == {"schema": '{"type": "object"}'}
    data = tmp_path / "data.json"
    data.write_text('{"a": 1}')
    await specwise.validate_json_schema(schema='{"type": "object"}', instance_path=str(data), draft="7")
    assert api.last_json() == {"schema": '{"type": "object"}', "instance": '{"a": 1}', "instance_format": "yaml",
                               "draft": "7"}
    with pytest.raises(ToolError, match="exactly one of schema or schema_path"):
        await specwise.validate_json_schema()


async def test_json_arguments_through_the_server(api):
    await specwise.server.call_tool("validate_json_schema", {"schema": '{"type": "object"}', "instance": "{}"})
    assert api.last_json() == {"schema": {"type": "object"}, "instance": {}, "instance_format": "value"}
    await specwise.server.call_tool("validate_json_schema", {"schema": "type: object", "instance": "a: 1"})
    assert api.last_json() == {"schema": "type: object", "instance": "a: 1", "instance_format": "yaml"}
    await specwise.server.call_tool("validate_openapi", {"spec": '{"openapi": "3.0.3"}'})
    assert api.last_json() == {"spec": {"openapi": "3.0.3"}}
    await specwise.server.call_tool("diff_openapi", {"base": '{"openapi": "3.0.3"}', "revision": SPEC_V2})
    assert api.last_json() == {"base": {"openapi": "3.0.3"}, "revision": SPEC_V2}
    await specwise.validate_json_schema(schema=True, instance=0)
    assert api.last_json() == {"schema": True, "instance": 0, "instance_format": "value"}


async def test_text_file_limits(tmp_path):
    with pytest.raises(ToolError, match="No such file"):
        files.read_text(str(tmp_path / "missing"), 100)
    big = tmp_path / "big"
    big.write_text("x" * 50)
    with pytest.raises(ToolError, match="limit is"):
        files.read_text(str(big), 10)
    binary = tmp_path / "bin"
    binary.write_bytes(b"\xff\xfe\x00")
    with pytest.raises(ToolError, match="not UTF-8"):
        files.read_text(str(binary), 100)
