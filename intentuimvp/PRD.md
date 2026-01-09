# Intent Canvas — Agent-Native Workspace PRD

---

## 0) Document Control

| Field | Value |
|-------|-------|
| **PRD Title** | Intent Canvas — Agent-Native Workspace |
| **Version** | 2.0.0 |
| **Status** | Active (Replaces v1.0.0) |
| **Owner** | Joey Basile |
| **Last Updated** | 2026-01-09 |
| **Audience** | Product, Design, Engineering |
| **Doc Type** | Vision + Engineering Contract (single PRD) |

### Change Summary vs v1.0.0

| Change Type | Description |
|-------------|-------------|
| **Vision Strengthened** | Re-centers product on literal canvas-first UX and vision invariants |
| **Scope Expanded** | Adds multi-judge compute, dashboards, Docs integration path, selection scope |
| **Structure Improved** | Separates Vision Invariants from Engineering Invariants |
| **All v1.0.0 Preserved** | Every FR/NFR/constraint from v1.0.0 is preserved or explicitly mapped |

### Links to Source Documentation

| Resource | Link | Purpose |
|----------|------|---------|
| PydanticAI | https://ai.pydantic.dev/ | Agent framework with structured outputs |
| Pydantic AI Gateway | https://ai.pydantic.dev/ | **GATEWAY-ONLY** - All inference through this API |
| AG-UI Protocol | https://docs.ag-ui.com/introduction | Agent-UI interaction protocol |
| CopilotKit | https://docs.copilotkit.ai/ | Copilot-style in-app assistance |

### Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-01-03 | PRD Generator | Initial draft from brain dump |
| 1.1.0 | 2026-01-03 | Audit Process | Post-audit hardening |
| 2.0.0 | 2026-01-09 | PRD Merge | Vision-forward restructure; full v1.0.0 preservation |

---

## 1) The Mantra

> **Vision bends technology, not vice-versa.**
> If a technology choice conflicts with invariants, replace the technology.

---

## 2) Vision Invariants (Non-Negotiable)

This product exists to replace linear, low-control "chatbot" interaction with an **agent-native, stateful workspace**.

| ID | Invariant | Meaning |
|----|-----------|---------|
| **VI-001** | **Not a chatbot** | Primary surface is a persistent **canvas** with editable artifacts, not a chat thread |
| **VI-002** | **Command/UI driven** | Users interact via command box + direct UI manipulation (CRUD, selection, linking) |
| **VI-003** | **Shared state** | User and agentic system operate on a **shared, observable state graph** |
| **VI-004** | **High throughput** | Multiple parallel jobs, streaming updates, fast context switching |
| **VI-005** | **HITL by design** | System surfaces assumptions and requires explicit reconciliation for ambiguity/side effects |
| **VI-006** | **Modular capability** | Tools/connectors are pluggable (MCP servers, workflows, future agents) |
| **VI-007** | **Canvas-first always** | Every feature must enhance spatial thinking, not regress to linear chat |

---

## 3) Engineering Invariants (Non-Negotiable Technical Constraints)

These constraints are **non-negotiable** and must not be weakened by any feature implementation.

### EI-001: Gateway-Only LLM Access (MUST)

**Constraint**: All PydanticAI inference MUST go through Pydantic AI Gateway API ONLY.

**Enforcement**:
- `GatewayClient` (`/backend/app/gateway/client.py`) is the ONLY module that imports PydanticAI inference
- No direct OpenAI, Anthropic, or other provider SDK imports anywhere in codebase
- All agents MUST inherit from `BaseAgent` and use `self.gateway` for LLM calls

**Validation**: Grep scan for `import.*openai|import.*anthropic|from.*openai|from.*anthropic` must return zero matches.

### EI-002: Secrets Management (MUST)

**Constraint**: All secrets stored in environment variables ONLY; never hardcoded.

| Rule | Implementation |
|------|----------------|
| Environment Variables Only | `.env` file (never committed); code references by name only |
| No Hardcoded Secrets | Linting rules detect and reject hardcoded keys |
| .env.example Pattern | Repository contains `.env.example` with variable names only (no values) |
| Runtime Validation | Application MUST fail to start if `PYDANTIC_GATEWAY_API_KEY` is missing |

**Required Environment Variables**:
- `PYDANTIC_GATEWAY_API_KEY` - Pydantic AI Gateway key (REQUIRED, no default)

**Optional Environment Variables**:
- `XAI_API_KEY` - xAI Grok model integration (passed to Gateway, NOT for direct API calls)
- `DATABASE_URL` - defaults to `sqlite:///./intentui.db`
- `REDIS_URL` - defaults to `redis://localhost:6379`
- `CORS_ORIGINS` - MUST be JSON array format: `["http://localhost:3000","http://localhost:8000"]`

### EI-003: AG-UI Protocol (MUST)

**Constraint**: Agent-UI interactions MUST follow AG-UI specification.

**Current Protocol Version**: 1.0.0

**Implementation**: WebSocket-based AG-UI with JSON message envelopes containing:
- `version`: Protocol version string
- `messageId`: Unique message ID
- `timestamp`: ISO 8601 timestamp
- `source` / `target`: `'agent'` or `'ui'`
- `correlationId`: Optional request/response correlation

### EI-004: CopilotKit Integration (MUST)

**Constraint**: Copilot-style assistance via CopilotKit, used headless (NOT chat-first UI).

**CopilotKit Handles**: Contextual assistance, action suggestions, quick queries (<5s)
**CopilotKit Does NOT Handle**: Executing destructive actions, direct MCP configuration, long-running operations (>10s)

### EI-005: Modular/DDD Architecture (MUST)

**Constraint**: Every module MUST answer Where/What/How/Why explicitly.

**Bounded Contexts**:
- Workspace Context (canvas, nodes, documents)
- Agent Context (orchestration, jobs, workflows)
- Integration Context (MCP, external connections)
- User Context (identity, intent index, sessions)
- Context Routing (classification, routing decisions)

---

## 4) Problem Statement

Current AI interfaces are:
- **Linear, hard to edit** - chatbot threads don't match spatial thinking
- **Stateless** - tools lose context between sessions
- **Low control** - AI makes silent assumptions
- **Fragmented** - users manually orchestrate between assistants, calendars, documents

### User Pain Points (from original brain dump)

| Pain Point | Quote |
|------------|-------|
| Static artifacts | "It's not like ChatGPT where you have a little artifact on the side" |
| Lack of control | "You're not sitting here with this unreliable horseshit with the lack of control" |
| Fragmented workflows | "Branching between chats and having multiple chats open" |
| Context chaos | "Context has to be handled systematically" |
| Speed needs | "We need reliability, high velocity, high throughput" |

---

## 5) Goals, Success Metrics, and Product Tenets

### 5.1 Product Goals (v1)

1. **Canvas-first workspace** that persists across sessions
2. **Command → Assumptions → Execution loop** that is fast, explicit, reliable
3. **Job blocks** that stream progress into the canvas (not just text)
4. **Graphs/Plans/DAGs** that are editable, annotatable structures
5. **Modular integrations** via MCP (start with Calendar; then Docs)
6. **Protocol-backed Agent↔UI contract** (AG-UI) to avoid reinventing streaming/state/tool semantics

### 5.2 Success Metrics (MVP Targets)

| Metric | Definition | Target |
|--------|------------|--------|
| Task Completion Rate | % of user intents successfully executed without failure | > 80% |
| Assumption Accuracy | % of system assumptions user accepts without modification | > 70% |
| Time-to-Value | Time from command to useful output (simple tasks) | < 30 seconds |
| Session Continuity | % of users resuming previous workspace vs. starting fresh | > 60% |
| Research Job Completion | % of deep research jobs completing successfully | > 75% |
| Command vs. Chat Ratio | Ratio of command-driven to chat-driven interactions | > 3:1 |
| MCP Adoption | % of users with at least one MCP configured | > 30% |

### 5.3 Product Tenets

- **Everything becomes an artifact** (nodes/jobs/reports/plans/dashboards)
- **State is the product** — streaming makes progress *felt*
- **Control loops prevent chaos** — assumptions + approvals are core UX
- **Compute is a UI primitive** — multi-judge, research, planners are first-class blocks

---

## 6) Target Users

### Primary Persona: Power User / Knowledge Worker

| Attribute | Description |
|-----------|-------------|
| **Profile** | High-throughput work style, rapid context switching, multiple parallel workstreams |
| **Technical Level** | Comfortable with keyboard shortcuts, command-driven interfaces |
| **Pain Points** | Cognitive overload, fragmented tools, slow AI interfaces |
| **Primary Needs** | Speed, state persistence, spatial organization, reliable AI assistance |
| **Quote** | "I'm juggling 20 different things at once and need my workspace to keep up" |

### Secondary Personas

| Persona | Profile | Primary Needs |
|---------|---------|---------------|
| **Researcher/Analyst** | Deep research, multi-source synthesis | Streaming updates, provenance tracking, multi-perspective critique |
| **Developer (Alpha)** | Building/testing system, configuring MCPs | Dynamic MCP config, debugging visibility, extensibility |

---

## 7) Scope

### 7.1 In-Scope (MVP)

| Category | Capabilities |
|----------|--------------|
| **Workspace** | Canvas-based UI with persistent state, nodes, documents, audio blocks |
| **Interaction** | Command-driven input, floating text box, assumption reconciliation UI |
| **Context** | Context routing, intent deciphering, selection scope, user intent index |
| **Agents** | PydanticAI agents via Gateway, agent orchestration, structured outputs |
| **Jobs** | Deep research jobs with streaming, LLM-as-judge patterns |
| **Visualization** | Node-based spatial layout, edges/connections, task DAG, basic graphs |
| **MCP** | MCP server framework, Google Calendar integration, security validation |
| **Persistence** | Canvas state, user preferences, job artifacts, backup/export |
| **Safety** | Agent guardrails, input sanitization, action blocking, HITL gates |

### 7.2 Out-of-Scope (Explicitly Deferred)

| Feature | Reason | Future Phase |
|---------|--------|--------------|
| Full self-modifying workflows | Complexity; MVP allows MCP addition only | Phase 2 |
| Multi-LLM provider orchestration | Requires multi-model infrastructure | Phase 2 |
| Google Docs integration | Focus on Calendar first | Phase 1.5 |
| Advanced annotatable graphs | Basic visualization sufficient for MVP | Phase 2 |
| Mobile/tablet interfaces | Desktop-first for power users | Phase 3 |
| Multi-user collaboration | Single-user reduces complexity | Phase 2 |
| Offline functionality | Requires significant architectural changes | Phase 3 |
| Custom agent creation | Power user feature | Phase 2 |
| Real-time voice input | AudioBlock transcription included; real-time voice deferred | Phase 2 |

---

## 8) Core Concepts (Product Primitives)

### 8.1 Canvas Entities

| Entity | Description |
|--------|-------------|
| **Workspace** | Persistent container (metadata, preferences, auth context) |
| **Node (typed)** | Note / Doc / Link / Audio+Transcript / Job / Dashboard / Graph / Plan |
| **Edge** | Typed relationship (depends_on, references, supports, conflicts, derived_from, critiques) |
| **Selection Scope** | User's current selected nodes/region; primary context focus primitive |

### 8.2 Jobs as First-Class Blocks

| Job Type | Output |
|----------|--------|
| Deep Research | Streams intermediate artifacts + final report node |
| LLM-as-Judge | Multiple critic outputs + synthesizer output |
| Planner | Structured plan + task DAG + links to sources/nodes |

**Job States**: `queued` → `running` → `paused` | `blocked(approval)` → `done` | `error`

### 8.3 Assumption Reconciliation (HITL)

When intent is ambiguous OR side effects are proposed, system returns an **Assumption Set**:
- Interpretations (acronyms, entity refs, missing required inputs)
- Proposed actions/tool usage
- Confidence + rationale + alternatives

User can: **Approve all** | **Edit** | **Reject** | **Explain**

### 8.4 Context Routing

Inputs (command text, node edits, job outputs, external signals) are routed to:
- Appropriate workflow/agent
- Appropriate tool set
- Focused context window (selection scope + referenced artifacts)

---

## 9) Technical Decisions (Locked for v1)

### 9.1 Canonical Agent↔UI Boundary: AG-UI

AG-UI as the wire contract between UI and agent backend:
- Event-based streaming (not just text)
- Shared-state sync patterns
- Tool calls and structured runs
- HITL and custom events (extensible)

### 9.2 Backend: PydanticAI + AG-UI Adapter

- Accept AG-UI RunAgentInput (messages, state, tools)
- Emit AG-UI events via streaming transport
- Validate shared state via typed Pydantic models at the boundary

### 9.3 Frontend: CopilotKit AG-UI Client (Headless)

Use CopilotKit for AG-UI client plumbing:
- Run management
- Event decoding + ordering
- State sync helpers

**CRITICAL**: We do NOT adopt chat-first UI. We build canvas-first components.

### 9.4 Streaming Transport Policy

| Channel | Transport | Notes |
|---------|-----------|-------|
| Agent↔UI (AG-UI runs) | **WebSocket** (canonical) | SSE allowed as future alternative |
| Job progress streaming | **WebSocket** | Broadcast to all connected clients |
| Background signals | **WebSocket** | Workspace push updates, heartbeats |

**WebSocket Semantic Requirements** (from v1.0.0, MUST preserve):

1. **Heartbeat**: 30-second interval pings (`HEARTBEAT_INTERVAL = 30`)
2. **Reconnection**: Exponential backoff (1s base, max 30s cap, max 10 attempts)
3. **Message Format**: JSON text messages with AG-UI envelope
4. **Ordering**: No guaranteed ordering across clients; UI must be tolerant
5. **Idempotency**: Client must handle duplicate events
6. **No automatic replay**: Client must query REST endpoints after reconnect

**WebSocket State Sync Protocol**:

```json
{
  "type": "state.update",
  "sequence": 12345,
  "timestamp": "2026-01-09T12:00:00Z",
  "patch": [{ "op": "add", "path": "/nodes/abc123", "value": {...} }],
  "checksum": "sha256:abc..."
}
```

**Conflict Resolution**:
1. Server is authoritative
2. Client applies patch only if `sequence = last_sequence + 1`
3. Gap detected → client requests full state sync
4. Optimistic updates: client applies locally, reverts on server rejection

---

## 10) UX Specification (Literal Visual Requirements)

### 10.1 Primary Surfaces

**Canvas**:
- Pan/zoom, infinite-ish space
- Nodes with type badges, titles, timestamps, status
- Edges with relation labels
- Drag/drop, multi-select, region-select

**Command Box (Floating / Dockable)**:
- Always accessible (keyboard shortcut to focus)
- Supports referencing selection scope ("use selected nodes")
- Supports templates: `/research`, `/judge`, `/plan`, `/dashboard`, `/graph`, `/export`
- Supports attaching files / audio capture

**Assumptions Panel**:
- Appears when confidence < auto-execute threshold OR when side effects proposed
- Shows assumptions, confidence, rationale, alternatives
- Approve / edit / reject controls
- "Explain" reveals reasoning + what would change the decision

**Job Blocks**:
- Show state, progress, streaming sub-artifacts
- Allow pause/cancel/retry
- When blocked, clearly show what approval is needed

**Inspector / Details Panel**:
- Shows selected node metadata, provenance, linked nodes, history
- Shows audit trail for tool calls + approvals

### 10.2 Golden Flows (Must Feel Amazing)

1. **Random thought capture** → node created instantly → optional analysis job spawned
2. **Deep research** → job streams sources/findings → report node appears → user rearranges
3. **Judge this** → multiple critic nodes + synthesis node appear linked to target
4. **Make a plan** → plan node + DAG node appear; tasks can sync to Calendar (with approval)
5. **Turn this into a dashboard** → dashboard node subscribes to state/tool outputs; updates live

---

## 11) Functional Requirements

### FR-001: Workspace Initialization & Restore

**Description**: System shall render a canvas-based workspace on load with persistent state.

**Inputs**: User session, previous canvas state (if any)
**Outputs**: Rendered canvas with restored nodes, documents, audio blocks

**Acceptance Criteria**:
- Given a user accesses the workspace URL, When the page loads, Then a canvas renders within **2 seconds** with floating text input visible
- Given the user has previous state, When the canvas loads, Then all previous nodes, documents, and positions are restored
- Given no API keys in client-side code, When source is inspected, Then no secrets are visible

**Edge Cases**: First-time user (blank canvas), corrupted state (fallback to blank), large canvas (virtualization)
**Error States**: State load failure → show error, offer blank canvas; Auth failure → redirect to login

---

### FR-002: Canvas Node CRUD

**Description**: System shall support create, read, update, delete operations on canvas nodes.

**Acceptance Criteria**:
- Given user creates a node, When rendered, Then it appears at specified position with editable label
- Given a node exists, When dragged, Then position updates in real-time and persists
- Given a node is selected, When context menu invoked, Then edit/delete/connect actions available
- Delete REQUIRES confirmation if it would remove many linked artifacts (**HITL Gate**)

---

### FR-003: Edge Creation & Relationship Semantics

**Description**: System shall support typed edges between nodes with visible, editable labels.

**Supported Edge Types**: `depends_on`, `references`, `supports`, `conflicts`, `derived_from`, `critiques`

**Acceptance Criteria**:
- Given two nodes exist, When user creates edge, Then edge persists with type and label
- Given edges exist, When queried, Then relationships drive context routing and provenance

---

### FR-004: Selection Scope as Context Primitive

**Description**: User can select nodes/region; selection scope is sent with runs and used by context router.

**Acceptance Criteria**:
- Given user selects nodes, When command submitted, Then selection scope is included in RunAgentInput
- Given command references "selected nodes", When processed, Then only selected nodes are in context

---

### FR-005: Command Box Submission + Templates

**Description**: System shall provide a floating text input box for context/command injection with slash templates.

**Supported Templates**: `/research`, `/judge`, `/plan`, `/dashboard`, `/graph`, `/export`

**Acceptance Criteria**:
- Given the canvas is loaded, When the user views the workspace, Then a floating text input is visible and focused
- Given the user types and presses Enter, When input is submitted, Then it is sent to the context routing pipeline within **500ms**
- Given the user uses `/research`, When submitted, Then a research job is spawned
- Given the user drags files, When dropped on text box, Then files are attached to context payload

---

### FR-006: Context Routing Pipeline

**Description**: System shall route incoming context to appropriate agents/workflows based on type and intent.

**Routing Algorithm**:
1. **Priority 1**: Exact command matching (slash commands like `/research`, `/calendar`)
2. **Priority 2**: Intent classification via LLM structured output (Gateway)
3. **Priority 3**: Keyword fallback (regex patterns for common phrases)

**When multiple handlers match**:
- Highest priority strategy wins
- If same priority, highest-confidence match wins
- If tie, prompt user for disambiguation

**Timeout**: 500ms for classification; fallback to keyword after timeout
**Circuit Breaker**: 3 consecutive failures → route to fallback handler for 30 seconds

**Acceptance Criteria**:
- Given context is submitted, When router receives it, Then it dispatches to appropriate handler within **500ms**
- Given context has multiple intents, When decomposition occurs, Then each intent is routed independently
- Given no handler matches, When routing fails, Then user is asked for clarification

---

### FR-007: Intent Deciphering + Assumption Generation

**Description**: System shall decipher user intent and generate structured assumptions for confirmation.

**Confidence Thresholds** (Configurable):

| Threshold | Value | Behavior |
|-----------|-------|----------|
| CONFIDENCE_AUTO_EXECUTE | >= 0.95 | Execute without confirmation |
| CONFIDENCE_SHOW_ASSUMPTIONS | 0.70 - 0.94 | Show assumptions panel for confirmation |
| CONFIDENCE_REQUEST_CLARIFICATION | < 0.70 | Request user to clarify input |

**Confidence Calculation**:
- Base: LLM structured output confidence from Gateway
- +0.1 if matching pattern exists in intent index with same resolution
- -0.1 if conflicting patterns exist in intent index
- Capped at 1.0, floored at 0.0

**Acceptance Criteria**:
- Given raw user input, When processed by deciphering agent, Then structured assumptions are produced with confidence scores
- Given available tools, When assumptions are made, Then they reference only feasible actions
- Given confidence >= 0.95, When assumption generated, Then action auto-executes without UI pause

---

### FR-008: Assumption Reconciliation UI (HITL Core)

**Description**: System shall display assumptions and allow user to confirm, reject, or modify.

**Acceptance Criteria**:
- Given assumptions are generated, When rendered, Then each shows intent, confidence, and Confirm/Reject/Edit buttons
- Given user approves assumption, When clicking Confirm, Then associated action is dispatched
- Given user rejects assumption, When clicking Reject, Then assumption is discarded and optional feedback captured
- Approved/rejected assumptions are stored for future reference (learning)

---

### FR-009: AG-UI Run Lifecycle (Canonical Contract)

**Description**: FE sends RunAgentInput (minimal messages + shared state snapshot + tools). BE streams AG-UI events.

**AG-UI Events (Server → Client)**:
- `run.start`, `run.end`
- `tool.call`, `tool.result`
- `state.snapshot`, `state.delta`
- `progress`

**Acceptance Criteria**:
- Given RunAgentInput submitted, When backend processes, Then AG-UI events stream to client
- Event ordering is correct; state updates are idempotent; reconnect can resume via REST query

---

### FR-010: "Canvas Actions" as Tools (Minimum v1 Toolset)

**Description**: Agents can only mutate workspace via these tools (no hidden state mutation).

| Tool | Purpose |
|------|---------|
| `canvas.create_node(type, content, position, metadata)` | Create new node |
| `canvas.update_node(node_id, patch)` | Update existing node |
| `canvas.link_nodes(from_id, to_id, relation_type, metadata)` | Create edge |
| `canvas.spawn_job(job_type, input_refs, params)` | Spawn async job → returns job_id |
| `hitl.request_approval(assumption_set)` | Blocks until user resolves |
| `workspace.search(query, scope)` | Search within workspace (optional early) |

---

### FR-011: Deep Research Job Dispatch + Streaming

**Description**: System shall dispatch deep research jobs that run asynchronously with streaming updates.

**Acceptance Criteria**:
- Given a research query is submitted, When job is created, Then research agent is invoked via Gateway
- Given research is in progress, When sources are found, Then intermediate results stream to UI at least every **10 seconds** during active phases
- Given research completes, When report is generated, Then it is stored as referenceable artifact and linked on canvas

---

### FR-012: Multi-Judge Compute (LLM-as-Judge) + Synthesis

**Description**: System shall support LLM-as-judge patterns for multi-perspective analysis.

**MVP Implementation** (single LLM model via Gateway):
- Configurable perspective count: 1-3 perspectives
- Run perspectives sequentially (single model)
- Timeout per perspective: 30 seconds
- If perspective fails: proceed with available perspectives, note in output

**Default Perspectives** (for research reports):
1. **skeptic** - Challenges claims, looks for weak evidence
2. **advocate** - Steelmans the argument, finds supporting evidence
3. **synthesizer** - Identifies common ground and key tensions

**v2.0 Expansion (Vision)**: Produces ≥3 critic nodes + 1 synthesis node linked to target artifact. User can re-run with more compute (more critics / deeper passes).

**Acceptance Criteria**:
- Given content to analyze, When LLM-as-judge invoked, Then multiple perspective agents are called
- Given perspectives generated, When synthesis occurs, Then combined analysis with agreements/disagreements produced
- Given analysis completes, When stored, Then both individual perspectives and synthesis are accessible

---

### FR-013: Planner Job → Plan Node + Task DAG Node

**Description**: Planner generates structured plan, tasks, dependencies as DAG.

**Acceptance Criteria**:
- Given planning request, When planner completes, Then plan node + DAG node created
- DAG is editable/annotatable; tasks are linkable to calendar events
- Edits propagate to derived artifacts (e.g., calendar suggestions)

---

### FR-014: Graph/Plan/DAG Editing & Annotation

**Description**: Graph nodes support bullet annotations, tags, status, dependency relations.

**Acceptance Criteria**:
- Given graph exists, When user edits node, Then changes persist
- Given dependencies change, When validated, Then DAG remains acyclic (cycle detection via topological sort)

---

### FR-015: Dashboards (Live State Visualization)

**Description**: Dashboard node subscribes to workspace state + tool outputs; updates live without becoming chat logs.

**Acceptance Criteria**:
- Given dashboard created, When state changes, Then dashboard refreshes deterministically
- Dashboard does not corrupt workspace state or become a scrolling log

---

### FR-016: Audio Blocks + Transcription

**Description**: Users can create audio blocks and generate transcripts as artifacts.

**Acceptance Criteria**:
- Given user creates audio block, When they record audio, Then recording is captured and stored
- Given audio block has recording, When transcription triggered, Then transcript generated and stored
- Transcript becomes searchable and usable as context for jobs

---

### FR-017: Persistence (Workspace Graph + Runs + Jobs + Decisions)

**Description**: System shall persist all state across sessions.

**What is Persisted**:
- Workspace nodes/edges/layout
- Job history + outputs
- Assumption sets + decisions
- Run/event logs for debugging/replay

**Acceptance Criteria**:
- Given canvas has state, When save triggered, Then full state is persisted
- Given user returns to workspace, When canvas loads, Then previous state is restored
- Given state is large, When saved, Then incremental/diff-based saving minimizes overhead

---

### FR-018: External Side Effects Safety Gates (HITL Required)

**Description**: Any action that mutates external systems, deletes workspace data, or changes integrations MUST:
1. Show preview/diff
2. Require explicit approval
3. Log audit record

**Acceptance Criteria**:
- Given agent proposes external write, When evaluated, Then action blocked until user confirms
- Given confirmation received, When action executes, Then audit log entry created

---

### FR-019: MCP Integration Framework (Discoverable, Guardrailed)

**Description**: System shall support Model Context Protocol servers for modular external integrations.

**Manifest Requirements**:
- MUST declare all capabilities upfront (tools, resources, prompts)
- MUST include version field (semver format)
- MUST NOT request blocked capabilities

**Capability Classification**:

| Category | ALLOWED | REQUIRES_CONFIRM | BLOCKED |
|----------|---------|------------------|---------|
| Calendar | read | write, delete | - |
| Document | read | write | delete_external |
| File | - | read_scoped | write, execute |
| Network | internal_api | - | raw_socket |
| System | - | - | shell_execute |

**Pass/Fail Criteria**:
- PASS: All requirements met, no blocked capabilities
- FAIL: Any blocked capability, missing required fields
- WARN: Unknown capabilities (log but allow with user approval)

**Runtime Monitoring**:
- Tool calls logged with timestamp, input hash, output size
- Rate limit: **100 tool calls per minute per MCP**
- Anomaly detection: alert if >10x normal call volume

**Acceptance Criteria**:
- Given MCP server is configured, When client connects, Then available tools are discovered
- Given a tool is invoked, When parameters provided, Then tool executes and returns results
- Given MCP connection fails, When error occurs, Then graceful degradation and user notification

---

### FR-020: Google Calendar MCP Integration

**Description**: System shall integrate with Google Calendar via MCP for event reading and creation.

**Acceptance Criteria**:
- Given Google Calendar MCP is configured, When queried, Then events are retrieved
- Given user requests calendar update, When processed, Then calendar is modified via MCP (REQUIRES_CONFIRM)
- Given task DAG exists, When synced to calendar, Then tasks appear as calendar events (with approval)

---

### FR-021: Docs Integration (MCP v1.5 / v1 if feasible)

**Description**: Generate structured docs from artifacts; sync updates with diff preview + HITL approval.

**Acceptance Criteria**:
- Given plan node exists, When export triggered, Then doc is created with preview
- Given doc exists, When artifact changes, Then update suggestion shown with diff (approval required)

---

### FR-022: Observability + Auditability

**Description**: System shall log all significant events for debugging and compliance.

**What is Logged**:
- Tool calls, approvals, job state transitions
- Run IDs, correlation IDs, error traces
- Sensitive data is redacted

**Acceptance Criteria**:
- Given any tool call, When executed, Then log entry created with timestamp and context
- Given error occurs, When logged, Then correlation ID enables trace reconstruction
- Given log inspected, When secrets searched, Then no secrets present

---

## 12) Non-Functional Requirements

### 12.1 Performance Targets (NFR-PERF)

| ID | Metric | Target |
|----|--------|--------|
| NFR-PERF-001 | Canvas initial load | < 2 seconds |
| NFR-PERF-002 | State update propagation | < 100ms |
| NFR-PERF-003 | Intent deciphering | < 5 seconds |
| NFR-PERF-004 | Simple command execution | < 30 seconds |
| NFR-PERF-005 | WebSocket reconnection | < 5 seconds |
| NFR-PERF-006 | Canvas with 100 nodes | Smooth pan/zoom (60fps) |

### 12.2 Reliability/Availability (NFR-REL)

| ID | Aspect | Expectation |
|----|--------|-------------|
| NFR-REL-001 | Gateway dependency | Retry with exponential backoff; graceful degradation if unavailable |
| NFR-REL-002 | WebSocket | Automatic reconnection with queued events |
| NFR-REL-003 | State persistence | Debounced auto-save; no data loss on normal close |
| NFR-REL-004 | Job system | Jobs recoverable after restart; idempotent operations |

### 12.3 Security (NFR-SEC)

| ID | Requirement | Implementation |
|----|-------------|----------------|
| NFR-SEC-001 | Environment Variables Only | All API keys in `.env`, code references by name only |
| NFR-SEC-002 | No Hardcoded Secrets | Linting + pre-commit hooks scan for secrets |
| NFR-SEC-003 | .env.example Pattern | Repository contains variable names only |
| NFR-SEC-004 | Runtime Validation | App fails to start if required env vars missing |
| NFR-SEC-005 | Gateway-Only Enforcement | GatewayClient is ONLY LLM inference module |

### 12.4 Privacy (NFR-PRIV)

| ID | Aspect | Approach |
|----|--------|----------|
| NFR-PRIV-001 | User Intent Index | Stored locally per user; not transmitted beyond LLM inference |
| NFR-PRIV-002 | Canvas Content | User-controlled; no automatic sharing |
| NFR-PRIV-003 | LLM Prompts | May contain user data; transmitted to Gateway; users informed |
| NFR-PRIV-004 | Logging | Structured logging excludes secrets, PII where possible |

### 12.5 Observability (NFR-OBS)

| ID | Component | Observability |
|----|-----------|---------------|
| NFR-OBS-001 | API endpoints | Request/response logging (no secrets) |
| NFR-OBS-002 | Agent invocations | Latency, success/failure metrics |
| NFR-OBS-003 | Job system | Job lifecycle events, duration, outcomes |
| NFR-OBS-004 | WebSocket | Connection events, message counts |
| NFR-OBS-005 | Errors | Structured error logging with correlation IDs |

### 12.6 Accessibility (NFR-A11Y)

| ID | Requirement | Implementation |
|----|-------------|----------------|
| NFR-A11Y-001 | Keyboard navigation | All primary actions accessible via keyboard |
| NFR-A11Y-002 | Screen reader | Semantic HTML, ARIA labels on canvas elements |
| NFR-A11Y-003 | Color contrast | Meet WCAG 2.1 AA standards |
| NFR-A11Y-004 | Focus management | Visible focus indicators |

### 12.7 Maintainability (NFR-MAINT)

| ID | Principle | Implementation |
|----|-----------|----------------|
| NFR-MAINT-001 | Domain-Driven Design | Bounded contexts with clear boundaries |
| NFR-MAINT-002 | Where/What/How/Why | Every module documented with explicit rationale |
| NFR-MAINT-003 | Modular Architecture | Loosely coupled services, clear interfaces |
| NFR-MAINT-004 | Test Coverage | Unit tests for core logic, integration tests for flows |

---

## 13) Agent Safety + Guardrails

### 13.1 Action Classification Matrix

| Domain | Safe (No Confirm) | Needs Confirm | Blocked |
|--------|-------------------|---------------|---------|
| Canvas | create_node, update_label, move | delete_node, clear_canvas | - |
| Documents | create, update | delete | - |
| Jobs | create, query | cancel | delete_history |
| MCP | query_* | write_*, send_* | configure_global |
| External | - | calendar_create, email_draft | email_send_bulk |

### 13.2 Novel Action Handling

For actions not in the matrix:
1. Extract action verb and target from tool call
2. If verb in `[delete, remove, clear, send, upload]` → Needs Confirm
3. If target in `[system, config, external]` → Needs Confirm
4. Default: Safe

### 13.3 Prompting Rules

1. System prompts MUST include explicit constraints on allowed actions
2. No external URLs in agent outputs UNLESS from trusted sources
3. No code execution WITHOUT user approval
4. Factual claims SHOULD cite sources where possible

### 13.4 Data Redaction Rules

1. **PII Detection**: WARN user before sending potentially sensitive info to Gateway
2. **Secrets Scanning**: NEVER log or persist API keys, passwords
3. **User Data**: REDACT from logs, ANONYMIZE in metrics

### 13.5 Logging Rules

1. No secrets in logs (validated by linting)
2. Correlation IDs for request tracing (REQUIRED)
3. Structured JSON format for parsing (REQUIRED)
4. Log levels: DEBUG for dev, INFO for prod

---

## 14) Domain Invariants & Business Rules

| ID | Invariant | Enforcement |
|----|-----------|-------------|
| CI-001 | Node position must be unique within Canvas | CanvasAggregate validates position |
| CI-002 | Node's linkedDocumentId must reference Document in same Canvas | Aggregate validation |
| SI-001 | Assumption must be resolved before executing dependent actions | Agent Context checks |
| JI-001 | Only one deep_research Job per topic simultaneously | JobService checks duplicates |
| JI-002 | Job cannot transition from completed/failed to running | State machine validation |
| MI-001 | MCPServer must pass security validation before activation | MCPServerAggregate |
| TI-001 | TaskDAG must be acyclic (validation on dependency addition) | Topological sort check |
| TI-002 | CalendarSync requires active MCP connection | MCPManager validation |

---

## 15) Data Storage

### 15.1 What Data is Stored

| Data Type | Fields | Purpose |
|-----------|--------|---------|
| **Canvas State** | id, userId, name, nodes[], documents[], audioBlocks[], positions | Persist workspace across sessions |
| **Node** | id, canvasId, type, label, position, linkedIds, metadata | Individual canvas elements |
| **Document** | id, canvasId, title, content, contentType, version | Text/markdown content |
| **AudioBlock** | id, canvasId, audioUri, transcription, duration, status | Voice notes with transcripts |
| **Job** | id, type, status, input, result, progress, createdAt, completedAt | Async task tracking |
| **Artifact** | id, jobId, type, content, metadata | Job outputs (research reports) |
| **Assumption** | id, sessionId, text, confidence, status, resolution | Intent reconciliation |
| **IntentIndex** | id, userId, patterns[], definitions[], preferences | Learning user patterns |
| **MCPConfig** | id, userId, serverId, config, status | MCP server configurations |

### 15.2 Intent Index Implementation

**Storage**: PostgreSQL with pgvector extension
**Embedding Model**: sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)

**Schema**:
- `id`: UUID
- `user_id`: UUID (foreign key)
- `intent_text`: TEXT (original input)
- `embedding`: VECTOR(384)
- `resolution`: JSONB (approved assumptions, actions taken)
- `outcome`: ENUM('success', 'failure', 'modified')
- `created_at`: TIMESTAMP

**Query Algorithm**:
1. Embed incoming input with same model
2. Cosine similarity: `SELECT * WHERE 1 - (embedding <=> query) > 0.7`
3. Rank by `similarity * recency_weight` (decay: 0.99^days_old)
4. Return top 5 matches

**Update Strategy**:
- Insert on assumption approval
- Update outcome on action completion
- Prune entries older than 90 days with outcome='failure'

### 15.3 Data Retention Rules

| Data Type | Retention |
|-----------|-----------|
| Canvas State | Indefinite (user-owned) |
| Jobs | 90 days after completion |
| Artifacts | Indefinite (user can delete) |
| Sessions | 30 days inactive |
| Audit Logs | 1 year |

---

## 16) Milestones (Convergent Path with Exit Criteria)

### Milestone A — "AG-UI substrate + first loop"

**Deliverables**:
- CopilotKit AG-UI client wired to PydanticAI AG-UI adapter
- Minimal shared state model: workspace id, selection scope, minimal nodes
- Assumptions panel + HITL loop
- Tools: create_node, update_node

**Exit Criteria**: command → assumptions → approve → node changes streamed and persisted

### Milestone B — "Job blocks + deep research streaming"

**Deliverables**:
- spawn_job + research job runtime
- Job block UI w/ progress events + final report node

**Exit Criteria**: deep research runs async and streams; report persists and links

### Milestone C — "Multi-judge compute + synthesis"

**Deliverables**:
- Judge job type produces critic nodes + synthesis node
- UI supports rerun with more compute and parameter tuning

**Exit Criteria**: judge flow works reliably and is stored as first-class artifacts

### Milestone D — "Planner + DAG + Calendar sync"

**Deliverables**:
- Planner creates plan + DAG artifacts
- Calendar MCP integrated; proposals require approval

**Exit Criteria**: plan → DAG → calendar suggestions end-to-end with HITL

### Milestone E — "Dashboards + Docs export"

**Deliverables**:
- Dashboard node subscribes to state/tool outputs
- Docs export + diff-based update approvals

**Exit Criteria**: dashboards feel "live"; docs export is stable and safe

---

## 17) Risks & Mitigations

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Gateway Beta Reliability | Medium | High | Retry logic, graceful degradation, fallback messaging |
| State Complexity | High | High | Single-user MVP, robust state machine, incremental persistence |
| MCP Integration Brittleness | Medium | Medium | Security validation, graceful degradation, retry logic |
| Context Routing Accuracy | Medium | High | Confidence thresholds, fallback to user disambiguation |
| Real-time Performance | Medium | Medium | Canvas virtualization, pagination, performance budgets |
| Chat Gravity | High | High | Enforce headless CopilotKit usage; no chat-first UI components |

### Security Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Secret Exposure | Low | Critical | Environment variables only, secret scanning, no hardcoding |
| Agent Hallucination | Medium | High | Safety guardrails, action blocking, confirmation for destructive actions |
| MCP Vulnerabilities | Medium | Medium | Security validation, allowlist pattern, capability scoping |
| Prompt Injection | Medium | Medium | Input sanitization (PromptInjectionDetector), structured outputs, action constraints |

---

## 18) CI Expectations

| Check | Tool | Pass Criteria |
|-------|------|---------------|
| Lint (Python) | Ruff | No errors |
| Lint (JS/TS) | ESLint | No errors |
| Type Check (Python) | Pyright | No errors |
| Type Check (JS/TS) | TypeScript | No errors |
| Unit Tests (Python) | Pytest | 100% pass |
| Unit Tests (JS/TS) | Vitest | 100% pass |
| Secret Scanning | gitleaks | No secrets detected |
| Gateway Import Check | grep | No direct provider imports |

---

## Appendix A: Old→New Mapping

This appendix maps every requirement from PRD v1.0.0 to its location in v2.0.0.

### Functional Requirements Mapping

| v1.0.0 ID | v1.0.0 Title | v2.0.0 ID | v2.0.0 Location | Status |
|-----------|--------------|-----------|-----------------|--------|
| FR-001 | Canvas Workspace Initialization | FR-001 | §11 FR-001 | Preserved verbatim |
| FR-002 | Floating Text Input for Context Injection | FR-005 | §11 FR-005 | Preserved, merged with templates |
| FR-003 | Context Routing Pipeline | FR-006 | §11 FR-006 | Preserved verbatim (algorithm intact) |
| FR-004 | Intent Deciphering with Assumption Generation | FR-007 | §11 FR-007 | Preserved verbatim (thresholds intact) |
| FR-005 | Assumption Reconciliation UI | FR-008 | §11 FR-008 | Preserved verbatim |
| FR-006 | Canvas Node CRUD Operations | FR-002 | §11 FR-002 | Preserved verbatim |
| FR-007 | Deep Research Job Dispatch | FR-011 | §11 FR-011 | Preserved, streaming interval added |
| FR-008 | WebSocket Real-time Streaming | §9.4 | §9.4 Transport Policy | Preserved, protocol details in §9.4 |
| FR-009 | MCP Server Integration | FR-019 | §11 FR-019 | Preserved verbatim (classification table intact) |
| FR-010 | Google Calendar MCP Integration | FR-020 | §11 FR-020 | Preserved verbatim |
| FR-011 | LLM-as-Judge Analysis Pattern | FR-012 | §11 FR-012 | Preserved, MVP constraints intact |
| FR-012 | User Intent/Meaning Index | §15.2 | §15.2 Intent Index Implementation | Preserved verbatim |
| FR-013 | Audio Block Transcription | FR-016 | §11 FR-016 | Preserved verbatim |
| FR-014 | Canvas State Persistence | FR-017 | §11 FR-017 | Preserved verbatim |
| FR-015 | Agent Safety Guardrails | §13 | §13 Agent Safety + Guardrails | Preserved, expanded (§13.1-13.5) |

### Non-Functional Requirements Mapping

| v1.0.0 Section | v1.0.0 Title | v2.0.0 Section | Status |
|----------------|--------------|----------------|--------|
| 6.1 | Security & Secrets Management | §12.3 NFR-SEC, §3 EI-002 | Preserved verbatim, elevated to Engineering Invariant |
| 6.2 | Performance Targets | §12.1 NFR-PERF | Preserved verbatim (all targets intact) |
| 6.3 | Reliability/Availability | §12.2 NFR-REL | Preserved verbatim |
| 6.4 | Privacy Considerations | §12.4 NFR-PRIV | Preserved verbatim |
| 6.5 | Observability | §12.5 NFR-OBS | Preserved verbatim |
| 6.6 | Accessibility | §12.6 NFR-A11Y | Preserved verbatim |
| 6.7 | Maintainability + Modularity | §12.7 NFR-MAINT | Preserved verbatim |

### Constraint Mapping

| v1.0.0 Constraint | v2.0.0 Location | Status |
|-------------------|-----------------|--------|
| Gateway-Only | §3 EI-001 | Preserved, elevated to Engineering Invariant |
| AG-UI Protocol | §3 EI-003 | Preserved, elevated to Engineering Invariant |
| CopilotKit Integration | §3 EI-004 | Preserved, elevated to Engineering Invariant |
| No Secrets in Code | §3 EI-002 | Preserved, elevated to Engineering Invariant |
| Modular/DDD Architecture | §3 EI-005 | Preserved, elevated to Engineering Invariant |

### Domain Invariants Mapping

| v1.0.0 ID | v2.0.0 Location | Status |
|-----------|-----------------|--------|
| CI-001 | §14 | Preserved verbatim |
| CI-002 | §14 | Preserved verbatim |
| SI-001 | §14 | Preserved verbatim |
| JI-001 | §14 | Preserved verbatim |
| JI-002 | §14 | Preserved verbatim |
| MI-001 | §14 | Preserved verbatim |
| TI-001 | §14 | Preserved verbatim |
| TI-002 | §14 | Preserved verbatim |

---

## Appendix B: Lossless Requirements Inventory

This inventory confirms every v1.0.0 requirement is accounted for.

### Functional Requirements

| v1.0.0 ID | Requirement | Status | New Location | Rationale |
|-----------|-------------|--------|--------------|-----------|
| FR-001 | Canvas Workspace Initialization | Preserved verbatim | FR-001 | Core functionality |
| FR-002 | Floating Text Input | Preserved but rewritten | FR-005 | Merged with slash templates |
| FR-003 | Context Routing Pipeline | Preserved verbatim | FR-006 | Algorithm preserved exactly |
| FR-004 | Intent Deciphering | Preserved verbatim | FR-007 | Confidence thresholds preserved |
| FR-005 | Assumption Reconciliation UI | Preserved verbatim | FR-008 | HITL core |
| FR-006 | Canvas Node CRUD | Preserved verbatim | FR-002 | Core functionality |
| FR-007 | Deep Research Job | Preserved verbatim | FR-011 | Streaming added |
| FR-008 | WebSocket Streaming | Preserved verbatim | §9.4 | Protocol section |
| FR-009 | MCP Integration | Preserved verbatim | FR-019 | Classification table preserved |
| FR-010 | Calendar MCP | Preserved verbatim | FR-020 | MCP integration |
| FR-011 | LLM-as-Judge | Preserved verbatim | FR-012 | MVP constraints intact |
| FR-012 | Intent Index | Preserved verbatim | §15.2 | Implementation section |
| FR-013 | Audio Transcription | Preserved verbatim | FR-016 | Core functionality |
| FR-014 | Canvas Persistence | Preserved verbatim | FR-017 | Core functionality |
| FR-015 | Safety Guardrails | Preserved verbatim | §13 | Expanded to full section |

### Non-Functional Requirements

| v1.0.0 ID | Requirement | Status | New Location |
|-----------|-------------|--------|--------------|
| NFR-SEC-001 | Env Vars Only | Preserved verbatim | §12.3, §3 EI-002 |
| NFR-SEC-002 | No Hardcoded Secrets | Preserved verbatim | §12.3, §3 EI-002 |
| NFR-SEC-003 | .env.example | Preserved verbatim | §12.3 |
| NFR-SEC-004 | Runtime Validation | Preserved verbatim | §12.3, §3 EI-002 |
| NFR-SEC-005 | Gateway-Only | Preserved verbatim | §12.3, §3 EI-001 |
| NFR-PERF-001 | Canvas load < 2s | Preserved verbatim | §12.1 |
| NFR-PERF-002 | State update < 100ms | Preserved verbatim | §12.1 |
| NFR-PERF-003 | Intent decipher < 5s | Preserved verbatim | §12.1 |
| NFR-PERF-004 | Command exec < 30s | Preserved verbatim | §12.1 |
| NFR-PERF-005 | WS reconnect < 5s | Preserved verbatim | §12.1 |
| NFR-PERF-006 | 100 nodes 60fps | Preserved verbatim | §12.1 |
| NFR-REL-001 | Gateway retry | Preserved verbatim | §12.2 |
| NFR-REL-002 | WS reconnection | Preserved verbatim | §12.2 |
| NFR-REL-003 | Debounced auto-save | Preserved verbatim | §12.2 |
| NFR-REL-004 | Job recovery | Preserved verbatim | §12.2 |
| NFR-PRIV-001 | Intent Index local | Preserved verbatim | §12.4 |
| NFR-PRIV-002 | Canvas user-controlled | Preserved verbatim | §12.4 |
| NFR-PRIV-003 | LLM prompts disclosure | Preserved verbatim | §12.4 |
| NFR-PRIV-004 | Logging excludes secrets | Preserved verbatim | §12.4 |
| NFR-OBS-001 | API logging | Preserved verbatim | §12.5 |
| NFR-OBS-002 | Agent metrics | Preserved verbatim | §12.5 |
| NFR-OBS-003 | Job lifecycle | Preserved verbatim | §12.5 |
| NFR-OBS-004 | WS connection events | Preserved verbatim | §12.5 |
| NFR-OBS-005 | Error correlation IDs | Preserved verbatim | §12.5 |
| NFR-A11Y-001 | Keyboard nav | Preserved verbatim | §12.6 |
| NFR-A11Y-002 | Screen reader | Preserved verbatim | §12.6 |
| NFR-A11Y-003 | Color contrast | Preserved verbatim | §12.6 |
| NFR-A11Y-004 | Focus management | Preserved verbatim | §12.6 |
| NFR-MAINT-001 | DDD | Preserved verbatim | §12.7 |
| NFR-MAINT-002 | Where/What/How/Why | Preserved verbatim | §12.7 |
| NFR-MAINT-003 | Modular architecture | Preserved verbatim | §12.7 |

### Detailed Specifications Preserved

| Specification | v1.0.0 Location | v2.0.0 Location | Status |
|---------------|-----------------|-----------------|--------|
| Confidence Thresholds (0.95, 0.70) | FR-004 | FR-007 | Preserved verbatim |
| Routing Algorithm (3 priorities) | FR-003 | FR-006 | Preserved verbatim |
| Circuit Breaker (3 failures, 30s) | FR-003 | FR-006 | Preserved verbatim |
| MCP Capability Classification Table | FR-009 | FR-019 | Preserved verbatim |
| Action Classification Matrix | FR-015 | §13.1 | Preserved verbatim |
| Intent Index pgvector Schema | FR-012 | §15.2 | Preserved verbatim |
| Intent Index Query Algorithm | FR-012 | §15.2 | Preserved verbatim |
| WebSocket Protocol (sequence, checksum) | FR-008 | §9.4 | Preserved verbatim |
| Heartbeat 30s | FR-008 | §9.4 | Preserved verbatim |
| Reconnection Backoff | FR-008 | §9.4 | Preserved verbatim |
| Data Retention Rules | §12 | §15.3 | Preserved verbatim |
| Default Perspectives (skeptic, advocate, synthesizer) | FR-011 | FR-012 | Preserved verbatim |
| Perspective Timeout 30s | FR-011 | FR-012 | Preserved verbatim |

---

## Appendix C: Glossary

| Term | Definition |
|------|------------|
| **Canvas** | Stateful visual workspace holding nodes, documents, audio blocks |
| **Node** | Labeled visual element on canvas representing a concept |
| **Context** | Any input to the system requiring processing (text, events, job results) |
| **Context Routing** | Intelligent delegation of context to appropriate handlers |
| **Intent/Meaning** | Inferred purpose behind user input |
| **Assumption** | System's interpretation of user intent requiring confirmation |
| **Reconciliation** | Process of reaching consensus with user about assumptions |
| **Job** | Asynchronous long-running task (e.g., deep research) |
| **MCP Server** | Model Context Protocol server providing external integrations |
| **Working Memory Augmentation** | Using spatial canvas to extend cognitive capacity |
| **Task DAG** | Directed acyclic graph representing task dependencies |
| **Eureka Note** | Quick-capture thought or idea with minimal friction input |
| **Selection Scope** | User's current selected nodes/region; context focus primitive |
| **HITL Gate** | Human-in-the-loop checkpoint requiring user approval |
| **Gateway** | Pydantic AI Gateway API; the ONLY path for LLM inference |
| **AG-UI** | Agent-Gateway-UI protocol for structured agent↔UI communication |
| **Dashboard** | Live visualization node that subscribes to workspace state |

---

## Final Checklist

- [x] **No secret keys or values included anywhere** (only env var names)
- [x] **Gateway-only is explicitly enforced** in §3 EI-001 and throughout
- [x] **Every major module answers Where/What/How/Why** (§3 EI-005 mandate)
- [x] **Requirements have acceptance criteria** (Given/When/Then format)
- [x] **All v1.0.0 requirements preserved** (Appendix B confirms 100% coverage)
- [x] **Old→New mapping provided** (Appendix A)
- [x] **Vision invariants separated from engineering invariants** (§2 vs §3)
- [x] **Transport semantics preserved** (§9.4 WebSocket protocol)
- [x] **MCP capability classification preserved** (FR-019)
- [x] **Action classification matrix preserved** (§13.1)
- [x] **Confidence thresholds preserved** (FR-007)
- [x] **Intent index implementation preserved** (§15.2)
- [x] **Data retention rules preserved** (§15.3)
- [x] **Domain invariants preserved** (§14)

---

*PRD v2.0.0 generated by merging v1.0.0 engineering contract with proposed vision-forward structure. All v1.0.0 requirements are preserved or explicitly mapped.*
