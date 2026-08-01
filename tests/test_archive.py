import importlib

import pytest


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("MANDAM_DB", str(tmp_path / "man-dam.sqlite3"))
    from app import archive

    return importlib.reload(archive)


PLAN = {
    "boke": {"name": "만식"},
    "tsukkomi": {"name": "담이"},
    "premise": "카페를 상상으로 운영한다",
    "punchline": "가게가 머릿속에 있다",
}
LINES = [("boke", "만식", None, "카페 차렸어"), ("tsukkomi", "담이", "때리기", "뭔 소리야")]


def test_survives_across_connections(store):
    store.save("카페 창업", PLAN, LINES, {"scores": {"premise": 5}}, 17, 1)
    # 새 연결로 다시 읽는다. 파일에 남지 않으면 여기서 빈다.
    assert importlib.reload(store).best()[0]["score"] == 17


def test_best_is_sorted_by_score(store):
    for topic, score in (("낮은 것", 4), ("높은 것", 19), ("중간", 11)):
        store.save(topic, PLAN, LINES, None, score, 0)
    assert [row["topic"] for row in store.best()] == ["높은 것", "중간", "낮은 것"]
    assert [row["topic"] for row in store.best(limit=1)] == ["높은 것"]


def test_script_round_trips(store):
    store.save("카페 창업", PLAN, LINES, None, 12, 0)
    script = store.best()[0]["script"]
    assert script[1] == {"who": "tsukkomi", "name": "담이", "action": "때리기", "text": "뭔 소리야"}


def test_a_broken_store_does_not_kill_the_show(store, monkeypatch, tmp_path):
    # 기록이 실패해도 공연은 이미 끝났다. 여기서 예외가 나가면 안 된다.
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "없는디렉터리" / "x" / "y.sqlite3")
    monkeypatch.setattr(store.Path, "mkdir", lambda *a, **k: (_ for _ in ()).throw(OSError))
    store.save("카페 창업", PLAN, LINES, None, 12, 0)
