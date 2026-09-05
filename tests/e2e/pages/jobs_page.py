import re

from playwright.sync_api import expect

TOTAL_COUNT_PATTERN = re.compile(r"\d+ job\(s\) total")


class JobsPage:
    """Page Object for the "/" jobs list page."""

    def __init__(self, page, base_url):
        self.page = page
        self.base_url = base_url

    def open(self):
        self.page.goto(self.base_url)
        self.page.wait_for_selector("table tbody tr")
        return self

    def row_count(self) -> int:
        return self.page.locator("table tbody tr").count()

    def total_count(self) -> int:
        text = self.page.get_by_text(TOTAL_COUNT_PATTERN).inner_text()
        return int(text.split()[0])

    def expect_total_count(self, count: int, timeout: int = 5000):
        """
        Waits (with Playwright's built-in retry) for the total-count text
        to reach the given value. Filters are debounced and/or trigger a
        re-fetch, so the result isn't visible immediately after the
        triggering action -- this polls the actual visible outcome
        instead of guessing a fixed sleep or matching a specific network
        response (React's effect dependencies can fire more than one
        /api/jobs request per action, so a same-URL response match isn't
        reliably *the* response for this specific action either -- this
        bit a run of the suite before the assertion was changed to poll
        the result rather than the request).
        """
        locator = self.page.get_by_text(TOTAL_COUNT_PATTERN)
        expect(locator).to_have_text(re.compile(rf"^{count} job\(s\) total$"), timeout=timeout)
        return self

    def filter_by_status(self, status: str):
        self.page.get_by_role("combobox", name="Filter by status").click()
        self.page.get_by_role("option", name=status, exact=True).click()
        return self

    def status_filter_value(self) -> str:
        return self.page.get_by_role("combobox", name="Filter by status").input_value()

    def filter_by_column(self, column_label: str, text: str):
        """Fill the per-column filter row cell under the given column header."""
        self.page.get_by_label(f"Filter by {column_label}").fill(text)
        return self

    def status_for_row(self, row_index: int) -> str:
        row = self.page.locator("table tbody tr").nth(row_index)
        return row.get_by_role("combobox").input_value()

    def set_status_for_row(self, row_index: int, status: str):
        row = self.page.locator("table tbody tr").nth(row_index)
        row.get_by_role("combobox").click()
        self.page.get_by_role("option", name=status, exact=True).click()
        self.page.wait_for_timeout(400)
        return self

    def column_headers(self) -> list[str]:
        return self.page.locator("table thead tr").first.locator("th").all_inner_texts()

    def cell_text(self, row_title: str, column_label: str) -> str:
        """Reads one cell's text, locating the row by its Title-column text
        rather than a positional index -- sort order isn't guaranteed when
        several rows tie (e.g. all have a null match_score)."""
        headers = [h.rstrip(" ^v") for h in self.column_headers()]
        col_index = headers.index(column_label)
        row = self.page.locator("table tbody tr").filter(has_text=row_title)
        return row.locator("td").nth(col_index).inner_text()

    def drag_column(self, source_label: str, target_label: str):
        source = self.page.locator("table thead tr").first.locator("th", has_text=source_label)
        target = self.page.locator("table thead tr").first.locator("th", has_text=target_label)
        source_box = source.bounding_box()
        target_box = target.bounding_box()

        self.page.mouse.move(source_box["x"] + source_box["width"] / 2, source_box["y"] + 10)
        self.page.mouse.down()
        self.page.mouse.move(target_box["x"] + 5, target_box["y"] + 10, steps=10)
        self.page.mouse.up()
        self.page.wait_for_timeout(400)
        return self

    def set_page_size(self, size: str):
        self.page.get_by_role("combobox", name="Per page").click()
        self.page.get_by_role("option", name=size, exact=True).click()
        self.page.wait_for_timeout(400)
        return self

    def column_width(self, header_text: str) -> float:
        th = self.page.locator("table thead tr").first.locator("th", has_text=header_text)
        return th.bounding_box()["width"]

    def resize_column(self, header_text: str, delta_x: int):
        th = self.page.locator("table thead tr").first.locator("th", has_text=header_text)
        handle = th.locator('div[style*="col-resize"]')
        box = handle.bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        self.page.mouse.move(cx, cy)
        self.page.mouse.down()
        self.page.mouse.move(cx + delta_x, cy, steps=15)
        self.page.mouse.up()
        self.page.wait_for_timeout(300)
        return self

    def open_job(self, title: str):
        from pages.job_detail_page import JobDetailPage

        self.page.get_by_role("link", name=title, exact=True).click()
        self.page.wait_for_url("**/jobs/*")
        return JobDetailPage(self.page, self.base_url)

    def click_next_unreviewed(self):
        """Clicks the button and waits for navigation to the job it found."""
        from pages.job_detail_page import JobDetailPage

        self.page.get_by_role("button", name="Next unreviewed job").click()
        self.page.wait_for_url("**/jobs/*")
        self.page.wait_for_selector("h2")
        return JobDetailPage(self.page, self.base_url)

    def click_next_unreviewed_expect_notification(self, text: str):
        """For the "nothing left to review" case -- no navigation happens."""
        self.page.get_by_role("button", name="Next unreviewed job").click()
        expect(self.page.get_by_text(text)).to_be_visible()
        return self

    def save_preset(self, name: str):
        self.page.get_by_label("New preset name").fill(name)
        self.page.get_by_role("button", name="Save current filters as preset").click()
        return self

    def load_preset(self, name: str):
        self.page.get_by_role("combobox", name="Load filter preset").click()
        self.page.get_by_role("option", name=name, exact=True).click()
        return self

    def delete_current_preset(self):
        self.page.get_by_title("Delete this preset").click()
        return self

    def preset_names(self) -> list[str]:
        combobox = self.page.get_by_role("combobox", name="Load filter preset")
        combobox.click()
        names = self.page.get_by_role("option").all_inner_texts()
        combobox.press("Escape")
        return names

    def goto_criteria(self):
        from pages.criteria_page import CriteriaPage

        self.page.get_by_role("link", name="Criteria").click()
        self.page.wait_for_url("**/criteria")
        return CriteriaPage(self.page, self.base_url)
