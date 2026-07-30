---
name: team-conventions
description: API 응답 형식, 에러 처리, 커밋 규칙 등 팀 컨벤션 적용이 필요할 때 사용. 새 엔드포인트를 만들거나 기존 코드를 팀 규칙에 맞게 고칠 때 참고.
---

## API 응답 형식

모든 엔드포인트 응답은 다음 형태를 따른다.

```json
{ "ok": true, "data": {}, "error": null }
```

- 성공: `ok: true`, `data`에 실제 페이로드
- 실패: `ok: false`, `data: null`, `error`에 `{ "code": "...", "message": "..." }` 형태로 담기

## 커밋 컨벤션

형식: `feat|fix|docs|refactor(scope): 제목`

- 제목은 100자 이내
- scope는 담당 영역 축약형 사용 (예: `listing`, `bookmark`, `mypage`)
- 기능 단위로 자주, 작게 커밋

예시:
```
feat(listing): POST /listing 엔드포인트 추가
fix(bookmark): 중복 찜 등록 방지 로직 수정
```

## 에러 처리

- 예외는 상위에서 잡아 표준 에러 응답으로 변환한다 (raw traceback을 클라이언트에 노출하지 않는다)
- 4xx는 클라이언트 오류(요청 검증 실패 등), 5xx는 서버 오류로 구분한다

## 담당 범위 (Backend B)

`/listing`, `/bookmark`, `/history`, `/comparison`, `/transaction`, `/mypage` — 이 범위 밖의 AI 분석 관련 엔드포인트(`/analyze`, `/compare` 등)는 Backend A 소관이니 스키마 변경 시 먼저 확인한다.

## 보안

- API 키, DB 접속정보는 `.env`에만 — 코드에 하드코딩하거나 커밋하지 않는다
