"""Run the complete job scraping + AI experience-filter pipeline (CLI path).

For the HTTP API, use ``run_api.py`` instead.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import config  # noqa: E402
from pipeline.ai_filter_step import run_ai_filter  # noqa: E402
from pipeline.scraper_runner import scrape_pipeline  # noqa: E402


def main() -> None:
    """Scrape jobs (per config.py), filter by experience, write both JSON files."""
    settings = config.load_config()

    jobs = scrape_pipeline()

    output_path = PROJECT_ROOT / "data" / "filtered_jobs.json"
    run_ai_filter(
        jobs,
        settings.get("experience_min_years", 0),
        settings.get("experience_max_years"),
        output_path,
    )


if __name__ == "__main__":
    main()
