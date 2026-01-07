# IntentUI MVP - Claude Code Context

## Project Overview

IntentUI is a **canvas-based agentic workspace** that breaks from chatbot paradigms. Core differentiators:
- **Stateful spatial canvas** with nodes, documents, audio blocks, and visual graphs persisted across sessions
- **Command-driven interaction** via floating text input with context routing to specialized agents
- **Intent deciphering** with assumption reconciliation before action execution
- **Gateway-only LLM access** via Pydantic AI Gateway (no direct provider imports)
- **MCP integration** for modular external capabilities (Calendar, etc.)

**Primary source of truth**: `intentuimvp/PRD.md`

## Technical Constraints

| Constraint | Enforcement |
|------------|-------------|
| Gateway-only | All LLM calls through `/backend/app/gateway/client.py`; no direct OpenAI/Anthropic imports |
| Secrets | Environment variables only (`PYDANTIC_GATEWAY_API_KEY`, `XAI_API_KEY`); never hardcode |
| AG-UI Protocol | Agent-UI interactions via AG-UI spec |
| CopilotKit | Copilot-style contextual assistance |

**Expected stack**: Next.js + React (frontend), FastAPI (backend), PostgreSQL + Alembic (persistence), Redis + Celery/ARQ (jobs), WebSockets (real-time).

## Beads (bd) Task Management

This repo uses **Beads** (`bd`) for issue tracking and task orchestration. The `.beads/` directory contains the local SQLite database (`beads.db`) and configuration.

### Core Commands

```bash
bd ready                           # Get next actionable task
bd list --status open              # List all open issues
bd show <id>                       # View issue details
bd create --title "..." --body ... # Create new issue
bd update <id> --status in_progress
bd close <id>                      # Mark complete
bd dep add <blocker> <blocked>     # Add dependency
bd sync                            # Sync with git
```

### Issue Hierarchy

- **Epics (E-00X)**: High-level feature areas
- **Stories (S-00X)**: User-facing capabilities within epics
- **Tasks**: Leaf-level implementation units with acceptance criteria

### Priority Semantics

| Priority | Meaning |
|----------|---------|
| P0 | Unblockers: repo scaffolding, Gateway client, local run, CI |
| P1 | First vertical slice: one agent step, UI integration, minimal persistence |
| P3 | Parking lot: deferred to future phases |

## Session Protocol

See @AGENTS.md for mandatory session completion workflow including:
1. File issues for remaining work
2. Run quality gates
3. Update issue status
4. **Push to remote** (mandatory)
5. Hand off context

## Directory Structure (Target)

```
intentuimvp/
├── frontend/           # Next.js + React
│   └── src/
│       ├── components/ # Canvas, Assumptions, TaskDAG
│       ├── state/      # Zustand stores
│       └── agui/       # AG-UI layer
├── backend/            # FastAPI
│   └── app/
│       ├── gateway/    # GatewayClient (Gateway-only)
│       ├── agents/     # PydanticAI agents
│       ├── context/    # Context router
│       ├── jobs/       # Celery/ARQ workers
│       └── mcp/        # MCP manager
└── PRD.md              # Authoritative requirements
```
