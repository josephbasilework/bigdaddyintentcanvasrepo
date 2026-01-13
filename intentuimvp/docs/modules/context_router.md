# Context Router

**Bounded Context:** Agent
**Location:** `intentuimvp/backend/app/context/router.py`
**PRD References:** FR-006 Context Routing, §8.1 Command-Driven Interaction

---

## Where

**Location in codebase:**
- File path: `intentuimvp/backend/app/context/router.py`
- Parent module: Agent Context
- Related modules: `agents/intent_decipherer.py`, `context/models.py`, `api/context.py`

**Physical placement:**
- Directory: `backend/app/context/`
- Entry points: `get_context_router()` (singleton), `ContextRouter.route()`
- Used by: API endpoint `/api/context`

---

## What

**Purpose:** Route user commands to appropriate agent handlers using a three-level priority algorithm.

**Responsibilities:**
- Slash command matching (highest priority: `/research`, `/plan`, etc.)
- LLM intent classification (via Intent Decipherer Agent)
- Keyword fallback patterns (lowest priority)
- Circuit breaker for LLM classification failures
- Assumption extraction and confidence scoring
- Clarification routing for ambiguous intents

**Key entities/exports:**
- `ContextRouter` - Main router class with three-level routing
- `get_context_router()` - Singleton accessor
- `RoutingDecision` - Result of routing with handler, confidence, assumptions
- `SLASH_COMMANDS` - Registry of known slash commands
- `KEYWORD_PATTERNS` - Fallback regex patterns for common intents

---

## How

**Implementation approach:**

Three-priority routing algorithm:
1. **Slash commands** - Exact match at start of input (confidence = 1.0)
2. **LLM classification** - Intent Decipherer Agent with timeout + circuit breaker
3. **Keyword fallback** - Regex patterns with fixed confidence scores

**Key algorithms/patterns:**

- **Circuit breaker**: Opens after `circuit_breaker_threshold` consecutive failures
- **Timeout protection**: `asyncio.wait_for` prevents LLM hangs
- **Confidence thresholds**: Below threshold → clarification handler
- **Assumption filtering**: Only show assumptions below `assumption_confidence_threshold`

**Dependencies:**
- Internal: `agents.intent_decipherer`, `context.models`, `logging_config`, `jobs.metrics_collection`
- External: `asyncio`, `re`, `dataclasses`, `typing`

**Data flow:**
```
User Input → ContextRouter.route()
  → [starts with /?] → _route_slash_command() → RoutingDecision
  → [circuit open?] → _route_keyword_fallback()
  → [LLM route] → _route_via_llm() → Intent Decipherer
    → [confidence low?] → DISAMBIGUATION_HANDLER
    → [success] → INTENT_HANDLERS[intent] → RoutingDecision
```

---

## Why

**Problem being solved:**

Users shouldn't need to know which agent to use for a given task. The router enables:
1. Explicit routing via slash commands for power users
2. Natural language intent understanding
3. Graceful fallback when LLM fails
4. HITL (Human-in-the-Loop) for ambiguous intents

**Design decisions:**

1. **Three-level priority**: Slash > LLM > Keywords
   - Rationale: Explicit user intent > AI classification > heuristics

2. **Circuit breaker for LLM**: Opens after 3 consecutive failures
   - Rationale: Prevents cascading failures when Gateway is down

3. **Clarification on low confidence**: Uses DISAMBIGUATION_HANDLER below 0.95
   - Rationale: HITL prevents incorrect agent selection

4. **Assumption filtering**: Only shows low-confidence assumptions
   - Rationale: Reduces UI clutter, focuses on uncertain items

**Trade-offs:**

- **Fixed keyword confidence**: Patterns have static 0.5-0.6 confidence
  - Accepted: Keywords are fallback; LLM provides dynamic scoring

- **No routing cache**: Every request routes independently
  - Accepted: Routing is fast (<500ms), cache complexity not warranted

**Alternatives considered:**

- Single-level (LLM only) - **Rejected**: Too slow, no backup on failure
- Pure keyword routing - **Rejected**: Too rigid, no intent understanding
- ML classifier - **Rejected**: Would require training data, LLM is sufficient

---

## Acceptance Criteria

- [x] Slash commands route to correct handlers
- [x] LLM classification extracts intents and assumptions
- [x] Circuit breaker opens after consecutive failures
- [x] Timeout prevents LLM hangs
- [x] Low confidence routes to clarification handler
- [x] Keyword fallback provides reasonable defaults
- [x] Ambiguous matches (same confidence, different handlers) request disambiguation

---

## Testing

**Test coverage:**
- Unit tests: `tests/unit/test_context_router.py`
- Coverage target: 80%+

**Key test scenarios:**
- Slash commands route with 1.0 confidence
- Unknown slash commands route to help
- LLM classification returns intent with assumptions
- LLM timeout falls back to keywords
- Circuit breaker opens after threshold failures
- Low confidence (<0.95) routes to clarification
- Keyword patterns match common phrases
- Ambiguous matches request disambiguation

---

## Future Work

- [ ] Add routing cache for repeated commands
- [ ] Learn from user corrections (reinforcement)
- [ ] Support context-aware routing (canvas selection, workspace state)
- [ ] Add middleware hooks for routing pipeline
- [ ] Consider streaming classification for early abort

---

**Last Updated:** 2026-01-13
**Author:** nastysandbox
