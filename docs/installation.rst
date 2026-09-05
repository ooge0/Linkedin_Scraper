Installation
=============

This page is the single source of truth for getting the project running
from a fresh clone -- both the scraper and the web app. If it drifts from
reality, fix it here rather than re-explaining setup in a chat or a
README that nobody re-reads.

Prerequisites
---------------

- **Python** (developed against 3.14) and **Google Chrome installed** --
  the scraper launches Chrome directly via Playwright's ``channel="chrome"``
  (see ``src/login.py`` / ``src/scraper.py``), not a Playwright-managed
  browser, so Chrome itself must already be on the machine.
- **Node.js + npm** -- only needed for the web app's frontend
  (``webapp/frontend``). Not required for the scraper alone.

Commands below are PowerShell, matching the rest of this project's docs.
On macOS/Linux, replace ``.venv\Scripts\Activate.ps1`` with
``source .venv/bin/activate`` and ``.venv\Scripts\python.exe`` with
``.venv/bin/python``.

Scraper setup
---------------

1. From the repository root, create and activate a virtual environment::

       python -m venv .venv
       .venv\Scripts\Activate.ps1

2. Install Python dependencies (this covers the scraper, the test suite,
   the FastAPI backend, and the Sphinx docs tooling -- everything in
   ``requirements.txt`` is one shared environment, not separate ones)::

       pip install -r requirements.txt

3. (Optional) install Playwright's own browser binaries::

       playwright install

   Not required for normal use -- step 2 above already gets you a working
   scraper, since it launches the Chrome you already have installed
   rather than a Playwright-managed one. Only needed if you later change
   ``login.py``/``scraper.py`` to launch a Playwright-managed browser
   instead of ``channel="chrome"``.

4. One-time login bootstrap -- opens a real, visible Chrome window; log
   in to LinkedIn manually, then close the window or press Enter in the
   terminal::

       .venv\Scripts\python.exe src\login.py

5. Run the scraper::

       .venv\Scripts\python.exe src\runner.py

See :doc:`overview` for what a run actually does and the full list of
CLI flags (``--pages``, ``--relogin``, ``--since``, ``--json``), and
``CLAUDE.md``'s Configuration Reference for every tunable in
``src/config.py``.

Web app setup
---------------

The backend's Python dependencies (FastAPI, uvicorn, httpx) are already
installed by step 2 above -- they're in the same ``requirements.txt``,
not a separate install. Only the frontend needs its own.

1. Start the backend (a separate terminal, venv active, from the repo
   root)::

       .venv\Scripts\python.exe -m uvicorn webapp.backend.main:app --reload

   Confirm it's up at ``http://127.0.0.1:8000/api/health``, or browse the
   interactive API docs at ``http://127.0.0.1:8000/docs``.

2. Install and start the frontend (another separate terminal)::

       cd webapp/frontend
       npm install
       npm run dev

   ``webapp/frontend/.env`` already exists (copied from ``.env.example``
   the first time this project was set up) and points ``VITE_API_URL`` at
   ``http://127.0.0.1:8000`` -- change it if the backend runs somewhere
   else. If it's ever missing, recreate it with::

       Copy-Item webapp\frontend\.env.example webapp\frontend\.env

3. Open ``http://localhost:5173`` (the CORS policy in
   ``webapp/backend/main.py`` allows any ``localhost``/``127.0.0.1`` port,
   not just 5173, so a different port works too if 5173 is taken).

Stopping the app
~~~~~~~~~~~~~~~~~~

The backend and frontend are two independent processes -- stopping one
doesn't stop the other. This matters because the frontend is *just* a
static dev server: it keeps serving the React app (the page, the table,
the buttons) even with the backend dead, so the symptom of "backend
stopped, frontend still running" isn't a blank page -- it's a normal-
looking page with `Error: Failed to load jobs` where the data should be,
because every ``fetch`` the page makes to ``VITE_API_URL`` has nothing to
answer it. See the "Failed to load jobs" entry in ``CLAUDE.md``'s
Debugging Checklist for the full diagnostic if that happens unexpectedly
rather than because you stopped something on purpose.

To stop either one:

- **If it's running in a terminal you're looking at**: ``Ctrl+C``. With
  ``--reload`` on the backend, Windows sometimes needs it twice -- once
  for the reloader process, once for the actual worker.
- **If it's detached and you don't have that terminal** (find the PID by
  the port it's on, then kill it)::

      Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess
      Stop-Process -Id <PID> -Force

  (swap ``8000`` for ``5173`` to stop the frontend instead). The
  ``netstat``/``taskkill`` equivalent, if ``Get-NetTCPConnection`` isn't
  available::

      netstat -ano | findstr :8000
      taskkill /F /PID <PID>

See :doc:`roadmap` for the full architecture, API surface, and build
status.

Running the tests
--------------------

The fast suite (no Node/npm, no real browser -- a few seconds)::

    .venv\Scripts\python.exe -m pytest tests/ --ignore=tests/e2e -v

With coverage::

    .venv\Scripts\python.exe -m pytest tests/ --ignore=tests/e2e --cov=src --cov=webapp/backend --cov-report=term-missing

The Playwright E2E suite (needs Node/npm, and Playwright's browser
binaries -- ``playwright install chromium`` if this is a fresh
environment; starts its own backend/frontend, no manual server startup
needed)::

    .venv\Scripts\python.exe -m pytest tests/e2e/ -v

See :doc:`qa` for what's covered, how the test suite is organized, and
why some modules are deliberately not chasing high coverage numbers.

.. _allure-test-reports:

Allure test reports
----------------------

``allure-pytest`` is already in ``requirements.txt`` -- it just needs
somewhere to write results, and a viewer to turn them into a report.

1. Install the Allure commandline tool (one-time; uses the Node/npm
   already required for the frontend, so no new prerequisite)::

       npm install -g allure-commandline

2. Run the suite(s) you want in the report, writing to the same results
   directory -- Allure merges multiple runs into one report, so running
   the fast suite and the E2E suite this way produces a single combined
   report covering all of it::

       .venv\Scripts\python.exe -m pytest tests/ --ignore=tests/e2e --alluredir=allure-results
       .venv\Scripts\python.exe -m pytest tests/e2e/ --alluredir=allure-results

3. Generate and open the report::

       allure serve allure-results

   (or ``allure generate allure-results -o allure-report --clean`` to
   write static HTML without opening a browser). Both ``allure-results/``
   and ``allure-report/`` are generated output -- gitignored, not
   committed.

Building this documentation
------------------------------

::

    .venv\Scripts\python.exe -m sphinx -b html docs docs/_build/html

Output lands in ``docs/_build/html/index.html``.
