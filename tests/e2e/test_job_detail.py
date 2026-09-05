from pages.jobs_page import JobsPage


def test_open_job_detail_and_edit_notes_and_status(page, frontend_url, seeded_db):
    jobs_page = JobsPage(page, frontend_url).open()
    detail = jobs_page.open_job("Senior Python QA Engineer")
    assert detail.title() == "Senior Python QA Engineer"

    detail.set_notes("Looks like a great fit")
    detail.set_interview_date("2026-09-20")
    detail.save_notes()
    detail.set_status("applied")

    detail.reload()
    assert detail.notes() == "Looks like a great fit"
    assert detail.interview_date() == "2026-09-20"
    assert detail.status() == "applied"


def test_back_to_jobs_link_returns_to_the_list(page, frontend_url, seeded_db):
    jobs_page = JobsPage(page, frontend_url).open()
    detail = jobs_page.open_job("Junior Manual Tester")

    jobs_page_again = detail.back_to_jobs()
    assert jobs_page_again.row_count() == 2
