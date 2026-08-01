# man-dam (만담)

AI 캐릭터 둘이서 만담(漫才)을 주고받는 웹 앱. 단톡방처럼 대사가 실시간으로 쌓이고, "머리 때리기" 같은 리액션은 카톡 이모티콘처럼 움직이는 이미지로 뜬다.

> AI Builder Sprint 2026 출품작

## 어떻게 굴러가나

```
브라우저 (Jinja2 + HTMX)
    │  SSE
    ▼
FastAPI  ──▶  LangGraph  ──▶  Upstage Solar
                 │
                 ├─ 보케 노드   "ChatGPT" 페르소나 — 엉뚱한 소리
                 └─ 츳코미 노드 "Claude"  페르소나 — 즉시 태클
```

두 캐릭터 모두 Solar 한 모델로 돌린다. 다른 건 페르소나 프롬프트뿐이다.

LLM이 대사에 액션 태그를 섞어서 뱉는다.

```
[액션:츳코미] 아니 그게 말이 되냐고!
```

서버가 태그를 떼어내고 `static/emoji/` 의 움직이는 이모티콘을 **별개의 메시지로** 띄운다. 카톡에서 이모티콘이 말풍선이 아니라 그 자체로 하나의 메시지인 것과 같다.

## 실행

```bash
uv sync
echo "UPSTAGE_API_KEY=sk-..." > .env
uv run uvicorn app.main:app --reload --env-file .env
```

http://localhost:8000 — 주제를 바꾸려면 상단 입력칸에 넣고 "이 주제로".

키가 없으면 서버가 기동 시점에 실패한다. 첫 만담 도중에 터지는 것보다 낫다.

### 실행 추적 (선택)

어느 단계에서 시간이 가고 어디서 무너지는지 보려면 [LangSmith](https://smith.langchain.com) 를 켠다.

```bash
cat >> .env <<'ENV'
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=man-dam
ENV
```

기획, 집필, 심사, 재작성 판정이 노드별로 남고 Solar/DeepSeek 호출이 그 아래 붙는다. 키가 없으면 추적만 꺼지고 앱은 그대로 돈다.

대사 원문이 LangSmith로 나간다. 개인정보는 없지만 알고 켜라.

### 컨테이너로 실행

`main` 에 푸시될 때마다 이미지가 GHCR에 올라간다.

```bash
docker run --rm -p 8000:8000 -e UPSTAGE_API_KEY=sk-... ghcr.io/apptive-game-team/man-dam:latest
```

`latest` 외에 커밋 SHA 태그도 붙는다. 특정 시점 이미지가 필요하면 `:<commit-sha>` 를 쓴다. 키는 이미지에 들어있지 않다. 실행할 때 넘겨야 한다.

## 스택 선택 이유

| 선택 | 이유 |
|---|---|
| Jinja2 | FastAPI 기본 템플릿 엔진. 별도 프론트 빌드 없음 |
| HTMX + SSE | 대사가 한 줄씩 떨어져야 단톡방 느낌이 산다. 단방향이라 WebSocket 불필요 |
| Upstage Solar | 한국어 구어체 만담이 소재다. 국내 모델을 쓴다. OpenAI 호환이라 호출 코드는 그대로 |
| LangGraph | 턴 교대와 종료 판정이 그래프로 그대로 표현된다 |
| SVG/APNG 이모티콘 | 런타임 애니메이션 라이브러리 없이 `<img>` 하나로 끝 |
| GHCR + Actions | 이미지 하나로 어디서든 같은 결과. 인증은 워크플로 기본 토큰으로 끝난다 |
| LangSmith | 노드가 다섯이라 로그로는 어디서 무너지는지 못 본다. 선택 사항이라 없어도 돈다 |

## 상태

만담 생성, 스트리밍, 액션 이모티콘 동작.
