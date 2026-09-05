from pages.jobs_page import JobsPage

EXPECTED_COLUMNS = [
    "Scraped",
    "Title",
    "Company",
    "Location",
    "Posted",
    "Salary",
    "Employment Type",
    "Seniority",
    "Applicants",
    "Score",
    "Job ID",
    "Search Location",
    "Notes",
    "Status",
]


def test_jobs_table_shows_all_expected_columns(page, frontend_url, seeded_db):
    jobs_page = JobsPage(page, frontend_url).open()
    headers = jobs_page.column_headers()

    # Sortable headers get a "^"/"v" indicator appended -- strip it before comparing.
    stripped = [h.rstrip(" ^v") for h in headers]
    assert stripped == EXPECTED_COLUMNS


def test_salary_employment_type_seniority_applicants_columns_show_job_data(page, frontend_url, seeded_db):
    jobs_page = JobsPage(page, frontend_url).open()

    row_title = "Senior Python QA Engineer"
    assert jobs_page.cell_text(row_title, "Salary") == "$120K/yr"
    assert jobs_page.cell_text(row_title, "Employment Type") == "Full-time"
    assert jobs_page.cell_text(row_title, "Seniority") == "Mid-Senior level"
    assert jobs_page.cell_text(row_title, "Applicants") == "50 applicants"


def test_resizing_a_column_changes_its_width(page, frontend_url, seeded_db):
    jobs_page = JobsPage(page, frontend_url).open()

    width_before = jobs_page.column_width("Title")
    jobs_page.resize_column("Title", delta_x=120)
    width_after = jobs_page.column_width("Title")

    assert width_after > width_before + 50


def test_dragging_a_column_header_reorders_it(page, frontend_url, seeded_db):
    jobs_page = JobsPage(page, frontend_url).open()

    # Default sort is by Score (best-match-first), so its header carries
    # the sort indicator -- not Scraped's, unlike before that default changed.
    assert jobs_page.column_headers()[:3] == ["Scraped", "Title", "Company"]

    jobs_page.drag_column(source_label="Company", target_label="Title")

    assert jobs_page.column_headers()[:3] == ["Scraped", "Company", "Title"]
