# MCP Troubleshooting Guide

This guide covers common MCP install and runtime issues, along with fixes.

## Install Blocked: Missing Credentials

**Symptom**
- Preview shows `Missing credentials`
- Install response: `Install blocked: Missing credentials: ...`

**Fix**
- Supply the required values in `credentials` (or via the UI).
- Confirm the required keys in the preview `required_env` list.

## Install Blocked: Sandbox Policy Violations

**Symptom**
- Preview shows `sandbox_issues` or sandbox validation failed.

**Fix**
- For `stdio`, use a direct executable command (no shell operators).
- Avoid blocked executables like `bash`, `sh`, or `powershell`.
- Remove blocked env keys (`PATH`, `HOME`, `LD_PRELOAD`, etc.).
- For `sse`, use `https://` URLs (localhost is allowed for development).

## Catalog Overrides Rejected

**Symptom**
- Source verification failed with catalog override warnings.

**Fix**
- Catalog installs only allow `env` overrides.
- For custom commands, URLs, or manifests, omit `catalog_id` and use the
  manual install flow.

## Capability Validation Failed

**Symptom**
- Preview shows failed capability validation (duplicates or empty capabilities).

**Fix**
- Ensure tool names are unique.
- Provide at least one capability (tool/resource/prompt).
- Add descriptions for tools to avoid warnings.

## Tools Blocked in Review

**Symptom**
- Some tools display `blocked` and cannot be approved.

**Fix**
- Rename capabilities to avoid blocked patterns (e.g., `execute`, `shell`).
- Align tool naming with allowed actions (read/query vs write/send).

## MCP Installed in Review Mode

**Symptom**
- Install succeeded but MCP remains disabled.

**Fix**
- Approve all non-blocked tools, then re-run install with `confirmed: true`.
- Or enable manually:

```bash
curl -X PUT http://localhost:8000/api/mcp/servers/my-mcp \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

## Runtime Connection Failures

**Symptom**
- MCP tools fail to execute or server shows as disabled.

**Fix**
- Check `GET /api/mcp/health` for server status.
- Verify the command or SSE endpoint is reachable.
- Review server logs for startup errors.
