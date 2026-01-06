# IntentUI MVP - PRD Generation TODO

**Status**: COMPLETED
**Started**: 2026-01-03
**Completed**: 2026-01-03

---

## Phase 1: Parsing & Understanding
- [x] Read PRD template file (toGenPRDUsingBrainDump.md) - COMPLETED
- [x] Read brain dump file (braindump.txt) - COMPLETED
- [x] Extract PRD required structure into working outline - COMPLETED
- [x] Parse brain dump into atomic statements with tags - COMPLETED

## Phase 2: Subagent Extraction (Parallel)
- [x] Extractor-Product: Extract product intent, users, journeys, MVP scope - COMPLETED
- [x] Extractor-Tech: Extract technical constraints, architecture, dependencies - COMPLETED
- [x] Extractor-DDD: Infer Domain-Driven Design model - COMPLETED
- [x] Extractor-UX-AGUI-Copilot: Infer UI/UX flows and AG-UI/CopilotKit model - COMPLETED
- [x] Backlog-Builder: Convert requirements to Epics → Stories → Tasks - COMPLETED

## Phase 3: Judge Reconciliation
- [x] Merge all subagent outputs - COMPLETED
- [x] Detect omissions from brain dump - COMPLETED (0 omissions found)
- [x] Resolve conflicts between extractions - COMPLETED
- [x] Build final coverage matrix - COMPLETED
- [x] Verify PRD template compliance - COMPLETED

## Phase 4: PRD Drafting (By Section)
- [x] Section 0: Document Control - COMPLETED
- [x] Section 1: Executive Summary - COMPLETED
- [x] Section 2: Background + Context - COMPLETED
- [x] Section 3: Personas + User Journeys - COMPLETED
- [x] Section 4: Scope (In-scope, Out-of-scope, Phases) - COMPLETED
- [x] Section 5: Functional Requirements (FR-001 through FR-015) - COMPLETED
- [x] Section 6: Non-Functional Requirements - COMPLETED
- [x] Section 7: Domain Model (DDD) - COMPLETED
- [x] Section 8: System Architecture (Where/What/How/Why) - COMPLETED
- [x] Section 9: AI/Agent Design (PydanticAI Gateway-only) - COMPLETED
- [x] Section 10: Dependency Plan Table - COMPLETED
- [x] Section 11: Repo + Dev Setup Specification - COMPLETED
- [x] Section 12: Data Storage - COMPLETED
- [x] Section 13: Analytics + Success Metrics - COMPLETED
- [x] Section 14: Risks + Mitigations - COMPLETED
- [x] Section 15: Open Questions + Validation Questions - COMPLETED
- [x] Section 16: Backlog (7 Epics, 38 Stories, 176 Tasks) - COMPLETED
- [x] Section 17: Documentation Plan - COMPLETED

## Phase 5: Final Verification
- [x] Run template's final checklist - PASSED
- [x] Verify: No secret values (env var names only) - PASSED
- [x] Verify: Gateway-only requirement in all relevant sections - PASSED (6 mentions)
- [x] Verify: Full brain dump coverage (traceability matrix) - PASSED (100%)
- [x] Verify: All FRs have acceptance criteria - PASSED (15/15)
- [x] Verify: All stories have acceptance criteria - PASSED (38/38)
- [x] Create PRD_TRACEABILITY.md - COMPLETED
- [x] Create PRD_VERIFICATION.md - COMPLETED

---

## Atomic Statements Extracted from Brain Dump (Coverage Checklist)

### Features
- [ ] F001: Canvas-based stateful workspace (not chatbot)
- [ ] F002: Text box input for context injection
- [ ] F003: Context routing system for intelligent delegation
- [ ] F004: Intent/meaning deciphering with user reconciliation
- [ ] F005: MCP server integration (modular, configurable)
- [ ] F006: Deep research jobs with streaming updates
- [ ] F007: LLM-as-judge patterns for critique/perspectives
- [ ] F008: Visual representations (graphs, nodes, annotations)
- [ ] F009: Persistence of workspace state (CRUD)
- [ ] F010: Audio block transcription and processing
- [ ] F011: Task DAG visualization
- [ ] F012: Self-modifying workflows (add MCPs on-the-fly)
- [ ] F013: Assumptions UI for user confirmation
- [ ] F014: Calendar/external service integrations
- [ ] F015: Working memory augmentation via spatial UI

### Constraints
- [ ] C001: Use PydanticAI via Gateway API ONLY
- [ ] C002: Env vars: PYDANTIC_GATEWAY_API_KEY, XAI_API_KEY
- [ ] C003: Never embed API keys in code
- [ ] C004: AG-UI protocol for agent/UI interaction
- [ ] C005: CopilotKit for copilot-style assistance
- [ ] C006: Modular/DDD architecture
- [ ] C007: Security checks for MCP additions
- [ ] C008: No information loss during context handling

### Personas
- [ ] P001: Power user/knowledge worker juggling many tasks
- [ ] P002: Developer in alpha environment

### Workflows
- [ ] W001: Input text → Intent deciphering → Assumptions → Reconciliation
- [ ] W002: Deep research job → LLM-as-judge analysis → Persist result
- [ ] W003: Canvas CRUD → Agent interaction → State update
- [ ] W004: Configure MCP → Security check → Enable capability
- [ ] W005: Hackathon planning → Task DAG → Calendar integration

### Data
- [ ] D001: User intent/meaning index (persisted memory)
- [ ] D002: Canvas state (nodes, documents, audio blocks)
- [ ] D003: Deep research reports/artifacts
- [ ] D004: Task DAGs
- [ ] D005: Session context
- [ ] D006: MCP configurations

### Integrations
- [ ] I001: Google Calendar via MCP
- [ ] I002: Google Docs for task export
- [ ] I003: WebSocket streaming for job updates
- [ ] I004: Obsidian/Git for backup (optional)

### Non-Functional
- [ ] N001: High throughput, high velocity interactions
- [ ] N002: Reliability for rapid context switching
- [ ] N003: Real-time state streaming
- [ ] N004: Granular context decomposition without redundancy

### Risks
- [ ] R001: Gateway beta reliability
- [ ] R002: Context window management
- [ ] R003: Agent hallucination/destructive actions
- [ ] R004: MCP security vulnerabilities

---

*Last Updated: 2026-01-03*
