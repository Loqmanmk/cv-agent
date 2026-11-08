from app.services.job_fetch_service import tidy


def test_removes_indentation_and_trailing_spaces() -> None:
    assert tidy("   Title   \n          Line two  ") == "Title\nLine two"


def test_collapses_runs_of_spaces_and_tabs_inside_a_line() -> None:
    assert tidy("React.js \t  and    SQL") == "React.js and SQL"


def test_keeps_one_blank_line_between_paragraphs_but_not_more() -> None:
    assert tidy("One\n\n\n\n\nTwo\n\nThree") == "One\n\nTwo\n\nThree"


def test_keeps_the_dash_of_a_list_item() -> None:
    assert tidy("-  Build REST APIs") == "- Build REST APIs"


def test_an_empty_text_stays_empty() -> None:
    assert tidy("  \n \n ") == ""
