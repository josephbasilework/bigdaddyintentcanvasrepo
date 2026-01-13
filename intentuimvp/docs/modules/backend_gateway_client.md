# Gateway Client Module

**Bounded Context:** Integration
**Location:** `intentuimvp/backend/app/gateway/client.py`
**PRD References:** EI-001 (Gateway-Only), NFR-REL-001, NFR-PERF-003, NFR-PRIV-004

---

## Where

**Location:** `intentuimvp/backend/app/gateway/client.py`

**Part of:** Integration Context

**Imports:**
- `httpx` - Async HTTP client
- `app.agents.safety` - PII detection
- `app.config` - Configuration settings
- `app.telemetry` - Gateway call tracking

**Exports:**
- `GatewayClient` class - Main client for LLM inference
- `GatewayClientError`, `GatewayDegradedError` - Exception types
- `GatewayDegradationInfo` - Degradation event data
- `get_gateway_client()` - Singleton accessor

---

## What

**Purpose:** Provides the single, Gateway-only interface for all LLM inference in IntentUI.

**Description:** The GatewayClient enforces EI-001 (Gateway-Only) by being the sole module allowed to make LLM calls. It handles retry logic with exponential backoff, tracks latency for observability, and warns when PII is detected in outbound messages.

**Key Types/Classes:**
- `GatewayClient` - Main client class with retry logic and degradation handling
- `GatewayDegradedError` - Raised when all retry attempts are exhausted (includes degradation context)
- `GatewayDegradationInfo` - Detailed information about degradation events

---

## How

**Implementation approach:** Async HTTP client with circuit-breaker-style retry logic.

**Key algorithms/flows:**
1. **PII Detection** (NFR-PRIV-004): Scan messages for PII patterns before sending
2. **Request with Telemetry**: Wrap Gateway call with latency tracking
3. **Retry Loop**: Attempt request up to `max_retries` times with exponential backoff + jitter
4. **Error Classification**:
   - 4xx errors: Don't retry (client error, won't succeed)
   - 5xx errors: Retry with backoff (server may recover)
   - Network errors: Retry with backoff
5. **Degradation Event**: After all retries fail, raise `GatewayDegradedError` with full context

**Exponential backoff formula:**
```
delay_ms = min(base_delay * 2^attempt + jitter, max_delay)
```

**Dependencies:**
- Internal: `app.config` (settings), `app.telemetry` (tracking), `app.agents.safety` (PII detection)
- External: `httpx` (async HTTP), `pydantic-ai` (Gateway SDK)

**State management:**
- Singleton pattern via `get_gateway_client()`
- Lazy HTTP client creation (`_get_client()`)
- Tracks consecutive failures for circuit breaker

---

## Why

**Rationale:** EI-001 requires all LLM calls to go through Pydantic AI Gateway. Without a single client, developers might import provider SDKs directly (OpenAI, Anthropic), breaking cost control and observability.

**Design decisions:**
- **Singleton pattern** - Ensures one HTTP client is reused across requests (connection pooling)
- **Exponential backoff + jitter** - Prevents thundering herd when Gateway recovers
- **4xx = don't retry** - Client errors won't succeed on retry (e.g., invalid API key)
- **Degradation info** - Provides context to handlers (attempts, duration, error type)
- **PII warning** - Logs before sending sensitive content (NFR-PRIV-004)

**Alternatives considered:**
- Direct provider SDK imports in each agent - Rejected (violates EI-001, loses cost control)
- Sync HTTP client - Rejected (would block async worker pool)
- No jitter in backoff - Rejected (could overwhelm Gateway on recovery)

**Trade-offs:**
- **Gain:** Consistent error handling, observability, cost control
- **Loss:** Slight latency overhead from abstraction (~1ms)
- **Gain:** Circuit breaker prevents cascading failures
- **Loss:** Complexity in retry logic (justified by reliability needs)

---

## Acceptance Criteria

- [x] All LLM calls go through GatewayClient (EI-001 enforcement)
- [x] Retry logic with exponential backoff implemented
- [x] PII detection and warning before sending (NFR-PRIV-004)
- [x] Gateway call latency tracked (NFR-PERF-003)
- [x] Degradation events logged with context (NFR-REL-001)

---

## Testing

**Test location:** `intentuimvp/backend/app/gateway/test_gateway_client.py` (to be created)

**Coverage notes:**
- Retry behavior on 5xx errors
- No retry on 4xx errors
- Exponential backoff calculation
- PII detection integration
- Degradation error contains expected fields

---

## Future Work

- [ ] Add request batching for multiple completions
- [ ] Implement streaming response support
- [ ] Add caching for repeated prompts (optional)
- [ ] Consider multiple Gateway endpoints for HA

---

**Last Updated:** 2026-01-13
**Author:** System (BigDaddyIntentCanvasRepo)
