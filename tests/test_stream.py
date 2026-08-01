from app.main import render_bubble, sse
from app.script import BOKE, TSUKKOMI


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
