"""만담 그래프. 기획 한 번, 대본 한 번. 그게 전부다."""

import json
import logging
import operator
import random
import re
from collections.abc import AsyncIterator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph

from app.actions import EMOJI, PROMPT_RULE, split_action
from app.llm import complete

log = logging.getLogger(__name__)

# 대사 수 상한. 없으면 그래프가 영원히 돈다.
MAX_LINES = 12
# 이만큼도 못 건지면 무대에 올릴 게 없다.
MIN_LINES = 8
SCRIPT_ATTEMPTS = 2

TOPICS = [
    "카페 창업",
    "헬스장 등록",
    "중고거래",
    "고양이 키우기",
    "제주도 여행",
    "회사 워크숍",
    "명절 잔소리",
    "배달 음식",
]

PLAN_SYSTEM = """너는 한국어 만담(漫才) 작가다. 공연 하나를 통째로 설계한다.

만담은 두 사람이 한다. 보케는 엉뚱한 전제를 진지하게 밀어붙이고, 츳코미는 그걸 즉시 잡아챈다.
좋은 만담은 설정에서 시작해 같은 전제를 계단처럼 키우다가 오치 한 방으로 끝난다.

JSON 하나만 출력한다. 설명, 머리말, 코드 펜스를 붙이지 않는다.

{
  "boke": {"name": "이름", "quirk": "이 사람이 밀어붙일 엉뚱한 전제 한 줄"},
  "tsukkomi": {"name": "이름", "style": "이 사람이 태클 거는 방식 한 줄"},
  "premise": "만담이 시작되는 상황 한 줄",
  "beats": ["전개 1", "전개 2", "전개 3"],
  "punchline": "마지막에 터뜨릴 오치 한 줄"
}

이름 규칙:
- 한국 사람 이름처럼 짓는다. 두세 글자.
- 실존 인물, 연예인, 브랜드, AI 제품 이름을 쓰지 않는다.
- 두 이름이 서로 헷갈리지 않게 첫 글자를 다르게 한다.
- 주제와 배역에 어울리게 짓는다. 매번 다른 이름을 짓는다.

내용 규칙:
- 모든 값은 40자 이내 한 줄이다. 괄호로 부연하지 마라.
- quirk와 style은 3인칭으로 쓴다. "나는" 이 아니라 "이 사람은" 이다.
- beats는 같은 전제가 점점 커지는 순서다. 새 화제를 나열하지 마라.
- punchline은 앞의 전개가 있어야 웃긴 것이어야 한다."""

FALLBACK_PLAN: dict[str, Any] = {
    "boke": {"name": "만식", "quirk": "엉뚱한 전제를 진지하게 밀어붙인다"},
    "tsukkomi": {"name": "담이", "style": "짧고 빠르게 급소만 찌른다"},
    "premise": "",
    "beats": [],
    "punchline": "",
}

SCRIPT_SYSTEM = f"""너는 한국어 만담(漫才) 대본을 쓴다. 기획을 받아 공연 전체를 완성한다.

JSON 하나만 출력한다.

{{
  "lines": [
    {{"who": "boke", "action": null, "text": "대사"}},
    {{"who": "tsukkomi", "action": "때리기", "text": "대사"}}
  ]
}}

형식 규칙:
- who는 "boke" 또는 "tsukkomi" 둘 중 하나다. 반드시 번갈아 나온다. boke가 먼저다.
- 대사는 정확히 {MAX_LINES}줄이다.
- text에 이름표를 넣지 않는다. `담이: 뭔 소리야` 가 아니라 `뭔 소리야` 다.
- text에 지문, 해설, 따옴표, 마크다운을 넣지 않는다. 입 밖으로 나오는 말만 쓴다.
- 한국어로만 쓴다. 영어 단어를 섞지 않는다.

대사 규칙:
- 한 문장, 40자 이내. 구어체 반말. 길어지면 만담이 아니라 연설이 된다.
- 앞 대사를 그대로 되풀이하지 마라. 같은 말을 두 사람이 하면 만담이 죽는다.
  받되, 거기에 없던 걸 하나 얹거나 뒤집어라.
- 보케는 엉뚱한 전제를 진지하게 밀어붙이고, 츳코미는 틀린 지점을 잡아 친다.
  츳코미가 맞장구를 치면 만담이 아니다.
- 기획의 전개 순서를 따라 판을 키우고, 마지막 줄은 기획의 오치로 확실히 끊는다.
{PROMPT_RULE}"""

JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)
NAME = re.compile(r"^[가-힣]{2,3}$")


class State(TypedDict):
    topic: str
    plan: dict[str, Any]
    # (배역, 이름, 액션 이름 또는 None, 대사)
    lines: Annotated[list[tuple[str, str, str | None, str]], operator.add]


def parse_plan(reply: str) -> dict[str, Any]:
    """응답에서 JSON을 꺼낸다. 코드 펜스나 머리말이 붙어 와도 건진다."""
    match = JSON_BLOCK.search(reply)
    if not match:
        raise ValueError("기획 응답에 JSON이 없다")
    return json.loads(match.group())


def cast_of(plan: dict[str, Any], role: str) -> dict[str, Any]:
    person = plan.get(role) or {}
    fallback = FALLBACK_PLAN[role]
    if not isinstance(person, dict):
        return fallback
    merged = {**fallback, **person}
    if not NAME.match(str(merged.get("name", ""))):
        # 한 글자 이름이나 영어 이름이 나온다. 화면에 이름이 그대로 나가므로
        # 프롬프트만 믿지 않는다.
        merged["name"] = fallback["name"]
    return merged


def name_of(plan: dict[str, Any], role: str) -> str:
    return str(cast_of(plan, role)["name"])


def persona(plan: dict[str, Any], role: str) -> str:
    person = cast_of(plan, role)
    if role == "boke":
        return f"""너는 보케다. 이름은 "{person["name"]}".
{person["quirk"]}
자기가 이상하다는 자각이 없다. 츳코미가 지적하면 굽히지 않고 한 발 더 나간다."""
    return f"""너는 츳코미다. 이름은 "{person["name"]}".
{person["style"]}
상대 말에 동조하지 마라. 맞장구는 만담이 아니다. 틀린 지점 하나를 잡아서 친다.
길게 설명하면 죽는다. 급소 하나만 찌른다."""


def briefing(plan: dict[str, Any]) -> str:
    beats = "\n".join(f"  {i + 1}. {b}" for i, b in enumerate(plan.get("beats") or []))
    parts = [f"상황: {plan.get('premise', '')}"]
    if beats:
        parts.append(f"전개 순서:\n{beats}")
    if plan.get("punchline"):
        parts.append(f"마지막에 터뜨릴 오치: {plan['punchline']}")
    return "\n".join(parts)


def brief_for(state: State) -> list[dict[str, str]]:
    plan = state["plan"]
    body = (
        f"주제: {state['topic']}\n\n"
        f"[기획]\n{briefing(plan)}\n\n"
        f"[출연]\n{persona(plan, 'boke')}\n\n{persona(plan, 'tsukkomi')}\n\n"
        f"이 기획대로 만담 {MAX_LINES}줄을 완성해라."
    )
    return [{"role": "user", "content": body}]


def clean_script(raw: Any, plan: dict[str, Any]) -> list[tuple[str, str, str | None, str]]:
    """모델이 준 대본을 화면에 올릴 수 있는 형태로 거른다.

    빈 대사, 모르는 배역, 대사 없이 태그만 있는 줄은 버린다. 남은 줄만 무대에
    올린다. 한 줄이 이상하다고 공연 전체를 접지는 않는다.
    """
    lines = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        role = item.get("who")
        action, text = split_action(str(item.get("text") or ""))
        if role not in ("boke", "tsukkomi") or not text:
            continue
        # action 자리에 리스트나 숫자가 오기도 한다. 문자열이 아니면 없는 셈 친다.
        named = item.get("action")
        named = named if isinstance(named, str) and named in EMOJI else None
        lines.append((role, name_of(plan, role), action or named, text))
    return lines[:MAX_LINES]


async def make_plan(state: State) -> dict:
    try:
        brief = [{"role": "user", "content": f"주제: {state['topic']}"}]
        reply = await complete(PLAN_SYSTEM, brief, json_mode=True)
        return {"plan": parse_plan(reply)}
    except Exception:
        # 기획이 없어도 만담은 시작되어야 한다. 무대를 비우는 것보다 낫다.
        log.exception("기획 실패, 기본값으로 진행")
        return {"plan": FALLBACK_PLAN}


async def write(state: State) -> dict:
    """대본 전체를 한 번에 받는다.

    한 줄씩 이어 부르면 모델이 앞 대사를 복창하고 오치가 맺히지 않는다. 전체를
    보고 쓰게 하면 판이 커지고 끝이 닫힌다. 호출도 12번에서 1번으로 준다.
    """
    plan = state["plan"]
    for attempt in range(1, SCRIPT_ATTEMPTS + 1):
        reply = await complete(
            SCRIPT_SYSTEM, brief_for(state), temperature=0.9, json_mode=True, effort="medium"
        )
        lines = clean_script(parse_plan(reply).get("lines"), plan)
        if len(lines) >= MIN_LINES:
            return {"lines": lines}
        log.warning("대본이 %s줄뿐이다(%s/%s), 다시 쓴다", len(lines), attempt, SCRIPT_ATTEMPTS)
    raise RuntimeError("쓸 만한 대본을 받지 못했다")


def build():
    graph = StateGraph(State)
    graph.add_node("plan", make_plan)
    graph.add_node("write", write)
    graph.set_entry_point("plan")
    graph.add_edge("plan", "write")
    graph.add_edge("write", END)
    return graph.compile()


GRAPH = build()


async def perform(topic: str) -> AsyncIterator[tuple[str, str, str | None, str]]:
    """완성된 대본을 한 줄씩 내보낸다. 기획 결과는 내보내지 않는다."""
    async for chunk in GRAPH.astream({"topic": topic, "plan": FALLBACK_PLAN, "lines": []}):
        for update in chunk.values():
            for line in update.get("lines") or []:
                yield line


def random_topic() -> str:
    return random.choice(TOPICS)
