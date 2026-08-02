import json

from app import verify


def reply(scores=None, notes=None):
    payload = {}
    if scores is not None:
        payload["scores"] = scores
    if notes is not None:
        payload["notes"] = notes
    return json.dumps(payload, ensure_ascii=False)


def test_every_anchor_reaches_the_prompt():
    prompt = verify.system_prompt()
    for key, scale in verify.SCALES.items():
        assert key in prompt
        assert scale["question"] in prompt
        for point in verify.POINTS:
            assert scale[point] in prompt  # 중간 기준이 빠지면 점수가 최하로 눌린다
    assert verify.EXAMPLES[0]["script"] in prompt


def test_scores_survive_the_round_trip():
    got = verify.verdict_of(
        reply({"funny": 8, "coherence": 4}, {"funny": "마지막 줄에서 뒤집힌다"})
    )
    assert got["scores"] == {"funny": 8, "coherence": 4}
    assert got["notes"]["funny"] == "마지막 줄에서 뒤집힌다"
    assert got["notes"]["coherence"] == ""


def test_broken_or_missing_scores_count_as_zero():
    # 봐주면 검증이 아니라 응원이 된다.
    assert verify.verdict_of("JSON 아님")["scores"]["funny"] == 0
    assert verify.verdict_of(reply())["scores"]["funny"] == 0
    assert verify.verdict_of(reply("망함"))["scores"]["funny"] == 0
    assert verify.verdict_of(reply({"funny": "여덟"}))["scores"]["funny"] == 0
    assert verify.verdict_of(reply({"funny": True}))["scores"]["funny"] == 0
    assert verify.verdict_of("[1, 2]")["scores"]["funny"] == 0


def test_scores_outside_the_scale_get_clamped():
    assert verify.verdict_of(reply({"funny": 99}))["scores"]["funny"] == verify.TOP
    assert verify.verdict_of(reply({"funny": -3}))["scores"]["funny"] == 0


def test_the_two_axes_are_scored_apart():
    # 딴소리인데 웃긴 대본이 있다. 한쪽 점수가 다른 쪽을 끌고 가면 못 본다.
    got = verify.verdict_of(reply({"funny": 9, "coherence": 1}))
    assert got["scores"] == {"funny": 9, "coherence": 1}
