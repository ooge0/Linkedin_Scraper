from csv import DictReader
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from pytest_bdd import given, parsers, scenarios, then, when

from config import build_search_url
from database import Database
from models import Job, ScraperStats
from runner import export_csv, finalize_stats
from scraper import Scraper, _results_url
from utils import (
    extract_job_id,
    looks_like_blocked,
    parse_location_meta,
    title_skip_reason,
    build_job_url,
)


scenarios("features/scraper.feature")


@given(
    parsers.parse(
        'the search filters are keyword "{keyword}", location "{location}", '
        "remote only, and posted in the last week"
    )
)
def search_filters(monkeypatch, keyword, location):
    import config

    monkeypatch.setattr(config, "SEARCH_KEYWORD", keyword)
    monkeypatch.setattr(config, "SEARCH_LOCATION", location)
    monkeypatch.setattr(config, "REMOTE_ONLY", True)
    monkeypatch.setattr(config, "POSTED_LAST_24H", False)
    monkeypatch.setattr(config, "POSTED_LAST_WEEK", True)
    monkeypatch.setattr(config, "FORM_LOCATION", "")


@when("the search URL is built", target_fixture="built_url")
def built_url():
    return build_search_url()


@then("the URL contains the selected LinkedIn filters")
def selected_filters(built_url):
    query = parse_qs(urlparse(built_url).query)
    assert query == {
        "keywords": ["Python"],
        "location": ["Remote"],
        "f_WT": ["2"],
        "f_TPR": ["r604800"],
    }


@given(parsers.parse('the search region is forced to "{region}"'))
def force_search_region(monkeypatch, region):
    import config

    monkeypatch.setattr(config, "FORM_LOCATION", region)


@given("the search region is not forced")
def unforced_search_region(monkeypatch):
    import config

    monkeypatch.setattr(config, "FORM_LOCATION", "")


@then(parsers.parse('the URL contains geoId "{geo_id}"'))
def url_contains_geo_id(built_url, geo_id):
    query = parse_qs(urlparse(built_url).query)
    assert query.get("geoId") == [geo_id]


@then("the URL does not contain a geoId")
def url_has_no_geo_id(built_url):
    query = parse_qs(urlparse(built_url).query)
    assert "geoId" not in query


@given(
    parsers.parse('a top-card summary line "{line}"'),
    target_fixture="summary_line",
)
def top_card_summary_line(line):
    return line


@when("the summary line is parsed", target_fixture="parsed_summary")
def parse_summary_line(summary_line):
    location_entity, posted, applicants = parse_location_meta(summary_line)
    return {
        "location_entity": location_entity,
        "posted": posted,
        "applicants": applicants,
    }


@then(parsers.parse('the location entity is "{location_entity}"'))
def location_entity_matches(parsed_summary, location_entity):
    assert parsed_summary["location_entity"] == location_entity


@then(parsers.parse('the posted date is "{posted}"'))
def posted_date_matches(parsed_summary, posted):
    assert parsed_summary["posted"] == posted


@then(parsers.parse('the applicants text is "{applicants}"'))
def applicants_text_matches(parsed_summary, applicants):
    assert parsed_summary["applicants"] == applicants


@given("an empty job database", target_fixture="database")
def empty_database(tmp_path):
    return Database(str(tmp_path / "jobs.db"))


@when("the same job is inserted twice")
def insert_duplicate_job(database):
    job = Job(job_id="123", title="Python Engineer")
    database.insert_job(job)
    database.insert_job(job)


@then("the database contains one job")
def one_job(database):
    assert database.count_jobs() == 1
    database.close()


@given("a database containing one job", target_fixture="database")
def database_with_job(tmp_path):
    database = Database(str(tmp_path / "jobs.db"))
    database.insert_job(Job(job_id="456", title="QA Engineer"))
    return database


@when("the jobs are exported to a CSV file", target_fixture="csv_path")
def export_jobs(database, tmp_path):
    path = tmp_path / "jobs.csv"
    assert export_csv(database, str(path)) == 1
    database.close()
    return path


@then("the CSV contains the job identifier and title")
def csv_contains_job(csv_path):
    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        rows = list(DictReader(csv_file))

    assert rows[0]["job_id"] == "456"
    assert rows[0]["title"] == "QA Engineer"


@given(
    "a scraper with statistics showing one visited page and two saved jobs",
    target_fixture="scraper_stats",
)
def scraper_with_stats():
    return ScraperStats(pages_visited=1, jobs_saved=2)


@when("the scraper finishes")
def finish_scraper(scraper_stats):
    return finalize_stats(SimpleNamespace(stats=scraper_stats))


@then("the scraper statistics retain those values")
def stats_are_retained(scraper_stats):
    assert scraper_stats.pages_visited == 1
    assert scraper_stats.jobs_saved == 2
    assert scraper_stats.end_time is not None


class FakeLocator:
    def __init__(self, text):
        self.text = text

    def inner_text(self):
        return self.text


class FakePage:
    def __init__(self, visible_text):
        self.visible_text = visible_text

    def locator(self, selector):
        assert selector == "body"
        return FakeLocator(self.visible_text)


@given("a page with internal verification markup but normal visible job results", target_fixture="page")
def normal_search_page():
    return FakePage("QA Engineer | Remote | Apply")


@given("a page with visible security verification text", target_fixture="page")
def blocked_page():
    return FakePage("Security verification required")


@when("the page is checked for blocking", target_fixture="blocked")
def check_for_blocking(page):
    return looks_like_blocked(page)


@then("the page is not considered blocked")
def page_is_not_blocked(blocked):
    assert blocked is False


@then("the page is considered blocked")
def page_is_blocked(blocked):
    assert blocked is True


@given(
    parsers.parse('a LinkedIn search URL with current job ID "{job_id}"'),
    target_fixture="job_url",
)
def search_url_with_current_job(job_id):
    return f"https://www.linkedin.com/jobs/search/?currentJobId={job_id}&keywords=QA"


@when("the job ID is extracted", target_fixture="extracted_job_id")
def extract_job(job_url):
    return extract_job_id(job_url)


@then(parsers.parse('the extracted job ID is "{job_id}"'))
def extracted_id_matches(extracted_job_id, job_id):
    assert extracted_job_id == job_id


@given(parsers.parse('a job ID "{job_id}"'), target_fixture="source_job_id")
def a_job_id(job_id):
    return job_id


@given("no job ID", target_fixture="source_job_id")
def no_job_id():
    return ""


@when("the canonical job URL is built", target_fixture="built_job_url")
def build_canonical_job_url(source_job_id):
    return build_job_url(source_job_id)


@then(parsers.re(r'the canonical job URL is "(?P<expected_url>.*)"'))
def canonical_job_url_matches(built_job_url, expected_url):
    assert built_job_url == expected_url


@given(
    parsers.parse("a scraper configured to scrape {page_count:d} result pages"),
    target_fixture="scraper",
)
def configured_scraper(page_count, tmp_path, monkeypatch):
    monkeypatch.setattr("scraper.Database", lambda: Database(str(tmp_path / "jobs.db")))
    return Scraper(max_pages=page_count)


@when("the scraper page limit is read", target_fixture="page_limit")
def read_page_limit(scraper):
    return scraper.max_pages


@then(parsers.parse("the scraper page limit is {page_count:d}"))
def page_limit_matches(page_limit, page_count):
    assert page_limit == page_count


class FakeCard:
    def __init__(self, job_id):
        self.job_id = job_id

    def get_attribute(self, name):
        assert name == "data-job-id"
        return self.job_id

    def evaluate(self, script, target_job_id=None):
        return self.page.advance_scroll()


class FakeCardLocator:
    def __init__(self, page):
        self.page = page

    def count(self):
        return len(self.page.visible_ids)

    def nth(self, index):
        return FakeCard(self.page.visible_ids[index])

    @property
    def first(self):
        card = FakeCard(self.page.visible_ids[0])
        card.page = self.page
        return card


class FakeResultsPage:
    def __init__(self):
        self.visible_ids = ["1", "2", "3"]
        self.scrolled = False

    def locator(self, selector):
        assert selector == "div.job-card-container"
        locator = FakeCardLocator(self)
        locator.first.page = self
        return locator

    def advance_scroll(self):
        if not self.scrolled:
            self.visible_ids = ["4", "5"]
            self.scrolled = True
            return {"found": False, "atEnd": False}
        return {"found": False, "atEnd": True}


@given(
    parsers.parse(
        "a results panel with {rendered:d} rendered cards and "
        "{additional:d} more cards after scrolling"
    ),
    target_fixture="results_page",
)
def virtualized_results_page(rendered, additional):
    assert (rendered, additional) == (3, 2)
    return FakeResultsPage()


@when("all result card IDs are collected", target_fixture="collected_ids")
def collect_result_ids(results_page):
    from scraper import _collect_all_card_ids

    return _collect_all_card_ids(results_page)


@then(parsers.parse("{count:d} unique result card IDs are collected"))
def result_ids_count(collected_ids, count):
    assert len(collected_ids) == count


@given(
    parsers.parse('a selected-job URL with result offset "{offset}"'),
    target_fixture="selected_job_url",
)
def selected_job_url(offset):
    return (
        "https://www.linkedin.com/jobs/search/?currentJobId=123456"
        f"&keywords=QA&start={offset}"
    )


@when("the selected-job parameter is removed", target_fixture="results_url")
def remove_selected_job(selected_job_url):
    return _results_url(selected_job_url)


@then(parsers.parse('the result offset remains "{offset}"'))
def result_offset_remains(results_url, offset):
    assert parse_qs(urlparse(results_url).query)["start"] == [offset]


def _split_keywords(raw: str) -> list:
    return [kw.strip() for kw in raw.split(",") if kw.strip()]


@given(
    parsers.parse('skip keywords "{skip}" and no must-keywords'),
    target_fixture="title_filter",
)
def title_filter_skip_only(skip):
    return {"skip": _split_keywords(skip), "must": []}


@given(
    parsers.parse('skip keywords "{skip}" and must-keywords "{must}"'),
    target_fixture="title_filter",
)
def title_filter_skip_and_must(skip, must):
    return {"skip": _split_keywords(skip), "must": _split_keywords(must)}


@when(parsers.parse('the title "{title}" is checked'), target_fixture="skip_reason")
def check_title(title, title_filter):
    return title_skip_reason(title, title_filter["skip"], title_filter["must"])


@then("the card is kept")
def card_is_kept(skip_reason):
    assert skip_reason is None


@then(parsers.parse('the card is skipped with reason "{reason}"'))
def card_is_skipped(skip_reason, reason):
    assert skip_reason == reason