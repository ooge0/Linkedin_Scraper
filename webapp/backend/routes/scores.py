from fastapi import APIRouter, Depends

from database import Database
from scoring import recalculate_all_scores

from webapp.backend.deps import get_db
from webapp.backend.schemas import RecalculateOut

router = APIRouter(tags=["scores"])


@router.post("/api/scores/recalculate", response_model=RecalculateOut)
def recalculate_scores(db: Database = Depends(get_db)):
    updated = recalculate_all_scores(db)
    return RecalculateOut(updated=updated)
