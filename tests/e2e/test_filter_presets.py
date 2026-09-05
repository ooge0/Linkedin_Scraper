from pages.jobs_page import JobsPage


def test_saving_and_loading_a_preset_restores_its_filter(page, frontend_url, seeded_db):
    jobs_page = JobsPage(page, frontend_url).open()

    jobs_page.filter_by_status("interview")
    jobs_page.expect_total_count(1)
    jobs_page.save_preset("Interview only")

    # Switch to a different filter -- the preset's own value is gone.
    jobs_page.filter_by_status("not_applied")
    assert jobs_page.status_filter_value() == "not_applied"

    # Loading the preset brings the filter (and its result) back.
    jobs_page.load_preset("Interview only")
    assert jobs_page.status_filter_value() == "interview"
    jobs_page.expect_total_count(1)


def test_presets_persist_across_a_reload(page, frontend_url, seeded_db):
    jobs_page = JobsPage(page, frontend_url).open()
    jobs_page.filter_by_column("Title", "Python")
    jobs_page.save_preset("Python roles")

    jobs_page.open()  # re-navigate, same as a fresh page load
    assert "Python roles" in jobs_page.preset_names()


def test_deleting_a_preset_removes_it_from_the_list(page, frontend_url, seeded_db):
    jobs_page = JobsPage(page, frontend_url).open()
    jobs_page.filter_by_status("interview")
    jobs_page.save_preset("Temp preset")
    assert "Temp preset" in jobs_page.preset_names()

    jobs_page.load_preset("Temp preset")
    jobs_page.delete_current_preset()
    assert "Temp preset" not in jobs_page.preset_names()
