from app import review


def full(score):
    return {"scores": dict.fromkeys(review.CRITERIA, score)}


def test_all_criteria_reach_the_prompt():
    prompt = review.system_prompt()
    for key, desc in review.CRITERIA.items():
        assert key in prompt
        assert desc["question"] in prompt
        assert desc[3] in prompt  # 중간 기준이 빠지면 점수가 최하로 눌린다


def test_passing_needs_every_criterion():
    assert review.passed(full(5))
    assert review.passed(full(review.PASS_SCORE))
    assert not review.passed(full(review.PASS_SCORE - 1))
    # 한 항목만 낮아도 떨어진다. 평균으로 덮이면 채점표가 무의미하다.
    mixed = full(5)
    mixed["scores"]["punchline"] = 1
    assert not review.passed(mixed)


def test_missing_or_junk_scores_count_as_zero():
    assert review.scores_of({})["premise"] == 0
    assert review.scores_of({"scores": "망함"})["premise"] == 0
    assert review.scores_of({"scores": {"premise": "다섯"}})["premise"] == 0
    assert review.total(full(5)) == 5 * len(review.CRITERIA)


def test_feedback_names_only_the_weak_parts():
    verdict = full(5)
    verdict["scores"]["variety"] = 1
    verdict["notes"] = {"variety": "그건 ~가 아니라 ~야 가 네 번"}
    verdict["fix"] = "츳코미 문형을 바꿔라"
    note = review.feedback(verdict)
    assert "variety" in note
    assert "그건 ~가 아니라 ~야 가 네 번" in note
    assert "츳코미 문형을 바꿔라" in note
    assert "premise" not in note  # 통과한 항목까지 지적하면 집필이 헷갈린다


def test_nothing_to_say_when_everything_passes():
    assert review.feedback(full(5)) == ""
