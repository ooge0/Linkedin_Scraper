Overview
========

What this project is
----------------------

A two-part personal job-search tool:

1. **The scraper** (``src/``) -- a Playwright-driven, human-paced browser
   session that walks LinkedIn's job search results the way a careful
   recruiter would: one job at a time, with pauses, scrolling, and
   occasional "distraction" breaks, saving each new listing to a local
   SQLite database. See the project philosophy in ``CLAUDE.md``.
2. **The job tracker web app** (``webapp/``) -- a FastAPI + React UI on
   top of that same database, for reviewing scraped jobs, filtering and
   sorting them, tracking where each one stands in your own application
   pipeline, and weighting/recalculating a match score per job. See
   :doc:`roadmap` for its architecture and build status.

Nothing here talks to LinkedIn except the scraper itself -- the web app
only ever reads and writes the local SQLite file the scraper produces.

Features
---------

Scraping
~~~~~~~~

- Keyword/location/remote/easy-apply/posted-date search filters, built
  into one search URL (``config.build_search_url``)
- Scroll-to-load discovery of every card in the results panel, not just
  the initially-rendered ones
- Dedup by ``job_id`` -- a previously-saved job is never re-opened
- Title pre-filtering (``TITLE_SKIP_KEYWORDS`` / ``TITLE_MUST_KEYWORDS``)
  skips obviously irrelevant listings before ever clicking them
- Session-health check -- a redirect to ``/login`` or ``/checkpoint`` is
  detected and stops the run with a clear message, instead of silently
  scraping a login wall
- Block/CAPTCHA detection on the page text itself
- CSV and JSON export, with an optional ``--since`` cutoff

Human-behavior emulation
~~~~~~~~~~~~~~~~~~~~~~~~~

- Randomized pauses, scrolling (with a chance of skipping it entirely, a
  fast skim, or scrolling back up), and mouse movement
- A per-card chance of a longer "distraction" pause, and a per-page chance
  of ending the session early -- so a run doesn't look metronomic
- Two independent, graceful safety caps: an hourly request-rate limit and
  a per-session card-count limit (see ``docs/pacing.rst`` for exactly how
  these numbers were chosen and what's known about LinkedIn's own
  restriction behavior)

Match scoring
~~~~~~~~~~~~~~

- A weighted keyword match score (0-100) per job, computed from
  user-defined criteria (term + weight, positive or negative)
- Criteria can change at any time; scores are recomputed for the *entire*
  database in one shot (``recalculate_scores.py`` or the web app's
  "Recalculate scores" button) -- no re-scraping needed

Web app (job tracker)
~~~~~~~~~~~~~~~~~~~~~~

- Filter the job list by application status, free-text search, or a
  minimum match score; sort by date scraped, title, company, posted date,
  or score; paginated
- A closed set of application statuses (``not_applied`` / ``viewed`` /
  ``applied`` / ``interview`` / ``rejected`` / ``offer`` / ``ignored``) plus free-text
  notes, editable inline
- Manage match-scoring criteria and trigger a full recalculation from the
  UI

User flows
-----------

End-to-end workflow
~~~~~~~~~~~~~~~~~~~~

.. mermaid::

   flowchart LR
       A[python login.py<br/>manual login, once] --> B[python runner.py<br/>scrape + export]
       B --> C[(output/jobs.db)]
       C --> D[Web app: review jobs,<br/>filter/sort, edit status/notes]
       D --> C
       D -->|criteria change| E[Recalculate scores]
       E --> C
       B -.->|session expired| A

Scraper run (one page)
~~~~~~~~~~~~~~~~~~~~~~~

.. mermaid::

   flowchart TD
       Start([Load search page]) --> Health{Session expired?<br/>/login or /checkpoint}
       Health -->|yes| StopExpired[Stop: re-run login.py]
       Health -->|no| Blocked{Blocked / CAPTCHA<br/>page text?}
       Blocked -->|yes| StopBlocked[Stop: log + snapshot]
       Blocked -->|no| Collect[Collect all card ids<br/>on this page, incl. scroll-to-load]
       Collect --> ForEach{Next card}
       ForEach -->|known job_id| Skip1[Skip: already saved]
       ForEach -->|title matches skip/must rules| Skip2[Skip: title filter]
       ForEach -->|hourly cap reached| StopRate[Stop: resume next run]
       ForEach -->|session card cap reached| StopCap[Stop: resume next run]
       ForEach -->|otherwise| Open[Click card, wait for<br/>detail panel to render]
       Open --> Parse[Parse title/company/location/<br/>salary/description/skills/...]
       Parse --> Save[(Insert into jobs.db)]
       Save --> ForEach
       ForEach -->|no cards left| NextPage{More pages<br/>requested?}
       NextPage -->|yes| Start
       NextPage -->|no| Done([Export CSV/JSON, print stats])

Web app: reviewing and updating a job
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. mermaid::

   sequenceDiagram
       participant U as User
       participant F as React (JobsPage)
       participant A as FastAPI
       participant D as jobs.db

       U->>F: open page / change filter
       F->>A: GET /api/jobs?status=&search=&sort_by=...
       A->>D: get_jobs_filtered() + count_jobs_filtered()
       D-->>A: rows, total
       A-->>F: JobListResponse
       F-->>U: render table + pagination

       U->>F: change a job's status
       F->>A: PATCH /api/jobs/{job_id}
       A->>D: update_job_status()
       D-->>A: ok
       A-->>F: updated Job
       F-->>U: row updates in place

       U->>F: click "Recalculate scores"
       F->>A: POST /api/scores/recalculate
       A->>D: recalculate_all_scores() (scoring.py)
       D-->>A: rows updated
       A-->>F: {updated: N}
       F->>A: GET /api/jobs (re-fetch)
       F-->>U: updated scores shown
