from content_machine.yoast_guidelines import assess_yoast_copywriting, yoast_research_requirements


def test_yoast_guidelines_flag_long_paragraphs_and_weak_intro():
    markdown = (
        "This opening waits too long before it says anything useful.\n\n"
        "## Introduction\n\n"
        + " ".join(["This paragraph keeps going without a useful break."] * 24)
    )

    report = assess_yoast_copywriting(markdown, "seo automation", {})

    assert report.score < 90
    assert any("first 100 words" in issue for issue in report.issues)
    assert any("paragraphs" in issue for issue in report.issues)


def test_yoast_guidelines_accept_structured_answer_content():
    markdown = "\n\n".join(
        [
            "SEO automation is a workflow that researches, writes, optimizes, and publishes search content with clear quality gates.",
            "## SEO automation: Quick Answer\n\nSEO automation helps lean teams connect keyword research with publishing decisions.",
            "## Search Intent\n\nFirst, the article answers the reader's main question.",
            "## Structure\n\nNext, it organizes the explanation into clear sections.",
            "## Internal Links\n\nThen, it points readers to related resources.",
            "## FAQ\n\n<details><summary>What does it automate?</summary><p>It automates research and publishing prep.</p></details>",
        ]
    )

    report = assess_yoast_copywriting(markdown, "SEO automation", {"requirements": yoast_research_requirements()})

    assert report.score >= 90
    assert not report.issues
