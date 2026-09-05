from pages.jobs_page import JobsPage


def test_jobs_list_shows_seeded_jobs(page, frontend_url, seeded_db):
    jobs_page = JobsPage(page, frontend_url).open()
    assert jobs_page.row_count() == 2


def test_filter_by_status_narrows_the_list(page, frontend_url, seeded_db):
    jobs_page = JobsPage(page, frontend_url).open()
    jobs_page.filter_by_status("interview")
    jobs_page.expect_total_count(1)


def test_column_filter_narrows_the_list(page, frontend_url, seeded_db):
    jobs_page = JobsPage(page, frontend_url).open()
    jobs_page.filter_by_column("Title", "Python")
    jobs_page.expect_total_count(1)


def test_status_change_persists_after_reload(page, frontend_url, seeded_db):
    jobs_page = JobsPage(page, frontend_url).open()
    jobs_page.set_status_for_row(0, "applied")

    jobs_page.open()  # re-navigate, same as a fresh page load
    assert jobs_page.status_for_row(0) == "applied"
