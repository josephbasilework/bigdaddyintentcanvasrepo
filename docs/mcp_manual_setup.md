# MCP Manual Setup Guide

This guide documents how to add and configure MCP integrations manually.
Use this when you want full control over MCP configuration or are integrating
custom MCP servers outside the built-in catalog.

## Overview

An MCP integration consists of:

- A **manifest** describing capabilities (tools/resources/prompts).
- A **transport configuration** (stdio or SSE).
- **Credentials/OAuth scopes** required for the server to operate.
- **Security rules** that classify tool risk (allowed / requires_confirm / blocked).

## Manual Install (API)

1. Build a manifest (required fields):

```json
{
  "protocolVersion": "2024-11-05",
  "name": "my-mcp",
  "version": "1.0.0",
  "description": "Custom MCP integration",
  "capabilities": {
    "tools": [
      {
        "name": "read_data",
        "description": "Read data",
        "input_schema": {
          "type": "object",
          "properties": {
            "id": { "type": "string" }
          },
          "required": ["id"]
        }
      }
    ]
  }
}
```

2. Choose a transport:

- **stdio** (local process):
  - Provide `command: [binary, ...args]`
  - Provide `env` for credentials/secrets
- **sse** (remote server):
  - Provide `url` to the SSE endpoint

3. Preview the install:

```bash
curl -X POST http://localhost:8000/api/mcp/install \
  -H "Content-Type: application/json" \
  -d '{
    "server_id": "my-mcp",
    "name": "My MCP",
    "transport_type": "stdio",
    "transport_config": {
      "command": ["node", "server.js"],
      "env": { "MY_SECRET": "..." }
    },
    "manifest": { ... }
  }'
```

The response includes:
- A capability review list
- Security rules applied to each tool
- Any sandbox or credential issues

4. Confirm and enable:

```bash
curl -X POST http://localhost:8000/api/mcp/install \
  -H "Content-Type: application/json" \
  -d '{
    "server_id": "my-mcp",
    "name": "My MCP",
    "transport_type": "stdio",
    "transport_config": { ... },
    "manifest": { ... },
    "approved_tools": ["read_data"],
    "confirmed": true
  }'
```

If you do not approve all tools, the MCP is created in **review mode** and stays disabled
until you explicitly enable it (via `PUT /api/mcp/servers/{server_id}`).

## Catalog Install (UI)

The MCP Setup panel in the UI surfaces catalog entries with:
- Required credential fields
- OAuth scopes
- Capability review

Use **Review install** to generate the preview and **Confirm install** to enable.

## Security & Sandbox Rules

- stdio commands cannot use shell operators (`;`, `&&`, `|`, backticks).
- Executables such as `bash`, `sh`, or `powershell` are blocked.
- Environment keys like `PATH`, `HOME`, and `LD_PRELOAD` are blocked.
- Tools classified as `blocked` stay disabled even after install.

## Manual Enable/Disable

```bash
curl -X PUT http://localhost:8000/api/mcp/servers/my-mcp \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

```bash
curl -X PUT http://localhost:8000/api/mcp/servers/my-mcp \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

## Notes

- Credentials are stored in transport config and are redacted in API responses.
- Use `GET /api/mcp/servers` to audit installed MCPs.
