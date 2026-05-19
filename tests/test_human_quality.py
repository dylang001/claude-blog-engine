from content_machine.human_quality import assess_human_quality


def test_human_quality_flags_generic_ai_filler():
    text = (
        "In today's digital landscape, it is important to note that robust platforms help. "
        "In today's digital landscape, teams can leverage a comprehensive solution. "
        "In conclusion, this game changer can take your business to the next level."
    )

    report = assess_human_quality(text)

    assert report.score < 75
    assert any("filler" in issue for issue in report.issues)


def test_human_quality_rewards_specific_varied_copy():
    text = (
        "Google published AI content guidance in 2023. That matters for MeetLyra because the bar is usefulness, not authorship. "
        "A founder can use the engine to compare five content gaps, pick one page, and update the draft before it reaches WordPress.\n\n"
        "The workflow still needs taste. For example, a thin claim gets cut unless it has a source, screenshot, or internal product proof."
    )

    report = assess_human_quality(text)

    assert report.score >= 85


def test_human_quality_flags_non_english_fragments():
    report = assess_human_quality("The workflow saves teams hours 每周 when drafts move into WordPress.")

    assert report.score < 85
    assert any("non-English" in issue for issue in report.issues)
