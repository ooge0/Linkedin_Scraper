"""
models.py

Pydantic models used across the project.
"""

import enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ApplicationStatus(str, enum.Enum):
    """
    Where a job stands in the user's own application pipeline.
    A constrained set rather than free text, so the web app can filter/
    sort/group by it reliably.
    """

    NOT_APPLIED = "not_applied"
    VIEWED = "viewed"
    APPLIED = "applied"
    INTERVIEW = "interview"
    REJECTED = "rejected"
    OFFER = "offer"
    IGNORED = "ignored"


class Job(BaseModel):
    """
    Represents a single LinkedIn vacancy.
    """

    # Unique LinkedIn job id (if available)
    job_id: str = ""

    # Raw page URL at the moment of scraping -- carries transient search
    # context (currentJobId/keywords/start), not stable to revisit later
    url: str = ""

    # Canonical, stable link to the job ("https://www.linkedin.com/jobs/view/{job_id}/"),
    # built from job_id -- always valid regardless of search context
    job_url: str = ""

    # Search parameters that produced this job (config.SEARCH_KEYWORD / SEARCH_LOCATION)
    search_keyword: str = ""
    search_location: str = ""

    # Basic information
    title: str = ""
    company: str = ""
    company_url: str = ""
    location: str = ""
    location_entity: str = ""

    # Additional information
    salary: str = ""
    posted: str = ""
    employment_type: str = ""
    seniority: str = ""
    workplace_type: str = ""

    # Company information
    company_size: str = ""
    industry: str = ""

    # Statistics
    applicants: str = ""

    # Job description
    description: str = ""

    # Parsed skills
    skills: list[str] = Field(default_factory=list)

    # Timestamp when vacancy was scraped
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    # Where this job stands in the user's own application pipeline
    application_status: ApplicationStatus = ApplicationStatus.NOT_APPLIED

    # Free-text notes the user attaches to the job
    notes: str = ""

    # Weighted keyword match score (0-100), None until recalculate_scores.py
    # or the web app's "Recalculate scores" action has run at least once
    match_score: Optional[float] = None


class SearchFilters(BaseModel):
    """
    Search parameters.
    """

    keyword: str = ""

    location: str = ""

    remote: bool = False

    easy_apply: bool = False

    max_pages: int = 5

    posted_last_24h: bool = False

    posted_last_week: bool = False

    experience: Optional[str] = None

    job_type: Optional[str] = None


class ScraperStats(BaseModel):
    """
    Runtime statistics.
    """

    pages_visited: int = 0

    cards_found: int = 0

    jobs_saved: int = 0

    jobs_skipped: int = 0

    parsing_errors: int = 0

    # Actions counted against the REQUESTS_PER_HOUR cap (see rate_limiter.py)
    rate_limited_actions: int = 0

    # True if the run stopped early because REQUESTS_PER_HOUR was hit
    rate_limit_stopped: bool = False

    # Cards looked at (clicked or skipped) this session, counted against
    # MAX_CARDS_PER_SESSION
    cards_processed: int = 0

    # True if the run stopped early because MAX_CARDS_PER_SESSION was hit
    card_limit_stopped: bool = False

    # True if the run stopped early because LinkedIn redirected to /login
    # or /checkpoint -- the persistent session has expired or been challenged
    session_expired: bool = False

    start_time: datetime = Field(default_factory=datetime.utcnow)

    end_time: Optional[datetime] = None
