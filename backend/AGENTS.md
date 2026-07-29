# AGENTS.md

AI 코딩 에이전트(Claude Code, Codex 등)가 이 저장소에서 작업할 때 따라야 할 공통 규칙입니다.
모든 팀원(A/B/프론트/디자이너)이 함께 참조하는 단일 진실 소스입니다.

## 프로젝트 개요

중고 매물의 링크/스크린샷을 넣으면 가격 적정성과 상태를 AI가 판별해주는 소비자용 앱.
Upstage Document Parse·Information Extract로 매물 정보를 구조화하고, Solar LLM으로 상태 등급·주의 신호·거래 체크리스트를 생성한다.

## 기술 스택

- **Frontend**: React Native (Expo), TypeScript, Zustand, React Query
- **Backend**: FastAPI, Python, PostgreSQL(Supabase)
- **AI**: Upstage Document Parse, Information Extract, Solar LLM
- **Backend 로직**: URL 파싱, Rule Engine, 신뢰도 점수 계산, 체크리스트 생성

## 팀 역할 분담

| 담당 | 영역 | 비고 |
|---|---|---|
| Backend A | AI 분석 파이프라인 (Upstage/Solar 직접 연동) | `/analyze`, `/price-analysis`, `/condition-analysis`, `/compare`, `/generate-questions`, `/generate-negotiation` |
| Backend B (ym) | 서비스·DB (인증, 매물관리, 찜, 기록, 비교, 거래, 마이페이지) | `/listing`, `/bookmark`, `/history`, `/comparison`, `/transaction`, `/mypage` |
| Frontend | React Native 화면 구현, mock → 실데이터 전환 | |
| Design | 화면 디자인 | |

## API 계약 (스키마 확정 후 채우기)

> ⚠️ 아래 스키마는 A가 오늘 확정 예정. 확정되는 대로 이 섹션을 업데이트할 것.

### `/analyze` 응답 스키마 (TBD)
- Backend B의 `/listing`과 Frontend 화면4(분석 결과)가 이 스키마에 의존함
- 확정 즉시 여기에 필드 정의 붙여넣기

### `/compare`, `/generate-questions`, `/generate-negotiation` 응답 스키마 (TBD)
- Backend B의 `/comparison`, `/transaction`이 이 결과값 구조를 참조함

## 공통 규칙

### API 응답 형식
```json
{ "ok": true, "data": {}, "error": null }
```
- 성공: `ok: true`, `data`에 실제 페이로드
- 실패: `ok: false`, `error`에 메시지/코드

### 커밋 컨벤션
- 형식: `feat|fix|docs|refactor(scope): 제목` — 제목 100자 이내
- 기능 단위로 자주, 작게 커밋 (히스토리 추적 용이하게)

### 브랜치 전략
- 기능 단위 브랜치, PR로 머지 (본 스켈레톤 브랜치는 리뷰 목적, 머지 대상 아님)

### 보안
- API 키, DB 접속정보는 `.env`에만 — 절대 커밋 금지
- `.claude/`, `AGENTS.md`, `CLAUDE.md`는 저장소에 커밋 (secrets 제외)

## 빌드 · 테스트 (TBD)

> 환경 설정 완료 후 채우기

```bash
# 설치
# 실행
# 테스트
```

## 에이전트 작업 방식 권장

- **plan 모드부터**: 큰 기능은 바로 코딩하지 말고 설계 검토 → 승인 후 구현
- **작은 커밋**: 기능 단위로 자주 커밋
- **테스트 우선**: 가능하면 테스트 먼저 작성 후 통과까지 확인
- **AI 활용 기록**: 작업 세션마다 한 줄씩 무엇을 AI와 함께 했는지 남기기 (데모/회고용)

## 데이터베이스 (Backend B 소관 테이블, TBD)

> 스키마 확정 후 채우기: 매물, 찜, 분석기록, 비교목록, 거래상태, 마이페이지 집계용 테이블

## 참고

- Analysis History, Product Rules, Scam Patterns, Checklist Templates 중 Product Rules·Scam Patterns·Checklist Templates는 Backend A 소관 (Rule Engine·체크리스트 생성 로직 참조용)
- Analysis History는 Backend B 소관
