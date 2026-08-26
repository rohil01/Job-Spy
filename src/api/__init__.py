"""FastAPI backend package for JobSpy.

Importing this package ensures both the project root and ``src`` are on
``sys.path`` so intra-project imports (``config``, ``scraper.scraper``,
``Agent.ai_job_agent``, ``pipeline.utils``) resolve regardless of how the app
was launched (``run_api.py`` or ``uvicorn src.api.app:app``).
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _path in (_ROOT, _ROOT / "src"):
    _path_str = str(_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)
