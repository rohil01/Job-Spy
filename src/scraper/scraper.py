"""
Job scraper module using jobsniffer for scraping job postings.
"""

from typing import List, Union, Optional
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


# For backward compatibility or direct export
__all__ = ["scrape_jobs_from_sites", "scrape_jobs_simple"]


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