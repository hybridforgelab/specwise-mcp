# hybridforgelab-specwise-mcp: moved to bytestay-specwise-mcp

This package has moved to **[bytestay-specwise-mcp](https://pypi.org/project/bytestay-specwise-mcp/)**. Hybrid Forge Lab is now ByteStay.

This last version only installs bytestay-specwise-mcp and forwards to it. It prints a one-line notice on stderr and gets no more updates.

## Switch

Replace `hybridforgelab-specwise-mcp` with `bytestay-specwise-mcp` in your MCP client config:

```json
"command": "uvx",
"args": ["--from", "bytestay-specwise-mcp", "specwise-mcp"]
```

Or with Claude Code:

```bash
claude mcp add specwise --env RAPIDAPI_KEY=your-rapidapi-key -- uvx --from bytestay-specwise-mcp specwise-mcp
```

The environment variables are the same, so your keys keep working.

## Links

- Package: [bytestay-specwise-mcp](https://pypi.org/project/bytestay-specwise-mcp/)
- Source: [Bytestay/specwise-mcp](https://github.com/Bytestay/specwise-mcp)
- Specwise API: [specwise.bytestay.pt](https://specwise.bytestay.pt)
