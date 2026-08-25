"""Run the complete job scraping and AI filtering pipeline."""

import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pipeline.ai_filter_step import run_ai_filter
from pipeline.scraper_runner import scrape_pipeline


def main() -> None:
    """Scrape jobs, filter them with AI, and write both result files."""
    config_path = PROJECT_ROOT / "src" / "pipeline" / "config.yaml"
    with config_path.open("r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}

    jobs = scrape_pipeline()
    output_path = PROJECT_ROOT / config.get(
        "ai_output_json_path", "data/filtered_jobs.json"
    )
    run_ai_filter(
        jobs,
        config.get("experience_levels", []),
        output_path,
    )


if __name__ == "__main__":
    main()
