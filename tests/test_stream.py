import pytest

from app.graph import (
    FALLBACK_PLAN,
    MAX_LINES,
    brief_for,
    clean_script,
    name_of,
    parse_plan,
    persona,
)
from app.llm import require_api_key
from app.main import render_bubble, render_sticker, sse

PLAN = {
    "boke": {"name": "만식", "quirk": "카페를 상상으로 운영한다"},
    "tsukkomi": {"name": "담이", "style": "짧게 끊어 친다"},
    "premise": "친구가 카페를 차렸다고 한다",
    "beats": ["원두를 안 산다", "가게가 머릿속에 있다"],
    "punchline": "그럼 나도 은행 세 개 굴린다",
}


def state(lines=()):
    return {"topic": "카페 창업", "plan": PLAN, "lines": list(lines)}


def test_sse_frame():
    assert sse("hello") == "data: hello\n\n"


def test_sse_splits_newlines():
    # 한 줄로 뭉치면 개행이 사라지고, 그대로 넣으면 프레임이 깨진다.
    assert sse("a\nb") == "data: a\ndata: b\n\n"


def test_sse_named_event():
    assert sse("", event="close") == "event: close\ndata: \n\n"


def test_bubble_escapes_text():
    # LLM 출력이 이 경로로 들어온다. 태그가 살아나오면 주입이다.
    assert "<script>" not in render_bubble("boke", "만식", "<script>alert(1)</script>")


def test_bubble_marks_role():
    assert 'class="line boke"' in render_bubble("boke", "만식", "만담")
    assert 'class="line tsukkomi"' in render_bubble("tsukkomi", "담이", "만담")
    assert 'class="line error"' in render_bubble("error", "무대", "사고")


def test_bubble_shows_the_name_not_the_role():
    html = render_bubble("tsukkomi", "담이", "뭔 소리야")
    assert "담이" in html
    assert "츳코미" not in html  # 배역은 화면에 쓰지 않는다


def test_sticker_is_its_own_message():
    html = render_sticker("tsukkomi", "때리기")
    assert 'class="line tsukkomi sticker"' in html
    assert "/static/emoji/tsukkomi.svg" in html
    assert "bubble" not in html  # 말풍선에 얹히는 장식이 아니다


def test_plan_reaches_the_prompt():
    brief = (
        brief_for(state())["content"]
        if isinstance(brief_for(state()), dict)
        else brief_for(state())[0]["content"]
    )
    assert "친구가 카페를 차렸다고 한다" in brief
    assert "원두를 안 산다" in brief
    assert "그럼 나도 은행 세 개 굴린다" in brief


def test_script_keeps_only_usable_lines():
    raw = [
        {"who": "boke", "action": None, "text": "카페 차렸어"},
        {"who": "tsukkomi", "action": "때리기", "text": "뭔 소리야"},
        {"who": "boke", "action": None, "text": ""},  # 빈 대사
        {"who": "narrator", "action": None, "text": "해설"},  # 모르는 배역
        {"who": "boke", "action": None, "text": "[액션:때리기]"},  # 태그뿐
        "쓰레기",
    ]
    lines = clean_script(raw, PLAN)
    assert [(r, n, a, t) for r, n, a, t in lines] == [
        ("boke", "만식", None, "카페 차렸어"),
        ("tsukkomi", "담이", "때리기", "뭔 소리야"),
    ]


def test_script_caps_at_the_limit():
    raw = [{"who": "boke", "text": f"대사 {i}"} for i in range(MAX_LINES + 5)]
    assert len(clean_script(raw, PLAN)) == MAX_LINES


def test_unknown_action_name_is_dropped():
    lines = clean_script([{"who": "boke", "action": "공중제비", "text": "어어"}], PLAN)
    assert lines[0][2] is None


def test_plan_json_survives_a_code_fence():
    reply = '설명입니다\n```json\n{"boke": {"name": "봉수"}}\n```'
    assert parse_plan(reply)["boke"]["name"] == "봉수"


def test_plan_without_json_is_rejected():
    with pytest.raises(ValueError):
        parse_plan("죄송합니다, 만들 수 없습니다.")


def test_partial_plan_falls_back_field_by_field():
    # 모델이 quirk를 빼먹어도 페르소나 문장이 비지 않아야 한다.
    plan = {"boke": {"name": "봉수"}}
    assert name_of(plan, "boke") == "봉수"
    assert FALLBACK_PLAN["boke"]["quirk"] in persona(plan, "boke")
    assert name_of(plan, "tsukkomi") == FALLBACK_PLAN["tsukkomi"]["name"]


def test_missing_api_key_fails_loudly(monkeypatch):
    monkeypatch.delenv("UPSTAGE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="UPSTAGE_API_KEY"):
        require_api_key()


def test_bad_names_fall_back():
    # 한 글자 이름이나 영어 이름이 화면에 그대로 나가면 안 된다.
    for bad in ("철", "Bob", "김철수철수", "", "민 재"):
        assert name_of({"boke": {"name": bad}}, "boke") == FALLBACK_PLAN["boke"]["name"]
    assert name_of({"boke": {"name": "민재"}}, "boke") == "민재"
