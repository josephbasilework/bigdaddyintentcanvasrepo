# WebSocket Reconnection Enhancement Plan

**Issue:** [T2-F9.2](bigdaddyintentcanvasrepo-827)
**Status:** ✅ Complete

## Summary

All T2-F9.2 requirements have been implemented in `useWebSocketEnhanced`:

1. ✅ Exponential backoff reconnection (1s base, 30s cap, max 10 attempts)
2. ✅ Event queuing during disconnection
3. ✅ Sequence gap detection with REST snapshot sync
4. ✅ Telemetry tracking for NFR-PERF-005

## Implementation Details

### Files Modified/Created

| File | Description |
|------|-------------|
| `intentuimvp/frontend/src/hooks/useWebSocketEnhanced.ts` | Enhanced hook with all T2-F9.2 features |
| `intentuimvp/frontend/src/hooks/useWebSocketEnhanced.test.ts` | Unit tests covering all features |
| `intentuimvp/docs/WEBSOCKET_RECONNECT.md` | This documentation |

### Features Implemented

#### Exponential Backoff Reconnection
- Base delay: 1000ms (configurable via `reconnectDelayMs`)
- Max delay cap: 30000ms (30s)
- Max attempts: 10 (configurable via `maxReconnectAttempts`)

#### Event Queueing
- Events sent while disconnected are queued (up to 100 by default)
- Queue is flushed automatically after successful reconnect
- Queue size limit configurable via `maxQueueSize`
- `onEventsFlushed` callback fires after reconnect with flushed events

#### Sequence Gap Detection
- Tracks `sequence` field in incoming messages
- Detects gaps and triggers `onSyncSnapshot` callback
- `lastSequence` state reflects most recent sequence
- `hasSequenceGap` state indicates gap detected
- Can be disabled via `enableSequenceTracking: false`

#### Telemetry (NFR-PERF-005)
- Tracks disconnect time using `performance.now()`
- Records reconnection time via `recordWsReconnect()`
- Marks success/failure based on reconnect outcome
- Target: < 5000ms reconnection time

### Hook Usage

```typescript
const {
  connectionState,
  send,
  queuedEventCount,
  lastSequence,
  hasSequenceGap,
} = useWebSocketEnhanced({
  url: "ws://localhost:8000/ws",
  reconnectDelayMs: 1000,
  maxReconnectAttempts: 10,
  maxQueueSize: 100,
  enableSequenceTracking: true,
  onEventsFlushed: (events) => {
    console.log(`Flushed ${events.length} events`);
  },
  onSyncSnapshot: async () => {
    const res = await fetch("/api/workspace/snapshot");
    return res.json();
  },
});
```

## Backend Requirements

For full sequence tracking, the backend should:

1. Add `sequence` field to WebSocket messages
2. Provide `/api/v1/workspace/snapshot` endpoint for state recovery

These are optional enhancements - the frontend handles missing sequences gracefully.

## Testing

Run tests with:
```bash
cd intentuimvp/frontend
npm test -- --run --grep "useWebSocketEnhanced"
```

All tests verify:
- Event queueing and flushing
- Sequence gap detection
- Exponential backoff behavior
- Telemetry recording
