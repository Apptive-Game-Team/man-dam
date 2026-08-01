# man-dam (만담)

AI 캐릭터 둘이서 만담(漫才)을 주고받는 웹 앱. 단톡방처럼 대사가 실시간으로 쌓이고, "머리 때리기" 같은 리액션은 카톡 이모티콘처럼 움직이는 이미지로 뜬다.

> AI Builder Sprint 2026 출품작

## 어떻게 굴러가나

```
브라우저 (Jinja2 + HTMX)
    │  SSE
    ▼
FastAPI  ──▶  LangGraph  ──▶  DeepSeek API
                 │
                 ├─ 보케 노드   "ChatGPT" 페르소나 — 엉뚱한 소리
                 └─ 츳코미 노드 "Claude"  페르소나 — 즉시 태클
```

두 캐릭터 모두 DeepSeek 한 모델로 돌린다. 다른 건 페르소나 프롬프트뿐이다.

LLM이 대사에 액션 태그를 섞어서 뱉는다.

```
[액션:츳코미] 아니 그게 말이 되냐고!
```

서버가 태그를 떼어내고 `static/emoji/` 의 움직이는 이모티콘으로 바꿔서 말풍선 옆에 붙인다.

## 실행

```bash
uv sync
export DEEPSEEK_API_KEY=sk-...
uv run uvicorn app.main:app --reload
```

http://localhost:8000

## 스택 선택 이유

| 선택 | 이유 |
|---|---|
| Jinja2 | FastAPI 기본 템플릿 엔진. 별도 프론트 빌드 없음 |
| HTMX + SSE | 대사가 한 줄씩 떨어져야 단톡방 느낌이 산다. 단방향이라 WebSocket 불필요 |
| LangGraph | 턴 교대와 종료 판정이 그래프로 그대로 표현된다 |
| SVG/APNG 이모티콘 | 런타임 애니메이션 라이브러리 없이 `<img>` 하나로 끝 |

## 상태

기획 및 부트스트랩 단계. 구현 전.
