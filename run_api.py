"""Launch the JobSpy FastAPI backend.

Usage:
    python run_api.py            # serve on http://127.0.0.1:8000
    python run_api.py --reload   # dev auto-reload

Swagger UI is available at http://127.0.0.1:8000/docs
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
for _path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import uvicorn  # noqa: E402  (import after sys.path setup)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the JobSpy API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="auto-reload (dev)")
    args = parser.parse_args()

    uvicorn.run(
        "src.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
