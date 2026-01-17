# Intent Canvas: Session Architecture & Interaction Model

## Philosophy

This is not a chatbot. The era of chat-dominant interfaces is ending. This is a **command-driven, UI-driven, stateful workspace** where:

- The canvas is shared state between user and agentic system
- Interaction is high-throughput, high-velocity
- The system augments working memory, not just answers questions
- Persistence and modularity are first-class concerns
- Agents are first-class citizens, not bolted-on assistants

---

## Core Concepts

### Turns

A **turn** is any state change in the system:
- User input submitted
- Canvas CRUD (node/edge created, updated, deleted)
- Job started, progressed, or returned
- System response or proposal
- Assumption confirmed/rejected/edited
- External state change observed

Turns are:
- **Persisted** — survive session, stored as referenceable data
- **Forward-only** — no undo, no branching; forward actions can remove/alter previous state
- **Contextual** — can be referenced in conversation ("In turn 47, you suggested X")
- **Numbered** — sequential timeline marker

### Canvas

The canvas is a **spatial, persistent, shared workspace**:
- Holds nodes, edges, documents, audio blocks, jobs, artifacts
- Accessible to both user and agentic system
- Not all context is used at once — context routing determines relevance
- **Expands dynamically** — when work requires space, canvas expands "in place" (like universe expansion) to avoid collisions
- **Drag-select** — user can select regions, selection becomes context for next input

### Node Types

| Type | Description |
|------|-------------|
| **Text/Entity** | Basic labeled node with optional content |
| **Document** | Rich text content, markdown-compatible |
| **Audio Block** | Recording or transcription; can be processed by agents (e.g., "analyze this 30-minute spiel") |
| **Job** | Long-running task with status, progress, and result |
| **Dashboard** | Live visualization of external state (see External State Observation) |
| **Task DAG** | Directed acyclic graph of tasks with dependencies and status |

Node types are extensible — new types can be added as capabilities grow.

### Nodes as Visual Tools

The system can create nodes to explain concepts:
- User asks about an AST → system produces nodes visualizing the tree
- User asks for a taxonomy → system creates hierarchical node structure
- User asks to visualize a plan → system generates Task DAG nodes
- These are **examples**, not hard-coded — any visual explanation is valid
- Created nodes are **persisted** — user can delete manually or instruct system
- System uses turn context to know what it just created (for targeted deletion)

### Node Interaction with Agent

When a node is selected or expanded:
- The node's content becomes **primary context** for the next input
- User can have a **contextual conversation** about that node
- Example: click a research artifact → ask follow-up questions → agent responds with that artifact as context
- This enables deep-dive interaction without losing spatial organization

### Advanced Annotatable Graphs

Nodes support:
- **Unlimited relations** — no cap on edges per node
- **Click to expand** — details panel or inline expansion, with agent interaction available
- **Drag to connect** — creates typed edges
- **Inline label editing** — direct manipulation
- **Nested/hierarchical nodes** — containers within containers
- **Edge annotations** — comments, labels, metadata on connections
- **Auto-layout** — system arranges nodes for readability (tree, force-directed, grid, etc.)

### Task DAG

A specialized visualization for plans and workflows:
- Nodes represent tasks with status (pending, in-progress, complete, blocked)
- Edges represent dependencies
- Granular display levels (high-level phases → detailed subtasks)
- Can be generated collaboratively with agent ("help me plan this hackathon")
- Integrates with external systems via MCP (see Integration Workflow Example)

### External State Observation / Live Dashboards

The system can observe external state and maintain live visual representations:

- **Single source of truth** — pull from API endpoint, WebSocket, or MCP server
- **Dashboard nodes** — visualize external state on canvas
- **Live updates** — state changes reflected in real-time
- **Optional mutation** — if integrations support it, user/system can alter external state and see updates propagate

Example: A dashboard node connected to a deployment pipeline shows live build status. User sees green/red indicators update as builds complete.

---

## Input & Intent Workflow

### Input Sources

Context enters the system via:
1. **Text field** — primary input, floating above canvas
2. **Canvas gestures** — direct manipulation (drag, select, create, delete)
3. **File attachments** — drag files to input
4. **Voice** — transcription via Whispr Flow or similar
5. **Job returns** — artifacts from completed jobs
6. **External state** — MCP servers, API endpoints, webhooks
7. **Deterministic hooks** — lifecycle events (e.g., "on job complete, run analysis"), scheduled triggers

### Intent/Meaning Decipherment

When input arrives, the system deciphers intent using:

1. **Persistent User Intent Memory Index**
   - Learns user patterns over time
   - User can explicitly define behavior ("When I have random thoughts like this, do X")
   - Scoped: user-level, workspace-level, or session-level (user-configurable)

2. **Agent Reasoning**
   - Makes assumptions/inferences based on context
   - Decomposes complex input into granular parts (no information loss)

3. **Available Tools/Capabilities**
   - Infers based on what's possible (MCPs, configured agents, workflows)
   - If capability doesn't exist, communicates that clearly

### Classification

The system classifies input as:

| Type | Handling |
|------|----------|
| **Question** | Respond conversationally, store as context, optionally invoke tools (web search, etc.) |
| **Command** | Parse intent, create assumptions, propose action, await confirmation |
| **Eureka/Note** | Capture and persist, optionally suggest related actions based on user intent memory |
| **Clarification response** | Incorporate into ongoing assumption reconciliation |
| **Configuration** | Apply system changes (add MCP, alter behavior, etc.) |
| **Ambiguous** | Ask clarifying question OR auto-classify based on user intent memory |

### Assumption Reconciliation

When the system proposes an action:

1. **Assumptions displayed** — editable inline (confirm/reject/edit per assumption)
2. **Or clarifying questions** — open-ended, user responds via text field
3. **Multi-round** — can go back and forth until consensus reached
4. **User intent memory influences** — system may auto-confirm if user has established trust patterns

Example flow:
```
User: "Create a node titled Y Combinator"

Turn 1 [User]: Input submitted
Turn 2 [System]: Proposal
  - Action: create_node(title="Y Combinator")
  - Assumptions:
    • Type: "entity" (inferred, not "task" or "research")
    • Placement: right of current selection
  - [Confirm] [Edit] [Reject]

Turn 3 [User]: Confirmed

Turn 4 [System]: Executed
  - Node created (id: abc123)
  - Placed at (450, 200)
  - Rationale: Adjacent to selected context node
```

---

## UI: Central Input & View Toggles

### Layout

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│                     [Canvas]                        │
│                                                     │
├─────────────────────────────────────────────────────┤
│  ▲ [Active View Panel - expands upward]             │
├─────────────────────────────────────────────────────┤
│  [Chat ▲] [Wheel] [Events]    ← Toggle buttons      │
│  ┌─────────────────────────────────────────────────┐│
│  │  [Text input field]                    [⏎]  ││
│  └─────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

### Three Views

**1. Chat**
- Traditional conversational view
- Shows user messages and system responses as dialogue
- The "legacy" perspective — still useful for some interactions

**2. Wheel (Turns)**
- Timeline of all turns
- Each turn shows: number, timestamp, actor, summary
- Expandable for details
- Filterable by actor (user/system/job) or type

**3. Events**
- Structured event log
- Granular: `intent.parsed`, `assumption.confirmed`, `node.created`, `job.started`
- Filterable by event type, actor, node scope
- Technical/audit perspective

### Behavior

- **One view open at a time** (MVP) — indicated by ▲ on active button
- Views expand upward from input field, top-center
- User can say "close all panels" via text input
- Toggle buttons sit above the input field

---

## Canvas CRUD: Lightweight Flow

Direct manipulation (drag, delete, connect) follows a **lightweight flow**:

- **No assumptions required** — immediate effect
- **Logged to stream** — appears in Wheel and Events
- **Turn created** — persisted, referenceable
- System can reference these actions in future context

---

## Responses & Conversation

The system can respond in multiple ways:

| Response Type | Description |
|---------------|-------------|
| **Conversational** | Answers question, provides explanation — no action proposed |
| **Proposal** | Suggests action with assumptions — requires confirmation |
| **Clarification** | Asks question to refine understanding |
| **Acknowledgment** | Simple confirmation ("Got it, noted.") |
| **Tool invocation** | Web search, MCP call, etc. — results folded into response |

Responses appear in:
- **Chat view** — as dialogue turns
- **Wheel view** — as system turns with expandable content
- **Events view** — as structured events (`response.sent`, `tool.invoked`, etc.)

---

## User Intent Memory

### Structure

- **User-level** — patterns that follow user across workspaces
- **Workspace-level** — domain-specific patterns for this canvas
- **Session-level** — temporary overrides (if user requests)

### Learning

- Implicit: system observes patterns over time
- Explicit: user instructs ("When I do X, always respond with Y")
- Assumption confirmations feed into memory (user consistently accepts → auto-confirm pattern)

### Storage

- Markdown files (Obsidian-style) acceptable
- Associated with user identity
- Can be exported, edited, versioned

---

## Jobs (Conceptual — Implementation Shelved)

Jobs are long-running tasks delegated to the agentic system:

- **Examples**: Deep research, LLM-as-judge analysis, multi-perspective synthesis
- **Lifecycle**: started → progress (streamed) → completed/failed
- **Results flexible**:
  - New node on canvas
  - Inserted into existing document
  - Persisted in user storage (not visualized)
  - Attached as artifact to originating node
  - User defines per-job

Jobs appear in Wheel and Events views with streaming progress.

*Implementation details (providers, execution infrastructure) deferred.*

---

## MCP Self-Modification

The system can modify itself to add capabilities:

### Automatic (via conversation)
```
User: "Add Google Calendar MCP"
System: [Proposal]
  - Action: install_mcp(name="google-calendar", source="...")
  - Security check: [passed/pending]
  - Configuration required: OAuth credentials
  [Confirm] [Reject]
```

### Manual (via configuration)
- Robust documentation for adding MCPs manually
- Both paths available for MVP

### Constraints
- MCPs must adhere to specified standards
- Security checks required (sandboxing, permission scopes)
- User can review capabilities before enabling

---

## Integration Workflow Example

Illustrating the power of MCPs working together:

```
User: "Help me plan this hackathon so I can win"

[Multi-round collaboration with agent]

Turn 12 [System]: Proposal
  - Generate Task DAG with 47 subtasks
  - Export to Google Docs (via Google Docs MCP)
  - Create calendar events for milestones (via Google Calendar MCP)
  - Set up reminder notifications
  [Confirm] [Adjust] [Reject]

Turn 13 [User]: Confirmed

Turn 14 [System]: Executed
  - Task DAG created on canvas (node id: plan-001)
  - Google Doc created: "Hackathon Battle Plan"
  - 8 calendar events created
  - Reminders configured

[Later: user completes a task]

Turn 89 [User]: Marked "Setup dev environment" complete

Turn 90 [System]: State propagated
  - Task DAG updated
  - Google Doc checkbox marked
  - Next task surfaced: "Initialize repo structure"
```

This demonstrates:
- Collaborative planning with agent
- Task DAG generation
- Multi-MCP integration (Docs + Calendar)
- State synchronization across systems
- Forward progress with live updates

---

## Offline Handling

When disconnected:

- **Queue maintained** — user actions stored locally
- **UI indicator** — badge showing queued count
- **Expandable queue view** — user can see pending messages
- **Edit/remove** — user can modify or cancel queued actions before reconnect
- **Replay on reconnect** — queue flushed, turns created

---

## Data Persistence

### Canvas State
- Nodes, edges, documents, artifacts
- Stored per-workspace
- Markdown/file-based (Obsidian-compatible) acceptable

### Turns
- Full timeline persisted
- Referenceable by number or content
- Queryable for context routing

### User Intent Memory
- Markdown files associated with user
- Cross-session, cross-workspace patterns

### Job Artifacts
- Stored with reference to originating turn
- Flexible format based on job type

### Session Identity
- **Global session ID** per workspace interaction (distinct from per-request assumption session IDs)
- Scopes WebSocket connection, turns, and context
- Persists across reconnects

---

## Context Routing

Not all canvas state is used for every interaction. The system routes context intelligently:

- **Selection scope** — drag-selected nodes become primary context
- **Expanded node** — selected/expanded node content becomes primary context for follow-up
- **Recency** — recent turns weighted higher
- **Relevance** — semantic similarity to current input
- **Explicit reference** — user mentions specific nodes/turns
- **User intent memory** — learned relevance patterns

This prevents context overload while maintaining accessibility.

---

## Summary of What Exists vs. What's Needed

| Component | Current State | Needed |
|-----------|---------------|--------|
| WebSocket infrastructure | ✅ Exists (AGUIClient, ConnectionManager) | Route all events through it |
| Global session identity | ❌ Only per-request assumption sessions | Add workspace-scoped session ID |
| Turns system | ❌ Does not exist | Full implementation |
| Chat/Wheel/Events views | ❌ Does not exist | Build all three |
| Intent workflow | 🟡 Partial (AssumptionsPanel is modal) | Expand to full classification + multi-round + inline |
| User intent memory | ❌ Does not exist | Design and implement |
| Node interaction with agent | ❌ Does not exist | Contextual conversation on selection |
| Canvas drag-select context | 🟡 Selection exists, not as agent context | Wire selection to input context |
| Canvas auto-expansion | ❌ Does not exist | Implement |
| Nodes as visual tools | ❌ Nodes exist, not as agent tools | Agent tooling + layout engine |
| Audio block node type | ❌ Does not exist | Implement |
| Task DAG | ✅ Exists (TaskDAG.tsx) | Integrate with planning workflow |
| External state / dashboards | ❌ Does not exist | Implement |
| Advanced annotatable graphs | ❌ Out of scope (was 7.2) | Bring into scope |
| Jobs | 🟡 Infrastructure exists, unclear delegation | Shelved |
| MCP self-modification | ❌ Does not exist | Implement with docs |
| Offline queue UI | 🟡 Queue exists in hook, no UI | Build UI |
| User data storage | ❌ Unclear | Markdown/Obsidian-style |
