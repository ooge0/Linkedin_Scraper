"""
models.py

Pydantic models used across the project.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Job(BaseModel):
    """
    Represents a single LinkedIn vacancy.
    """

    # Unique LinkedIn job id (if available)
    job_id: str = ""

    # Full job url
    url: str = ""

    # Basic information
    title: str = ""
    company: str = ""
    location: str = ""

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

    start_time: datetime = Field(default_factory=datetime.utcnow)

    end_time: Optional[datetime] = None
