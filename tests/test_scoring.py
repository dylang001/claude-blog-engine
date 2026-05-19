from content_machine.models import Opportunity, WorkItemType
from content_machine.scoring import choose_opportunity, decide_publish, opportunity_score


def test_publish_decision_thresholds():
    assert decide_publish(85).value == "publish"
    assert decide_publish(70).value == "draft"
    assert decide_publish(69.9).value == "block"


def test_opportunity_score_prefers_low_difficulty_high_volume():
    good = opportunity_score(volume=10000, kd=20, funnel="BOFU")
    weak = opportunity_score(volume=100, kd=80, funnel="TOFU")
    assert good > weak


def test_choose_opportunity_skips_seen_keyword_when_possible():
    candidates = [
        Opportunity(WorkItemType.NEW_ARTICLE, "seen", "Seen", 99),
        Opportunity(WorkItemType.REFRESH, "fresh", "Fresh", 80),
    ]
    chosen = choose_opportunity(candidates, {"seen"})
    assert chosen.keyword == "fresh"
