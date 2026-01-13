# Context Router Module

**Bounded Context:** Agent
**Location:** `intentuimvp/backend/app/context/router.py`
**PRD References:** FR-006 (Context Routing), §11.1 Intent Deciphering

---

## Where

**Location:** `intentuimvp/backend/app/context/router.py`

**Part of:** Agent Context

**Imports:**
- `app.agents.intent_decipherer` - LLM-based intent classification
- `app.context.models` - Routing data models
- `app.jobs.metrics_collection` - Performance tracking
- `app.logging_config` - Correlation ID

**Exports:**
- `ContextRouter` class - Main routing logic
- `RoutingDecision` - Routing result with handler and reasoning
- `get_context_router()` - Singleton accessor

---

## What

**Purpose:** Routes user commands to appropriate agent handlers using a three-tier priority system.

**Description:** The ContextRouter is the central command dispatcher for IntentUI. It accepts user text input and decides which agent should handle it: research, planning, analysis, creation, etc. Uses a 3-priority algorithm (slash commands > LLM classification > keyword patterns) with fallback and disambiguation.

**Key Types/Classes:**
- `ContextRouter` - Main router with 3-priority algorithm
- `RoutingDecision` - Result containing handler, confidence, assumptions, and reasoning
- `_RoutingCandidate` - Internal type for comparing routing options

---

## How

**Implementation approach:** Priority-based routing with LLM fallback and circuit breaker.

**Key algorithms/flows:**

**1. Priority Order (per FR-006):**
```
1. Slash commands (exact match)
   - "/research" → research_handler
   - "/plan" → plan_handler
   - "/judge" → judge_handler
   - etc.

2. LLM Classification (via IntentDeciphererAgent)
   - Analyzes natural language intent
   - Returns confidence + assumptions needing confirmation
   - Maps intent → handler

3. Keyword Fallback (regex patterns)
   - Research keywords → research_handler (0.6 confidence)
   - Planning keywords → plan_handler (0.55 confidence)
   - Etc.
```

**2. Circuit Breaker:**
- Opens after `circuit_breaker_threshold` consecutive failures
- Stays open for `circuit_breaker_window` seconds
- When open, skips LLM and uses keyword fallback

**3. Assumption Filtering:**
- LLM returns assumptions with confidence scores
- Only assumptions below `assumption_confidence_threshold` need user confirmation
- Passed to handler via `RoutingDecision.assumptions`

**4. Disambiguation:**
- If confidence < `clarification_confidence_threshold` (0.70) → clarification_handler
- If multiple handlers tie at same confidence → clarification_handler
- Handler prompts user for clarification

**Dependencies:**
- Internal: `IntentDeciphererAgent` (LLM classification), `context.models` (data types)
- External: `re` (regex), `asyncio` (timeout handling), `pydantic-ai`

**State management:**
- Singleton pattern via `get_context_router()`
- Tracks consecutive failures for circuit breaker
- Records circuit open time for auto-reset

---

## Why

**Rationale:** FR-006 requires "Context routing with 3-priority algorithm" - users shouldn't need to know which agent handles which command. The router abstracts agent selection while allowing explicit control via slash commands.

**Design decisions:**
- **Slash commands = highest priority** - User intent is explicit; don't second-guess
- **LLM before keywords** - LLM understands nuance; keywords are crude fallback
- **Circuit breaker** - Prevents cascading failures when LLM is down
- **Timeout on LLM** - Keywords are better than hanging forever
- **Disambiguation handler** - Better to ask than guess wrong (HITL principle)

**Alternatives considered:**
- Direct agent selection from frontend - Rejected (exposes implementation, poor UX)
- Only LLM classification - Rejected (slow, no fallback when LLM down)
- Only keywords - Rejected (can't understand nuance, high error rate)

**Trade-offs:**
- **Gain:** Natural, discoverable command interface
- **Gain:** Graceful degradation when LLM fails
- **Loss:** ~500ms timeout for LLM before fallback (acceptable for UX)
- **Gain:** HITL disambiguation builds user trust

---

## Acceptance Criteria

- [x] Slash commands route with 1.0 confidence
- [x] LLM classification with confidence scoring
- [x] Keyword fallback when LLM fails/times out
- [x] Circuit breaker opens after consecutive failures
- [x] Assumptions passed to handler below confidence threshold
- [x] Disambiguation triggered on low confidence or ties

---

## Testing

**Test location:** `intentuimvp/backend/app/context/test_router.py` (to be created)

**Coverage notes:**
- Slash command routing (exact match, unknown command)
- LLM routing success and failure modes
- Keyword pattern matching
- Circuit breaker state transitions
- Disambiguation on low confidence
- Disambiguation on tied candidates

---

## Future Work

- [ ] Learn from user corrections (improve routing over time)
- [ ] Add contextual awareness (selected nodes, recent history)
- [ ] Multi-language keyword patterns
- [ ] A/B test confidence thresholds

---

**Last Updated:** 2026-01-13
**Author:** System (BigDaddyIntentCanvasRepo)
