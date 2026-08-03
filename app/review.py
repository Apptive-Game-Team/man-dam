"""대본 채점표. 기준의 원본은 `docs/funny.md` 다.

"웃긴가"를 물으면 모델은 아무 대본이나 통과시킨다. 무엇이 웃긴 만담을 만드는지
쪼개서 항목별로 묻는다. 기준이 코드에 있어야 프롬프트를 고칠 때 나아졌는지
말할 수 있다.
"""

# 항목마다 1점·3점·5점이 어떤 대본인지 적는다.
#
# 5점 기준점만 주면 "그것만큼 좋지 않다"가 전부 최하점이 된다. 실제로 사람이
# 11점쯤으로 읽은 대본이 4점(전 항목 1점)으로 눌렸다. 그러면 뭘 고쳐 써도
# 점수가 안 움직여서 재작성이 무의미해지고, 되먹임도 "전부 고쳐라"가 된다.
CRITERIA: dict[str, dict] = {
    "premise": {
        "question": "전제가 하나인가",
        5: "하나의 전제가 첫 줄부터 마지막 줄까지 간다. 곁가지가 없다.",
        3: "전제는 유지되는데 중간에 곁가지가 한두 번 샌다.",
        1: "줄마다 새 소재를 꺼낸다. 만담이 아니라 잡담이다.",
    },
    "escalation": {
        "question": "계단이 있는가",
        5: "매 줄이 앞줄보다 확실히 한 칸 크다. 뒤로 갈수록 판이 커진다.",
        3: "커지긴 하는데 같은 높이로 머무는 구간이 있다.",
        1: "처음부터 끝까지 같은 크기다. 세 줄째부터 지루하다.",
    },
    "punchline": {
        "question": "마지막 줄이 오치인가",
        5: "마지막 줄이 전제를 뒤집거나 끝까지 밀어 터뜨린다. 확실히 끊긴다.",
        3: "끝맺으려는 시도는 있는데 앞의 전개를 안 봐도 똑같이 읽힌다.",
        1: "그냥 멈춘다. 한 줄 더 있어도 이상하지 않다.",
    },
    "variety": {
        "question": "츳코미가 매번 다르게 치는가",
        5: "되묻기, 정정, 반문, 급소 찌르기가 고루 섞인다.",
        3: "두어 번 같은 문형이 겹치지만 나머지는 다르다.",
        1: "같은 문형이 세 번 이상 반복된다.",
    },
}

PASS_SCORE = 3  # 5점 만점. 한 항목이라도 이 밑이면 다시 쓴다.

SYSTEM = """너는 한국어 만담 대본을 심사한다. 작가가 아니라 심사위원이다.

각 항목을 1~5점으로 매기고, 점수의 근거를 대본에서 인용해 한 줄로 적는다.

점수는 아래 기준에 맞춘다. 완벽하지 않다고 전부 1점을 주지 마라. 1점은 그
항목이 아예 없을 때다. 2점과 4점은 기준 사이에 걸릴 때 쓴다.

[모든 항목 5점인 대본]
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
    note_keys = ", ".join(f'"{k}": "대본에서 인용한 근거"' for k in CRITERIA)
    rubric = "\n\n".join(
        f"[{key}] {item['question']}\n  5점: {item[5]}\n  3점: {item[3]}\n  1점: {item[1]}"
        for key, item in CRITERIA.items()
    )
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
        f"- {key} ({scores[key]}점): {notes.get(key) or CRITERIA[key]['question']}"
        for key in CRITERIA
        if scores[key] < PASS_SCORE
    ]
    if fix := verdict.get("fix"):
        lines.append(f"\n무엇보다: {fix}")
    return "\n".join(lines)
