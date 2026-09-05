"""
scoring.py

Weighted keyword match scoring for jobs, kept independent of both the
scraper and the web app so the exact same recompute logic can be invoked
from the CLI (recalculate_scores.py) and the web app's
POST /api/scores/recalculate and GET /api/jobs/{job_id}/score-breakdown.
"""

import re
from dataclasses import dataclass

# A title match counts more than the same term buried in the description --
# "Senior Python Engineer" is a much stronger signal for a "python"
# criterion than one passing mention 10 paragraphs into a tech-stack list.
# Applied to the raw weight before normalizing, so a term matched only in
# the body still scores exactly as before (multiplier of 1.0) -- the
# normalizing denominator (sum of positive weights) is unchanged, so
# nothing in a body-only match's score shifts, and 100 is still reachable
# the same way it always was.
TITLE_MATCH_MULTIPLIER = 2.0


@dataclass(frozen=True)
class MatchCriterion:
    term: str
    weight: float


@dataclass(frozen=True)
class JobText:
    """Lowercased title, kept separate from body (description + skills) so
    calculate_score() can weight a title match differently from a body
    match."""

    title: str
    body: str


@dataclass(frozen=True)
class MatchDetail:
    """One criterion's match result against a specific job -- the basis for
    both calculate_score()'s total and the web app's "why did this job
    score X" breakdown."""

    term: str
    weight: float
    matched: bool
    matched_in_title: bool


def build_job_text(title: str, description: str, skills) -> JobText:
    """
    Lowercase title and (description + skills) into a JobText.

    skills may be a list[str] (Job objects) or a comma-joined str
    (sqlite3.Row, since skills is stored as TEXT) -- both shapes are
    normalized here so calculate_score()/score_breakdown() stay pure
    functions over plain strings.
    """

    if isinstance(skills, str):
        skills_text = skills.replace(",", " ")
    else:
        skills_text = " ".join(skills or [])

    return JobText(
        title=(title or "").lower(),
        body=" ".join([description or "", skills_text]).lower(),
    )


def _term_matches(term: str, text: str) -> bool:
    """
    Whole-word match, not substring: a plain `"ai" in text` check matches
    "detail", "remain", "explained", ... -- checked against 126 real
    scraped jobs, that false-positived on 122 of them for a term that
    genuinely appears in only 76. `\\b` is imperfect for terms that are
    themselves mostly punctuation (e.g. "C++"), but is a solid default for
    the free-text keywords this is actually used with.
    """

    pattern = r"\b" + re.escape(term.lower()) + r"\b"
    return re.search(pattern, text) is not None


def score_breakdown(job_text: JobText, criteria: list[MatchCriterion]) -> list[MatchDetail]:
    """
    Per-criterion match detail against one job -- calculate_score() sums
    this same breakdown rather than duplicating the matching logic, so the
    web app's "why this score" view can never disagree with the actual
    stored score.
    """

    details = []

    for criterion in criteria:
        matched_in_title = _term_matches(criterion.term, job_text.title)
        matched = matched_in_title or _term_matches(criterion.term, job_text.body)
        details.append(MatchDetail(
            term=criterion.term,
            weight=criterion.weight,
            matched=matched,
            matched_in_title=matched_in_title,
        ))

    return details


def calculate_score(job_text: JobText, criteria: list[MatchCriterion]) -> float:
    """
    Word-boundary match per criterion contributes its weight (doubled if
    matched in the title) to a raw score, normalized to [0, 100] as
    raw / sum(positive weights) * 100, clamped. No positive-weight
    criteria -> 0.0 (no div-by-zero).
    """

    positive_weight_total = sum(c.weight for c in criteria if c.weight > 0)

    if positive_weight_total <= 0:
        return 0.0

    raw_score = sum(
        detail.weight * (TITLE_MATCH_MULTIPLIER if detail.matched_in_title else 1.0)
        for detail in score_breakdown(job_text, criteria)
        if detail.matched
    )

    score = (raw_score / positive_weight_total) * 100

    return max(0.0, min(100.0, score))


def recalculate_all_scores(db) -> int:
    """
    Recompute match_score for every job currently in the database, using
    the currently-enabled criteria. Returns the number of jobs updated.

    This is the single reuse point shared by recalculate_scores.py (CLI)
    and POST /api/scores/recalculate -- no scoring logic should ever be
    duplicated outside of this function.
    """

    criteria = [
        MatchCriterion(term=row["term"], weight=row["weight"])
        for row in db.get_criteria(enabled_only=True)
    ]

    scores = {}
    for row in db.get_all_jobs():
        job_text = build_job_text(row["title"], row["description"], row["skills"])
        scores[row["job_id"]] = calculate_score(job_text, criteria)

    return db.bulk_update_scores(scores)
