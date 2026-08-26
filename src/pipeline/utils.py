import time
import logging
from datetime import date, datetime, time as time_obj
from decimal import Decimal
from typing import List, Dict, Any
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


def deduplicate_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicates based on job_url if present, otherwise fallback to a hash of
    title, company, location, and date_posted.
    """
    seen = set()
    unique_jobs = []
    for job in jobs:
        key = job.get("job_url")
        if not key:
            # Build a fallback key
            date_value = job.get("date_posted")
            if isinstance(date_value, (datetime, date, time_obj)):
                date_value = date_value.isoformat()
            key = f"{job.get('title','')}|{job.get('company','')}|{job.get('location','')}|{date_value}"
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)
    return unique_jobs


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