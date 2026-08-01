FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# 의존성을 먼저 굳혀서 소스만 바뀔 때 이 레이어를 다시 받지 않게 한다.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY templates ./templates
COPY static ./static

EXPOSE 8000
# ponytail: 단일 스테이지라 이미지가 493MB다. 멀티스테이지로 .venv만 옮기면
# 절반 아래로 떨어진다. pull이 느려서 데모에 걸리면 그때 쪼갠다.
# DEEPSEEK_API_KEY는 이미지에 굽지 않는다. 실행 시점에 -e 로 넣는다.
CMD ["uv", "run", "--no-dev", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
