# MCP Configuration Reference

This reference summarizes MCP install payloads, manifest schema fields, and
preview/response data used for MCP security review.

## Install Request (MCPInstallRequest)

```json
{
  "catalog_id": "google-calendar",
  "server_id": "my-mcp",
  "name": "My MCP",
  "description": "Custom MCP integration",
  "transport_type": "stdio",
  "transport_config": {
    "command": ["node", "server.js"],
    "args": [],
    "env": {
      "MY_SECRET": "..."
    }
  },
  "manifest": { ... },
  "credentials": { "MY_SECRET": "..." },
  "oauth": { "provider": "google", "scopes": ["..."] },
  "approved_tools": ["read_data"],
  "confirmed": true,
  "rate_limit": 60
}
```

Key notes:
- `catalog_id` installs from a trusted catalog entry.
- `transport_config.command` is required for `stdio`.
- `transport_config.url` is required for `sse`.
- `credentials` are merged into `transport_config.env` for runtime use.
- `approved_tools` controls which tools are enabled on install.
- `confirmed` gates writes and installation.

## Manifest Schema (MCPManifest)

Required fields:
- `protocolVersion` (string)
- `name` (string)
- `version` (semver string)
- `capabilities` (tools/resources/prompts list)

Minimal example:

```json
{
  "protocolVersion": "2024-11-05",
  "name": "custom-mcp",
  "version": "1.0.0",
  "description": "Custom MCP integration",
  "capabilities": {
    "tools": [
      {
        "name": "read_data",
        "description": "Read data",
        "input_schema": {
          "type": "object",
          "properties": { "id": { "type": "string" } },
          "required": ["id"]
        }
      }
    ],
    "resources": [
      {
        "uri": "file:///data/{id}",
        "name": "Data file",
        "description": "Read-only data file",
        "mime_type": "text/plain"
      }
    ],
    "prompts": [
      {
        "name": "summarize",
        "description": "Summarize a document",
        "arguments": [{ "name": "tone", "type": "string" }]
      }
    ]
  },
  "metadata": {
    "oauth": { "provider": "google", "scopes": ["scope-a"] },
    "required_env": ["MY_SECRET"]
  }
}
```

## Preview & Response Fields

Preview responses include additional data for security review:

- `security_checks`: status list of source verification, manifest validation,
  capability validation, permission scopes, sandbox checks, and issue scan.
- `permission_scopes`: OAuth scopes gathered from catalog + manifest metadata.
- `required_env`: environment keys required by manifest or catalog.
- `resources` / `prompts`: declared non-tool capabilities.
- `missing_credentials`: required env keys still missing.
- `sandbox_issues`: blocked commands, env keys, or non-https SSE URLs.
- `blocked_tools`: tools classified as blocked.

Security check entries use:

```json
{
  "id": "sandbox_validation",
  "label": "Sandbox validation",
  "status": "passed",
  "details": "Sandbox policy checks passed",
  "issues": [],
  "blocking": false
}
```

## Catalog Constraints

Catalog installs are locked to verified sources:
- `server_id`, `transport_type`, and `manifest` cannot be overridden.
- `transport_config` only accepts `env` overrides.
- Use the manual path (no `catalog_id`) for custom commands or manifests.

## Review Mode

If you do not approve all tools, the MCP is installed disabled and must be
enabled manually:

```bash
curl -X PUT http://localhost:8000/api/mcp/servers/my-mcp \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```
