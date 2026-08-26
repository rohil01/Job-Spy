# JobSpy frontend

A small React (Vite) UI for the JobSpy API: browse scraped jobs, filter them by
required years of experience, and assess / rewrite your resume for a chosen job.

## Prerequisites
- The backend running (defaults to `http://127.0.0.1:8000`):
  ```bash
  # from the repo root
  ./.venv/Scripts/python.exe run_api.py --port 8000
  ```
- Node.js 18+ and npm.

## Setup & run (dev)
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173.

By default the app talks to `http://127.0.0.1:8000`. To point elsewhere, copy
`.env.example` to `.env` and set `VITE_API_BASE`.

## What each tab does
- **Jobs** — load the latest scraped jobs (`GET /jobs`) or kick off a fresh
  scrape (`POST /scrape`, polled). Open **Scrape filters** to set your own
  search terms, location, sites, results-per-site, recency, country, and the
  **cooldown** between search terms (in minutes; `0.5` = 30s, `0` disables)
  (prefilled from `GET /config/scrape`); blank fields fall back to `config.py`.
  A progress bar tracks the scrape across your search terms. Click **Use for
  resume** on a job to target it.
- **Filtered** — keep only jobs whose required experience overlaps a
  **min–max years window** (`POST /filter/experience`). Leave *max* blank for an
  open-ended "N+". This calls the AI once per job, so it is slow and needs a
  working API key; each matched card shows a `needs N yrs` badge.
- **Resume** — upload a `.docx`, pick a target job, then **Assess suitability**
  (`POST /suitability`) or **Rewrite & download** the tailored resume
  (`POST /tailor-resume`).

## Note on the AI key
Filtering, suitability, and rewriting call the backend's LLM (NVIDIA). If the
backend has no valid `NVIDIA_API_KEY`, the header shows **"AI not configured"**
and those actions return a clear error — browsing jobs still works.

## Production build
```bash
npm run build      # outputs dist/
npm run preview    # serve the built app locally
```
