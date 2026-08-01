import pytest

from app.graph import BOKE, MAX_LINES, TSUKKOMI, keep_going, transcript
from app.llm import require_api_key
from app.main import render_bubble, sse


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


def test_transcript_first_line_has_no_history():
    text = transcript({"topic": "카페 창업", "lines": []})
    assert "카페 창업" in text
    assert "지금까지의 만담" not in text


def test_transcript_carries_history():
    text = transcript(
        {"topic": "카페 창업", "lines": [(BOKE, "카페 차렸어"), (TSUKKOMI, "뭔 소리야")]}
    )
    assert "ChatGPT: 카페 차렸어" in text
    assert "Claude: 뭔 소리야" in text


def test_graph_stops_at_limit():
    # 상한이 없으면 그래프가 영원히 돈다.
    assert keep_going({"topic": "x", "lines": [(BOKE, "a")] * MAX_LINES}) == "__end__"
    assert keep_going({"topic": "x", "lines": [(BOKE, "a")]}) == "boke"


def test_missing_api_key_fails_loudly(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        require_api_key()
