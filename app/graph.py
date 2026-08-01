"""만담 그래프. 보케와 츳코미가 번갈아 한 줄씩 친다."""

import operator
import random
from collections.abc import AsyncIterator
from typing import Annotated, TypedDict

from langgraph.graph import END, StateGraph

from app.llm import complete

BOKE = "ChatGPT"
TSUKKOMI = "Claude"

# 대사 수 상한. 없으면 그래프가 영원히 돈다.
MAX_LINES = 12

TOPICS = [
    "카페 창업",
    "헬스장 등록",
    "중고거래",
    "고양이 키우기",
    "제주도 여행",
    "회사 워크숍",
]

COMMON = """너는 한국어 만담(漫才) 대본을 쓴다. 보케와 츳코미 두 사람이 주고받는 2인 콩트다.

규칙:
- 대사 한 줄만 출력한다. 이름표, 따옴표, 지문, 설명을 붙이지 않는다.
- 한 문장, 40자 이내. 구어체 반말. 길어지면 만담이 아니라 연설이 된다.
- 앞사람 대사를 받아친다. 새 화제를 혼자 꺼내지 않는다.
- 실제로 웃긴 걸 노린다. 설명하지 말고 치고 빠진다."""

BOKE_SYSTEM = f"""{COMMON}

너는 보케다. 이름은 "ChatGPT".
엉뚱한 전제를 아주 진지하게 밀어붙인다. 자기가 이상하다는 자각이 없다.
츳코미가 지적하면 굽히지 않고 한 발 더 나간다."""

TSUKKOMI_SYSTEM = f"""{COMMON}

너는 츳코미다. 이름은 "Claude".
보케의 헛소리를 즉시 잡아챈다. 짧고 빠르게 친다.
길게 설명하면 죽는다. 급소 하나만 찌른다."""


class State(TypedDict):
    topic: str
    lines: Annotated[list[tuple[str, str]], operator.add]


def transcript(state: State) -> str:
    if not state["lines"]:
        return f"주제: {state['topic']}\n\n첫 대사를 쳐라."
    body = "\n".join(f"{speaker}: {text}" for speaker, text in state["lines"])
    return f"주제: {state['topic']}\n\n지금까지의 만담:\n{body}\n\n다음 대사를 쳐라."


async def boke(state: State) -> dict:
    return {"lines": [(BOKE, await complete(BOKE_SYSTEM, transcript(state)))]}


async def tsukkomi(state: State) -> dict:
    return {"lines": [(TSUKKOMI, await complete(TSUKKOMI_SYSTEM, transcript(state)))]}


def keep_going(state: State) -> str:
    return END if len(state["lines"]) >= MAX_LINES else "boke"


def build():
    graph = StateGraph(State)
    graph.add_node("boke", boke)
    graph.add_node("tsukkomi", tsukkomi)
    graph.set_entry_point("boke")
    graph.add_edge("boke", "tsukkomi")
    graph.add_conditional_edges("tsukkomi", keep_going, {"boke": "boke", END: END})
    return graph.compile()


GRAPH = build()


async def perform(topic: str) -> AsyncIterator[tuple[str, str]]:
    """대사가 생성되는 대로 하나씩 흘려보낸다."""
    async for chunk in GRAPH.astream({"topic": topic, "lines": []}):
        for update in chunk.values():
            for line in update["lines"]:
                yield line


def random_topic() -> str:
    return random.choice(TOPICS)
