# AG-UI Protocol Module

**Bounded Context:** Agent
**Location:** `intentuimvp/frontend/src/agui/protocol.ts`
**PRD References:** FR-009 (AG-UI Run Lifecycle)

---

## Where

**Location:** `intentuimvp/frontend/src/agui/protocol.ts`

**Part of:** Agent Context (Frontend AG-UI Layer)

**Imports:**
- None (pure type definitions and utilities)

**Exports:**
- `AgentToUIMessageType`, `UIToAgentMessageType` - All message types
- `AgentToUIMessageHandler`, `UIToAgentMessageHandler` - Handler types
- `applyJSONPatch()`, `computeChecksum()` - Protocol utilities
- `AGUI_PROTOCOL_VERSION` - Current version constant
- `createEnvelope()`, `generateMessageId()` - Message builders

---

## What

**Purpose:** Defines the type-safe communication protocol between agents (backend) and UI (frontend) via WebSocket.

**Description:** The AG-UI protocol is the contract for real-time agent-UI communication. It specifies message formats, state synchronization with JSON Patch, and checksums for integrity. All agent streaming (progress, tool calls, state updates) uses these types.

**Key Types/Classes:**
- `AgentToUIMessage` - Base type for all backend → frontend messages
- `UIToAgentMessage` - Base type for all frontend → backend messages
- `StateUpdateMessage` - Incremental state updates with JSON Patch
- `StateSnapshotMessage` - Full state sync on connection/reconnect
- `RunStartMessage`, `RunEndMessage` - Agent run lifecycle events

---

## How

**Implementation approach:** TypeScript types for WebSocket messages with JSON Patch (RFC 6902) for state sync.

**Key algorithms/flows:**

**1. Message Envelope:**
```typescript
{
  version: string,      // Protocol version
  messageId: string,    // Unique ID
  timestamp: string,    // ISO 8601
  source: 'agent'|'ui',
  target: 'agent'|'ui',
  correlationId?: string  // Request/response linking
}
```

**2. State Sync (Optimistic + Server-Authoritative):**
- **Client → Server:** `UIStateUpdateProposalMessage` with patch + checksum
- **Server → Client:** `StateUpdateAcceptedMessage` or `StateUpdateRejectedMessage`
- **Server → Client:** `StateUpdateMessage` with sequence number + checksum
- **Gap detection:** Client requests full `StateSnapshotMessage` if sequence mismatch

**3. JSON Patch (RFC 6902):**
- Operations: `add`, `remove`, `replace`, `move`, `copy`, `test`
- Path syntax: `/nodes/0/title` (JSON Pointer)
- Implemented in `applyJSONPatch()` with path utilities

**4. Checksums (SHA-256):**
- Computed over sorted JSON string (deterministic ordering)
- Format: `sha256:{hexdigest}`
- Validates patch/state integrity

**5. Message Categories:**

**Agent → UI:**
- `status` - Agent working/idle/error
- `progress` - Long-running operation progress (0-1)
- `result` - Operation result
- `error` - Error with recoverable flag
- `request` - HITL request (input, confirmation, choice)
- `notification` - Toast-level messages
- `run.start`, `run.end` - Agent run lifecycle
- `tool.call`, `tool.result` - Tool execution events
- `state.update`, `state.snapshot` - State sync
- `state.update_rejected`, `state.update_accepted` - Proposal responses

**UI → Agent:**
- `command` - Execute operation
- `response` - Response to HITL request
- `cancel` - Cancel ongoing operation
- `context` - UI context update (selection, viewport)
- `state.sync_request` - Request full state sync
- `state.update_proposal` - Optimistic update proposal

**Dependencies:**
- Internal: `crypto.subtle` (Web Crypto API for SHA-256)
- External: None (pure TypeScript)

**State management:**
- Stateless (message definitions only)
- Sequence tracking in consumer (e.g., `agui/client.ts`)

---

## Why

**Rationale:** FR-009 requires "AG-UI run lifecycle with streaming". A typed protocol ensures backend and frontend stay in sync as features evolve, prevents breaking changes, and enables TypeScript compile-time checking.

**Design decisions:**
- **TypeScript types, not classes** - Data-only; serialization-friendly
- **JSON Patch (RFC 6902)** - Standard format; libraries available; bandwidth-efficient
- **SHA-256 checksums** - Detect corruption/man-in-the-middle
- **Sequence numbers** - Detect out-of-order and missing messages
- **Optimistic proposals** - Client suggests update; server authorizes (prevents desync)
- **HITL request type** - Built-in support for human-in-the-loop workflows

**Alternatives considered:**
- Unstructured JSON messages - Rejected (no type safety, easy to break)
- gRPC/Protobuf - Rejected (overkill, harder to evolve)
- Full-state sync only - Rejected (bandwidth-heavy, slow)

**Trade-offs:**
- **Gain:** Type safety across WebSocket boundary
- **Gain:** Bandwidth-efficient incremental updates (JSON Patch)
- **Gain:** Optimistic UI with server authorization
- **Loss:** Complexity in state sync logic (justified by real-time UX)
- **Gain:** Standard JSON Patch enables future tooling

---

## Acceptance Criteria

- [x] All message types defined with TypeScript types
- [x] Message envelope with version, ID, timestamp
- [x] JSON Patch implementation (RFC 6902)
- [x] SHA-256 checksum utility
- [x] Message builders (envelope, ID, timestamp)
- [x] Agent run lifecycle messages (start/end)
- [x] Tool call/result messages
- [x] State sync messages (update, snapshot, accept, reject)

---

## Testing

**Test location:** `intentuimvp/frontend/src/agui/protocol.test.ts` (to be created)

**Coverage notes:**
- `applyJSONPatch()` with all operation types
- `computeChecksum()` produces deterministic output
- Message builders generate valid envelopes
- Path utilities handle edge cases (root, nested, missing)

---

## Future Work

- [ ] Protocol version negotiation (upgrade path)
- [ ] Message compression for large patches
- [ ] Binary protocol option (for high-frequency updates)
- [ ] Message batching

---

**Last Updated:** 2026-01-13
**Author:** System (BigDaddyIntentCanvasRepo)
