# Telemetry Success Metrics Specification (JM-8)

**PRD Reference:** §5.2 Success Metrics (MVP Targets)
**Author:** Claude Code (bigdaddyintentcanvasrepo-xht)
**Version:** 1.0
**Last Updated:** 2026-01-13

## Overview

This specification defines event schemas, calculation rules, and handling constraints for the 7 success metrics defined in PRD §5.2. All metrics are computed from telemetry events emitted by the IntentUI backend and processed by an observability pipeline compatible with FR-022 (OpenTelemetry) and NFR-OBS (Logging/Metrics/Tracing).

---

## Canonical Event Envelope

All telemetry events MUST conform to this canonical envelope structure:

```typescript
interface TelemetryEvent {
  // Event identification
  event_name: string;           // e.g., "intent.executed", "assumption.accepted"
  event_timestamp: ISO8601;     // When the event occurred (UTC)
  event_id: UUID;               // Unique identifier for this event

  // Correlation & context
  user_id: string | REDACTED;   // User identifier (redacted if PII)
  session_id: string;           // Session identifier (ephemeral)
  workspace_id: string;         // Canvas/workspace identifier
  run_id: string;               // Intent execution identifier
  correlation_id: string;       // Links related events (e.g., job -> report)

  // Event-specific data
  event_data: Record<string, unknown>;

  // Metadata
  source_service: string;       // e.g., "intent-api", "job-worker", "mcp-manager"
  environment: string;          // "production", "staging", "development"
}
```

### Required Fields (All Events)
- `event_name`, `event_timestamp`, `event_id`
- `user_id` (or REDACTED marker), `session_id`
- `source_service`, `environment`

### Conditional Fields
- `workspace_id` - Required for workspace-scoped events
- `run_id` - Required for intent execution events
- `correlation_id` - Required for multi-step operations (jobs, async flows)

### Event Data Schema
Each event type defines its own `event_data` schema. All event_data:
- MUST NOT contain PII unless explicitly marked for redaction
- MUST NOT contain secrets/API keys
- SHOULD use semantic naming (e.g., `task_count` not `n`)

---

## Success Metrics Definitions

### 1. Task Completion Rate

**Target:** > 80%

**Definition:** Percentage of user intents successfully executed without failure.

**Numerator:** Count of `intent.executed` events with `status = "success"`

**Denominator:** Count of `intent.executed` events (all statuses)

**Required Events:**
- `intent.executed` - Emitted when intent execution completes

**Event Schema:**
```typescript
interface IntentExecutedEvent extends TelemetryEvent {
  event_name: "intent.executed";
  event_data: {
    status: "success" | "failed" | "cancelled";
    failure_reason?: string;      // Present if status = "failed"
    intent_type: string;          // e.g., "research", "plan", "execute"
    execution_duration_ms: number;
  };
}
```

**Time Window:** Rolling 7-day window

**Calculation:**
```
Task Completion Rate = (
  COUNT(intent.executed WHERE status = "success" OVER 7 days)
  /
  COUNT(intent.executed OVER 7 days)
) * 100
```

---

### 2. Assumption Accuracy

**Target:** > 70%

**Definition:** Percentage of system assumptions that users accept without modification.

**Numerator:** Count of `assumption.resolved` events with `resolution = "accepted_as_is"`

**Denominator:** Count of `assumption.resolved` events (all resolutions)

**Required Events:**
- `assumption.created` - Emitted when system generates an assumption
- `assumption.resolved` - Emitted when user resolves the assumption

**Event Schemas:**
```typescript
interface AssumptionCreatedEvent extends TelemetryEvent {
  event_name: "assumption.created";
  event_data: {
    assumption_id: string;
    assumption_type: string;      // e.g., "context_gap", "ambiguous_term"
    run_id: string;
  };
}

interface AssumptionResolvedEvent extends TelemetryEvent {
  event_name: "assumption.resolved";
  event_data: {
    assumption_id: string;
    resolution: "accepted_as_is" | "modified" | "rejected";
    modifications_made?: number;  // Present if resolution = "modified"
  };
}
```

**Time Window:** Rolling 7-day window

**Calculation:**
```
Assumption Accuracy = (
  COUNT(assumption.resolved WHERE resolution = "accepted_as_is" OVER 7 days)
  /
  COUNT(assumption.resolved OVER 7 days)
) * 100
```

---

### 3. Time-to-Value (Simple Tasks)

**Target:** < 30 seconds

**Definition:** Time from command submission to useful output for simple tasks.

**Numerator:** Sum of `execution_duration_ms` for `intent.executed` events (simple tasks)

**Denominator:** Count of `intent.executed` events (simple tasks only)

**Required Events:**
- `intent.executed` - Same event as Task Completion Rate, filtered for simple tasks

**Simple Task Classification:**
- `intent_type = "execute"` (one-shot commands)
- `intent_type = "query"` (simple queries, not deep research)
- Excludes: `intent_type = "research"`, `intent_type = "plan"`

**Event Schema:**
```typescript
interface IntentExecutedEvent extends TelemetryEvent {
  event_name: "intent.executed";
  event_data: {
    status: "success" | "failed" | "cancelled";
    intent_type: string;
    execution_duration_ms: number;  // Time from submission to completion
    is_simple_task: boolean;        // True for one-shot operations
  };
}
```

**Time Window:** Rolling 7-day window

**Calculation:**
```
Time-to-Value = (
  SUM(execution_duration_ms WHERE is_simple_task = true OVER 7 days)
  /
  COUNT(* WHERE is_simple_task = true OVER 7 days)
) / 1000  // Convert to seconds
```

**Note:** Only successful executions (`status = "success"`) are included.

---

### 4. Session Continuity

**Target:** > 60%

**Definition:** Percentage of users who resume a previous workspace rather than starting fresh.

**Numerator:** Count of unique `user_id` values with `workspace.is_new = false`

**Denominator:** Count of unique `user_id` values with a `session.started` event

**Required Events:**
- `session.started` - Emitted when a user starts a new session

**Event Schema:**
```typescript
interface SessionStartedEvent extends TelemetryEvent {
  event_name: "session.started";
  event_data: {
    workspace_id: string;
    workspace_is_new: boolean;    // True if workspace created this session
    workspace_age_days?: number;  // Present if workspace_is_new = false
    previous_session_id?: string;  // Present if resuming
  };
}
```

**Time Window:** Rolling 30-day window (broader to capture user behavior patterns)

**Calculation:**
```
Session Continuity = (
  COUNT(DISTINCT user_id WHERE workspace_is_new = false OVER 30 days)
  /
  COUNT(DISTINCT user_id OVER 30 days)
) * 100
```

---

### 5. Research Job Completion Rate

**Target:** > 75%

**Definition:** Percentage of deep research jobs that complete successfully.

**Numerator:** Count of `job.completed` events where `job_type = "deep_research"` and `status = "success"`

**Denominator:** Count of `job.completed` events where `job_type = "deep_research"`

**Required Events:**
- `job.enqueued` - Emitted when job is queued
- `job.completed` - Emitted when job reaches terminal state

**Event Schemas:**
```typescript
interface JobEnqueuedEvent extends TelemetryEvent {
  event_name: "job.enqueued";
  event_data: {
    job_id: string;
    job_type: "deep_research" | "synthesis" | "export" | "transcription";
    job_params: Record<string, unknown>;
  };
}

interface JobCompletedEvent extends TelemetryEvent {
  event_name: "job.completed";
  event_data: {
    job_id: string;
    job_type: "deep_research" | "synthesis" | "export" | "transcription";
    status: "success" | "failed" | "cancelled";
    failure_reason?: string;
    execution_duration_ms: number;
  };
}
```

**Time Window:** Rolling 7-day window

**Calculation:**
```
Research Job Completion = (
  COUNT(job.completed WHERE job_type = "deep_research" AND status = "success" OVER 7 days)
  /
  COUNT(job.completed WHERE job_type = "deep_research" OVER 7 days)
) * 100
```

---

### 6. Command vs. Chat Ratio

**Target:** > 3:1 (75% of interactions are command-driven)

**Definition:** Ratio of command-driven interactions to chat-driven interactions.

**Numerator:** Count of `intent.submitted` events with `interaction_mode = "command"`

**Denominator:** Count of `intent.submitted` events with `interaction_mode = "chat"`

**Required Events:**
- `intent.submitted` - Emitted when user submits an intent/command

**Event Schema:**
```typescript
interface IntentSubmittedEvent extends TelemetryEvent {
  event_name: "intent.submitted";
  event_data: {
    intent_type: string;
    interaction_mode: "command" | "chat";
    input_length_chars: number;
    has_attachments: boolean;
  };
}
```

**Time Window:** Rolling 7-day window

**Calculation:**
```
Command vs. Chat Ratio = (
  COUNT(intent.submitted WHERE interaction_mode = "command" OVER 7 days)
  /
  COUNT(intent.submitted WHERE interaction_mode = "chat" OVER 7 days)
)
```

**Interpretation:**
- Ratio > 3.0 indicates >75% of interactions are command-driven (target met)
- Ratio = 1.0 indicates 50/50 split
- Ratio < 1.0 indicates more chat than command usage

---

### 7. MCP Adoption Rate

**Target:** > 30%

**Definition:** Percentage of users who have configured at least one MCP server.

**Numerator:** Count of unique `user_id` values with at least one `mcp.configured` event

**Denominator:** Count of unique `user_id` values with a `session.started` event

**Required Events:**
- `mcp.configured` - Emitted when user successfully configures an MCP server
- `session.started` - Emitted when user starts a session

**Event Schemas:**
```typescript
interface MCPConfiguredEvent extends TelemetryEvent {
  event_name: "mcp.configured";
  event_data: {
    mcp_id: string;
    mcp_type: string;            // e.g., "calendar", "filesystem", "database"
    mcp_name: string;            // User-provided name
    is_active: boolean;
  };
}

interface SessionStartedEvent extends TelemetryEvent {
  event_name: "session.started";
  // ... (same as Session Continuity metric)
}
```

**Time Window:** Rolling 30-day window (adoption is a longer-term metric)

**Calculation:**
```
MCP Adoption = (
  COUNT(DISTINCT user_id WHERE event_name = "mcp.configured" OVER 30 days)
  /
  COUNT(DISTINCT user_id WHERE event_name = "session.started" OVER 30 days)
) * 100
```

---

## PII/Secrets Handling Constraints

### Applicable NFRs
- **NFR-PRIV-004:** PII Detection & Warning
- **NFR-PRIV-005:** Audit Logging
- **NFR-SEC-003:** Secrets Detection (Gitleaks)
- **NFR-SEC-004:** Input Sanitization

### PII Handling Rules

**Fields Requiring Redaction:**
- `user_id` - Hash or UUID instead of email/username
- Free-text fields in `event_data` (e.g., `query_text`, `command_text`)
  - Apply PII detection (NFR-PRIV-004) before logging
  - Redact detected PII with `[REDACTED_PII]` placeholder

**Redaction Format:**
```typescript
// Before redaction
{ query_text: "Send email to john@example.com about the project" }

// After redaction
{ query_text: "Send email to [REDACTED_PII] about the project" }
```

### Secrets Handling Rules

**Prohibited Fields:**
- Never include in event_data:
  - API keys
  - Passwords
  - Tokens
  - Private keys
  - Database connection strings
  - OAuth credentials

**Secret Detection:**
- Apply Gitleaks rules (NFR-SEC-003) to all event_data before emission
- Drop events containing detected secrets (do not attempt redaction)
- Alert monitoring if secret detection rate > threshold

### Audit Trail (NFR-PRIV-005)

**Required Audit Fields for PII-Related Events:**
```typescript
interface AuditTrailEvent extends TelemetryEvent {
  event_name: "pii.accessed" | "pii.redacted" | "secret.detected";
  event_data: {
    pii_type: string;           // e.g., "email", "phone", "ssn"
    redaction_count: number;
    detector_version: string;   // PII detector version
  };
}
```

---

## Implementation Notes

### FR-022 Compatibility (OpenTelemetry)
- Events map to OpenTelemetry `LogRecord`
- `event_name` → `instrumentation_scope`
- `event_data` → `attributes`
- Use `OTEL_RESOURCE_ATTRIBUTES` for service identification

### NFR-OBS Compliance
- **Metrics:** Export to Prometheus/Grafana
- **Logs:** Structured JSON logs (existing logfire integration)
- **Tracing:** Correlate events via `correlation_id` to OpenTelemetry traces

### Event Emission Points
1. **Backend API** (`app/api/`) - `intent.submitted`, `session.started`
2. **Context Router** (`app/context.py`) - `intent.executed`, `assumption.created/resolved`
3. **Job Worker** (`app/jobs/`) - `job.enqueued`, `job.completed`
4. **MCP Manager** (`app/mcp/`) - `mcp.configured`

### Event Storage
- Short-term: Redis/PostgreSQL (raw events, 7-30 day retention)
- Long-term: S3/MinIO (aggregated metrics, 90+ day retention)
- Aggregation: Scheduled job rolls up events hourly/daily

---

## Related Tasks

- **T2-JM8:** `bigdaddyintentcanvasrepo-1rn` - Emit telemetry events for runs/jobs/assumptions
- **JM-8 Dashboard:** `bigdaddyintentcanvasrepo-jm8` - Success Metrics Dashboard (§5.2)

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-13 | Initial specification covering all 7 PRD §5.2 metrics |
