"""Scraper stage of the pipeline.

Thin wrapper around ``JobScraper`` (see ``scraper/scraper.py``) so the CLI
pipeline and tests keep a stable ``scrape_pipeline()`` entry point. All settings
come from the root ``config.py``.
"""

from typing import Any, Dict, List


def scrape_pipeline() -> List[Dict[str, Any]]:
    """Scrape all configured jobs, save them to JSON, and return them."""
    from scraper.scraper import JobScraper

    return JobScraper().scrape_and_save()


def main() -> None:
    scrape_pipeline()


if __name__ == "__main__":
    main()
