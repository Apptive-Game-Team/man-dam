from app import examples
from app.graph import script_system


def test_same_topic_example_is_left_out():
    # 주제가 같으면 모델이 예시의 전제와 오치를 그대로 베낀다.
    prompt = script_system("헬스장 등록")
    assert "회원권이 대신 운동한다" not in prompt


def test_partial_overlap_still_counts():
    assert examples.overlaps("헬스장 등록", "헬스장")
    assert examples.overlaps("헬스장", "헬스장 등록")
    assert examples.overlaps("중고 거래", "중고거래")  # 띄어쓰기만 다른 경우
    assert not examples.overlaps("다이어트", "고양이 키우기")
    assert not examples.overlaps("", "고양이 키우기")


def test_unrelated_topic_keeps_every_example():
    prompt = examples.as_prompt("고양이 키우기")
    for ex in examples.EXAMPLES:
        assert ex["premise"] in prompt


def test_nothing_left_falls_back_to_all():
    # 예시가 전부 걸러지면 그때는 넣는다. 예시 없는 프롬프트가 더 나쁘다.
    only = [{"topic": "다이어트", "premise": "p", "script": "s"}]
    saved, examples.EXAMPLES = examples.EXAMPLES, only
    try:
        assert "다이어트" in examples.as_prompt("다이어트")
    finally:
        examples.EXAMPLES = saved


def test_prompt_forbids_reusing_the_material():
    prompt = script_system("고양이 키우기")
    assert "재사용하지 마라" in prompt
