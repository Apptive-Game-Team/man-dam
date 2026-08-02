"""만담 그래프.

기획 -> 집필 -> 심사, 떨어지면 다시 쓴다. 심사가 통과시키거나 재작성 횟수를
다 쓰면 그중 제일 점수 높은 대본이 무대에 오른다.

기획과 심사는 Solar가, 집필은 DeepSeek이 맡는다. 이유는 app/llm.py에 적었다.
"""

import json
import logging
import operator
import random
import re
from collections.abc import AsyncIterator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph

from app import archive, review
from app.actions import EMOJI, PROMPT_RULE, split_action
from app.examples import as_prompt
from app.llm import DEEPSEEK, SOLAR, complete

log = logging.getLogger(__name__)

# 대사 수 상한. 없으면 그래프가 영원히 돈다.
MAX_LINES = 12
# 이만큼도 못 건지면 무대에 올릴 게 없다.
MIN_LINES = 8
SCRIPT_ATTEMPTS = 2
# 채점에서 떨어지면 다시 쓴다. 무한정 고쳐 쓰면 관객이 기다린다.
MAX_REWRITES = 2

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
- quirk는 전제 하나다. 여러 개를 나열하지 마라. 이 전제가 대본 끝까지 간다.
- **전제에 마법을 넣지 마라.** 벌어지는 일은 현실에서 일어날 수 있어야 하고,
  틀린 것은 보케의 해석과 논리뿐이다. 괴물, 말하는 사물, 초능력은 쓰지 않는다.
- beats는 그 전제 하나가 점점 커지는 계단이다. 새 소재를 나열하면 잡담이 된다.
- punchline은 그 전제를 뒤집는다. 앞의 전개를 안 보고도 웃기면 잘못 쓴 것이다.
- punchline에 쓸 구체적인 말이나 물건이 beats 안에 이미 나와 있어야 한다.

예: 전제가 "회원권이 대신 운동한다"면
beats는 [회원권이 탄탄해진다, 무거워서 못 꺼낸다, 오늘은 쉬라고 말한다]이고
punchline은 "운동한 건 회원권이 아니라 자랑한 입이다"이다."""

FALLBACK_PLAN: dict[str, Any] = {
    "boke": {"name": "만식", "quirk": "엉뚱한 전제를 진지하게 밀어붙인다"},
    "tsukkomi": {"name": "담이", "style": "짧고 빠르게 급소만 찌른다"},
    "premise": "",
    "beats": [],
    "punchline": "",
}

SCRIPT_TEMPLATE = f"""너는 한국어 만담(漫才) 대본을 쓴다. 기획을 받아 공연 전체를 완성한다.

JSON 하나만 출력한다.

{{
  "lines": [
    {{"who": "boke", "action": null, "text": "대사"}},
    {{"who": "tsukkomi", "action": "액션 이름 또는 null", "text": "대사"}}
  ]
}}

형식 규칙:
- who는 "boke" 또는 "tsukkomi" 둘 중 하나다. 반드시 번갈아 나온다. boke가 먼저다.
- 대사는 정확히 {MAX_LINES}줄이다.
- text에 이름표를 넣지 않는다. `담이: 뭔 소리야` 가 아니라 `뭔 소리야` 다.
- text에 지문, 해설, 따옴표, 마크다운을 넣지 않는다. 입 밖으로 나오는 말만 쓴다.
- 한국어로만 쓴다. 영어 단어를 섞지 않는다.
- action에는 아래 목록의 이름을 그대로 쓰거나 null을 쓴다. 상황에 맞는 것을 고른다.
  한 대본에서 같은 액션을 세 번 이상 쓰지 않는다.

대사 규칙:
- 한 문장, 40자 이내. 구어체 반말. 길어지면 만담이 아니라 연설이 된다.
- 앞 대사를 그대로 되풀이하지 마라. 같은 말을 두 사람이 하면 만담이 죽는다.
- 보케는 엉뚱한 전제를 진지하게 밀어붙이고, 츳코미는 틀린 지점을 잡아 친다.
  츳코미가 맞장구를 치면 만담이 아니다.
- 츳코미가 매번 같은 문형으로 치면 안 된다. 되묻기, 정정, 반문, 급소 찌르기를 섞는다.

이 넷이 전부다:

1. **보케는 마법을 쓰지 않는다.** 이게 제일 중요하다.
   보케가 틀린 건 세상이 아니라 생각이다. 벌어지는 일은 전부 현실에서 일어날 수 있어야 하고,
   말이 안 되는 건 보케의 해석과 논리뿐이다.
   나쁜 예: 회원권을 샀더니 괴물이 튀어나왔다 / 화분이 말을 걸었다 / 냉동고가 던전이었다.
   좋은 예: 삼 년 탄 자전거를 새 거라고 우긴다. "탄 건 나지 자전거가 아니야."
   괴물이 나오면 츳코미는 "그게 말이 되냐" 말고 할 말이 없다. 궤변이어야 반박할 거리가 생긴다.

2. 전제는 하나다. 줄마다 새 소재를 꺼내면 만담이 아니라 잡담이다.

3. 매 줄이 앞줄보다 한 칸 크다. 츳코미가 반박하면 보케가 물러서지 않고 한 발 더 나간다.

4. **마지막 줄은 앞에 나온 것으로 뒤집는다.**
   오치에 쓸 구체적인 말이나 물건을 전반부에 반드시 심어둬라. 마지막 줄은 그걸 되받는다.
   앞을 안 읽어도 이해되는 마지막 줄은 오치가 아니다.
{PROMPT_RULE}

아래는 잘된 만담이다. **밀도와 리듬만** 따라라.
전제, 소재, 오치는 절대 재사용하지 마라. 예시에 나온 물건과 상황은 쓰지 마라.
따라야 할 것은 한 전제를 끝까지 밀고 계단을 올리고 마지막에 뒤집는 방식이다.

{{examples}}"""

JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)
NAME = re.compile(r"^[가-힣]{2,3}$")


Line = tuple[str, str, str | None, str]  # (배역, 이름, 액션 이름 또는 None, 대사)


class State(TypedDict):
    topic: str
    plan: dict[str, Any]
    draft: list[Line]  # 심사 중인 대본
    best: list[Line]  # 지금까지 중 제일 점수가 높았던 대본
    best_score: int
    best_verdict: dict[str, Any]  # 그 대본이 받은 채점표
    feedback: str  # 직전 심사에서 받은 지적
    rewrites: int
    lines: Annotated[list[Line], operator.add]  # 무대에 올라간 것


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
        reply = await complete(SOLAR, PLAN_SYSTEM, brief, json_mode=True)
        return {"plan": parse_plan(reply)}
    except Exception:
        # 기획이 없어도 만담은 시작되어야 한다. 무대를 비우는 것보다 낫다.
        log.exception("기획 실패, 기본값으로 진행")
        return {"plan": FALLBACK_PLAN}


def script_system(topic: str) -> str:
    """이번 주제에 맞춰 예시를 골라 프롬프트를 짠다.

    format()이 아니라 replace()를 쓴다. 프롬프트 안에 JSON 중괄호가 있어서
    format()은 그걸 채울 필드로 읽는다.
    """
    return SCRIPT_TEMPLATE.replace("{examples}", as_prompt(topic))


async def write(state: State) -> dict:
    """대본 전체를 한 번에 받는다.

    한 줄씩 이어 부르면 모델이 앞 대사를 복창하고 오치가 맺히지 않는다. 전체를
    보고 쓰게 하면 판이 커지고 끝이 닫힌다.
    """
    plan = state["plan"]
    messages = brief_for(state)
    if note := state.get("feedback"):
        messages.append(
            {
                "role": "user",
                "content": (
                    f"방금 쓴 대본이 심사에서 떨어졌다. 아래를 고쳐서 처음부터 다시 써라.\n\n{note}"
                ),
            }
        )
    for attempt in range(1, SCRIPT_ATTEMPTS + 1):
        reply = await complete(
            DEEPSEEK, script_system(state["topic"]), messages, temperature=0.9, json_mode=True
        )
        lines = clean_script(parse_plan(reply).get("lines"), plan)
        if len(lines) >= MIN_LINES:
            return {"draft": lines, "rewrites": state.get("rewrites", 0) + 1}
        log.warning("대본이 %s줄뿐이다(%s/%s), 다시 쓴다", len(lines), attempt, SCRIPT_ATTEMPTS)
    raise RuntimeError("쓸 만한 대본을 받지 못했다")


def as_text(lines: list[Line]) -> str:
    return "\n".join(
        f"{'보케' if role == 'boke' else '츳코미'}: {text}" for role, _, _, text in lines
    )


async def judge(state: State) -> dict:
    """채점표로 대본을 심사한다.

    떨어뜨리는 게 목적이 아니라 무엇이 부족한지 집필에 돌려주는 게 목적이다.
    심사가 실패하면 통과시킨다. 심사 때문에 공연이 멈추면 본말전도다.
    """
    draft = state["draft"]
    best_score = state.get("best_score", -1)
    try:
        reply = await complete(
            SOLAR,
            review.system_prompt(),
            [{"role": "user", "content": as_text(draft)}],
            temperature=0.2,
            json_mode=True,
        )
        verdict = parse_plan(reply)
    except Exception:
        log.exception("심사 실패, 이 대본으로 간다")
        return {"best": draft, "best_score": 99, "best_verdict": {}, "feedback": ""}

    score = review.total(verdict)
    log.info("심사 %s점 %s", score, review.scores_of(verdict))
    keep = score > best_score
    return {
        "best": draft if keep else state.get("best", draft),
        "best_score": max(score, best_score),
        "best_verdict": verdict if keep else state.get("best_verdict", verdict),
        "feedback": "" if review.passed(verdict) else review.feedback(verdict),
    }


def curtain_up(state: State) -> dict:
    """제일 나은 대본을 무대에 올린다.

    심사를 끝내 통과하지 못해도 무대는 비우지 않는다. 여러 번 쓴 것 중 점수가
    제일 높았던 것을 올린다.
    """
    lines = state.get("best") or state["draft"]
    archive.save(
        topic=state["topic"],
        plan=state["plan"],
        lines=lines,
        verdict=state.get("best_verdict"),
        score=state.get("best_score", 0),
        rewrites=state.get("rewrites", 0),
    )
    return {"lines": lines}


def rewrite_or_go(state: State) -> str:
    if not state.get("feedback"):
        return "stage"  # 통과했다
    if state.get("rewrites", 0) >= MAX_REWRITES:
        log.info("재작성 %s회 소진, 제일 나은 대본으로 간다", MAX_REWRITES)
        return "stage"
    return "write"


def build():
    graph = StateGraph(State)
    graph.add_node("plan", make_plan)
    graph.add_node("write", write)
    graph.add_node("judge", judge)
    graph.add_node("stage", curtain_up)
    graph.set_entry_point("plan")
    graph.add_edge("plan", "write")
    graph.add_edge("write", "judge")
    graph.add_conditional_edges("judge", rewrite_or_go, {"write": "write", "stage": "stage"})
    graph.add_edge("stage", END)
    return graph.compile()


GRAPH = build()


async def perform(topic: str) -> AsyncIterator[tuple[str, str, str | None, str]]:
    """완성된 대본을 한 줄씩 내보낸다. 기획 결과는 내보내지 않는다."""
    start: State = {
        "topic": topic,
        "plan": FALLBACK_PLAN,
        "draft": [],
        "best": [],
        "best_score": -1,
        "best_verdict": {},
        "feedback": "",
        "rewrites": 0,
        "lines": [],
    }
    async for chunk in GRAPH.astream(start):
        for update in chunk.values():
            for line in update.get("lines") or []:
                yield line


def random_topic() -> str:
    return random.choice(TOPICS)
