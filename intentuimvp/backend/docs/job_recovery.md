# Job Recovery and Idempotency

## Overview

The Intent Canvas job system implements recovery and idempotency mechanisms to ensure reliable operation across restarts and failures. This document describes the recovery scenarios, checkpoint system, and idempotency guarantees.

## Recovery Mechanisms

### 1. Checkpoint System

Jobs save checkpoints at key steps during execution. Checkpoints are stored in the `job_metadata` field of the Job model and contain:

- `job_id`: Job identifier
- `step_name`: Name of the step being checkpointed
- `step_number`: Current step number
- `data`: Checkpoint data for recovery (job-specific state)
- `timestamp`: When checkpoint was created

**Example checkpoint:**
```json
{
  "job_id": "abc-123-def",
  "step_name": "perspective_technical",
  "step_number": 2,
  "data": {
    "perspective_results": [...],
    "current_perspective": "technical"
  },
  "timestamp": "2026-01-13T04:00:00Z"
}
```

### 2. Recovery Scenarios

#### Scenario 1: Mid-Execution Recovery

**Situation:** Worker crashes or restarts while a job is in progress.

**Behavior:**
1. On restart, job checks for existing checkpoint via `checkpoint_manager.load_checkpoint(job_id)`
2. If checkpoint exists, job resumes from the last completed step
3. Job skips already-completed work and continues from checkpoint state
4. Progress updates reflect resumed execution

**Example:** Deep research job crashes after completing 2 of 5 perspectives. On restart:
- Loads checkpoint with `perspective_results` for completed perspectives
- Skips perspectives 1-2
- Continues with perspective 3

#### Scenario 2: Startup Stale Job Recovery

**Situation:** Worker restarts and finds jobs left `in_progress` beyond the stale threshold.

**Behavior:**
1. On startup, worker queries for stale `in_progress` jobs (default 30 minutes)
2. Each stale job is marked as failed with a recovery message
3. Checkpoints remain available for manual retry
4. No duplicate side effects occur because jobs are not re-run automatically

**Example:** Worker restarts after a crash:
- Finds an in-progress job started an hour ago
- Marks job as failed with a recovery error message
- Job can be retried manually, resuming from checkpoint data

#### Scenario 3: Graceful Failure

**Situation:** Job encounters an unrecoverable error (e.g., invalid input, authentication failure).

**Behavior:**
1. Job catches exception and classifies it (transient vs permanent)
2. For permanent errors, job fails immediately without retry
3. Job status set to "failed" with error message
4. Checkpoint preserved for debugging/analysis
5. No partial results committed to database

**Example:** Job fails due to invalid API key:
- Exception classified as `FailureType.PERMANENT`
- Job marked as failed
- No retry attempted
- Error message stored in `job.error_message`

#### Scenario 4: Transient Failure with Retry

**Situation:** Job encounters a transient error (e.g., network timeout, rate limit).

**Behavior:**
1. Job catches exception and classifies it as transient
2. Retry policy determines backoff delay (exponential by default)
3. Job retries from last checkpoint (not from beginning)
4. After max retries, job fails gracefully
5. Retry count tracked in job metadata

**Example:** Job hits rate limit on step 3:
- Exception classified as `FailureType.TRANSIENT`
- Waits 2s (exponential backoff)
- Retries from checkpoint at step 3
- If still failing after 3 attempts, marks as failed

#### Scenario 5: Duplicate Job Prevention (Idempotency)

**Situation:** Same job submitted multiple times (e.g., user double-clicks, network retry).

**Behavior:**
1. Job ID is deterministic or checked for duplicates
2. If job already exists and is not in terminal state (complete/failed/cancelled), reject new submission
3. If job is complete, return existing result
4. No duplicate side effects (nodes, edges, artifacts)

**Example:** User submits deep research job twice:
- First submission creates job with ID `abc-123`
- Second submission checks for existing job with same parameters
- Returns existing job ID or result
- No duplicate research nodes created

## Idempotency Guarantees

### Database Operations

All database operations in job functions are designed to be idempotent:

1. **Node Creation:** Nodes are created with unique constraints or checked for existence before creation
2. **Edge Creation:** Edges are created with unique constraints on (canvas_id, from_node_id, to_node_id, relation_type)
3. **Artifact Storage:** Artifacts are keyed by job_id; re-storing overwrites previous artifact
4. **Job Status Updates:** Status transitions are validated by JobStateMachine to prevent invalid state changes

### External API Calls

External API calls (LLM, web search) are NOT automatically idempotent. Recovery strategy:

1. **Checkpoint before expensive calls:** Save state before calling external APIs
2. **Store results in checkpoint:** After successful API call, checkpoint the result
3. **Check checkpoint on retry:** Before making API call, check if result already exists in checkpoint
4. **Skip if already done:** If checkpoint contains result, skip the API call

**Example:**
```python
# Check checkpoint for existing result
checkpoint = await checkpoint_manager.load_checkpoint(job_id)
if checkpoint and "web_research" in checkpoint.data:
    research_report = checkpoint.data["web_research"]
else:
    # Make expensive API call
    research_report = await research_agent.research(query)
    # Save result in checkpoint
    await checkpoint_manager.save_checkpoint(
        job_id=job_id,
        step_name="web_research",
        step_number=2,
        data={"web_research": research_report}
    )
```

## Recovery Testing

### Test Scenarios

1. **Checkpoint Persistence:** Verify checkpoints are saved and loaded correctly
2. **Mid-Execution Resume:** Simulate crash and verify job resumes from checkpoint
3. **Startup Stale Recovery:** Mark stale in-progress jobs failed on worker startup
4. **Idempotent Node Creation:** Verify re-running job doesn't create duplicate nodes
5. **Graceful Failure:** Verify permanent errors fail without retry
6. **Transient Retry:** Verify transient errors trigger retry with backoff

### Test Implementation

See `intentuimvp/backend/tests/jobs/test_recovery.py` for comprehensive recovery tests.

## Monitoring and Debugging

### Checkpoint Inspection

To inspect checkpoint state for a job:

```python
from app.jobs.retry import checkpoint_manager

checkpoint = await checkpoint_manager.load_checkpoint(job_id)
if checkpoint:
    print(f"Last checkpoint: {checkpoint.step_name} at {checkpoint.timestamp}")
    print(f"Checkpoint data: {checkpoint.data}")
```

### Recovery Logs

Recovery events are logged at INFO level:

- `[job_id] Resuming from checkpoint: {step_name} (step {step_number})`
- `[job_id] Checkpoint saved: {step_name} (step {step_number})`
- `[job_id] Checkpoint cleared`
- `Recovered stale job during startup`

### Retry Tracking

Retry attempts are tracked in job metadata:

```python
from app.jobs.retry import get_job_retry_state

retry_state = await get_job_retry_state(job_id)
print(f"Retry count: {retry_state['retry_count']}/{retry_state['max_attempts']}")
print(f"Can retry: {retry_state['can_retry']}")
```

## Best Practices

### For Job Developers

1. **Checkpoint frequently:** Save checkpoints after each major step or expensive operation
2. **Include recovery state:** Store enough data in checkpoint to resume execution
3. **Check for existing work:** Before expensive operations, check if work already done in checkpoint
4. **Use idempotent operations:** Design database operations to be safely re-runnable
5. **Classify exceptions:** Use `TransientError` and `PermanentError` for proper retry behavior

### For Operators

1. **Monitor retry rates:** High retry rates indicate systemic issues (rate limits, network problems)
2. **Inspect failed jobs:** Check error messages and checkpoints for debugging
3. **Clear stale checkpoints:** Checkpoints are cleared on job completion, but may persist for failed jobs
4. **Set appropriate retry policies:** Adjust `max_attempts` and `backoff_strategy` per job type

## Configuration

### Retry Policies

Default retry policies are defined in `app/jobs/retry.py`:

```python
DEFAULT_RETRY_POLICIES = {
    "deep_research": RetryPolicy(
        max_attempts=3,
        backoff_strategy=BackoffStrategy.EXPONENTIAL,
        base_delay=2.0,
        max_delay=60.0,
        retry_transient_only=True,
    ),
    # ... other job types
}
```

### Checkpoint Storage

Checkpoints are stored in the `job_metadata` JSON field of the Job model. No separate storage required.

## Limitations

1. **Worker-level recovery only:** Recovery works within a single worker restart. Distributed recovery across multiple workers is not supported.
2. **No automatic resume:** Jobs do not automatically resume on worker restart. They must be manually retried or re-enqueued.
3. **Checkpoint size limits:** Large checkpoint data may exceed database field limits. Keep checkpoint data minimal.
4. **External API idempotency:** External APIs (LLM, web search) are not automatically idempotent. Manual checkpoint checks required.

## Future Enhancements

1. **Automatic resume on restart:** Detect in-progress jobs on worker startup and resume automatically
2. **Distributed checkpoints:** Store checkpoints in Redis for multi-worker recovery
3. **Checkpoint compression:** Compress large checkpoint data to reduce storage
4. **Recovery metrics:** Track recovery success rates and checkpoint usage
