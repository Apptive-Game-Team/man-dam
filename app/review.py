"""대본 채점표.

"웃긴가"를 물으면 모델은 아무 대본이나 통과시킨다. 무엇이 웃긴 만담을 만드는지
쪼개서 항목별로 묻는다. 기준이 코드에 있어야 프롬프트를 고칠 때 나아졌는지
말할 수 있다.
"""

CRITERIA: dict[str, str] = {
    "premise": (
        "전제가 하나인가. 하나의 전제가 대본 끝까지 유지되어야 한다. "
        "줄마다 새 소재를 꺼내면 만담이 아니라 잡담이다."
    ),
    "escalation": (
        "계단이 있는가. 매 줄이 앞줄보다 한 칸 커야 한다. "
        "같은 크기로 반복하면 세 줄째부터 지루하다."
    ),
    "punchline": ("마지막 줄이 전제를 뒤집거나 끝까지 밀어 터뜨리는가. 그냥 멈추면 오치가 아니다."),
    "variety": (
        "츳코미가 매번 다른 방식으로 치는가. 같은 문형이 세 번 이상 나오면 안 된다. "
        "되묻기, 정정, 반문, 급소 찌르기를 섞어야 한다."
    ),
}

PASS_SCORE = 3  # 5점 만점. 한 항목이라도 이 밑이면 다시 쓴다.

SYSTEM = """너는 한국어 만담 대본을 심사한다. 작가가 아니라 심사위원이다.

각 항목을 1~5점으로 매기고, 점수의 근거를 대본에서 인용해 한 줄로 적는다.
근거를 못 대면 낮은 점수다. 다만 기준점을 지켜라. 아래 대본이 모든 항목 5점이다.
이보다 나은 대본은 드물다. 이 정도면 5점, 절반쯤 되면 3점이다.

[5점짜리 대본]
{anchor}

JSON 하나만 출력한다.

{{
  "scores": {{{keys}}},
  "notes": {{{note_keys}}},
  "worst": "가장 문제인 항목 이름 하나",
  "fix": "그 항목을 고치려면 무엇을 바꿔야 하는지 한 줄"
}}

채점 항목:
{rubric}"""


def system_prompt() -> str:
    """채점 기준점을 예시 대본으로 준다.

    기준점 없이 물으면 모든 항목에 1~2점만 주고, 뭘 고쳐 써도 통과가 안 된다.
    그러면 재작성 횟수만 소진하고 관객은 그만큼 더 기다린다.
    """
    from app.examples import EXAMPLES

    keys = ", ".join(f'"{k}": 1' for k in CRITERIA)
    note_keys = ", ".join(f'"{k}": "근거"' for k in CRITERIA)
    rubric = "\n".join(f"- {k}: {desc}" for k, desc in CRITERIA.items())
    return SYSTEM.format(
        keys=keys, note_keys=note_keys, rubric=rubric, anchor=EXAMPLES[0]["script"]
    )


def scores_of(verdict: dict) -> dict[str, int]:
    """점수만 꺼낸다. 빠졌거나 숫자가 아니면 0점으로 본다."""
    raw = verdict.get("scores")
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for key in CRITERIA:
        value = raw.get(key)
        out[key] = int(value) if isinstance(value, int | float) else 0
    return out


def total(verdict: dict) -> int:
    return sum(scores_of(verdict).values())


def passed(verdict: dict) -> bool:
    return all(score >= PASS_SCORE for score in scores_of(verdict).values())


def feedback(verdict: dict) -> str:
    """다시 쓸 때 붙일 지적. 낮은 항목만 짚는다."""
    scores = scores_of(verdict)
    notes = verdict.get("notes") if isinstance(verdict.get("notes"), dict) else {}
    lines = [
        f"- {key} ({scores[key]}점): {notes.get(key, CRITERIA[key])}"
        for key in CRITERIA
        if scores[key] < PASS_SCORE
    ]
    if fix := verdict.get("fix"):
        lines.append(f"\n무엇보다: {fix}")
    return "\n".join(lines)
