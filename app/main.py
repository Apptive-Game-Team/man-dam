import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.actions import EMOJI
from app.graph import BOKE, perform, random_topic
from app.llm import require_api_key

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    require_api_key()  # 첫 만담 도중이 아니라 기동할 때 터지게 한다
    yield


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


def render_bubble(
    speaker: str, text: str, role: str | None = None, action: str | None = None
) -> str:
    if role is None:
        role = "boke" if speaker == BOKE else "tsukkomi"
    return templates.get_template("bubble.html").render(
        speaker=speaker, text=text, role=role, emoji=EMOJI.get(action or "")
    )


@app.get("/")
async def index(request: Request, topic: str | None = None):
    return templates.TemplateResponse(request, "index.html", {"topic": topic or random_topic()})


@app.get("/stream")
async def stream(topic: str | None = None) -> StreamingResponse:
    subject = topic or random_topic()

    async def lines() -> AsyncIterator[str]:
        try:
            async for speaker, action, text in perform(subject):
                yield sse(render_bubble(speaker, text, action=action))
        except Exception:
            # 무대가 멈춘 채로 방치되면 뭐가 잘못됐는지 화면에서 알 수 없다.
            log.exception("만담 생성 실패")
            yield sse(render_bubble("무대", "대사를 받아오지 못했다. 서버 로그를 봐라.", "error"))
        # 이게 없으면 EventSource가 재연결해서 만담을 처음부터 다시 시작한다.
        yield sse("", event="close")

    return StreamingResponse(
        lines(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
