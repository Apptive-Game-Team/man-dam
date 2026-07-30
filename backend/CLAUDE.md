@../AGENTS.md

# Backend 전용 지침
 
이 프로젝트의 Backend B(서비스·DB) 작업 시 Claude Code 전용 참고사항.
 
- FastAPI + PostgreSQL(Supabase) 기준으로 코드를 작성한다
- 새 엔드포인트나 스키마 변경은 `plan` 서브에이전트로 먼저 설계를 검토한다 (`.claude/agents/plan.md`)
- 공통 API 응답 형식·커밋 컨벤션은 `team-conventions` 스킬 참고 (`.claude/skills/team-conventions/`)