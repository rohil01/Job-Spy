# JobSpy

JobSpy scrapes fresh job postings from multiple boards, then uses LLM "agents"
to filter them by required experience, score your resume against each role, and
rewrite your resume for the best fits — all driven by a FastAPI backend and a
small React UI.

## How it works

```
                ┌──────────────┐        ┌───────────────────────────────────┐
 search terms ──▶│   Scraper    │──jobs──▶│ Agent 1 · Experience filter       │
 (config.py)    │ (jobsniffer) │  JSON   │ keep jobs whose required years    │
                └──────────────┘         │ overlap your target window        │
                                         └───────────────┬───────────────────┘
                    ┌──────────────┐                     ▼
 resume (.docx) ───▶│ Agent 2 · Suitability │──scores──▶┌──────────────────────┐
                    │ score resume vs job   │           │ Agent 3 · Tailoring  │
                    └───────────────────────┘           │ rewrite resume .docx │
                                                        └──────────────────────┘
```

- **Scraper** (`src/scraper/`) — runs one pass per search term over the configured
  job boards via the jobsniffer library,
  merges, deduplicates, and writes `data/scraped_jobs.json`.
  Supported boards include linkedin, indeed, glassdoor, google, ziprecruiter,
  bayt, naukri, and bdjobs.
- **Agent 1 — Experience filter** (`src/pipeline/ai_filter_step.py`,
  `src/Agent/ai_job_agent.py`) — keeps jobs whose estimated required years of
  experience overlap `[min_years, max_years]`. Writes `data/filtered_jobs.json`.
- **Agent 2 — Suitability** — scores how well a resume fits a specific job.
- **Agent 3 — Tailoring** — rewrites a resume for a specific job and returns an
  updated `.docx`.

All three agents share one OpenAI-compatible chat model — NVIDIA NIM by default
(`meta/llama-3.3-70b-instruct`) reached through the `openai` client,
or OpenAI itself. Prompts live in `src/Agent/Prompt/v1.yaml`.

## Project layout

```
config.py                  single source of truth for all settings (no secrets)
main.py                    CLI entry point: scrape -> experience filter
run_api.py                 launch the FastAPI backend
src/
├── scraper/               jobsniffer wrapper
├── pipeline/              scrape stage, AI filter stage, shared utils
├── Agent/                 AIJobAgent (agents 1–3) + .docx resume I/O
│   └── Prompt/v1.yaml     agent prompts
└── api/                   FastAPI app, routes, schemas, background-run tracking
frontend/                  React (Vite) UI — see frontend/README.md
tests/                     pytest suite (unit + integration)
scripts/run_code_review.py lint / format / type / security checks locally
data/                      scraped_jobs.json, filtered_jobs.json (generated)
```

## Requirements

- Python 3.9+
- Node.js 18+ and npm (frontend only)
- An API key for the LLM provider (NVIDIA by default) — only needed for the
  agent steps; browsing scraped jobs works without one

## Backend setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install the package (add [dev] for test/lint tooling)
pip install -e ".[dev]"

# 3. Configure secrets
cp .env.example .env               # Windows: copy .env.example .env
# then edit .env and set NVIDIA_API_KEY=... (or OPENAI_API_KEY if you switch providers)
```

### Run as an HTTP API

```bash
python run_api.py            # http://127.0.0.1:8000
python run_api.py --reload   # dev auto-reload
```

Interactive docs (Swagger UI): <http://127.0.0.1:8000/docs>

#### Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness + whether the AI client is configured |
| POST | `/scrape` | Start a background scrape; body fields override `config.py` |
| GET | `/scrape/{run_id}` | Poll a scrape run |
| GET | `/config/scrape` | Default scrape parameters (for UI prefill) |
| GET | `/jobs` | Latest scraped jobs from disk |
| POST | `/filter/experience` | Agent 1: keep jobs matching a min–max years window |
| POST | `/suitability` | Agent 2: score a resume against one job (multipart: resume `.docx` + `job_id` or `job` JSON) |
| POST | `/tailor-resume` | Agent 3: rewrite a resume for a job, returns `.docx` |
| POST | `/run` | Full chain (background): scrape/load → filter → suitability → tailor |
| GET | `/run/{run_id}` | Poll a full run |
| GET | `/run/{run_id}/resume/{job_id}` | Download a tailored resume |

Resumes must be `.docx` files (parsed with `python-docx`). Background endpoints
return a `run_id` that you poll for status/results.

## Frontend setup

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The UI expects the backend on
`http://127.0.0.1:8000` — set `VITE_API_BASE` in `frontend/.env` to point
elsewhere. Tabs:

- **Jobs** — browse the latest scrape or kick off a new one with custom filters.
- **Filtered** — apply the experience-window filter (one LLM call per job).
- **Resume** — upload a `.docx`, assess suitability against a chosen job, or
  rewrite and download a tailored resume.

See [`frontend/README.md`](frontend/README.md) for details.

## Configuration

All settings live in [`config.py`](config.py) — edit it directly. Secrets stay
in `.env` (see [`.env.example`](.env.example)); never commit `.env`.

| Setting (config.py) | Default | Meaning |
| --- | --- | --- |
| `SITES` | `["linkedin", "indeed"]` | Job boards to scrape |
| `SEARCH_TERMS` | 5 AI/engineering roles | One scrape pass per term, merged + deduplicated |
| `LOCATION` | `"Bengaluru"` | Search location |
| `RESULTS_WANTED` | `5` | Results per site, per search term |
| `HOURS_OLD` | `6` | Only jobs posted within this many hours |
| `COUNTRY_INDEED` | `"india"` | Country context for Indeed |
| `LINKEDIN_FETCH_DESCRIPTION` | `True` | Fetch full descriptions (richer, slower) |
| `SCRAPE_COOLDOWN_MINUTES` | `0.5` | Cooldown between search terms in minutes; accepts decimals (`0.5` = 30s), `0` disables |
| `EXPERIENCE_MIN_YEARS` / `EXPERIENCE_MAX_YEARS` | `0` / `3` | Target experience window; `None` = open-ended "min and up" |
| `AI_PROVIDER` | `"nvidia"` | `"nvidia"` or `"openai"` |
| `AI_MODEL` | `meta/llama-3.3-70b-instruct` | Chat model used by all agents |
| `AI_BASE_URL` | NVIDIA integrate endpoint | Override to point at any OpenAI-compatible API |

Environment variables: `NVIDIA_API_KEY` (default provider), or
`OPENAI_API_KEY` when `AI_PROVIDER = "openai"`. Optional LinkedIn credentials
can be set for authenticated scrapes.

## Testing & code quality

```bash
pytest tests/                       # full suite (unit + integration)
pytest tests/unit -m unit           # unit tests only
pytest --cov=src tests/             # with coverage

pre-commit run --all-files          # black, flake8, mypy, bandit
python scripts/run_code_review.py   # same checks as CI, locally
```

CI (`.github/workflows/code-review.yml`) runs black, flake8, mypy, bandit, and
the pytest suite with coverage on Python 3.9–3.11.

## License

MIT — see [pyproject.toml](pyproject.toml).
