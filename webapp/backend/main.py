"""
main.py

FastAPI app for the job-tracker web UI. A thin HTTP layer over the
scraper's existing database.py/scoring.py -- no new data logic lives here,
only request/response handling (see webapp/backend/routes/).

Run from the project root:

    .venv\\Scripts\\python.exe -m uvicorn webapp.backend.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from webapp.backend.routes import criteria, jobs, scores

app = FastAPI(title="LinkedIn Job Tracker API")

# Any localhost/127.0.0.1 port, not just Vite's default 5173 -- this app
# is a local personal tool, not internet-facing, so that's still safe,
# and it's needed because the E2E suite (tests/e2e/) runs the frontend on
# a dynamically-picked free port to avoid clashing with a dev server that
# might already be running on 5173.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(criteria.router)
app.include_router(scores.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
