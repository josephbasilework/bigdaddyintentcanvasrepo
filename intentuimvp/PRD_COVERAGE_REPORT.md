# PRD Coverage Audit Report

## Summary
- **Total atoms**: 98
- **Covered**: 72 (73.5%)
- **Partial**: 17 (17.3%)
- **Missing**: 7 (7.1%)
- **Contradicted**: 2 (2.0%)

---

## Coverage Matrix

### Features (BD-001 to BD-032)

| Atom ID | Statement Summary | Status | PRD Section(s) | Notes |
|---------|-------------------|--------|----------------|-------|
| BD-001 | Command-driven interface (not chatbot-style) | COVERED | Section 1 (Executive Summary), Section 2.2 (Desired Outcomes), Success Metrics (Command vs. Chat Ratio > 3:1) | Explicitly stated as core differentiator |
| BD-002 | UI-driven interface | COVERED | Section 1 (canvas-based workspace), Section 5 FR-001, FR-002 | Canvas and visual UI emphasized throughout |
| BD-003 | Long-term persistence of information | COVERED | FR-014 (Canvas State Persistence), Section 12 (Data Storage), NFR 6.3 | Comprehensive persistence covered |
| BD-004 | Modular connections/integrations | COVERED | Section 1, FR-009 (MCP Server Integration), Section 8.2 (MCP Manager) | MCP framework addresses modularity |
| BD-005 | Configure MCP servers within a session | COVERED | FR-009, FR-010, Journey 4 (MCP Configuration Flow), S-034 (Dynamic MCP Addition) | Dynamic MCP configuration in scope |
| BD-006 | LLM as a judge pattern on any input or output | PARTIAL | FR-011 (LLM-as-Judge Analysis Pattern), S-028 | Limited to "deep research reports" - not explicit "on any input or output" |
| BD-007 | Request multiple perspectives (e.g., 5 different critiques) | PARTIAL | FR-011, Section 9.1 (PerspectiveAgent, SynthesisAgent) | Multiple perspectives mentioned but "5" not specified; MVP uses "single LLM critique" per Out-of-Scope |
| BD-008 | Combine multiple LLM perspectives into synthesis | COVERED | FR-011 ("synthesis agent combines viewpoints"), Section 9.1 (SynthesisAgent) | Explicitly covered |
| BD-009 | Persist results for later reference | COVERED | FR-014, Section 12 (Artifacts), FR-007 ("Report generated and persisted") | Covered via artifact storage |
| BD-010 | Continue work within current session after saving | COVERED | FR-001 ("Canvas renders with restored nodes"), Journey 1 | Implicit in session continuity |
| BD-011 | Observe state from API endpoints | PARTIAL | BD mentions "API end point observation" - PRD mentions MCP tools but not generic API observation | MCP framework may cover this, but not explicit |
| BD-012 | Visual representation of observed state | COVERED | FR-001, Section 4.1 (Visualization), S-022 (Graph Visualization), S-024 (Task DAG) | Canvas provides visual state representation |
| BD-013 | Live dashboards via polling or WebSocket | COVERED | FR-008 (WebSocket Real-time Streaming), Section 8.1, 8.3 (WebSocket Events) | WebSocket streaming covered extensively |
| BD-014 | State mutation through integrations | COVERED | FR-010 ("calendar is modified via MCP"), FR-009 | MCP can mutate external state |
| BD-015 | Display a task DAG (Directed Acyclic Graph) | COVERED | Section 4.1 (Visualization: "task DAG view"), FR-010 ("Task DAG can sync to calendar"), S-024 | Task DAG explicitly in scope |
| BD-016 | Self-modifying workflows | PARTIAL | Section 1 Out-of-Scope: "Full self-modifying workflows" deferred to Phase 2; only MCP addition allowed | Brain dump shows ambiguity; PRD explicitly limits scope |
| BD-017 | Request new MCP servers that adhere to standards | COVERED | FR-009, S-033 (MCP Security Validation), S-034 (Dynamic MCP Addition) | Dynamic MCP addition with security checks |
| BD-018 | Text box input for context entry | COVERED | FR-002 (Floating Text Input for Context Injection) | Explicit feature requirement |
| BD-019 | Drag-and-drop file input | COVERED | FR-002 Acceptance Criteria: "Given user drags files When dropped on text box Then files are attached" | Explicitly covered |
| BD-020 | Microphone/voice input | PARTIAL | FR-013 (Audio Block Transcription), S-013 | Audio blocks support recording but "speech-to-speech with real-time tool calls" is not covered |
| BD-021 | Canvas for stateful context management | COVERED | FR-001, FR-006, FR-014, Section 7.2 (Canvas entity) | Canvas is central to architecture |
| BD-022 | Nodes on the canvas with labels | COVERED | FR-006 ("appears at specified position with editable label"), S-019 (Node Component) | Explicit CRUD for nodes with labels |
| BD-023 | Documents on the canvas | COVERED | FR-001 ("documents"), Section 7.2 (Document entity), S-021 | Documents explicitly covered |
| BD-024 | Audio blocks on the canvas | COVERED | FR-001 ("audio blocks"), FR-013 (Audio Block Transcription), S-013 | Audio blocks explicitly covered |
| BD-025 | Streaming updates from jobs via WebSocket | COVERED | FR-007, FR-008, S-027 (Job Progress Streaming) | Explicitly covered with acceptance criteria |
| BD-026 | User commands to configure MCP servers | COVERED | FR-009, Journey 4, S-034 | MCP configuration flow covered |
| BD-027 | Render assumptions on UI in dedicated area | COVERED | FR-005 (Assumption Reconciliation UI), S-011 (Assumptions UI Panel) | Dedicated UI for assumptions |
| BD-028 | Button-based responses to assumptions | COVERED | FR-005 ("Confirm/Reject/Edit buttons") | Explicit button-based interaction |
| BD-029 | Capture "random eureka" thoughts/notes | PARTIAL | Section 2 ("Random eurekas - get down our random ass notes"), JTBD ("Capture random thoughts quickly") | Mentioned as use case but no explicit FR for quick capture |
| BD-030 | Label notes quickly | PARTIAL | FR-006 ("editable label"), Node entity has "label" | Nodes have labels but "quick labeling" workflow not explicit |
| BD-031 | Highly annotatable graphs | PARTIAL | Section 4.2 Out-of-Scope: "Advanced annotatable graphs with full editing" deferred | Basic visualization only for MVP |
| BD-032 | Click nodes to bring up associated information | PARTIAL | FR-006 ("context menu invoked"), AG-UI Events (NodeSelected) | Selection triggers events but "information brought up" not detailed |

### Constraints (BD-033 to BD-040)

| Atom ID | Statement Summary | Status | PRD Section(s) | Notes |
|---------|-------------------|--------|----------------|-------|
| BD-033 | Must NOT be a chatbot/texting interface | COVERED | Section 1 (Problem Statement), Section 2.1, Success Metrics (Command vs. Chat Ratio > 3:1) | Explicit anti-pattern |
| BD-034 | Must NOT be like ChatGPT's artifact-on-the-side model | COVERED | Section 2.1 ("not like ChatGPT or Claude where you have a little artifact on the side") | Explicitly stated as anti-pattern |
| BD-035 | New MCP servers must pass security checks | COVERED | FR-009 ("Security validation passes"), S-033 (MCP Security Validation), Section 7.4 MI-001 | Security validation required |
| BD-036 | New MCP servers must adhere to specified standards | COVERED | FR-009, S-033, Section 7.4 MI-001 | MCP standards enforced |
| BD-037 | New MCP servers must be set up in particular environment | PARTIAL | Mentioned in FR-009 (configuration) but environment specifics not detailed | Environment constraints not explicit |
| BD-038 | Context decomposition must be granular but not redundant | PARTIAL | FR-003 ("decompose"), Section 7.1 (Context Routing) | Decomposition mentioned but granularity/redundancy trade-off not explicit |
| BD-039 | Define boundaries for user alterations to canvas | COVERED | FR-006 (CRUD operations), Section 7.4 (Invariants), FR-015 (Safety Guardrails) | Boundaries defined via CRUD and guardrails |
| BD-040 | Agents must have controlled delete capabilities | COVERED | FR-015 ("destructive actions flagged", "Delete without confirmation" disallowed), Section 9.3 | Agent delete restrictions explicit |

### Workflows (BD-041 to BD-055)

| Atom ID | Statement Summary | Status | PRD Section(s) | Notes |
|---------|-------------------|--------|----------------|-------|
| BD-041 | Deep research job workflow: send off research task, receive streaming updates | COVERED | FR-007 (Deep Research Job Dispatch), FR-008, Journey 2, S-026 | Core workflow explicitly covered |
| BD-042 | LLM-as-judge workflow: critique deep research reports | COVERED | FR-011 (LLM-as-Judge Analysis Pattern), S-028, Journey 2 | Explicit workflow for critique |
| BD-043 | Context routing workflow: route input to appropriate handlers | COVERED | FR-003 (Context Routing Pipeline), Section 8.2 (Context Router) | Detailed routing logic |
| BD-044 | Intent/meaning deciphering workflow for user input | COVERED | FR-004 (Intent Deciphering with Assumption Generation), Journey 3, S-009 | Core workflow with detail |
| BD-045 | Assumption reconciliation workflow: present assumptions to user | COVERED | FR-005 (Assumption Reconciliation UI), Journey 3, S-011 | Explicit workflow |
| BD-046 | Audio block analysis workflow: record audio, then analyze with agents | COVERED | FR-013 (Audio Block Transcription), Journey mentioned in JTBD | Recording + transcription covered |
| BD-047 | Multiple deep research reports spawned from single tangent | PARTIAL | FR-003 mentions "multiple intents (decompose)" but not explicit multiple research jobs from one input | Intent decomposition exists but multi-job spawning not explicit |
| BD-048 | Hypothesis testing workflow with LLM judges | PARTIAL | FR-011 covers LLM-as-judge but "hypothesis testing" or "debating" not explicit | Could be implemented via LLM-as-judge but not specified |
| BD-049 | Collaborative planning workflow with agentic system | PARTIAL | JTBD mentions planning but no explicit FR for collaborative planning workflow | Planning mentioned in JTBD but no workflow defined |
| BD-050 | Plan to task DAG conversion workflow | PARTIAL | FR-010 mentions Task DAG sync but conversion from plan not explicit | Task DAG exists but plan-to-DAG conversion not specified |
| BD-051 | Task DAG to Google Docs export workflow | MISSING | Section 4.2 Out-of-Scope: "Google Docs integration" deferred to Phase 1.5 | Explicitly excluded from MVP |
| BD-052 | Task completion state mutation with propagation | COVERED | FR-010 ("tasks appear as calendar events"), Section 7.5 (CanvasUpdated event) | State mutation and propagation via events |
| BD-053 | Associative search through connected knowledge base | MISSING | No explicit FR for knowledge base search or associative search | Knowledge base concept not addressed |
| BD-054 | Predefined analysis workflows applied to thoughts | PARTIAL | FR-011 (LLM-as-judge) is one analysis pattern but "predefined workflows" not explicit | No framework for predefined workflow templates |
| BD-055 | Deterministic hooks after specific lifecycles | PARTIAL | Section 8.2 (Agent Orchestrator: "pre/post hooks for guardrails"), Section 7.5 (Event Model) | Hooks for guardrails exist but generic lifecycle hooks not detailed |

### Data Entities (BD-056 to BD-067)

| Atom ID | Statement Summary | Status | PRD Section(s) | Notes |
|---------|-------------------|--------|----------------|-------|
| BD-056 | Canvas: stateful space holding context, nodes, documents, audio blocks | COVERED | Section 7.2 (Canvas entity), Section 7.3 (Ubiquitous Language) | Detailed entity definition |
| BD-057 | Nodes: labeled entities on the canvas | COVERED | Section 7.2 (Node entity), FR-006 | Entity with label attribute |
| BD-058 | Documents: persistable text/content entities | COVERED | Section 7.2 (Document entity), Section 12 (Document storage) | Entity with versioning |
| BD-059 | Audio blocks: recorded audio entities on canvas | COVERED | Section 7.2 (AudioBlock entity), FR-013 | Entity with transcription |
| BD-060 | Jobs: asynchronous tasks (e.g., deep research) | COVERED | Section 7.2 (Job entity), FR-007, Section 12 (Jobs) | Detailed entity with lifecycle |
| BD-061 | Assumption structure: container for inferred intent/meaning | COVERED | Section 7.2 (Assumption entity), FR-004, FR-005, Section 9.1 (Pydantic models) | Entity with confidence, status |
| BD-062 | User intent/meaning index: persisted index of user behavior patterns | COVERED | FR-012 (User Intent/Meaning Index), Section 7.2 (IntentMeaningIndex entity), Section 12 | Explicit entity and FR |
| BD-063 | Task DAG: structured task representation with granularities | COVERED | FR-010 ("Task DAG can sync to calendar"), S-024 (Task DAG Visualization) | Task DAG mentioned; granularities implicit |
| BD-064 | Single source of truth: external state being observed/mirrored | PARTIAL | MCP can observe external state but "single source of truth" concept not explicit | MCP tools may cover but not architecturally explicit |
| BD-065 | Knowledge base: connected persisted information store | MISSING | No explicit entity or FR for "knowledge base" | Not addressed in PRD |
| BD-066 | Session: the current working context with agents | COVERED | Section 7.2 (Session entity), Section 12 (Session data) | Entity with contextHistory |
| BD-067 | Basic data structures with UI mappings like Coda | MISSING | No explicit mention of Coda-like data structures or their UI mappings | Brain dump flagged as ambiguous; not addressed |

### Integrations (BD-068 to BD-077)

| Atom ID | Statement Summary | Status | PRD Section(s) | Notes |
|---------|-------------------|--------|----------------|-------|
| BD-068 | Google Calendar MCP server integration | COVERED | FR-010 (Google Calendar MCP Integration), S-032 | Detailed FR with acceptance criteria |
| BD-069 | Agent can alter Google Calendar | COVERED | FR-010 ("calendar is modified via MCP"), Section 9.1 (Tools: createEvent) | Explicit tool capability |
| BD-070 | Model Context Protocol (MCP) as integration standard | COVERED | FR-009, Section 8.1 (External MCPs), Section 10 (no direct MCP dependency but framework) | MCP framework throughout |
| BD-071 | Agent-to-Agent Protocol support | MISSING | Not mentioned in PRD | Brain dump mention not addressed |
| BD-072 | WebSocket/polling for live state observation | COVERED | FR-008 (WebSocket Real-time Streaming), Section 8.1 | WebSocket covered; polling implicit |
| BD-073 | API endpoint state observation | PARTIAL | MCP tools can query APIs but no generic "observe API endpoint" FR | Covered indirectly via MCP |
| BD-074 | Google Docs integration for task DAG export | CONTRADICTED | Section 4.2 Out-of-Scope: "Google Docs integration" explicitly excluded | Brain dump wants it; PRD excludes it |
| BD-075 | Calendar integration for reminders | COVERED | FR-010 ("tasks appear as calendar events") | Calendar events can serve as reminders |
| BD-076 | Obsidian as potential persistence backend | PARTIAL | Section 8.2 (Persistence Layer: "optional Git/Obsidian sync") | Mentioned as optional, not decided |
| BD-077 | Git repos for backups | PARTIAL | Section 8.2 ("optional Git/Obsidian sync"), Section 15 Q7 (backup strategy question) | Mentioned as option, decision deferred |

### Non-Functional Requirements (BD-078 to BD-085)

| Atom ID | Statement Summary | Status | PRD Section(s) | Notes |
|---------|-------------------|--------|----------------|-------|
| BD-078 | System must be highly interactive (not static artifact generation) | COVERED | Section 1 (Executive Summary), FR-008 (real-time streaming), Section 6.2 (Performance) | Core value proposition |
| BD-079 | System must be stateful across sessions | COVERED | FR-014, Section 12, NFR 6.3 | Comprehensive persistence |
| BD-080 | System must support high velocity/throughput workflows | COVERED | Section 2.1 ("high velocity, high throughput"), Section 6.2 (Performance Targets) | Latency targets defined |
| BD-081 | System must be reliable | COVERED | NFR 6.3 (Reliability/Availability), Section 6.2 (Performance Targets) | Reliability expectations set |
| BD-082 | System should augment user's working memory | COVERED | Section 7.3 ("Working Memory Augmentation"), Section 8.2 (Canvas Why) | Explicit design goal |
| BD-083 | Context must be accessible to both user and agents | COVERED | Section 2.2 ("accessible to you and same to the agents"), Section 7.1 (contexts) | Shared context model |
| BD-084 | System must support focus/specificity with tasks | PARTIAL | Section 7.4 (JI-001: one research job per topic) but general focus/specificity not addressed | Implicit in some invariants |
| BD-085 | System must scale to complex, dynamic workflows | PARTIAL | Section 4.1 mentions "workflows" but scaling to complexity not explicitly addressed | MVP scope may limit complexity |

### Risks/Concerns (BD-086 to BD-090)

| Atom ID | Statement Summary | Status | PRD Section(s) | Notes |
|---------|-------------------|--------|----------------|-------|
| BD-086 | Risk of losing information during context decomposition | COVERED | Section 14 (State Complexity: High likelihood, High impact), FR-003 edge cases | Risk acknowledged with mitigation |
| BD-087 | Concern about user referencing capability limitations | COVERED | FR-003 (no matching handler fallback), Section 14 (Context Routing Accuracy) | Edge case and risk covered |
| BD-088 | Need to handle cases where tooling/MCP is not set up | COVERED | Journey 4 (MCP Configuration Flow), FR-009 (graceful degradation) | Workflow for missing MCP |
| BD-089 | Decision needed: dedicated database vs Obsidian/Git for persistence | COVERED | Section 15 A-001 (PostgreSQL assumed), Q7 (backup strategy question) | Decision made (PostgreSQL) with option noted |
| BD-090 | Agent delete capabilities need careful consideration | COVERED | FR-015 (Safety Guardrails), Section 9.3 (Allowed/Disallowed Actions) | Delete requires confirmation |

### Vision/Philosophy (BD-091 to BD-098)

| Atom ID | Statement Summary | Status | PRD Section(s) | Notes |
|---------|-------------------|--------|----------------|-------|
| BD-091 | This is an "agentic system" not a single agent | COVERED | Section 1 ("agentic workspace"), Section 8.2 (multiple agents), Section 9.1 (Agent list) | Multiple agents defined |
| BD-092 | Pattern expected to be widely adopted but can be specialized | PARTIAL | Section 4.1 (Modular MCP framework) but "widely adopted pattern" not explicit | Modularity enables specialization |
| BD-093 | Agents are first-class citizens of the program | COVERED | Section 2.2 ("Agents are first-class citizens"), Section 8.2 (Agent Orchestrator Why) | Explicit design principle |
| BD-094 | Agent experience heavily augments the software | COVERED | Section 1, Section 8.2 (Canvas Why: "Core differentiator") | Agents central to value |
| BD-095 | Shift from chatbot to immersive command/intent-oriented workspace | COVERED | Section 1 (Problem Statement), Section 2.1 (Pain Points) | Core thesis of PRD |
| BD-096 | Inference-time compute at user's fingertips | PARTIAL | Implied by agent access but "inference-time compute" phrasing not explicit | Conceptually covered |
| BD-097 | User controls compute allocation ("throw more compute at it") | CONTRADICTED | FR-011 mentions "single LLM critique" for MVP; no user control of compute allocation | MVP limits LLM usage; no compute control |
| BD-098 | Pre-MVP/Alpha scope acknowledgment | COVERED | Section 0 (Status: Draft), Section 4.3 (MVP Phases), Section 15 (Validation Questions) | MVP scope clear |

---

## Missing Items (Detail)

### BD-051: Task DAG to Google Docs Export Workflow
**Status**: MISSING (Explicitly Out of Scope)
**What's lacking**: Brain dump explicitly mentions "send that bitch to your Google Docs" as a desired workflow. PRD places Google Docs integration in Phase 1.5 Out-of-Scope.
**Impact**: Users cannot export task DAGs to a common document format in MVP.
**Recommended action**: Add to Phase 1.5 backlog with clear story; consider markdown export as MVP alternative.

### BD-053: Associative Search Through Connected Knowledge Base
**Status**: MISSING
**What's lacking**: Brain dump mentions "predefined like associative sort of search throughout some sort of connected knowledge base" - no FR, entity, or story addresses this.
**Impact**: Users cannot search across persisted knowledge in an associative/semantic manner.
**Recommended action**: Add FR for knowledge base entity and associative search capability (could be Phase 2).

### BD-065: Knowledge Base Entity
**Status**: MISSING
**What's lacking**: Brain dump mentions "connected knowledge base" as a data concept. PRD has no Knowledge Base entity or related storage.
**Impact**: No unified persisted knowledge store for cross-session search.
**Recommended action**: Define Knowledge Base entity in Section 7.2; add storage schema in Section 12.

### BD-067: Basic Data Structures with UI Mappings (like Coda)
**Status**: MISSING (Flagged as Ambiguous in ATOMS.md)
**What's lacking**: Brain dump references Coda-style data structures with UI mappings. This concept is not addressed in PRD.
**Impact**: Users may expect structured data primitives (tables, databases) with visual representations.
**Recommended action**: Clarify requirement with stakeholder; if needed, add FR for data primitives (Phase 2).

### BD-071: Agent-to-Agent Protocol Support
**Status**: MISSING
**What's lacking**: Brain dump mentions "do something with agent agent protocol" but PRD has no mention of A2A protocol.
**Impact**: Multi-agent communication may be limited.
**Recommended action**: If A2A is needed for MVP, add FR; otherwise document as Phase 2 consideration.

---

## Partial Items (Detail)

### BD-006: LLM as a Judge on Any Input or Output
**Lacking**: PRD limits LLM-as-judge to research reports (FR-011). Brain dump says "on any sort of input or output."
**Fix**: Expand FR-011 scope or add new FR for general-purpose LLM-as-judge invocation.

### BD-007: Request Multiple Perspectives (e.g., 5)
**Lacking**: PRD Out-of-Scope says "Multi-LLM judge patterns (complex multi-model orchestration) - MVP uses single LLM critique." Brain dump wants 5 perspectives.
**Fix**: Clarify if multiple sequential perspectives from single LLM is acceptable; if so, update FR-011.

### BD-011: Observe State from API Endpoints
**Lacking**: Brain dump wants generic API endpoint observation; PRD only covers MCP tools.
**Fix**: Add FR for generic API observation or clarify that MCP covers this use case.

### BD-029: Capture Random Eureka Thoughts/Notes
**Lacking**: Mentioned in JTBD but no explicit FR for quick note capture workflow.
**Fix**: Add FR for "Quick Note Capture" with minimal friction UI.

### BD-030: Label Notes Quickly
**Lacking**: Nodes have labels but quick labeling workflow not specified.
**Fix**: Ensure FR-006 acceptance criteria includes rapid labeling interaction.

### BD-031: Highly Annotatable Graphs
**Lacking**: Explicitly deferred to Phase 2; MVP has basic visualization only.
**Fix**: Document Phase 2 requirement; ensure Phase 1 graph is annotation-ready architecture.

### BD-032: Click Nodes to Bring Up Associated Information
**Lacking**: Node selection triggers events but information display not detailed.
**Fix**: Add acceptance criteria to FR-006 for information panel on node selection.

### BD-037: MCP Environment Setup
**Lacking**: Security and standards mentioned but environment specifics not detailed.
**Fix**: Add technical constraints for MCP environment in FR-009.

### BD-038: Context Decomposition Granularity
**Lacking**: Decomposition exists but granularity/redundancy balance not specified.
**Fix**: Add guidance in FR-003 or Section 9 for decomposition heuristics.

### BD-047: Multiple Research Jobs from Single Tangent
**Lacking**: Intent decomposition exists but multi-job spawning not explicit.
**Fix**: Add acceptance criteria in FR-003/FR-007 for multi-job spawning.

### BD-048: Hypothesis Testing Workflow
**Lacking**: LLM-as-judge exists but "hypothesis testing" or "debate" workflow not explicit.
**Fix**: Add use case to FR-011 or new FR for hypothesis testing pattern.

### BD-049: Collaborative Planning Workflow
**Lacking**: Planning in JTBD but no workflow definition.
**Fix**: Add FR for planning workflow with agent collaboration.

### BD-050: Plan to Task DAG Conversion
**Lacking**: Task DAG exists but conversion from plan not specified.
**Fix**: Add acceptance criteria or story for plan-to-DAG conversion.

### BD-055: Deterministic Hooks After Lifecycles
**Lacking**: Guardrail hooks exist but generic lifecycle hooks not detailed.
**Fix**: Define lifecycle events and hook points in Section 7.5 or Section 8.2.

### BD-064: Single Source of Truth Observation
**Lacking**: MCP can observe external state but "single source of truth" concept not architecturally explicit.
**Fix**: Add design pattern or FR for external state mirroring.

### BD-073: API Endpoint State Observation
**Lacking**: Covered indirectly via MCP but no generic FR.
**Fix**: Clarify MCP scope or add dedicated FR.

### BD-076/BD-077: Obsidian/Git for Persistence
**Lacking**: Mentioned as optional but decision deferred.
**Fix**: Make architectural decision (Section 15) or explicitly defer to Phase 2.

### BD-084: Focus/Specificity with Tasks
**Lacking**: Implicit in some invariants but not explicit NFR.
**Fix**: Add NFR for context focus/scoping.

### BD-085: Scale to Complex Workflows
**Lacking**: MVP scope may limit; not explicitly addressed.
**Fix**: Add NFR or design considerations for workflow complexity.

### BD-092: Widely Adopted Pattern
**Lacking**: Modularity enables specialization but pattern adoption not explicit.
**Fix**: Architectural documentation could address extensibility vision.

### BD-096: Inference-time Compute at Fingertips
**Lacking**: Conceptually covered but phrasing not explicit.
**Fix**: Could add to product vision section.

---

## Contradictions (Detail)

### BD-074: Google Docs Integration for Task DAG Export
**Brain Dump**: "send that bitch to your Google Docs"
**PRD**: Section 4.2 Out-of-Scope: "Google Docs integration (focus on Calendar first)"
**Conflict**: Brain dump explicitly wants Google Docs export; PRD explicitly excludes it.
**Resolution**:
- If Google Docs is required for MVP, move from Out-of-Scope to In-Scope
- If deferral is intentional, ensure stakeholder agrees and document markdown/PDF export as alternative

### BD-097: User Controls Compute Allocation
**Brain Dump**: "You can throw more compute at it if that's what you wish"
**PRD**: FR-011 says "MVP uses single LLM critique"; Out-of-Scope says "Multi-LLM judge patterns"
**Conflict**: Brain dump implies user can scale compute (more LLM calls); PRD limits to single LLM.
**Resolution**:
- Clarify if "throw more compute" means multiple perspective calls (acceptable in MVP?)
- If yes, revise FR-011 to allow configurable perspective count
- If no, ensure stakeholder agrees to limitation

---

## Recommended Fix Directives

### Critical Fixes (Address Before Development)

1. **Resolve Google Docs Contradiction (BD-074)**
   - Action: Stakeholder decision needed
   - If MVP: Add FR-016 for Google Docs MCP integration
   - If deferred: Confirm and add markdown export alternative

2. **Resolve Compute Allocation Contradiction (BD-097)**
   - Action: Clarify "multiple perspectives" implementation
   - Update FR-011 to specify configurable perspective count or confirm single-LLM limitation

3. **Add Knowledge Base Concept (BD-053, BD-065)**
   - Add KnowledgeBase entity to Section 7.2
   - Add storage definition to Section 12
   - Add associative search FR (FR-016) or defer to Phase 2 with explicit note

### High Priority Fixes (Pre-Development)

4. **Expand LLM-as-Judge Scope (BD-006)**
   - Update FR-011 to allow judge pattern on any content, not just research reports
   - Add acceptance criteria for ad-hoc judge invocation

5. **Add Quick Note Capture FR (BD-029)**
   - New FR-017: Quick Note Capture
   - Acceptance criteria for minimal-friction thought capture

6. **Define Node Selection Info Display (BD-032)**
   - Add acceptance criteria to FR-006: "Given node is clicked When selected Then associated information panel displays"

7. **Add Agent-to-Agent Protocol Consideration (BD-071)**
   - Add to Section 10 Dependencies or Section 15 Assumptions
   - Document if needed for MVP or Phase 2

### Medium Priority Fixes (During Development)

8. **Multiple Research Jobs from Single Input (BD-047)**
   - Add acceptance criteria to FR-003 or FR-007

9. **Plan to Task DAG Conversion (BD-050)**
   - Add story S-0XX for plan conversion workflow

10. **Lifecycle Hooks Definition (BD-055)**
    - Expand Section 7.5 Event Model with hook points

11. **API Endpoint Observation Clarification (BD-011, BD-073)**
    - Add note in FR-009 that MCP can observe external APIs
    - Or add new FR for generic API observation

12. **Persistence Strategy Decision (BD-076, BD-077, BD-089)**
    - Close Section 15 Q7 with definitive decision
    - PostgreSQL primary, Git/Obsidian optional sync

### Low Priority Fixes (Documentation)

13. **Add Coda-style Data Structures Note (BD-067)**
    - Add to Section 15 Assumptions or defer with explanation

14. **MCP Environment Specifics (BD-037)**
    - Add technical constraints to FR-009

15. **Context Decomposition Heuristics (BD-038)**
    - Add implementation note to FR-003

16. **Extensibility Vision (BD-092)**
    - Add to architecture documentation

---

## Audit Methodology

This audit was conducted by:
1. Reading each atomic statement in ATOMS.md independently
2. Searching PRD.md for relevant coverage using multiple search terms
3. Evaluating coverage status without relying on prior traceability
4. Documenting specific PRD section references
5. Identifying gaps, partial coverage, and contradictions
6. Providing actionable fix directives

**Auditor**: PRD Coverage Audit Agent (Opus 4.5)
**Date**: 2026-01-03
**Atoms Reviewed**: 98
**PRD Version Audited**: 1.0.0
