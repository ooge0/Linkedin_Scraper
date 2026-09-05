Pacing and rate limits
======================

This page explains exactly what controls how fast the scraper moves
through LinkedIn, where those controls live in the code, what speed they
actually produce, and how that relates to LinkedIn's own ban/restriction
behavior.

Where the settings live
------------------------

There is **no single "speed" knob** -- pacing is the combination of several
things, in two different files:

``src/config.py``
    - ``REQUESTS_PER_HOUR`` (default ``150``) -- a hard safety backstop, not
      the primary pacing mechanism. Caps how many job-detail-panel opens
      (the expensive, per-job action) can happen in any rolling 60-minute
      window. Implemented by ``RateLimiter`` in ``src/rate_limiter.py``,
      checked in ``Scraper.collect_cards()`` right before each card click.
    - ``MAX_CARDS_PER_SESSION`` (default ``40``) -- a second, independent
      cap: total cards *looked at* (clicked or skipped) in one run,
      regardless of how much time that took. Checked at the top of every
      loop iteration in ``collect_cards()``, so it can stop mid-page, not
      just between pages. Calibrated to match a normal session (~5 pages
      x ~8 new cards/page for this account's search) -- it's a ceiling on
      a normal run, not a further throttle on top of it.
    - ``TITLE_SKIP_KEYWORDS`` / ``TITLE_MUST_KEYWORDS`` -- not pacing
      exactly, but directly reduces click volume: cards are filtered by
      title (via ``title_skip_reason()`` in ``utils.py``) *before* ever
      being clicked, so irrelevant listings cost a cheap text read instead
      of a full detail-panel open.

    Both numeric caps stop the run gracefully (not a crash) and log a
    resume hint -- re-running the same command later continues where it
    left off (already-saved jobs are skipped via ``Database.job_exists()``).

``src/utils.py``
    The actual pacing calls, hardcoded as function defaults rather than
    ``config.py`` constants (this is a real gap -- see *Not yet
    centralized* below):

    - ``random_sleep(min_sec=2.0, max_sec=4.0)`` -- the base "think time"
      used all over ``scraper.py``, called with no arguments (2-4s) or an
      explicit range depending on the call site.
    - ``long_break()`` -- a 25-60s pause, triggered every 3rd page in
      ``Scraper.run()``.
    - ``human_scroll()`` -- 2-9 small scroll steps, each followed by a
      short pause. Not deterministic any more: 12% chance of not
      scrolling at all, 20% chance of a fast skim (shorter pauses), 15%
      chance of scrolling back up afterward -- a fixed step range/pace
      every single time was itself a detectable pattern.
    - ``maybe_distraction_pause()`` -- ~7% chance per card (roughly once
      every 14 cards) of an extra 25-75s pause, simulating the user
      tabbing away. Called after a job is read, before returning to the
      results list.

``src/scraper.py``
    Where those helpers are actually called, and how often, per job and
    per page (see *Effective speed* below). Also where the ~15% chance of
    stopping a run early (from page 3 onward, in ``Scraper.run()``) lives
    -- so session *length* itself varies run to run, not just the pacing
    within a session.

Not yet centralized
--------------------

The ``random_sleep``/``long_break``/``human_scroll``/
``maybe_distraction_pause`` ranges and probabilities are not ``config.py``
constants today -- they're literal defaults/literals inside ``utils.py``.
``REQUESTS_PER_HOUR``, ``MAX_CARDS_PER_SESSION``, ``TITLE_SKIP_KEYWORDS``
and ``TITLE_MUST_KEYWORDS`` *are* proper ``config.py`` tunables. If you
want to change the base pacing or the scroll/distraction probabilities
(not just the safety caps or title filter), you currently have to edit
``utils.py`` directly. Pulling these into named ``config.py`` constants is
a reasonable small follow-up, not yet done.

Effective speed (per job)
--------------------------

Walking through ``Scraper.collect_cards()`` for one newly-seen,
title-passing job (i.e. one that actually gets clicked), the explicit
sleep/pause calls alone add up to roughly:

.. list-table::
   :header-rows: 1

   * - Step
     - Call
     - Average
   * - Before clicking the card
     - ``random_sleep()``
     - ~3.0s
   * - After the detail panel loads
     - ``random_sleep(2, 4)``
     - ~3.0s
   * - Scrolling the panel
     - ``human_scroll()`` -- 12% chance of 0s, otherwise 2-9 steps
     - ~3.2s (0s-~9s+, highly variable)
   * - After scrolling
     - ``random_sleep()``
     - ~3.0s
   * - Distraction pause
     - ``maybe_distraction_pause()`` -- ~7% chance of 25-75s
     - ~3.5s (0s most of the time, 25-75s occasionally)
   * - After reloading the results list
     - ``random_sleep(2, 3)``
     - ~2.5s
   * - **Total explicit pause per clicked job (average)**
     -
     - **~18.2s**

That's *pause time only* -- real page-load/render/network latency on top
of it (LinkedIn's own response time, ``wait_for_load_state``, the actual
click) typically adds several more seconds in practice, so real-world
per-job time is usually higher than 18.2s. A **title-skipped** card (see
``TITLE_SKIP_KEYWORDS``/``TITLE_MUST_KEYWORDS``) costs almost none of
this -- just a locator read and a string check, no click, no detail-panel
load -- so title-filtering reduces real click volume below every number
in this section, by an amount that depends entirely on how many results
match the skip/must lists for a given search.

Per page, add ``goto_next_page()``'s two ``random_sleep()`` calls
(~6s) and, every 3rd page, ``long_break()`` (~42.5s average, amortized to
~14s/page).

Theoretical ceiling
--------------------

If every card on every page were brand new and title-passing (worst case
for request volume -- a rerun mostly skips already-saved jobs via dedup,
and title-filtering removes some fraction of cards entirely, so this
scenario is really only "first big run against fresh, all-relevant search
results"):

- ~18.2s/job x 25 jobs/page (typical LinkedIn results-per-page) = ~455s
  of job-level pausing per page
- + ~6s page-transition sleep, + ~14s amortized long-break
- = ~475s (~7.9 min) of *explicit pause* per page

3600s / 475s ≈ **7.6 pages/hour ≈ 190 new-job-opens/hour**, from pause
timing alone -- before counting real network latency (lower in practice)
or title-filtering (also lower in practice, since not every card is
clicked).

Two independent caps now sit under that ~190/hour ceiling:

- ``REQUESTS_PER_HOUR = 150`` -- bounds the *rate* (any rolling hour)
- ``MAX_CARDS_PER_SESSION = 40`` -- bounds the *session*, regardless of
  time. For this account's normal usage (2 runs/day, ~5 pages, ~40 cards
  per session -- see the project context in ``CLAUDE.md``), this is a
  ceiling matching a normal run, not an extra throttle on top of it: a
  typical session simply won't hit it, but an unattended/misconfigured
  run (e.g. an accidental ``--pages 100``) is stopped at a small, fixed
  amount of work no matter how long it takes.

On a normal run neither cap fires (the scraper's own pacing is already
slower); they exist as backstops for when something is already wrong --
a misconfigured run, an accidentally-weakened pacing change, or similar --
not as the primary safety mechanism.

LinkedIn ban/restriction risk -- what's known
-----------------------------------------------

(Summarized from current -- 2026 -- third-party write-ups; treat the exact
numbers below as directional folklore, not verified fact. Real forum
threads on this are thin and the blog posts citing precise numbers are
largely SEO content, often inconsistent with each other.)

- The strict, well-agreed-on limits (roughly 20-25 actions/day for new
  accounts, up to ~100-150/day for established ones) are about **active,
  outbound actions**: connection requests, InMail, Easy Apply automation.
  Passive job-search browsing (search + viewing a job's detail panel --
  what this scraper does) is treated far more leniently, since it's core,
  expected LinkedIn usage.
- The escalation pattern is consistent across sources: a **silent soft
  throttle** first (pages/cards load slower, fewer results returned --
  this is exactly what ``looks_like_blocked()`` in ``utils.py`` is meant
  to catch), then a **temporary restriction** (typically 1-3 weeks) if
  the elevated activity continues, and only rarely an outright permanent
  ban -- usually reserved for clear automation/API abuse or fake profiles,
  not for a human-paced browser session like this one.
- Multi-accounting (a second "throwaway" account to spread risk) is its
  own ToS violation and tends to trigger its own verification/restriction
  flow -- it doesn't obviously reduce risk versus just pacing the primary
  account well and spreading a large run across multiple days.

Practical takeaway: for a run much larger than the normal ~40-card
session (e.g. a 100-page backfill), prefer spreading it across several
daily runs (e.g. via Task Scheduler, one run/day at a random time -- not
yet automated, see Stage 5 in ``CLAUDE.md``) rather than relying on the
two caps above as the only thing standing between a single sitting and
LinkedIn's attention.
