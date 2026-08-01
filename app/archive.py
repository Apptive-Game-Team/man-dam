"""공연 기록.

무대에 올린 대본과 그 점수를 남긴다. 남기는 이유는 둘이다.

프롬프트를 고쳤을 때 나아졌는지 눈대중이 아니라 점수로 말하려는 것이고,
점수 높은 대본이 쌓이면 그게 그대로 `app/examples.py` 에 넣을 예시가 된다.
직접 만든 것만 쌓이므로 출처도 깨끗하다.

SQLite 파일 하나다. `sqlite3` 는 표준 라이브러리라 의존성이 늘지 않고, 점수로
정렬해서 상위 대본을 뽑는 게 한 줄이라 목적에 맞는다.
"""

import json
import logging
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("MANDAM_DB") or BASE_DIR / "data" / "man-dam.sqlite3")

SCHEMA = """
CREATE TABLE IF NOT EXISTS performances (
    id        INTEGER PRIMARY KEY,
    at        TEXT    NOT NULL,
    topic     TEXT    NOT NULL,
    score     INTEGER NOT NULL,
    rewrites  INTEGER NOT NULL,
    scores    TEXT,
    notes     TEXT,
    boke      TEXT,
    tsukkomi  TEXT,
    premise   TEXT,
    punchline TEXT,
    script    TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS performances_score ON performances (score DESC);
"""

log = logging.getLogger(__name__)


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def save(
    topic: str,
    plan: dict,
    lines: list[tuple[str, str, str | None, str]],
    verdict: dict | None,
    score: int,
    rewrites: int,
) -> None:
    """공연 하나를 기록한다. 기록에 실패해도 공연은 이미 끝났으니 넘어간다."""
    script = [
        {"who": role, "name": name, "action": action, "text": text}
        for role, name, action, text in lines
    ]
    verdict = verdict or {}
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO performances"
                " (at, topic, score, rewrites, scores, notes, boke, tsukkomi,"
                "  premise, punchline, script)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    datetime.now(UTC).isoformat(timespec="seconds"),
                    topic,
                    score,
                    rewrites,
                    json.dumps(verdict.get("scores"), ensure_ascii=False),
                    json.dumps(verdict.get("notes"), ensure_ascii=False),
                    (plan.get("boke") or {}).get("name"),
                    (plan.get("tsukkomi") or {}).get("name"),
                    plan.get("premise"),
                    plan.get("punchline"),
                    json.dumps(script, ensure_ascii=False),
                ),
            )
    except (sqlite3.Error, OSError):
        log.exception("공연 기록 실패")


def best(limit: int = 10) -> list[dict]:
    """점수 높은 순으로 꺼낸다. 예시 코퍼스를 고를 때 쓴다."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT topic, score, premise, punchline, script"
            " FROM performances ORDER BY score DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [{**dict(row), "script": json.loads(row["script"])} for row in rows]
