"""Service layer: orchestrates the scraper and the three AI agents.

The FastAPI routes in ``app.py`` stay thin; all the wiring lives here so it can
be unit-tested and reused. Blocking work (scraping, LLM calls) is invoked from
background tasks by ``app.py`` via Starlette's threadpool.
"""

import json
import math
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import config
from scraper.scraper import JobScraper
from Agent.ai_job_agent import AIJobAgent
from Agent.resume_io import build_docx
from pipeline.utils import make_json_safe, group_jobs

from . import tasks

# --------------------------------------------------------------------------- #
# Shared config / singletons
# --------------------------------------------------------------------------- #
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_OUTPUT_ROOT = _PROJECT_ROOT / "data" / "output"

_agent: Optional[AIJobAgent] = None
_agent_lock = threading.Lock()


def load_config() -> Dict[str, Any]:
    return config.load_config()


def get_agent() -> AIJobAgent:
    """Lazy, thread-safe singleton for the AI agent."""
    global _agent
    if _agent is None:
        with _agent_lock:
            if _agent is None:
                _agent = AIJobAgent()
    return _agent


def get_scraper(overrides: Optional[Dict[str, Any]] = None) -> JobScraper:
    """Fresh scraper (re-reads config.py each time).

    When ``overrides`` is given, they are merged over config.py so callers can
    set custom scrape parameters without editing config.py.
    """
    if overrides:
        return JobScraper({**load_config(), **overrides})
    return JobScraper()


def scrape_defaults() -> Dict[str, Any]:
    """The scrape-related subset of config.py, for prefilling the UI."""
    cfg = load_config()
    keys = (
        "sites",
        "search_terms",
        "location",
        "results_wanted",
        "hours_old",
        "country_indeed",
        "linkedin_fetch_description",
        "scrape_cooldown_minutes",
    )
    return {key: cfg[key] for key in keys}


def agent_status() -> Dict[str, Any]:
    """Provider / model / readiness info for the health endpoint."""
    agent = get_agent()
    return {
        "ai_provider": agent.ai_provider,
        "ai_model": agent.ai_model,
        "ai_client_ready": agent._ai_client is not None,
    }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _json_sanitize(value: Any) -> Any:
    """Replace NaN/Infinity (pandas leftovers) with None so output is valid JSON."""
    if isinstance(value, float):
        return None if (math.isnan(value) or math.isinf(value)) else value
    if isinstance(value, dict):
        return {key: _json_sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_sanitize(item) for item in value]
    return value


def _scraped_path() -> Path:
    return _PROJECT_ROOT / load_config().get("scraped_jobs_path", "data/scraped_jobs.json")


def _sanitize_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name)[:120] or "job"


def _job_summary(job: Dict[str, Any]) -> Dict[str, Any]:
    keys = ("id", "site", "title", "company", "location", "job_url", "date_posted")
    return {key: job.get(key) for key in keys if key in job}


def output_dir(run_id: str) -> Path:
    return _OUTPUT_ROOT / _sanitize_filename(run_id)


def resume_path(run_id: str, job_id: str) -> Path:
    return output_dir(run_id) / f"resume_{_sanitize_filename(job_id)}.docx"


def load_latest_jobs() -> List[Dict[str, Any]]:
    """Read the most recent scraped jobs from disk (empty list if none)."""
    path = _scraped_path()
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return _json_sanitize(data) if isinstance(data, list) else []


def _save_scraped(jobs: List[Dict[str, Any]]) -> None:
    """Persist the flat, deduped job list to disk (JSON-safe)."""
    path = _scraped_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(make_json_safe(jobs), handle, ensure_ascii=False, indent=2)


def load_grouped_jobs(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Group the latest scraped jobs by company + exact title for display.

    ``limit`` caps the number of *groups* returned (not postings).
    """
    groups = group_jobs(load_latest_jobs())
    if limit is not None:
        groups = groups[:limit]
    return groups


def find_job_by_id(job_id: str, jobs: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    jobs = jobs if jobs is not None else load_latest_jobs()
    for job in jobs:
        if str(job.get("id")) == str(job_id) or str(job.get("job_url")) == str(job_id):
            return job
    return None


# --------------------------------------------------------------------------- #
# Individual steps
# --------------------------------------------------------------------------- #
def filter_experience(
    jobs: List[Dict[str, Any]],
    min_years: Optional[int] = None,
    max_years: Optional[int] = None,
) -> List[Dict[str, Any]]:
    return get_agent().filter_by_experience_years(jobs, min_years, max_years)


def assess(job: Dict[str, Any], resume_text: str) -> Dict[str, Any]:
    return get_agent().assess_suitability(job, resume_text)


def tailor_to_docx(resume_text: str, job: Dict[str, Any]) -> bytes:
    resume = get_agent().tailor_resume(resume_text, job)
    return build_docx(resume)


# --------------------------------------------------------------------------- #
# Background tasks
# --------------------------------------------------------------------------- #
def run_scrape_task(run_id: str, overrides: Optional[Dict[str, Any]] = None) -> None:
    """Background: scrape (config.py, optionally overridden) and save to JSON."""
    try:
        tasks.update_run(run_id, status="running", progress="scraping", percent=0.0)

        def _on_progress(completed: int, total: int, message: str) -> None:
            percent = round(100.0 * completed / total, 1) if total else None
            tasks.update_run(run_id, progress=message, percent=percent)

        jobs = get_scraper(overrides).scrape_and_save(progress_callback=_on_progress)
        tasks.update_run(
            run_id,
            status="completed",
            progress="done",
            percent=100.0,
            result={
                "count": len(jobs),
                "path": str(_scraped_path()),
                "params": overrides or {},
            },
        )
    except Exception as exc:  # noqa: BLE001 - surface failure via run status
        tasks.update_run(run_id, status="failed", error=str(exc))


def run_full_task(
    run_id: str,
    resume_text: str,
    top_n: int = 10,
    min_score: int = 60,
    do_scrape: bool = False,
) -> None:
    """Background: scrape/load -> experience filter -> suitability -> tailor.

    Chains all four functionalities. Writes tailored resumes and a result.json
    into ``data/output/{run_id}/``.
    """
    try:
        tasks.update_run(run_id, status="running", progress="loading jobs")
        if do_scrape:
            tasks.update_run(run_id, progress="scraping")
            jobs = get_scraper().scrape_and_save()
        else:
            jobs = load_latest_jobs()

        if not jobs:
            tasks.update_run(
                run_id,
                status="completed",
                progress="done",
                result={
                    "jobs_considered": 0,
                    "experience_matched": 0,
                    "tailored": 0,
                    "results": [],
                    "message": "No jobs available. POST /scrape first (or pass scrape=true).",
                },
            )
            return

        agent = get_agent()
        cfg = load_config()
        min_years = cfg.get("experience_min_years", 0)
        max_years = cfg.get("experience_max_years")

        tasks.update_run(run_id, progress=f"experience filter over {len(jobs)} jobs")
        filtered = agent.filter_by_experience_years(jobs, min_years, max_years)

        assessed: List[tuple] = []
        for index, job in enumerate(filtered):
            tasks.update_run(run_id, progress=f"assessing {index + 1}/{len(filtered)}")
            assessed.append((job, agent.assess_suitability(job, resume_text)))

        def _score(pair: tuple) -> float:
            score = pair[1].get("score")
            return float(score) if isinstance(score, (int, float)) else -1.0

        assessed.sort(key=_score, reverse=True)

        out_dir = output_dir(run_id)
        out_dir.mkdir(parents=True, exist_ok=True)

        results: List[Dict[str, Any]] = []
        tailored_count = 0
        for job, suitability in assessed:
            entry: Dict[str, Any] = {
                "job": _job_summary(job),
                "suitability": suitability,
                "resume_file": None,
            }
            score = suitability.get("score")
            if (
                tailored_count < top_n
                and isinstance(score, (int, float))
                and score >= min_score
            ):
                tasks.update_run(
                    run_id, progress=f"tailoring resume for {job.get('title', '')}"
                )
                job_id = _sanitize_filename(
                    str(job.get("id") or job.get("job_url") or tailored_count)
                )
                docx_bytes = tailor_to_docx(resume_text, job)
                (out_dir / f"resume_{job_id}.docx").write_bytes(docx_bytes)
                entry["job_id"] = job_id
                entry["resume_file"] = f"resume_{job_id}.docx"
                entry["resume_download"] = f"/run/{run_id}/resume/{job_id}"
                tailored_count += 1
            results.append(entry)

        result = {
            "jobs_considered": len(jobs),
            "experience_matched": len(filtered),
            "tailored": tailored_count,
            "results": results,
        }
        (out_dir / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tasks.update_run(run_id, status="completed", progress="done", result=result)
    except Exception as exc:  # noqa: BLE001 - surface failure via run status
        tasks.update_run(run_id, status="failed", error=str(exc))


# --------------------------------------------------------------------------- #
# Streaming (NDJSON) generators
# --------------------------------------------------------------------------- #
def _ndjson_line(payload: Dict[str, Any]) -> str:
    """Serialize one event as a flush-sized JSON-safe NDJSON line.

    Padding is insignificant to JSON parsers but prevents browsers and small
    HTTP buffers from holding several streamed events for one combined paint.
    """
    safe = _json_sanitize(make_json_safe(payload))
    return json.dumps(safe, ensure_ascii=False) + (" " * 2048) + "\n"


def stream_scrape(overrides: Optional[Dict[str, Any]] = None):
    """Yield NDJSON events as each search term is scraped.

    Sync generator (Starlette threadpools it) so the blocking per-term scrape
    doesn't block the event loop. Duplicate postings (same company + title) are
    grouped incrementally; each ``term`` event carries the created-or-updated
    group deltas. The final flat, deduped list is persisted to disk so a later
    "Load jobs"/filter still works.

    Events: ``start`` -> ``term`` (xN) -> ``done``; a fatal failure emits
    ``error`` instead of ``done``.
    """
    from pipeline.utils import JobGrouper

    try:
        scraper = get_scraper(overrides)
        total = len(scraper.config.get("search_terms", []))
        grouper = JobGrouper()
        yield _ndjson_line({"type": "start", "total": total})

        for event in scraper.scrape_iter():
            deltas = grouper.add_jobs(event["jobs"])
            index = event["index"]
            ev_total = event["total"] or total
            percent = round(100.0 * (index + 1) / ev_total, 1) if ev_total else 100.0
            yield _ndjson_line(
                {
                    "type": "term",
                    "term": event["term"],
                    "index": index,
                    "total": ev_total,
                    "percent": percent,
                    "term_job_count": len(event["jobs"]),
                    "error": event["error"],
                    "groups": deltas,
                }
            )

        _save_scraped(grouper.flat_annotated())
        yield _ndjson_line(
            {
                "type": "done",
                "total_groups": grouper.num_groups(),
                "total_jobs": grouper.num_jobs(),
            }
        )
    except Exception as exc:  # noqa: BLE001 - report as a stream event, not a 500
        yield _ndjson_line({"type": "error", "message": str(exc)})


def stream_filter_experience(
    jobs: Optional[List[Dict[str, Any]]] = None,
    min_years: Optional[int] = None,
    max_years: Optional[int] = None,
):
    """Yield NDJSON events after bounded concurrent per-posting evaluations.

    Each posting is tagged ``selected`` (its required-years range overlaps the
    target window) or not. Jobs whose requirement can't be estimated are
    ``selected=False`` with ``required_years=null`` ("experience unknown"). The
    window defaults to config.py when the request sets neither bound.

    Events: ``start`` -> ``job`` (xN) -> ``done``; a fatal failure (e.g. no AI
    client) emits ``error``.
    """
    try:
        agent = get_agent()
        if jobs is None:
            jobs = load_latest_jobs()
        if min_years is None and max_years is None:
            cfg = load_config()
            min_years = cfg.get("experience_min_years", 0)
            max_years = cfg.get("experience_max_years")
        else:
            min_years = min_years if min_years is not None else 0

        agent._require_client()  # fail fast with a clear message if unconfigured
        total = len(jobs)
        yield _ndjson_line(
            {
                "type": "start",
                "total": total,
                "min_years": min_years,
                "max_years": max_years,
            }
        )

        selected_count = 0
        not_selected_count = 0
        estimates = agent.estimate_required_years_parallel(jobs)
        if not isinstance(estimates, list):
            estimates = [agent._estimate_required_years(job) for job in jobs]
        for index, (job, required) in enumerate(zip(jobs, estimates)):
            matched = agent.experience_matches(required, min_years, max_years)
            if matched:
                selected_count += 1
            else:
                not_selected_count += 1
            annotated = dict(job)
            annotated["required_years"] = required
            percent = round(100.0 * (index + 1) / total, 1) if total else 100.0
            yield _ndjson_line(
                {
                    "type": "job",
                    "index": index,
                    "total": total,
                    "percent": percent,
                    "selected": matched,
                    "required_years": required,
                    "job": annotated,
                }
            )

        yield _ndjson_line(
            {
                "type": "done",
                "total": total,
                "selected_count": selected_count,
                "not_selected_count": not_selected_count,
            }
        )
    except Exception as exc:  # noqa: BLE001 - report as a stream event, not a 500
        yield _ndjson_line({"type": "error", "message": str(exc)})


def stream_screen_jobs(
    resume_text: str,
    jobs: Optional[List[Dict[str, Any]]] = None,
    min_years: Optional[int] = None,
    max_years: Optional[int] = None,
):
    """Yield NDJSON events as each posting is screened one-by-one.

    Combines the experience filter and the suitability assessment into a single
    LLM call per posting (:meth:`AIJobAgent.screen_job`): each call BOTH
    estimates the job's required experience AND scores the resume against it.
    ``match`` is the deterministic overlap of the required-years estimate with
    the target ``[min_years, max_years]`` window; the window defaults to
    config.py when the request sets neither bound. Each ``job`` payload also
    carries ``score`` / ``verdict`` / ``matched_skills`` / ``missing_skills`` /
    ``reasoning`` so the frontend can show the fit alongside the match verdict.

    Events: ``start`` -> ``job`` (xN) -> ``done``; a fatal failure (e.g. no AI
    client) emits ``error``.
    """
    try:
        agent = get_agent()
        if jobs is None:
            jobs = load_latest_jobs()
        if min_years is None and max_years is None:
            cfg = load_config()
            min_years = cfg.get("experience_min_years", 0)
            max_years = cfg.get("experience_max_years")
        else:
            min_years = min_years if min_years is not None else 0

        agent._require_client()  # fail fast with a clear message if unconfigured
        total = len(jobs)
        yield _ndjson_line(
            {
                "type": "start",
                "total": total,
                "min_years": min_years,
                "max_years": max_years,
            }
        )

        match_count = 0
        no_match_count = 0
        completed = 0
        try:
            results = agent.screen_jobs_parallel_stream(
                jobs, resume_text, min_years, max_years
            )
            for index, job, result in results:
                completed += 1
                matched = bool(result.get("experience_match"))
                if matched:
                    match_count += 1
                else:
                    no_match_count += 1
                annotated = dict(job)
                annotated["required_years"] = result.get("required_years")
                annotated["experience_match"] = matched
                annotated["score"] = result.get("score")
                annotated["verdict"] = result.get("verdict")
                annotated["matched_skills"] = result.get("matched_skills") or []
                annotated["missing_skills"] = result.get("missing_skills") or []
                annotated["reasoning"] = result.get("reasoning") or ""
                percent = round(100.0 * completed / total, 1) if total else 100.0
                yield _ndjson_line(
                    {
                        "type": "job",
                        "index": index,
                        "total": total,
                        "percent": percent,
                        "match": matched,
                        "job": annotated,
                    }
                )
        except (AttributeError, TypeError):
            # Keep lightweight legacy test doubles compatible with streaming.
            for index, job in enumerate(jobs):
                result = agent.screen_job(job, resume_text, min_years, max_years)
                completed += 1
                matched = bool(result.get("experience_match"))
                if matched:
                    match_count += 1
                else:
                    no_match_count += 1
                annotated = dict(job)
                annotated["required_years"] = result.get("required_years")
                annotated["experience_match"] = matched
                annotated["score"] = result.get("score")
                annotated["verdict"] = result.get("verdict")
                annotated["matched_skills"] = result.get("matched_skills") or []
                annotated["missing_skills"] = result.get("missing_skills") or []
                annotated["reasoning"] = result.get("reasoning") or ""
                percent = round(100.0 * completed / total, 1) if total else 100.0
                yield _ndjson_line(
                    {
                        "type": "job",
                        "index": index,
                        "total": total,
                        "percent": percent,
                        "match": matched,
                        "job": annotated,
                    }
                )

        yield _ndjson_line(
            {
                "type": "done",
                "total": total,
                "match_count": match_count,
                "no_match_count": no_match_count,
            }
        )
    except Exception as exc:  # noqa: BLE001 - report as a stream event, not a 500
        yield _ndjson_line({"type": "error", "message": str(exc)})
