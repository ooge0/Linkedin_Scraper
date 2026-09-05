from pages.jobs_page import JobsPage


def test_opening_a_job_marks_it_viewed(page, frontend_url, seeded_db):
    jobs_page = JobsPage(page, frontend_url).open()
    detail_page = jobs_page.open_job("Senior Python QA Engineer")
    detail_page.expect_status("viewed")

    # Persists after reload -- proves it was actually saved, not just an
    # in-memory optimistic update.
    detail_page.reload()
    assert detail_page.status() == "viewed"


def test_next_unreviewed_job_navigates_to_a_not_applied_job(page, frontend_url, seeded_db):
    jobs_page = JobsPage(page, frontend_url).open()
    detail_page = jobs_page.click_next_unreviewed()
    assert detail_page.title() == "Senior Python QA Engineer"


def test_next_unreviewed_job_reports_when_none_are_left(page, frontend_url, seeded_db):
    jobs_page = JobsPage(page, frontend_url).open()

    # The only not_applied job (e2e-2 already starts as "interview") --
    # view it so it becomes "viewed" and no longer counts as unreviewed.
    detail_page = jobs_page.open_job("Senior Python QA Engineer")
    detail_page.expect_status("viewed")
    jobs_page = detail_page.back_to_jobs()

    jobs_page.click_next_unreviewed_expect_notification("All caught up")
