# Project Context

Agents must verify commands against repository configuration before running them.

## Overview

- Product: man-dam — AI 캐릭터끼리 만담(漫才)을 주고받는 웹 앱. 단톡방 UI로 대사가 실시간으로 쌓이고, 리액션 액션(츳코미, 넘어짐 등)은 움직이는 이모티콘으로 표시된다.
- Primary users: AI Builder Sprint 2026 심사위원 및 데모 관객
- Core domain: 만담 대본 생성(보케/츳코미 턴 교대), 액션 태그 파싱, 이모티콘 렌더링
- Runtime environment: Python 3.12+, FastAPI, 로컬 단일 프로세스

## Architecture

- Entry points: `app/main.py` (FastAPI ASGI 앱)
- Main modules:
  - `app/graph.py` — LangGraph. 보케 노드 / 츳코미 노드 / 종료 판정
  - `app/llm.py` — DeepSeek 클라이언트 (OpenAI 호환 엔드포인트)
  - `app/actions.py` — 대사 속 `[액션:*]` 태그 파싱 → 이모티콘 매핑
  - `templates/` — Jinja2. 단톡방 화면
  - `static/emoji/` — 움직이는 이모티콘 에셋 (SVG SMIL / APNG)
- Dependency direction: `main` → `graph` → `llm`. `actions`는 leaf. 템플릿은 라우터에서만 렌더.
- External systems: DeepSeek API (`DEEPSEEK_API_KEY`)
- Persistent data: 없음. 세션은 인메모리. 서버 재시작하면 날아간다.

## Characters

두 캐릭터 모두 DeepSeek 한 모델로 구동한다. 페르소나만 다르다.

| 배역 | 페르소나 | 역할 |
|---|---|---|
| 보케 (ボケ) | "ChatGPT" | 엉뚱한 소리를 진지하게 함 |
| 츳코미 (ツッコミ) | "Claude" | 즉시 태클. 액션 태그 대부분 여기서 나옴 |

## Commands

| Purpose | Command |
|---|---|
| Install dependencies | `uv sync` |
| Run locally | `uv run uvicorn app.main:app --reload --env-file .env` |
| Format | `uv run ruff format .` |
| Lint | `uv run ruff check .` |
| Type-check | TODO |
| Unit tests | `uv run pytest` |
| Integration tests | TODO |
| Build | 없음 (빌드 스텝 없이 실행) |

## Constraints

- Supported platforms: 최신 데스크톱 브라우저. 데모용이므로 구형 브라우저 미지원.
- Compatibility requirements: 대사 스트리밍은 SSE + HTMX. WebSocket 도입 금지 (단방향이라 불필요).
- Performance constraints: 첫 대사가 3초 안에 화면에 떠야 데모가 산다.
- Security or privacy requirements: `DEEPSEEK_API_KEY`는 환경변수로만. 커밋 금지. 클라이언트로 절대 노출 금지.

## Ownership

- Maintainers: Yunseong (me@yunseong.dev)
- Sensitive modules: `app/llm.py` (API 키 취급)
- Changes requiring explicit review: 프롬프트 변경 (만담 품질이 곧 제품이다)
