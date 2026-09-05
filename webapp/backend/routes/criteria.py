from fastapi import APIRouter, Depends, HTTPException

from database import Database

from webapp.backend.deps import get_db
from webapp.backend.schemas import CriterionIn, CriterionOut, CriterionUpdateIn

router = APIRouter(tags=["criteria"])


@router.get("/api/criteria", response_model=list[CriterionOut])
def list_criteria(db: Database = Depends(get_db)):
    return [CriterionOut.from_row(row) for row in db.get_criteria()]


@router.post("/api/criteria", response_model=CriterionOut, status_code=201)
def add_criterion(body: CriterionIn, db: Database = Depends(get_db)):
    criterion_id = db.add_criterion(term=body.term, weight=body.weight, enabled=body.enabled)
    row = next(r for r in db.get_criteria() if r["id"] == criterion_id)
    return CriterionOut.from_row(row)


@router.patch("/api/criteria/{criterion_id}", response_model=CriterionOut)
def update_criterion(criterion_id: int, body: CriterionUpdateIn, db: Database = Depends(get_db)):
    if body.term is None and body.weight is None and body.enabled is None:
        raise HTTPException(status_code=400, detail="Provide at least one field to update")

    updated = db.update_criterion(
        criterion_id, term=body.term, weight=body.weight, enabled=body.enabled
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Criterion {criterion_id} not found")

    row = next(r for r in db.get_criteria() if r["id"] == criterion_id)
    return CriterionOut.from_row(row)


@router.delete("/api/criteria/{criterion_id}", status_code=204)
def delete_criterion(criterion_id: int, db: Database = Depends(get_db)):
    if not db.delete_criterion(criterion_id):
        raise HTTPException(status_code=404, detail=f"Criterion {criterion_id} not found")
