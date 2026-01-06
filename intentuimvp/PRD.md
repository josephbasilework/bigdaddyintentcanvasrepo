# IntentUI MVP - Product Requirements Document

---

## 0) Document Control

| Field | Value |
|-------|-------|
| **PRD Title** | IntentUI MVP - Agentic Canvas Workspace |
| **Version** | 1.0.0 |
| **Date** | 2026-01-03 |
| **Authors** | PRD Generation System (Opus 4.5) |
| **Status** | Draft |

### Links to Source Documentation

| Resource | Link | Purpose |
|----------|------|---------|
| BMAD-METHOD | https://github.com/bmad-code-org/BMAD-METHOD | Repo initialization and backlog generation methodology |
| PydanticAI | https://ai.pydantic.dev/ | Agent framework with structured outputs |
| Pydantic AI Gateway | https://ai.pydantic.dev/ (Gateway section) | **GATEWAY-ONLY** - All inference through this API |
| AG-UI Protocol | https://docs.ag-ui.com/introduction | Agent-UI interaction protocol |
| CopilotKit | https://docs.copilotkit.ai/ | Copilot-style in-app assistance |

### Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-01-03 | PRD Generator | Initial draft from brain dump |
| 1.1.0 | 2026-01-03 | Audit Process | Post-audit hardening (see RELEASE_NOTES.md) |

---

## 1) Executive Summary

### Problem Statement

Current AI interfaces force users into linear, chatbot-style interactions that don't match how power users think or work. Key pain points:

1. **Chatbot Interaction Fatigue** - Users must explicitly request artifacts and struggle to rapidly iterate on them
2. **Statelessness & Context Loss** - Tools lose context between sessions; users repeatedly re-explain their situation
3. **Cognitive Overload from Context Switching** - Power users juggling multiple complex tasks lack tools matching their high-throughput needs
4. **Intent Ambiguity Goes Unresolved** - AI systems make silent assumptions rather than surfacing and reconciling ambiguity
5. **Fragmented Tool Landscape** - Users manually orchestrate between AI assistants, calendars, documents, and research tools

### Proposed MVP Solution

IntentUI is a **canvas-based agentic workspace** that breaks from the chatbot paradigm. Users interact with a stateful, persistent, command-driven environment where:

- A spatial canvas holds nodes, documents, audio blocks, and graphs that persist across sessions
- Context routing intelligently delegates user input to appropriate agents and workflows
- Intent deciphering surfaces assumptions for user confirmation before action
- Deep research jobs run asynchronously with real-time streaming updates
- MCP (Model Context Protocol) servers provide modular, configurable external integrations
- All AI inference flows exclusively through the **Pydantic AI Gateway API**

### MVP Success Definition (Measurable)

| Metric | Definition | Target (MVP) |
|--------|------------|--------------|
| Task Completion Rate | % of user intents successfully executed without failure | > 80% |
| Assumption Accuracy | % of system assumptions user accepts without modification | > 70% |
| Time-to-Value | Time from command to useful output | < 30 seconds (simple tasks) |
| Session Continuity | % of users resuming previous workspace vs. starting fresh | > 60% |
| Research Job Completion | % of deep research jobs completing successfully | > 75% |
| Command vs. Chat Ratio | Ratio of command-driven to chat-driven interactions | > 3:1 |

### What is Explicitly Out of Scope

- Full self-modifying workflows (add MCPs entirely on-the-fly without config)
- Multi-LLM judge patterns (complex multi-model orchestration) - MVP uses single LLM critique
- Google Docs integration (focus on Calendar first)
- Advanced annotatable graphs with full editing
- Mobile/tablet interfaces
- Collaborative multi-user workspaces
- Offline functionality
- Custom agent creation by end users
- Advanced learning/personalization from usage patterns

---

## 2) Background + Context

### User Pain Points (from brain dump)

1. **"It's not like ChatGPT or Claude where you have a little artifact on the side"** - Current AI UX is limiting and static
2. **"You're not sitting here in ChatGPT with this unreliable horseshit with the lack of control"** - Users want control over AI interactions
3. **"Branching between chats and having multiple chats open getting different perspectives"** - Fragmented workflows
4. **"Context has to be handled systematically"** - Need for structured context management
5. **"We need reliability, high velocity, high throughput"** - Power users need speed

### Desired Outcomes

1. **Stateful experience** - "Going to be persistence of information long-term"
2. **Command-driven interaction** - "It's going to be command-driven, UI-driven"
3. **Modular connections** - "Modular, can cover a lot of ground"
4. **Working memory augmentation** - "This is really augmenting processing ability"
5. **Intent understanding** - "We have to decipher the intent/meaning"

### Key Constraints

1. **Gateway-Only**: All PydanticAI inference must go through Pydantic AI Gateway API
2. **AG-UI Protocol**: Agent-UI interactions follow AG-UI specification
3. **CopilotKit Integration**: Copilot-style assistance via CopilotKit
4. **No Secrets in Code**: Only environment variable names (PYDANTIC_GATEWAY_API_KEY, XAI_API_KEY)
5. **Modular/DDD Architecture**: Painfully explicit specs answering Where/What/How/Why

### Notable "Must-Have" Statements (paraphrased from brain dump)

- "Agents are first-class citizens to the program"
- "We want to be able to command the system to generate visual representations"
- "Random eurekas - we want to be able to get down our random ass notes"
- "Self-modifying workflows would be nice"
- "We could form a structured, competitive, first-place-minded plan"
- "The point is, it will be accessible - accessible to you and same to the agents"

---

## 3) Personas + User Journeys

### Primary Persona(s)

#### Power User / Knowledge Worker

| Attribute | Description |
|-----------|-------------|
| **Profile** | High-throughput work style, rapid context switching, multiple parallel workstreams |
| **Technical Level** | Comfortable with keyboard shortcuts, command-driven interfaces |
| **Pain Points** | Cognitive overload, fragmented tools, slow AI interfaces |
| **Primary Needs** | Speed, state persistence, spatial organization, reliable AI assistance |
| **Quote** | "I'm juggling 20 different things at once and need my workspace to keep up" |

### Secondary Persona(s)

#### Researcher / Analyst

| Attribute | Description |
|-----------|-------------|
| **Profile** | Deep research jobs, need for multiple perspectives, synthesis across sources |
| **Technical Level** | Moderate; values results over process |
| **Primary Needs** | Streaming research updates, LLM-as-judge patterns, provenance tracking |

#### Developer (Alpha Environment)

| Attribute | Description |
|-----------|-------------|
| **Profile** | Building/testing the system, configuring MCPs |
| **Technical Level** | High; understands system internals |
| **Primary Needs** | Dynamic MCP configuration, debugging visibility, extensibility |

### User Journey Maps

#### Journey 1: Power User Quick Task Execution

```
1. User opens IntentUI workspace (persisted from last session)
2. Issues command via floating text input or keyboard shortcut
3. System deciphers intent, surfaces assumptions for quick confirmation
4. User confirms/adjusts assumptions via buttons
5. Agent executes task, updates canvas state in real-time
6. User annotates/adjusts output directly on canvas
7. State persists automatically
```

#### Journey 2: Deep Research Session

```
1. User initiates research job with query/topic
2. System routes to research agent, begins streaming updates
3. Visual nodes populate canvas showing sources, findings, connections
4. LLM-as-judge pattern provides critique/perspectives
5. User spatially arranges findings, adds annotations
6. Research job completes; workspace state saved with full provenance
```

#### Journey 3: Intent Clarification Flow

```
1. User issues ambiguous command
2. System identifies assumptions it must make
3. Assumption reconciliation UI surfaces options
4. User confirms/adjusts assumptions
5. System proceeds with clarified intent
6. Assumptions stored for future reference (learning)
```

#### Journey 4: MCP Configuration Flow

```
1. User needs capability agent lacks (e.g., Calendar access)
2. System detects missing capability, proposes MCP
3. User approves MCP connection
4. Security validation runs
5. MCP connected, original task resumes
6. New capabilities available for future use
```

### Jobs-to-be-Done (JTBD)

| Job | Context | Expected Outcome |
|-----|---------|------------------|
| Capture random thoughts quickly | During high-velocity work session | Thought persisted as node with optional deep analysis |
| Research a topic comprehensively | Need balanced, multi-source analysis | Deep research report with provenance and perspectives |
| Organize ideas spatially | Complex project with many interconnected concepts | Visual graph with nodes, connections, annotations |
| Schedule based on task dependencies | Planning a project or hackathon | Task DAG synced to calendar with reminders |
| Get AI to understand my intent | Vague or complex request | Assumptions surfaced, confirmed, and accurately executed |

---

## 4) Scope

### 4.1 In-Scope (MVP)

| Category | Capabilities |
|----------|--------------|
| **Workspace** | Canvas-based UI with persistent state, nodes, documents, audio blocks |
| **Interaction** | Command-driven input, floating text box, assumption reconciliation UI |
| **Context** | Context routing, intent deciphering, user intent/meaning index |
| **Agents** | PydanticAI agents via Gateway, agent orchestration, structured outputs |
| **Jobs** | Deep research jobs with streaming, basic LLM-as-judge patterns |
| **Visualization** | Node-based spatial layout, edges/connections, task DAG view |
| **MCP** | MCP server framework, Google Calendar integration, security validation |
| **Persistence** | Canvas state, user preferences, job artifacts, backup/export |
| **Safety** | Agent guardrails, input sanitization, action blocking |

### 4.2 Out-of-Scope (Explicit)

| Feature | Reason | Future Phase |
|---------|--------|--------------|
| Full self-modifying workflows | Complexity; MVP allows MCP addition only | Phase 2 |
| Multi-LLM judge orchestration | Requires multi-model infrastructure | Phase 2 |
| Google Docs integration | Focus on Calendar first | Phase 1.5 |
| Advanced graph editing | Basic visualization sufficient for MVP | Phase 2 |
| Mobile/tablet interfaces | Desktop-first for power users | Phase 3 |
| Multi-user collaboration | Single-user reduces complexity | Phase 2 |
| Offline functionality | Requires significant architectural changes | Phase 3 |
| Custom agent creation | Power user feature | Phase 2 |
| Advanced personalization/learning | Basic intent index sufficient for MVP | Phase 2 |

#### Brain Dump Items Explicitly Excluded (with Acknowledgment)

| Item | Brain Dump Reference | Rationale for Exclusion |
|------|---------------------|-------------------------|
| Associative Knowledge Base Search | "predefined associative sort of search" | Requires vector DB infrastructure; deferred to Phase 2 |
| Predefined Analysis Workflows | "useful analysis workflow that we can just throw" | MVP focuses on flexible, not predefined workflows |
| Generic Lifecycle Hooks | "deterministic hooks after specific life cycles" | Agent pre/post hooks sufficient for MVP; full lifecycle hooks Phase 2 |
| Connected Knowledge Base Entity | "connected knowledge base" | Document/node search sufficient for MVP |
| Coda-style Data Structures | "basic data structures like in Coda" | Out of scope; canvas provides spatial organization |
| Agent-to-Agent Protocol | "do something with agent agent protocol" | MCP is MVP integration standard; A2A protocol deferred to Phase 2 |
| Real-time Voice Input | "microphone icon," "speech-to-speech" | AudioBlock transcription included; real-time voice is Phase 2 |

### 4.3 MVP Phases

**Phase 0: Foundation (Sprints 1-2)**
- Canvas shell, state management, WebSocket infrastructure
- PydanticAI Gateway client, agent base class
- AG-UI integration, CopilotKit base

**Phase 1: Core Features (Sprints 3-5)**
- Context routing, intent deciphering, assumptions UI
- Canvas nodes, edges, documents, graphs
- Deep research jobs, job streaming
- Basic persistence

**Phase 1.5: Integration (Sprints 6-7)**
- MCP framework, Google Calendar integration
- LLM-as-judge workflow
- Full persistence, backup/export

---

## 5) Functional Requirements

### FR-001: Canvas Workspace Initialization

| Field | Value |
|-------|-------|
| **ID** | FR-001 |
| **Description** | System shall render a canvas-based workspace on load with persistent state |
| **User Value** | Enables spatial thinking; breaks from linear chat paradigm |
| **Inputs** | User session, previous canvas state (if any) |
| **Outputs** | Rendered canvas with restored nodes, documents, audio blocks |
| **Primary Flow** | 1. User navigates to workspace URL 2. System authenticates 3. Previous state loaded 4. Canvas rendered with floating text input |
| **Edge Cases** | First-time user (blank canvas), corrupted state (fallback to blank), large canvas (virtualization) |
| **Error States** | State load failure → show error, offer blank canvas; Auth failure → redirect to login |

**Acceptance Criteria**:
- **Given** a user accesses the workspace URL **When** the page loads **Then** a canvas renders within 2 seconds with floating text input visible
- **Given** the user has previous state **When** the canvas loads **Then** all previous nodes, documents, and positions are restored
- **Given** no API keys in client-side code **When** source is inspected **Then** no secrets are visible

---

### FR-002: Floating Text Input for Context Injection

| Field | Value |
|-------|-------|
| **ID** | FR-002 |
| **Description** | System shall provide a floating text input box for context/command injection |
| **User Value** | Always-accessible input for high-velocity interactions |
| **Inputs** | User text, optional file attachments |
| **Outputs** | Context payload dispatched to routing pipeline |
| **Primary Flow** | 1. User types in text box 2. User presses Enter or clicks submit 3. Text + attachments sent to context router |
| **Edge Cases** | Empty input (ignore), very long input (warn), file type unsupported (reject with message) |
| **Error States** | Router unavailable → queue locally, retry |

**Acceptance Criteria**:
- **Given** the canvas is loaded **When** the user views the workspace **Then** a floating text input is visible and focused
- **Given** the user types and presses Enter **When** input is submitted **Then** it is sent to the context routing pipeline
- **Given** the user drags files **When** dropped on text box **Then** files are attached to context payload

---

### FR-003: Context Routing Pipeline

| Field | Value |
|-------|-------|
| **ID** | FR-003 |
| **Description** | System shall route incoming context to appropriate agents/workflows based on type and intent |
| **User Value** | Intelligent delegation; user doesn't manually assign tasks |
| **Inputs** | Context payload (text, attachments, source metadata) |
| **Outputs** | Routing decision with target handler(s) |
| **Primary Flow** | 1. Context received 2. Intent classified 3. Routing decision made 4. Context dispatched to handler |
| **Edge Cases** | Ambiguous intent (route to intent decipherer), multiple intents (decompose), no matching handler (fallback) |
| **Error States** | Classification failure → ask user for clarification |

**Acceptance Criteria**:
- **Given** context is submitted **When** router receives it **Then** it dispatches to appropriate handler within 500ms
- **Given** context has multiple intents **When** decomposition occurs **Then** each intent is routed independently
- **Given** no handler matches **When** routing fails **Then** user is asked for clarification

---

### FR-004: Intent Deciphering with Assumption Generation

| Field | Value |
|-------|-------|
| **ID** | FR-004 |
| **Description** | System shall decipher user intent and generate structured assumptions for confirmation |
| **User Value** | Prevents misunderstanding; user controls what actions are taken |
| **Inputs** | Raw user input, user intent index, available tools/capabilities |
| **Outputs** | Structured assumptions with confidence scores |
| **Primary Flow** | 1. Input received 2. Query intent index for patterns 3. Analyze with PydanticAI agent (via Gateway) 4. Generate assumption structure 5. Send to assumption UI |
| **Edge Cases** | High confidence (minimal assumptions), very low confidence (request clarification), conflicting assumptions |
| **Error States** | Gateway timeout → retry with backoff; Agent failure → show error, allow retry |

**Acceptance Criteria**:
- **Given** raw user input **When** processed by deciphering agent **Then** structured assumptions are produced with confidence scores
- **Given** the user intent index exists **When** deciphering occurs **Then** historical patterns inform assumptions
- **Given** available tools **When** assumptions are made **Then** they reference only feasible actions

#### Confidence Thresholds (Configurable)

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

---

### FR-005: Assumption Reconciliation UI

| Field | Value |
|-------|-------|
| **ID** | FR-005 |
| **Description** | System shall display assumptions and allow user to confirm, reject, or modify |
| **User Value** | Transparency and control over AI decisions |
| **Inputs** | Assumption list from intent decipherer |
| **Outputs** | Resolved assumptions (approved/rejected/modified) |
| **Primary Flow** | 1. Assumptions received 2. Rendered in panel 3. User clicks Confirm/Reject/Edit per assumption 4. Resolution sent to orchestrator |
| **Edge Cases** | All assumptions auto-confirmed (high confidence), user edits assumption text, user rejects all |
| **Error States** | UI fails to render → show error, allow manual input |

**Acceptance Criteria**:
- **Given** assumptions are generated **When** rendered **Then** each shows intent, confidence, and Confirm/Reject/Edit buttons
- **Given** user approves assumption **When** clicking Confirm **Then** associated action is dispatched
- **Given** user rejects assumption **When** clicking Reject **Then** assumption is discarded and optional feedback captured

---

### FR-006: Canvas Node CRUD Operations

| Field | Value |
|-------|-------|
| **ID** | FR-006 |
| **Description** | System shall support create, read, update, delete operations on canvas nodes |
| **User Value** | Spatial organization of thoughts and concepts |
| **Inputs** | User actions (create, drag, edit, delete), agent actions |
| **Outputs** | Updated canvas state, visual feedback |
| **Primary Flow** | 1. User creates node (click + type label) 2. Node appears at position 3. User drags to reposition 4. Position persists |
| **Edge Cases** | Overlapping nodes (adjust position), many nodes (virtualization), linked nodes (cascade updates) |
| **Error States** | State save failure → show warning, retry |

**Acceptance Criteria**:
- **Given** user creates a node **When** rendered **Then** it appears at specified position with editable label
- **Given** a node exists **When** dragged **Then** position updates in real-time and persists
- **Given** a node is selected **When** context menu invoked **Then** edit/delete/connect actions available

---

### FR-007: Deep Research Job Dispatch

| Field | Value |
|-------|-------|
| **ID** | FR-007 |
| **Description** | System shall dispatch deep research jobs that run asynchronously with streaming updates |
| **User Value** | Comprehensive research without blocking workspace |
| **Inputs** | Research query/topic, optional constraints |
| **Outputs** | Research artifact (report), streaming progress updates |
| **Primary Flow** | 1. User requests research 2. Job created and queued 3. Research agent invokes via Gateway 4. Progress streams to UI 5. Report generated and persisted 6. Result appears on canvas |
| **Edge Cases** | Very broad topic (ask for narrowing), sources unavailable (partial results), duplicate topic (warn) |
| **Error States** | Job failure → show error, allow retry or modify parameters |

**Acceptance Criteria**:
- **Given** a research query is submitted **When** job is created **Then** research agent is invoked
- **Given** research is in progress **When** sources are found **Then** intermediate results stream to UI
- **Given** research completes **When** report is generated **Then** it is stored as referenceable artifact

---

### FR-008: WebSocket Real-time Streaming

| Field | Value |
|-------|-------|
| **ID** | FR-008 |
| **Description** | System shall stream real-time updates via WebSocket for jobs, agent responses, and state sync |
| **User Value** | Immediate feedback on long-running operations |
| **Inputs** | Server events (job progress, state changes, agent output) |
| **Outputs** | UI updates reflecting current state |
| **Primary Flow** | 1. WebSocket connection established 2. Client subscribes to relevant channels 3. Server broadcasts updates 4. Client applies updates to state |
| **Edge Cases** | Connection drop (reconnect with backoff), message ordering (sequence numbers), large payloads (chunking) |
| **Error States** | Connection failure → show indicator, queue events, retry |

**Acceptance Criteria**:
- **Given** application loads **When** WebSocket connects **Then** persistent connection maintained with heartbeat
- **Given** WebSocket message arrives **When** it contains state update **Then** global state updates and UI reflects changes
- **Given** WebSocket drops **When** reconnection attempted **Then** connection restores within 5 seconds with backoff

---

### FR-009: MCP Server Integration

| Field | Value |
|-------|-------|
| **ID** | FR-009 |
| **Description** | System shall support Model Context Protocol servers for modular external integrations |
| **User Value** | Extensibility; connect to calendars, docs, and other services |
| **Inputs** | MCP server configuration, tool invocation requests |
| **Outputs** | Tool results, capability registration |
| **Primary Flow** | 1. MCP configured in registry 2. Security validation passes 3. Tools discovered 4. Agents can invoke tools 5. Results returned |
| **Edge Cases** | MCP unavailable (graceful degradation), tool timeout (retry), invalid response (error handling) |
| **Error States** | Security validation failure → block with explanation; Connection failure → show error, allow retry |

**Acceptance Criteria**:
- **Given** MCP server is configured **When** client connects **Then** available tools are discovered
- **Given** a tool is invoked **When** parameters provided **Then** tool executes and returns results
- **Given** MCP connection fails **When** error occurs **Then** graceful degradation and user notification

#### MCP Security Validation Rules

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
- Rate limit: 100 tool calls per minute per MCP
- Anomaly detection: alert if >10x normal call volume

---

### FR-010: Google Calendar MCP Integration

| Field | Value |
|-------|-------|
| **ID** | FR-010 |
| **Description** | System shall integrate with Google Calendar via MCP for event reading and creation |
| **User Value** | Time-aware workspace; schedule from canvas |
| **Inputs** | Calendar queries, event creation requests |
| **Outputs** | Calendar events, sync status |
| **Primary Flow** | 1. User requests calendar access 2. Google Calendar MCP configured 3. OAuth completed 4. Events queryable 5. Task DAG can sync to calendar |
| **Edge Cases** | OAuth failure, calendar API rate limits, event conflicts |
| **Error States** | Auth failure → show OAuth prompt; API error → show error, allow retry |

**Acceptance Criteria**:
- **Given** Google Calendar MCP is configured **When** queried **Then** events are retrieved
- **Given** user requests calendar update **When** processed **Then** calendar is modified via MCP
- **Given** task DAG exists **When** synced to calendar **Then** tasks appear as calendar events

---

### FR-011: LLM-as-Judge Analysis Pattern

| Field | Value |
|-------|-------|
| **ID** | FR-011 |
| **Description** | System shall support LLM-as-judge patterns for multi-perspective analysis |
| **User Value** | Balanced analysis; reduced blind spots |
| **Inputs** | Content to analyze, perspective configurations |
| **Outputs** | Multiple perspectives, synthesized analysis |
| **Primary Flow** | 1. Content identified for judge analysis 2. Multiple perspective prompts prepared 3. Perspectives generated (via Gateway) 4. Synthesis agent combines viewpoints 5. Combined analysis returned |
| **Edge Cases** | Conflicting perspectives, one perspective fails, very short content |
| **Error States** | Partial failure → return available perspectives with note |

**Acceptance Criteria**:
- **Given** content to analyze **When** LLM-as-judge invoked **Then** multiple perspective agents are called
- **Given** perspectives generated **When** synthesis occurs **Then** combined analysis with agreements/disagreements produced
- **Given** analysis completes **When** stored **Then** both individual perspectives and synthesis are accessible

#### Implementation Note: Compute Allocation

MVP supports configurable perspective count (1-3 perspectives from single LLM model via Gateway).
"Throwing more compute" from brain dump is achieved via additional perspective iterations, not multiple provider calls.
Multi-model orchestration (true parallel multi-provider) is deferred to Phase 2.

**Default Perspectives** (for research reports):
1. "skeptic" - Challenges claims, looks for weak evidence
2. "advocate" - Steelmans the argument, finds supporting evidence
3. "synthesizer" - Identifies common ground and key tensions

**Execution**:
- Run perspectives sequentially (single model)
- Timeout per perspective: 30 seconds
- If perspective fails: proceed with available perspectives, note in output

---

### FR-012: User Intent/Meaning Index

| Field | Value |
|-------|-------|
| **ID** | FR-012 |
| **Description** | System shall persist user intent patterns to improve future assumption accuracy |
| **User Value** | System learns user's patterns over time |
| **Inputs** | Approved/rejected assumptions, user actions |
| **Outputs** | Updated intent index, improved suggestions |
| **Primary Flow** | 1. Assumption resolved 2. Resolution indexed with context 3. Future inputs query index 4. Higher confidence assumptions made |
| **Edge Cases** | New user (no history), conflicting patterns, index growth |
| **Error States** | Index query failure → proceed without historical data |

**Acceptance Criteria**:
- **Given** assumption is approved **When** stored **Then** it is indexed by intent type and outcome
- **Given** new input received **When** similar patterns exist **Then** higher confidence assumptions are made
- **Given** index is queried **When** results returned **Then** relevance scoring is applied

#### Intent Index Implementation

**Storage**: PostgreSQL with pgvector extension
**Embedding Model**: sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)

**Schema**:
- id: UUID
- user_id: UUID (foreign key)
- intent_text: TEXT (original input)
- embedding: VECTOR(384)
- resolution: JSONB (approved assumptions, actions taken)
- outcome: ENUM('success', 'failure', 'modified')
- created_at: TIMESTAMP

**Query Algorithm**:
1. Embed incoming input with same model
2. Cosine similarity: `SELECT * WHERE 1 - (embedding <=> query) > 0.7`
3. Rank by `similarity * recency_weight` (decay: 0.99^days_old)
4. Return top 5 matches

**Update Strategy**:
- Insert on assumption approval
- Update outcome on action completion
- Prune entries older than 90 days with outcome='failure'

---

### FR-013: Audio Block Transcription

| Field | Value |
|-------|-------|
| **ID** | FR-013 |
| **Description** | System shall support audio capture and transcription as canvas elements |
| **User Value** | Rapid voice-based context capture |
| **Inputs** | Audio recording or file upload |
| **Outputs** | Transcription text, audio block on canvas |
| **Primary Flow** | 1. User creates audio block 2. Records audio or uploads file 3. Transcription job dispatched 4. Transcript appears in block 5. Searchable and processable |
| **Edge Cases** | Long audio (chunked transcription), poor audio quality, unsupported format |
| **Error States** | Transcription failure → show error, allow retry |

**Acceptance Criteria**:
- **Given** user creates audio block **When** they record audio **Then** recording is captured and stored
- **Given** audio block has recording **When** transcription triggered **Then** transcript generated and stored
- **Given** audio block has transcript **When** viewed **Then** transcript is displayed and searchable

---

### FR-014: Canvas State Persistence

| Field | Value |
|-------|-------|
| **ID** | FR-014 |
| **Description** | System shall persist canvas state across sessions |
| **User Value** | Never lose work; resume anytime |
| **Inputs** | Canvas state changes |
| **Outputs** | Persisted state, restore capability |
| **Primary Flow** | 1. State changes occur 2. Changes debounced 3. State serialized 4. Saved to storage 5. Restored on next session |
| **Edge Cases** | Large state (incremental save), rapid changes (batching), conflict resolution |
| **Error States** | Save failure → retry, show warning; Restore failure → offer blank canvas |

**Acceptance Criteria**:
- **Given** canvas has state **When** save triggered **Then** full state is persisted
- **Given** user returns to workspace **When** canvas loads **Then** previous state is restored
- **Given** state is large **When** saved **Then** incremental/diff-based saving minimizes overhead

---

### FR-015: Agent Safety Guardrails

| Field | Value |
|-------|-------|
| **ID** | FR-015 |
| **Description** | System shall prevent agents from executing destructive actions without explicit approval |
| **User Value** | Safety; agents can't cause unintended harm |
| **Inputs** | Proposed agent actions |
| **Outputs** | Approved/blocked actions with explanation |
| **Primary Flow** | 1. Agent proposes action 2. Guardrails evaluate action 3. Destructive actions flagged 4. User confirmation required 5. Action executed or blocked |
| **Edge Cases** | Action appears safe but has side effects, novel action types |
| **Error States** | Classification uncertainty → default to asking for confirmation |

**Acceptance Criteria**:
- **Given** agent proposes destructive action **When** evaluated **Then** action blocked or requires explicit confirmation
- **Given** agent attempts restricted resource access **When** detected **Then** action denied with explanation
- **Given** prompt injection attempted **When** detected **Then** input sanitized or rejected

---

## 6) Non-Functional Requirements

### 6.1 Security & Secrets Management

| Requirement | Implementation |
|-------------|----------------|
| **Environment Variables Only** | All API keys stored in `.env` (never committed). Code references by name only: `PYDANTIC_GATEWAY_API_KEY`, `XAI_API_KEY` |
| **No Hardcoded Secrets** | Linting rules detect and reject hardcoded keys. Pre-commit hooks scan for secrets |
| **.env.example Pattern** | Repository contains `.env.example` with variable names only (no values) |
| **Runtime Validation** | Application fails to start if required env vars are missing |
| **Gateway-Only Enforcement** | `GatewayClient` is the ONLY module that imports PydanticAI inference; no direct provider imports |

### 6.2 Performance Targets (MVP-Grade)

| Metric | Target |
|--------|--------|
| Canvas initial load | < 2 seconds |
| State update propagation | < 100ms |
| Intent deciphering | < 5 seconds |
| Simple command execution | < 30 seconds |
| WebSocket reconnection | < 5 seconds |
| Canvas with 100 nodes | Smooth pan/zoom (60fps) |

### 6.3 Reliability/Availability Expectations

| Aspect | Expectation |
|--------|-------------|
| Gateway dependency | Retry with exponential backoff; graceful degradation if unavailable |
| WebSocket | Automatic reconnection with queued events |
| State persistence | Debounced auto-save; no data loss on normal close |
| Job system | Jobs recoverable after restart; idempotent operations |

### 6.4 Privacy Considerations

| Aspect | Approach |
|--------|----------|
| User Intent Index | Stored locally per user. Not transmitted beyond LLM inference |
| Canvas Content | User-controlled. No automatic sharing |
| LLM Prompts | May contain user data; transmitted to Gateway. Users informed |
| Logging | Structured logging excludes secrets, PII where possible |

### 6.5 Observability (Logs/Metrics/Traces)

| Component | Observability |
|-----------|---------------|
| API endpoints | Request/response logging (no secrets) |
| Agent invocations | Latency, success/failure metrics |
| Job system | Job lifecycle events, duration, outcomes |
| WebSocket | Connection events, message counts |
| Errors | Structured error logging with correlation IDs |

### 6.6 Accessibility

| Requirement | Implementation |
|-------------|----------------|
| Keyboard navigation | All primary actions accessible via keyboard |
| Screen reader | Semantic HTML, ARIA labels on canvas elements |
| Color contrast | Meet WCAG 2.1 AA standards |
| Focus management | Visible focus indicators |

### 6.7 Maintainability + Modularity Requirements

| Principle | Implementation |
|-----------|----------------|
| Domain-Driven Design | Bounded contexts with clear boundaries |
| Where/What/How/Why | Every module documented with explicit rationale |
| Modular architecture | Loosely coupled services, clear interfaces |
| Test coverage | Unit tests for core logic, integration tests for flows |

---

## 7) Domain Model (DDD)

### 7.1 Bounded Contexts

```
+------------------+          +------------------+
|   User Context   |<-------->|  Agent Context   |
| (intent, memory) |          | (workflows,jobs) |
+--------+---------+          +--------+---------+
         |                             |
         v                             v
+--------+---------+          +--------+---------+
|Context Routing   |<-------->| Integration Ctx  |
|   (routing)      |          | (MCP, external)  |
+--------+---------+          +--------+---------+
         |                             |
         +-------------+---------------+
                       |
                       v
              +--------+---------+
              | Workspace Context|
              | (canvas, nodes)  |
              +------------------+
```

| Context | Responsibilities |
|---------|------------------|
| **Workspace Context** | Canvas state, nodes, documents, audio blocks, visual graphs, spatial layout |
| **Agent Context** | Agent orchestration, jobs, workflows, tool invocation, LLM-as-judge |
| **Integration Context** | MCP servers, external connections, security validation |
| **User Context** | User identity, intent index, sessions, assumptions, preferences |
| **Context Routing** | Input classification, routing decisions, context decomposition |

### 7.2 Core Domain Concepts

#### Entities (Have Identity)

| Entity | Key Attributes | Context |
|--------|----------------|---------|
| Canvas | id, sessionId, name, nodes[], documents[], audioBlocks[] | Workspace |
| Node | id, canvasId, label, position, linkedDocumentId | Workspace |
| Document | id, canvasId, title, content, version | Workspace |
| AudioBlock | id, canvasId, audioUri, transcription, status | Workspace |
| TaskDAG | id, canvasId, name, tasks[], dependencies[], calendarSyncEnabled | Workspace |
| VisualGraph | id, canvasId, name, nodes[], edges[], layoutType | Workspace |
| Job | id, type, status, input, result, progress | Agent |
| Workflow | id, name, steps[], triggers[], isModifiable | Agent |
| MCPServer | id, name, endpoint, config, capabilities[], status | Integration |
| Session | id, userId, canvasId, status, contextHistory[] | User |
| Assumption | id, sessionId, text, confidence, status | User |
| IntentMeaningIndex | id, userId, patterns[], definitions[] | User |

#### Value Objects (Immutable)

| Value Object | Attributes |
|--------------|------------|
| NodePosition | x, y, z |
| JobProgress | percentComplete, currentStep, stepsCompleted |
| ConfidenceScore | value (0-1), factors[] |
| ContextPacket | source, type, payload, timestamp |
| RoutingDecision | targetContext, handler, priority |

#### Aggregates

| Aggregate | Root | Contains |
|-----------|------|----------|
| Canvas Aggregate | Canvas | Nodes, Documents, AudioBlocks, VisualGraphs, TaskDAGs |
| TaskDAG Aggregate | TaskDAG | Tasks, Dependencies |
| Session Aggregate | Session | ContextPackets (history), Assumptions |
| Job Aggregate | Job | JobProgress, JobResult |
| MCP Server Aggregate | MCPServer | Capabilities, SecurityPolicy |

**TaskDAG Invariants**:
- TI-001: TaskDAG must be acyclic (validation on dependency addition)
- TI-002: CalendarSync requires active MCP connection (MCPManager validation)

### 7.3 Ubiquitous Language Glossary

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
| **Task DAG** | Directed acyclic graph representing task dependencies with optional calendar sync |
| **Eureka Note** | Quick-capture thought or idea with minimal friction input |
| **Knowledge Base** | Connected repository of workspace information for semantic search (Phase 2) |
| **Live Dashboard** | Real-time visualization of external state from API endpoints (Phase 2) |

### 7.4 Key Invariants and Business Rules

| ID | Invariant | Enforcement |
|----|-----------|-------------|
| CI-001 | Node position must be unique within Canvas | CanvasAggregate validates position |
| CI-002 | Node's linkedDocumentId must reference Document in same Canvas | Aggregate validation |
| SI-001 | Assumption must be resolved before executing dependent actions | Agent Context checks |
| JI-001 | Only one deep_research Job per topic simultaneously | JobService checks duplicates |
| JI-002 | Job cannot transition from completed/failed to running | State machine validation |
| MI-001 | MCPServer must pass security validation before activation | MCPServerAggregate |

### 7.5 Event Model

| Event | Trigger | Consumers |
|-------|---------|-----------|
| ContextReceived | Any input enters system | Context Router |
| IntentDeciphered | Intent analysis complete | Assumption Creator |
| AssumptionCreated | System makes assumption | UI, Session |
| AssumptionResolved | User approves/rejects | Agent Context, Intent Index |
| JobCreated | New job requested | Job Executor |
| JobProgressUpdated | Progress changed | UI (WebSocket) |
| JobCompleted | Job finished | Session, Workspace |
| CanvasUpdated | Node/document changed | Persistence |
| MCPServerActivated | MCP passed validation | Agent Context |

---

## 8) System Architecture

### 8.1 High-Level Architecture

```
+-----------------------------------------------------------------------------------+
|                                   FRONTEND LAYER                                   |
+-----------------------------------------------------------------------------------+
|  +-------------------+  +-------------------+  +-------------------+              |
|  |   Canvas/Workspace |  |  Copilot Sidebar  |  |  Assumptions UI   |              |
|  |   (React + Next.js)|  |   (CopilotKit)    |  |  (Reconciliation) |              |
|  +-------------------+  +-------------------+  +-------------------+              |
|                          +-------------------+                                     |
|                          |    AG-UI Layer    |                                     |
|                          +---------+---------+                                     |
+-----------------------------------------------------------------------------------+
                                     | WebSocket / HTTP
                                     v
+-----------------------------------------------------------------------------------+
|                                   BACKEND LAYER                                    |
+-----------------------------------------------------------------------------------+
|  +-------------------+  +-------------------+  +-------------------+              |
|  |  Context Router   |  | Intent Decipherer |  |   Job Manager     |              |
|  +-------------------+  +-------------------+  +-------------------+              |
|                          +-------------------+                                     |
|                          |Agent Orchestrator |                                     |
|                          +---------+---------+                                     |
|                                    |                                               |
|                          +---------+---------+                                     |
|                          |   MCP Manager     |                                     |
|                          +-------------------+                                     |
+-----------------------------------------------------------------------------------+
                                     |
                                     v
+-----------------------------------------------------------------------------------+
|                               INTEGRATION LAYER                                    |
+-----------------------------------------------------------------------------------+
|  +-------------------+  +-------------------+  +-------------------+              |
|  | Pydantic Gateway  |  |  External MCPs    |  |  WebSocket Hub    |              |
|  |    (LLM Access)   |  | (Calendar, etc.)  |  |  (Real-time)      |              |
|  +-------------------+  +-------------------+  +-------------------+              |
+-----------------------------------------------------------------------------------+
                                     |
                                     v
+-----------------------------------------------------------------------------------+
|                                  DATA LAYER                                        |
+-----------------------------------------------------------------------------------+
|  +-------------------+  +-------------------+  +-------------------+              |
|  | Canvas State DB   |  | Intent Index      |  | Job Artifacts     |              |
|  | (PostgreSQL)      |  | (PostgreSQL)      |  | (File/DB)         |              |
|  +-------------------+  +-------------------+  +-------------------+              |
+-----------------------------------------------------------------------------------+
```

### 8.2 Module Breakdown (Where/What/How/Why)

#### Canvas/Workspace UI

| Aspect | Detail |
|--------|--------|
| **Where** | `/frontend/src/components/Canvas/`, `/frontend/src/features/workspace/` |
| **What** | Stateful visual workspace with nodes, documents, audio blocks, graphs |
| **How** | React components with drag-and-drop, Zustand state, AG-UI events, canvas virtualization |
| **Why** | Core differentiator from chatbots; enables spatial working memory augmentation |

#### Context Router

| Aspect | Detail |
|--------|--------|
| **Where** | `/backend/app/context/router.py` |
| **What** | Routes incoming context to appropriate agents/workflows based on type and intent |
| **How** | `ContextRouter` class with pluggable strategies; integrates with Intent Decipherer |
| **Why** | Single agent can't handle everything; modular delegation prevents bottleneck |

**Routing Algorithm**:

1. `ContextRouter` uses a priority-ordered strategy pattern:
   - Priority 1: Exact command matching (slash commands like `/research`, `/calendar`)
   - Priority 2: Intent classification via LLM structured output (Gateway)
   - Priority 3: Keyword fallback (regex patterns for common phrases)

2. When multiple handlers match:
   - Highest priority strategy wins
   - If same priority, highest-confidence match wins
   - If tie, prompt user for disambiguation

3. Timeout: 500ms for classification; fallback to keyword after timeout

4. Circuit breaker: 3 consecutive failures → route to fallback handler for 30 seconds

#### Intent Decipherer

| Aspect | Detail |
|--------|--------|
| **Where** | `/backend/app/agents/intent_decipherer.py`, `/backend/app/intent/models.py` |
| **What** | Parses user input, makes assumptions, generates structured output for confirmation |
| **How** | PydanticAI agent via Gateway; queries intent index; produces `IntentAssumptions` model |
| **Why** | Core value proposition - understanding what user actually means |

#### Agent Orchestrator

| Aspect | Detail |
|--------|--------|
| **Where** | `/backend/app/orchestration/orchestrator.py` |
| **What** | Coordinates agent activities, manages lifecycles, enforces safety |
| **How** | Registry pattern; capability matching; pre/post hooks for guardrails |
| **Why** | Agents are "first-class citizens"; need centralized coordination |

#### MCP Manager

| Aspect | Detail |
|--------|--------|
| **Where** | `/backend/app/mcp/manager.py`, `/backend/app/mcp/registry.py` |
| **What** | Manages MCP server registration, security validation, capability exposure |
| **How** | `MCPManager` with lifecycle management; `MCPSecurityChecker` for validation |
| **Why** | Modularity requirement; self-modifying workflows need robust MCP management |

#### Job Manager

| Aspect | Detail |
|--------|--------|
| **Where** | `/backend/app/jobs/manager.py`, `/backend/app/jobs/research.py` |
| **What** | Handles async jobs (deep research), streaming updates, artifact persistence |
| **How** | Celery/ARQ queue; Redis for state; WebSocket for progress streaming |
| **Why** | Long-running tasks must not block workspace; real-time feedback essential |

#### LLM Gateway Client

| Aspect | Detail |
|--------|--------|
| **Where** | `/backend/app/gateway/client.py` |
| **What** | Unified client for ALL LLM inference via Pydantic AI Gateway ONLY |
| **How** | httpx async client; reads `PYDANTIC_GATEWAY_API_KEY`; retry with backoff |
| **Why** | **GATEWAY-ONLY ENFORCEMENT** - architectural constraint, centralizes LLM access |

#### Persistence Layer

| Aspect | Detail |
|--------|--------|
| **Where** | `/backend/app/persistence/` |
| **What** | CRUD for canvas state, intent index, job artifacts, MCP configs |
| **How** | Repository pattern; PostgreSQL for MVP; optional Git/Obsidian sync |
| **Why** | Persistence is fundamental to stateful workspace value |

#### Task DAG Manager

| Aspect | Detail |
|--------|--------|
| **Where** | `/backend/app/taskdag/manager.py`, `/frontend/src/components/TaskDAG/` |
| **What** | Manages task DAG creation, dependency validation, calendar synchronization |
| **How** | Graph validation algorithms (cycle detection via topological sort), MCP integration for calendar sync |
| **Why** | Enables structured planning workflows from brain dump; supports "task DAG" feature explicitly mentioned |

### 8.3 API Surface

#### REST Endpoints

| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/api/workspace` | GET | Get current workspace state | Required |
| `/api/workspace` | PUT | Update workspace state | Required |
| `/api/context` | POST | Submit context for routing | Required |
| `/api/jobs` | POST | Create new job | Required |
| `/api/jobs/{id}` | GET | Get job status/result | Required |
| `/api/mcp` | GET | List available MCPs | Required |
| `/api/mcp/{id}` | POST | Configure MCP | Required |
| `/api/assumptions/{id}` | PUT | Resolve assumption | Required |

#### WebSocket Events

| Event Direction | Event Type | Payload |
|-----------------|------------|---------|
| Server → Client | `job.progress` | { jobId, progress, message } |
| Server → Client | `state.update` | { patch } (JSON Patch format) |
| Server → Client | `assumptions.new` | { assumptions[] } |
| Client → Server | `assumption.resolve` | { assumptionId, resolution } |
| Client → Server | `canvas.update` | { changes[] } |

#### WebSocket State Sync Protocol

**Message Schema**:
```json
{
  "type": "state.update",
  "sequence": 12345,
  "timestamp": "2026-01-03T12:00:00Z",
  "patch": [
    { "op": "add", "path": "/nodes/abc123", "value": {...} }
  ],
  "checksum": "sha256:abc..."
}
```

**Conflict Resolution**:
1. Server is authoritative
2. Client applies patch only if sequence = last_sequence + 1
3. If gap detected, client requests full state sync
4. Optimistic updates: client applies locally, reverts on server rejection

**Reconnection**:
1. Client sends last known sequence on reconnect
2. Server sends patches since that sequence (or full state if >100 patches)
3. Client validates checksum after applying patches

### 8.4 Agent + UI Interaction Model

#### AG-UI Events (UI → Agent)

| Event | Payload | Description |
|-------|---------|-------------|
| `UserInputSubmitted` | { text, attachments?, context? } | User submits intent |
| `AssumptionResolved` | { assumptionId, resolution, newValue? } | User responds to assumption |
| `NodeSelected` | { nodeId, nodeType } | User selects canvas node |
| `JobRequested` | { jobType, parameters } | Explicit job request |
| `MCPApproved` | { mcpId, scopes[] } | User approves MCP connection |

#### AG-UI Messages (Agent → UI)

| Message | Payload | Description |
|---------|---------|-------------|
| `IntentDeciphered` | { originalInput, interpretedIntent, confidence } | Agent's understanding |
| `AssumptionsProposed` | { assumptions[] } | List for user reconciliation |
| `JobStatusUpdate` | { jobId, status, progress, message } | Streaming job progress |
| `ContentGenerated` | { contentType, content, placement? } | New content for canvas |
| `AgentStatusChanged` | { status, message? } | Agent state transition |

#### CopilotKit Integration

**CopilotKit Handles:**
- Contextual assistance (answering questions about canvas content)
- Action suggestions based on current context
- Assumption resolution guidance
- Quick queries (< 5 second responses)

**CopilotKit Does NOT Handle:**
- Executing destructive actions without approval
- Direct MCP configuration
- Modifying canvas without user awareness
- Long-running operations (> 10 seconds)

---

## 9) AI/Agent Design (PydanticAI via Gateway ONLY)

### 9.1 PydanticAI Usage Pattern

#### Agent Responsibilities

| Agent | Responsibilities |
|-------|------------------|
| IntentDecipherer | Parse user input, query intent index, generate assumptions |
| ResearchAgent | Execute deep research, aggregate sources, synthesize reports |
| PerspectiveAgent | Generate single perspective for LLM-as-judge |
| SynthesisAgent | Combine multiple perspectives into coherent analysis |
| RoutingAgent | Classify context, determine appropriate handler |

#### Tools/Functions Agents Can Call

| Tool Category | Examples |
|---------------|----------|
| Canvas Operations | createNode, updateNode, linkNodes, createDocument |
| MCP Invocation | queryCalendar, createEvent, searchDocs |
| Job Management | dispatchResearch, getJobStatus |
| Persistence | saveArtifact, queryIntentIndex |

#### Structured Outputs (Pydantic Models)

```python
class IntentAssumptions(BaseModel):
    original_input: str
    assumptions: List[Assumption]
    decomposed_intents: List[DecomposedIntent]
    confidence: float
    requires_clarification: bool

class Assumption(BaseModel):
    id: str
    text: str
    category: AssumptionCategory
    confidence: float
    blocking: bool
    suggested_action: Optional[str]

class ResearchReport(BaseModel):
    topic: str
    summary: str
    sources: List[Source]
    findings: List[Finding]
    perspectives: Optional[List[Perspective]]
```

#### Validation and Retries Strategy

1. **Schema Validation**: All agent outputs validated against Pydantic models
2. **Retry on Failure**: If validation fails, agent re-invoked with correction prompt
3. **Exponential Backoff**: Gateway errors trigger retry with 1s, 2s, 4s delays
4. **Max Retries**: 3 attempts before surfacing error to user

### 9.2 Gateway-Only Enforcement

**CRITICAL CONSTRAINT**: All PydanticAI inference goes through Pydantic AI Gateway ONLY.

#### How Code References Environment Variables

```python
# /backend/app/config.py
import os

# Environment variable names ONLY - never values
PYDANTIC_GATEWAY_API_KEY = os.getenv("PYDANTIC_GATEWAY_API_KEY")
XAI_API_KEY = os.getenv("XAI_API_KEY")

if not PYDANTIC_GATEWAY_API_KEY:
    raise EnvironmentError("PYDANTIC_GATEWAY_API_KEY must be set")

# /backend/app/gateway/client.py
from app.config import PYDANTIC_GATEWAY_API_KEY

class GatewayClient:
    def __init__(self):
        self.api_key = PYDANTIC_GATEWAY_API_KEY
        self.base_url = "https://api.pydantic.ai/gateway"
        # Gateway is free while in Beta
```

#### When/Why XAI_API_KEY is Used

- **Purpose**: Optional xAI Grok model integration via Gateway
- **Usage**: Passed to Gateway for model selection, not for direct API calls
- **Configuration**: Set in `.env`, referenced by name only

#### Configuration Layering (Local Dev vs Prod)

| Environment | Configuration |
|-------------|---------------|
| Local Dev | `.env` file with development keys |
| CI/Test | Environment variables set in CI |
| Production | Secrets manager (Vault, AWS Secrets, etc.) |

#### Failure Modes

| Failure | Handling |
|---------|----------|
| Gateway down | Retry with backoff; show user message after 3 failures |
| Invalid key | Fail fast on startup; clear error message |
| Rate limited | Retry with longer backoff; queue requests |
| Provider errors | Pass through error details; allow user retry |

### 9.3 Safety + Guardrails

#### Prompting Rules

1. **System prompts** include explicit constraints on allowed actions
2. **No external URLs** in agent outputs unless from trusted sources
3. **No code execution** without user approval
4. **Factual claims** should cite sources where possible

#### Data Redaction Rules

1. **PII Detection**: Warn user before sending potentially sensitive info to Gateway
2. **Secrets Scanning**: Never log or persist API keys, passwords
3. **User Data**: Redact from logs, anonymize in metrics

#### Logging Rules

1. **No secrets** in logs (validated by linting)
2. **Correlation IDs** for request tracing
3. **Structured JSON** format for parsing
4. **Log levels**: DEBUG for dev, INFO for prod

#### Allowed/Disallowed Actions

| Allowed | Disallowed |
|---------|------------|
| Create/update canvas elements | Delete without confirmation |
| Create jobs | Cancel running jobs without confirmation |
| Read MCP data | Write to external systems without confirmation |
| Generate suggestions | Execute suggestions automatically |

#### Action Classification Matrix

| Domain | Safe (No Confirm) | Needs Confirm | Blocked |
|--------|-------------------|---------------|---------|
| Canvas | create_node, update_label, move | delete_node, clear_canvas | - |
| Documents | create, update | delete | - |
| Jobs | create, query | cancel | delete_history |
| MCP | query_* | write_*, send_* | configure_global |
| External | - | calendar_create, email_draft | email_send_bulk |

**Novel Action Handling**:
- Extract action verb and target from tool call
- If verb in [delete, remove, clear, send, upload]: Needs Confirm
- If target in [system, config, external]: Needs Confirm
- Default: Safe

---

## 10) Dependency Plan

| Dependency | Purpose | Where Used | Version Strategy | Risk/Notes | Documentation |
|------------|---------|------------|------------------|------------|---------------|
| **PydanticAI** | Agent framework with structured outputs | `/backend/app/agents/`, `/backend/app/gateway/` | Pin major.minor | **GATEWAY-ONLY**: Must use Gateway API. Gateway free in Beta. | https://ai.pydantic.dev/ |
| **AG-UI** | Agent-UI interaction protocol | `/frontend/src/agui/`, `/backend/app/agui/` | Pin major | Relatively new; docs evolving | https://docs.ag-ui.com/ |
| **CopilotKit** | Copilot-style in-app assistance | `/frontend/src/copilot/` | Pin major.minor | React-only; tight coupling | https://docs.copilotkit.ai/ |
| **FastAPI** | Backend web framework | `/backend/app/api/` | Pin major.minor | Well-established; minimal risk | https://fastapi.tiangolo.com/ |
| **Next.js** | Frontend React framework | `/frontend/` | Pin major | Standard choice | https://nextjs.org/docs |
| **Zustand** | Frontend state management | `/frontend/src/state/` | Pin major.minor | Lightweight | https://github.com/pmndrs/zustand |
| **PostgreSQL** | Primary database | `/backend/app/persistence/` | 14+ | Mature; JSON support | https://postgresql.org/docs |
| **Redis** | Job queue, caching | `/backend/app/jobs/` | 6+ | Optional for MVP | https://redis.io/docs |
| **Celery** | Background job processing | `/backend/app/jobs/` | Pin major.minor | Alternative: ARQ | https://docs.celeryq.dev/ |
| **httpx** | Async HTTP client | `/backend/app/gateway/` | Pin major.minor | For Gateway requests | https://www.python-httpx.org/ |
| **Pydantic** | Data validation | `/backend/app/domain/models/` | v2.x | Core dependency | https://docs.pydantic.dev/ |
| **Alembic** | Database migrations | `/backend/migrations/` | Pin major.minor | For schema evolution | https://alembic.sqlalchemy.org/ |
| **Tiptap** | Rich text editor | `/frontend/src/components/Canvas/` | Pin major | For document blocks | https://tiptap.dev/ |
| **D3.js** | Graph visualization | `/frontend/src/components/Canvas/` | Pin major | For graph/DAG views | https://d3js.org/ |

---

## 11) Repo + Dev Setup Specification

### Proposed Repository Structure

```
intentuimvp/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Canvas/
│   │   │   ├── primitives/
│   │   │   ├── ContextInput/
│   │   │   ├── Assumptions/
│   │   │   └── TaskDAG/
│   │   ├── state/
│   │   ├── services/
│   │   ├── agui/
│   │   ├── copilot/
│   │   ├── hooks/
│   │   └── styles/
│   ├── public/
│   ├── package.json
│   └── next.config.js
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── agents/
│   │   ├── context/
│   │   ├── orchestration/
│   │   ├── gateway/
│   │   ├── jobs/
│   │   ├── mcp/
│   │   ├── persistence/
│   │   ├── safety/
│   │   ├── ws/
│   │   ├── domain/
│   │   │   ├── models/
│   │   │   └── services/
│   │   └── agui/
│   ├── migrations/
│   ├── tests/
│   ├── pyproject.toml
│   └── alembic.ini
├── docs/
│   ├── architecture.md
│   ├── domain-model.md
│   ├── agent-design.md
│   ├── ag-ui-integration.md
│   ├── copilotkit-integration.md
│   ├── runbook.md
│   └── security-secrets.md
├── .env.example
├── docker-compose.yml
├── README.md
└── PRD.md
```

### Tooling

| Tool | Purpose | Configuration |
|------|---------|---------------|
| **Formatter (Python)** | Ruff | `pyproject.toml` |
| **Formatter (JS/TS)** | Prettier | `.prettierrc` |
| **Linter (Python)** | Ruff | `pyproject.toml` |
| **Linter (JS/TS)** | ESLint | `.eslintrc.js` |
| **Type Checking (Python)** | Pyright | `pyrightconfig.json` |
| **Type Checking (JS/TS)** | TypeScript | `tsconfig.json` |
| **Test Framework (Python)** | Pytest | `pyproject.toml` |
| **Test Framework (JS/TS)** | Vitest | `vitest.config.ts` |
| **Env Management** | python-dotenv | `.env` files |

### Local Setup Steps (No Secrets)

```bash
# 1. Clone repository
git clone <repo-url>
cd intentuimvp

# 2. Copy environment template
cp .env.example .env
# Edit .env to add your API keys (not committed)

# 3. Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -e ".[dev]"

# 4. Run database migrations
alembic upgrade head

# 5. Frontend setup
cd ../frontend
npm install

# 6. Start development servers
# Terminal 1: Backend
cd backend && uvicorn app.main:app --reload

# Terminal 2: Frontend
cd frontend && npm run dev
```

### .env.example Contents (Names Only)

```bash
# Pydantic AI Gateway (REQUIRED)
# Gateway is free while in Beta
PYDANTIC_GATEWAY_API_KEY=

# Optional: xAI Grok integration via Gateway
XAI_API_KEY=

# Database
DATABASE_URL=postgresql://localhost:5432/intentui

# Redis (for job queue)
REDIS_URL=redis://localhost:6379

# Application
SECRET_KEY=
DEBUG=false
```

### CI Expectations

| Check | Tool | Pass Criteria |
|-------|------|---------------|
| Lint (Python) | Ruff | No errors |
| Lint (JS/TS) | ESLint | No errors |
| Type Check (Python) | Pyright | No errors |
| Type Check (JS/TS) | TypeScript | No errors |
| Unit Tests (Python) | Pytest | 100% pass |
| Unit Tests (JS/TS) | Vitest | 100% pass |
| Secret Scanning | gitleaks | No secrets detected |

---

## 12) Data Storage

### What Data is Stored

| Data Type | Fields | Purpose |
|-----------|--------|---------|
| **Canvas State** | id, userId, name, nodes[], documents[], audioBlocks[], positions, createdAt, updatedAt | Persist workspace across sessions |
| **Node** | id, canvasId, type, label, position, linkedIds, metadata | Individual canvas elements |
| **Document** | id, canvasId, title, content, contentType, version | Text/markdown content |
| **AudioBlock** | id, canvasId, audioUri, transcription, duration, status | Voice notes with transcripts |
| **Job** | id, type, status, input, result, progress, createdAt, completedAt | Async task tracking |
| **Artifact** | id, jobId, type, content, metadata | Job outputs (research reports) |
| **Assumption** | id, sessionId, text, confidence, status, resolution | Intent reconciliation |
| **IntentIndex** | id, userId, patterns[], definitions[], preferences | Learning user patterns |
| **MCPConfig** | id, userId, serverId, config, status | MCP server configurations |
| **Session** | id, userId, canvasId, createdAt, lastActivityAt | User session tracking |

### Why Data is Stored

- **Canvas State**: Core value proposition - persistent workspace
- **Jobs/Artifacts**: Enable async operations and result retrieval
- **Intent Index**: Improve assumption accuracy over time
- **Sessions**: Track activity, enable state restoration

### Where Data is Stored

| Data | Storage | Rationale |
|------|---------|-----------|
| Structured data | PostgreSQL | ACID compliance, JSON support, mature |
| Large artifacts | PostgreSQL (or S3 for prod) | MVP simplicity |
| Job state | Redis | Fast access, TTL support |
| Audit logs | PostgreSQL | Queryable history |

### Migration Strategy (MVP-Simple)

1. **Alembic** for schema migrations
2. **Version tracking** in `alembic_version` table
3. **Forward-only migrations** for MVP (rollback tested but not required)
4. **Data migrations** as Python scripts when needed

### Retention Rules

| Data Type | Retention |
|-----------|-----------|
| Canvas State | Indefinite (user-owned) |
| Jobs | 90 days after completion |
| Artifacts | Indefinite (user can delete) |
| Sessions | 30 days inactive |
| Audit Logs | 1 year |

---

## 13) Analytics + Success Metrics

### North Star Metric

**Weekly Active Canvas Hours**: Total hours users spend actively working in IntentUI workspaces per week. This measures both adoption and engagement depth.

### Supporting Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| Task Completion Rate | % of user intents successfully executed | > 80% |
| Assumption Accuracy | % of assumptions accepted without modification | > 70% |
| Time to First Value | Time from signup to first meaningful action | < 5 minutes |
| Research Job Success | % of research jobs completing successfully | > 75% |
| Session Continuity | % of sessions resuming previous canvas | > 60% |
| Command/Chat Ratio | Ratio of commands to chat-style interactions | > 3:1 |
| MCP Adoption | % of users with at least one MCP configured | > 30% |

### Event Tracking Plan (Minimal)

| Event | Properties | Purpose |
|-------|------------|---------|
| `workspace.opened` | workspaceId, isNewSession | Track session starts |
| `context.submitted` | contextType, length | Track input patterns |
| `assumption.resolved` | assumptionId, resolution, timeToResolve | Track reconciliation effectiveness |
| `job.created` | jobType | Track job usage |
| `job.completed` | jobId, duration, success | Track job performance |
| `node.created` | nodeType | Track canvas usage |
| `mcp.configured` | mcpType | Track MCP adoption |
| `error.occurred` | errorType, context | Track reliability issues |

---

## 14) Risks + Mitigations

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Gateway Beta Reliability** | Medium | High | Retry logic, graceful degradation, fallback messaging |
| **State Complexity** | High | High | Single-user MVP, robust state machine, incremental persistence |
| **MCP Integration Brittleness** | Medium | Medium | Security validation, graceful degradation, retry logic |
| **Context Routing Accuracy** | Medium | High | Confidence thresholds, fallback to user disambiguation |
| **Real-time Performance** | Medium | Medium | Canvas virtualization, pagination, performance budgets |
| **LLM Cost/Latency** | High | Medium | Caching, model tiering, efficient prompts |

### Product Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Paradigm Rejection** | Medium | High | Onboarding tutorial, optional chat-mode fallback |
| **Scope Creep** | High | High | Strict MVP definition, defer non-core features |
| **Unclear Value Prop** | Medium | Medium | Clear messaging, demo videos, guided first-run |
| **Power User Niche** | Medium | Medium | Design for power users first, simplify later |

### Security Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Secret Exposure** | Low | Critical | Environment variables only, secret scanning, no hardcoding |
| **Agent Hallucination** | Medium | High | Safety guardrails, action blocking, confirmation for destructive actions |
| **MCP Vulnerabilities** | Medium | Medium | Security validation, allowlist pattern, capability scoping |
| **Prompt Injection** | Medium | Medium | Input sanitization, structured outputs, action constraints |

---

## 15) Open Questions + Validation Questions

### Assumptions Made

| ID | Assumption | Impact | Risk |
|----|------------|--------|------|
| A-001 | PostgreSQL as primary database | Affects persistence layer | Low - can migrate |
| A-002 | Next.js + React for frontend | Affects UI development | Low - standard choice |
| A-003 | Single-user MVP (no multi-tenancy) | Reduces complexity | Medium - architecture change for multi-user |
| A-004 | Command syntax is natural language with slash shortcuts | Affects intent deciphering | Medium - may need refinement |
| A-005 | Audio transcription via external service (Whisper) | Affects audio pipeline | Low - can swap providers |
| A-006 | LLM-as-judge uses single LLM with structured prompts | Simplifies MVP | Low - can extend to multi-LLM |
| A-007 | Celery + Redis for job queue | Affects async infrastructure | Low - alternatives available |
| A-008 | Cloud storage for persistence (not local-first) | Affects architecture | Medium - local-first is different |

### Validation Questions

1. **Database**: Is PostgreSQL the preferred persistence layer, or is SQLite/local-first preferred?
2. **Multi-user**: Is single-user sufficient for MVP, or is multi-tenancy required?
3. **Scale**: What is expected concurrent user count and canvas size?
4. **Audio**: Should transcription be real-time or batch-processed?
5. **MCP**: Which MCP servers beyond Google Calendar are required for MVP?
6. **Auth**: What authentication strategy (OAuth, API keys, none for alpha)?
7. **Backup**: Should backup support Git-style, DB snapshot, or both?
8. **Response Time**: What is the target latency for intent deciphering?
9. **Model Selection**: Are there required LLM models via Gateway?
10. **Offline**: Is any offline capability needed for MVP?

---

## 16) Backlog for BMAD (Epics → Stories → Tasks)

### 16.1 Epics

| Epic ID | Title | Description | Exit Criteria |
|---------|-------|-------------|---------------|
| E-001 | Core Workspace Infrastructure | Canvas shell, state management, WebSocket, AG-UI, CopilotKit | Canvas renders, state persists, real-time works |
| E-002 | Context Input & Intent Deciphering | Text input, audio blocks, intent processing, assumptions UI | User input processed, assumptions shown and resolvable |
| E-003 | Agent Orchestration & Gateway | PydanticAI Gateway client, agent base, orchestrator, safety | Agents work via Gateway, safety enforced |
| E-004 | Canvas & Visual Components | Nodes, edges, documents, graphs, annotations, Task DAG | Visual components functional and persistable |
| E-005 | Job System (Deep Research) | Job queue, deep research, streaming, LLM-as-judge | Research jobs complete with streaming updates |
| E-006 | MCP Integration | MCP registry, client, Google Calendar, security, dynamic add | MCP framework works with Calendar integration |
| E-007 | Persistence Layer | Canvas state, preferences, migrations, backup | All state persists across sessions |

### 16.2 Stories (Summary)

**Epic E-001: Core Workspace Infrastructure**
- S-001: Canvas Shell Setup
- S-002: Global State Management
- S-003: WebSocket Infrastructure
- S-004: AG-UI Protocol Integration
- S-005: CopilotKit Base Integration
- S-006: Base Component Library

**Epic E-002: Context Input & Intent Deciphering**
- S-007: Text Input Box Component
- S-008: Context Routing Pipeline
- S-009: Intent Deciphering Agent
- S-010: Assumptions Data Structure
- S-011: Assumptions UI Panel
- S-012: User Intent/Meaning Index
- S-013: Audio Block Transcription

**Epic E-003: Agent Orchestration & Gateway**
- S-014: PydanticAI Gateway Client
- S-015: Agent Base Class
- S-016: Agent Orchestrator
- S-017: Safety Guardrails
- S-018: Structured Output Validation

**Epic E-004: Canvas & Visual Components**
- S-019: Node Component
- S-020: Edge/Connection Component
- S-021: Document Block Component
- S-022: Graph Visualization
- S-023: Annotation Layer
- S-024: Task DAG Visualization

**Epic E-005: Job System (Deep Research)**
- S-025: Job Queue Infrastructure
- S-026: Deep Research Job Type
- S-027: Job Progress Streaming
- S-028: LLM-as-Judge Workflow
- S-029: Job Artifact Storage

**Epic E-006: MCP Integration**
- S-030: MCP Registry
- S-031: MCP Client Adapter
- S-032: Google Calendar MCP Integration
- S-033: MCP Security Validation
- S-034: Dynamic MCP Addition

**Epic E-007: Persistence Layer**
- S-035: Canvas State Persistence
- S-036: User Preferences Storage
- S-037: Database Migrations
- S-038: Backup/Export System

*See BACKLOG.md for complete story details with acceptance criteria and task breakdowns.*

### 16.3 Task Breakdown

Total: **176 engineering tasks** across 38 stories. Each task includes:
- Task ID (T-001 through T-176)
- Description
- File/module hints
- Dependencies

*See BACKLOG.md for complete task breakdown.*

---

## 17) Documentation Plan

### Required Documentation

| Document | Path | What It Explains | Audience | Definition of Done |
|----------|------|------------------|----------|-------------------|
| **Architecture** | `/docs/architecture.md` | High-level system architecture, component diagram, data flow | Dev, Ops | Diagrams accurate, all major components documented |
| **Domain Model** | `/docs/domain-model.md` | DDD model: contexts, entities, aggregates, events | Dev | All domain concepts defined with examples |
| **Agent Design** | `/docs/agent-design.md` | Agent responsibilities, Gateway usage, structured outputs | Dev | All agents documented with examples |
| **AG-UI Integration** | `/docs/ag-ui-integration.md` | AG-UI event/message model, state sync | Dev | All events/messages documented |
| **CopilotKit Integration** | `/docs/copilotkit-integration.md` | Copilot actions, context, constraints | Dev | Integration points documented |
| **Runbook** | `/docs/runbook.md` | Operations guide: deployment, monitoring, troubleshooting | Ops | All operational procedures covered |
| **Security & Secrets** | `/docs/security-secrets.md` | Secrets management, Gateway-only enforcement, guardrails | Dev, Ops | All security measures documented |

### Documentation Standards

Each document must answer:
- **Where**: File/module locations
- **What**: Purpose and functionality
- **How**: Implementation details
- **Why**: Design rationale

---

## FINAL CHECKLIST

- [x] **No secret keys or values included anywhere** (only env var names: `PYDANTIC_GATEWAY_API_KEY`, `XAI_API_KEY`)
- [x] **Gateway-only is explicitly enforced** and repeated in: Executive Summary, Section 9, Section 10, Section 11
- [x] **Every major module answers Where/What/How/Why** (Section 8.2)
- [x] **Requirements have acceptance criteria** (Section 5, Given/When/Then format)
- [x] **Backlog is detailed enough for BMAD** (7 epics, 38 stories, 176 tasks)
- [x] **Dependencies are justified and minimal** (Section 10)
- [x] **Assumptions are labeled** and **open questions listed** (Section 15)

---

*PRD generated from brain dump using Opus 4.5 with subagent extraction and reconciliation pattern.*
