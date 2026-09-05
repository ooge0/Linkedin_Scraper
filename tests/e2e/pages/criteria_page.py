class CriteriaPage:
    """Page Object for the "/criteria" management page."""

    def __init__(self, page, base_url):
        self.page = page
        self.base_url = base_url

    def open(self):
        self.page.goto(f"{self.base_url}/criteria")
        self.page.wait_for_selector("h2")
        return self

    def row_count(self) -> int:
        return self.page.locator("table tbody tr").count()

    def add(self, term: str, weight: float = 1):
        self.page.get_by_label("Term").fill(term)
        self.page.get_by_label("Weight").fill(str(weight))
        self.page.get_by_role("button", name="Add criterion").click()
        self.page.wait_for_timeout(400)
        return self

    def delete(self, row_index: int = 0):
        self.page.locator("table tbody tr").nth(row_index).get_by_title("Delete criterion").click()
        self.page.wait_for_timeout(300)
        return self

    def recalculate(self):
        self.page.get_by_role("button", name="Recalculate scores").click()
        self.page.wait_for_timeout(800)
        return self

    def recalculation_notification_visible(self) -> bool:
        return self.page.get_by_text("Scores recalculated").count() > 0
