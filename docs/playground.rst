Poking at the database
=======================

Two ways to inspect or edit ``output/jobs.db`` by hand: the raw
``sqlite3`` CLI (read/write any column, no project code involved), or a
Python console using the project's own ``Database`` class (gets you the
typed helpers -- ``update_job_status``, ``get_jobs_filtered``, criteria
CRUD, ``bulk_update_scores`` -- instead of hand-written SQL).

.. warning::

   ``output/jobs.db`` is your real scraped data. If you want to
   experiment without risk, copy it first and point the examples below
   at the copy, e.g.::

       Copy-Item output\jobs.db output\jobs.playground.db

   Every example below uses ``output/jobs.db`` directly for brevity --
   swap in a copy's path if you're just exploring.

sqlite3 CLI
------------

Windows ships a ``sqlite3.exe`` with some Python installs; if you don't
have one on PATH, the Python console examples below need no separate
install. Assuming you do::

    sqlite3 output\jobs.db

Then, inside the ``sqlite>`` prompt::

    .headers on
    .mode column

    -- how many jobs, by status
    SELECT application_status, COUNT(*) FROM jobs GROUP BY application_status;

    -- top 10 by match score
    SELECT title, company, match_score FROM jobs
    ORDER BY match_score DESC LIMIT 10;

    -- mark one job as applied, by hand
    UPDATE jobs SET application_status = 'applied', notes = 'Applied via referral'
    WHERE job_id = '4457497582';

    -- see the current scoring criteria
    SELECT term, weight, enabled FROM match_criteria;

    .quit

Python console
----------------

Run from the project root, with the venv active
(``.venv\Scripts\Activate.ps1``)::

    .venv\Scripts\python.exe

.. code-block:: python

    import sys
    sys.path.insert(0, "src")

    from database import Database
    from models import ApplicationStatus

    db = Database("output/jobs.db")

    # --- read ---
    db.count_jobs()
    db.get_status_counts()
    db.get_job("4457497582")                       # one job by id
    db.get_jobs_filtered(status="applied")          # filtered list
    db.get_jobs_filtered(sort_by="match_score", sort_dir="DESC", limit=10)

    # --- edit a job's status/notes ---
    db.update_job_status(
        "4457497582",
        status=ApplicationStatus.APPLIED,
        notes="Applied via referral, waiting to hear back",
    )

    # --- manage match-scoring criteria ---
    db.add_criterion("AI", weight=3.0)
    db.add_criterion("manual", weight=-1.0)         # negative weight = penalty
    db.get_criteria()
    db.update_criterion(1, weight=5.0)              # by id, from get_criteria()
    db.delete_criterion(2)

    db.close()

After changing criteria, recompute scores for every job in one shot
(no re-scraping) with the standalone CLI command::

    .venv\Scripts\python.exe src\recalculate_scores.py

    # or against a specific DB file:
    .venv\Scripts\python.exe src\recalculate_scores.py --db output\jobs.playground.db

Merging in a CSV from another machine
----------------------------------------

For a setup where one machine holds the canonical database and scrapes
happen elsewhere (e.g. a Raspberry Pi as the always-on "core" machine,
a laptop doing the actual scraping and pushing its ``output/jobs.csv``
over by scp/rsync/whatever afterwards) -- ``import_csv.py`` merges a CSV
in ``export_csv()``'s format into a target database through the same
``Database.insert_job()`` path a live scrape uses::

    .venv\Scripts\python.exe src\import_csv.py path\to\jobs.csv

    # or against a specific DB file:
    .venv\Scripts\python.exe src\import_csv.py path\to\jobs.csv --db output\jobs.playground.db

A ``job_id`` already in the target database -- including any status,
notes, or interview date edited since in the web app -- is left
completely untouched; only genuinely new job ids are added. Getting the
CSV onto this machine in the first place is outside this script's
concern.

Available statuses
--------------------

``application_status`` is a closed set (``src/models.py``,
``ApplicationStatus``) -- any other value is rejected by the ``Database``/
``Job`` layer, though raw ``sqlite3``/SQL edits bypass that validation, so
stick to these values by hand too:

- ``not_applied`` (default)
- ``viewed``
- ``applied``
- ``interview``
- ``rejected``
- ``offer``
- ``ignored``
