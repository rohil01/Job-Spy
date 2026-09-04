"""
Single source of truth for the JobSpy project.

Holds all scraper, experience-filter, and AI-agent settings as plain Python
values. Everything in the pipeline and the FastAPI backend is driven by the
constants defined here (see ``load_config``).

Secrets (API keys) are NOT stored here — they are read from the ``.env`` file
at the project root (see ``.env.example``). ``AI_API_KEY`` below stays ``None``
so the agent falls back to the ``NVIDIA_API_KEY`` environment variable.
"""

from pathlib import Path
from typing import Any, Dict, List

# --------------------------------------------------------------------------- #
# Scraper settings
# --------------------------------------------------------------------------- #
# Job boards to scrape. Supported by jobsniffer: linkedin, indeed, glassdoor,
# google, ziprecruiter, bayt, naukri, bdjobs.
SITES: List[str] = ["linkedin", "indeed"]

# One scrape pass is run per search term; results are merged and deduplicated.
SEARCH_TERMS: List[str] = [
    "AI Engineer",
    "Agentic AI Engineer",
    "Software Engineer",
    "Applied AI Engineer",
    "Backend Engineer",
]

LOCATION: str = "Bengaluru"
RESULTS_WANTED: int = 5          # per site, per search term
HOURS_OLD: int = 6               # only jobs posted within this many hours
COUNTRY_INDEED: str = "india"    # country context for Indeed searches
LINKEDIN_FETCH_DESCRIPTION: bool = True  # richer data, but slower

# Cooldown (minutes) between search terms, to look less bot-like. Accepts
# fractional minutes: 0.5 = 30 seconds. Set to 0 to disable. Users can override
# this per-run from the UI (Scrape filters).
SCRAPE_COOLDOWN_MINUTES: float = 0.5

# Where the scraper writes its results (relative to the project root).
SCRAPED_JOBS_PATH: str = "data/scraped_jobs.json"

# --------------------------------------------------------------------------- #
# Experience filter (Agent 1)
# --------------------------------------------------------------------------- #
# The candidate's target experience window, in years. Jobs whose estimated
# required experience does not overlap ``[EXPERIENCE_MIN_YEARS,
# EXPERIENCE_MAX_YEARS]`` are dropped by ``filter_by_experience_years``. Set
# EXPERIENCE_MAX_YEARS to None for an open-ended "min and up" window.
EXPERIENCE_MIN_YEARS: int = 0
EXPERIENCE_MAX_YEARS: int = 3

# --------------------------------------------------------------------------- #
# AI configuration (Agents 1-3)
# --------------------------------------------------------------------------- #
# Provider is one of: "nvidia", "openai". NVIDIA is OpenAI-API compatible and
# is reached through the openai client with a custom base_url.
AI_PROVIDER: str = "nvidia"
# NOTE: nvidia/llama-3.1-nemotron-70b-instruct still appears in the NVIDIA
# catalog but its inference function has been decommissioned — invoking it
# returns HTTP 404 "Function ... not found for account". Use a model that is
# actually served. meta/llama-3.3-70b-instruct is a confirmed-working drop-in.
AI_MODEL: str = "nvidia/nemotron-3-super-120b-a12b"
AI_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

# API key is loaded from .env (NVIDIA_API_KEY). Leave as None here.
AI_API_KEY = None

# Project root (this file lives at the root).
PROJECT_ROOT = Path(__file__).resolve().parent


def load_config() -> Dict[str, Any]:
    """Return all settings as a single dict.

    This is the accessor used by the scraper, agent, and API so that callers
    do not have to import individual module-level constants.
    """
    return {
        # scraper
        "sites": SITES,
        "search_terms": SEARCH_TERMS,
        "location": LOCATION,
        "results_wanted": RESULTS_WANTED,
        "hours_old": HOURS_OLD,
        "country_indeed": COUNTRY_INDEED,
        "linkedin_fetch_description": LINKEDIN_FETCH_DESCRIPTION,
        "scrape_cooldown_minutes": SCRAPE_COOLDOWN_MINUTES,
        "scraped_jobs_path": SCRAPED_JOBS_PATH,
        # experience filter
        "experience_min_years": EXPERIENCE_MIN_YEARS,
        "experience_max_years": EXPERIENCE_MAX_YEARS,
        # ai
        "ai_provider": AI_PROVIDER,
        "ai_model": AI_MODEL,
        "ai_base_url": AI_BASE_URL,
        "api_key": AI_API_KEY,
    }
