import os

import httpx

API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"
TIMEOUT = httpx.Timeout(60.0)


def require_api_key() -> str:
    """키를 읽고, 없으면 즉시 실패한다.

    서버 기동 시점에 불러서 첫 만담 도중이 아니라 시작할 때 터지게 한다.
    """
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY가 없다. .env에 넣고 `uv run uvicorn app.main:app --env-file .env` 로 실행한다."
        )
    return key


async def complete(system: str, user: str, temperature: float = 1.0) -> str:
    """대사 한 줄을 받아온다.

    temperature를 1.3까지 올리면 후반 대사가 문장으로 성립하지 않는다. 1.0이
    엉뚱함과 말이 되는 것 사이의 경계였다.
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(
            API_URL,
            headers={"Authorization": f"Bearer {require_api_key()}"},
            json={
                "model": MODEL,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
