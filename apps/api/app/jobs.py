"""Background jobs — re-exports from job_runner (PROD-3 seam)."""

from app.job_runner import (  # noqa: F401
    JobHandle,
    JobRunner,
    InProcessJobRunner,
    JOB_TIMEOUTS,
    MAX_CONCURRENT_JOBS,
    cancel_job,
    create_job,
    enqueue,
    get_job,
    get_job_runner,
    job_cancelled,
    mark_interrupted_jobs_on_boot,
)

__all__ = [
    "JobHandle",
    "JobRunner",
    "InProcessJobRunner",
    "JOB_TIMEOUTS",
    "MAX_CONCURRENT_JOBS",
    "cancel_job",
    "create_job",
    "enqueue",
    "get_job",
    "get_job_runner",
    "job_cancelled",
    "mark_interrupted_jobs_on_boot",
]
