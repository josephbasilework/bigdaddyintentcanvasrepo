# Consolidated Fix Directives

**Audit Run Date**: 2026-01-03
**Status**: ADJUDICATED AND PRIORITIZED
**Sources**: All 7 audit reports

---

## Executive Summary

| Audit | Key Finding | Fixes Required |
|-------|-------------|----------------|
| PRD Coverage | 77.6% covered (not 100%) | 6 missing items, 2 contradictions |
| Backlog Coverage | 88.4% actionable atoms mapped | 8 missing stories |
| Template Compliance | 87% compliant | Section 16, 17 need work |
| Ambiguity | 8 high-priority gaps | Algorithm/threshold specs needed |
| Secrets/Gateway | PASS | None required |
| DDD Architecture | Good with gaps | TaskDAG entity missing |
| BMAD Quality | 94/100 ready | Minor dependency fixes |

---

## Priority Classification

- **P1-CRITICAL**: Must fix before BMAD ingestion (blocks development)
- **P2-HIGH**: Should fix before development (causes ambiguity)
- **P3-MEDIUM**: Fix during development (improves quality)
- **P4-LOW**: Nice to have (documentation polish)

---

## P1-CRITICAL Fixes

### FD-001: Add Missing Items to Out-of-Scope Section
**File**: PRD.md
**Section**: 4.2 Out-of-Scope
**Source**: PRD Coverage Report

Add the following with rationale:

```markdown
### Explicitly Excluded from MVP (with Brain Dump Acknowledgment)

| Item | Brain Dump Reference | Rationale for Exclusion |
|------|---------------------|-------------------------|
| Associative Knowledge Base Search (BD-053) | "predefined associative sort of search" | Requires vector DB infrastructure; Phase 2 |
| Predefined Analysis Workflows (BD-054) | "useful analysis workflow that we can just throw" | MVP focuses on flexible, not predefined workflows |
| Lifecycle Hooks (BD-055) | "deterministic hooks after specific life cycles" | Agent pre/post hooks sufficient for MVP |
| Knowledge Base Entity (BD-065) | "connected knowledge base" | Document/node search sufficient for MVP |
| Coda-style Data Structures (BD-067) | "basic data structures like in Coda" | Out of scope; canvas provides spatial organization |
| Agent-to-Agent Protocol (BD-071) | "do something with agent agent protocol" | MCP is MVP integration standard; A2A is Phase 2 |
```

---

### FD-002: Resolve Compute Allocation Contradiction
**File**: PRD.md
**Section**: FR-011, Section 4.2
**Source**: PRD Coverage Report (BD-097)

**Issue**: Brain dump says "throw more compute at it"; PRD says "single LLM critique"

**Resolution**: Add clarification to FR-011:

```markdown
#### Implementation Note: Compute Allocation

MVP supports configurable perspective count (1-3 perspectives from single LLM model).
"Throwing more compute" is achieved via additional perspective iterations, not multiple provider calls.
Multi-model orchestration (true parallel multi-provider) is Phase 2.
```

---

### FD-003: Add TaskDAG Entity to Domain Model
**File**: PRD.md
**Section**: 7.2 Entities
**Source**: DDD Architecture Audit (FIX-DM-001)

Add to entity table:

```markdown
| TaskDAG | id, canvasId, name, tasks[], dependencies[], calendarSyncEnabled | Workspace |
| VisualGraph | id, canvasId, name, nodes[], edges[], layoutType | Workspace |
```

Add to Aggregates:

```markdown
| TaskDAG Aggregate | TaskDAG | Tasks, Dependencies |
```

Add invariants:

```markdown
| TI-001 | TaskDAG must be acyclic | Validation on dependency addition |
```

---

### FD-004: Normalize Backlog Task Dependencies
**File**: BACKLOG.md
**Source**: BMAD Quality Report

Fix mixed story/task dependencies:

```markdown
# Line ~1441: T-044
Change: Dependencies = T-013, S-014
To:     Dependencies = T-013, T-067

# Line ~1678: T-150
Change: Dependencies = T-147, S-024
To:     Dependencies = T-147, T-114
```

---

## P2-HIGH Fixes

### FD-005: Add Context Router Algorithm Specification
**File**: PRD.md
**Section**: 8.2 Context Router Module
**Source**: Ambiguity Report (High Priority)

Expand the HOW section:

```markdown
**How**:
1. `ContextRouter` uses a priority-ordered strategy pattern:
   - Priority 1: Exact command matching (slash commands like `/research`, `/calendar`)
   - Priority 2: Intent classification via LLM structured output
   - Priority 3: Keyword fallback (regex patterns for common phrases)
2. When multiple handlers match:
   - Highest priority strategy wins
   - If same priority, highest-confidence match wins
   - If tie, prompt user for disambiguation
3. Timeout: 500ms for classification; fallback to keyword after timeout
4. Circuit breaker: 3 consecutive failures → route to fallback handler for 30 seconds
```

---

### FD-006: Add Intent Confidence Thresholds
**File**: PRD.md
**Section**: FR-004, Section 9.1
**Source**: Ambiguity Report (High Priority)

Add explicit thresholds:

```markdown
#### Confidence Thresholds (Configurable)

| Threshold | Value | Behavior |
|-----------|-------|----------|
| CONFIDENCE_AUTO_EXECUTE | ≥ 0.95 | Execute without confirmation |
| CONFIDENCE_SHOW_ASSUMPTIONS | 0.70 - 0.94 | Show assumptions panel |
| CONFIDENCE_REQUEST_CLARIFICATION | < 0.70 | Request user to clarify |

**Confidence Calculation**:
- Base: LLM structured output confidence
- +0.1 if matching pattern in intent index
- -0.1 if conflicting patterns exist
- Capped at 1.0, floored at 0.0
```

---

### FD-007: Add MCP Security Rules Enumeration
**File**: PRD.md
**Section**: FR-009, S-033
**Source**: Ambiguity Report (High Priority)

Add explicit security rules:

```markdown
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
```

---

### FD-008: Add Destructive Actions Classification
**File**: PRD.md
**Section**: 9.3 Safety + Guardrails
**Source**: Ambiguity Report (High Priority)

Expand the Allowed/Disallowed table:

```markdown
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
```

---

### FD-009: Add Missing Stories to Backlog
**File**: BACKLOG.md
**Source**: Backlog Coverage Report

Add 4 new stories:

```markdown
### S-039: External API State Observer

**User Story**: As a power user, I want to observe and mirror state from external API endpoints, so that I can see live data on my canvas.

**Acceptance Criteria**:
- Given an API endpoint URL is configured, When the observer connects, Then state is polled at configured interval
- Given external state changes, When detected, Then canvas state is updated to reflect the change
- Given connection fails, When retry exhausted, Then user is notified with reconnection option

**Implementation Notes**:
- Where: `/backend/app/services/state_observer.py`
- What: Service that polls external APIs and syncs state to canvas
- How: Async polling with configurable interval, WebSocket upgrade path for Phase 2
- Why: Enables "live dashboard" use case from brain dump

**Test Notes**: Mock external API, test state sync, test failure recovery

---

### S-044: Knowledge Base Store

**User Story**: As a power user, I want my workspace information indexed in a knowledge store, so that I can search across all my content semantically.

**Acceptance Criteria**:
- Given information is added to workspace, When indexed, Then it is stored with searchable embeddings
- Given knowledge base is queried, When search executed, Then relevant entries returned with similarity scores
- Given entries have relationships, When queried, Then related entries are surfaced

**Implementation Notes**:
- Where: `/backend/app/persistence/knowledge_store.py`
- What: Vector-enabled knowledge store using pgvector
- How: Embed content on save, cosine similarity search
- Why: Enables "associative search" from brain dump

**Test Notes**: Test indexing, test search accuracy, test relationship traversal

---

### S-041: Associative Knowledge Search (Depends: S-044)

**User Story**: As a power user, I want to perform semantic/associative searches across my knowledge, so that I can find related concepts without exact keywords.

**Acceptance Criteria**:
- Given knowledge exists in store, When user triggers search, Then semantically similar entries are returned
- Given search context includes canvas elements, When search executed, Then results ranked by relevance to context

**Implementation Notes**:
- Where: `/backend/app/services/associative_search.py`
- What: Semantic search service over knowledge store
- How: Query embedding + similarity search + context boosting
- Why: Supports "connected knowledge base" requirement

**Test Notes**: Test semantic matching, test context relevance

---

### S-042: Lifecycle Hook System

**User Story**: As a developer, I want deterministic hooks that fire after specific lifecycle events, so that I can extend system behavior predictably.

**Acceptance Criteria**:
- Given a lifecycle event occurs (job_complete, assumption_approved), When hooks are registered, Then callbacks are invoked deterministically
- Given multiple hooks registered, When event fires, Then hooks execute in defined priority order

**Implementation Notes**:
- Where: `/backend/app/orchestration/lifecycle_hooks.py`
- What: Hook registration and execution engine
- How: Event enum, hook registry, priority-ordered execution
- Why: Enables "deterministic hooks after lifecycles" from brain dump

**Test Notes**: Test registration, test execution order, test error isolation
```

---

### FD-010: Add WebSocket State Sync Protocol
**File**: PRD.md
**Section**: 8.3 API Surface
**Source**: Ambiguity Report (High Priority)

Add protocol specification:

```markdown
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
```

---

### FD-011: Add Intent Index Implementation Details
**File**: PRD.md
**Section**: Section 12 or FR-012
**Source**: Ambiguity Report (High Priority)

Add implementation specification:

```markdown
#### Intent Index Implementation

**Storage**: PostgreSQL with pgvector extension
**Embedding Model**: sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)

**Schema**:
- id: UUID
- user_id: UUID
- intent_text: TEXT (original input)
- embedding: VECTOR(384)
- resolution: JSONB (approved assumptions, actions taken)
- outcome: ENUM('success', 'failure', 'modified')
- created_at: TIMESTAMP

**Query Algorithm**:
1. Embed incoming input with same model
2. Cosine similarity: WHERE 1 - (embedding <=> query) > 0.7
3. Rank by similarity * recency_weight (0.99^days_old)
4. Return top 5 matches

**Update Strategy**:
- Insert on assumption approval
- Update outcome on action completion
- Prune entries older than 90 days with outcome='failure'
```

---

## P3-MEDIUM Fixes

### FD-012: Expand Story Details in PRD Section 16
**File**: PRD.md
**Section**: 16.2 Stories
**Source**: Template Compliance Report (Fix 1)

For each story, ensure format includes:
- User story format ("As a... I want... so that...")
- Acceptance criteria (Given/When/Then)
- Implementation notes (Where/What/How/Why)
- Test notes

**Note**: If stories are detailed in BACKLOG.md, add reference:
```markdown
### 16.2 Stories

See [BACKLOG.md](./BACKLOG.md) for complete story specifications.

Summary: 38 stories across 7 epics, all with:
- Given/When/Then acceptance criteria
- Where/What/How/Why implementation notes
- Unit/Integration/E2E test notes
```

---

### FD-013: Expand Documentation Plan DoD Checklists
**File**: PRD.md
**Section**: 17 Documentation Plan
**Source**: Template Compliance Report (Fix 3)

Expand each document's DoD:

```markdown
### /docs/architecture.md

**Definition of Done Checklist**:
- [ ] Component diagram matches current codebase
- [ ] Data flow diagram shows all major paths
- [ ] All bounded contexts from Section 7 represented
- [ ] Gateway-only constraint explicitly stated
- [ ] Reviewed by tech lead
```

---

### FD-014: Add Missing Edge Case ACs to Stories
**File**: BACKLOG.md
**Source**: BMAD Quality Report

```markdown
# S-026: Add AC
- Given research job exceeds 5-minute timeout, When timeout occurs, Then partial results are saved and user is notified with extend option

# S-032: Add AC
- Given Google Calendar OAuth authentication fails, When user attempts operation, Then clear error with re-auth option is shown

# S-028: Add AC
- Given one perspective agent fails, When synthesis occurs, Then available perspectives are used with note about missing perspective
```

---

### FD-015: Add TaskDAG Module to Architecture
**File**: PRD.md
**Section**: 8.2 Module Breakdown
**Source**: DDD Architecture Audit (FIX-ARCH-001)

Add module:

```markdown
#### Task DAG Manager

| Aspect | Detail |
|--------|--------|
| **Where** | `/backend/app/taskdag/manager.py`, `/frontend/src/components/TaskDAG/` |
| **What** | Manages task DAG creation, dependency validation, calendar synchronization |
| **How** | Graph validation algorithms (cycle detection), MCP integration for calendar sync |
| **Why** | Enables structured planning workflows; supports "task DAG" feature from brain dump |
```

---

### FD-016: Add Glossary Terms
**File**: PRD.md
**Section**: 7.3 Ubiquitous Language Glossary
**Source**: DDD Architecture Audit (FIX-DM-007)

Add terms:

```markdown
| **Task DAG** | Directed acyclic graph representing task dependencies with optional calendar sync |
| **Eureka Note** | Quick-capture thought or idea with minimal friction input |
| **Knowledge Base** | Connected repository of workspace information for semantic search |
| **Live Dashboard** | Real-time visualization of external state from API endpoints |
```

---

## P4-LOW Fixes

### FD-017: Enhance Changelog
**File**: PRD.md
**Section**: 0 Document Control
**Source**: Template Compliance Report (Fix 4)

Add structure:

```markdown
### Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-01-03 | PRD Generator | Initial draft |
| 1.1.0 | 2026-01-03 | Audit Process | Post-audit hardening (see RELEASE_NOTES.md) |
```

---

### FD-018: Clarify Component Relationships
**File**: BACKLOG.md
**Section**: S-006 Notes
**Source**: BMAD Quality Report

Add clarification:

```markdown
**Component Architecture Note**:
- `/frontend/src/components/primitives/`: Abstract base components
- `/frontend/src/components/Canvas/`: Canvas-specific implementations
- T-029 (Node primitive) → T-090 (Canvas Node with drag behavior)
- T-030 (Edge primitive) → T-094 (Canvas Edge with connection handling)
```

---

## Application Order

Apply fixes in this order to maintain document consistency:

1. **PRD.md** (P1 first, then P2, P3, P4)
   - FD-001 (Out-of-scope additions)
   - FD-002 (Compute allocation clarification)
   - FD-003 (TaskDAG entity)
   - FD-005 (Router algorithm)
   - FD-006 (Confidence thresholds)
   - FD-007 (MCP security rules)
   - FD-008 (Action classification)
   - FD-010 (WebSocket protocol)
   - FD-011 (Intent index)
   - FD-012 (Story section reference)
   - FD-013 (Doc plan DoD)
   - FD-015 (TaskDAG module)
   - FD-016 (Glossary)
   - FD-017 (Changelog)

2. **BACKLOG.md**
   - FD-004 (Dependency normalization)
   - FD-009 (New stories S-039, S-041, S-042, S-044)
   - FD-014 (Edge case ACs)
   - FD-018 (Component clarification)

3. **PRD_TRACEABILITY.md**
   - Update to reflect 98 atoms
   - Update coverage percentages
   - Add new story mappings

4. **PRD_VERIFICATION.md**
   - Regenerate with audit findings
   - Document applied fixes

---

## Fix Directive Count

| Priority | Count | Status |
|----------|-------|--------|
| P1-CRITICAL | 4 | To Apply |
| P2-HIGH | 7 | To Apply |
| P3-MEDIUM | 5 | To Apply |
| P4-LOW | 2 | To Apply |
| **TOTAL** | **18** | - |

---

*Fix directives compiled 2026-01-03 from 7 audit reports*
