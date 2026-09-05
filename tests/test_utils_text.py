"""
clean_description() specifically -- see the docstring in utils.py for why
it exists separately from clean_text(): LinkedIn sometimes renders a job
description as one <p> with <br> line breaks instead of several <p>
elements, and clean_text()'s blanket whitespace collapse turns that into
one unreadable run-on paragraph. This is plain pytest, not BDD, since the
behavior is fully described by the test names below -- see the testing
philosophy note in docs/qa.rst.
"""

from utils import clean_description


def test_preserves_single_line_breaks():
    assert clean_description("Line one\nLine two\nLine three") == (
        "Line one\nLine two\nLine three"
    )


def test_preserves_paragraph_breaks():
    assert clean_description("Paragraph one.\n\nParagraph two.") == (
        "Paragraph one.\n\nParagraph two."
    )


def test_collapses_three_or_more_blank_lines_to_one():
    assert clean_description("First\n\n\n\nSecond") == "First\n\nSecond"


def test_normalizes_horizontal_whitespace_without_touching_line_breaks():
    assert clean_description("Too    many   spaces\nAnother   line") == (
        "Too many spaces\nAnother line"
    )


def test_strips_leading_and_trailing_whitespace():
    assert clean_description("  \n Padded text \n  ") == "Padded text"


def test_replaces_non_breaking_space_with_regular_space():
    assert clean_description("Salary:\xa0$100k") == "Salary: $100k"


def test_empty_input_returns_empty_string():
    assert clean_description("") == ""
