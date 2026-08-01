import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.actions import EMOJI
from app.graph import perform, random_topic
from app.llm import require_all_keys

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    require_all_keys()  # 첫 만담 도중이 아니라 기동할 때 터지게 한다
    yield


# 읽는 속도. 짧은 대사가 순식간에 지나가지 않도록 하한을 둔다.
SECONDS_PER_CHAR = 0.055
MIN_DELAY = 1.0
BEAT = 0.45  # 대사와 리액션 사이의 한 박자

app = FastAPI(title="man-dam", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


def sse(payload: str, event: str | None = None) -> str:
    """SSE 프레임 하나로 감싼다.

    payload에 개행이 있으면 줄마다 `data:` 로 쪼갠다. 한 줄로 뭉치면 개행이
    사라지고, 그대로 넣으면 프레임이 깨진다.
    """
    head = f"event: {event}\n" if event else ""
    body = "".join(f"data: {line}\n" for line in payload.split("\n"))
    return f"{head}{body}\n"


def render_bubble(role: str, speaker: str, text: str) -> str:
    return templates.get_template("bubble.html").render(speaker=speaker, text=text, role=role)


def render_sticker(role: str, action: str) -> str:
    """이모티콘은 말풍선에 붙는 장식이 아니라 그 자체로 하나의 메시지다."""
    return templates.get_template("sticker.html").render(
        role=role, emoji=EMOJI[action], label=action
    )


@app.get("/")
async def index(request: Request, topic: str | None = None):
    return templates.TemplateResponse(request, "index.html", {"topic": topic or random_topic()})


@app.get("/stream")
async def stream(topic: str | None = None) -> StreamingResponse:
    subject = topic or random_topic()

    async def lines() -> AsyncIterator[str]:
        try:
            first = True
            async for role, speaker, action, text in perform(subject):
                # 대본은 한 번에 완성되어 오지만 화면에는 읽는 속도로 흘린다.
                # 12줄이 한꺼번에 쏟아지면 만담이 아니라 로그다.
                if not first:
                    await asyncio.sleep(max(MIN_DELAY, len(text) * SECONDS_PER_CHAR))
                first = False
                yield sse(render_bubble(role, speaker, text))
                if action:
                    # 대사가 먼저, 리액션이 뒤. 그래야 한 박자 늦게 얻어맞는다.
                    await asyncio.sleep(BEAT)
                    yield sse(render_sticker(role, action))
        except Exception:
            # 무대가 멈춘 채로 방치되면 뭐가 잘못됐는지 화면에서 알 수 없다.
            log.exception("만담 생성 실패")
            yield sse(render_bubble("error", "무대", "대사를 받아오지 못했다. 서버 로그를 봐라."))
        # 이게 없으면 EventSource가 재연결해서 만담을 처음부터 다시 시작한다.
        yield sse("", event="close")

    return StreamingResponse(
        lines(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
