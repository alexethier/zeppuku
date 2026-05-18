# aethier-mcp-lib

Shared Python helpers for MCP servers under `mcp/`.

Current modules:
- `csvq_adapter` — generic csvq-over-host-bridge adapter.

This package is intentionally generic. MCP-specific query helpers should live
in each MCP package (for example, repository/service files under that MCP).
