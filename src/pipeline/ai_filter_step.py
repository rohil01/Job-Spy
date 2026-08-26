"""AI filtering stage for scraped jobs."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from Agent.ai_job_agent import AIJobAgent
from .utils import make_json_safe


def run_ai_filter(
    jobs: List[Dict[str, Any]],
    min_years: Optional[int],
    max_years: Optional[int],
    output_path: Union[str, Path],
    agent: Optional[AIJobAgent] = None,
) -> List[Dict[str, Any]]:
    """Filter jobs by required experience window and save the result as JSON."""
    agent = agent or AIJobAgent()
    filtered_jobs = agent.filter_by_experience_years(jobs, min_years, max_years)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(make_json_safe(filtered_jobs), output_file, ensure_ascii=False, indent=2)

    return filtered_jobs
