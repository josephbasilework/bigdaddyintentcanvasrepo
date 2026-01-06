# IntentUI MVP - BMAD-Ready Backlog

**Version**: 1.0.0
**Date**: 2026-01-03
**Status**: Draft
**Author**: Backlog-Builder Agent

---

## 1. EPIC LIST

### E-001: Core Workspace Infrastructure

**Description**: Establish the foundational canvas-based workspace that provides a stateful, persistent, and interactive environment distinct from traditional chatbot interfaces. This epic covers the core UI shell, state management patterns, and the fundamental architecture that all other features will build upon.

**Exit Criteria**:
- Canvas workspace renders and is navigable
- Global state store is operational with persistence hooks
- WebSocket infrastructure is established for real-time updates
- Base component library (nodes, containers, panels) is functional
- AG-UI protocol integration is working for agent-UI communication
- CopilotKit base integration is operational

---

### E-002: Context Input & Intent Deciphering

**Description**: Build the context ingestion system including text input, audio blocks, and file attachments. Implement the intent/meaning deciphering pipeline that parses user input, makes assumptions, and reconciles with the user before taking action.

**Exit Criteria**:
- Text input box captures user context and sends to processing pipeline
- Audio block transcription (via Whisper/external service) is functional
- Intent deciphering agent produces structured assumption output
- Assumptions UI renders for user confirmation/rejection
- User intent/meaning index is persisted and queryable
- Context is decomposed granularly without information loss

---

### E-003: Agent Orchestration & Gateway Integration

**Description**: Implement the PydanticAI agent system exclusively through the Gateway API. Build the agent orchestration layer that routes context to appropriate agents/workflows, manages agent lifecycles, and enforces safety guardrails.

**Exit Criteria**:
- PydanticAI agents connect exclusively via Gateway API
- Environment variables (PYDANTIC_GATEWAY_API_KEY, XAI_API_KEY) are properly utilized
- Agent orchestrator routes context to appropriate handlers
- Structured outputs via Pydantic models are validated
- Retry and fallback strategies are implemented
- Agent safety guardrails prevent destructive actions

---

### E-004: Canvas & Visual Components

**Description**: Build the visual representation layer including nodes, graphs, documents, annotations, and spatial layout. Enable users to create, position, and interact with visual elements that augment their working memory.

**Exit Criteria**:
- Nodes can be created, positioned, labeled, and connected
- Documents/text blocks render on canvas with CRUD operations
- Audio blocks display with playback and transcription state
- Graph visualization shows relationships between nodes
- Annotations can be added to any canvas element
- Spatial positioning persists across sessions

---

### E-005: Job System (Deep Research)

**Description**: Implement the asynchronous job system for long-running tasks like deep research reports. Include WebSocket streaming for real-time progress updates, LLM-as-judge patterns for multi-perspective analysis, and artifact persistence.

**Exit Criteria**:
- Deep research jobs can be dispatched and tracked
- WebSocket streaming delivers real-time progress updates to UI
- LLM-as-judge workflow produces multiple perspectives
- Perspective synthesis combines multiple viewpoints
- Job artifacts (reports, analyses) persist and are referenceable
- Jobs can be triggered from canvas context or text input

---

### E-006: MCP Integration

**Description**: Build the Model Context Protocol integration layer enabling modular, configurable connections to external services. Implement security checks for MCP additions and self-modifying workflow capabilities.

**Exit Criteria**:
- MCP server registry allows configuration of available MCPs
- Google Calendar MCP integration works end-to-end
- Security checks validate MCP additions against standards
- MCPs can be added/removed within active sessions
- Agent tools dynamically reflect available MCP capabilities
- MCP errors are handled gracefully with user feedback

---

### E-007: Persistence Layer

**Description**: Implement the data persistence layer for workspace state, user preferences, intent index, and artifacts. Support both structured storage and potential Obsidian/Git-style backup options.

**Exit Criteria**:
- Canvas state persists and restores across sessions
- User intent/meaning index is stored and queryable
- Job artifacts and deep research reports are persisted
- MCP configurations persist per user/workspace
- Task DAGs are stored with full history
- Backup/export functionality is available (Git-style or DB)

---

## 2. STORY LIST WITH ACCEPTANCE CRITERIA

---

### Epic E-001: Core Workspace Infrastructure

#### S-001: Canvas Shell Setup

**Title**: Initialize Canvas Workspace Shell

**User Story**: As a power user, I want a canvas-based workspace that loads instantly, so that I can begin my high-velocity knowledge work without waiting.

**Acceptance Criteria**:
- **Given** the application is accessed via browser
  **When** the workspace URL is loaded
  **Then** a blank canvas renders within 2 seconds with a floating text input box

- **Given** the canvas is loaded
  **When** the user inspects the page
  **Then** no API keys or secrets are visible in client-side code

- **Given** the canvas is loaded
  **When** the user resizes the browser window
  **Then** the canvas and components adapt responsively

**Implementation Notes**:
- **Where**: `/frontend/src/components/Canvas/` - React/Next.js component
- **What**: Main canvas container, viewport management, zoom/pan controls
- **How**: Use React with canvas libraries (react-flow or custom SVG-based), implement viewport state
- **Why**: Foundation for all visual interactions; must be performant for high-throughput use

**Test Notes**:
- Unit test canvas render and viewport calculations
- E2E test initial load time < 2 seconds
- Visual regression test for responsive behavior

---

#### S-002: Global State Management

**Title**: Implement Global State Store

**User Story**: As a power user, I want my workspace state to be consistent and reactive, so that changes I make or agents make are immediately reflected everywhere.

**Acceptance Criteria**:
- **Given** a state change occurs (user or agent action)
  **When** the change is committed to the store
  **Then** all subscribed components re-render within 100ms

- **Given** the application has state
  **When** a new component subscribes to state
  **Then** it receives the current state immediately

- **Given** multiple rapid state changes occur
  **When** changes are batched
  **Then** the UI remains responsive without jank

**Implementation Notes**:
- **Where**: `/frontend/src/state/` - Zustand or Redux store
- **What**: Global store for canvas, nodes, jobs, user preferences
- **How**: Zustand with immer for immutable updates; selectors for performance
- **Why**: Central state enables agent-UI sync and persistence layer integration

**Test Notes**:
- Unit test state transitions
- Performance test batch update scenarios
- Integration test with persistence hooks

---

#### S-003: WebSocket Infrastructure

**Title**: Establish WebSocket Connection Layer

**User Story**: As a power user, I want real-time updates from background jobs, so that I see progress without refreshing the page.

**Acceptance Criteria**:
- **Given** the application loads
  **When** WebSocket connection is established
  **Then** a persistent connection is maintained with heartbeat

- **Given** a WebSocket message arrives
  **When** it contains state update payload
  **Then** the global state is updated and UI reflects changes

- **Given** the WebSocket connection drops
  **When** reconnection is attempted
  **Then** the connection restores within 5 seconds with exponential backoff

**Implementation Notes**:
- **Where**: `/frontend/src/services/websocket.ts`, `/backend/app/ws/`
- **What**: WebSocket client and server, message routing, reconnection logic
- **How**: FastAPI WebSocket endpoints, frontend WebSocket service with reconnection
- **Why**: Enables streaming job updates, agent responses, collaborative state sync

**Test Notes**:
- Unit test message parsing
- Integration test connection lifecycle
- Chaos test connection drop/restore scenarios

---

#### S-004: AG-UI Protocol Integration

**Title**: Integrate AG-UI Protocol for Agent-UI Communication

**User Story**: As a power user, I want seamless agent-UI interaction following standard patterns, so that agent responses render predictably and correctly.

**Acceptance Criteria**:
- **Given** an agent produces an AG-UI event
  **When** the event is received by the UI
  **Then** the appropriate UI update handler is invoked

- **Given** the UI needs to send user input to an agent
  **When** the input is dispatched
  **Then** it follows AG-UI message format

- **Given** an agent streams partial output
  **When** tokens arrive
  **Then** they render incrementally in the UI

**Implementation Notes**:
- **Where**: `/frontend/src/agui/`, `/backend/app/agui/`
- **What**: AG-UI event handlers, message formatters, state reconciliation
- **How**: Follow AG-UI protocol spec for events/messages; integrate with state store
- **Why**: Standardized agent-UI contract prevents custom glue code proliferation

**Test Notes**:
- Unit test event parsing and handling
- Integration test full message round-trip
- Contract test against AG-UI spec

---

#### S-005: CopilotKit Base Integration

**Title**: Integrate CopilotKit for Copilot-Style Assistance

**User Story**: As a power user, I want a copilot interface embedded in my workspace, so that I can get contextual assistance without leaving the canvas.

**Acceptance Criteria**:
- **Given** CopilotKit is initialized
  **When** the workspace loads
  **Then** the copilot panel is available and responsive

- **Given** the user triggers copilot assistance
  **When** context is sent
  **Then** relevant suggestions or actions are returned

- **Given** the copilot suggests an action
  **When** the user approves
  **Then** the action is executed on the canvas

**Implementation Notes**:
- **Where**: `/frontend/src/copilot/`, integrate with CopilotKit SDK
- **What**: CopilotKit provider, action definitions, context providers
- **How**: CopilotKit React components; define actions that map to canvas operations
- **Why**: Provides discoverable, contextual AI assistance within the workspace

**Test Notes**:
- Integration test CopilotKit initialization
- E2E test user triggers copilot and receives response
- Test action execution on approval

---

#### S-006: Base Component Library

**Title**: Create Base Canvas Component Library

**User Story**: As a developer, I want reusable canvas components, so that I can build features quickly without reimplementing primitives.

**Acceptance Criteria**:
- **Given** a developer needs to add a node
  **When** they use the Node component
  **Then** it renders with standard styling and interaction handlers

- **Given** a component is created
  **When** it is rendered
  **Then** it has consistent visual styling matching design system

- **Given** a component needs custom behavior
  **When** props are passed
  **Then** the component adapts without breaking base functionality

**Implementation Notes**:
- **Where**: `/frontend/src/components/primitives/`
- **What**: Node, Edge, Panel, Container, TextBlock, AudioBlock components
- **How**: Composable React components with TypeScript props; Tailwind/CSS-in-JS styling
- **Why**: Consistency and velocity; prevents UI fragmentation

**Test Notes**:
- Storybook stories for each component
- Unit test prop variations
- Visual regression tests

---

### Epic E-002: Context Input & Intent Deciphering

#### S-007: Text Input Box Component

**Title**: Implement Floating Text Input Box

**User Story**: As a power user, I want a persistent text input box on my canvas, so that I can inject context and commands at any time.

**Acceptance Criteria**:
- **Given** the canvas is loaded
  **When** the user views the workspace
  **Then** a floating text input box is visible and focused

- **Given** the user types in the text box
  **When** they press Enter
  **Then** the input is sent to the context routing pipeline

- **Given** the user is typing
  **When** they drag files onto the text box
  **Then** the files are attached to the context payload

**Implementation Notes**:
- **Where**: `/frontend/src/components/ContextInput/TextInput.tsx`
- **What**: Floating text input, file drop zone, submit handler
- **How**: React component with drag-drop support; dispatch to context router
- **Why**: Primary context ingestion point; must be always accessible

**Test Notes**:
- Unit test input capture and submission
- E2E test file drag-drop
- Accessibility test keyboard navigation

---

#### S-008: Context Routing Pipeline

**Title**: Build Context Router for Input Processing

**User Story**: As a power user, I want my input intelligently routed, so that the right agent or workflow handles my request.

**Acceptance Criteria**:
- **Given** context is submitted
  **When** the router receives it
  **Then** it dispatches to the intent deciphering agent

- **Given** context has multiple intents
  **When** decomposition occurs
  **Then** each intent is routed independently

- **Given** context references existing canvas elements
  **When** routing occurs
  **Then** element context is included in the payload

**Implementation Notes**:
- **Where**: `/backend/app/context/router.py`
- **What**: Context router, intent classifier, dispatch logic
- **How**: PydanticAI agent for classification; rule-based routing fallback
- **Why**: Intelligent delegation prevents single-agent bottleneck

**Test Notes**:
- Unit test routing logic
- Integration test with intent deciphering
- Test multi-intent decomposition

---

#### S-009: Intent Deciphering Agent

**Title**: Implement Intent/Meaning Deciphering Agent

**User Story**: As a power user, I want the system to understand what I mean, so that it takes the right action even when I'm vague.

**Acceptance Criteria**:
- **Given** raw user input
  **When** processed by the deciphering agent
  **Then** structured assumptions are produced

- **Given** the user intent index exists
  **When** deciphering occurs
  **Then** historical patterns inform the assumptions

- **Given** available tools/capabilities
  **When** assumptions are made
  **Then** they reference feasible actions only

**Implementation Notes**:
- **Where**: `/backend/app/agents/intent_decipherer.py`
- **What**: PydanticAI agent, assumption schema, capability matcher
- **How**: Gateway API call with structured output; query intent index
- **Why**: Core value proposition - understanding user intent accurately

**Test Notes**:
- Unit test assumption schema validation
- Integration test with intent index
- Prompt regression tests for accuracy

---

#### S-010: Assumptions Data Structure

**Title**: Define Assumptions Data Structure

**User Story**: As a developer, I want a clear data structure for assumptions, so that they can be rendered, approved, and acted upon consistently.

**Acceptance Criteria**:
- **Given** an assumption is created
  **When** it is serialized
  **Then** it includes intent, confidence, suggested action, and clarifying questions

- **Given** multiple assumptions exist
  **When** they are grouped
  **Then** they maintain order and association to original input

- **Given** an assumption has dependencies
  **When** rendered
  **Then** dependencies are visible

**Implementation Notes**:
- **Where**: `/backend/app/domain/models/assumption.py`
- **What**: Pydantic models for Assumption, AssumptionGroup, AssumptionResolution
- **How**: Pydantic BaseModel with validation; enum for confidence levels
- **Why**: Explicit data contract between agents and UI

**Test Notes**:
- Unit test model validation
- Serialization round-trip tests
- Schema evolution tests

---

#### S-011: Assumptions UI Panel

**Title**: Build Assumptions UI for User Confirmation

**User Story**: As a power user, I want to see and approve assumptions, so that I control what actions the system takes.

**Acceptance Criteria**:
- **Given** assumptions are generated
  **When** rendered in UI
  **Then** each assumption shows intent, confidence, and approve/reject buttons

- **Given** the user approves an assumption
  **When** clicking approve
  **Then** the associated action is dispatched

- **Given** the user rejects an assumption
  **When** clicking reject
  **Then** the assumption is discarded and optional feedback is captured

**Implementation Notes**:
- **Where**: `/frontend/src/components/Assumptions/AssumptionPanel.tsx`
- **What**: Assumption cards, approval buttons, feedback input
- **How**: React component subscribed to assumptions state; dispatch actions on approval
- **Why**: User reconciliation prevents unwanted actions

**Test Notes**:
- E2E test approval flow
- Unit test button actions
- Accessibility test screen reader support

---

#### S-012: User Intent/Meaning Index

**Title**: Implement Persisted User Intent Index

**User Story**: As a power user, I want the system to learn my patterns, so that assumptions improve over time.

**Acceptance Criteria**:
- **Given** an assumption is approved
  **When** stored
  **Then** it is indexed by intent type and outcome

- **Given** a new input is received
  **When** similar patterns exist in index
  **Then** higher confidence assumptions are made

- **Given** the index is queried
  **When** results are returned
  **Then** relevance scoring is applied

**Implementation Notes**:
- **Where**: `/backend/app/domain/services/intent_index.py`, `/backend/app/persistence/intent_store.py`
- **What**: Intent index service, storage adapter, query interface
- **How**: Vector storage (optional) or keyword index; persistence to DB
- **Why**: Learning from user behavior improves accuracy over time

**Test Notes**:
- Unit test indexing logic
- Integration test query accuracy
- Performance test index growth

---

#### S-013: Audio Block Transcription

**Title**: Implement Audio Block Capture and Transcription

**User Story**: As a power user, I want to record audio notes on the canvas, so that I can capture thoughts quickly without typing.

**Acceptance Criteria**:
- **Given** the user creates an audio block
  **When** they record audio
  **Then** the recording is captured and stored

- **Given** an audio block has a recording
  **When** transcription is triggered
  **Then** the transcript is generated and stored with the block

- **Given** an audio block has a transcript
  **When** viewed
  **Then** the transcript is displayed and searchable

**Implementation Notes**:
- **Where**: `/frontend/src/components/Canvas/AudioBlock.tsx`, `/backend/app/services/transcription.py`
- **What**: Audio recorder component, transcription service (Whisper API or similar)
- **How**: MediaRecorder API for capture; async transcription job
- **Why**: Supports rapid context capture for high-velocity workflows

**Test Notes**:
- E2E test record and playback
- Integration test transcription pipeline
- Unit test transcript storage

---

### Epic E-003: Agent Orchestration & Gateway Integration

#### S-014: PydanticAI Gateway Client

**Title**: Implement PydanticAI Gateway API Client

**User Story**: As a developer, I want a single client for all LLM inference, so that all calls go through the Gateway consistently.

**Acceptance Criteria**:
- **Given** an agent needs inference
  **When** it invokes the client
  **Then** the request goes to Pydantic AI Gateway only

- **Given** PYDANTIC_GATEWAY_API_KEY is set
  **When** the client initializes
  **Then** authentication is configured correctly

- **Given** the Gateway returns an error
  **When** handled
  **Then** appropriate retries and fallback occur

**Implementation Notes**:
- **Where**: `/backend/app/gateway/client.py`
- **What**: Gateway HTTP client, auth config, error handling
- **How**: httpx async client; retry with exponential backoff; structured error types
- **Why**: Gateway-only is a hard constraint; centralizes LLM access

**Test Notes**:
- Unit test client construction
- Integration test with Gateway (mocked)
- Error scenario tests

---

#### S-015: Agent Base Class

**Title**: Create PydanticAI Agent Base Class

**User Story**: As a developer, I want a base agent class, so that I can build new agents quickly with consistent patterns.

**Acceptance Criteria**:
- **Given** a new agent is needed
  **When** extending the base class
  **Then** Gateway client and structured output are pre-configured

- **Given** an agent produces output
  **When** validated
  **Then** Pydantic models enforce schema

- **Given** an agent needs tools
  **When** defined
  **Then** they are registered and invocable

**Implementation Notes**:
- **Where**: `/backend/app/agents/base.py`
- **What**: BaseAgent class, tool registration, output validation
- **How**: PydanticAI agent patterns; dependency injection for Gateway client
- **Why**: Consistency and reduced boilerplate for agent development

**Test Notes**:
- Unit test base class functionality
- Test tool registration
- Test output validation

---

#### S-016: Agent Orchestrator

**Title**: Build Agent Orchestrator Service

**User Story**: As a power user, I want my requests handled by the right agents, so that I get specialized responses.

**Acceptance Criteria**:
- **Given** a context payload arrives
  **When** processed by orchestrator
  **Then** appropriate agent(s) are invoked

- **Given** multiple agents could handle a request
  **When** selection occurs
  **Then** the most appropriate is chosen based on capability matching

- **Given** an agent fails
  **When** fallback is configured
  **Then** alternative handling occurs

**Implementation Notes**:
- **Where**: `/backend/app/orchestration/orchestrator.py`
- **What**: Orchestrator service, agent registry, capability matching
- **How**: Registry pattern; capability tags on agents; routing rules
- **Why**: Modular agent system requires intelligent coordination

**Test Notes**:
- Unit test routing logic
- Integration test agent invocation
- Fallback scenario tests

---

#### S-017: Safety Guardrails

**Title**: Implement Agent Safety Guardrails

**User Story**: As a power user, I want the system to prevent destructive actions, so that I don't accidentally lose data or cause harm.

**Acceptance Criteria**:
- **Given** an agent proposes a destructive action
  **When** evaluated
  **Then** the action is blocked or requires explicit confirmation

- **Given** an agent attempts to access restricted resources
  **When** detected
  **Then** the action is denied with explanation

- **Given** prompt injection is attempted
  **When** detected
  **Then** the input is sanitized or rejected

**Implementation Notes**:
- **Where**: `/backend/app/safety/guardrails.py`
- **What**: Action classifier, permission checker, input sanitizer
- **How**: Pre/post hooks on agent invocation; blocklist of actions
- **Why**: Prevents agent hallucination from causing real harm

**Test Notes**:
- Unit test action classification
- Red team test injection attacks
- Integration test with orchestrator

---

#### S-018: Structured Output Validation

**Title**: Enforce Pydantic Structured Outputs

**User Story**: As a developer, I want agent outputs validated, so that downstream code can rely on consistent schemas.

**Acceptance Criteria**:
- **Given** an agent produces output
  **When** validated against Pydantic model
  **Then** type errors are caught and reported

- **Given** output validation fails
  **When** retry is configured
  **Then** the agent is re-invoked with correction prompt

- **Given** output is valid
  **When** serialized
  **Then** JSON schema is consistent

**Implementation Notes**:
- **Where**: `/backend/app/agents/validation.py`
- **What**: Validation wrapper, retry logic, error reporting
- **How**: Pydantic model validation; structured error responses
- **Why**: Reliability of downstream processing depends on schema compliance

**Test Notes**:
- Unit test validation scenarios
- Test retry behavior
- Schema consistency tests

---

### Epic E-004: Canvas & Visual Components

#### S-019: Node Component

**Title**: Implement Canvas Node Component

**User Story**: As a power user, I want to create labeled nodes on my canvas, so that I can organize my thoughts spatially.

**Acceptance Criteria**:
- **Given** the user creates a node
  **When** rendered
  **Then** it appears at the specified position with editable label

- **Given** a node exists
  **When** dragged
  **Then** position updates in real-time and persists

- **Given** a node is selected
  **When** context menu is invoked
  **Then** actions (edit, delete, connect) are available

**Implementation Notes**:
- **Where**: `/frontend/src/components/Canvas/Node.tsx`
- **What**: Node component, drag handler, context menu
- **How**: React-flow or custom implementation; Zustand for position state
- **Why**: Primary unit of spatial organization

**Test Notes**:
- E2E test drag behavior
- Unit test render with props
- Accessibility test keyboard selection

---

#### S-020: Edge/Connection Component

**Title**: Implement Node Connection Edges

**User Story**: As a power user, I want to connect nodes, so that I can visualize relationships between concepts.

**Acceptance Criteria**:
- **Given** two nodes exist
  **When** the user creates a connection
  **Then** an edge renders between them

- **Given** an edge exists
  **When** selected
  **Then** it can be labeled or deleted

- **Given** a node is moved
  **When** it has connections
  **Then** edges update dynamically

**Implementation Notes**:
- **Where**: `/frontend/src/components/Canvas/Edge.tsx`
- **What**: Edge component, connection handlers, label support
- **How**: SVG paths between node positions; event handlers
- **Why**: Relationships are key to knowledge graph utility

**Test Notes**:
- E2E test edge creation
- Unit test edge rendering
- Visual test edge positioning

---

#### S-021: Document Block Component

**Title**: Implement Document Text Block

**User Story**: As a power user, I want to create document blocks on my canvas, so that I can write and reference longer text.

**Acceptance Criteria**:
- **Given** the user creates a document block
  **When** rendered
  **Then** a rich text editor is available

- **Given** a document block has content
  **When** saved
  **Then** content persists with formatting

- **Given** a document block is referenced by an agent
  **When** accessed
  **Then** content is available as context

**Implementation Notes**:
- **Where**: `/frontend/src/components/Canvas/DocumentBlock.tsx`
- **What**: Rich text editor, persistence hooks, agent context provider
- **How**: Tiptap or Slate.js for rich text; serialization to persistence
- **Why**: Documents support detailed note-taking and knowledge capture

**Test Notes**:
- E2E test rich text editing
- Unit test serialization
- Integration test with persistence

---

#### S-022: Graph Visualization

**Title**: Implement Graph Visualization Layer

**User Story**: As a power user, I want to see a graph of my nodes and connections, so that I can understand relationships at a glance.

**Acceptance Criteria**:
- **Given** nodes and edges exist
  **When** graph view is activated
  **Then** a force-directed or hierarchical layout renders

- **Given** the graph is displayed
  **When** a node is clicked
  **Then** it is focused and details are shown

- **Given** the graph has many nodes
  **When** zoomed
  **Then** clustering and labels adjust for readability

**Implementation Notes**:
- **Where**: `/frontend/src/components/Canvas/GraphView.tsx`
- **What**: Graph layout engine, clustering, zoom controls
- **How**: D3.js or react-force-graph; layout algorithms
- **Why**: Visual relationships support working memory augmentation

**Test Notes**:
- E2E test graph rendering
- Performance test with many nodes
- Visual test zoom behavior

---

#### S-023: Annotation Layer

**Title**: Implement Annotation Capability

**User Story**: As a power user, I want to annotate any canvas element, so that I can add context and notes.

**Acceptance Criteria**:
- **Given** an element exists
  **When** the user adds an annotation
  **Then** the annotation is attached and visible

- **Given** annotations exist
  **When** toggled
  **Then** they can be shown or hidden

- **Given** an annotation is added
  **When** persisted
  **Then** it survives session reload

**Implementation Notes**:
- **Where**: `/frontend/src/components/Canvas/Annotation.tsx`
- **What**: Annotation component, attachment logic, toggle controls
- **How**: Overlay positioned relative to parent element
- **Why**: Annotations add depth without cluttering main content

**Test Notes**:
- E2E test annotation CRUD
- Unit test positioning
- Persistence test

---

#### S-024: Task DAG Visualization

**Title**: Implement Task DAG Display

**User Story**: As a power user, I want to see my tasks as a directed acyclic graph, so that I understand dependencies and progress.

**Acceptance Criteria**:
- **Given** tasks with dependencies exist
  **When** DAG view is rendered
  **Then** tasks display with directional edges showing dependencies

- **Given** a task is completed
  **When** reflected in DAG
  **Then** visual state updates (e.g., color change)

- **Given** the DAG has a critical path
  **When** highlighted
  **Then** the user can identify bottlenecks

**Implementation Notes**:
- **Where**: `/frontend/src/components/TaskDAG/DAGView.tsx`
- **What**: DAG layout, task nodes, dependency edges, status indicators
- **How**: Dagre layout algorithm; status-based styling
- **Why**: Task planning and tracking benefit from visual dependency view

**Test Notes**:
- E2E test DAG rendering
- Unit test layout algorithm
- Visual test status changes

---

### Epic E-005: Job System (Deep Research)

#### S-025: Job Queue Infrastructure

**Title**: Implement Background Job Queue

**User Story**: As a power user, I want long-running tasks to execute in the background, so that my workspace remains responsive.

**Acceptance Criteria**:
- **Given** a job is dispatched
  **When** queued
  **Then** it runs asynchronously without blocking UI

- **Given** a job is running
  **When** progress occurs
  **Then** updates are streamed to the UI

- **Given** a job completes
  **When** result is available
  **Then** it is stored and accessible

**Implementation Notes**:
- **Where**: `/backend/app/jobs/queue.py`, `/backend/app/jobs/worker.py`
- **What**: Job queue, worker process, status tracking
- **How**: Celery or async task queue; Redis for state; WebSocket for updates
- **Why**: Deep research and LLM-heavy tasks require async execution

**Test Notes**:
- Integration test job execution
- Unit test queue management
- Performance test concurrent jobs

---

#### S-026: Deep Research Job Type

**Title**: Implement Deep Research Job

**User Story**: As a power user, I want to dispatch deep research jobs, so that I get comprehensive analysis on topics.

**Acceptance Criteria**:
- **Given** a research query is submitted
  **When** job is created
  **Then** research agent is invoked with query context

- **Given** research is in progress
  **When** sources are found
  **Then** intermediate results stream to UI

- **Given** research completes
  **When** report is generated
  **Then** it is stored as a referenceable artifact

- **Given** research job exceeds 5-minute timeout
  **When** timeout occurs
  **Then** partial results are saved and user is notified with option to extend

**Implementation Notes**:
- **Where**: `/backend/app/jobs/deep_research.py`, `/backend/app/agents/research_agent.py`
- **What**: Research job handler, research agent, report schema
- **How**: Multi-step agent workflow; source aggregation; report synthesis
- **Why**: Deep research is a primary use case for high-value analysis

**Test Notes**:
- Integration test research flow
- Unit test report schema
- Mock test external sources

---

#### S-027: Job Progress Streaming

**Title**: Implement WebSocket Job Progress Streaming

**User Story**: As a power user, I want to see real-time job progress, so that I know what's happening.

**Acceptance Criteria**:
- **Given** a job is running
  **When** progress events occur
  **Then** they are sent via WebSocket to subscribed clients

- **Given** a client subscribes to a job
  **When** events arrive
  **Then** they are processed and rendered in UI

- **Given** a job completes
  **When** final event is sent
  **Then** UI shows completion status

**Implementation Notes**:
- **Where**: `/backend/app/ws/job_events.py`, `/frontend/src/hooks/useJobProgress.ts`
- **What**: Job event emitter, WebSocket broadcaster, React hook
- **How**: Pub/sub pattern; WebSocket rooms per job; React state updates
- **Why**: Real-time feedback is essential for long-running tasks

**Test Notes**:
- Integration test WebSocket streaming
- E2E test UI updates
- Load test concurrent job subscriptions

---

#### S-028: LLM-as-Judge Workflow

**Title**: Implement LLM-as-Judge Analysis Pattern

**User Story**: As a power user, I want multiple AI perspectives on my research, so that I get balanced analysis.

**Acceptance Criteria**:
- **Given** content to analyze
  **When** LLM-as-judge is invoked
  **Then** multiple perspective agents are called

- **Given** perspectives are generated
  **When** synthesis occurs
  **Then** a combined analysis with agreements/disagreements is produced

- **Given** the analysis completes
  **When** stored
  **Then** both individual perspectives and synthesis are accessible

- **Given** one or more perspective agents fail
  **When** synthesis agent processes available perspectives
  **Then** synthesis proceeds with available perspectives and notes which are missing

**Implementation Notes**:
- **Where**: `/backend/app/agents/judge_workflow.py`
- **What**: Multi-agent judge workflow, synthesis agent, perspective schema
- **How**: Parallel agent calls; structured comparison; synthesis prompt
- **Why**: LLM-as-judge provides inference-time compute and balanced views

**Test Notes**:
- Unit test workflow orchestration
- Integration test perspective generation
- Quality test synthesis coherence

---

#### S-029: Job Artifact Storage

**Title**: Implement Job Artifact Persistence

**User Story**: As a power user, I want job results saved, so that I can reference them later.

**Acceptance Criteria**:
- **Given** a job produces artifacts
  **When** job completes
  **Then** artifacts are stored with job reference

- **Given** artifacts exist
  **When** queried
  **Then** they are retrievable by job ID or search

- **Given** an artifact is large
  **When** stored
  **Then** efficient storage and retrieval is maintained

**Implementation Notes**:
- **Where**: `/backend/app/persistence/artifact_store.py`
- **What**: Artifact storage service, indexing, retrieval API
- **How**: Database or object storage; metadata indexing; pagination
- **Why**: Artifacts are the tangible output of deep research

**Test Notes**:
- Unit test storage operations
- Performance test large artifacts
- Integration test with job system

---

### Epic E-006: MCP Integration

#### S-030: MCP Registry

**Title**: Implement MCP Server Registry

**User Story**: As a power user, I want to see available MCP servers, so that I know what capabilities I can enable.

**Acceptance Criteria**:
- **Given** the registry is queried
  **When** listing MCPs
  **Then** available and configured MCPs are shown

- **Given** an MCP is in the registry
  **When** details are requested
  **Then** capabilities, status, and configuration are returned

- **Given** a new MCP is added
  **When** registered
  **Then** it appears in the list after validation

**Implementation Notes**:
- **Where**: `/backend/app/mcp/registry.py`
- **What**: MCP registry, capability schema, configuration store
- **How**: In-memory or DB-backed registry; schema validation
- **Why**: Central registry enables dynamic capability discovery

**Test Notes**:
- Unit test registry operations
- Integration test with MCP client
- Validation test for malformed MCPs

---

#### S-031: MCP Client Adapter

**Title**: Implement MCP Client Adapter

**User Story**: As a developer, I want a unified MCP client, so that I can interact with any MCP server consistently.

**Acceptance Criteria**:
- **Given** an MCP server is configured
  **When** the client connects
  **Then** available tools are discovered

- **Given** a tool is invoked
  **When** parameters are provided
  **Then** the tool executes and returns results

- **Given** an MCP connection fails
  **When** error occurs
  **Then** graceful degradation and user notification occur

**Implementation Notes**:
- **Where**: `/backend/app/mcp/client.py`
- **What**: MCP client, tool discovery, invocation wrapper
- **How**: MCP protocol implementation; async operations; error handling
- **Why**: Unified client simplifies agent tool integration

**Test Notes**:
- Unit test client operations
- Integration test with mock MCP server
- Error scenario tests

---

#### S-032: Google Calendar MCP Integration

**Title**: Integrate Google Calendar MCP

**User Story**: As a power user, I want to manage my calendar from the workspace, so that I can schedule and update events seamlessly.

**Acceptance Criteria**:
- **Given** Google Calendar MCP is configured
  **When** queried
  **Then** events are retrieved

- **Given** the user requests a calendar update
  **When** processed
  **Then** the calendar is modified via MCP

- **Given** a task DAG exists
  **When** synced to calendar
  **Then** tasks appear as calendar events

- **Given** Google Calendar OAuth authentication fails
  **When** user attempts calendar operation
  **Then** clear error message displays with re-authentication option

**Implementation Notes**:
- **Where**: `/backend/app/mcp/integrations/google_calendar.py`
- **What**: Google Calendar MCP config, event mapping, sync logic
- **How**: MCP client for Google Calendar; bidirectional sync
- **Why**: Calendar integration is explicitly requested use case

**Test Notes**:
- Integration test with Google Calendar MCP
- E2E test event creation
- Sync consistency tests

---

#### S-033: MCP Security Validation

**Title**: Implement MCP Security Checks

**User Story**: As a power user, I want MCPs validated before use, so that malicious servers cannot harm my system.

**Acceptance Criteria**:
- **Given** an MCP is added
  **When** validation runs
  **Then** security checks verify compliance with standards

- **Given** an MCP fails validation
  **When** attempted to enable
  **Then** it is blocked with explanation

- **Given** an MCP performs a dangerous action
  **When** detected
  **Then** the action is blocked and logged

**Implementation Notes**:
- **Where**: `/backend/app/mcp/security.py`
- **What**: MCP validator, security rules, action blocklist
- **How**: Static analysis of MCP manifest; runtime action monitoring
- **Why**: Self-modifying workflow requires security boundaries

**Test Notes**:
- Unit test validation rules
- Red team test malicious MCP
- Integration test with registry

---

#### S-034: Dynamic MCP Addition

**Title**: Enable Dynamic MCP Configuration

**User Story**: As a power user, I want to add MCPs during a session, so that I can extend capabilities on-the-fly.

**Acceptance Criteria**:
- **Given** the user requests an MCP addition
  **When** the request is processed
  **Then** the MCP is validated and added to registry

- **Given** an MCP is added
  **When** agents query capabilities
  **Then** new tools are available

- **Given** an MCP is removed
  **When** session continues
  **Then** tools are no longer available

**Implementation Notes**:
- **Where**: `/backend/app/mcp/dynamic.py`
- **What**: Dynamic MCP manager, hot-reload logic, capability refresh
- **How**: Registry update triggers capability cache invalidation
- **Why**: Self-modifying workflow is a key differentiator

**Test Notes**:
- E2E test add/remove MCP
- Integration test capability refresh
- Concurrency test during MCP changes

---

### Epic E-007: Persistence Layer

#### S-035: Canvas State Persistence

**Title**: Implement Canvas State Storage

**User Story**: As a power user, I want my canvas state saved, so that I can continue work across sessions.

**Acceptance Criteria**:
- **Given** the canvas has state
  **When** save is triggered
  **Then** full state is persisted

- **Given** the user returns to workspace
  **When** canvas loads
  **Then** previous state is restored

- **Given** state is large
  **When** saved
  **Then** incremental/diff-based saving minimizes overhead

**Implementation Notes**:
- **Where**: `/backend/app/persistence/canvas_store.py`
- **What**: Canvas state serializer, storage adapter, restore logic
- **How**: JSON serialization; PostgreSQL or file-based; debounced auto-save
- **Why**: Persistence is fundamental to stateful workspace value

**Test Notes**:
- Unit test serialization
- E2E test save/restore cycle
- Performance test large canvas

---

#### S-036: User Preferences Storage

**Title**: Implement User Preferences Persistence

**User Story**: As a power user, I want my preferences saved, so that my workspace is configured to my liking.

**Acceptance Criteria**:
- **Given** a preference is changed
  **When** saved
  **Then** it persists across sessions

- **Given** the user logs in
  **When** workspace loads
  **Then** preferences are applied

- **Given** preferences conflict
  **When** resolved
  **Then** explicit user preference takes precedence

**Implementation Notes**:
- **Where**: `/backend/app/persistence/preferences_store.py`
- **What**: Preferences schema, storage, merge logic
- **How**: User-scoped key-value store; Pydantic schema
- **Why**: Personalization improves user experience

**Test Notes**:
- Unit test preference merge
- Integration test load/save
- Migration test schema changes

---

#### S-037: Database Migrations

**Title**: Implement Database Migration System

**User Story**: As a developer, I want managed database migrations, so that schema changes are safe and reversible.

**Acceptance Criteria**:
- **Given** a schema change is needed
  **When** migration is created
  **Then** it is versioned and reversible

- **Given** migrations exist
  **When** applied
  **Then** database is updated atomically

- **Given** a migration fails
  **When** rolled back
  **Then** database returns to previous state

**Implementation Notes**:
- **Where**: `/backend/migrations/`
- **What**: Migration scripts, runner, version tracking
- **How**: Alembic for SQLAlchemy; version table
- **Why**: Safe schema evolution as MVP grows

**Test Notes**:
- Unit test migration up/down
- Integration test migration chain
- Rollback test on failure

---

#### S-038: Backup/Export System

**Title**: Implement Workspace Backup and Export

**User Story**: As a power user, I want to backup my workspace, so that I don't lose my work.

**Acceptance Criteria**:
- **Given** the user requests backup
  **When** export is triggered
  **Then** a complete workspace snapshot is created

- **Given** a backup exists
  **When** restore is triggered
  **Then** workspace is restored to backup state

- **Given** Git-style backup is configured
  **When** changes occur
  **Then** they are committed to repository

**Implementation Notes**:
- **Where**: `/backend/app/persistence/backup.py`
- **What**: Export serializer, backup storage, Git integration (optional)
- **How**: JSON/YAML export; Git commits for versioning; scheduled backups
- **Why**: Data safety is critical for user trust

**Test Notes**:
- E2E test backup/restore
- Integration test Git commits
- Consistency test after restore

---

## 3. TASK BREAKDOWN (Per Story)

---

### Epic E-001 Tasks

#### S-001: Canvas Shell Setup

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-001 | Set up Next.js project with TypeScript | `/frontend/` | None |
| T-002 | Create Canvas container component | `/frontend/src/components/Canvas/Canvas.tsx` | T-001 |
| T-003 | Implement viewport pan/zoom controls | `/frontend/src/components/Canvas/Viewport.tsx` | T-002 |
| T-004 | Add floating TextInput component placeholder | `/frontend/src/components/ContextInput/` | T-002 |
| T-005 | Configure responsive CSS/Tailwind | `/frontend/src/styles/` | T-001 |
| T-006 | Add environment variable validation (no secrets in client) | `/frontend/src/config/` | T-001 |

#### S-002: Global State Management

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-007 | Install and configure Zustand | `/frontend/package.json`, `/frontend/src/state/` | T-001 |
| T-008 | Define canvas state slice | `/frontend/src/state/canvasSlice.ts` | T-007 |
| T-009 | Define nodes state slice | `/frontend/src/state/nodesSlice.ts` | T-007 |
| T-010 | Define jobs state slice | `/frontend/src/state/jobsSlice.ts` | T-007 |
| T-011 | Implement selector patterns for performance | `/frontend/src/state/selectors.ts` | T-007 |
| T-012 | Add persistence middleware hook | `/frontend/src/state/persistMiddleware.ts` | T-007 |

#### S-003: WebSocket Infrastructure

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-013 | Set up FastAPI backend project | `/backend/` | None |
| T-014 | Implement WebSocket endpoint | `/backend/app/ws/connection.py` | T-013 |
| T-015 | Create WebSocket client service | `/frontend/src/services/websocket.ts` | T-001 |
| T-016 | Implement reconnection with exponential backoff | `/frontend/src/services/websocket.ts` | T-015 |
| T-017 | Add heartbeat mechanism | `/backend/app/ws/connection.py`, `/frontend/src/services/websocket.ts` | T-014, T-015 |
| T-018 | Integrate WebSocket messages with state store | `/frontend/src/services/wsStateSync.ts` | T-015, T-007 |

#### S-004: AG-UI Protocol Integration

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-019 | Define AG-UI event types | `/backend/app/agui/events.py`, `/frontend/src/agui/types.ts` | T-013, T-001 |
| T-020 | Implement AG-UI event handlers (frontend) | `/frontend/src/agui/handlers.ts` | T-019 |
| T-021 | Implement AG-UI message formatter (backend) | `/backend/app/agui/formatter.py` | T-019 |
| T-022 | Add streaming token handler | `/frontend/src/agui/streaming.ts` | T-020 |
| T-023 | Integrate AG-UI with WebSocket transport | `/backend/app/ws/agui_transport.py` | T-014, T-021 |

#### S-005: CopilotKit Base Integration

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-024 | Install CopilotKit SDK | `/frontend/package.json` | T-001 |
| T-025 | Configure CopilotKit provider | `/frontend/src/copilot/provider.tsx` | T-024 |
| T-026 | Define initial copilot actions | `/frontend/src/copilot/actions.ts` | T-025 |
| T-027 | Create copilot context providers | `/frontend/src/copilot/context.ts` | T-025, T-007 |
| T-028 | Add copilot panel component | `/frontend/src/copilot/CopilotPanel.tsx` | T-025 |

#### S-006: Base Component Library

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-029 | Create base Node component | `/frontend/src/components/primitives/Node.tsx` | T-002 |
| T-030 | Create Edge component | `/frontend/src/components/primitives/Edge.tsx` | T-002 |
| T-031 | Create Panel component | `/frontend/src/components/primitives/Panel.tsx` | T-002 |
| T-032 | Create Container component | `/frontend/src/components/primitives/Container.tsx` | T-002 |
| T-033 | Set up Storybook for components | `/frontend/.storybook/` | T-001 |
| T-034 | Add component design tokens | `/frontend/src/styles/tokens.ts` | T-005 |

---

### Epic E-002 Tasks

#### S-007: Text Input Box Component

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-035 | Create TextInput component | `/frontend/src/components/ContextInput/TextInput.tsx` | T-002 |
| T-036 | Add drag-drop file support | `/frontend/src/components/ContextInput/FileDrop.tsx` | T-035 |
| T-037 | Implement submit handler | `/frontend/src/components/ContextInput/submit.ts` | T-035 |
| T-038 | Style floating behavior | `/frontend/src/components/ContextInput/TextInput.css` | T-035 |

#### S-008: Context Routing Pipeline

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-039 | Define context payload schema | `/backend/app/context/schema.py` | T-013 |
| T-040 | Implement context router | `/backend/app/context/router.py` | T-039 |
| T-041 | Add intent classifier stub | `/backend/app/context/classifier.py` | T-040 |
| T-042 | Implement routing rules | `/backend/app/context/rules.py` | T-040 |
| T-043 | Add multi-intent decomposition | `/backend/app/context/decomposer.py` | T-040 |

#### S-009: Intent Deciphering Agent

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-044 | Create IntentDecipherer agent | `/backend/app/agents/intent_decipherer.py` | T-013, T-067 |
| T-045 | Define assumption output schema | `/backend/app/domain/models/assumption.py` | T-013 |
| T-046 | Implement capability matching | `/backend/app/agents/capability_matcher.py` | T-044 |
| T-047 | Add prompt templates | `/backend/app/agents/prompts/intent.py` | T-044 |

#### S-010: Assumptions Data Structure

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-048 | Define Assumption Pydantic model | `/backend/app/domain/models/assumption.py` | T-013 |
| T-049 | Define AssumptionGroup model | `/backend/app/domain/models/assumption.py` | T-048 |
| T-050 | Define confidence enum | `/backend/app/domain/models/assumption.py` | T-048 |
| T-051 | Add serialization tests | `/backend/tests/domain/test_assumption.py` | T-048 |

#### S-011: Assumptions UI Panel

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-052 | Create AssumptionCard component | `/frontend/src/components/Assumptions/AssumptionCard.tsx` | T-001 |
| T-053 | Create AssumptionPanel container | `/frontend/src/components/Assumptions/AssumptionPanel.tsx` | T-052 |
| T-054 | Add approval/rejection handlers | `/frontend/src/components/Assumptions/handlers.ts` | T-053 |
| T-055 | Integrate with state store | `/frontend/src/state/assumptionsSlice.ts` | T-053, T-007 |
| T-056 | Add feedback input on rejection | `/frontend/src/components/Assumptions/FeedbackInput.tsx` | T-053 |

#### S-012: User Intent/Meaning Index

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-057 | Define intent index schema | `/backend/app/domain/models/intent_index.py` | T-013 |
| T-058 | Implement intent index service | `/backend/app/domain/services/intent_index.py` | T-057 |
| T-059 | Create storage adapter | `/backend/app/persistence/intent_store.py` | T-057 |
| T-060 | Add relevance scoring | `/backend/app/domain/services/intent_index.py` | T-058 |
| T-061 | Implement query interface | `/backend/app/domain/services/intent_index.py` | T-058 |

#### S-013: Audio Block Transcription

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-062 | Create AudioBlock component | `/frontend/src/components/Canvas/AudioBlock.tsx` | T-002 |
| T-063 | Implement MediaRecorder integration | `/frontend/src/components/Canvas/AudioRecorder.ts` | T-062 |
| T-064 | Create transcription service | `/backend/app/services/transcription.py` | T-013 |
| T-065 | Add transcription job type | `/backend/app/jobs/transcription.py` | T-064 |
| T-066 | Display transcript in AudioBlock | `/frontend/src/components/Canvas/AudioBlock.tsx` | T-062 |

---

### Epic E-003 Tasks

#### S-014: PydanticAI Gateway Client

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-067 | Create Gateway client class | `/backend/app/gateway/client.py` | T-013 |
| T-068 | Implement auth configuration | `/backend/app/gateway/auth.py` | T-067 |
| T-069 | Add retry with exponential backoff | `/backend/app/gateway/retry.py` | T-067 |
| T-070 | Define error types | `/backend/app/gateway/errors.py` | T-067 |
| T-071 | Add environment variable loading | `/backend/app/config.py` | T-013 |

#### S-015: Agent Base Class

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-072 | Create BaseAgent class | `/backend/app/agents/base.py` | T-067 |
| T-073 | Implement tool registration decorator | `/backend/app/agents/tools.py` | T-072 |
| T-074 | Add structured output validation | `/backend/app/agents/validation.py` | T-072 |
| T-075 | Create agent factory | `/backend/app/agents/factory.py` | T-072 |

#### S-016: Agent Orchestrator

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-076 | Create Orchestrator service | `/backend/app/orchestration/orchestrator.py` | T-072 |
| T-077 | Implement agent registry | `/backend/app/orchestration/registry.py` | T-076 |
| T-078 | Add capability matching logic | `/backend/app/orchestration/matcher.py` | T-076 |
| T-079 | Implement routing rules engine | `/backend/app/orchestration/rules.py` | T-076 |
| T-080 | Add fallback handler | `/backend/app/orchestration/fallback.py` | T-076 |

#### S-017: Safety Guardrails

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-081 | Create guardrails service | `/backend/app/safety/guardrails.py` | T-013 |
| T-082 | Implement action classifier | `/backend/app/safety/classifier.py` | T-081 |
| T-083 | Add permission checker | `/backend/app/safety/permissions.py` | T-081 |
| T-084 | Create input sanitizer | `/backend/app/safety/sanitizer.py` | T-081 |
| T-085 | Define action blocklist | `/backend/app/safety/blocklist.py` | T-081 |

#### S-018: Structured Output Validation

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-086 | Create validation wrapper | `/backend/app/agents/validation.py` | T-072 |
| T-087 | Implement retry on validation failure | `/backend/app/agents/retry.py` | T-086 |
| T-088 | Add error reporting | `/backend/app/agents/errors.py` | T-086 |
| T-089 | Create schema consistency tests | `/backend/tests/agents/test_validation.py` | T-086 |

---

### Epic E-004 Tasks

#### S-019: Node Component

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-090 | Implement Node component with drag | `/frontend/src/components/Canvas/Node.tsx` | T-029 |
| T-091 | Add label editing | `/frontend/src/components/Canvas/NodeLabel.tsx` | T-090 |
| T-092 | Implement context menu | `/frontend/src/components/Canvas/NodeContextMenu.tsx` | T-090 |
| T-093 | Add position persistence | `/frontend/src/components/Canvas/Node.tsx` | T-090, T-012 |

#### S-020: Edge/Connection Component

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-094 | Implement Edge component | `/frontend/src/components/Canvas/Edge.tsx` | T-030 |
| T-095 | Add connection handlers | `/frontend/src/components/Canvas/ConnectionHandler.tsx` | T-094 |
| T-096 | Implement edge labeling | `/frontend/src/components/Canvas/EdgeLabel.tsx` | T-094 |
| T-097 | Add dynamic edge updates | `/frontend/src/components/Canvas/Edge.tsx` | T-094 |

#### S-021: Document Block Component

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-098 | Create DocumentBlock component | `/frontend/src/components/Canvas/DocumentBlock.tsx` | T-002 |
| T-099 | Integrate rich text editor (Tiptap) | `/frontend/src/components/Canvas/RichTextEditor.tsx` | T-098 |
| T-100 | Add content serialization | `/frontend/src/components/Canvas/documentSerializer.ts` | T-099 |
| T-101 | Implement persistence hooks | `/frontend/src/components/Canvas/DocumentBlock.tsx` | T-100, T-012 |

#### S-022: Graph Visualization

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-102 | Create GraphView component | `/frontend/src/components/Canvas/GraphView.tsx` | T-002 |
| T-103 | Integrate layout algorithm (D3/dagre) | `/frontend/src/components/Canvas/graphLayout.ts` | T-102 |
| T-104 | Add node click focus | `/frontend/src/components/Canvas/GraphView.tsx` | T-102 |
| T-105 | Implement zoom with label scaling | `/frontend/src/components/Canvas/GraphView.tsx` | T-102 |

#### S-023: Annotation Layer

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-106 | Create Annotation component | `/frontend/src/components/Canvas/Annotation.tsx` | T-002 |
| T-107 | Implement attachment logic | `/frontend/src/components/Canvas/annotationAttach.ts` | T-106 |
| T-108 | Add toggle visibility | `/frontend/src/components/Canvas/Annotation.tsx` | T-106 |
| T-109 | Implement annotation persistence | `/frontend/src/components/Canvas/Annotation.tsx` | T-106, T-012 |

#### S-024: Task DAG Visualization

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-110 | Create DAGView component | `/frontend/src/components/TaskDAG/DAGView.tsx` | T-102 |
| T-111 | Define Task node schema | `/frontend/src/components/TaskDAG/types.ts` | T-110 |
| T-112 | Implement status-based styling | `/frontend/src/components/TaskDAG/taskStyles.ts` | T-110 |
| T-113 | Add critical path highlighting | `/frontend/src/components/TaskDAG/criticalPath.ts` | T-110 |
| T-114 | Integrate with task state | `/frontend/src/state/tasksSlice.ts` | T-110, T-007 |

---

### Epic E-005 Tasks

#### S-025: Job Queue Infrastructure

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-115 | Set up job queue (Celery/ARQ) | `/backend/app/jobs/queue.py` | T-013 |
| T-116 | Create worker process | `/backend/app/jobs/worker.py` | T-115 |
| T-117 | Implement job status tracking | `/backend/app/jobs/status.py` | T-115 |
| T-118 | Add Redis connection for state | `/backend/app/jobs/redis.py` | T-115 |
| T-119 | Create job dispatcher service | `/backend/app/jobs/dispatcher.py` | T-115 |

#### S-026: Deep Research Job Type

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-120 | Create DeepResearchJob class | `/backend/app/jobs/deep_research.py` | T-115 |
| T-121 | Implement ResearchAgent | `/backend/app/agents/research_agent.py` | T-072 |
| T-122 | Define research report schema | `/backend/app/domain/models/research_report.py` | T-013 |
| T-123 | Add source aggregation logic | `/backend/app/agents/research_agent.py` | T-121 |
| T-124 | Implement report synthesis | `/backend/app/agents/research_agent.py` | T-121 |

#### S-027: Job Progress Streaming

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-125 | Create job event emitter | `/backend/app/ws/job_events.py` | T-014, T-115 |
| T-126 | Implement WebSocket broadcaster | `/backend/app/ws/broadcaster.py` | T-125 |
| T-127 | Create useJobProgress hook | `/frontend/src/hooks/useJobProgress.ts` | T-015 |
| T-128 | Add job subscription management | `/backend/app/ws/subscriptions.py` | T-125 |

#### S-028: LLM-as-Judge Workflow

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-129 | Create JudgeWorkflow orchestrator | `/backend/app/agents/judge_workflow.py` | T-076 |
| T-130 | Implement perspective agents | `/backend/app/agents/perspective_agent.py` | T-072 |
| T-131 | Define perspective schema | `/backend/app/domain/models/perspective.py` | T-013 |
| T-132 | Create synthesis agent | `/backend/app/agents/synthesis_agent.py` | T-072 |
| T-133 | Add parallel execution for perspectives | `/backend/app/agents/judge_workflow.py` | T-129 |

#### S-029: Job Artifact Storage

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-134 | Create artifact storage service | `/backend/app/persistence/artifact_store.py` | T-013 |
| T-135 | Define artifact schema | `/backend/app/domain/models/artifact.py` | T-013 |
| T-136 | Implement metadata indexing | `/backend/app/persistence/artifact_store.py` | T-134 |
| T-137 | Add retrieval API | `/backend/app/api/artifacts.py` | T-134 |
| T-138 | Handle large artifact storage | `/backend/app/persistence/artifact_store.py` | T-134 |

---

### Epic E-006 Tasks

#### S-030: MCP Registry

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-139 | Create MCPRegistry class | `/backend/app/mcp/registry.py` | T-013 |
| T-140 | Define MCP capability schema | `/backend/app/mcp/schema.py` | T-139 |
| T-141 | Implement configuration storage | `/backend/app/mcp/config_store.py` | T-139 |
| T-142 | Add registry query API | `/backend/app/api/mcp.py` | T-139 |

#### S-031: MCP Client Adapter

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-143 | Create MCPClient class | `/backend/app/mcp/client.py` | T-139 |
| T-144 | Implement tool discovery | `/backend/app/mcp/discovery.py` | T-143 |
| T-145 | Add tool invocation wrapper | `/backend/app/mcp/invocation.py` | T-143 |
| T-146 | Implement error handling | `/backend/app/mcp/errors.py` | T-143 |

#### S-032: Google Calendar MCP Integration

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-147 | Create GoogleCalendarMCP integration | `/backend/app/mcp/integrations/google_calendar.py` | T-143 |
| T-148 | Define event mapping | `/backend/app/mcp/integrations/calendar_events.py` | T-147 |
| T-149 | Implement bidirectional sync | `/backend/app/mcp/integrations/google_calendar.py` | T-147 |
| T-150 | Add task-to-calendar mapping | `/backend/app/mcp/integrations/task_calendar_sync.py` | T-147, T-114 |

#### S-033: MCP Security Validation

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-151 | Create MCPValidator class | `/backend/app/mcp/security.py` | T-139 |
| T-152 | Define security rules | `/backend/app/mcp/security_rules.py` | T-151 |
| T-153 | Implement manifest analysis | `/backend/app/mcp/manifest_analyzer.py` | T-151 |
| T-154 | Add runtime action monitoring | `/backend/app/mcp/action_monitor.py` | T-151 |

#### S-034: Dynamic MCP Addition

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-155 | Create DynamicMCPManager | `/backend/app/mcp/dynamic.py` | T-139, T-151 |
| T-156 | Implement hot-reload logic | `/backend/app/mcp/hot_reload.py` | T-155 |
| T-157 | Add capability cache invalidation | `/backend/app/mcp/capability_cache.py` | T-155 |
| T-158 | Create MCP add/remove API | `/backend/app/api/mcp.py` | T-155 |

---

### Epic E-007 Tasks

#### S-035: Canvas State Persistence

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-159 | Create CanvasStateStore | `/backend/app/persistence/canvas_store.py` | T-013 |
| T-160 | Define canvas state schema | `/backend/app/domain/models/canvas_state.py` | T-159 |
| T-161 | Implement serialization | `/backend/app/persistence/serializers/canvas.py` | T-159 |
| T-162 | Add debounced auto-save | `/frontend/src/state/autoSave.ts` | T-012 |
| T-163 | Create restore API | `/backend/app/api/canvas.py` | T-159 |

#### S-036: User Preferences Storage

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-164 | Create PreferencesStore | `/backend/app/persistence/preferences_store.py` | T-013 |
| T-165 | Define preferences schema | `/backend/app/domain/models/preferences.py` | T-164 |
| T-166 | Implement merge logic | `/backend/app/persistence/preferences_store.py` | T-164 |
| T-167 | Add preferences API | `/backend/app/api/preferences.py` | T-164 |

#### S-037: Database Migrations

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-168 | Set up Alembic | `/backend/alembic.ini`, `/backend/migrations/` | T-013 |
| T-169 | Create initial migration | `/backend/migrations/versions/` | T-168 |
| T-170 | Add migration runner script | `/backend/scripts/migrate.py` | T-168 |
| T-171 | Implement rollback tests | `/backend/tests/migrations/` | T-168 |

#### S-038: Backup/Export System

| Task ID | Description | File/Module Hints | Dependencies |
|---------|-------------|-------------------|--------------|
| T-172 | Create BackupService | `/backend/app/persistence/backup.py` | T-159 |
| T-173 | Implement JSON/YAML export | `/backend/app/persistence/exporters/` | T-172 |
| T-174 | Add Git integration (optional) | `/backend/app/persistence/git_backup.py` | T-172 |
| T-175 | Create restore from backup | `/backend/app/persistence/backup.py` | T-172 |
| T-176 | Add scheduled backup job | `/backend/app/jobs/backup_job.py` | T-172, T-115 |

---

## 4. DEPENDENCY ORDERING

### 4.1 Foundational Stories (Must Complete First)

**Phase 0 - Infrastructure Setup**
1. **S-001**: Canvas Shell Setup (Foundation for all UI)
2. **S-002**: Global State Management (Required by all stateful components)
3. **S-003**: WebSocket Infrastructure (Required for real-time features)
4. **S-014**: PydanticAI Gateway Client (Required for all agent work)
5. **S-015**: Agent Base Class (Required for all agents)

**Phase 1 - Core Agent System**
6. **S-006**: Base Component Library (Enables E-004 work)
7. **S-004**: AG-UI Protocol Integration (Enables agent-UI communication)
8. **S-016**: Agent Orchestrator (Enables context routing)
9. **S-010**: Assumptions Data Structure (Contract for intent system)

### 4.2 Parallelizable Stories

After Phase 0-1, these can be developed in parallel:

**Stream A - Context & Intent** (Requires: S-014, S-015, S-016, S-010)
- S-007: Text Input Box Component
- S-008: Context Routing Pipeline
- S-009: Intent Deciphering Agent
- S-011: Assumptions UI Panel
- S-012: User Intent/Meaning Index
- S-013: Audio Block Transcription

**Stream B - Canvas Components** (Requires: S-001, S-002, S-006)
- S-019: Node Component
- S-020: Edge/Connection Component
- S-021: Document Block Component
- S-022: Graph Visualization
- S-023: Annotation Layer
- S-024: Task DAG Visualization

**Stream C - Job System** (Requires: S-003, S-014, S-015)
- S-025: Job Queue Infrastructure
- S-026: Deep Research Job Type
- S-027: Job Progress Streaming
- S-028: LLM-as-Judge Workflow
- S-029: Job Artifact Storage

**Stream D - MCP Integration** (Requires: S-015, S-016, S-017)
- S-030: MCP Registry
- S-031: MCP Client Adapter
- S-032: Google Calendar MCP Integration
- S-033: MCP Security Validation
- S-034: Dynamic MCP Addition

**Stream E - Persistence** (Requires: S-002)
- S-035: Canvas State Persistence
- S-036: User Preferences Storage
- S-037: Database Migrations
- S-038: Backup/Export System

**Stream F - Safety & Copilot** (Can start after Phase 0)
- S-005: CopilotKit Base Integration
- S-017: Safety Guardrails
- S-018: Structured Output Validation

### 4.3 Critical Path

```
S-001 (Canvas) --> S-002 (State) --> S-006 (Components) --> S-019/S-020/S-021 (Nodes/Edges/Docs)
                                  |
                                  v
                          S-035 (Canvas Persistence)

T-013 (FastAPI) --> T-067 (Gateway) --> T-072 (BaseAgent) --> S-016 (Orchestrator)
                |                                            |
                v                                            v
          T-014 (WebSocket) --> T-125 (Job Events)     S-009 (Intent Agent)
                                      |
                                      v
                              S-026 (Deep Research)
```

### 4.4 Suggested Sprint Organization

| Sprint | Focus | Stories |
|--------|-------|---------|
| Sprint 1 | Infrastructure | S-001, S-002, S-003, S-014, S-015 |
| Sprint 2 | Core Components | S-004, S-005, S-006, S-016, S-017 |
| Sprint 3 | Context System | S-007, S-008, S-009, S-010, S-011 |
| Sprint 4 | Canvas UI | S-019, S-020, S-021, S-022 |
| Sprint 5 | Job System | S-025, S-026, S-027, S-028 |
| Sprint 6 | MCP & Persistence | S-030, S-031, S-033, S-035, S-037 |
| Sprint 7 | Polish & Integration | S-012, S-013, S-023, S-024, S-029, S-032, S-034, S-036, S-038 |
| Sprint 8 | Testing & Hardening | S-018, final integration testing |

---

## 5. COVERAGE MAP

### Brain Dump Feature Coverage

| Feature ID | Feature | Epic | Stories | Tasks |
|------------|---------|------|---------|-------|
| F001 | Canvas-based stateful workspace (not chatbot) | E-001, E-004 | S-001, S-002, S-019-S-024 | T-002, T-007-T-012, T-090-T-114 |
| F002 | Text box input for context injection | E-002 | S-007 | T-035-T-038 |
| F003 | Context routing system for intelligent delegation | E-002, E-003 | S-008, S-016 | T-039-T-043, T-076-T-080 |
| F004 | Intent/meaning deciphering with user reconciliation | E-002 | S-009, S-010, S-011 | T-044-T-056 |
| F005 | MCP server integration (modular, configurable) | E-006 | S-030, S-031, S-034 | T-139-T-158 |
| F006 | Deep research jobs with streaming updates | E-005 | S-025, S-026, S-027 | T-115-T-128 |
| F007 | LLM-as-judge patterns for critique/perspectives | E-005 | S-028 | T-129-T-133 |
| F008 | Visual representations (graphs, nodes, annotations) | E-004 | S-019, S-020, S-022, S-023 | T-090-T-109 |
| F009 | Persistence of workspace state (CRUD) | E-007 | S-035, S-036, S-037, S-038 | T-159-T-176 |
| F010 | Audio block transcription and processing | E-002 | S-013 | T-062-T-066 |
| F011 | Task DAG visualization | E-004 | S-024 | T-110-T-114 |
| F012 | Self-modifying workflows (add MCPs on-the-fly) | E-006 | S-033, S-034 | T-151-T-158 |
| F013 | Assumptions UI for user confirmation | E-002 | S-011 | T-052-T-056 |
| F014 | Calendar/external service integrations | E-006 | S-032 | T-147-T-150 |
| F015 | Working memory augmentation via spatial UI | E-004 | S-019, S-022, S-023 | T-090-T-109 |

### Constraint Coverage

| Constraint ID | Constraint | Covered In |
|---------------|------------|------------|
| C001 | PydanticAI via Gateway API ONLY | S-014, T-067-T-071 |
| C002 | Env vars: PYDANTIC_GATEWAY_API_KEY, XAI_API_KEY | S-014 (T-071), S-001 (T-006) |
| C003 | Never embed API keys in code | S-014, S-001 (explicit validation) |
| C004 | AG-UI protocol for agent/UI interaction | S-004, T-019-T-023 |
| C005 | CopilotKit for copilot-style assistance | S-005, T-024-T-028 |
| C006 | Modular/DDD architecture | All epics (directory structure) |
| C007 | Security checks for MCP additions | S-033, T-151-T-154 |
| C008 | No information loss during context handling | S-008 (T-043), S-009 |

### Workflow Coverage

| Workflow ID | Workflow | Stories |
|-------------|----------|---------|
| W001 | Input text -> Intent deciphering -> Assumptions -> Reconciliation | S-007, S-008, S-009, S-011 |
| W002 | Deep research job -> LLM-as-judge -> Persist result | S-026, S-028, S-029 |
| W003 | Canvas CRUD -> Agent interaction -> State update | S-019-S-024, S-035 |
| W004 | Configure MCP -> Security check -> Enable capability | S-030, S-033, S-034 |
| W005 | Hackathon planning -> Task DAG -> Calendar integration | S-024, S-032 |

### Data Entity Coverage

| Data ID | Entity | Stories |
|---------|--------|---------|
| D001 | User intent/meaning index | S-012 |
| D002 | Canvas state (nodes, documents, audio) | S-035 |
| D003 | Deep research reports/artifacts | S-026, S-029 |
| D004 | Task DAGs | S-024 |
| D005 | Session context | S-002, S-008 |
| D006 | MCP configurations | S-030, S-036 |

### Integration Coverage

| Integration ID | Integration | Stories |
|----------------|-------------|---------|
| I001 | Google Calendar via MCP | S-032 |
| I002 | Google Docs for task export | S-032 (ASSUMPTION: via MCP) |
| I003 | WebSocket streaming for job updates | S-003, S-027 |
| I004 | Obsidian/Git for backup | S-038 |

### Non-Functional Coverage

| NFR ID | Requirement | Stories |
|--------|-------------|---------|
| N001 | High throughput, high velocity | S-002, S-003, S-025 |
| N002 | Reliability for rapid context switching | S-016, S-017 |
| N003 | Real-time state streaming | S-003, S-027 |
| N004 | Granular context decomposition | S-008, S-009 |

### Risk Mitigation Coverage

| Risk ID | Risk | Mitigation Stories |
|---------|------|-------------------|
| R001 | Gateway beta reliability | S-014 (retry logic) |
| R002 | Context window management | S-008, S-012 |
| R003 | Agent hallucination/destructive actions | S-017 |
| R004 | MCP security vulnerabilities | S-033 |

---

## ASSUMPTIONS MADE

1. **ASSUMPTION-001**: PostgreSQL will be the primary database for persistence. Rationale: Mature, supports JSON fields well, good for MVP. Labeled for validation.

2. **ASSUMPTION-002**: Celery with Redis will be used for job queue. Rationale: Well-documented, Python-native, scales well. Alternative: ARQ if simpler async is preferred.

3. **ASSUMPTION-003**: React with Next.js for frontend. Rationale: Industry standard, SSR capabilities, good DX.

4. **ASSUMPTION-004**: Google Docs export will be handled via MCP integration rather than direct API. Rationale: Follows modular MCP pattern established for Calendar.

5. **ASSUMPTION-005**: Audio transcription will use an external service (Whisper API or similar) rather than local processing. Rationale: MVP simplicity, quality.

6. **ASSUMPTION-006**: Single-user MVP initially; multi-tenancy can be added later. Rationale: Reduces complexity for MVP scope.

7. **ASSUMPTION-007**: Frontend and backend will be separate services (not monolithic). Rationale: Supports independent scaling and deployment.

8. **ASSUMPTION-008**: WebSocket will be used for all real-time communication (not SSE). Rationale: Bidirectional support needed for agent interactions.

---

## VALIDATION QUESTIONS

1. What is the preferred persistence layer (PostgreSQL vs. SQLite vs. other)?
2. Is multi-user/multi-tenant support required for MVP?
3. What is the expected scale (concurrent users, jobs, canvas size)?
4. Should audio transcription be real-time or batch processed?
5. Are there specific MCP servers beyond Google Calendar that must be supported in MVP?
6. What is the authentication strategy (OAuth, API keys, none for alpha)?
7. Is there a preference for frontend framework (Next.js vs. Vite+React)?
8. Should backup support both Git-style and DB snapshot, or one approach?
9. What is the target response time for intent deciphering?
10. Are there specific LLM models required via Gateway (GPT-4, Claude, etc.)?

---

*This backlog is designed to be BMAD-compatible and provides complete traceability from brain dump requirements to actionable engineering tasks.*
