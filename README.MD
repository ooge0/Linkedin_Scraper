## LinkedIn Vacancy Scraper

A Playwright-based scraper for collecting LinkedIn job vacancies from a
manually authenticated Chrome session, plus a FastAPI + React web app for
reviewing what it finds. Both are designed around slow, human-paced
browsing rather than bulk extraction — see `CLAUDE.md` for the project
philosophy.

## Setup

Full installation for both the scraper and the web app (Python venv,
`pip install`, Playwright, Node/npm) lives in **`docs/installation.rst`**
so it's maintained in one place — build the docs (see below) or read the
file directly. Quick version for the scraper alone:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
# Once, or when the session expires — opens a visible Chrome window to log in manually
.venv\Scripts\python.exe src\login.py

# Every scrape run
.venv\Scripts\python.exe src\runner.py
.venv\Scripts\python.exe src\runner.py --pages 2
```

A page means one LinkedIn search-results batch, not one job. The runner
checks that `user_data/` exists and isn't empty, opens the configured
search URL, scrolls the full results panel, skips job IDs already in the
database, exports all stored jobs to CSV (and JSON with `--json`), and
prints run statistics. See `src/runner.py --help` for every flag
(`--relogin`, `--since`, `--json`, `--pages`).

## Configuration

Edit [src/config.py](src/config.py) — every tunable is commented there.
For a table of what each one does, see `CLAUDE.md`'s Configuration
Reference (kept as the single copy of this table, rather than duplicated
here and risking the two drifting apart).

## Web app

A FastAPI + React UI on top of `output/jobs.db`, for filtering/sorting
scraped jobs, tracking application status and notes, and recalculating a
weighted match score without re-scraping. Setup is in
`docs/installation.rst`; architecture, API surface, and build status are
in `docs/roadmap.rst`.

## Outputs

- `output/jobs.db`: SQLite database with unique `job_id` values.
- `output/jobs.csv`: UTF-8 export recreated after every run.
- `output/jobs.json`: JSON export, written when `runner.py --json` is passed.
- `logs/scraper.log`: rotating debug and progress log.
- `logs/login.log`: login bootstrap and browser lifecycle log.
- `user_data/`: persistent browser session data. Treat this directory as
  sensitive and do not commit or share it.

## Test

```powershell
.venv\Scripts\python.exe -m pytest tests --ignore=tests/e2e -q
```

pytest-bdd (scraper behavior, rate limiting) plus plain pytest (database
layer, match scoring, web app API). None of it contacts LinkedIn or
requires an authenticated browser session. A separate, slower Playwright
E2E suite (real backend + frontend + browser) runs with
`pytest tests/e2e/ -v` — see `docs/installation.rst`. See `docs/qa.rst`
for the full test inventory, a traceability matrix (behavior → test), and
coverage —
including why some modules deliberately don't chase high coverage
numbers. For an HTML Allure report combining both suites, see
`docs/installation.rst`.

## Documentation

The maintained documentation surface is the Sphinx project in `docs/`:

```powershell
.venv\Scripts\python.exe -m sphinx -b html docs docs/_build/html
```

Then open `docs/_build/html/index.html`. `CLAUDE.md` in the repo root
stays a short orientation file for working in the codebase, not a
duplicate of this content.

## Project Structure

```text
linkedin_scrapper/
|-- src/
|   |-- config.py             # Search filters, tunables, and URL builder
|   |-- database.py           # SQLite persistence, dedup, filter/sort/CRUD for the web app
|   |-- login.py              # Manual session bootstrap
|   |-- models.py             # Pydantic Job / ApplicationStatus / ScraperStats
|   |-- rate_limiter.py       # Sliding-hour request cap
|   |-- recalculate_scores.py # CLI: recompute match_score for every job
|   |-- runner.py             # Session check, scrape, export, and reporting
|   |-- scoring.py            # Weighted keyword match scoring
|   |-- scraper.py            # Playwright browser workflow
|   `-- utils.py              # Delays, logging, text, and block detection
|-- webapp/
|   |-- backend/              # FastAPI app
|   `-- frontend/             # Vite + React + TypeScript + Mantine SPA
|-- tests/
|   |-- features/             # Gherkin scenarios (scraper, rate limiting)
|   |-- backend/              # Database + scoring unit tests
|   |-- webapp_api/           # FastAPI endpoint tests
|   `-- test_*.py
|-- docs/                     # Sphinx documentation
|-- output/                   # Generated database, CSV, JSON
|-- logs/                     # Generated logs
|-- user_data/                # Persistent Chrome profile
|-- requirements.txt
`-- README.MD
```
