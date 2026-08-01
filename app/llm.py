import asyncio
import logging
import os

import httpx

# Upstage Solar. OpenAI 호환 엔드포인트라 응답 형태가 같다.
API_URL = "https://api.upstage.ai/v1/chat/completions"
MODEL = "solar-pro3"

# 추론을 켜고 대본 전체를 쓰므로 한 호출이 길다. 그래도 무한정 기다리진 않는다.
TIMEOUT = httpx.Timeout(120.0)
ATTEMPTS = 3

log = logging.getLogger(__name__)


def require_api_key() -> str:
    """키를 읽고, 없으면 즉시 실패한다.

    서버 기동 시점에 불러서 첫 만담 도중이 아니라 시작할 때 터지게 한다.
    """
    key = os.environ.get("UPSTAGE_API_KEY")
    if not key:
        raise RuntimeError(
            "UPSTAGE_API_KEY가 없다. .env에 넣고 `uv run uvicorn app.main:app --env-file .env` 로 실행한다."
        )
    return key


async def complete(
    system: str,
    messages: list[dict[str, str]],
    temperature: float = 1.0,
    json_mode: bool = False,
    max_tokens: int | None = None,
    effort: str | None = None,
) -> str:
    """Solar를 한 번 부른다.

    호출 하나가 늘어지면 공연이 통째로 멈춘다. 여기서 다시 걸어보고, 그래도 안
    되면 그때 포기한다.
    """
    payload: dict = {
        "model": MODEL,
        "temperature": temperature,
        "messages": [{"role": "system", "content": system}, *messages],
    }
    if effort:
        # solar-pro3는 추론을 끈 채로 온다. 켜야 대본이 대본다워진다.
        payload["reasoning_effort"] = effort
    if max_tokens:
        # 길이는 프롬프트로 안 잡힌다. 40자 넘지 말라고 해도 세 문장을 쓴다.
        payload["max_tokens"] = max_tokens
    if json_mode:
        # 형식을 모델 선의에 맡기지 않는다. 깨진 JSON은 파서로 못 살린다.
        payload["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for attempt in range(1, ATTEMPTS + 1):
            try:
                response = await client.post(
                    API_URL,
                    headers={"Authorization": f"Bearer {require_api_key()}"},
                    json=payload,
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"].strip()
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status is not None and status < 500 and status != 429:
                    raise  # 키가 틀렸거나 요청이 잘못됐다. 다시 걸어도 같다.
                if attempt == ATTEMPTS:
                    raise
                log.warning("Solar 호출 실패(%s/%s): %s", attempt, ATTEMPTS, exc)
                await asyncio.sleep(attempt)
    raise AssertionError("unreachable")
