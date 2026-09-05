from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from database import Database
from models import ApplicationStatus
from scoring import MatchCriterion, build_job_text, score_breakdown

from webapp.backend.deps import get_db
from webapp.backend.schemas import JobListResponse, JobOut, JobUpdateIn, MatchDetailOut, StatsOut

router = APIRouter(tags=["jobs"])


@router.get("/api/jobs", response_model=JobListResponse)
def list_jobs(
    status: Optional[ApplicationStatus] = None,
    search: Optional[str] = None,
    min_score: Optional[float] = None,
    title: Optional[str] = None,
    company: Optional[str] = None,
    location: Optional[str] = None,
    posted: Optional[str] = None,
    job_id: Optional[str] = None,
    search_location: Optional[str] = None,
    notes: Optional[str] = None,
    salary: Optional[str] = None,
    employment_type: Optional[str] = None,
    seniority: Optional[str] = None,
    applicants: Optional[str] = None,
    sort_by: str = "scraped_at",
    sort_dir: str = "DESC",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Database = Depends(get_db),
):
    status_value = status.value if status else None
    # Per-column filter row on the Jobs page -- "location" maps to the
    # cleaned location_entity column, not the raw location text, since
    # that's what's actually displayed in that column.
    column_filters = {
        "title": title,
        "company": company,
        "location_entity": location,
        "posted": posted,
        "job_id": job_id,
        "search_location": search_location,
        "notes": notes,
        "salary": salary,
        "employment_type": employment_type,
        "seniority": seniority,
        "applicants": applicants,
    }

    try:
        rows = db.get_jobs_filtered(
            status=status_value,
            search=search,
            min_score=min_score,
            column_filters=column_filters,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    total = db.count_jobs_filtered(
        status=status_value, search=search, min_score=min_score, column_filters=column_filters
    )

    return JobListResponse(items=[JobOut.from_row(row) for row in rows], total=total)


@router.get("/api/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Database = Depends(get_db)):
    row = db.get_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    return JobOut.from_row(row)


@router.patch("/api/jobs/{job_id}", response_model=JobOut)
def update_job(job_id: str, body: JobUpdateIn, db: Database = Depends(get_db)):
    if body.status is None and body.notes is None and body.interview_date is None:
        raise HTTPException(
            status_code=400, detail="Provide at least one of status, notes, or interview_date"
        )

    updated = db.update_job_status(
        job_id, status=body.status, notes=body.notes, interview_date=body.interview_date
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")

    return JobOut.from_row(db.get_job(job_id))


@router.delete("/api/jobs/{job_id}", status_code=204)
def delete_job(job_id: str, db: Database = Depends(get_db)):
    if db.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    db.delete_job(job_id)


@router.get("/api/jobs/{job_id}/score-breakdown", response_model=list[MatchDetailOut])
def get_score_breakdown(job_id: str, db: Database = Depends(get_db)):
    """
    Which enabled criteria matched this job, and whether the match was in
    the title (worth double, see scoring.TITLE_MATCH_MULTIPLIER) -- turns
    the stored match_score from an opaque number into something a user can
    actually act on when tuning criteria. Computed on demand rather than
    stored, since it depends on whatever criteria are enabled *right now*.
    """
    row = db.get_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")

    criteria = [
        MatchCriterion(term=c["term"], weight=c["weight"])
        for c in db.get_criteria(enabled_only=True)
    ]
    job_text = build_job_text(row["title"], row["description"], row["skills"])

    return [
        MatchDetailOut(
            term=d.term, weight=d.weight, matched=d.matched, matched_in_title=d.matched_in_title
        )
        for d in score_breakdown(job_text, criteria)
    ]


@router.get("/api/stats", response_model=StatsOut)
def get_stats(db: Database = Depends(get_db)):
    return StatsOut(total=db.count_jobs(), by_status=db.get_status_counts())
