"""Pydantic request/response models for the JobSpy API."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    ai_client_ready: bool = False


class RunAccepted(BaseModel):
    run_id: str
    status: str = "pending"


class RunStatus(BaseModel):
    run_id: str
    status: str  # pending | running | completed | failed
    progress: Optional[str] = None
    percent: Optional[float] = None  # 0-100 completion, when known
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class JobsResponse(BaseModel):
    count: int
    jobs: List[Dict[str, Any]]


class JobGroup(BaseModel):
    """A set of duplicate postings for the same company + exact role title."""

    group_id: str
    company: str
    title: str
    count: int
    postings: List[Dict[str, Any]]


class GroupedJobsResponse(BaseModel):
    count: int  # number of groups
    groups: List[JobGroup]


class ExperienceFilterRequest(BaseModel):
    jobs: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Jobs to filter. Defaults to the latest scraped jobs on disk.",
    )
    min_years: Optional[int] = Field(
        default=None,
        ge=0,
        description="Minimum years of experience to target. Defaults to config.py.",
    )
    max_years: Optional[int] = Field(
        default=None,
        ge=0,
        description="Maximum years to target; null (with a min set) means open-ended.",
    )


class ExperienceFilterResponse(BaseModel):
    input_count: int
    filtered_count: int
    min_years: int
    max_years: Optional[int] = None
    jobs: List[Dict[str, Any]]


class SuitabilityResponse(BaseModel):
    job: Dict[str, Any]
    score: Optional[int] = None
    verdict: str = "unknown"
    experience_match: Optional[bool] = None
    matched_skills: List[str] = []
    missing_skills: List[str] = []
    reasoning: str = ""


class ScrapeRequest(BaseModel):
    """Optional overrides for a scrape run. Omitted fields fall back to config.py."""

    sites: Optional[List[str]] = Field(
        default=None, description="Job boards to scrape (linkedin, indeed, glassdoor, …)."
    )
    search_terms: Optional[List[str]] = Field(
        default=None, description="One scrape pass is run per term; results are merged."
    )
    location: Optional[str] = Field(default=None, description="Location to search in.")
    results_wanted: Optional[int] = Field(
        default=None, ge=1, description="Results per site, per search term."
    )
    hours_old: Optional[int] = Field(
        default=None, ge=1, description="Only jobs posted within this many hours."
    )
    country_indeed: Optional[str] = Field(
        default=None, description="Country context for Indeed searches."
    )
    linkedin_fetch_description: Optional[bool] = Field(
        default=None, description="Fetch full LinkedIn descriptions (richer but slower)."
    )
    scrape_cooldown_minutes: Optional[float] = Field(
        default=None,
        ge=0,
        description="Cooldown between search terms, in minutes (0.5 = 30s; 0 disables).",
    )


class ScrapeConfigResponse(BaseModel):
    """The scrape-related defaults from config.py, for prefilling the UI."""

    sites: List[str]
    search_terms: List[str]
    location: str
    results_wanted: int
    hours_old: int
    country_indeed: str
    linkedin_fetch_description: bool
    scrape_cooldown_minutes: float
