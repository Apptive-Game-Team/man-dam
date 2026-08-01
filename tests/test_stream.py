import pytest

from app.graph import BOKE, MAX_LINES, TSUKKOMI, keep_going, transcript
from app.llm import require_api_key
from app.main import render_bubble, render_sticker, sse


def test_sse_frame():
    assert sse("hello") == "data: hello\n\n"


def test_sse_splits_newlines():
    # 한 줄로 뭉치면 개행이 사라지고, 그대로 넣으면 프레임이 깨진다.
    assert sse("a\nb") == "data: a\ndata: b\n\n"


def test_sse_named_event():
    assert sse("", event="close") == "event: close\ndata: \n\n"


def test_bubble_escapes_text():
    # LLM 출력이 이 경로로 들어온다. 태그가 살아나오면 주입이다.
    assert "<script>" not in render_bubble(BOKE, "<script>alert(1)</script>")


def test_bubble_marks_role():
    assert 'class="line boke"' in render_bubble(BOKE, "만담")
    assert 'class="line tsukkomi"' in render_bubble(TSUKKOMI, "만담")
    assert 'class="line error"' in render_bubble("무대", "사고", "error")


def test_sticker_is_its_own_message():
    html = render_sticker(TSUKKOMI, "츳코미")
    assert 'class="line tsukkomi sticker"' in html
    assert "/static/emoji/tsukkomi.svg" in html
    assert "bubble" not in html  # 말풍선에 얹히는 장식이 아니다


def test_transcript_first_line_has_no_history():
    text = transcript({"topic": "카페 창업", "lines": []})
    assert "카페 창업" in text
    assert "지금까지의 만담" not in text


def test_transcript_carries_history():
    text = transcript(
        {
            "topic": "카페 창업",
            "lines": [(BOKE, None, "카페 차렸어"), (TSUKKOMI, "츳코미", "뭔 소리야")],
        }
    )
    assert "ChatGPT: 카페 차렸어" in text
    assert "Claude: 뭔 소리야" in text
    # 액션 이름은 다음 턴 컨텍스트에 끼어들지 않는다.
    assert "츳코미: " not in text


def test_graph_stops_at_limit():
    # 상한이 없으면 그래프가 영원히 돈다.
    assert keep_going({"topic": "x", "lines": [(BOKE, None, "a")] * MAX_LINES}) == "__end__"
    assert keep_going({"topic": "x", "lines": [(BOKE, None, "a")]}) == "boke"


def test_missing_api_key_fails_loudly(monkeypatch):
    monkeypatch.delenv("UPSTAGE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="UPSTAGE_API_KEY"):
        require_api_key()
