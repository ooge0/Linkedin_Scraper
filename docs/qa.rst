QA & Testing
=============

This page is regenerated from the actual test suite, not hand-maintained
prose -- the numbers below (126 tests, coverage percentages) came from
running ``pytest`` and ``pytest --cov`` directly against this codebase.
If they look stale, re-run the commands in `Test coverage`_ and update
this page rather than trusting it blindly.

Testing philosophy
--------------------

Each behavior is tested **once, at the layer where it actually lives** --
deliberately, not by omission:

.. mermaid::

   flowchart TD
       L1["Pure-logic unit tests<br/>(BDD + plain pytest)<br/>URL building, id extraction, text parsing,<br/>title filtering, rate limiting, scoring math"]
       L2["DB-layer unit tests<br/>filter/sort/paginate, status updates,<br/>criteria CRUD, bulk score writes"]
       L3["API-layer integration tests<br/>HTTP status codes, request/response shape,<br/>wiring between routes and the DB layer"]
       L4["E2E (Playwright + Page Object Model)<br/>real backend + frontend as subprocesses,<br/>a real browser driving the actual UI"]
       L1 --> L2 --> L3 --> L4

- **Layer 1-2** (``tests/test_scraper_bdd.py``, ``tests/test_human_behaviour.py``,
  ``tests/test_rate_limiting_bdd.py``, ``tests/backend/``) test scraper
  logic and the database directly, with no HTTP or browser involved.
- **Layer 3** (``tests/webapp_api/``) does **not** re-test filtering/
  sorting/scoring correctness -- that's already proven at Layer 2. It only
  checks that the FastAPI routes parse requests correctly, call the right
  DB method, and return the right status code and shape. See the comment
  at the top of ``tests/webapp_api/test_jobs_api.py``.
- **Layer 4** (``tests/e2e/``) does **not** re-test HTTP status codes or
  request validation -- that's already proven at Layer 3. It only checks
  that the React UI actually renders the data, wires up user actions to
  the right API calls, and reflects the result -- the part no lower layer
  can see, since it's the only layer with a real browser and a real
  ``fetch()`` call in it. Excluded from the default ``pytest tests/``
  run (see `Test inventory`_) since it needs Node/npm and takes longer;
  run it explicitly with ``pytest tests/e2e/``.
- Live browser-orchestration code in ``scraper.py`` (the actual Playwright
  clicking/scrolling/navigation) and the interactive ``login.py`` flow are
  intentionally **not** unit-tested -- they're exercised by running the
  real thing against LinkedIn, with heavy diagnostic logging
  (``SELECTOR HIT``/``MISS``, page snapshots, the block detector) as the
  safety net instead. Every parsing/decision rule *inside* those flows
  (title filtering, id extraction, applicant-count parsing, ...) is
  pulled out into a plain function and unit-tested at Layer 1 -- see the
  traceability matrix below for exactly which ones.

Given-When-Then scenarios (``tests/features/*.feature``) are used for
scraper and rate-limiting behavior specifically because those are the
rules most likely to need re-explaining to a future reader (or a future
me) months later; the newer backend/scoring/API tests are plain pytest,
since their behavior is already obvious from the function they're named
after.

Test inventory
----------------

126 tests total, across 14 files: 106 fast ones (no Node/npm, no real
browser) plus 20 E2E ones. Run the fast suite with::

    .venv\Scripts\python.exe -m pytest tests/ --ignore=tests/e2e -v

E2E is excluded from that command on purpose (it needs Node/npm installed
and takes noticeably longer -- ~13-20s versus ~3s). Run it explicitly,
and before considering a frontend or API-contract change done::

    .venv\Scripts\python.exe -m pytest tests/e2e/ -v

Scraper behavior -- ``tests/test_scraper_bdd.py`` (23 tests, BDD)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Backed by ``tests/features/scraper.feature``. Covers: search URL
building, job persistence/dedup, CSV export, run statistics, block-page
detection, job-id extraction, canonical URL building, page-count limits,
scroll-to-load card discovery, result-batch preservation after opening a
job, region (geoId) filtering, applicant/posted-date text parsing, and
title-based skip/must-keyword filtering.

Rate limiting -- ``tests/test_rate_limiting_bdd.py`` (3 tests, BDD)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Backed by ``tests/features/rate_limiting.feature``. Covers the sliding
hourly window in ``rate_limiter.py``: allowed under the cap, denied at the
cap, allowed again once the window has elapsed.

Human-behavior helpers -- ``tests/test_human_behaviour.py`` (5 tests)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The randomized parts of ``utils.py`` (``human_scroll``,
``maybe_distraction_pause``) tested for their *statistical* contract
(a skip/skim/scroll-back chance exists and fires within its stated
probability), not for producing an exact sequence.

Text cleaning -- ``tests/test_utils_text.py`` (7 tests)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``clean_description()`` specifically: preserves single line breaks and
paragraph gaps, collapses runs of 3+ blank lines to one, normalizes
horizontal whitespace without touching line breaks, and handles
``\xa0``/empty input -- see the traceability matrix for the bug this
exists to fix.

Database layer -- ``tests/backend/test_database_extensions.py`` (34 tests)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Direct ``Database`` class tests against a temp SQLite file: job lookup,
partial status/notes/interview-date updates (incl. that setting a status
stamps ``status_updated_at``, that a notes-only update does *not*, and
that an empty-string ``interview_date`` clears it rather than being
treated as "leave alone" -- same convention as ``notes``),
filter/sort/paginate (incl. the per-column ``column_filters`` map backing
the Jobs page's filter row -- including ``salary``/``employment_type``/
``seniority``/``applicants``, its Gmail-style ``-term`` exclude syntax,
that it doesn't drop ``NULL`` column values, and that an unwhitelisted
column name is rejected), status-count zero-filling, full match-criteria
CRUD + bulk score writes, the two backfills that repair rows saved before
a given piece of parsing existed (``job_url``, and
``location_entity``/``posted``/``applicants`` -- see the traceability
matrix below), that the DB opens in WAL journal mode (needed so the web
app and the scraper can share ``output/jobs.db`` without a web app read
blocking on the scraper's writer), and that a ``Database`` can be used
from a different thread than it was created on (deterministic regression
test for a real intermittent E2E failure -- see the concurrency rows in
the traceability matrix for both).

Match scoring -- ``tests/backend/test_scoring.py`` (11 tests)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pure-function tests for ``scoring.py``: weight contribution, zero-match
and zero-positive-weight edge cases (no divide-by-zero), full-match
scoring, clamping at 100 even with a penalty criterion present, matches
are whole-word not substring (the false-positive bug this fixed -- see
the traceability matrix), a title match scoring higher than the same term
in the body, ``score_breakdown()`` reporting per-criterion match/title
detail, and the ``skills`` field's two shapes (a list from a
freshly-scraped ``Job``, a comma-joined string from a DB row).

Web app API -- ``tests/webapp_api/`` (23 tests)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``test_jobs_api.py`` (17): list/filter jobs (incl. a per-column filter,
that ``location`` maps to ``location_entity``, and the new
``salary``/``employment_type``/``seniority``/``applicants`` filters),
reject an unknown sort column, get/update/delete a job, that
``interview_date`` persists through a ``PATCH`` and that setting a status
stamps ``status_updated_at`` in the response, 404s on unknown ids, stats,
and the score-breakdown endpoint (matched/unmatched criteria, 404 on
unknown job). ``test_criteria_api.py`` (6): add/list/update/delete a
criterion, 404 on an unknown id, and recalculate-scores actually changing
a job's stored ``match_score``.

Web app E2E -- ``tests/e2e/`` (20 tests, Playwright + Page Object Model)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A real backend and frontend, started as subprocesses per test session
(``tests/e2e/conftest.py``) against a database reseeded with two known
jobs before every test, driven by a real (headless) browser. Page Object
classes live in ``tests/e2e/pages/`` -- one per page
(``JobsPage``/``JobDetailPage``/``CriteriaPage``), each exposing intent-
named methods (``filter_by_status``, ``open_job``, ``recalculate``, ...)
so the test files themselves read as scenarios, not selector soup.

``test_jobs_list.py`` (4): the list renders seeded jobs, status and
per-column filters narrow the result count, a status edit persists after
a reload. ``test_job_detail.py`` (2): opening a job from the list,
editing its notes, interview date, and status and having all three
survive a reload, and the "back to jobs" link. ``test_criteria.py`` (2):
adding a criterion and recalculating actually changes a job's displayed
match score; deleting a criterion removes it. ``test_jobs_table_layout.py``
(4): the jobs table renders every expected column (now including
Salary/Employment Type/Seniority/Applicants) in the right order, those
four new columns show the seeded job's actual data, dragging a column's
resize handle actually changes its rendered width, and dragging a column
header onto another actually reorders them. ``test_review_loop.py`` (3):
opening a job's detail page silently promotes it from "not applied" to
"viewed" (and that survives a reload), the "Next unreviewed job" button
navigates to a not-applied job, and it shows an "All caught up" message
once none are left. ``test_filter_presets.py`` (3): saving the current
filters as a named preset and loading it back restores them (including
after manually changing the filter away and reselecting the *same*
preset -- see the traceability matrix for the Mantine ``Select`` bug this
caught), presets persist across a reload, and deleting a preset removes
it from the list. ``test_follow_up_reminder.py`` (2): a job "applied" 20
days ago with no status change since shows the "consider following up"
reminder; one applied 2 days ago doesn't -- seeded via direct DB writes
(the natural aging can't happen inside a test), not the shared
``seeded_db`` fixture other tests depend on for its exact job count/
statuses.

Traceability matrix
----------------------

Maps user-facing behavior to the test(s) that would fail if it broke.
Anything not listed here (mainly: the live Playwright browser-driving
code *in the scraper*, and ``login.py``'s interactive flow) isn't covered
by an automated test -- see *Testing philosophy* above for how those are
verified instead. The React UI itself **is** covered, at the bottom of
this table, by the E2E suite.

.. list-table::
   :header-rows: 1
   :widths: 40 40 20

   * - Behavior
     - Test(s)
     - Suite
   * - Search URL reflects keyword/location/remote/easy-apply/posted filters
     - ``test_build_a_search_url_with_selected_filters``
     - scraper BDD
   * - A job is never saved/opened twice (dedup by job_id)
     - ``test_persist_a_job_only_once``
     - scraper BDD
   * - Canonical job URL built from job_id (and empty when there's no id)
     - ``test_build_a_canonical_job_url_from_a_job_id``,
       ``test_building_a_canonical_job_url_from_a_missing_job_id_gives_an_empty_string``,
       ``test_insert_job_persists_the_canonical_job_url``
     - scraper BDD + DB
   * - job_id extracted correctly from the SPA search URL
     - ``test_extract_a_job_id_from_a_spa_search_url``
     - scraper BDD
   * - Page-count limit (``--pages`` / ``MAX_PAGES``) is respected
     - ``test_respect_the_requested_result_page_count``
     - scraper BDD
   * - Cards beyond the initially-rendered viewport are found (scroll-to-load)
     - ``test_discover_cards_beyond_the_initially_rendered_viewport``
     - scraper BDD
   * - The result batch survives reloading the list after opening a job
     - ``test_preserve_the_current_result_batch_when_reloading_after_a_job``
     - scraper BDD
   * - Region filter (geoId) applied only when a region is actually selected
     - ``test_force_the_search_region_via_geoid``,
       ``test_leave_the_region_unforced_when_no_region_is_selected``
     - scraper BDD
   * - One summary line splits correctly into location/posted/applicants
       (incl. promoted-listing tags and trailing insight text glued on)
     - ``test_split_a_summary_line_into_location_posted_date_and_applicant_count``,
       ``test_trim_a_promotedlisting_tag_glued_onto_the_applicant_count``,
       ``test_recognize_the_people_clicked_apply_variant_of_the_applicant_count``,
       ``test_trim_trailing_insight_text_glued_directly_to_the_applicant_count``
     - scraper BDD
   * - Title pre-filter (skip/must keywords, skip takes priority)
     - ``test_keep_a_card_whose_title_matches_no_skip_keyword``,
       ``test_skip_a_card_whose_title_matches_a_skip_keyword``,
       ``test_skip_a_card_that_matches_no_mustkeyword_when_mustkeywords_are_set``,
       ``test_keep_a_card_that_matches_a_mustkeyword``,
       ``test_skip_keywords_take_priority_over_mustkeywords``
     - scraper BDD
   * - Block/CAPTCHA page detected from visible text, not internal markup
     - ``test_ignore_internal_verification_markup_on_a_normal_search_page``,
       ``test_detect_a_visible_security_verification_page``
     - scraper BDD
   * - Job description line/paragraph breaks are preserved, not flattened into one run-on blob (bug: LinkedIn sometimes renders a description as one ``<p>`` with ``<br>`` tags instead of several ``<p>`` elements; ``clean_text()``'s blanket whitespace collapse ate the ``<br>``-based breaks along with incidental whitespace)
     - ``test_preserves_single_line_breaks``,
       ``test_preserves_paragraph_breaks``,
       ``test_collapses_three_or_more_blank_lines_to_one``,
       ``test_normalizes_horizontal_whitespace_without_touching_line_breaks``
     - text cleaning unit
   * - CSV export writes every stored job
     - ``test_export_stored_jobs_to_csv``
     - scraper BDD
   * - Run statistics (pages/cards/saved/skipped/errors) are preserved for reporting
     - ``test_preserve_scraper_statistics_for_reporting``
     - scraper BDD
   * - Scroll behavior varies (can skip, varies step count, can scroll back up)
     - ``test_human_scroll_can_skip_entirely``,
       ``test_human_scroll_scrolls_the_requested_number_of_steps``,
       ``test_human_scroll_can_scroll_back_up``
     - human behaviour
   * - Distraction pause fires within its stated probability, not outside it
     - ``test_maybe_distraction_pause_fires_below_threshold``,
       ``test_maybe_distraction_pause_does_not_fire_above_threshold``
     - human behaviour
   * - Hourly rate cap: allow under cap, deny at cap, allow again after the window elapses
     - ``test_allow_actions_while_under_the_hourly_cap``,
       ``test_deny_actions_once_the_hourly_cap_is_reached``,
       ``test_allow_actions_again_once_the_window_has_fully_elapsed``
     - rate limiting BDD
   * - ``update_job_status`` only touches the field(s) given, no-ops with none, false on unknown id
     - ``test_update_job_status_updates_only_status``,
       ``test_update_job_status_updates_only_notes``,
       ``test_update_job_status_no_args_is_a_no_op``,
       ``test_update_job_status_returns_false_for_unknown_job``
     - DB unit
   * - Job list filter/sort/paginate, incl. rejecting an unknown sort column
     - ``test_get_jobs_filtered_by_status``,
       ``test_get_jobs_filtered_by_search_term``,
       ``test_get_jobs_filtered_rejects_unknown_sort_column``,
       ``test_count_jobs_filtered_matches_get_jobs_filtered``
     - DB unit
   * - Per-column filter row (Jobs page): single and combined column filters match correctly, and a column name outside the whitelist is rejected rather than reaching raw SQL
     - ``test_get_jobs_filtered_by_column_filter``,
       ``test_get_jobs_filtered_combines_multiple_column_filters``,
       ``test_get_jobs_filtered_rejects_a_column_not_in_the_filter_whitelist``,
       ``test_count_jobs_filtered_respects_column_filters``
     - DB unit
   * - Status counts always include every known status, zero-filled
     - ``test_get_status_counts_zero_fills_unused_statuses``
     - DB unit
   * - Match-criteria CRUD (add, list enabled-only, partial update, delete)
     - ``test_add_and_get_criteria``,
       ``test_get_criteria_enabled_only_excludes_disabled``,
       ``test_update_criterion_partial_update``,
       ``test_delete_criterion``
     - DB unit
   * - Bulk score writes touch every row in one transaction; score is null until scored
     - ``test_bulk_update_scores_writes_all_rows``,
       ``test_match_score_defaults_to_null_until_scored``
     - DB unit
   * - Rows saved before ``job_url`` existed get backfilled with it from ``job_id`` (a pure function -- no re-scrape needed)
     - ``test_backfill_populates_missing_job_url_from_job_id``
     - DB unit
   * - Rows saved before ``location_entity``/``posted``/``applicants`` parsing existed get backfilled from the raw ``location`` text already stored -- and rows already parsed are left untouched
     - ``test_backfill_parses_location_meta_from_raw_location``,
       ``test_backfill_does_not_touch_rows_already_parsed``
     - DB unit
   * - The DB opens in WAL journal mode, so a web app read doesn't block on (or get blocked by) the scraper's writer sharing the same file
     - ``test_database_uses_wal_journal_mode``
     - DB unit
   * - A Database connection survives being used from a different thread than it was created on (FastAPI's Depends(get_db) resolves the dependency and calls the route handler as two separate threadpool dispatches, not guaranteed to be the same thread -- hit this for real, intermittently, in the E2E suite)
     - ``test_database_can_be_used_from_a_different_thread_than_it_was_created_on``
     - DB unit
   * - Per-column filter row supports excluding with a leading "-" (Gmail-style), without dropping rows whose column value is NULL
     - ``test_get_jobs_filtered_excludes_with_a_leading_dash``,
       ``test_get_jobs_filtered_exclude_filter_does_not_drop_null_column_values``
     - DB unit
   * - Match-score math: weights, full-match, clamping at 100, zero-division safety
     - ``test_matched_terms_contribute_their_weight``,
       ``test_no_criteria_matched_gives_zero``,
       ``test_no_positive_weight_criteria_gives_zero_without_dividing_by_zero``,
       ``test_all_terms_matched_gives_full_score``,
       ``test_score_is_clamped_to_100_even_with_a_negative_weight_criterion``
     - scoring unit
   * - Criteria match on whole words, not substring (bug: "ai" matched inside "detail"/"remain"/... on 122 of 126 real scraped jobs even though only 76 actually contain the word "AI")
     - ``test_matches_are_whole_word_not_substring``
     - scoring unit
   * - A term matched in the job title scores higher than the same term matched only in the body
     - ``test_matching_in_the_title_scores_higher_than_matching_in_the_body``
     - scoring unit
   * - ``score_breakdown()`` reports whether each criterion matched and whether the match was in the title -- the same function calculate_score() itself sums, so the two can't disagree
     - ``test_score_breakdown_reports_whether_each_criterion_matched_and_where``
     - scoring unit
   * - Scoring text builder splits title from description+skills, handles both skills shapes and missing fields
     - ``test_build_job_text_splits_title_from_description_and_skills``,
       ``test_build_job_text_accepts_comma_joined_string_skills``,
       ``test_build_job_text_handles_missing_fields``
     - scoring unit
   * - API: job list/filter/sort wired correctly over HTTP (incl. 400 on bad sort column)
     - ``test_list_jobs_returns_seeded_jobs``,
       ``test_list_jobs_filters_by_status``,
       ``test_list_jobs_rejects_unknown_sort_column``
     - webapp API
   * - API: per-column filter query params reach the DB layer correctly, incl. ``location`` mapping to ``location_entity``
     - ``test_list_jobs_filters_by_column_filter``,
       ``test_list_jobs_filters_by_location_column_maps_to_location_entity``
     - webapp API
   * - API: job detail/update/delete, incl. 404s and "at least one field" validation
     - ``test_get_job_by_id``,
       ``test_get_job_404_for_unknown_id``,
       ``test_update_job_status_and_notes_persists``,
       ``test_update_job_requires_at_least_one_field``,
       ``test_update_job_404_for_unknown_id``,
       ``test_delete_job_removes_it``
     - webapp API
   * - API: stats endpoint reflects real status counts
     - ``test_stats_reflects_seeded_statuses``
     - webapp API
   * - API: criteria CRUD over HTTP, incl. 404s and validation
     - ``test_add_and_list_criteria``,
       ``test_update_criterion``,
       ``test_update_criterion_requires_at_least_one_field``,
       ``test_update_criterion_404_for_unknown_id``,
       ``test_delete_criterion`` in ``webapp_api/test_criteria_api.py``
       (same name, different test, from ``backend/test_database_extensions.py``
       above)
     - webapp API
   * - API: recalculate-scores actually updates stored scores for matching/non-matching jobs
     - ``test_recalculate_scores_updates_matching_jobs``
     - webapp API
   * - API: score-breakdown endpoint reports matched/unmatched criteria for a job, 404s on an unknown one
     - ``test_score_breakdown_reports_matched_and_unmatched_criteria``,
       ``test_score_breakdown_404_for_unknown_job``
     - webapp API
   * - UI: jobs list renders real data, status and per-column filters change what's shown
     - ``test_jobs_list_shows_seeded_jobs``,
       ``test_filter_by_status_narrows_the_list``,
       ``test_column_filter_narrows_the_list``
     - E2E
   * - UI: a status edit made in the list actually reaches the API and survives a reload
     - ``test_status_change_persists_after_reload``
     - E2E
   * - UI: opening a job navigates to its detail page; notes and status edits reach the API and survive a reload
     - ``test_open_job_detail_and_edit_notes_and_status``
     - E2E
   * - UI: "back to jobs" returns to the list
     - ``test_back_to_jobs_link_returns_to_the_list``
     - E2E
   * - UI: adding a criterion and clicking "Recalculate scores" changes a job's displayed match score
     - ``test_add_criterion_and_recalculate_updates_match_score``
     - E2E
   * - UI: deleting a criterion removes it from the list
     - ``test_delete_criterion_removes_it``
     - E2E
   * - UI: jobs table renders every expected column (incl. Job ID, Search Location, read-only Notes) in the right order
     - ``test_jobs_table_shows_all_expected_columns``
     - E2E
   * - UI: dragging a column's resize handle changes its rendered width
     - ``test_resizing_a_column_changes_its_width``
     - E2E
   * - UI: dragging a column header onto another reorders the columns
     - ``test_dragging_a_column_header_reorders_it``
     - E2E
   * - API: job responses expose ``search_location`` (the search filter active when the job was found), distinct from the job's own ``location``/``location_entity``
     - ``test_get_job_by_id``
     - webapp API
   * - UI: opening a job's detail page silently marks a "not applied" job "viewed", and that survives a reload
     - ``test_opening_a_job_marks_it_viewed``
     - E2E
   * - UI: "Next unreviewed job" navigates to a not-applied job; reports "All caught up" once none are left
     - ``test_next_unreviewed_job_navigates_to_a_not_applied_job``,
       ``test_next_unreviewed_job_reports_when_none_are_left``
     - E2E
   * - UI: saving the current filters as a named preset and loading it back restores status/text-filter/sort state, including re-loading the same preset after a manual filter change
     - ``test_saving_and_loading_a_preset_restores_its_filter``
     - E2E
   * - UI: filter presets persist across a reload; deleting one removes it from the list
     - ``test_presets_persist_across_a_reload``,
       ``test_deleting_a_preset_removes_it_from_the_list``
     - E2E
   * - DB/API: setting a job's status stamps ``status_updated_at``; a notes-only update does not
     - ``test_update_job_status_stamps_status_updated_at``,
       ``test_update_job_status_does_not_stamp_status_updated_at_for_notes_only``,
       ``test_update_job_status_stamps_status_updated_at_in_the_response``
     - DB unit + webapp API
   * - DB/API: ``interview_date`` can be set and cleared (empty string), independent of status/notes
     - ``test_update_job_status_updates_only_interview_date``,
       ``test_update_job_status_interview_date_empty_string_clears_it``,
       ``test_update_job_interview_date_persists``
     - DB unit + webapp API
   * - DB/API: jobs list can be filtered by salary/employment_type/seniority/applicants
     - ``test_get_jobs_filtered_by_salary_employment_type_seniority_applicants``,
       ``test_list_jobs_filters_by_salary_employment_type_seniority_applicants``
     - DB unit + webapp API
   * - UI: jobs table shows Salary/Employment Type/Seniority/Applicants columns with the job's actual data
     - ``test_salary_employment_type_seniority_applicants_columns_show_job_data``
     - E2E
   * - UI: job detail page shows a "consider following up" reminder for a job applied 14+ days ago with no status change; not for a recent one
     - ``test_follow_up_reminder_shown_after_14_days_with_no_status_change``,
       ``test_no_follow_up_reminder_for_a_recently_applied_job``
     - E2E
   * - UI: interview date can be set on the job detail page and survives a reload
     - ``test_open_job_detail_and_edit_notes_and_status``
     - E2E

Test coverage
---------------

Generated with::

    .venv\Scripts\python.exe -m pytest tests/ --cov=src --cov=webapp/backend --cov-report=term-missing

.. list-table::
   :header-rows: 1
   :widths: 34 12 12 12 30

   * - Module
     - Statements
     - Missed
     - Coverage
     - Why
   * - ``models.py``
     - 60
     - 0
     - **100%**
     - Pure Pydantic models
   * - ``scoring.py``
     - 38
     - 0
     - **100%**
     - Pure functions, fully unit-tested
   * - ``webapp/backend/deps.py``
     - 11
     - 0
     - **100%**
     - Trivial DB-session dependency
   * - ``webapp/backend/schemas.py``
     - 30
     - 0
     - **100%**
     - Pydantic request/response models
   * - ``webapp/backend/routes/scores.py``
     - 10
     - 0
     - **100%**
     - One endpoint, fully tested
   * - ``webapp/backend/routes/jobs.py``
     - 48
     - 1
     - 98%
     - One unreachable branch (404 message formatting)
   * - ``webapp/backend/routes/criteria.py``
     - 26
     - 1
     - 96%
     - Same as above
   * - ``webapp/backend/main.py``
     - 11
     - 1
     - 91%
     - ``__main__`` guard, not exercised under pytest
   * - ``rate_limiter.py``
     - 21
     - 2
     - 90%
     - One defensive branch not exercised
   * - ``config.py``
     - 37
     - 4
     - 89%
     - A couple of URL-builder branches for filter combos not hit
   * - ``webapp/backend/__init__.py``
     - 6
     - 1
     - 83%
     - The sys.path-guard branch (already-inserted case)
   * - ``database.py``
     - 196
     - 34
     - 83%
     - Mostly the one-time schema-migration branches (``ALTER TABLE`` for
       columns that already exist on a fresh test DB) and ``vacuum``/``clear``
   * - ``utils.py``
     - 127
     - 30
     - 76%
     - Logging/screenshot helpers and the live ``looks_like_blocked`` page
       scan aren't exercised without a real ``Page`` object
   * - ``runner.py``
     - 83
     - 47
     - 43%
     - CLI entry point (``main()``, arg parsing, ``--relogin``); the
       reusable pieces (``export_csv``, ``export_json``, ``finalize_stats``)
       *are* covered. The new post-scrape ``recalculate_all_scores()`` call
       lives here too -- verified manually (see :doc:`roadmap`), not
       unit-tested, since ``main()`` as a whole needs a real Playwright
       browser and isn't unit-tested at all today.
   * - ``login.py``
     - 41
     - 30
     - 27%
     - Interactive manual-login flow -- opens a real visible browser and
       blocks on ``input()``, not meaningfully unit-testable
   * - ``scraper.py``
     - 303
     - 239
     - 21%
     - The live Playwright browser-orchestration (clicking, scrolling,
       navigating). Every *decision rule* inside it that doesn't need a
       real ``Page`` (title filtering, id extraction, applicant-count
       parsing, URL building, block detection) is pulled out into a
       tested helper -- see the traceability matrix
   * - ``recalculate_scores.py``
     - 22
     - 22
     - 0%
     - Thin CLI wrapper; its actual logic (``recalculate_all_scores``) is
       ``scoring.py``, which is 100% covered
   * - **TOTAL**
     - **1070**
     - **412**
     - **61%**
     -

The low numbers are concentrated entirely in code that talks to a real
browser or a real terminal (``scraper.py``, ``login.py``, ``runner.py``'s
CLI shell) -- chasing coverage there would mean mocking Playwright itself,
which tends to prove the mock behaves as written, not that the scraper
does. The alternative used throughout this project instead: extract every
piece of *decision logic* out of the browser-driving code into a plain,
named function, and unit-test that function directly. The traceability
matrix above is the evidence that this was actually done, not just
claimed.

Allure reporting
-------------------

``allure-pytest`` writes a machine-readable result for every test; the
Allure commandline tool turns those into an HTML report. Running the
fast suite and the E2E suite into the *same* results directory produces
one combined report for all tests, without any custom
``@allure.feature``/``@allure.story`` annotations -- Allure's default
"Suites" grouping already reads directly off the test file's Python
module path (``tests``, ``tests.backend``, ``tests.webapp_api``,
``tests.e2e``), which already matches this project's actual test-layer
structure closely enough that adding manual grouping on top of it would
just be maintaining the same information twice. See
:ref:`allure-test-reports` for the exact commands (``allure serve
allure-results``, or ``generate`` for static HTML). Neither
``allure-results/`` nor the generated report are committed -- they're
regenerated from a test run, not source.

Other QA signals
-------------------

- **BDD feature files as living documentation** --
  ``tests/features/scraper.feature`` and ``rate_limiting.feature`` are
  Given/When/Then, readable without any code, and are the actual source
  of truth pytest-bdd runs against (not a description written after the
  fact).
- **Deliberate non-duplication across layers** -- see *Testing
  philosophy* above; the API tests' own module docstring
  (``tests/webapp_api/test_jobs_api.py``) states this explicitly so it
  doesn't get "fixed" into redundant coverage later.
- **Diagnostic logging as a production safety net** for the parts that
  aren't unit-tested: every selector lookup in ``scraper.py`` logs a HIT
  or MISS with the exact selector used, full-page snapshots are dumped on
  block/no-cards-found conditions, and ``docs/index.rst``'s Debugging
  Checklist (in ``CLAUDE.md``) turns those logs into a repeatable
  diagnosis procedure rather than guesswork.
- **Manual verification discipline for UI work** -- frontend changes were
  driven with a real Playwright browser against the live dev server
  before being called done even before the E2E suite existed, not just
  typechecked/built (see the Stage W2 notes in :doc:`roadmap`); now that
  suite is automated (Stage W4, see above). The sticky table header is
  checked this way rather than as a permanent E2E test -- verified by
  comparing the header's on-screen Y position and the scroll container's
  ``scrollTop`` before/after scrolling the table body (confirming the
  container actually scrolled while the header didn't move), which is
  more awkward to assert robustly than the behaviors that do have E2E
  coverage. (The row-height control mentioned when this was first
  verified was later removed -- see :doc:`roadmap`'s Jobs page
  filtering & interaction pass.)
- **Bugs found by testing at the right layer, not just claimed** -- three
  real, permanent fixes came directly out of running the E2E suite, none
  visible from the API-layer tests alone: a Vite IPv6-binding default and
  a CORS allowlist that only worked for one hardcoded port (Stage W4, see
  :doc:`roadmap`), and an intermittent ``sqlite3.ProgrammingError:
  SQLite objects created in a thread can only be used in that same
  thread`` -- FastAPI's ``Depends(get_db)`` resolves the dependency and
  calls the route handler as two separate threadpool dispatches, not
  guaranteed to land on the same thread, so it only showed up once in a
  while depending on scheduling. Fixed with ``check_same_thread=False``
  in ``Database.__init__`` (safe here since each connection is
  single-request-scoped) and locked in with a *deterministic* regression
  test (``test_database_can_be_used_from_a_different_thread_than_it_was_created_on``)
  rather than trusting E2E timing to catch it again.
- **A fourth E2E-caught bug, in the filter-presets feature**: Mantine's
  ``Select`` defaults ``allowDeselect`` to ``true``, which clears the
  value (fires ``onChange(null)``) when the user clicks the option that's
  already selected -- exactly what happens when reselecting the
  currently-loaded preset. Diagnosed by writing a small throwaway
  Playwright script that printed the delete button's visibility after
  each step rather than guessing from the failure message alone; the
  first hypothesis (the ``clearable`` prop) turned out to be wrong --
  removing it didn't fix it -- and the actual cause was only confirmed by
  comparing "select the *same* preset again" against "select a
  *different* preset", which behaved differently. Fixed with
  ``allowDeselect={false}`` **and** clearing the preset selection on any
  manual filter edit (so reselecting the same preset afterward is a real
  value change the Select will actually notify about -- selecting an
  option that already equals the current value is otherwise a no-op).
  See :doc:`roadmap` for the full writeup.
- **A reported bug that turned out not to be one, checked against real
  data before "fixing" anything**: asked to fix job descriptions still
  showing as unreadable single-line text, a direct query against
  ``output/jobs.db`` for the 5 most recently scraped jobs (all from the
  same run, after ``clean_description()`` was already in place) found 4
  with real line breaks (10-48 newlines each) and exactly 1 with none --
  a 4071-character wall of text with no ``\n``, ``\r``, bullet characters,
  or ``\xa0`` anywhere in it. That job's description was never scraped as
  separate paragraphs or ``<br>``-delimited lines in the first place --
  LinkedIn rendered it, and therefore Playwright's ``inner_text()``
  returned it, as one unbroken run of text; there is nothing left in the
  DOM at scrape time to preserve, unlike the original bug this project
  already fixed (see the "no paragraph breaks" entry in ``CLAUDE.md``'s
  Debugging Checklist). No code change made -- the fix already in place
  works for postings that have real structure, confirmed by checking, not
  assumed from the ticket description alone.
