from app.infrastructure.trafilatura_extractor import TrafilaturaExtractor

PAGE = """<html><head><title>Job</title><script>alert('tracking')</script></head><body>
<nav><a href="/">Home</a><a href="/jobs">All jobs</a></nav>
<article><h1>Python Developer</h1>
<p>Acme builds credit insurance software used in 58 countries. We are looking for a
Python developer to join our data team and work on production systems every day.</p>
<p>Your missions: design APIs with FastAPI, deploy services with Docker, monitor models
in production and contribute to the technology watch of the team.</p>
<p>Requirements: solid Python skills, experience with SQL databases, and a good
understanding of software quality practices such as tests and code review.</p>
</article><footer>Cookie settings. Privacy policy.</footer></body></html>"""


def test_extracts_the_offer_text() -> None:
    text = TrafilaturaExtractor().extract(PAGE)

    assert "FastAPI" in text
    assert "credit insurance" in text


def test_scripts_are_never_part_of_the_text() -> None:
    assert "tracking" not in TrafilaturaExtractor().extract(PAGE)


def test_a_page_without_content_gives_an_empty_text() -> None:
    assert TrafilaturaExtractor().extract("<html><body></body></html>") == ""
