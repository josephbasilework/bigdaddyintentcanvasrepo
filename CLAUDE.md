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

## Running the Application Locally (WSL2)

### Prerequisites
- WSL2 Ubuntu environment
- Python 3.11+ (venv at `intentuimvp/backend/.venv/`)
- Node.js 20+ (dependencies in `intentuimvp/frontend/node_modules/`)
- Redis server

### Required Environment Variables

Backend `.env` file at `intentuimvp/backend/.env`:
```bash
# Copy from example if not exists
cp intentuimvp/backend/.env.example intentuimvp/backend/.env
```

**Required:**
- `PYDANTIC_GATEWAY_API_KEY` - Pydantic AI Gateway key (MUST be set)

**Has defaults (no action needed):**
- `DATABASE_URL` - defaults to `sqlite:///./intentui.db`
- `CORS_ORIGINS` - must be JSON array format: `["http://localhost:3000","http://localhost:8000"]`

### Services to Run (4 Terminals)

| Terminal | Service | Command | Port |
|----------|---------|---------|------|
| 1 | Redis | `sudo service redis-server start` | 6379 |
| 2 | Backend API | See below | 8000 |
| 3 | ARQ Worker | See below | - |
| 4 | Frontend | See below | 3000 |

**Note:** The backend venv is missing the `activate` script. Use executables directly from `.venv/bin/`.

### Startup Commands

**Terminal 1 - Redis (start once, runs as service):**
```bash
sudo service redis-server start
redis-cli ping  # Should return PONG
```

**Terminal 2 - Backend API:**
```bash
cd ~/bigdaddyintentcanvasrepo/intentuimvp/backend
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 3 - ARQ Worker (processes background jobs):**
```bash
cd ~/bigdaddyintentcanvasrepo/intentuimvp/backend
.venv/bin/arq app.jobs.worker.WorkerSettings
```

**Terminal 4 - Frontend:**
```bash
cd ~/bigdaddyintentcanvasrepo/intentuimvp/frontend
npm run dev
```

### Accessing the Application

- **Frontend UI:** http://localhost:3000
- **Backend API docs:** http://localhost:8000/docs
- **Health check:** `curl http://localhost:8000/`

### Troubleshooting

**"Failed to fetch" in browser:**
- Backend isn't running. Check Terminal 2 for errors.

**"ModuleNotFoundError: No module named 'aiosqlite'":**
```bash
cd ~/bigdaddyintentcanvasrepo/intentuimvp/backend
.venv/bin/pip install aiosqlite
```

**CORS_ORIGINS parse error:**
- Ensure it's JSON array format: `["http://localhost:3000","http://localhost:8000"]`

**Alembic migrations (if needed):**
```bash
cd ~/bigdaddyintentcanvasrepo/intentuimvp/backend
DATABASE_URL=sqlite:///./intentui.db .venv/bin/alembic upgrade head
```

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
