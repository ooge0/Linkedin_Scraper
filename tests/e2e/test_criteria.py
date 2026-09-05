from pages.criteria_page import CriteriaPage
from pages.jobs_page import JobsPage


def test_add_criterion_and_recalculate_updates_match_score(page, frontend_url, seeded_db):
    criteria_page = CriteriaPage(page, frontend_url).open()
    criteria_page.add("python", weight=1)
    assert criteria_page.row_count() == 1

    criteria_page.recalculate()
    assert criteria_page.recalculation_notification_visible()

    jobs_page = JobsPage(page, frontend_url).open()
    detail = jobs_page.open_job("Senior Python QA Engineer")
    assert "100" in detail.match_score_text()


def test_delete_criterion_removes_it(page, frontend_url, seeded_db):
    criteria_page = CriteriaPage(page, frontend_url).open()
    criteria_page.add("selenium")
    assert criteria_page.row_count() == 1

    criteria_page.delete(0)
    assert criteria_page.row_count() == 0
