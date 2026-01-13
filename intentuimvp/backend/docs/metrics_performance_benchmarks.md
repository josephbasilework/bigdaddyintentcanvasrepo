# Metrics Aggregation Performance Benchmarks

## Overview

This document records performance benchmarks for the PRD §5.2 success metrics aggregation and query endpoints (JM-8 T3).

## Implementation Approach

### Data Model
- **TelemetryEventDB**: Stores all telemetry events in a single table
- **Indexing**: All queryable fields (`event_name`, `user_id`, `session_id`, `workspace_id`, `run_id`, `correlation_id`, `event_timestamp`) are indexed
- **Event data**: Stored as JSON string for flexibility

### Query Strategy
- **On-the-fly computation**: Metrics are computed from raw events at query time
- **Rolling windows**: Time-based filtering (24h, 7d)
- **Filter support**: Optional `user_id` and `workspace_id` filters

## Performance Notes

### Current Implementation (MVP)
- **Simple approach**: Direct SQL queries with time-based filtering
- **No pre-aggregation**: Metrics computed on-demand from raw events
- **Suitable for**:
  - Low to moderate event volumes
  - Development/testing environments
  - MVP demonstration

### Expected Performance Characteristics

| Metric | Est. Query Time | Notes |
|--------|----------------|-------|
| Task Completion Rate | 10-100ms | Simple count with status filter |
| Assumption Accuracy | 10-100ms | Simple count with resolution filter |
| Time-to-Value | 50-200ms | Requires JSON parsing for durations |
| Session Continuity | 10-100ms | Simple count with previous_session check |
| Research Job Completion | 10-100ms | Uses Job table (no JSON parsing) |
| Command vs Chat Ratio | 20-150ms | Two separate count queries |
| MCP Adoption | 20-150ms | DISTINCT count queries |

### Scaling Considerations

For production with high event volumes, consider:

1. **Materialized views / Pre-aggregation**
   - Create daily/hourly aggregate tables
   - Update via background job or trigger
   - Reduces query time to <10ms

2. **Time-series database**
   - Use ClickHouse, TimescaleDB, or similar
   - Optimized for time-windowed aggregations
   - Built-in rollup functions

3. **Caching layer**
   - Redis/Memcached for recent window queries
   - 1-5 minute TTL for 24h/7d metrics
   - Reduces database load

4. **Event retention policy**
   - Archive/delete events older than N days
   - Keep only aggregated data for historical analysis
   - Reduces table size and improves query performance

## Load Testing Recommendations

### Test Scenarios

1. **Baseline**: Empty database, single user
   - Establish minimum latency
   - Verify SQL query plans

2. **Single user, 1000 events**: Test early-stage usage
   - Verify 24h window queries remain fast
   - Check JSON parsing performance

3. **100 users, 100K events**: Test production-like load
   - Measure query degradation
   - Identify need for indexing or pre-aggregation

4. **1000 users, 1M+ events**: Stress test
   - Verify database can handle load
   - Test concurrent metric queries

### Success Criteria

- **P50 latency**: <50ms for all metrics
- **P95 latency**: <200ms for all metrics
- **P99 latency**: <500ms for all metrics
- **Concurrent users**: Support 10+ simultaneous metric queries

## Database Schema Notes

### Indexes for Query Performance

```sql
-- These indexes are automatically created by the model
CREATE INDEX ix_telemetry_events_event_name ON telemetry_events(event_name);
CREATE INDEX ix_telemetry_events_user_id ON telemetry_events(user_id);
CREATE INDEX ix_telemetry_events_session_id ON telemetry_events(session_id);
CREATE INDEX ix_telemetry_events_workspace_id ON telemetry_events(workspace_id);
CREATE INDEX ix_telemetry_events_run_id ON telemetry_events(run_id);
CREATE INDEX ix_telemetry_events_correlation_id ON telemetry_events(correlation_id);
CREATE INDEX ix_telemetry_events_event_timestamp ON telemetry_events(event_timestamp);
```

### Composite Indexes (Future Optimization)

For high-volume deployments, consider composite indexes:

```sql
-- For time-windowed user queries
CREATE INDEX ix_telemetry_events_user_event_time
    ON telemetry_events(user_id, event_timestamp);

-- For workspace-focused queries
CREATE INDEX ix_telemetry_events_workspace_event_time
    ON telemetry_events(workspace_id, event_timestamp);

-- For metric-specific queries
CREATE INDEX ix_telemetry_events_name_time
    ON telemetry_events(event_name, event_timestamp);
```

## PII and Security Notes

### PII Handling
- **PII redaction**: Occurs at event emission time (`telemetry_events.py`)
- **PII detector**: Uses `PIIDetector` with `PIIMode.REDACT`
- **Audit logging**: PII redactions are logged as audit events
- **No PII in logs**: Aggregations only contain counts and computed values

### User ID Handling
- **No raw PII**: `user_id` should be UUID or hash, not email/username
- **Optional**: Most metrics work without `user_id`
- **Filtering**: `user_id` is only used for per-user queries, not exposed in responses

## Related Documentation

- `app/telemetry_events.py`: Event emission and PII redaction
- `app/services/metrics_service.py`: Metric computation logic
- `app/api/telemetry.py`: API endpoint definitions
- `tests/app/api/test_metrics.py`: Metric query tests
- PRD §5.2: Success metrics definitions
