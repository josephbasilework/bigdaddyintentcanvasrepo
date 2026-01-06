# Ambiguity Audit Report

**Auditor**: AUDITOR-AMBIGUITY-WHEREWHATHOWWHY
**Date**: 2026-01-03
**Documents Reviewed**: PRD.md, BACKLOG.md

---

## Summary

| Metric | Count |
|--------|-------|
| Areas audited | 42 |
| Clear (all 4 answered) | 18 |
| Partially clear (2-3 answered) | 16 |
| Ambiguous (0-1 answered) | 8 |

---

## Ambiguity Findings

### High Priority (BMAD will guess wrong)

| Area | Missing | Current Text | Suggested Clarification |
|------|---------|--------------|------------------------|
| **Context Router - Routing Algorithm** | HOW | "routes to handlers based on type and intent" | Specify: exact classification algorithm (ML model? regex? keyword?), priority rules when multiple handlers match, timeout handling, what happens when router itself fails |
| **Context Router - Fallback Behavior** | HOW, WHY | "fallback to user disambiguation" | Define: when exactly fallback triggers (confidence threshold?), what disambiguation UI looks like, how many retries before fallback, what happens if user dismisses disambiguation |
| **Intent Decipherer - Confidence Thresholds** | HOW | "high confidence (minimal assumptions)" | Specify: exact numeric thresholds (e.g., >0.9 = auto-approve, 0.5-0.9 = show assumptions, <0.5 = request clarification), how confidence is calculated |
| **MCP Security Validation - Security Rules** | WHAT, HOW | "security checks verify compliance with standards" | Define: exact validation rules, what "standards" means (allowlist? capability restrictions? signature verification?), what constitutes pass/fail, specific dangerous actions to block |
| **Agent Guardrails - Destructive Actions** | WHAT | "prevents destructive actions" | Enumerate: explicit list of destructive vs. safe actions, how novel actions are classified, what triggers confirmation vs. blocking |
| **Intent Index - Query/Matching Algorithm** | HOW | "relevance scoring is applied" | Specify: scoring algorithm (cosine similarity? BM25? exact match?), vector storage strategy (if any), embedding model, index update strategy |
| **WebSocket Message Format - State Updates** | WHAT | "JSON Patch format" | Define: exact patch schema, how conflicts are resolved, message ordering guarantees, what happens on malformed messages |
| **Multi-Intent Decomposition** | HOW | "each intent is routed independently" | Specify: decomposition algorithm, how overlapping intents are handled, sequencing vs. parallel execution, dependency detection between intents |

### Medium Priority

| Area | Missing | Current Text | Suggested Clarification |
|------|---------|--------------|------------------------|
| **Audio Transcription Service** | WHERE, HOW | "Whisper API or similar" | Specify: exact service (OpenAI Whisper API? local Whisper? cloud provider?), chunking strategy for long audio, real-time vs. batch, error handling for poor audio |
| **LLM-as-Judge - Perspective Configuration** | WHAT | "perspective configurations" | Define: what perspectives are available (optimist/pessimist? domain-specific?), how many perspectives run, whether user can configure them |
| **Canvas Virtualization Strategy** | HOW | "canvas virtualization for many nodes" | Specify: virtualization library/approach, threshold for virtualization (50 nodes? 100?), how off-screen nodes are handled, impact on search/selection |
| **Assumption Auto-Confirmation** | HOW, WHY | "auto-confirmed (high confidence)" | Specify: exact confidence threshold for auto-confirm, whether user can disable auto-confirm, audit trail for auto-confirmed assumptions |
| **Job Queue - Concurrency Limits** | WHAT | Celery/ARQ mentioned, no limits | Specify: max concurrent jobs, job priority levels, queue overflow behavior, job cancellation mechanism |
| **Research Agent - Source Discovery** | HOW | "source aggregation logic" | Specify: what sources are searched (web? internal docs? APIs?), how source credibility is assessed, deduplication strategy |
| **Node Position Uniqueness** | HOW, WHY | "position must be unique within Canvas" | Clarify: is this exact x,y uniqueness? minimum distance? what happens on position conflict? is snap-to-grid enforced? |
| **Document Content Format** | WHAT | "rich text with formatting" | Specify: exact format (HTML? Markdown? Tiptap JSON?), allowed formatting options, max document size, embedded media support |
| **MCP Manifest Structure** | WHAT | "static analysis of MCP manifest" | Define: exact manifest schema, required vs. optional fields, version compatibility rules |
| **Graph Layout Algorithm** | HOW | "force-directed or hierarchical" | Specify: which one is default, user toggle between them, layout parameters, performance for large graphs |

### Low Priority

| Area | Missing | Current Text | Suggested Clarification |
|------|---------|--------------|------------------------|
| **Error Logging - Correlation IDs** | HOW | "correlation IDs for request tracing" | Specify: ID format, propagation mechanism (header name), retention period |
| **Database Connection Pooling** | HOW | PostgreSQL mentioned, no pooling details | Specify: pool size, connection timeout, health check interval |
| **Session Timeout** | WHAT | "30 days inactive" retention | Specify: what counts as "activity", warning before expiration, data recovery options |
| **Keyboard Shortcuts** | WHAT | "keyboard-driven interfaces" | Define: default shortcut mappings, customization support, conflict resolution |
| **Canvas Zoom Limits** | WHAT | "smooth pan/zoom" | Specify: min/max zoom levels, zoom step size, double-click behavior |
| **File Upload Limits** | WHAT | "file attachments" supported | Specify: max file size, allowed types, storage location, virus scanning |
| **Rate Limiting** | HOW | "Gateway rate limited" mentioned | Specify: rate limit strategy for internal APIs, per-user vs. global limits |
| **Backup Schedule** | WHAT | "scheduled backups" mentioned | Specify: frequency, retention policy, storage location, encryption |

---

## Detailed Analysis by Module

### 1. Context Routing Pipeline (`/backend/app/context/router.py`)

**Current State**: WHERE and WHAT are clear. HOW and WHY are underspecified.

**Critical Gaps**:
- No algorithm specified for intent classification
- No priority rules when multiple handlers match
- No specification of what "decomposition" means algorithmically
- No timeout or circuit breaker patterns defined

**Risk**: BMAD will implement a naive if-else chain or random selection, leading to unpredictable routing.

### 2. Intent Deciphering (`/backend/app/agents/intent_decipherer.py`)

**Current State**: WHERE and WHAT are clear. HOW partially specified.

**Critical Gaps**:
- Confidence calculation method unspecified
- Threshold values for different actions unspecified
- No specification of how capability matching works
- No detail on how intent index query results influence assumptions

**Risk**: BMAD will hardcode arbitrary thresholds, leading to either too many or too few user confirmations.

### 3. MCP Security Validation (`/backend/app/mcp/security.py`)

**Current State**: WHERE is clear. WHAT, HOW, and WHY are vague.

**Critical Gaps**:
- No enumeration of security rules
- No definition of "dangerous actions"
- No manifest schema defined
- No specification of runtime monitoring scope

**Risk**: Security validation will be either too permissive (vulnerable) or too restrictive (breaks legitimate MCPs).

### 4. Agent Safety Guardrails (`/backend/app/safety/guardrails.py`)

**Current State**: WHERE is clear. WHAT is partially defined.

**Critical Gaps**:
- Allowed/Disallowed actions table is incomplete
- No algorithm for classifying "novel" actions
- No specification of confirmation UI flow
- No audit logging requirements specified

**Risk**: BMAD will implement incomplete blocklists, missing edge cases.

### 5. WebSocket State Sync (`/frontend/src/services/wsStateSync.ts`)

**Current State**: WHERE is clear. WHAT and HOW are underspecified.

**Critical Gaps**:
- JSON Patch mentioned but no schema
- No conflict resolution strategy
- No message ordering guarantees
- No reconnection state reconciliation

**Risk**: Race conditions and inconsistent state between clients and server.

### 6. User Intent Index (`/backend/app/domain/services/intent_index.py`)

**Current State**: WHERE is clear. HOW is vague.

**Critical Gaps**:
- Storage mechanism unclear (vector DB? PostgreSQL? in-memory?)
- Query algorithm unspecified
- No embedding model specified if using vectors
- No update/decay strategy for old patterns

**Risk**: Index will be ineffective (too slow or inaccurate), negating the learning benefit.

---

## Recommended Fix Directives

### High Priority Fixes

#### 1. Context Router Algorithm

**BEFORE (PRD Section 8.2)**:
```
**How**: `ContextRouter` class with pluggable strategies; integrates with Intent Decipherer
```

**AFTER**:
```
**How**:
1. `ContextRouter` uses a priority-ordered strategy pattern:
   - Priority 1: Exact command matching (slash commands like `/research`, `/calendar`)
   - Priority 2: ML classifier (DistilBERT fine-tuned on intent categories)
   - Priority 3: Keyword fallback (regex patterns for common phrases)
2. When multiple handlers match:
   - Highest priority strategy wins
   - If same priority, highest-confidence match wins
   - If tie, prompt user for disambiguation
3. Timeout: 500ms for classification; fallback to keyword after timeout
4. Circuit breaker: 3 consecutive failures → route to fallback handler for 30 seconds
```

#### 2. Intent Confidence Thresholds

**BEFORE (FR-004)**:
```
High confidence (minimal assumptions), very low confidence (request clarification)
```

**AFTER**:
```
Confidence thresholds (configurable per environment):
- CONFIDENCE_AUTO_EXECUTE = 0.95  # No assumptions shown, action taken immediately
- CONFIDENCE_SHOW_ASSUMPTIONS = 0.70  # Default: show assumptions for confirmation
- CONFIDENCE_REQUEST_CLARIFICATION = 0.40  # Below this, ask user to rephrase

Confidence calculation:
- Base confidence from LLM structured output
- +0.1 if pattern exists in user intent index with same resolution
- -0.1 if conflicting patterns exist
- Capped at 1.0, floored at 0.0
```

#### 3. MCP Security Rules

**BEFORE (FR-009, S-033)**:
```
Security validation passes
```

**AFTER**:
```
MCP Security Validation Rules:
1. Manifest Requirements:
   - MUST declare all capabilities upfront (tools, resources, prompts)
   - MUST include version field (semver)
   - MUST NOT request filesystem_write, shell_execute, or network_unrestricted capabilities

2. Capability Restrictions:
   - ALLOWED: calendar_read, calendar_write, document_read
   - REQUIRES_CONFIRMATION: document_write, email_send
   - BLOCKED: filesystem_write, code_execute, network_raw

3. Runtime Monitoring:
   - Tool calls logged with timestamp, input hash, output size
   - Rate limit: 100 tool calls per minute per MCP
   - Anomaly detection: alert if >10x normal call volume

4. Pass/Fail Criteria:
   - PASS: All manifest requirements met, no blocked capabilities
   - FAIL: Any blocked capability, missing required manifest fields
   - WARN: Unknown capabilities (log but allow)
```

#### 4. Destructive Actions Enumeration

**BEFORE (Section 9.3)**:
```
Allowed: Create/update canvas elements
Disallowed: Delete without confirmation
```

**AFTER**:
```
Action Classification Matrix:

| Action Category | Safe (No Confirm) | Needs Confirm | Blocked |
|----------------|-------------------|---------------|---------|
| Canvas | create_node, update_node_label, move_node | delete_node, clear_canvas | - |
| Documents | create_doc, update_doc | delete_doc | - |
| Jobs | create_job, cancel_own_job | cancel_others_job | delete_job_history |
| MCP | query_* | write_*, send_* | configure_mcp, remove_mcp |
| External | - | calendar_create_event | email_send, file_upload_external |
| System | - | - | modify_config, access_logs |

Novel Action Handling:
1. Extract action verb and target from tool call
2. If verb in [delete, remove, clear, send, upload, modify]: Needs Confirm
3. If target in [system, config, external, user_data]: Needs Confirm
4. Default: Safe
```

#### 5. WebSocket State Sync Protocol

**BEFORE (Section 8.3)**:
```
Server → Client: `state.update` { patch } (JSON Patch format)
```

**AFTER**:
```
WebSocket State Sync Protocol:

Message Schema:
{
  "type": "state.update",
  "sequence": 12345,           // Monotonically increasing per session
  "timestamp": "2026-01-03T12:00:00Z",
  "patch": [
    { "op": "add", "path": "/nodes/abc123", "value": {...} }
  ],
  "checksum": "sha256:abc..."  // Of resulting state
}

Conflict Resolution:
1. Server is authoritative
2. Client applies patch only if sequence = last_sequence + 1
3. If gap detected, client requests full state sync
4. Optimistic updates: client applies locally, reverts on server rejection

Reconnection:
1. Client sends last known sequence on reconnect
2. Server sends patches since that sequence (or full state if >100 patches)
3. Client validates checksum after applying patches
```

#### 6. Intent Index Implementation

**BEFORE (S-012)**:
```
Vector storage (optional) or keyword index; persistence to DB
```

**AFTER**:
```
Intent Index Implementation:

Storage: PostgreSQL with pgvector extension
Embedding Model: sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)

Schema:
- id: UUID
- user_id: UUID (foreign key)
- intent_text: TEXT (original input)
- embedding: VECTOR(384)
- resolution: JSONB (approved assumptions and actions taken)
- outcome: ENUM('success', 'failure', 'modified')
- created_at: TIMESTAMP

Query Algorithm:
1. Embed incoming input with same model
2. Cosine similarity search: SELECT * WHERE 1 - (embedding <=> query_embedding) > 0.7
3. Filter by user_id
4. Rank by similarity * recency_weight (decay factor: 0.99^days_old)
5. Return top 5 matches

Update Strategy:
- Insert on assumption approval
- Update outcome on action completion
- Prune entries older than 90 days with outcome='failure'
```

### Medium Priority Fixes

#### 7. Audio Transcription

**BEFORE**:
```
Whisper API or similar
```

**AFTER**:
```
Audio Transcription:
- Service: OpenAI Whisper API (whisper-1 model)
- Chunking: Split at 25MB or 10 minutes, whichever is smaller
- Processing: Batch (not real-time); job queued on upload completion
- Retry: 3 attempts with exponential backoff (1s, 2s, 4s)
- Fallback: Store "transcription_failed" status; allow manual retry
- Error handling: Log audio fingerprint (not content); notify user of failure
```

#### 8. LLM-as-Judge Perspectives

**BEFORE**:
```
perspective configurations
```

**AFTER**:
```
LLM-as-Judge Configuration:

Default Perspectives (for research reports):
1. "skeptic" - Challenges claims, looks for weak evidence
2. "advocate" - Steelmans the argument, finds supporting evidence
3. "synthesizer" - Identifies common ground and key tensions

Execution:
- Run all perspectives in parallel (Promise.all)
- Timeout per perspective: 30 seconds
- If perspective fails: proceed with available perspectives, note in output

User Configuration (Phase 2):
- Custom perspective prompts
- Enable/disable specific perspectives
- Adjust perspective count (1-5)
```

---

## Module Boundary Clarifications Needed

| Boundary | Question | Impact if Unclear |
|----------|----------|-------------------|
| Context Router vs. Intent Decipherer | Does router call decipherer, or are they peers? | Circular dependency or duplicate processing |
| Agent Orchestrator vs. Job Manager | Who owns job lifecycle? | Jobs may be orphaned or double-processed |
| MCP Manager vs. MCP Client | Is client owned by manager or independent? | Resource leaks, inconsistent state |
| State Store vs. Persistence Layer | Sync vs. async persistence? Debounce timing? | Data loss on crash, performance issues |
| AG-UI vs. WebSocket | Is AG-UI over WS, or separate channel? | Duplicate transport, complexity |

---

## Data Schema Clarifications Needed

### Assumption Schema

**Current**:
```python
class Assumption(BaseModel):
    id: str
    text: str
    category: AssumptionCategory
    confidence: float
    blocking: bool
    suggested_action: Optional[str]
```

**Needs Addition**:
```python
class Assumption(BaseModel):
    id: str
    text: str
    category: AssumptionCategory  # NEEDS: enum values defined
    confidence: float
    blocking: bool  # NEEDS: what makes an assumption "blocking"?
    suggested_action: Optional[str]
    # MISSING:
    original_input_id: str  # Link to source input
    depends_on: List[str]  # Other assumption IDs that must resolve first
    alternatives: List[str]  # Other possible interpretations
    created_at: datetime
    expires_at: Optional[datetime]  # Auto-reject if not resolved
```

### ContextPacket Schema

**Current**:
```python
class ContextPacket:
    source: str
    type: str
    payload: Any
    timestamp: datetime
```

**Needs Addition**:
```python
class ContextPacket(BaseModel):
    source: Literal["user_input", "agent", "mcp", "system"]
    type: Literal["text", "file", "audio", "event", "job_result"]
    payload: Union[TextPayload, FilePayload, AudioPayload, EventPayload]
    timestamp: datetime
    # MISSING:
    session_id: str
    correlation_id: str  # For tracing
    priority: Literal["low", "normal", "high", "urgent"]
    canvas_context: Optional[CanvasContextRef]  # Selected nodes, active doc
```

---

## Non-Functional Requirements Gaps

| NFR | Current | Needs |
|-----|---------|-------|
| Intent deciphering latency | "< 5 seconds" | Cold vs. warm path? P50/P95/P99? |
| Canvas node limit | "100 nodes smooth" | What happens at 101? Degradation strategy? |
| State persistence | "debounced auto-save" | Debounce interval? Max data loss window? |
| Job recovery | "recoverable after restart" | Recovery mechanism? Idempotency keys? |
| WebSocket connections | "reconnect within 5 seconds" | Max reconnection attempts? Backoff strategy? |

---

## Recommendations Summary

1. **Immediately clarify** the 8 High Priority items before BMAD begins implementation
2. **Add explicit schemas** for ContextPacket, Assumption (with enum values), and WebSocket messages
3. **Define module boundaries** with interface contracts (who calls whom, data flow direction)
4. **Enumerate all thresholds** as configuration constants with default values
5. **Create decision matrices** for routing, action classification, and error handling

---

*Report generated by AUDITOR-AMBIGUITY-WHEREWHATHOWWHY*
