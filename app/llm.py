"""두 모델을 쓴다. 각자 잘하는 자리에 놓는다.

Solar는 짧은 프롬프트에 구조화된 JSON을 뱉는 일을 잘한다. 대신 프롬프트가
2KB를 넘고 추론까지 켜면 180초를 넘겨 응답이 오지 않는 것을 확인했다. 그래서
기획과 리뷰를 맡는다. 둘 다 지시가 짧다.

집필은 예시 대본이 통째로 들어간 긴 프롬프트를 버텨야 해서 DeepSeek이 맡는다.

호출은 LangSmith에 남긴다. langchain 클라이언트가 아니라 httpx로 직접 부르므로
그래프 노드만으로는 안 잡히고, 이 함수에 `@traceable` 을 걸어야 입력과 출력이
보인다. `LANGSMITH_TRACING` 이 꺼져 있으면 데코레이터는 아무 일도 하지 않는다.
"""

import asyncio
import logging
import os
from dataclasses import dataclass

import httpx
from langsmith import traceable

TIMEOUT = httpx.Timeout(120.0)
ATTEMPTS = 3

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Provider:
    name: str
    url: str
    model: str
    env: str
    reasoning: bool = False


SOLAR = Provider(
    name="Upstage Solar",
    url="https://api.upstage.ai/v1/chat/completions",
    model="solar-pro3",
    env="UPSTAGE_API_KEY",
    reasoning=True,
)

DEEPSEEK = Provider(
    name="DeepSeek",
    url="https://api.deepseek.com/chat/completions",
    model="deepseek-chat",
    env="DEEPSEEK_API_KEY",
)

PROVIDERS = (SOLAR, DEEPSEEK)


def require_api_key(provider: Provider) -> str:
    key = os.environ.get(provider.env)
    if not key:
        raise RuntimeError(
            f"{provider.env}가 없다({provider.name}). .env에 넣고 "
            "`uv run uvicorn app.main:app --env-file .env` 로 실행한다."
        )
    return key


def require_all_keys() -> None:
    """기동 시점에 전부 확인한다. 만담 중간에 한쪽만 없는 걸 알게 되면 늦다."""
    for provider in PROVIDERS:
        require_api_key(provider)


@traceable(run_type="llm", name="chat")
async def complete(
    provider: Provider,
    system: str,
    messages: list[dict[str, str]],
    temperature: float = 1.0,
    json_mode: bool = False,
    max_tokens: int | None = None,
    effort: str | None = None,
) -> str:
    """한 번 부른다. 늘어지거나 5xx면 다시 걸고, 그래도 안 되면 포기한다."""
    payload: dict = {
        "model": provider.model,
        "temperature": temperature,
        "messages": [{"role": "system", "content": system}, *messages],
    }
    if effort and provider.reasoning:
        payload["reasoning_effort"] = effort
    if max_tokens:
        payload["max_tokens"] = max_tokens
    if json_mode:
        # 형식을 모델 선의에 맡기지 않는다. 깨진 JSON은 파서로 못 살린다.
        payload["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for attempt in range(1, ATTEMPTS + 1):
            try:
                response = await client.post(
                    provider.url,
                    headers={"Authorization": f"Bearer {require_api_key(provider)}"},
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
                log.warning("%s 호출 실패(%s/%s): %s", provider.name, attempt, ATTEMPTS, exc)
                await asyncio.sleep(attempt)
    raise AssertionError("unreachable")
