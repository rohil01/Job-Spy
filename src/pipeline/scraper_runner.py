import yaml
import json
from pathlib import Path

from .utils import setup_logger, random_backoff, deduplicate_jobs, make_json_safe

def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def scrape_pipeline():
    from scraper.scraper import scrape_jobs_from_sites

    # Paths: base_dir is the src/pipeline directory
    base_dir = Path(__file__).resolve().parent
    config_file = base_dir / "config.yaml"
    config = load_config(config_file)

    # Setup
    logger = setup_logger()
    logger.info("Starting job scraper pipeline")

    search_terms: list[str] = config.get("search_terms", config.get("search_term", []))
    sites: list[str] = config.get("sites", config.get("site_name", []))
    location: str = config.get("location", "Bengaluru")
    backoff_min = config.get("backoff_min_minutes", 1)
    backoff_max = config.get("backoff_max_minutes", 2)
    # output_json_path is relative to project root (two levels up from src/pipeline)
    output_path = base_dir.parent.parent / config.get("output_json_path", "data/scraped_jobs.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Scraper parameters (everything except search_term and proxies)
    scraper_params = {
        k: v for k, v in config.items()
        if k not in {
            "search_terms", "search_term", "sites", "site_name", "backoff_min_minutes",
            "backoff_max_minutes", "output_json_path", "ai_output_json_path",
            "experience_levels", "location"
        }
    }

    all_jobs: list[dict] = []

    for term in search_terms:
        logger.info(f"Processing search term: '{term}'")
        try:
            # Call the scraper function from scraper.scraper
            df = scrape_jobs_from_sites(
                site_name=sites,
                search_term=term,
                location=location,
                **scraper_params
                # proxies can be added here if configured elsewhere
            )
            # Convert DataFrame to list of dicts
            if df is not None and not df.empty:
                jobs = df.to_dict('records')
                logger.info(f"Retrieved {len(jobs)} jobs for term '{term}'")
                all_jobs.extend(jobs)
            else:
                logger.warning(f"No jobs returned for term '{term}'")
        except Exception as e:
            logger.error(f"Error while scraping term '{term}': {e}", exc_info=True)

        # Backoff before next term (except after the last term)
        if term != search_terms[-1]:
            random_backoff(backoff_min, backoff_max, logger)

    # Deduplicate
    logger.info(f"Total jobs before deduplication: {len(all_jobs)}")
    unique_jobs = deduplicate_jobs(all_jobs)
    logger.info(f"Total jobs after deduplication: {len(unique_jobs)}")

    # Save to JSON
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(make_json_safe(unique_jobs), f, ensure_ascii=False, indent=2)
    logger.info(f"Results saved to {output_path}")
    return unique_jobs


def main():
    scrape_pipeline()

if __name__ == "__main__":
    main()