import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates

from app.script import BOKE, DUMMY_SCRIPT

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

app = FastAPI(title="man-dam")

# 읽는 속도. 짧은 대사가 순식간에 지나가지 않도록 하한을 둔다.
SECONDS_PER_CHAR = 0.055
MIN_DELAY = 1.0


def sse(payload: str, event: str | None = None) -> str:
    """SSE 프레임 하나로 감싼다.

    payload에 개행이 있으면 줄마다 `data:` 로 쪼갠다. 한 줄로 뭉치면 개행이
    사라지고, 그대로 넣으면 프레임이 깨진다.
    """
    head = f"event: {event}\n" if event else ""
    body = "".join(f"data: {line}\n" for line in payload.split("\n"))
    return f"{head}{body}\n"


def render_bubble(speaker: str, text: str) -> str:
    role = "boke" if speaker == BOKE else "tsukkomi"
    return templates.get_template("bubble.html").render(speaker=speaker, text=text, role=role)


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/stream")
async def stream() -> StreamingResponse:
    async def lines() -> AsyncIterator[str]:
        for speaker, text in DUMMY_SCRIPT:
            yield sse(render_bubble(speaker, text))
            await asyncio.sleep(max(MIN_DELAY, len(text) * SECONDS_PER_CHAR))
        # 이게 없으면 EventSource가 재연결해서 대본을 무한 반복한다.
        yield sse("", event="close")

    return StreamingResponse(
        lines(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
