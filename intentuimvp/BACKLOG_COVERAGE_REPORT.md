# Backlog Coverage Audit Report

**Generated**: 2026-01-03
**Auditor**: AUDITOR-COVERAGE-BACKLOG
**ATOMS.md Version**: 98 atoms
**BACKLOG.md Version**: 1.0.0

---

## Summary

| Metric | Count | Percentage |
|--------|-------|------------|
| **Total Atoms** | 98 | 100% |
| **Actionable Atoms** | 69 | 70.4% |
| **Mapped to Backlog** | 61 | 88.4% |
| **Missing from Backlog** | 8 | 11.6% |
| **Inadequate Detail** | 6 | - |

**Breakdown of Actionable Categories:**
- Features: 32 (all actionable)
- Workflows: 15 (all actionable)
- Data Entities: 12 (all actionable)
- Integrations: 10 (all actionable)

**Non-Actionable Categories (excluded from coverage check):**
- Constraints: 8 (design constraints, not features)
- Non-Functional Requirements: 8 (quality attributes)
- Risks/Concerns: 5 (risk items)
- Vision/Philosophy: 8 (strategic guidance)

---

## Coverage Matrix

### Features (BD-001 to BD-032)

| Atom ID | Statement | Epic | Story | Tasks | Status | Notes |
|---------|-----------|------|-------|-------|--------|-------|
| BD-001 | Command-driven interface (not chatbot) | E-001 | S-001 | T-002-T-006 | COVERED | Canvas-based workspace distinct from chatbot |
| BD-002 | UI-driven interface | E-001, E-004 | S-001, S-006 | T-002-T-006, T-029-T-034 | COVERED | Canvas + component library |
| BD-003 | Long-term persistence of information | E-007 | S-035, S-036, S-037, S-038 | T-159-T-176 | COVERED | Full persistence epic |
| BD-004 | Modular connections/integrations | E-006 | S-030, S-031, S-034 | T-139-T-158 | COVERED | MCP integration epic |
| BD-005 | Configure MCP servers within session | E-006 | S-034 | T-155-T-158 | COVERED | Dynamic MCP addition |
| BD-006 | LLM as judge pattern | E-005 | S-028 | T-129-T-133 | COVERED | JudgeWorkflow implementation |
| BD-007 | Multiple perspectives (5 critiques) | E-005 | S-028 | T-130 | COVERED | Perspective agents |
| BD-008 | Combine LLM perspectives into synthesis | E-005 | S-028 | T-132 | COVERED | Synthesis agent |
| BD-009 | Persist results for later reference | E-005, E-007 | S-029, S-035 | T-134-T-138, T-159 | COVERED | Artifact storage |
| BD-010 | Continue work within session after saving | E-001, E-007 | S-002, S-035 | T-007-T-012, T-162 | COVERED | Auto-save + state continuity |
| BD-011 | Observe state from API endpoints | E-006 | - | - | **MISSING** | No story for API state observation |
| BD-012 | Visual representation of observed state | E-004 | S-022 | T-102-T-105 | PARTIAL | Graph viz exists but not for external state |
| BD-013 | Live dashboards via polling/WebSocket | E-001 | S-003, S-027 | T-013-T-018, T-125-T-128 | COVERED | WebSocket infrastructure |
| BD-014 | State mutation through integrations | E-006 | S-032 | T-147-T-150 | COVERED | Calendar modification via MCP |
| BD-015 | Task DAG display | E-004 | S-024 | T-110-T-114 | COVERED | DAGView component |
| BD-016 | Self-modifying workflows | E-006 | S-034 | T-155-T-158 | COVERED | Dynamic MCP addition |
| BD-017 | Request new MCP servers with standards | E-006 | S-033, S-034 | T-151-T-158 | COVERED | Security validation + dynamic add |
| BD-018 | Text box input for context entry | E-002 | S-007 | T-035-T-038 | COVERED | TextInput component |
| BD-019 | Drag-and-drop file input | E-002 | S-007 | T-036 | COVERED | FileDrop component |
| BD-020 | Microphone/voice input | - | - | - | **MISSING** | No story for real-time voice input |
| BD-021 | Canvas for stateful context management | E-001, E-004 | S-001, S-019-S-024 | T-002-T-006, T-090-T-114 | COVERED | Canvas workspace |
| BD-022 | Nodes on canvas with labels | E-004 | S-019 | T-090-T-093 | COVERED | Node component |
| BD-023 | Documents on canvas | E-004 | S-021 | T-098-T-101 | COVERED | DocumentBlock component |
| BD-024 | Audio blocks on canvas | E-002 | S-013 | T-062-T-066 | COVERED | AudioBlock component |
| BD-025 | Streaming updates from jobs via WebSocket | E-005 | S-027 | T-125-T-128 | COVERED | Job progress streaming |
| BD-026 | User commands to configure MCP servers | E-006 | S-034 | T-158 | COVERED | MCP add/remove API |
| BD-027 | Render assumptions in dedicated UI area | E-002 | S-011 | T-052-T-056 | COVERED | AssumptionPanel |
| BD-028 | Button-based responses to assumptions | E-002 | S-011 | T-054 | COVERED | Approval/rejection handlers |
| BD-029 | Capture random eureka thoughts/notes | E-002, E-004 | S-007, S-021 | T-035, T-098-T-101 | PARTIAL | Text input exists but no "quick capture" mode |
| BD-030 | Label notes quickly | E-004 | S-019, S-023 | T-091, T-106-T-109 | COVERED | Node labels + annotations |
| BD-031 | Highly annotatable graphs | E-004 | S-022, S-023 | T-102-T-109 | COVERED | Graph + annotation layer |
| BD-032 | Click nodes to bring up information | E-004 | S-022 | T-104 | COVERED | Node click focus |

### Workflows (BD-041 to BD-055)

| Atom ID | Statement | Epic | Story | Tasks | Status | Notes |
|---------|-----------|------|-------|-------|--------|-------|
| BD-041 | Deep research job workflow | E-005 | S-026, S-027 | T-120-T-128 | COVERED | DeepResearchJob + streaming |
| BD-042 | LLM-as-judge critique workflow | E-005 | S-028 | T-129-T-133 | COVERED | JudgeWorkflow |
| BD-043 | Context routing workflow | E-002 | S-008 | T-039-T-043 | COVERED | Context router |
| BD-044 | Intent/meaning deciphering workflow | E-002 | S-009 | T-044-T-047 | COVERED | IntentDecipherer agent |
| BD-045 | Assumption reconciliation workflow | E-002 | S-011 | T-052-T-056 | COVERED | AssumptionPanel + handlers |
| BD-046 | Audio block analysis workflow | E-002 | S-013 | T-062-T-066 | COVERED | AudioBlock + transcription |
| BD-047 | Multiple deep research reports from tangent | E-005 | S-026 | T-120 | PARTIAL | Single research job exists; spawning multiple not explicit |
| BD-048 | Hypothesis testing with LLM judges | E-005 | S-028 | T-129-T-133 | COVERED | Perspective agents |
| BD-049 | Collaborative planning with agentic system | E-002, E-003 | S-009, S-016 | T-044-T-047, T-076-T-080 | PARTIAL | Intent + orchestration exist but no explicit "planning mode" |
| BD-050 | Plan to task DAG conversion | E-004 | S-024 | T-110-T-114 | PARTIAL | DAGView exists but no auto-conversion from plan |
| BD-051 | Task DAG to Google Docs export | E-006 | S-032 | T-147-T-150 | PARTIAL | Calendar sync exists; Google Docs export is ASSUMPTION-004 |
| BD-052 | Task completion state mutation with propagation | E-004 | S-024 | T-112 | COVERED | Status-based styling implies state tracking |
| BD-053 | Associative search through knowledge base | - | - | - | **MISSING** | No explicit knowledge base search story |
| BD-054 | Predefined analysis workflows | E-003 | S-016 | T-076-T-080 | PARTIAL | Orchestrator exists but no predefined workflow catalog |
| BD-055 | Deterministic hooks after lifecycles | - | - | - | **MISSING** | No explicit lifecycle hook story |

### Data Entities (BD-056 to BD-067)

| Atom ID | Statement | Epic | Story | Tasks | Status | Notes |
|---------|-----------|------|-------|-------|--------|-------|
| BD-056 | Canvas: stateful space | E-001, E-007 | S-001, S-035 | T-002, T-159-T-163 | COVERED | Canvas state persistence |
| BD-057 | Nodes: labeled entities | E-004 | S-019 | T-090-T-093 | COVERED | Node component |
| BD-058 | Documents: persistable text | E-004 | S-021 | T-098-T-101 | COVERED | DocumentBlock |
| BD-059 | Audio blocks | E-002 | S-013 | T-062-T-066 | COVERED | AudioBlock component |
| BD-060 | Jobs: async tasks | E-005 | S-025 | T-115-T-119 | COVERED | Job queue infrastructure |
| BD-061 | Assumption structure | E-002 | S-010 | T-048-T-051 | COVERED | Assumption Pydantic model |
| BD-062 | User intent/meaning index | E-002 | S-012 | T-057-T-061 | COVERED | Intent index service |
| BD-063 | Task DAG with granularities | E-004 | S-024 | T-110-T-114 | COVERED | DAGView + critical path |
| BD-064 | Single source of truth (external state) | E-006 | - | - | **MISSING** | No explicit external state mirroring story |
| BD-065 | Knowledge base (connected info store) | - | - | - | **MISSING** | No explicit knowledge base entity/store |
| BD-066 | Session: current working context | E-001 | S-002 | T-007-T-012 | COVERED | Global state store |
| BD-067 | Basic data structures with UI mappings | E-004 | S-006 | T-029-T-034 | PARTIAL | Component library exists but no Coda-style data structures |

### Integrations (BD-068 to BD-077)

| Atom ID | Statement | Epic | Story | Tasks | Status | Notes |
|---------|-----------|------|-------|-------|--------|-------|
| BD-068 | Google Calendar MCP integration | E-006 | S-032 | T-147-T-150 | COVERED | GoogleCalendarMCP |
| BD-069 | Agent can alter Google Calendar | E-006 | S-032 | T-149 | COVERED | Bidirectional sync |
| BD-070 | MCP as integration standard | E-006 | S-030, S-031 | T-139-T-146 | COVERED | MCPRegistry + MCPClient |
| BD-071 | Agent-to-Agent Protocol support | - | - | - | **MISSING** | No A2A protocol story |
| BD-072 | WebSocket/polling for live state | E-001 | S-003 | T-013-T-018 | COVERED | WebSocket infrastructure |
| BD-073 | API endpoint state observation | E-006 | - | - | **MISSING** | Same as BD-011 |
| BD-074 | Google Docs integration | E-006 | S-032 | T-147 (ASSUMPTION) | PARTIAL | Assumed via MCP; no explicit story |
| BD-075 | Calendar integration for reminders | E-006 | S-032 | T-147-T-150 | COVERED | Google Calendar MCP |
| BD-076 | Obsidian as persistence backend | E-007 | S-038 | T-172-T-176 | PARTIAL | Git backup exists; Obsidian not explicit |
| BD-077 | Git repos for backups | E-007 | S-038 | T-174 | COVERED | Git integration (optional) |

---

## Missing Items

The following actionable atoms are NOT represented in the backlog:

### Critical Gaps

| Atom ID | Statement | Category | Recommended Action |
|---------|-----------|----------|-------------------|
| BD-011 | Observe state from API endpoints | Feature | **ADD STORY S-039**: Implement External API State Observer |
| BD-020 | Microphone/voice input | Feature | **ADD STORY S-040**: Implement Real-Time Voice Input (Flagged as MVP scope question in ATOMS.md) |
| BD-053 | Associative search through knowledge base | Workflow | **ADD STORY S-041**: Implement Knowledge Base Search Service |
| BD-055 | Deterministic hooks after lifecycles | Workflow | **ADD STORY S-042**: Implement Lifecycle Hook System |
| BD-064 | Single source of truth (external state mirroring) | Data | **ADD STORY S-043**: Implement External State Synchronization |
| BD-065 | Knowledge base (connected info store) | Data | **ADD STORY S-044**: Implement Knowledge Base Entity & Store |
| BD-071 | Agent-to-Agent Protocol support | Integration | **ADD STORY S-045**: Implement A2A Protocol Adapter |
| BD-073 | API endpoint state observation | Integration | Duplicate of BD-011 - resolve with S-039 |

---

## Weak Stories (Inadequate AC or Detail)

### Stories Needing Improvement

| Story | Issue | Recommended Fix |
|-------|-------|-----------------|
| **S-013** (Audio Block Transcription) | Missing AC for search/filter by transcript content | Add AC: "Given transcripts exist, When searched, Then results highlight matching text" |
| **S-024** (Task DAG Visualization) | No AC for converting natural language plan to DAG | Add AC: "Given a collaborative plan, When DAG conversion is triggered, Then tasks are extracted and connected" |
| **S-032** (Google Calendar MCP) | No AC for Google Docs export | Either add explicit AC or create separate story S-046 for Google Docs MCP |
| **S-026** (Deep Research Job) | No AC for spawning multiple research jobs from one input | Add AC: "Given a tangent with multiple research questions, When processed, Then multiple research jobs are dispatched in parallel" |
| **S-022** (Graph Visualization) | Missing clustering algorithm specification | Add implementation note specifying clustering approach (k-means, community detection) |
| **S-016** (Agent Orchestrator) | No explicit predefined workflow catalog | Add AC: "Given predefined workflows exist, When context matches a workflow pattern, Then the workflow is suggested to user" |

### Stories Missing File/Module Hints

All stories have file/module hints - this requirement is satisfied.

### Stories Missing Given/When/Then AC

All stories have proper Given/When/Then acceptance criteria - this requirement is satisfied.

---

## Ordering/Dependency Issues

### Issue 1: Orphaned Dependency
**S-024 (Task DAG)** depends implicitly on data from the intent deciphering system but this is not explicitly stated.

**Recommendation**: Add explicit dependency note: "Requires S-009 (Intent Deciphering) for plan extraction"

### Issue 2: Knowledge Base Circular Dependency Risk
**BD-053** (associative search) and **BD-065** (knowledge base) are both missing. If added:
- Knowledge base store must be created before search service
- Intent index (S-012) could leverage knowledge base

**Recommendation**: Add knowledge base in Stream E (Persistence), add search in Stream A (Context & Intent)

### Issue 3: External State Observation Gap
**BD-011**, **BD-064**, **BD-073** all relate to observing external API state. These should be consolidated into a single epic or feature area.

**Recommendation**: Create new Epic E-008: External State Observation, or add as sub-feature to E-006 (MCP Integration)

### Issue 4: Voice Input Placement
**BD-020** (voice input) is flagged as "maybe MVP" in ATOMS.md. If included, it should be in Stream A (Context & Intent) after S-013 (Audio Block).

**Recommendation**: Validate scope with stakeholder. If included, add as S-040 with dependency on S-013.

### Issue 5: A2A Protocol Missing
**BD-071** (Agent-to-Agent Protocol) is a significant integration point that has no coverage. This could affect multi-agent orchestration.

**Recommendation**: Add S-045 to Stream D (MCP Integration) or create dedicated epic if scope is large.

---

## Recommended Fix Directives

### Priority 1: Critical Missing Stories (Add Immediately)

```
DIRECTIVE: ADD_STORY
ID: S-039
Title: External API State Observer
Epic: E-006
Description: Implement capability to observe and mirror state from external API endpoints
AC:
- Given an API endpoint URL is configured
  When the observer connects
  Then state is polled at configured interval or via WebSocket
- Given external state changes
  When detected
  Then canvas state is updated to reflect change
- Given connection fails
  When retry exhausted
  Then user is notified with reconnection option
Files: /backend/app/services/state_observer.py, /frontend/src/hooks/useExternalState.ts
Tasks:
- T-177: Create StateObserver service
- T-178: Implement polling/WebSocket adapter
- T-179: Add state reconciliation logic
- T-180: Create useExternalState hook
Coverage: BD-011, BD-064, BD-073
```

```
DIRECTIVE: ADD_STORY
ID: S-044
Title: Knowledge Base Store
Epic: E-007
Description: Implement a connected, persistent knowledge store for workspace information
AC:
- Given information is added to workspace
  When indexed
  Then it is stored in knowledge base with embeddings
- Given knowledge base is queried
  When search executed
  Then relevant entries are returned with similarity scores
- Given entries have relationships
  When queried
  Then related entries are surfaced
Files: /backend/app/persistence/knowledge_store.py, /backend/app/domain/models/knowledge_entry.py
Tasks:
- T-181: Define knowledge entry schema
- T-182: Implement vector storage adapter
- T-183: Add indexing service
- T-184: Create query interface
Coverage: BD-065
```

```
DIRECTIVE: ADD_STORY
ID: S-041
Title: Associative Knowledge Search
Epic: E-002
Description: Enable associative/semantic search across connected knowledge base
AC:
- Given knowledge exists in store
  When user triggers associative search
  Then semantically similar entries are returned
- Given search context includes canvas elements
  When search executed
  Then results are ranked by relevance to context
Files: /backend/app/services/associative_search.py
Tasks:
- T-185: Create associative search service
- T-186: Implement relevance scoring
- T-187: Add search API endpoint
- T-188: Integrate with context router
Coverage: BD-053
Dependencies: S-044
```

### Priority 2: Scope Validation Required

```
DIRECTIVE: VALIDATE_SCOPE
ID: BD-020
Question: Is real-time voice/microphone input in MVP scope?
If YES: Add S-040 (Voice Input)
If NO: Document as post-MVP in backlog
```

```
DIRECTIVE: VALIDATE_SCOPE
ID: BD-071
Question: Is Agent-to-Agent Protocol required for MVP?
If YES: Add S-045 (A2A Protocol Adapter) to E-006
If NO: Document as post-MVP integration
```

### Priority 3: Story Enhancements

```
DIRECTIVE: ENHANCE_STORY
ID: S-024
Add AC:
- Given a natural language plan is created collaboratively
  When DAG conversion is triggered
  Then tasks are extracted with inferred dependencies
- Given multiple research questions emerge from a tangent
  When processed
  Then each spawns a separate deep research job
```

```
DIRECTIVE: ENHANCE_STORY
ID: S-026
Add AC:
- Given an input contains multiple research questions
  When processed by research orchestrator
  Then multiple DeepResearchJob instances are dispatched in parallel
- Given spawned jobs complete
  When results are ready
  Then they are aggregated with links to originating tangent
```

```
DIRECTIVE: ADD_LIFECYCLE_STORY
ID: S-042
Title: Lifecycle Hook System
Epic: E-003
Description: Implement deterministic hooks that fire after specific agent/workflow lifecycles
AC:
- Given a lifecycle event occurs (job complete, assumption approved, etc.)
  When hooks are registered
  Then registered callbacks are invoked deterministically
- Given a hook is registered
  When its lifecycle event fires
  Then hook executes in defined order with access to event context
Files: /backend/app/orchestration/lifecycle_hooks.py
Tasks:
- T-189: Define lifecycle event enum
- T-190: Create hook registration service
- T-191: Implement hook execution engine
- T-192: Add hook configuration API
Coverage: BD-055
```

### Priority 4: Documentation Updates

```
DIRECTIVE: UPDATE_BACKLOG
Section: ASSUMPTIONS MADE
Add:
- ASSUMPTION-009: External API state observation will use polling initially; WebSocket upgrade as enhancement. Rationale: MVP simplicity.
- ASSUMPTION-010: Knowledge base will use vector embeddings for semantic search. Rationale: Industry standard for associative search.
```

```
DIRECTIVE: UPDATE_COVERAGE_MAP
Add to Brain Dump Feature Coverage table:
| F016 | External API state observation | E-006 | S-039 | T-177-T-180 |
| F017 | Knowledge base with associative search | E-007, E-002 | S-044, S-041 | T-181-T-188 |
| F018 | Lifecycle hooks for deterministic workflows | E-003 | S-042 | T-189-T-192 |
```

---

## Audit Conclusion

The backlog achieves **88.4% coverage** of actionable atoms, which is strong for a draft backlog. The primary gaps are:

1. **External state observation** (BD-011, BD-064, BD-073) - A coherent feature area that needs a dedicated story
2. **Knowledge base** (BD-053, BD-065) - A foundational capability for associative search
3. **Voice input** (BD-020) - Scope needs validation before adding
4. **A2A Protocol** (BD-071) - Integration scope needs validation
5. **Lifecycle hooks** (BD-055) - Infrastructure for deterministic workflows

The backlog structure is well-organized with clear epics, stories with proper Given/When/Then AC, and detailed task breakdowns with file hints. Dependencies are mostly explicit, though a few ordering issues were identified.

**Recommended Next Steps:**
1. Add the 4 Priority 1 stories immediately
2. Validate scope for BD-020 and BD-071 with stakeholders
3. Apply Priority 3 story enhancements
4. Update coverage map and assumptions

---

*Generated by AUDITOR-COVERAGE-BACKLOG agent*
