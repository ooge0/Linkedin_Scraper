"""
schemas.py

API request/response models. Deliberately separate from src/models.Job:
that model shapes what the scraper writes (raw search-context URL,
scraped_at as a datetime, skills as a list at write time), while these
shape what the DB actually stores and what the UI needs to read -- e.g.
skills is TEXT (comma-joined) in the DB, so JobOut converts it back to a
list here rather than stretching the scraper's own model to cover both.
"""

from typing import Optional

from pydantic import BaseModel

from models import ApplicationStatus


class JobOut(BaseModel):
    job_id: str
    job_url: str
    title: str
    company: str
    company_url: Optional[str] = None
    location: str
    location_entity: str
    search_location: str
    salary: str
    posted: str
    employment_type: str
    seniority: str
    workplace_type: str
    applicants: str
    description: str
    skills: list[str]
    scraped_at: str
    application_status: ApplicationStatus
    notes: str
    match_score: Optional[float] = None
    interview_date: str
    status_updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "JobOut":
        skills_text = row["skills"] or ""
        return cls(
            job_id=row["job_id"],
            job_url=row["job_url"] or "",
            title=row["title"] or "",
            company=row["company"] or "",
            company_url=row["company_url"],
            location=row["location"] or "",
            location_entity=row["location_entity"] or "",
            search_location=row["search_location"] or "",
            salary=row["salary"] or "",
            posted=row["posted"] or "",
            employment_type=row["employment_type"] or "",
            seniority=row["seniority"] or "",
            workplace_type=row["workplace_type"] or "",
            applicants=row["applicants"] or "",
            description=row["description"] or "",
            skills=[s for s in skills_text.split(",") if s],
            scraped_at=row["scraped_at"] or "",
            application_status=row["application_status"] or ApplicationStatus.NOT_APPLIED,
            notes=row["notes"] or "",
            match_score=row["match_score"],
            interview_date=row["interview_date"] or "",
            status_updated_at=row["status_updated_at"],
        )


class JobListResponse(BaseModel):
    items: list[JobOut]
    total: int


class JobUpdateIn(BaseModel):
    status: Optional[ApplicationStatus] = None
    notes: Optional[str] = None
    interview_date: Optional[str] = None


class StatsOut(BaseModel):
    total: int
    by_status: dict[str, int]


class CriterionOut(BaseModel):
    id: int
    term: str
    weight: float
    enabled: bool

    @classmethod
    def from_row(cls, row) -> "CriterionOut":
        return cls(id=row["id"], term=row["term"], weight=row["weight"], enabled=bool(row["enabled"]))


class CriterionIn(BaseModel):
    term: str
    weight: float = 1.0
    enabled: bool = True


class CriterionUpdateIn(BaseModel):
    term: Optional[str] = None
    weight: Optional[float] = None
    enabled: Optional[bool] = None


class RecalculateOut(BaseModel):
    updated: int


class MatchDetailOut(BaseModel):
    term: str
    weight: float
    matched: bool
    matched_in_title: bool
