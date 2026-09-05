from scoring import JobText, MatchCriterion, build_job_text, calculate_score, score_breakdown


def test_matched_terms_contribute_their_weight():
    criteria = [MatchCriterion("python", weight=2), MatchCriterion("java", weight=1)]
    job_text = JobText(title="", body="senior python engineer")

    score = calculate_score(job_text, criteria)

    # only "python" matches (in the body, no title bonus) -> 2 / (2+1) * 100
    assert round(score, 2) == round(2 / 3 * 100, 2)


def test_no_criteria_matched_gives_zero():
    criteria = [MatchCriterion("rust", weight=1)]
    job_text = JobText(title="", body="python engineer")

    assert calculate_score(job_text, criteria) == 0.0


def test_no_positive_weight_criteria_gives_zero_without_dividing_by_zero():
    criteria = [MatchCriterion("python", weight=0)]
    job_text = JobText(title="", body="python engineer")

    assert calculate_score(job_text, criteria) == 0.0


def test_all_terms_matched_gives_full_score():
    criteria = [MatchCriterion("python", weight=1), MatchCriterion("remote", weight=1)]
    job_text = JobText(title="", body="remote python role")

    assert calculate_score(job_text, criteria) == 100.0


def test_score_is_clamped_to_100_even_with_a_negative_weight_criterion():
    criteria = [MatchCriterion("python", weight=1), MatchCriterion("java", weight=-5)]
    # "java" doesn't match, so it doesn't subtract -- score is exactly 100, not clamped down
    job_text = JobText(title="", body="python role")

    assert calculate_score(job_text, criteria) == 100.0


def test_matches_are_whole_word_not_substring():
    # The bug this fixed: a plain "in" check matches "ai" inside "detail",
    # "remain", "explained", ... -- checked against 126 real scraped jobs,
    # 122 false-positived on "ai" this way even though only 76 actually
    # contain the word. Word-boundary matching must not match here.
    criteria = [MatchCriterion("ai", weight=1)]
    job_text = JobText(title="", body="a detail-oriented engineer who can remain calm")

    assert calculate_score(job_text, criteria) == 0.0


def test_matching_in_the_title_scores_higher_than_matching_in_the_body():
    criteria = [MatchCriterion("python", weight=1), MatchCriterion("java", weight=1)]
    title_match = JobText(title="python engineer", body="")
    body_match = JobText(title="", body="python engineer")

    assert calculate_score(title_match, criteria) > calculate_score(body_match, criteria)


def test_score_breakdown_reports_whether_each_criterion_matched_and_where():
    criteria = [MatchCriterion("python", weight=1), MatchCriterion("java", weight=1)]
    job_text = JobText(title="python engineer", body="some other text")

    details = {d.term: d for d in score_breakdown(job_text, criteria)}

    assert details["python"].matched is True
    assert details["python"].matched_in_title is True
    assert details["java"].matched is False
    assert details["java"].matched_in_title is False


def test_build_job_text_splits_title_from_description_and_skills():
    job_text = build_job_text("Engineer", "Build things", ["Python", "SQL"])

    assert job_text.title == "engineer"
    assert job_text.body == "build things python sql"


def test_build_job_text_accepts_comma_joined_string_skills():
    job_text = build_job_text("Engineer", "Build things", "Python,SQL")

    assert job_text.body == "build things python sql"


def test_build_job_text_handles_missing_fields():
    assert build_job_text("", "", []) == JobText(title="", body=" ")
    assert build_job_text("", "", "") == JobText(title="", body=" ")
