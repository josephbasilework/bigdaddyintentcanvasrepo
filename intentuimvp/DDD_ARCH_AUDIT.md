# DDD Architecture Audit Report

## Summary

| Metric | Count |
|--------|-------|
| Bounded Contexts Defined | 5 |
| Entities Defined | 10 |
| Value Objects Defined | 5 |
| Aggregates Defined | 4 |
| Domain Events Defined | 9 |
| Invariants/Business Rules | 6 |
| Glossary Terms | 10 |
| Domain Concepts from Brain Dump | 28 covered, 7 missing/underspecified |

**Overall Assessment**: The DDD model in Section 7 is reasonably comprehensive and captures most core concepts from the brain dump. However, there are gaps in representing some important domain concepts, ambiguities in bounded context boundaries, and some overreach where the PRD introduces concepts not explicitly in the brain dump.

---

## Bounded Context Analysis

### 1. Workspace Context
**Responsibilities**: Canvas state, nodes, documents, audio blocks, visual graphs, spatial layout

**Coherence**: GOOD
- Well-aligned with brain dump emphasis on "canvas" as the central stateful workspace
- Captures the spatial/visual aspects mentioned extensively ("nodes," "graphs," "documents," "audio blocks")

**Boundary Issues**:
- Brain dump mentions "live dashboard" showing state from API endpoints - this appears split between Workspace and Integration contexts without clear ownership
- "Task DAG" visualization is mentioned in brain dump as a key concept but only appears in functional requirements, not as an entity in this context

**Missing**:
- `VisualGraph` entity is referenced in Canvas aggregate but not defined in entity table
- `TaskDAG` should be an explicit entity for "task directed acyclic graph" mentioned in brain dump

### 2. Agent Context
**Responsibilities**: Agent orchestration, jobs, workflows, tool invocation, LLM-as-judge

**Coherence**: GOOD
- Aligns with brain dump's "agents are first-class citizens" concept
- Captures deep research jobs, LLM-as-judge patterns

**Boundary Issues**:
- The "self-modifying workflow" concept from brain dump is partially captured but marked as out-of-scope for MVP - the Workflow entity has `isModifiable` field but no clear mechanism for self-modification
- "Inference time compute" concept from brain dump (throwing more compute at problems) lacks explicit representation

**Missing**:
- No explicit `ResearchReport` or `DeepResearchJob` entity - only generic `Job` entity
- No `Perspective` entity for LLM-as-judge multi-perspective pattern (only in code models, not domain model)

### 3. Integration Context
**Responsibilities**: MCP servers, external connections, security validation

**Coherence**: GOOD
- Aligns with brain dump's MCP server modularity concept
- Security validation requirement captured (brain dump mentions "security check," "adhere to specified standards")

**Boundary Issues**:
- Google Calendar is specifically mentioned in brain dump but Integration Context is too generic - could benefit from more specific integration types

**Missing**:
- `CalendarEvent` or similar entity for calendar integration
- `ExternalState` entity for the "single source of truth" observation pattern mentioned in brain dump

### 4. User Context
**Responsibilities**: User identity, intent index, sessions, assumptions, preferences

**Coherence**: EXCELLENT
- Very well-aligned with brain dump's emphasis on "decipher intent/meaning"
- IntentMeaningIndex captures the "persisted user intent meaning index" concept verbatim
- Assumption entity captures the reconciliation workflow well

**Boundary Issues**:
- Session entity contains `contextHistory[]` but Context Routing is a separate bounded context - potential data duplication

**Missing**:
- `UserCommand` entity for explicit command-driven interactions mentioned in brain dump
- `EurekaNote` or similar for "random eureka" thoughts concept - this is a distinct use case mentioned explicitly

### 5. Context Routing
**Responsibilities**: Input classification, routing decisions, context decomposition

**Coherence**: ADEQUATE
- Captures the routing concept from brain dump
- Decomposition aligns with brain dump's "decompose all this information" and "granular but not redundant"

**Boundary Issues**:
- This feels more like a service/mechanism than a full bounded context
- Heavily dependent on User Context (intent index) and Agent Context (handlers) - unclear if this warrants its own context or should be a service within another context

**Missing**:
- No explicit representation of "deterministic hooks after specific life cycles" mentioned in brain dump
- No `ContextSource` entity distinguishing between text input, canvas CRUD, job results, streaming data

---

## Missing Domain Concepts

The following concepts appear in the brain dump but are not adequately represented in the domain model:

### 1. Task DAG (Critical)
**Brain Dump**: "we have a task DAG, a task directed acyclic graph," "you can get that in a task DAG form," "Task DAG can sync to calendar"
**Status**: Mentioned in functional requirements (FR-010) and UI components but NOT defined as an entity or aggregate
**Impact**: HIGH - This is a key differentiating feature

### 2. Live Dashboard / State Observation (Important)
**Brain Dump**: "you could perhaps observe some state from an API endpoint," "live dashboard of this state," "single source of truth"
**Status**: Not represented in domain model
**Impact**: MEDIUM - Important use case for power users

### 3. Random Eureka / Quick Notes (Important)
**Brain Dump**: "random eureka thoughts," "we want to be able to get down our random ass notes add a little labeling"
**Status**: Partially covered by Node entity but lacks specific handling
**Impact**: MEDIUM - Key workflow for target persona

### 4. Hackathon/Plan Mode (Important)
**Brain Dump**: "collaborate on a plan with the agentic system," "structured, competitive, first-place-minded plan," "small steps"
**Status**: Not explicitly modeled - could be a specialized Workflow type
**Impact**: MEDIUM - Concrete use case mentioned

### 5. Working Memory Augmentation (Conceptual)
**Brain Dump**: "augmenting working memory," "associative short-term memory," "spatial associativity"
**Status**: In glossary as concept but no supporting entities for spatial relationships
**Impact**: LOW - More of a design principle than entity

### 6. Speech Input / Real-time Tool Calls
**Brain Dump**: "microphone icon," "speech-to-speech with real-time tool calls," "Wispr Flow"
**Status**: AudioBlock covers recording/transcription but not real-time speech-to-speech
**Impact**: LOW for MVP (acknowledged out of scope)

### 7. Knowledge Base Connection
**Brain Dump**: "connected knowledge base," "predefined associative sort of search"
**Status**: Not modeled - could be an MCP integration but deserves explicit entity
**Impact**: MEDIUM - Mentioned multiple times

---

## Overreach

The following concepts appear in the PRD domain model but are NOT explicitly mentioned in the brain dump:

### 1. Session Entity
**PRD**: Full Session entity with `status`, `contextHistory[]`
**Brain Dump**: Mentions "session" casually but not as a formal persistent entity
**Assessment**: ACCEPTABLE - reasonable inference for stateful system

### 2. JobProgress Value Object
**PRD**: `percentComplete`, `currentStep`, `stepsCompleted`
**Brain Dump**: Mentions streaming updates but not specific progress tracking
**Assessment**: ACCEPTABLE - reasonable implementation detail

### 3. RoutingDecision Value Object
**PRD**: `targetContext`, `handler`, `priority`
**Brain Dump**: Mentions routing but not explicit decision structure
**Assessment**: ACCEPTABLE - necessary for implementation

### 4. ConfidenceScore Value Object
**PRD**: `value (0-1)`, `factors[]`
**Brain Dump**: Mentions confidence but not formal scoring
**Assessment**: ACCEPTABLE - adds precision to assumption system

### 5. Assumption Category Enum (Implied)
**PRD**: Referenced in Pydantic model `AssumptionCategory`
**Brain Dump**: Not mentioned
**Assessment**: ACCEPTABLE - useful categorization

### 6. Node `linkedDocumentId`
**PRD**: Explicit field linking nodes to documents
**Brain Dump**: Mentions information being "brought up" when clicking nodes but not formal linking
**Assessment**: ACCEPTABLE - reasonable interpretation

**Overall Overreach Assessment**: No significant overreach. All additions are reasonable interpretations or necessary implementation details.

---

## Inconsistencies

### 1. VisualGraph Entity Missing
**Section 7.2 (Entities)**: Does not list `VisualGraph`
**Section 7.2 (Aggregates)**: Canvas Aggregate contains "VisualGraphs"
**Resolution**: Add VisualGraph entity to entity table

### 2. Context Routing as Bounded Context vs. Service
**Section 7.1**: Context Routing is shown as a bounded context
**Section 8.2**: Context Router is described as a module/service
**Resolution**: Clarify if Context Routing is a full bounded context or a cross-cutting service

### 3. Job Types Not Enumerated
**Section 7.2**: Job entity has `type` field
**Section 5**: References specific job types (deep_research)
**Section 7.4**: Invariant JI-001 mentions `deep_research` specifically
**Resolution**: Define JobType enum in domain model (deep_research, llm_judge, transcription, etc.)

### 4. Assumption Status Values Undefined
**Section 7.2**: Assumption has `status` field
**Section 5 (FR-005)**: Mentions confirm/reject/edit
**Resolution**: Define AssumptionStatus enum (pending, approved, rejected, modified)

### 5. MCP Capabilities Not Defined
**Section 7.2**: MCPServer has `capabilities[]`
**Section 5 (FR-009)**: Mentions tools are discovered
**Resolution**: Define Capability value object or reference MCP protocol specification

### 6. Node Types Not Enumerated
**Section 7.2**: Node entity exists
**Brain Dump**: Mentions different node types (concept nodes, document nodes, audio blocks as nodes)
**Resolution**: Define NodeType enum or clarify Node vs specialized block types

### 7. Event Consumer Specificity
**Section 7.5**: Events list consumers but some are vague ("UI (WebSocket)")
**Resolution**: Specify concrete UI components as consumers

---

## Recommended Fix Directives

### Section 7 - Domain Model

#### FIX-DM-001: Add Missing Entities
Add the following entities to Section 7.2:

```markdown
| TaskDAG | id, canvasId, name, tasks[], dependencies[], calendarSyncId | Workspace |
| VisualGraph | id, canvasId, name, nodes[], edges[], layout | Workspace |
| KnowledgeBase | id, userId, name, sources[], indexStatus | Integration |
| CalendarSync | id, mcpServerId, taskDAGId, eventMappings[] | Integration |
```

#### FIX-DM-002: Add Missing Value Objects
Add the following value objects:

```markdown
| TaskDependency | fromTaskId, toTaskId, dependencyType |
| GraphEdge | sourceNodeId, targetNodeId, label, weight |
| AssumptionStatus | enum: pending, approved, rejected, modified |
| JobType | enum: deep_research, llm_judge, transcription, custom |
| NodeType | enum: concept, document_link, audio_link, graph_link |
```

#### FIX-DM-003: Expand Canvas Aggregate
Update Canvas Aggregate to include TaskDAG:

```markdown
| Canvas Aggregate | Canvas | Nodes, Documents, AudioBlocks, VisualGraphs, TaskDAGs |
```

#### FIX-DM-004: Add TaskDAG Aggregate
Add new aggregate:

```markdown
| TaskDAG Aggregate | TaskDAG | Tasks, Dependencies, CalendarSync |
```

#### FIX-DM-005: Add Missing Invariants
Add business rules for new entities:

```markdown
| TI-001 | TaskDAG must be acyclic | Validation on dependency addition |
| TI-002 | CalendarSync requires active MCP connection | MCPManager validation |
| GI-001 | VisualGraph edges must reference existing nodes | Aggregate validation |
```

#### FIX-DM-006: Add Missing Events
Add events for new workflows:

```markdown
| TaskDAGCreated | Task DAG created | Persistence, Calendar Sync |
| TaskDAGSynced | DAG synced to calendar | UI, Notification |
| KnowledgeBaseQueried | KB search executed | Research Agent |
| EurekaNoteCaptured | Quick note created | Intent Decipherer, Canvas |
```

#### FIX-DM-007: Expand Glossary
Add missing terms:

```markdown
| **Task DAG** | Directed acyclic graph representing task dependencies with optional calendar sync |
| **Eureka Note** | Quick-capture thought or idea with minimal friction |
| **Knowledge Base** | Connected repository of documents/information for agent reference |
| **Live Dashboard** | Real-time visualization of external state from API endpoints |
| **Plan Mode** | Collaborative workflow for creating structured, actionable plans |
```

#### FIX-DM-008: Clarify Context Routing Status
Either:
- (A) Promote to full bounded context with its own entities (RoutingRule, RoutingHistory)
- (B) Demote to cross-cutting service and remove from bounded context diagram

Recommendation: Option (B) - Context Routing is more service-like

### Section 8 - Architecture

#### FIX-ARCH-001: Add TaskDAG Module
Add to Section 8.2:

```markdown
#### Task DAG Manager

| Aspect | Detail |
|--------|--------|
| **Where** | `/backend/app/taskdag/manager.py`, `/frontend/src/components/TaskDAG/` |
| **What** | Manages task DAG creation, dependency validation, calendar synchronization |
| **How** | Graph validation algorithms, MCP integration for calendar sync |
| **Why** | Enables structured planning workflows from brain dump; competitive advantage |
```

#### FIX-ARCH-002: Add Knowledge Base Module
Add to Section 8.2:

```markdown
#### Knowledge Base Connector

| Aspect | Detail |
|--------|--------|
| **Where** | `/backend/app/kb/connector.py` |
| **What** | Connects to external knowledge bases, enables associative search |
| **How** | MCP integration pattern, semantic search, caching |
| **Why** | Supports "connected knowledge base" requirement from brain dump |
```

#### FIX-ARCH-003: Update Repository Structure
Add directories to Section 11:

```
backend/
  app/
    taskdag/           # NEW: Task DAG management
    kb/                # NEW: Knowledge base connector
```

#### FIX-ARCH-004: Add API Endpoints
Add to Section 8.3:

```markdown
| `/api/taskdag` | POST | Create task DAG | Required |
| `/api/taskdag/{id}` | GET | Get task DAG | Required |
| `/api/taskdag/{id}/sync` | POST | Sync DAG to calendar | Required |
| `/api/kb` | GET | List knowledge bases | Required |
| `/api/kb/search` | POST | Search knowledge base | Required |
```

#### FIX-ARCH-005: Add WebSocket Events
Add to Section 8.3:

```markdown
| Server -> Client | `taskdag.synced` | { dagId, calendarEvents[] } |
| Server -> Client | `eureka.captured` | { noteId, suggestions[] } |
```

---

## Priority Matrix

| Fix ID | Priority | Effort | Rationale |
|--------|----------|--------|-----------|
| FIX-DM-001 | HIGH | Medium | TaskDAG is critical MVP feature |
| FIX-DM-002 | MEDIUM | Low | Improves type safety |
| FIX-DM-003 | HIGH | Low | Consistency fix |
| FIX-DM-004 | HIGH | Low | Supports FIX-DM-001 |
| FIX-DM-005 | MEDIUM | Low | Business rules for new entities |
| FIX-DM-006 | MEDIUM | Low | Event completeness |
| FIX-DM-007 | HIGH | Low | Ubiquitous language completeness |
| FIX-DM-008 | LOW | Low | Clarification only |
| FIX-ARCH-001 | HIGH | Medium | Module for critical feature |
| FIX-ARCH-002 | MEDIUM | Medium | Supports research workflows |
| FIX-ARCH-003 | HIGH | Low | Directory structure |
| FIX-ARCH-004 | HIGH | Low | API completeness |
| FIX-ARCH-005 | MEDIUM | Low | Real-time event support |

---

## Conclusion

The DDD model in the PRD is a solid foundation that captures most of the brain dump's intent. The primary gaps are:

1. **Task DAG** - This is a critical missing entity that is explicitly mentioned multiple times in the brain dump as a key differentiator
2. **Knowledge Base Connection** - Referenced repeatedly but not modeled
3. **Some bounded context boundaries need clarification** - particularly Context Routing

The model does NOT suffer from significant overreach - additions beyond the brain dump are reasonable implementation necessities.

**Recommendation**: Implement HIGH priority fixes before development begins, particularly FIX-DM-001 (TaskDAG entity) and FIX-ARCH-001 (TaskDAG module), as these represent core functionality from the original vision.
