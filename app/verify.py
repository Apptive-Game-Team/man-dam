"""채점표를 검증한다.

`app/review.py` 는 구조를 잰다. 전제가 하나인가, 계단이 있는가, 오치가 맺히는가.
구조가 맞으면 웃긴다는 가정 위에 서 있는데 그 가정 자체는 아무도 안 잰다.

여기서는 결과만 묻는다. 웃겼나. 그리고 대화가 이어지긴 했나.

둘을 따로 재는 이유는 서로 다른 실패라서다. 딴소리를 늘어놓는데 한 줄이 얻어걸려
웃길 수 있고, 앞뒤가 완벽하게 맞물리는데 하나도 안 웃길 수 있다. 한 숫자로 합치면
어느 쪽이 무너졌는지 못 본다.

이 판정은 그래프에 넣지 않는다. 넣으면 `app/review.py` 가 채점표를 항목으로 쪼갠
이유를 되돌리는 것이다. 대신 기록된 공연을 놓고 채점표 점수와 나란히 놓는다.
채점표 25점인데 재미 2점이면 채점표가 못 잡는 게 있는 것이고, 12점인데 8점이면
통과 기준이 너무 빡빡한 것이다. 어느 쪽이든 프롬프트를 어디로 고칠지 알려준다.
"""

import asyncio
import json

from app import archive
from app.examples import EXAMPLES
from app.llm import SOLAR, complete

TOP = 10
POINTS = (10, 7, 5, 3, 0)

# 축마다 0·3·5·7·10점이 어떤 대본인지 적는다. 최고점 기준만 주면 "그만큼 좋지
# 않다"가 전부 0점이 된다. app/review.py 에서 같은 걸 이미 밟았다.
SCALES: dict[str, dict] = {
    "funny": {
        "question": "웃겼나",
        10: "읽다가 숨이 막힌다. 마지막 줄에서 앞이 다시 읽히고 거기서 한 번 더 터진다.",
        7: "두세 번 확실히 웃는다. 뒤집히는 지점이 분명하다.",
        5: "한 군데는 걸린다. 나머지 줄은 밋밋하게 지나간다.",
        3: "구조는 갖췄는데 어느 줄에서 웃어야 할지 짚을 수 없다.",
        0: "말이 안 된다. 웃기려는 시도가 안 보이거나 무슨 소린지 모르겠다.",
        "up": [
            "다음 줄이 예상되지 않는다.",
            "보케의 헛소리가 그럴듯해서 읽는 동안 잠깐 설득된다.",
            "마지막 줄이 앞 대사의 의미를 바꾼다.",
        ],
        "down": [
            "읽기 전에 다음 줄이 보인다.",
            "츳코미가 왜 이상한지 설명한다. 설명하면 죽는다.",
            "억지로 웃기려 든다. 웃음을 노린 티가 난다.",
        ],
    },
    "coherence": {
        "question": "대화가 이어지나",
        10: "모든 줄이 바로 앞 줄을 받는다. 가운데 한 줄을 빼면 다음 줄이 무너진다.",
        7: "거의 다 이어진다. 한 군데쯤 앞을 안 받고 건너뛴다.",
        5: "절반은 주고받고 절반은 각자 하고 싶은 말을 한다.",
        3: "주제만 같다. 앞 줄을 가리고 읽어도 똑같이 읽힌다.",
        0: "딴소리다. 대답이 상대가 한 말과 상관없다.",
        "up": [
            "질문이 나오면 그 질문에 답한다.",
            "츳코미가 잡은 지점을 보케가 받아서 한 발 더 나간다.",
            "앞에 나온 물건이나 말이 뒤에서 다시 쓰인다.",
        ],
        "down": [
            "물어본 것과 다른 걸 답한다.",
            "앞 대사를 그대로 되풀이한다. 되받는 게 아니라 복창이다.",
            "줄마다 새 소재를 꺼내서 순서를 섞어도 티가 안 난다.",
        ],
    },
}

SYSTEM = """너는 한국어 만담(漫才) 대본을 판정한다. 작가가 아니라 관객이다.

두 축을 따로 매긴다. 서로 끌고 가지 마라. 딴소리인데 웃길 수 있고, 앞뒤가 맞는데
하나도 안 웃길 수 있다.

<Rubric>
{rubric}
</Rubric>

<Instructions>
1. 대본을 끝까지 읽는다.
2. 축마다 0~10점을 매긴다. 결과만 본다. 전제가 하나인지, 계단이 있는지는 묻지 않는다.
   그건 다른 데서 잰다.
3. 축마다 근거를 대본에서 인용해 한 줄로 적는다.
4. 중간 점수를 아끼지 마라. 기준 사이에 걸리면 그 사이 숫자를 쓴다.
</Instructions>

[두 축 모두 10점인 대본]
{anchor}

JSON 하나만 출력한다.

{{
  "scores": {{{keys}}},
  "notes": {{{note_keys}}}
}}"""


def system_prompt() -> str:
    rubric = "\n\n".join(
        f"[{key}] {scale['question']}\n"
        + "\n".join(f"  {point:>2}점: {scale[point]}" for point in POINTS)
        + "\n  올리는 것: "
        + " / ".join(scale["up"])
        + "\n  내리는 것: "
        + " / ".join(scale["down"])
        for key, scale in SCALES.items()
    )
    return SYSTEM.format(
        rubric=rubric,
        anchor=EXAMPLES[0]["script"],
        keys=", ".join(f'"{key}": 0' for key in SCALES),
        note_keys=", ".join(f'"{key}": "대본에서 인용한 근거"' for key in SCALES),
    )


def verdict_of(reply: str) -> dict:
    """판정을 꺼낸다.

    형식이 깨지거나 숫자가 아니면 0점으로 본다. 봐주면 검증이 아니라 응원이 된다.
    """
    try:
        raw = json.loads(reply)
    except (json.JSONDecodeError, TypeError):
        raw = {}
    raw = raw if isinstance(raw, dict) else {}
    scores = raw.get("scores") if isinstance(raw.get("scores"), dict) else {}
    notes = raw.get("notes") if isinstance(raw.get("notes"), dict) else {}
    out: dict[str, dict] = {"scores": {}, "notes": {}}
    for key in SCALES:
        value = scores.get(key)
        ok = isinstance(value, int | float) and not isinstance(value, bool)
        out["scores"][key] = max(0, min(TOP, int(value))) if ok else 0
        out["notes"][key] = str(notes.get(key) or "")
    return out


async def judge(script: str) -> dict:
    """대본 하나를 판정한다. 대본은 `보케:` / `츳코미:` 가 붙은 평문이다."""
    reply = await complete(
        SOLAR,
        system_prompt(),
        [{"role": "user", "content": script}],
        temperature=0.2,
        json_mode=True,
    )
    return verdict_of(reply)


def as_text(script: list[dict]) -> str:
    return "\n".join(
        f"{'보케' if line['who'] == 'boke' else '츳코미'}: {line['text']}" for line in script
    )


async def audit(limit: int = 20) -> None:
    """기록된 공연을 채점표 점수와 나란히 찍는다."""
    rows = archive.best(limit)
    if not rows:
        print("기록된 공연이 없다. 만담을 몇 번 돌리고 다시 와라.")
        return
    print("채점표  재미  대화  주제")
    for row in rows:
        got = await judge(as_text(row["script"]))
        scores = got["scores"]
        print(
            f"{row['score']:>5}  {scores['funny']:>4}  {scores['coherence']:>4}"
            f"  {row['topic']:<12} {got['notes']['funny']}"
        )


if __name__ == "__main__":
    asyncio.run(audit())
