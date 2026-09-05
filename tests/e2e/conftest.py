"""
E2E fixtures: start a real backend + frontend as subprocesses once per
test session, and reset the database to a known state before every test.

This is the only place in the project that talks to a real, running
instance of both halves of the app at once -- see docs/qa.rst's testing
philosophy for why the API and DB layers don't repeat that here.
"""

import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
E2E_DIR = Path(__file__).resolve().parent
for path in (str(PROJECT_ROOT), str(SRC_DIR), str(E2E_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from database import Database
from models import ApplicationStatus, Job


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _terminate_process_tree(process: subprocess.Popen) -> None:
    """
    process.terminate() only signals the process we spawned directly --
    on Windows, `npm run dev` is a cmd.exe wrapper (npm.CMD) around a real
    node.exe it launches as a *child*, so terminate() kills the wrapper
    and leaves node (and the port it's listening on) running behind.
    `taskkill /T` kills the whole tree in one call.
    """
    subprocess.run(
        ["taskkill", "/F", "/T", "/PID", str(process.pid)],
        capture_output=True,
    )
    process.wait(timeout=10)


def _wait_until_serving(url: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except (urllib.error.URLError, ConnectionError, OSError) as e:
            last_error = e
            time.sleep(0.3)
    raise RuntimeError(f"Timed out waiting for {url} to respond") from last_error


@pytest.fixture(scope="session")
def e2e_db_path(tmp_path_factory) -> str:
    return str(tmp_path_factory.mktemp("e2e") / "jobs.db")


@pytest.fixture(scope="session")
def backend_url(e2e_db_path):
    port = _free_port()
    env = {**os.environ, "JOBS_DB_PATH": e2e_db_path}
    process = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "webapp.backend.main:app",
            "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning",
        ],
        cwd=PROJECT_ROOT,
        env=env,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        _wait_until_serving(f"{url}/api/health")
        yield url
    finally:
        _terminate_process_tree(process)


@pytest.fixture(scope="session")
def frontend_url(backend_url):
    npm = shutil.which("npm")
    if npm is None:
        pytest.skip("npm not found on PATH -- required to run the frontend for E2E tests")

    port = _free_port()
    env = {**os.environ, "VITE_API_URL": backend_url}
    process = subprocess.Popen(
        [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(port), "--strictPort"],
        cwd=PROJECT_ROOT / "webapp" / "frontend",
        env=env,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        _wait_until_serving(url)
        yield url
    finally:
        _terminate_process_tree(process)


@pytest.fixture
def seeded_db(e2e_db_path, backend_url):
    """
    Resets the E2E database to two known jobs before every test. Servers
    stay up for the whole session (that's the slow part); only the data
    is reset per test, so tests stay isolated without paying to restart
    uvicorn/Vite each time.
    """
    db = Database(e2e_db_path)
    db.clear()
    db.cursor.execute("DELETE FROM match_criteria")
    db.connection.commit()

    db.insert_job(Job(
        job_id="e2e-1",
        title="Senior Python QA Engineer",
        company="Acme",
        description="We need a QA engineer with strong Python skills.",
        skills=["python", "selenium"],
        salary="$120K/yr",
        employment_type="Full-time",
        seniority="Mid-Senior level",
        applicants="50 applicants",
    ))
    db.insert_job(Job(
        job_id="e2e-2",
        title="Junior Manual Tester",
        company="Beta",
        application_status=ApplicationStatus.INTERVIEW,
        description="Manual testing role, no coding required.",
    ))
    db.close()
