from contextlib import closing
"""Bounded background workers with durable status/results and restart recovery.

Use one API worker process. A restarted process resumes queued descriptors and
marks interrupted running work failed; it never pretends that work completed.
"""
import json
import logging
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from backend.config import (DB_PATH, JOB_WORKERS, MAX_PENDING_JOBS, MAX_JOBS_PER_USER,
                            JOB_RETENTION_SECONDS, MAX_JOB_HISTORY)
from backend.services.serializer import sanitize_for_json

logger = logging.getLogger(__name__)


def now():
    return datetime.now(timezone.utc).isoformat()


class QueueFullError(ValueError):
    pass


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    job_id: str
    project_id: str
    owner_id: str = ""
    kind: str = "custom"
    payload: dict = field(default_factory=dict)
    status: JobStatus = JobStatus.QUEUED
    progress: int = 0
    current_step: str = "Queued"
    result: dict | None = None
    error: str | None = None
    created_at: str = field(default_factory=now)
    started_at: str | None = None
    completed_at: str | None = None
    execution_steps: list = field(default_factory=list)


class JobQueue:
    def __init__(self, db_path=DB_PATH, *, max_workers=JOB_WORKERS,
                 max_pending=MAX_PENDING_JOBS, max_per_user=MAX_JOBS_PER_USER,
                 retention_seconds=JOB_RETENTION_SECONDS, max_history=MAX_JOB_HISTORY):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_pending, self.max_per_user = max_pending, max_per_user
        self.retention_seconds, self.max_history = retention_seconds, max_history
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="analyst-job")
        self._jobs = {}
        self._recovered = False
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute("CREATE TABLE IF NOT EXISTS background_jobs (job_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, snapshot TEXT NOT NULL)")
            conn.execute("CREATE INDEX IF NOT EXISTS jobs_project ON background_jobs(project_id)")
            for (snapshot,) in conn.execute("SELECT snapshot FROM background_jobs"):
                values = json.loads(snapshot)
                values['status'] = JobStatus(values['status'])
                job = Job(**values)
                self._jobs[job.job_id] = job
        self._cleanup_expired()

    def _save(self, job):
        payload = json.dumps(sanitize_for_json(asdict(job)), allow_nan=False)
        with closing(sqlite3.connect(self.db_path, timeout=30)) as conn, conn:
            conn.execute("INSERT OR REPLACE INTO background_jobs VALUES(?,?,?)", (job.job_id, job.project_id, payload))

    def submit(self, project_id, fn, fn_args=(), fn_kwargs=None, on_progress=None,
               *, owner_id="", kind="custom", payload=None):
        with self._lock:
            self._cleanup_expired()
            pending = [j for j in self._jobs.values() if j.status in (JobStatus.QUEUED, JobStatus.RUNNING)]
            if len(pending) >= self.max_pending:
                raise QueueFullError("Job capacity reached. Try again after current work completes.")
            if any(j.project_id == project_id for j in pending):
                raise QueueFullError("This project already has queued or running work.")
            if owner_id and sum(j.owner_id == owner_id for j in pending) >= self.max_per_user:
                raise QueueFullError("Your active-job limit has been reached.")
            job = Job(str(uuid.uuid4()), project_id, owner_id=owner_id, kind=kind, payload=payload or {})
            self._save(job)
            self._jobs[job.job_id] = job
            self._executor.submit(self._run_job, job.job_id, fn, fn_args or (), dict(fn_kwargs or {}), on_progress)
            return job.job_id

    def _run_job(self, job_id, fn, fn_args, fn_kwargs, on_progress):
        try:
            with self._lock:
                job = self._jobs[job_id]
                job.status, job.started_at = JobStatus.RUNNING, now()
                job.current_step, job.progress = "Starting", 1
                self._save(job)
            if on_progress is not None:
                def report(pct, step):
                    self.update_progress(job_id, pct, step)
                    if callable(on_progress):
                        on_progress(job_id, pct, step)
                fn_kwargs['_progress_callback'] = report
            result = fn(*fn_args, **fn_kwargs)
            with self._lock:
                job.result = sanitize_for_json(result)
                job.status, job.progress, job.current_step = JobStatus.COMPLETED, 100, "Complete"
                job.completed_at = now()
                self._save(job)
        except Exception as exc:
            logger.exception("Job %s failed", job_id)
            with self._lock:
                job = self._jobs[job_id]
                job.status, job.error, job.completed_at = JobStatus.FAILED, str(exc), now()
                job.current_step = "Failed: " + str(exc)
                self._save(job)

    def update_progress(self, job_id, pct, step):
        with self._lock:
            job = self._jobs.get(job_id)
            if job and job.status == JobStatus.RUNNING:
                job.progress = max(job.progress, min(99, max(0, int(pct))))
                job.current_step = str(step)
                job.execution_steps.append(f"[{job.progress}%] {step}")
                job.execution_steps = job.execution_steps[-100:]
                self._save(job)

    def get_status(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            result = asdict(job)
            result['status'] = job.status.value
            result['has_result'] = job.result is not None
            result['execution_steps'] = list(job.execution_steps[-10:])
            for key in ('result', 'payload', 'owner_id'):
                result.pop(key)
            return result

    def get_result(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            return job.result if job and job.status == JobStatus.COMPLETED else None

    def latest_for_project(self, project_id):
        with self._lock:
            jobs = sorted((j for j in self._jobs.values() if j.project_id == project_id), key=lambda j: j.created_at)
            return {j.kind: self.get_status(j.job_id) for j in jobs}

    def has_pending(self, project_id):
        with self._lock:
            return any(j.project_id == project_id and j.status in (JobStatus.QUEUED, JobStatus.RUNNING) for j in self._jobs.values())

    def recover(self, handlers):
        """Called once at app startup after durable session handlers are available."""
        with self._lock:
            if self._recovered:
                return
            self._recovered = True
            for job in self._jobs.values():
                if job.status == JobStatus.RUNNING or (job.status == JobStatus.QUEUED and job.kind not in handlers):
                    job.status, job.completed_at = JobStatus.FAILED, now()
                    job.error = "Server restarted during this job. Submit it again to retry."
                    job.current_step = "Interrupted by server restart"
                    self._save(job)
                elif job.status == JobStatus.QUEUED:
                    def resume(_progress_callback, item=job):
                        return handlers[item.kind](item.project_id, item.owner_id, item.payload, _progress_callback)
                    self._executor.submit(self._run_job, job.job_id, resume, (), {}, True)

    def _cleanup_expired(self):
        with self._lock:
            terminal = sorted((j for j in self._jobs.values() if j.completed_at), key=lambda j: j.completed_at, reverse=True)
            delete = []
            for index, job in enumerate(terminal):
                if index >= self.max_history or time.time() - datetime.fromisoformat(job.completed_at).timestamp() > self.retention_seconds:
                    delete.append(job.job_id)
            if delete:
                with closing(sqlite3.connect(self.db_path)) as conn, conn:
                    conn.executemany("DELETE FROM background_jobs WHERE job_id=?", [(j,) for j in delete])
                for job_id in delete:
                    del self._jobs[job_id]

    def shutdown(self, wait=True):
        self._executor.shutdown(wait=wait, cancel_futures=not wait)


job_queue = JobQueue()
