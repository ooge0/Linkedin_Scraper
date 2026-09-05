from playwright.sync_api import expect


class JobDetailPage:
    """Page Object for the "/jobs/:jobId" detail page."""

    def __init__(self, page, base_url):
        self.page = page
        self.base_url = base_url

    def title(self) -> str:
        return self.page.locator("h2").first.inner_text()

    def status(self) -> str:
        return self.page.get_by_role("combobox", name="Status").input_value()

    def expect_status(self, status: str, timeout: int = 5000):
        """
        Polls for the status field's value rather than reading it once --
        the auto-mark-as-viewed transition (opening the page while its
        status is "not_applied") fires a background PATCH after the
        initial GET resolves, so the value isn't necessarily there yet on
        the very next line of a test.
        """
        expect(self.page.get_by_role("combobox", name="Status")).to_have_value(status, timeout=timeout)
        return self

    def set_status(self, status: str):
        self.page.get_by_role("combobox", name="Status").click()
        self.page.get_by_role("option", name=status, exact=True).click()
        self.page.wait_for_timeout(400)
        return self

    def notes(self) -> str:
        return self.page.get_by_label("Notes").input_value()

    def set_notes(self, text: str):
        self.page.get_by_label("Notes").fill(text)
        return self

    def interview_date(self) -> str:
        return self.page.get_by_label("Interview date").input_value()

    def set_interview_date(self, date: str):
        self.page.get_by_label("Interview date").fill(date)
        return self

    def save_notes(self):
        # Button is labeled "Save" -- it saves notes and interview date
        # together as one "application tracking" update.
        self.page.get_by_role("button", name="Save", exact=True).click()
        self.page.wait_for_timeout(500)
        return self

    def expect_follow_up_reminder(self, timeout: int = 5000):
        expect(self.page.get_by_text("Consider following up")).to_be_visible(timeout=timeout)
        return self

    def expect_no_follow_up_reminder(self):
        expect(self.page.get_by_text("Consider following up")).not_to_be_visible()
        return self

    def match_score_text(self) -> str:
        return self.page.get_by_text("Match score:").inner_text()

    def reload(self):
        self.page.reload()
        self.page.wait_for_selector("h2")
        return self

    def back_to_jobs(self):
        from pages.jobs_page import JobsPage

        self.page.get_by_text("Back to jobs").click()
        self.page.wait_for_selector("table tbody tr")
        return JobsPage(self.page, self.base_url)
