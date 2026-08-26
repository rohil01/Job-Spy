"""In-memory registry for background runs (scrape / full pipeline).

This is a process-local store — fine for a single-worker deployment. For
multi-worker or persistent status, swap this for Redis or a database.
"""

import threading
import uuid
from typing import Any, Dict, Optional

_runs: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()


def create_run() -> str:
    """Register a new run and return its id."""
    run_id = uuid.uuid4().hex
    with _lock:
        _runs[run_id] = {
            "run_id": run_id,
            "status": "pending",
            "progress": None,
            "percent": None,
            "error": None,
            "result": None,
        }
    return run_id


def update_run(
    run_id: str,
    *,
    status: Optional[str] = None,
    progress: Optional[str] = None,
    percent: Optional[float] = None,
    error: Optional[str] = None,
    result: Optional[Dict[str, Any]] = None,
) -> None:
    """Update fields of an existing run (no-op if unknown)."""
    with _lock:
        run = _runs.get(run_id)
        if run is None:
            return
        if status is not None:
            run["status"] = status
        if progress is not None:
            run["progress"] = progress
        if percent is not None:
            run["percent"] = percent
        if error is not None:
            run["error"] = error
        if result is not None:
            run["result"] = result


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    """Return a copy of the run record, or None if unknown."""
    with _lock:
        run = _runs.get(run_id)
        return dict(run) if run is not None else None
