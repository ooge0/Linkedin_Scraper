Web app roadmap
================

This page is the living plan and progress tracker for the job-tracker web
app built on top of the scraper's database. ``CLAUDE.md`` stays a short
orientation file for the scraper itself; this is where the web app's
architecture, decisions, and stage-by-stage progress are recorded (see
``docs/index.rst``).

Why a web app at all
---------------------

The scraper's data layer (``src/database.py``) was already built with a web
app in mind, well before one existed: ``get_jobs_filtered`` /
``count_jobs_filtered`` (filter, sort, paginate), ``get_status_counts``,
``update_job_status``, full CRUD for match-scoring criteria, and
``scoring.recalculate_all_scores`` -- all already used from the CLI
(``recalculate_scores.py``) and from a Python console (see
``docs/playground.rst``), but with nothing else built on top of them. The
web app's job is to put a real UI on that existing data layer -- it adds
no new scraper functionality.

Decision
--------

- **Backend: FastAPI**, as a pure JSON API (no server-rendered HTML).
  Reuses ``src/database.py`` and ``src/scoring.py`` directly -- no new data
  layer, only routes that call the existing methods. ``src/models.py`` is
  already Pydantic, so ``Job`` / ``ApplicationStatus`` are reused as
  response/request schemas as-is.
- **Frontend: React + Vite + TypeScript**, talking to the API over
  ``fetch``. Chosen over a server-rendered (Jinja2/HTMX) approach for
  transferable skill value (React is the most commonly asked-for frontend
  skill) despite the extra build tooling; chosen over Streamlit because
  the goal is a real, presentable UI, not a quick data-science dashboard.
  **Mantine** is used as the component library (tables, inputs, badges,
  buttons pre-styled) specifically to get a clean, non-default look
  without hand-writing CSS -- the instruction to keep code simple applies
  to *logic*, not to reinventing a design system from scratch.
- **No Redux/Zustand/react-query.** Plain ``useState``/``useEffect`` and a
  small hand-written API client. The app is small enough (three pages,
  one data source) that a state-management library would be pure overhead
  and would work against "keep the code simple, I'm learning from this."
- **Testing**: pytest + FastAPI's ``TestClient`` for the backend (a
  temp-file SQLite DB per test, same pattern the scraper's own BDD tests
  use), Playwright (Python) with the Page Object Model for end-to-end,
  ``allure-pytest`` for reporting on both suites. Scenario count is
  deliberately kept small and assertions target visible/functional
  outcomes only -- broad coverage of the data layer already exists via
  the scraper's own test suite; the web app's tests exist to catch wiring
  mistakes between UI, API, and DB, not to re-prove the DB layer itself.
- **Docs**: this Sphinx page is the single source of truth for the plan
  and its progress -- updated as each stage lands, not written once and
  left stale.

Project layout
--------------

A new top-level ``webapp/`` directory, sibling to ``src/`` -- keeps the
scraper's own ``src/`` untouched and matches "a web app that reads the
scraper's database" rather than being part of the scraper itself::

    webapp/
    ├── backend/
    │   ├── main.py            # FastAPI app, CORS, router registration
    │   └── routes/
    │       ├── jobs.py        # /api/jobs
    │       ├── criteria.py    # /api/criteria
    │       └── scores.py      # /api/scores/recalculate
    └── frontend/
        ├── package.json
        ├── vite.config.ts
        └── src/
            ├── main.tsx
            ├── App.tsx
            ├── api/client.ts
            ├── pages/
            │   ├── JobsPage.tsx
            │   ├── JobDetailPage.tsx
            │   └── CriteriaPage.tsx
            └── components/     # JobTable, FilterBar, StatusBadge, ...

    tests/
    ├── webapp_api/      # pytest + TestClient, backend only
    └── e2e/
        ├── pages/       # Page Object Model classes
        └── test_*.py    # Playwright scenarios, full stack

The backend adds ``src/`` to ``sys.path`` and imports ``Database``,
``Job``, ``ApplicationStatus``, ``recalculate_all_scores`` directly --
the same pattern ``runner.py`` and ``recalculate_scores.py`` already use.

API surface
-----------

.. list-table::
   :header-rows: 1

   * - Method
     - Path
     - Backed by
   * - GET
     - ``/api/jobs``
     - ``get_jobs_filtered`` + ``count_jobs_filtered`` (status, search,
       min_score, sort_by, sort_dir, limit, offset -> items + total)
   * - GET
     - ``/api/jobs/{job_id}``
     - ``get_job``
   * - PATCH
     - ``/api/jobs/{job_id}``
     - ``update_job_status`` (status and/or notes)
   * - DELETE
     - ``/api/jobs/{job_id}``
     - ``delete_job``
   * - GET
     - ``/api/stats``
     - ``get_status_counts`` + ``count_jobs``
   * - GET
     - ``/api/criteria``
     - ``get_criteria``
   * - POST
     - ``/api/criteria``
     - ``add_criterion``
   * - PATCH
     - ``/api/criteria/{id}``
     - ``update_criterion``
   * - DELETE
     - ``/api/criteria/{id}``
     - ``delete_criterion``
   * - POST
     - ``/api/scores/recalculate``
     - ``scoring.recalculate_all_scores``

Frontend pages
--------------

- **Jobs list** (``/``) -- filter bar (status, search text, min score),
  sortable/paginated table, inline status dropdown per row, "Recalculate
  scores" button.
- **Job detail** (``/jobs/:jobId``) -- full description and all fields,
  status + notes editing.
- **Criteria** (``/criteria``) -- list existing match criteria (term,
  weight, enabled), add/edit/delete.

Staged plan
-----------

Stages are built and verified one at a time -- each stage's tests must
pass before the next one starts.

- [x] **Stage W0 -- Planning** (this document)
- [x] **Stage W1 -- Backend API**: FastAPI app (``webapp/backend/``) with
  every route in the table above, CORS for the Vite dev server, and 16
  API-layer tests in ``tests/webapp_api/`` (73 tests total in the project
  now). These tests check HTTP wiring (status codes, request/response
  shape) -- the DB logic itself was already covered by
  ``tests/backend/test_database_extensions.py`` and ``test_scoring.py``
  before the web app existed, so it isn't re-tested here.
- [x] **Stage W2 -- Frontend skeleton + Jobs list**: Vite + React + TS +
  Mantine scaffold (``webapp/frontend/``), a typed ``fetch`` API client
  (``src/api/client.ts`` / ``types.ts``), and the Jobs list page (status/
  search/min-score filters, sortable columns, pagination, inline status
  editing, "Recalculate scores") wired to the live backend. Verified
  manually with Playwright driving a real browser against the running
  dev server (filters change the result count, a status edit persists
  across a reload, sorting changes row order) -- see the screenshot
  discussion in this stage's implementation notes; automated E2E coverage
  of the same flows is Stage W4.
- [x] **Stage W3 -- Remaining pages**: Job detail page (``/jobs/:jobId`` --
  full description, salary/employment/seniority/skills, status + notes
  editing, link out to LinkedIn) and Criteria management page
  (``/criteria`` -- add/edit weight/toggle enabled/delete, and
  "Recalculate scores"). Both verified with a real Playwright-driven
  browser (navigation from the list, notes/status edits persisting across
  a reload, full criteria CRUD, recalculate triggering a visible
  notification). Along the way, found and fixed a real display bug this
  way: the detail page's subtitle was showing the *raw* ``location``
  column (which still has posted-date/applicant-count text glued onto it
  for jobs scraped before ``location_entity`` parsing existed --
  see ``docs/pacing.rst``'s parsing notes) instead of the cleaned
  ``location_entity``, duplicating information already shown as separate
  fields below it. Fixed in ``webapp/backend/schemas.py`` (``JobOut`` now
  exposes both) and the frontend now prefers ``location_entity``, falling
  back to raw ``location`` only when the clean field is empty; locked in
  with a new assertion in ``test_get_job_by_id`` (``tests/webapp_api/test_jobs_api.py``).
- [x] **Stage W4 -- Playwright E2E**: Page Object Model classes for all
  three pages (``tests/e2e/pages/``) and 8 golden-path scenarios across
  ``test_jobs_list.py``/``test_job_detail.py``/``test_criteria.py`` --
  list/filter/search, a status edit persisting after reload, job-detail
  notes+status editing, back-navigation, and criteria add/delete +
  recalculate actually changing a displayed match score. ``tests/e2e/conftest.py``
  starts a real backend and frontend as subprocesses on dynamically-picked
  free ports once per test session, reseeding the database before each
  test rather than restarting the servers. Two real bugs surfaced and got
  fixed building this, both now permanent fixes rather than just test
  workarounds:

  - Vite's dev server binds ``[::1]`` (IPv6) only by default; a plain
    ``http://127.0.0.1:<port>`` health-check never saw it come up. Fixed
    by passing ``--host 127.0.0.1`` explicitly when starting it.
  - The backend's CORS policy was a fixed allowlist for port 5173 only
    (from Stage W2) -- meaningless once the E2E suite needed a dynamic
    port to avoid clashing with a developer's already-running dev server.
    Changed to ``allow_origin_regex`` for any ``localhost``/``127.0.0.1``
    port in ``webapp/backend/main.py`` (still safe: this is a local
    personal tool, never internet-facing).

  Also worth knowing for anyone extending this: on Windows, ``npm run dev``
  is a ``cmd.exe`` wrapper (npm.CMD) around a real ``node.exe`` child --
  ``subprocess.Popen(...).terminate()`` only kills the wrapper and leaves
  the child (and the port) running. Fixed with ``taskkill /F /T`` in the
  fixture teardown, which kills the whole process tree.
- [x] **Stage W5 -- Allure + docs polish**: ``allure-pytest`` added
  (``requirements.txt``); running the fast suite and the E2E suite into
  the same ``--alluredir`` and generating once produces a single combined
  report for all 81 tests. Verified for real: generated a report, served
  it, and confirmed in a browser it shows 81/81 passing, correctly split
  into 4 suites (``tests``: 31, ``tests.backend``: 26,
  ``tests.webapp_api``: 16, ``tests.e2e``: 8) -- using Allure's default
  module-based "Suites" grouping, with no custom
  ``@allure.feature``/``@allure.story`` annotations added, since that
  default already matches this project's test-layer structure closely
  enough that duplicating it manually wouldn't add anything. See
  :ref:`allure-test-reports` in :doc:`installation` for exact commands.
  This is the last item on the web app's original build plan -- the
  Stage W0-W7 track above is now fully checked off; further web app work
  starts a new, separately-scoped entry on this page rather than
  stretching this list further.

Post-W5: Jobs page layout pass
--------------------------------

A round of UI feedback from actually using the app day to day (not part
of the original staged plan, hence its own section):

- Nav links (Jobs/Criteria) moved from the far right of the header to
  right next to the title -- they were sharing the top-right corner with
  the notifications popup, and required more mouse travel than necessary.
- Jobs table gained four columns: Location (prefers ``location_entity``,
  falls back to raw ``location``), Job ID, Search Location (which
  ``config.SEARCH_LOCATION`` filter was active when this job was found --
  distinct from the job's own location), and a read-only Notes preview
  (full text on hover via tooltip; still only editable from the job
  detail page). Backed by a new ``search_location`` field on the
  ``JobOut`` API schema.
- Pagination re-centered at the bottom (was right-aligned) with a
  "Per page" selector (10/20/50/100) added alongside it.
- Table columns on both the Jobs and Criteria pages are now manually
  resizable, via a small hand-rolled drag handle
  (``src/hooks/useColumnWidths.ts`` + ``src/components/ResizableTh.tsx``)
  rather than adopting a full data-grid library for it -- reused on both
  pages rather than duplicated.

Verified with 2 new E2E tests (``tests/e2e/test_jobs_table_layout.py``)
plus a manual Playwright pass against an isolated test instance (separate
ports, disposable DB copy) confirming the nav position, all ten column
headers in order, and an actual drag-resize changing a column's rendered
width.

Post-W5: Jobs page filtering & interaction pass
--------------------------------------------------

A second round of feedback from daily use, landing alongside an
unrelated operational issue (below):

- **Per-column filter row**: a second header row under the column
  labels, one filter control per column (text input, the Score column
  gets a min-value number input, Status gets its dropdown) -- replacing
  the old single top filter bar (Status/Search/Min score), which
  duplicated what the columns already show. Backed by a new
  ``column_filters`` map on ``Database.get_jobs_filtered()``/
  ``count_jobs_filtered()`` (substring match, column name checked against
  a fixed ``FILTERABLE_TEXT_COLUMNS`` whitelist the same way
  ``SORTABLE_COLUMNS`` already worked) and matching query params on
  ``GET /api/jobs``. Trade-off worth knowing: the old free-text search
  covered ``description`` too (no visible column for it), which the
  column-filter model doesn't replace -- description content isn't
  quick-filterable from the table anymore, only from a job's own detail
  page.
- **Sticky header**: both the label row and the new filter row stay
  fixed while the table body scrolls (a fixed-height, ``overflow: auto``
  wrapper div + ``position: sticky`` on each ``<th>`` individually, not
  on ``<thead>`` -- sticky positioning on ``display: table-header-group``
  isn't reliably supported across browsers, unlike on table cells).
- **Draggable column reordering**, via the native HTML5 drag-and-drop
  API -- no library needed. Composes with the existing resize handle
  (which calls ``preventDefault``/``stopPropagation`` on its own
  ``mousedown``, which is also what stops it from starting a native drag).
- **Row height control**: a single numeric input governing all rows
  uniformly, not per-row independent heights -- simpler and more robust
  to implement reliably than absolutely-positioned per-``<tr>`` resize
  handles, and matches how most real data grids expose row density.
- Column order, column widths, and row height now persist per-browser via
  ``localStorage`` (``src/hooks/useLocalStorageState.ts``) -- a viewer-
  local layout preference, not app data, so it's fine that it's not
  shared or backed up.
- New ``ApplicationStatus.VIEWED`` ("viewed") value, between
  ``not_applied`` and ``applied`` -- a job looked at but not yet acted on.
- Pagination re-centered with "Per page" grouped immediately after it
  (both centered together), rather than the two being separated to
  opposite ends of the bottom bar.

**Unrelated but discovered in the same session**: two separate reports of
"Failed to load jobs" turned out to both be port/config mismatches, not
application bugs -- the FastAPI backend running under an entirely
different, unrelated local project on the same port, and later
``webapp/frontend/.env`` pointing at a since-abandoned port after the
backend moved. Neither required a code change; both are now covered by a
`CLAUDE.md` Debugging Checklist entry so they're a two-minute diagnosis
next time instead of a fresh investigation.

Verified with 1 new DB-unit test file addition (4 tests) and 2 new API
tests for column filtering, 1 new E2E test for drag-reordering, plus a
manual Playwright pass against an isolated test instance confirming the
column filter narrows results with the correct network request, the
status filter includes "viewed", the row-height input actually changes
rendered row height, and -- checked rigorously, not just visually -- that
the header truly stays fixed (constant on-screen Y position) while the
scroll container's own ``scrollTop`` genuinely changes underneath it.

**Row height control removed** (later feedback): the original ask behind
this pass was the ability to resize the jobs table's *columns* by hand --
already covered by the drag-to-resize handles above. The row height
``NumberInput`` was an addition beyond that ask, and the user didn't want
it living in the footer. Removed along with its ``localStorage`` key
(``jobs-table-row-height``) and the ``rowHeight`` state; row height is
now a fixed 40px in ``cellStyle()``. Column order and column widths still
persist as before -- only the row-height piece is gone. No test changes
needed (nothing referenced "Row height" in the E2E suite). Full suite
still green: 98 fast + 17 E2E.

Post-W5: Scoring & "reach the best match faster" pass
---------------------------------------------------------

Prompted by an explicit ask for improvements to filtering/scoring aimed
at surfacing the best-matching jobs faster. The most consequential item
here is a correctness bug found by checking a suggestion against the
user's own real data before proposing it, not by inspection alone.

- **Word-boundary matching, not substring** (the headline fix):
  ``calculate_score()`` used a plain ``term.lower() in job_text`` check.
  Checked directly against the real ``output/jobs.db``: the user's own
  "AI" criterion (weight 60) matched **122 of 126 jobs (97%)** by
  substring, but only **76 (60%)** actually contain the real word "AI" --
  the rest were false hits inside "det\ **ai**\ l", "rem\ **ai**\ n",
  "expl\ **ai**\ ned", etc. Fixed with a ``\bterm\b`` regex
  (``scoring._term_matches``). Recalculating the real database with the
  fix dropped the average match score from 53.5 to 49.2 -- a real,
  material change, not a rounding difference.
- **Title matches count double** (``scoring.TITLE_MATCH_MULTIPLIER``):
  a term in "Senior **Python** Engineer" is a much stronger signal than
  the same word once in paragraph 12 of the description. The normalizing
  denominator is unchanged (sum of positive weights, as before), so a
  body-only match still reaches 100 exactly as it always could --
  title matches just get there with fewer terms, or push past the old
  ceiling before the final clamp.
- **"Why this score" breakdown**: new ``scoring.score_breakdown()``
  (which ``calculate_score()`` itself now sums, so the two can never
  disagree) and ``GET /api/jobs/{job_id}/score-breakdown``, rendered on
  the job detail page as one badge per criterion -- matched (green,
  ``(title)`` tag if the match was there), a matched negative criterion
  (red), or unmatched (grey, contributing 0). Turns the score from an
  opaque number into something a user can actually act on when tuning
  criteria.
- **Auto-recalculate after every scrape** (``runner.py``): new jobs get
  a real score the moment a run finishes, instead of "--" until someone
  remembers to click "Recalculate scores" in the web app. Safe
  unconditionally -- with no criteria defined, every score is just 0.0.
- **Default sort changed to match score, descending** (was
  ``scraped_at``) -- the jobs worth acting on are what's on screen by
  default, not buried behind a manual sort click every session.
- **Per-column filters gained a Gmail-style exclude syntax**: a leading
  ``-`` (e.g. ``-senior``) hides rows whose column contains the rest of
  the term, implemented as ``(column IS NULL OR column NOT LIKE ?)`` so
  ``NULL`` values aren't silently dropped by the exclusion.
- **Stale-listing visual cue**: the Posted column shows in orange when
  the text mentions "month(s)"/"year(s)" rather than days/hours/weeks --
  a coarse, deliberately-not-precise heuristic against free-text data
  ("11 months ago" isn't a real date), just enough to flag likely-dead
  listings without new backend logic.

**Found and fixed along the way, not part of the original ask**: while
verifying the score-breakdown feature end to end, the E2E suite hit
``sqlite3.ProgrammingError: SQLite objects created in a thread can only
be used in that same thread`` -- intermittently, on a route that had
existed unchanged for a while. Root cause: FastAPI's ``Depends(get_db)``
resolves the generator dependency and then calls the route handler as
two *separate* ``run_in_threadpool`` dispatches, which aren't guaranteed
to land on the same worker thread -- a well-documented FastAPI+SQLite
gotcha that had been silently latent in every route using this
dependency since Stage W1, not something the new endpoint introduced.
Fixed with ``check_same_thread=False`` in ``Database.__init__`` (safe
here since each connection is single-request-scoped, used by one thread
at a time) and locked in with a deterministic unit test rather than
trusting E2E scheduling to catch it again.

Verified with 14 new/changed backend unit tests (word-boundary matching,
title weighting, score breakdown, exclude filters, the cross-thread
fix), 2 new API tests for the score-breakdown endpoint, and a manual
Playwright pass against an isolated test instance with a copy of the
real database and its real criteria -- confirming the default sort shows
Score with its indicator, an exclude filter narrows 126 jobs to 65, the
score breakdown renders correctly (including a real "AI" match inside
"...AI is not used in our recruitment process..."), and the stale-listing
highlight correctly flags "2 months ago"/"11 months ago" postings.
Deferred from the original suggestion list (kept smaller, riskier, or
needing more design input): must-have/exclude criteria as a distinct
type, OR-groups for criteria, duplicate-listing detection, and bulk
status actions -- not started. The "next unreviewed job" review-loop
action and saved filter presets are both done -- see below.

**A second, genuine flaky-test investigation happened while finishing
this pass** -- worth recording since it's a real E2E-testing lesson, not
just a scoring one. ``test_column_filter_narrows_the_list`` failed on
roughly 1 run in 5 of the full E2E suite (never in isolation). First fix
attempt was wrong: wrapping the filter action in
``page.expect_response(lambda r: "/api/jobs?" in r.url)`` assumed exactly
one matching request per action, but React's effect dependencies (plus
``<StrictMode>``'s deliberate double-invoke of effects in dev mode) can
fire more than one ``/api/jobs`` request around a single state change --
the predicate matched *a* response, not reliably *the* response for that
specific filter value, so it occasionally resolved on a stale one and the
assertion saw the pre-filter count. Confirmed by finally reproducing the
exact failure (``assert 2 == 1``) rather than continuing to guess.
Correct fix: stopped trying to match a specific network response at all
and instead poll the *visible result* with Playwright's auto-retrying
``expect(locator).to_have_text(...)`` (new
``JobsPage.expect_total_count()``) -- robust to however many requests
fire underneath, since it only cares what ends up on screen. 5/5 clean
full-suite runs after the fix, versus roughly 1-in-5 failing before it.

Post-W5: "Next unreviewed job" review loop
----------------------------------------------

The next item off the deferred list above: a one-click way to move
through jobs in match-score order without hand-picking the next row from
the table each time.

- **Auto-mark-as-viewed on open** (``JobDetailPage.tsx``): loading a
  job's detail page while its status is still ``not_applied`` silently
  fires a background ``PATCH`` promoting it to ``viewed``. Best-effort --
  if it fails, the page still works, the job just stays ``not_applied``
  and gets offered again later. This is what keeps the "next" button
  from landing on the same job twice.
- **"Next unreviewed job" button** (``JobsPage.tsx``): calls the existing
  ``GET /api/jobs?status=not_applied&sort_by=match_score&sort_dir=DESC&limit=1``
  and navigates to whatever comes back, or shows an "All caught up"
  notification if nothing does. No backend changes needed -- the
  filter/sort/limit API already did everything this required; the
  feature is entirely a new way to call it.
- Both together turn "look at jobs" into a loop: click the button, the
  best unscored candidate opens and is immediately marked viewed, click
  the button again for the next one, until "All caught up".

Verified with 3 new E2E tests (``tests/e2e/test_review_loop.py``): the
auto-viewed transition persists across a reload (not just an optimistic
UI update), the button navigates to the correct not-applied job, and it
reports "All caught up" once the only not-applied seed job has been
viewed. No backend/unit tests were needed since no ``src``/backend code
changed. Full suite green: 98 fast + 14 E2E (up from 11) tests, all
passing.

Post-W5: Saved filter presets
----------------------------------

Another item off the deferred list: a way to save the current
status/text-filter/sort combination under a name and jump back to it,
instead of re-entering the same filters every session (e.g. "unreviewed,
best match first" vs "applied this week"). Pure frontend, no backend
changes -- presets are stored in ``localStorage`` (key
``jobs-filter-presets``) the same way column order/width already are,
deliberately *not* including layout in what a preset captures, since
layout isn't something a user switches back and forth between the way
they switch filter views.

UI (``JobsPage.tsx``, following the existing "inline row" convention used
for adding a criterion on the Criteria page rather than introducing a
modal): a "Load preset..." ``Select`` populated from the saved presets, a
"New preset name" text field plus "Save current filters as preset"
button (overwrites a same-named preset -- simpler than a separate
rename/overwrite-confirmation flow for a small, low-stakes list of
shortcuts), and a delete icon next to the loaded preset.

**A real, reproducible Mantine bug found and fixed while verifying this
end to end** -- not visible from a code read, only from actually clicking
through it in a browser: reselecting the *same* already-loaded preset
(e.g. after tweaking a filter by hand and wanting to snap back) silently
did nothing, or in one variant, cleared the filter entirely. Diagnosed
with a small throwaway Playwright script that printed the delete
button's visibility after each step (see ``docs/qa.rst``'s "Other QA
signals" for the full account) rather than guessing from the test
failure message alone:

- First hypothesis -- the ``clearable`` prop was causing a "click active
  option to deselect" toggle -- was wrong. Removing it changed nothing,
  confirmed by rerunning the same diagnostic script.
- Comparing "reselect the *same* preset" against "select a *different*
  preset" (the latter always worked) isolated the real cause: Mantine's
  ``Select`` defaults ``allowDeselect`` to ``true``, which fires
  ``onChange(null)`` when the clicked option already equals the current
  value -- independent of ``clearable``.
- Fixed with ``allowDeselect={false}``, plus clearing the preset
  selection on any manual filter edit (status, per-column text filters,
  min score, sort) so that reselecting the same preset afterward is a
  genuine value change (``null`` -> the preset's name) the ``Select``
  will actually call ``onChange`` for -- selecting an option that already
  equals the controlled value is otherwise a no-op, preset or not.

Verified with 3 new E2E tests (``tests/e2e/test_filter_presets.py``):
saving and reloading a preset restores its filter (including the
reselect-the-same-preset case that exposed the bug above), presets
persist across a reload, and deleting one removes it from the list. No
backend/unit tests needed since no ``src``/backend code changed. Full
suite green: 98 fast + 17 E2E (up from 14) tests, all passing.

Post-W5: More columns, interview dates & follow-up reminders
------------------------------------------------------------------

Prompted by a competitive comparison against other job trackers (Huntr,
Teal, Simplify) and self-hosted LinkedIn-scraper projects on GitHub --
see the conversation for the full list of what was considered and
deliberately not built (resume tailoring, a browser-extension autofill,
multi-source aggregation: all out of scope for what this tool is for).
Three concrete, scoped items came out of it:

- **Salary / Employment Type / Seniority / Applicants columns**
  (``JobsPage.tsx``): these fields were already scraped and stored (and
  already shown on the job detail page) but never surfaced as columns on
  the jobs table, so they weren't filterable or scannable across many
  jobs at once. Added as four more text-filterable columns, following
  the exact same pattern as the existing ones -- no new concepts, just
  more of what already existed. Backend: added to
  ``database.FILTERABLE_TEXT_COLUMNS`` and ``GET /api/jobs``'s query
  params/``column_filters`` map.
- **Interview date + follow-up reminder**: a job detail page now has an
  editable "Interview date" field (plain ``<input type="date">`` via
  Mantine's ``TextInput type="date"`` -- no new dependency) saved
  together with notes. Separately, ``Database.update_job_status()`` now
  stamps a new ``status_updated_at`` column every time a job's status is
  set (not on a notes-only update), and the detail page shows a
  "Consider following up" banner when a job has sat in ``applied`` for
  ``FOLLOW_UP_REMINDER_DAYS`` (14, a constant, not a setting -- same
  deliberately-coarse-heuristic philosophy as the "stale posting"
  highlight) with no status change since. No scheduler/notification
  system was built for this -- it's a passive banner the user sees next
  time they open that job, not a push alert; that bigger version was
  identified but explicitly deferred as a separate, larger piece of
  work.
- **Investigated, not fixed: job descriptions still looking like
  unreadable single-line text for some jobs.** This looked like a
  regression of the paragraph-break fix from the scoring pass, but
  checking the real ``output/jobs.db`` first (rather than assuming from
  the report) showed otherwise: of the 5 most recently scraped jobs (one
  scrape run, after the fix was already live), 4 had real line breaks
  (10-48 newlines each) and exactly 1 had none -- a 4071-character block
  with no ``\n``, ``\r``, bullet characters, or ``\xa0`` anywhere in the
  raw text. That specific posting was never rendered by LinkedIn as
  separate paragraphs or ``<br>``-delimited lines to begin with, so
  there's nothing in the DOM at scrape time for ``clean_description()``
  to preserve -- the same class of limitation already documented for
  jobs scraped before the fix existed, just showing up here for a
  different reason (the source posting itself has no structure, not a
  stale row). No code change made. See ``docs/qa.rst``'s "Other QA
  signals" for the exact numbers.

Verified with 8 new backend/API tests (status_updated_at stamping,
interview_date set/clear, the four new column filters) and 3 new E2E
tests: the four new columns render real job data
(``test_salary_employment_type_seniority_applicants_columns_show_job_data``),
the follow-up reminder shows for a job "applied" 20 days ago and not for
one applied 2 days ago (``tests/e2e/test_follow_up_reminder.py`` --
seeded via direct DB writes since the underlying condition is real
elapsed time, not something the UI can be driven into), plus the
existing notes/status E2E test extended to also cover the interview-date
field surviving a reload. Full suite green: 106 fast + 20 E2E (up from
98 + 17) tests, all passing.

Post-W5: CSV import, for a "Pi holds the canonical DB" deployment
----------------------------------------------------------------------

Prompted by a deployment plan: run scrapes wherever, but keep one
machine (a Raspberry Pi 4, in the case that prompted this) as the single
source of truth for the database the web app reads. Two ways to get a
remote scrape's results into that canonical DB were considered --
exposing the webapp itself over the network (rejected: this app has zero
authentication, built for a single local user, so WAN/LAN exposure is a
separate and much bigger piece of work than what follows here), and
pushing the *scraped data* to the Pi instead. The scraper already writes
a CSV every run (``export_csv()``); the missing half was reading one
back in.

- **``src/import_csv.py``** (new, same CLI shape as
  ``recalculate_scores.py``): reads a CSV in ``export_csv()``'s format
  and, for each row, calls ``Database.insert_job()`` -- the *exact* code
  path a live scrape uses, not a separate bulk-load query. That matters
  because it means a pushed row is subject to the same rules a locally-
  scraped one would be, automatically, with no new merge logic to keep
  in sync as those rules evolve.
- **``Database.insert_job()`` now returns ``bool``** (``True`` = new row
  inserted, ``False`` = ``job_id`` already existed and the
  ``INSERT OR IGNORE`` was a no-op) instead of implicitly ``None`` --
  additive and backward compatible, every existing call site already
  ignored the return value. This is what lets ``import_csv.py`` report
  accurate added/skipped counts without a separate ``job_exists()``
  lookup per row, and it's the guarantee the whole feature depends on:
  a job already in the target DB -- including any status/notes/
  interview-date you've since edited in the web app -- is left
  completely untouched by a re-import, never overwritten.
- Getting the CSV from the scraping machine to the Pi (scp, rsync,
  whatever triggers it) is deliberately outside this script's concern --
  it only handles what happens once the file is already there.

Verified with 9 new tests: 2 at the DB layer
(``test_insert_job_returns_true_when_the_row_is_new``,
``test_insert_job_returns_false_and_does_not_overwrite_an_existing_row``)
and 7 in the new ``tests/test_import_csv.py`` (the ``skills``/
``match_score`` string<->Python round trip, a full export-then-import
round trip through real temp files preserving every field, skipping an
already-known job, and adding only the new job out of a mixed batch).
Also smoke-tested manually end to end as the actual CLI (not just the
unit-tested functions): exported a small DB to CSV, ran
``python import_csv.py`` against a fresh target DB (2 added, 0 skipped),
ran it again unchanged (0 added, 2 skipped), and confirmed every field
-- including ``skills``, ``match_score``, and the target DB's own
``job_url`` backfill -- round-tripped correctly. No E2E tests needed
(no frontend/API-contract code changed). Full suite green: 115 fast + 20
E2E (up from 106 + 20), all passing.

Running the app (filled in as each stage lands)
------------------------------------------------

Backend (from the project root, venv active)::

    .venv\Scripts\python.exe -m uvicorn webapp.backend.main:app --reload

Docs at ``http://127.0.0.1:8000/docs`` (FastAPI's automatic Swagger UI --
useful for poking at the API before the frontend exists). Health check at
``/api/health``.

Backend tests::

    .venv\Scripts\python.exe -m pytest tests/webapp_api/

Frontend (separate terminal, backend must already be running)::

    cd webapp/frontend
    npm install      # first time only
    npm run dev

Opens on ``http://localhost:5173`` (any ``localhost``/``127.0.0.1`` port
is allowed by CORS, see ``webapp/backend/main.py``, so a different port
works too). ``webapp/frontend/.env`` controls ``VITE_API_URL`` if the
backend isn't on the default ``http://127.0.0.1:8000``.

Playwright E2E tests (``tests/e2e/``) start their own backend + frontend
as subprocesses on dynamically-picked free ports -- no manual server
startup needed::

    .venv\Scripts\python.exe -m pytest tests/e2e/ -v

This requires Playwright's own browser binaries (unlike the scraper,
which launches your installed Chrome) -- if this is a fresh environment::

    playwright install chromium

Excluded from the default ``pytest tests/`` run (see :doc:`qa`) since it
needs Node/npm and takes noticeably longer -- run it explicitly, and
before considering frontend or API-contract changes done.

Stopping either one is just ``Ctrl+C`` in its terminal (backend and
frontend are independent processes -- stopping one leaves the other
running, which shows up as the frontend's page loading fine but every
API call failing). See :doc:`installation`'s "Stopping the app" for the
full explanation and the command to use when the process is detached and
there's no terminal to ``Ctrl+C`` in.
