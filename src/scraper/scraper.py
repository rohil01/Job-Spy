"""
Job scraper module using jobsniffer for scraping job postings.

Exposes two low-level functions (``scrape_jobs_from_sites`` /
``scrape_jobs_simple``) and a high-level ``JobScraper`` class that is driven by
the project ``config.py`` and saves its results to JSON.
"""

import json
import importlib.util
from pathlib import Path
from typing import List, Union, Optional, Dict, Any

import pandas as pd

try:
    from jobsniffer import scrape_jobs
    JOBSNIFFER_AVAILABLE = True
except ImportError:
    JOBSNIFFER_AVAILABLE = False
    scrape_jobs = None


def scrape_jobs_from_sites(
    site_name: Union[str, List[str]],
    search_term: str,
    location: str,
    results_wanted: int = 15,
    hours_old: int = 72,
    country_indeed: str = 'usa',
    linkedin_fetch_description: bool = False,
    proxies: Optional[List[str]] = None,
    distance: int = 50,
    is_remote: bool = False,
    easy_apply: bool = False,
    description_format: str = "markdown",
    google_search_term: Optional[str] = None,
    employment_type: Optional[str] = None,
) -> pd.DataFrame:
    """
    Scrape job postings from specified job boards using jobsniffer.

    Args:
        site_name: Single site name or list of site names to scrape from.
                  Supported sites: "linkedin", "indeed", "glassdoor", "google", "ziprecruiter", "bayt", "naukri", "bdjobs"
        search_term: Job title or keyword to search for (e.g., "software engineer", "AI Developer")
        location: Location to search in (e.g., "Bengaluru", "Remote", "New York, NY")
        results_wanted: Number of job results to retrieve per site (default: 15)
        hours_old: Only return jobs posted within this many hours (default: 72)
        country_indeed: Country for Indeed searches (default: "usa")
        linkedin_fetch_description: Whether to fetch full job description for LinkedIn (slower but more detailed)
        proxies: List of proxy servers to use for avoiding blocks (e.g., ["http://ip:port", "http://ip:port"])
        distance: Radius from location to search in miles/km (default: 50)
        is_remote: Whether to search for remote positions only
        easy_apply: Whether to filter for easy apply jobs (LinkedIn only)
        description_format: Format of job description ("markdown" or "html")
        google_search_term: Custom search term for Google jobs (overrides search_term if provided)
        employment_type: Type of employment for Glassdoor jobs (OVERSEAS, CONTRACT, PERMANENT, INTERN)

    Returns:
        pandas.DataFrame containing job postings with columns like:
        - id, site, title, company, location, date_posted, job_type, salary_source,
          interval, min_amount, max_amount, currency, is_remote, url, description,
          company_url, company_logo, company_num_employees, company_revenue,
          company_description, skills, experience_level, etc.

    Raises:
        ImportError: If jobsniffer is not installed

    Example:
        >>> jobs = scrape_jobs_from_sites(
        ...     site_name=["indeed", "linkedin"],
        ...     search_term="AI Developer",
        ...     location="Bengaluru",
        ...     results_wanted=10
        ... )
        >>> print(f"Found {len(jobs)} jobs")
        >>> print(jobs[['title', 'company', 'location']].head())
    """
    if not JOBSNIFFER_AVAILABLE:
        raise ImportError(
            "jobsniffer is not installed. "
            "Please install it using: pip install jobsniffer"
        )

    # Prepare kwargs for the scrape_jobs function
    kwargs = {
        "site_name": site_name,
        "search_term": search_term,
        "location": location,
        "results_wanted": results_wanted,
        "hours_old": hours_old,
        "country_indeed": country_indeed,
        "linkedin_fetch_description": linkedin_fetch_description,
        "proxies": proxies,
        "distance": distance,
        "is_remote": is_remote,
        "easy_apply": easy_apply,
        "description_format": description_format,
    }

    # Add optional parameters if provided
    if google_search_term is not None:
        kwargs["google_search_term"] = google_search_term
    if employment_type is not None:
        kwargs["employment_type"] = employment_type

    # Call jobsniffer.scrape_jobs
    jobs_df = scrape_jobs(**kwargs)

    return jobs_df


def scrape_jobs_simple(
    site_name: List[str],
    search_term: str,
    location: str,
    results_wanted: int = 10
) -> pd.DataFrame:
    """
    Simple interface for scraping jobs with minimal parameters.

    Args:
        site_name: List of site names to scrape from
        search_term: Job title or keyword to search for
        location: Location to search in
        results_wanted: Number of results wanted per site

    Returns:
        pandas.DataFrame with job postings
    """
    return scrape_jobs_from_sites(
        site_name=site_name,
        search_term=search_term,
        location=location,
        results_wanted=results_wanted,
        hours_old=24,  # Recent jobs only
        linkedin_fetch_description=True,  # Get full details
    )


def _load_project_config() -> Dict[str, Any]:
    """Load settings from the root ``config.py`` via ``load_config()``.

    Uses importlib directly so it works regardless of how the package was
    imported (``scraper.scraper`` or ``src.scraper.scraper``).
    """
    project_root = Path(__file__).resolve().parents[2]
    config_path = project_root / "config.py"
    spec = importlib.util.spec_from_file_location("jobspy_config", config_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"Could not load config from {config_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load_config()


class JobScraper:
    """Config-driven job scraper.

    Reads settings from the root ``config.py`` (or an override dict passed to
    the constructor), scrapes every configured search term across every
    configured site, deduplicates the merged results, and can save them to
    JSON. This is the entry point used by the pipeline and the FastAPI backend.

    Example:
        >>> scraper = JobScraper()
        >>> jobs = scraper.scrape_and_save()
        >>> print(len(jobs))
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config if config is not None else _load_project_config()
        # Lazy imports keep the module importable even without the src path set.
        from pipeline.utils import setup_logger
        self.logger = setup_logger("scraper")

    def scrape(self, progress_callback=None) -> List[Dict[str, Any]]:
        """Scrape all configured terms/sites and return deduplicated jobs.

        ``progress_callback(completed, total, message)`` (optional) is called as
        each search term is processed so callers can render a progress bar.
        """
        from pipeline.utils import cooldown_sleep, deduplicate_jobs

        sites = self.config.get("sites", [])
        search_terms = self.config.get("search_terms", [])
        location = self.config.get("location", "")
        cooldown_minutes = self.config.get("scrape_cooldown_minutes", 0)

        # Only forward parameters that jobsniffer actually accepts.
        scraper_params = {
            "results_wanted": self.config.get("results_wanted", 15),
            "hours_old": self.config.get("hours_old", 72),
            "country_indeed": self.config.get("country_indeed", "usa"),
            "linkedin_fetch_description": self.config.get(
                "linkedin_fetch_description", False
            ),
        }

        total = len(search_terms)

        def _report(completed: int, message: str) -> None:
            if progress_callback is not None:
                progress_callback(completed, total, message)

        all_jobs: List[Dict[str, Any]] = []
        for index, term in enumerate(search_terms):
            _report(index, f"Scraping '{term}' ({index + 1}/{total})")
            self.logger.info(f"Scraping '{term}' across {sites}")
            try:
                df = scrape_jobs_from_sites(
                    site_name=sites,
                    search_term=term,
                    location=location,
                    **scraper_params,
                )
                if df is not None and not df.empty:
                    jobs = df.to_dict("records")
                    self.logger.info(f"Retrieved {len(jobs)} jobs for '{term}'")
                    all_jobs.extend(jobs)
                    _report(index + 1, f"Found {len(jobs)} jobs for '{term}' ({index + 1}/{total})")
                else:
                    self.logger.warning(f"No jobs returned for '{term}'")
                    _report(index + 1, f"No jobs for '{term}' ({index + 1}/{total})")
            except Exception as exc:  # noqa: BLE001 - log and continue other terms
                self.logger.error(f"Error scraping '{term}': {exc}", exc_info=True)
                _report(index + 1, f"Error on '{term}' ({index + 1}/{total})")

            # Cooldown between terms (never after the last one).
            if cooldown_minutes and index < total - 1:
                _report(index + 1, f"Cooling down {cooldown_minutes:g} min before next term…")
                cooldown_sleep(cooldown_minutes, self.logger)

        unique_jobs = deduplicate_jobs(all_jobs)
        self.logger.info(
            f"{len(all_jobs)} jobs scraped -> {len(unique_jobs)} after dedup"
        )
        return unique_jobs

    def scrape_and_save(
        self, output_path: Optional[Union[str, Path]] = None, progress_callback=None
    ) -> List[Dict[str, Any]]:
        """Scrape jobs and write them to ``output_path`` (or the config path)."""
        from pipeline.utils import make_json_safe

        jobs = self.scrape(progress_callback=progress_callback)
        path = Path(output_path) if output_path else self._default_output_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as output_file:
            json.dump(make_json_safe(jobs), output_file, ensure_ascii=False, indent=2)
        self.logger.info(f"Saved {len(jobs)} jobs to {path}")
        return jobs

    def _default_output_path(self) -> Path:
        project_root = Path(__file__).resolve().parents[2]
        return project_root / self.config.get(
            "scraped_jobs_path", "data/scraped_jobs.json"
        )


# For backward compatibility or direct export
__all__ = ["scrape_jobs_from_sites", "scrape_jobs_simple", "JobScraper"]


if __name__ == "__main__":
    # Example usage when run directly
    import sys

    if len(sys.argv) < 4:
        print("Usage: python scraper.py <site_name> <search_term> <location> [results_wanted]")
        print("Example: python scraper.py indeed \"AI Developer\" Bengaluru 10")
        sys.exit(1)

    site = sys.argv[1]
    term = sys.argv[2]
    loc = sys.argv[3]
    count = int(sys.argv[4]) if len(sys.argv) > 4 else 10

    try:
        jobs = scrape_jobs_simple(
            site_name=[site],
            search_term=term,
            location=loc,
            results_wanted=count
        )
        print(f"Found {len(jobs)} jobs:")
        if len(jobs) > 0:
            print(jobs[['title', 'company', 'location', 'date_posted']].to_string(index=False))
        else:
            print("No jobs found.")
    except Exception as e:
        print(f"Error scraping jobs: {e}")
        sys.exit(1)