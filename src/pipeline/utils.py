import time
import logging
from datetime import date, datetime, time as time_obj
from decimal import Decimal
from typing import List, Dict, Any, Tuple
# from ..agent.ai_job_agent import AIJobAgent


def make_json_safe(value: Any) -> Any:
    """Convert non-JSON-native Python values into JSON-safe equivalents."""
    if isinstance(value, (datetime, date, time_obj)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (list, tuple)):
        return [make_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): make_json_safe(item) for key, item in value.items()}
    if isinstance(value, set):
        return [make_json_safe(item) for item in value]
    return value


def setup_logger(name: str = "pipeline") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def cooldown_sleep(minutes: float, logger: logging.Logger) -> None:
    """Pause for ``minutes`` minutes between scrape passes.

    Accepts fractional minutes so short cooldowns are possible: ``0.5`` sleeps
    for 30 seconds. Non-positive values are a no-op.
    """
    seconds = max(0.0, float(minutes) * 60.0)
    if seconds <= 0:
        return
    logger.info(f"Cooling down for {int(seconds // 60)}m {int(seconds % 60)}s…")
    time.sleep(seconds)


def _posting_key(job: Dict[str, Any]) -> str:
    """Stable identity for a single posting.

    Prefers ``job_url``; falls back to a hash of title/company/location/date so
    postings without a URL still collapse when they are genuinely the same.
    """
    key = job.get("job_url")
    if not key:
        date_value = job.get("date_posted")
        if isinstance(date_value, (datetime, date, time_obj)):
            date_value = date_value.isoformat()
        key = f"{job.get('title','')}|{job.get('company','')}|{job.get('location','')}|{date_value}"
    return key


def deduplicate_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicates based on job_url if present, otherwise fallback to a hash of
    title, company, location, and date_posted.
    """
    seen = set()
    unique_jobs = []
    for job in jobs:
        key = _posting_key(job)
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)
    return unique_jobs


def _normalize_text(value: Any) -> str:
    """Trim, collapse internal whitespace, and case-fold for match keys."""
    return " ".join(str(value or "").split()).casefold()


def group_key(job: Dict[str, Any]) -> Tuple[str, str]:
    """Duplicate-grouping key: normalized ``(company, title)``.

    Normalization only trims/collapses whitespace and case-folds — it does NOT
    strip seniority, so "Senior Software Engineer" and "Software Engineer" are
    distinct groups (per the agreed matching rule).
    """
    return (_normalize_text(job.get("company")), _normalize_text(job.get("title")))


class JobGrouper:
    """Incrementally groups postings by exact (company, title) match.

    Stateful so it can be fed one search term at a time during a streamed
    scrape: postings for the same role that arrive across several batches merge
    into a single group. Exact-duplicate postings (same ``job_url``/fallback
    key) are collapsed globally.
    """

    def __init__(self) -> None:
        self._groups: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._order: List[Tuple[str, str]] = []
        self._seen: set = set()

    def add_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge a batch of postings; return the created-or-updated groups.

        The returned list contains a fresh snapshot of every group this batch
        touched (in first-affected order) — used to stream group deltas.
        """
        affected: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for job in jobs or []:
            pkey = _posting_key(job)
            if pkey in self._seen:
                continue
            self._seen.add(pkey)

            gkey = group_key(job)
            group = self._groups.get(gkey)
            if group is None:
                group = {
                    "group_id": f"g{len(self._groups)}",
                    "company": job.get("company") or "",
                    "title": job.get("title") or "",
                    "postings": [],
                }
                self._groups[gkey] = group
                self._order.append(gkey)
            group["postings"].append(job)
            affected[gkey] = group

        return [self._snapshot(group) for group in affected.values()]

    @staticmethod
    def _snapshot(group: Dict[str, Any]) -> Dict[str, Any]:
        """Build a serializable group dict, annotating postings with group info."""
        postings = group["postings"]
        count = len(postings)
        for posting in postings:
            posting["group_id"] = group["group_id"]
            posting["group_count"] = count
        return {
            "group_id": group["group_id"],
            "company": group["company"],
            "title": group["title"],
            "count": count,
            "postings": postings,
        }

    def ordered_groups(self) -> List[Dict[str, Any]]:
        """All groups in first-seen order."""
        return [self._snapshot(self._groups[key]) for key in self._order]

    def flat_annotated(self) -> List[Dict[str, Any]]:
        """Flat, deduped list of postings, each annotated with group_id/group_count."""
        flat: List[Dict[str, Any]] = []
        for group in self.ordered_groups():
            flat.extend(group["postings"])
        return flat

    def num_groups(self) -> int:
        return len(self._order)

    def num_jobs(self) -> int:
        return len(self._seen)


def group_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Batch convenience: group a full list of postings in one call."""
    grouper = JobGrouper()
    grouper.add_jobs(jobs)
    return grouper.ordered_groups()


# AI Agent singleton
# _ai_agent = None


# def _get_ai_agent() -> AIJobAgent:
#     """Lazy singleton for AIJobAgent."""
#     global _ai_agent
#     if _ai_agent is None:
#         _ai_agent = AIJobAgent()
#     return _ai_agent


# def filter_by_experience_level(jobs: List[Dict[str, Any]], experience_levels: List[str]) -> List[Dict[str, Any]]:
#     """
#     Filter jobs by experience level using AI agent (with fallback to string matching).
#     """
#     agent = _get_ai_agent()
#     return agent.filter_by_experience_level(jobs, experience_levels)


# def match_resume(jobs: List[Dict[str, Any]], resume_skills: List[str]) -> List[Dict[str, Any]]:
#     """Match jobs against resume skills using AI agent (with fallback to string matching)."""
#     agent = _get_ai_agent()
#     return agent.match_resume(jobs, resume_skills)