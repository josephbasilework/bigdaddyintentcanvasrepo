# E-005: Job System Deep Research - Implementation Plan

## Executive Summary

This document outlines the architecture and implementation plan for IntentUI's job system supporting deep research agents, streaming LLM responses, and LLM-as-judge validation.

**Key Decision**: Use **ARQ** (async Redis Queue) instead of Celery because:
- Native asyncio integration with FastAPI
- Simpler setup (Redis only, no separate result backend)
- More efficient for I/O-bound tasks (LLM API calls, web requests)
- Lower memory footprint due to cooperative multitasking

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FastAPI Application                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │   API Route  │───▶│ Job Manager  │───▶│ ARQ Client   │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│         │                    │                    │                  │
│         ▼                    ▼                    ▼                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │ SSE Endpoint │    │   WebSocket  │    │   Database   │          │
│  │  (streaming) │    │   (progress) │    │  (jobs table)│          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Redis (pub/sub + queue)
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        ARQ Worker Process                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                      Job Functions                           │   │
│  ├──────────────────────────────────────────────────────────────┤   │
│  │  • deep_research_job()                                      │   │
│  │  • streaming_generation_job()                               │   │
│  │  • llm_judge_job()                                          │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                   │                                  │
│                                   ▼                                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Research Agents                           │   │
│  ├──────────────────────────────────────────────────────────────┤   │
│  │  • DeepResearchAgent (multi-step reasoning)                  │   │
│  │  • StreamingAgent (token-by-token generation)                │   │
│  │  • JudgeAgent (LLM-as-judge validation)                      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                   │                                  │
│                                   ▼                                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                   External Services                          │   │
│  ├──────────────────────────────────────────────────────────────┤   │
│  │  • Gateway Client (Pydantic AI Gateway)                      │   │
│  │  • MCP Tools (Calendar, Web Search, etc.)                    │   │
│  │  • Z.AI CLI (web search, vision)                             │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. Job Queue System (ARQ + Redis)

**Purpose**: Async job processing with Redis as broker and state backend.

**Key Features**:
- Job enqueueing with priority queues
- Job status tracking (pending, in_progress, complete, failed)
- Automatic retries with exponential backoff
- Job results storage in Redis
- Concurrent job execution (configurable max_jobs)

**Configuration**:
```python
# Worker settings
functions = [
    deep_research_job,
    streaming_generation_job,
    llm_judge_job,
]
redis_settings = RedisSettings(
    host=settings.redis_host,
    port=settings.redis_port,
    database=settings.redis_db,
)
max_jobs = 10  # Concurrent jobs
job_timeout = 600  # 10 minutes
```

---

### 2. Database Models

**File**: `app/models/job.py`

```python
class Job(Base):
    """Job model for tracking async tasks."""

    __tablename__ = "job"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[str] = mapped_column(String, unique=True, index=True)  # ARQ job ID
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String, nullable=False)  # research, judge, stream
    status: Mapped[str] = mapped_column(String, default="pending")  # pending, in_progress, complete, failed
    priority: Mapped[int] = mapped_column(Integer, default=5)
    input_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0 to 1.0
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

---

### 3. Gateway Client with Streaming Support

**File**: `app/gateway/client.py` (modifications)

Add streaming support to the Gateway client:

```python
async def generate_stream(
    self,
    model: str,
    messages: list[dict[str, Any]],
    **kwargs: Any,
) -> AsyncIterator[str]:
    """Generate a streaming completion via the Gateway.

    Yields tokens as they arrive from the Gateway.

    Args:
        model: Model identifier
        messages: Chat messages
        **kwargs: Additional parameters

    Yields:
        Individual tokens from the LLM response.
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,  # Enable streaming
        **kwargs,
    }

    async with self._get_client().stream(
        "POST", "/v1/chat/completions", json=payload
    ) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data = line[6:]  # Remove "data: " prefix
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    token = chunk["choices"][0]["delta"].get("content", "")
                    if token:
                        yield token
                except (json.JSONDecodeError, KeyError):
                    continue
```

---

### 4. Research Agents

**File**: `app/agents/research.py`

#### DeepResearchAgent
Multi-step reasoning for complex research tasks:
1. Decompose query into sub-questions
2. Gather information from multiple sources (web, MCP tools)
3. Synthesize findings
4. Validate with LLM-as-judge
5. Return structured results

#### StreamingAgent
Token-by-token generation with SSE streaming:
- Wraps Gateway streaming calls
- Broadcasts progress via WebSocket
- Yields tokens to SSE endpoint

#### JudgeAgent
LLM-as-judge for validation:
- Evaluates research outputs
- Scores relevance, correctness, completeness
- Detects hallucinations
- Returns structured judgment

---

### 5. API Endpoints

**File**: `app/api/jobs.py`

```python
# POST /api/v1/jobs - Create and enqueue a job
# GET /api/v1/jobs/{job_id} - Get job status
# GET /api/v1/jobs - List user's jobs
# DELETE /api/v1/jobs/{job_id} - Cancel a job
# GET /api/v1/jobs/{job_id}/stream - SSE stream for job progress
```

---

### 6. Real-time Updates

**SSE Endpoint**: For streaming job progress and token generation
```python
@router.get("/jobs/{job_id}/stream")
async def stream_job(job_id: str):
    """Stream job progress via Server-Sent Events."""
    async def event_generator():
        while True:
            job = await get_job_status(job_id)
            yield f"data: {json.dumps(job)}\n\n"
            if job["status"] in ("complete", "failed"):
                break
            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())
```

**WebSocket Integration**: Extend existing ConnectionManager for job updates
```python
async def broadcast_job_update(job_id: str, update: dict):
    """Broadcast job update to all connected clients."""
    await manager.broadcast(json.dumps({
        "type": "job_update",
        "job_id": job_id,
        **update
    }))
```

---

### 7. Job Functions (ARQ Workers)

**File**: `app/jobs/functions.py`

```python
async def deep_research_job(ctx: dict, query: str, user_id: str, job_id: str):
    """Execute deep research with multi-step reasoning."""
    # Update status
    await update_job_status(job_id, "in_progress", progress=0.0)

    # Initialize agent
    agent = DeepResearchAgent()

    # Execute research steps
    result = await agent.run({"query": query})

    # Validate with judge
    judge = JudgeAgent()
    validation = await judge.validate(result, query)

    # Store results
    await update_job_status(job_id, "complete", result=result, validation=validation)

    return result
```

---

## Implementation Phases

### Phase 1: Infrastructure Setup (Week 1)
1. Add ARQ and Redis to dependencies
2. Set up Redis configuration (local dev + production)
3. Create Job database model
4. Set up database migrations
5. Create ARQ worker entry point

### Phase 2: Job System Core (Week 2)
1. Implement JobManager class for enqueueing/status queries
2. Create job API endpoints
3. Implement ARQ worker functions
4. Add job retry logic
5. Implement job priority queues

### Phase 3: Streaming Support (Week 3)
1. Add streaming support to Gateway client
2. Implement SSE endpoint for job progress
3. Extend WebSocket for job updates
4. Implement StreamingAgent
5. Test token-by-token delivery

### Phase 4: Research Agents (Week 4)
1. Implement DeepResearchAgent
2. Implement JudgeAgent (LLM-as-judge)
3. Add MCP tool integration
4. Implement multi-step reasoning pipeline
5. Add validation and scoring

### Phase 5: Testing & Polish (Week 5)
1. Add comprehensive tests
2. Performance testing and optimization
3. Error handling and edge cases
4. Documentation
5. Deployment configuration

---

## Dependencies to Add

**pyproject.toml**:
```toml
dependencies = [
    # ... existing
    "arq>=0.26.0",           # Async job queue
    "redis>=5.0.0",          # Redis client
    "aiosse>=1.0.0",         # SSE support for FastAPI
]
```

---

## Configuration

**app/config.py** additions:
```python
# Redis
redis_host: str = Field(default="localhost", description="Redis host")
redis_port: int = Field(default=6379, description="Redis port")
redis_db: int = Field(default=0, description="Redis database")
redis_password: str = Field(default="", description="Redis password")

# Job System
job_max_concurrent: int = Field(default=10, description="Max concurrent jobs")
job_timeout_seconds: int = Field(default=600, description="Job timeout")
job_retry_attempts: int = Field(default=3, description="Job retry attempts")
```

---

## File Structure

```
intentuimvp/backend/app/
├── agents/
│   ├── base.py (existing)
│   ├── echo.py (existing)
│   ├── research.py (NEW)
│   │   ├── DeepResearchAgent
│   │   ├── StreamingAgent
│   │   └── JudgeAgent
│   └── __init__.py
├── gateway/
│   └── client.py (MODIFY - add streaming)
├── jobs/
│   ├── __init__.py
│   ├── functions.py (NEW - ARQ job functions)
│   ├── manager.py (NEW - JobManager class)
│   └── worker.py (NEW - ARQ worker entry point)
├── models/
│   ├── canvas.py (existing)
│   ├── job.py (NEW - Job database model)
│   └── __init__.py
├── api/
│   ├── jobs.py (NEW - Job API endpoints)
│   └── stream.py (NEW - SSE endpoints)
├── config.py (MODIFY - add Redis/jobs config)
└── main.py (MODIFY - register job routes)
```

---

## Exit Criteria

E-005 is complete when:
1. [ ] ARQ worker can run and process jobs
2. [ ] Deep research agent executes multi-step reasoning
3. [ ] LLM-as-judge validates research outputs
4. [ ] SSE streaming delivers tokens in real-time
5. [ ] WebSocket broadcasts job progress
6. [ ] Jobs persist to database with status tracking
7. [ ] Retry mechanism handles failures
8. [ ] All tests pass with >80% coverage

---

## References

- **ARQ Documentation**: https://arq-docs.helpmanual.io/
- **FastAPI SSE**: https://fastapi.tiangolo.com/advanced/custom-response/#server-send-events
- **LLM-as-Judge Guide**: https://www.evidentlyai.com/llm-guide/llm-as-a-judge
- **Celery vs ARQ**: https://leapcell.io/blog/celery-versus-arq-choosing-the-right-task-queue-for-python-applications
