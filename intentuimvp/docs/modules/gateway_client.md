# Gateway Client

**Bounded Context:** Integration
**Location:** `intentuimvp/backend/app/gateway/client.py`
**PRD References:** EI-001 Gateway-Only, NFR-PERF-003, NFR-REL-001

---

## Where

**Location in codebase:**
- File path: `intentuimvp/backend/app/gateway/client.py`
- Parent module: Integration Context
- Related modules: All agents (via BaseAgent), telemetry

**Physical placement:**
- Directory: `backend/app/gateway/`
- Entry points: `get_gateway_client()` (singleton), `GatewayClient` class
- Singleton instance: `_client` module-level variable

---

## What

**Purpose:** Enforce Gateway-only constraint for all LLM inference in the application.

**Responsibilities:**
- All LLM calls MUST go through this module (EI-001 enforcement)
- HTTP client management with connection pooling
- Retry with exponential backoff and jitter (NFR-REL-001)
- Gateway call latency tracking (NFR-PERF-003)
- Degradation detection and reporting
- Gateway error handling with proper exception types

**Key entities/exports:**
- `GatewayClient` - Main client class for Gateway communication
- `GatewayClientError` - Base exception for Gateway errors
- `GatewayDegradedError` - Exception with degradation context
- `GatewayDegradationInfo` - Dataclass for degradation event details
- `get_gateway_client()` - Singleton accessor

---

## How

**Implementation approach:**

The GatewayClient wraps the Pydantic AI Gateway HTTP API with:
1. Async httpx client with connection pooling
2. Retry loop with exponential backoff + jitter
3. Structured logging with correlation IDs
4. Telemetry integration for performance tracking

**Key algorithms/patterns:**

- **Exponential backoff with jitter**: `delay = base * 2^attempt ± 25% jitter`
- **Circuit breaker pattern**: Not implemented (considered for future)
- **Error classification**: 4xx = don't retry, 5xx = retry, network = retry

**Dependencies:**
- Internal: `app.config` (settings), `app.telemetry` (track_gateway_call)
- External: `httpx` (async HTTP), `asyncio` (async/await)

**Data flow:**
```
Agent → generate() → GatewayClient.generate()
  → _make_request() → httpx.AsyncClient
  → [retry loop on failure] → Response
  → track_gateway_call() → Return JSON
```

---

## Why

**Problem being solved:**

The project requires Gateway-only LLM access (EI-001) to ensure:
1. Single control point for all LLM calls
2. Consistent error handling and retry logic
3. Observability across all AI operations
4. No direct provider SDK dependencies

**Design decisions:**

1. **Singleton pattern**: Ensures single HTTP client for connection pooling
   - Rationale: Reduces connection overhead, enables proper cleanup

2. **Exponential backoff with jitter**: Prevents thundering herd on Gateway outages
   - Rationale: Standard pattern for distributed system resilience

3. **Separate degradation error**: Provides context for UI feedback
   - Rationale: Users need to know when the system is degraded vs. broken

**Trade-offs:**

- **Async-only**: Requires async context for all calls
  - Accepted: FastAPI is async-first, consistent with platform architecture

- **No circuit breaker**: Currently relies on Gateway for rate limiting
  - Accepted: Gateway provides throttling; may add local circuit breaker later

**Alternatives considered:**

- Direct provider SDKs (OpenAI, Anthropic) - **Rejected**: Violates EI-001
- Synchronous client - **Rejected**: Inconsistent with FastAPI async architecture
- Multiple Gateway instances - **Rejected**: Unnecessary complexity for single-tenant app

---

## Acceptance Criteria

- [x] All LLM calls go through GatewayClient (enforced by code review)
- [x] Retry with exponential backoff implemented
- [x] Gateway latency tracked via telemetry
- [x] Degradation errors include context (attempts, error type, duration)
- [x] Client errors (4xx) not retried, server errors (5xx) retried
- [x] Singleton accessor provides consistent instance

---

## Testing

**Test coverage:**
- Unit tests: `tests/unit/test_gateway_client.py`
- Integration tests: Handled via agent tests that use Gateway
- Coverage target: 80%+

**Key test scenarios:**
- Successful Gateway request returns parsed JSON
- 4xx errors raise GatewayClientError without retry
- 5xx errors trigger retry with backoff
- Network errors trigger retry with backoff
- Retries exhausted raises GatewayDegradedError with info
- Telemetry is called on success and failure
- Jitter prevents exact delay alignment

---

## Future Work

- [ ] Add circuit breaker for repeated failures (NFR-REL-001)
- [ ] Add request/response caching for idempotent calls
- [ ] Support streaming responses (for agentic streaming)
- [ ] Add batch request support for multiple prompts
- [ ] Consider connection pooling configuration options

---

**Last Updated:** 2026-01-13
**Author:** nastysandbox
