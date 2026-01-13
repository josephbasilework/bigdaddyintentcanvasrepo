"""Performance metrics instrumentation for job execution.

Implements NFR-PERF-004: Simple command execution timing with Logfire spans.
"""

import functools
import time
from collections.abc import Callable
from typing import Any

import logfire

from app.jobs.base import JobType


def track_job_execution(job_type: JobType) -> Callable:
    """Decorator to track job execution time with Logfire spans.

    Implements NFR-PERF-004: Command execution timing for jobs.

    Args:
        job_type: The type of job being executed.

    Returns:
        Decorator function that wraps the job function.

    Example:
        ```python
        @track_job_execution(JobType.DEEP_RESEARCH)
        async def deep_research_job(ctx, query: str) -> JobResult:
            ...
        ```
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract job_id from context if available
            ctx = args[0] if args else {}
            job_id = ctx.get("job_id", "unknown") if isinstance(ctx, dict) else "unknown"

            with logfire.span(
                f"job.{job_type.value}",
                job_type=job_type.value,
                job_id=job_id,
            ) as span:
                start_time = time.monotonic()
                try:
                    result = await func(*args, **kwargs)
                    duration_ms = (time.monotonic() - start_time) * 1000

                    span.set_attribute("duration_ms", duration_ms)
                    span.set_attribute("success", getattr(result, "success", True))

                    return result
                except Exception as e:
                    duration_ms = (time.monotonic() - start_time) * 1000
                    span.set_attribute("duration_ms", duration_ms)
                    span.set_attribute("success", False)
                    span.set_attribute("error", type(e).__name__)
                    raise

        return wrapper

    return decorator
