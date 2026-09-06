# LinkedIn Vacancy Scraper — Project Guide

## Philosophy

This scraper is built around **polite, human-paced browsing**, not bulk extraction.
The goal is a single logged-in session that moves through LinkedIn the way a careful
human recruiter would: reading one job at a time, pausing between actions, never
hammering the server. Speed is explicitly not a priority.

---

## Development Workflow — mandatory after every feature/bugfix

No iteration (new feature, bugfix, refactor) is done until all of these
have happened, in this order:

1. **Update the tests** — new/changed behavior gets a test; a bugfix gets
   a regression test that would have caught it. See `docs/qa.rst`'s
   testing philosophy for which layer a given test belongs at.
2. **Run everything and confirm it's green**: fast suite
   (`pytest tests/ --ignore=tests/e2e`), E2E suite (`pytest tests/e2e/`)
   if frontend/API-contract code changed, and a Sphinx build
   (`sphinx-build docs docs/_build/html`) with zero warnings.
3. **Update the docs with the real, verified result** — not what was
   intended, what actually happened: refresh `docs/qa.rst`'s test
   counts/traceability matrix, `docs/roadmap.rst`'s checklist/notes if it
   touches the web app, and this file's Configuration Reference /
   Debugging Checklist if it changes a tunable or fixes a class of bug
   worth recognizing next time.
4. If a UI change was involved, **verify it worked in a real browser**
   (Playwright against the running dev server) before calling it done —
   see the Stage W2 notes in `docs/roadmap.rst` for the pattern, and
   never test against the real `output/jobs.db` when a disposable copy
   will do.

The point is that `docs/qa.rst` and this file stay an accurate account of
what the codebase actually does and how well it's actually tested — not
aspirational notes that quietly drift out of date.

---

## Project Structure

```
linkedin_scrapper/
├── src/
│   ├── config.py             # All tuneable parameters and URL builder
│   ├── runner.py             # Entry point: session check → scrape → export → stats
│   ├── scraper.py            # Playwright browser logic
│   ├── database.py           # SQLite persistence, dedup via job_id, filter/sort/CRUD for the web app
│   ├── models.py             # Pydantic Job / ApplicationStatus / ScraperStats
│   ├── utils.py               # Human behaviour helpers, logging, text cleaning
│   ├── login.py               # One-time session bootstrap (run manually)
│   ├── rate_limiter.py        # Sliding-hour request cap (REQUESTS_PER_HOUR)
│   ├── scoring.py             # Weighted keyword match scoring (pure functions)
│   ├── recalculate_scores.py  # CLI: recompute match_score for every job, no re-scrape
│   └── import_csv.py          # CLI: merge a jobs CSV exported elsewhere into a DB
│
├── webapp/                    # FastAPI + React job-tracker UI on top of output/jobs.db
│   ├── backend/                # FastAPI app (see docs/roadmap.rst for the API surface)
│   └── frontend/                # Vite + React + TypeScript + Mantine SPA
│
├── tests/                      # pytest-bdd (scraper/rate-limiting) + plain pytest (DB/scoring/API/E2E)
├── docs/                       # Sphinx docs — see "Documentation" below
│
├── user_data/                  # Persistent Chrome profile (created by login.py)
├── output/
│   ├── jobs.db                 # SQLite database
│   ├── jobs.csv                # Exported after every run
│   └── jobs.json                # Exported when `runner.py --json` is passed
└── logs/
    └── scraper.log
```

---

## Running the Project

Full first-time setup (venv, `pip install`, Playwright, Node/npm for the
web app) is in **`docs/installation.rst`** — not repeated here. Once set
up:

```bash
# Step 1 — only once, or when the session expires
.venv\Scripts\python.exe src\login.py
# A real Chrome window opens. Log in manually. Close it when done.

# Step 2 — every scrape run
.venv\Scripts\python.exe src\runner.py
```

For the web app (reviewing scraped jobs, tracking application status,
match scoring), see the "Web App" section below and `docs/roadmap.rst`.

## Documentation

This file is a short orientation file for working *in* the codebase. The
maintained documentation surface is the Sphinx project in `docs/`:

```bash
.venv\Scripts\python.exe -m sphinx -b html docs docs/_build/html
```

Then open `docs/_build/html/index.html`. Pages: `installation` (full
setup for both the scraper and the web app), `overview` (features + user
flow diagrams), `qa` (test inventory, traceability matrix, coverage),
`pacing` (rate-limit tuning and what's known about LinkedIn's own
ban/restriction behavior), `playground` (poking at the DB by hand), and
`roadmap` (web app architecture and staged progress).

---

## Human Behaviour Emulation — Current State

Everything that makes the scraper look like a real user lives in `utils.py`
and is called explicitly at each step in `scraper.py`.

### What is implemented

| Behaviour | Where | Detail |
|---|---|---|
| Random pauses between actions | `random_sleep(min, max)` | Default 2–4 s; extended to 3–5 s after page loads |
| Long breaks between page batches | `long_break()` | 25–60 s pause every 3 pages |
| Random mouse movement | `move_mouse_random(page)` | Moves to a random (x, y) before each card click |
| Randomized scroll | `human_scroll(page)` | 2–9 steps; 12% chance of no scroll at all, 20% chance of a fast skim, 15% chance of scrolling back up afterward |
| Distraction pause | `maybe_distraction_pause()` | ~7% chance per card of a 25–75 s pause (simulates tabbing away mid-session) |
| Block / captcha detection | `looks_like_blocked(page)` | Checks page HTML for "verify", "captcha", "unusual activity" keywords |
| Persistent login session | `user_data/` Chrome profile | Avoids re-login on every run; credentials never touch the code |
| Dedup before clicking | `collect_cards()` reads `data-job-id` | Already-seen jobs are skipped without even opening the detail panel |
| Title pre-filter | `title_skip_reason()` in `utils.py` | Skips obviously-irrelevant/non-matching titles without ever opening the detail panel — fewer clicks, fewer signals |
| Hourly request cap | `REQUESTS_PER_HOUR` + `RateLimiter` (`rate_limiter.py`) | Sliding 1-hour window on detail-panel opens; stops gracefully, resumes safely via dedup. See `docs/pacing.rst` |
| Session card cap | `MAX_CARDS_PER_SESSION` | Session stops once N cards have been looked at (clicked *or* skipped), independent of the hourly cap |
| Early session exit | random check in `Scraper.run()` | ~15% chance per page (from page 3 onward) of stopping before the configured page limit — session length varies, not metronomic |

### Load state strategy

LinkedIn is a SPA that fires continuous background XHR calls, making
`networkidle` always time out. The pattern used throughout is:

```python
page.wait_for_load_state("domcontentloaded")
_wait_for_cards(page)   # or _wait_for_detail_panel(page) for the job panel
```

`domcontentloaded` fires fast and reliably but doesn't wait for React to
render anything. `_wait_for_cards()` / `_wait_for_detail_panel()` (in
`scraper.py`) wait on `wait_for_selector` — up to 10 s for `div[data-job-id]`
or a bare `h1` respectively — then add a 0.5–1.5 s jitter, so a fast
connection isn't held back by a fixed sleep and a slow one doesn't read a
half-rendered page. Both fail soft: a timeout logs a warning and returns
`False` rather than raising, leaving the existing "no cards found" /
blocked-page diagnostics to explain why.

### Selector stability

LinkedIn obfuscates CSS class names that rotate on deploys. Selectors are
chosen in this priority order:

1. **Data attributes** — `div[data-job-id]` — stable, semantic, never changes
2. **Aria labels** — `button[aria-label*='Next']` — tied to accessibility, rarely changes
3. **BEM class names** — `job-details-jobs-unified-top-card__job-title` — change occasionally
4. **Dynamic ID** — `#JobDetails_AboutTheJob_{job_id}` — built at runtime from the job ID

---

## Configuration Reference

All tuneable values are in `config.py`. Edit there, nothing else needs to change.

| Variable | Default | Purpose |
|---|---|---|
| `SEARCH_KEYWORD` | `"trading QA"` | LinkedIn search keyword |
| `SEARCH_LOCATION` | `"Remote"` | Location filter (free text; see `FORM_LOCATION` below — LinkedIn doesn't reliably honor this alone) |
| `FORM_LOCATION` | `"European Union"` | Forces the search region via a LinkedIn `geoId` (must be `""` or a key in `GEO_ID_BY_REGION`) — works around LinkedIn silently falling back to the browser/account's detected location when `SEARCH_LOCATION` doesn't resolve to a real place |
| `GEO_ID_BY_REGION` | `{"Worldwide": ..., "European Union": ...}` | The geoId values `FORM_LOCATION` can select |
| `REMOTE_ONLY` | `False` | Adds `f_WT=2` to the search URL |
| `EASY_APPLY` | `False` | Adds `f_AL=true` |
| `POSTED_LAST_24H` | `False` | Adds `f_TPR=r86400` |
| `POSTED_LAST_WEEK` | `False` | Adds `f_TPR=r604800` |
| `MAX_PAGES` | `5` | Hard cap on pages per run |
| `HEADLESS` | `True` | Set `False` for a visible browser window (harder to fingerprint, easier to debug) |
| `REQUESTS_PER_HOUR` | `150` | Sliding-hour safety cap on job-detail-panel opens (see `docs/pacing.rst`) |
| `MAX_CARDS_PER_SESSION` | `40` | Hard cap on cards looked at (clicked or skipped) per session, regardless of time elapsed |
| `TITLE_SKIP_KEYWORDS` | `["junior", "intern", ...]` | Skip a card without clicking if its title contains any of these |
| `TITLE_MUST_KEYWORDS` | `[]` | If non-empty, skip a card unless its title contains at least one of these |
| `USER_DATA_DIR` | `./user_data` | Persistent Chrome profile path |
| `OUTPUT_CSV` | `output/jobs.csv` | CSV export path |
| `OUTPUT_JSON` | `output/jobs.json` | JSON export path (written when `runner.py --json` is passed) |
| `OUTPUT_DB` | `output/jobs.db` | SQLite path |

---

## Staged Roadmap

### Stage 2 — Smarter waiting (done)

- ✅ Fixed `random_sleep()` after load replaced with **element-presence
  waits** — `_wait_for_cards()` waits on `div[data-job-id]`,
  `_wait_for_detail_panel()` waits on `h1` (see `scraper.py`), both up to
  10 s with a 0.5–1.5 s jitter, failing soft to a logged warning on timeout
  rather than raising
- Applied at every load point: initial search page, after a card click,
  after returning to the results list, and after clicking "Next"

### Stage 3 — Richer field extraction

The `Job` model already has fields for `salary`, `employment_type`, `seniority`,
`workplace_type`, `skills`, `applicants`. The detail panel contains all of these —
they just need selectors confirmed against the live DOM. Priority order:

1. `salary` — high signal for filtering
2. `skills` — the "Skills" pill section below the description
3. `employment_type` / `seniority` — in the job criteria list
4. `applicants` — the "X applicants" line in the top card

### Stage 4 — Session health monitoring (done)

- ✅ `_session_expired(page)` checks at the start of each page loop in
  `Scraper.run()` — if LinkedIn redirected to `/login` or `/checkpoint`,
  the run logs an error, sets `ScraperStats.session_expired`, and stops
  gracefully (dedup means the next run resumes cleanly)
- ✅ `--relogin` CLI flag on `runner.py` runs `login.py`'s manual login
  flow (still an interactive, visible-browser step — credentials never
  touch the code) before the scrape starts

### Stage 5 — Rate limiting and run scheduling (done)

- ✅ `REQUESTS_PER_HOUR` cap in `config.py`, tracked via a sliding-window
  `RateLimiter` (`rate_limiter.py`) and mirrored in `ScraperStats`
- ✅ The run stops automatically when the cap is hit and logs a resume hint
  (dedup makes the next run pick up where it left off)
- ⬜ Not done: scheduling via cron / Task Scheduler to run once per day at
  a random time — still a manual `runner.py` invocation today

See `docs/pacing.rst` for the exact numbers and how they relate to
LinkedIn's own ban/restriction behavior.

### Stage 6 — Export improvements (done)

- ✅ CSV export was already dedup-safe: `export_csv()` opens in `"w"` mode
  and re-queries the DB fresh on every call (rows are unique by `job_id`),
  so reruns overwrite rather than append — this note in the roadmap
  predated that fix
- ✅ `--since` flag on `runner.py` limits the export to jobs scraped at or
  after a given ISO date/datetime (e.g. `--since 2026-09-01`); it only
  affects what gets exported, not what gets scraped. Backed by
  `Database.get_jobs_since()`
- ✅ `--json` flag also writes `output/jobs.json` (same row set as the CSV,
  as a JSON array) for downstream pipeline consumption
- ✅ `import_csv.py` — the reverse direction: merges a CSV from
  `export_csv()` (scraped on another machine, moved over by whatever
  means — scp/rsync, not this project's concern) into a target database
  through the same `Database.insert_job()` path a live scrape uses, so a
  job already in the target DB (including any status/notes edited since)
  is left untouched; only genuinely-new `job_id`s are added. Built for a
  "one machine holds the canonical DB, scrapes done elsewhere get pushed
  into it" setup — see `docs/roadmap.rst` for the full writeup.

### Stage 7 — Proxy / multi-profile support

Only relevant if the account gets restricted. Structure:

- `config.py` gets a `PROXY` field (`None` by default)
- `user_data/` becomes `user_data/<profile_name>/` to support rotating profiles
- `runner.py` accepts `--profile` CLI argument

---

## Web App (in progress)

A FastAPI + React UI on top of the scraper's existing database, so job
review/filtering/status-tracking doesn't require the `sqlite3` CLI or a
Python console (see `docs/playground.rst` for that interim workflow).
This is tracked separately from the scraper's own Stage 2-7 roadmap above
since it adds no scraper functionality — it's a UI on top of the already-
built data layer in `database.py`.

**Full architecture, API surface, and staged progress: `docs/roadmap.rst`**
(build it with `sphinx-build docs docs/_build` or read the source directly).

---

## Debugging Checklist

When 0 cards are found:

1. Check the PAGE SNAPSHOT in the log — is it a login wall or the real search page?
2. Open the URL from `config.py` manually in Chrome and inspect the first card —
   confirm `data-job-id` is present on the outer `div`
3. Check `looks_like_blocked()` output — LinkedIn may have served a CAPTCHA silently

When the description is empty:

1. The selector is `#JobDetails_AboutTheJob_{job_id} > div > div > div > div > p`
2. Open the job page in DevTools → Elements → search for `JobDetails_AboutTheJob`
3. Count the `> div` nesting levels — LinkedIn occasionally adds or removes one layer
4. Update `description_selector()` in `scraper.py` to match

When the description has no paragraph breaks (one unreadable run-on
blob): fixed — `parse_job()` used to run descriptions through
`clean_text()`, whose blanket whitespace collapse (`\s+` → `" "`) ate
line breaks along with incidental whitespace. This mattered because
LinkedIn sometimes renders a description as a single `<p>` with `<br>`
tags instead of several `<p>` elements, so all its structure lived in
those `<br>`-derived line breaks. Now uses `clean_description()` (see
`utils.py`), which normalizes whitespace per line instead of across the
whole text. **This can't be backfilled** for jobs already in the DB —
unlike `job_url`/`location_entity` (pure functions of data already
stored), the original line breaks were destroyed at scrape time and
aren't recoverable from the flattened text sitting in the database. The
only way to recover an already-broken description is to re-scrape that
job's page, which means removing its row so dedup doesn't skip it —
not something to do automatically, since the listing may no longer
exist on LinkedIn.

When selectors break after a LinkedIn deploy:

- Data attributes (`data-job-id`) and aria labels (`aria-label*='Next'`) are stable
- BEM class names (`.job-details-jobs-unified-top-card__*`) change occasionally —
  re-inspect and update the constants at the top of `scraper.py`

When a column is empty for jobs scraped before some date, but populated
after it (already happened twice: `job_url`, then
`location_entity`/`posted`/`applicants`):

- This means parsing for that field was added/fixed in `scraper.py` at
  some point, but dedup (`job_exists()`) means older rows are never
  re-scraped, so they keep the old empty value forever
- If the field can be derived from data already stored elsewhere in the
  same row (e.g. `location_entity` from the raw `location` text,
  `job_url` from `job_id`), fix it with a one-time backfill in
  `database.py`'s `_migrate_schema()` — see `_backfill_missing_job_urls()`
  and `_backfill_missing_location_meta()` for the pattern — rather than
  telling the user to re-scrape. It runs automatically on every
  `Database()` init, so it self-heals any copy of the DB.
- If it genuinely requires re-visiting the LinkedIn page (not just
  re-parsing already-stored text), a backfill can't help — that field
  will only fill in for newly-scraped jobs going forward.

When the web app shows "Failed to load jobs" and the scraper *isn't*
running (if it is, see the WAL/locking entry below instead) — check for a
port mismatch (or a backend that just isn't running) before suspecting a
code bug, in this order:

1. Is anything actually listening on the port `webapp/frontend/.env`'s
   `VITE_API_URL` points at? (`netstat -ano` on Windows, filter for that
   port's `LISTENING` line, then `Get-CimInstance Win32_Process -Filter
   "ProcessId=<pid>"` to see what it actually is.) Three variants of this
   have happened for real: an unrelated local project's FastAPI server
   happened to already be running on the same default port (8000) the
   docs recommend, `.env` was left pointing at a port the backend had
   since moved off of, and — the simplest one, easy to overlook because
   the page still looks normal — the backend process had simply been
   stopped while the frontend's dev server was left running. The backend
   and frontend are independent processes; the frontend is just a static
   dev server, so it keeps serving the React app fine with the backend
   dead, and every API call inside it just fails instead. None of these
   is a code bug — either restart the backend, or make `.env` match
   wherever `webapp.backend.main:app` is actually listening and restart
   the Vite dev server (`.env` is only read at startup, not
   hot-reloaded). See `docs/installation.rst`'s "Stopping the app" for
   how to find and stop either process by port when there's no terminal
   to `Ctrl+C` in.
2. Confirm the *right* backend is up with `curl
   http://127.0.0.1:<port>/api/health` and `/api/jobs?limit=1` — if
   those 404 or return something that isn't this project's JSON shape,
   it's the wrong process on that port (see step 1), not a broken
   endpoint.
3. Only once both of those check out is it worth looking at the DB layer
   (WAL/locking entry below) or the frontend code itself.

When the web app shows "Failed to load ..." / "Could not add ..." while
the scraper is also running:

- Both processes share `output/jobs.db` — the scraper holds one
  long-lived write connection for the whole run, the web app opens a
  fresh one per request. A web app write landing while the scraper is
  mid-commit can fail with `sqlite3.OperationalError: database is
  locked` (surfaces to the browser as a generic 500).
- Reproduced directly (see `docs/qa.rst`'s traceability matrix,
  "WAL journal mode" row) and fixed in `Database.__init__`: WAL journal
  mode (`PRAGMA journal_mode=WAL`) lets reads proceed without waiting on
  a writer at all, plus a 10s connect `timeout` (was the sqlite3 default
  of 5s) so a write on the losing side of a race waits instead of
  failing outright. Both are already in place — if this error still
  shows up, it means the write side of an *actual* contention window
  (two writes at once, not a read) exceeded 10s, which would be worth
  investigating rather than just raising the timeout further.

When a web app request intermittently fails with `sqlite3.ProgrammingError:
SQLite objects created in a thread can only be used in that same thread`:

- Already fixed (`check_same_thread=False` in `Database.__init__`), but
  worth understanding if it ever resurfaces: FastAPI's `Depends(get_db)`
  resolves a sync generator dependency and then calls the route handler
  as two *separate* `run_in_threadpool` dispatches -- not guaranteed to
  land on the same worker thread. sqlite3's default same-thread check
  rejects a connection used from a thread other than the one that
  created it, so this could hit *any* route using `Depends(get_db)`, not
  just whichever one happens to trip it first -- it's about request
  scheduling luck, not something specific to one endpoint.
- Safe to disable the check here specifically because each `Database` is
  single-request-scoped (opened and closed within one `get_db()` call) --
  it's used by one thread at a time, sequentially, never two threads at
  once.
- See `test_database_can_be_used_from_a_different_thread_than_it_was_created_on`
  in `tests/backend/test_database_extensions.py` for a deterministic
  reproduction, rather than relying on E2E scheduling to catch a
  regression here again.