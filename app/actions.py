"""모델이 뱉은 응답을 대사 한 줄로 정리한다.

`[액션:츳코미] 아니 그게 말이 되냐고!` 이 원하는 형태다. 태그는 이모티콘이
되고 대사에는 남지 않는다. 모델은 이 형태를 자주 어긴다. 이름표를 붙이고,
한 응답에 여러 턴을 쏟아내고, 태그를 문장 중간에 끼워 넣는다. 프롬프트로
줄이되, 새는 건 여기서 막는다.
"""

import re

# 액션 이름 -> static/emoji/ 파일 이름
EMOJI = {
    "츳코미": "tsukkomi",
    "넘어짐": "fall",
    "당황": "panic",
}

# 앞머리에 붙은 괄호 덩어리를 통째로 잡는다. LLM이 `[액션:츳코미]` 대신
# `[츳코미]` 나 `(액션: 츳코미)` 로 흘리는 일이 잦고, 어느 쪽이든 대사에 남으면
# 안 되는 건 같다.
TAG = re.compile(r"^\s*[\[(]([^\])]*)[\])]\s*")
# 문장 중간에 남은 괄호 덩어리. 앞머리 태그를 뗀 뒤에도 남는 것들을 쓸어낸다.
TAG_ANYWHERE = re.compile(r"[\[(][^\])]*[\])]")
# "Claude: ", "GPT: " 같은 이름표. 붙이지 말라고 해도 붙인다.
SPEAKER = re.compile(r"^\s*[\w가-힣]{1,12}\s*[::]\s*")

PROMPT_RULE = """- 리액션이 큰 대사에는 맨 앞에 액션 태그를 붙인다. 형식은 `[액션:이름]` 하나뿐이다.
- 쓸 수 있는 이름: {names}. 목록에 없는 이름은 쓰지 않는다.
- 매번 붙이지 마라. 진짜 세게 치는 대사에만 붙인다.""".format(names=", ".join(EMOJI))


def first_turn(reply: str) -> str:
    """응답에서 첫 대사 한 줄만 꺼낸다.

    모델이 한 응답에 여러 턴을 쏟아낼 때가 있다. 그대로 두면 한 말풍선에
    만담 전체가 들어가고 턴 교대가 무너진다.
    """
    for raw in reply.splitlines():
        line = SPEAKER.sub("", raw.strip())
        if line:
            return line
    return reply.strip()


def tidy(text: str) -> str:
    """남은 태그를 걷어내고 그 자리에 생긴 빈칸을 메운다."""
    return re.sub(r"\s+", " ", TAG_ANYWHERE.sub("", text)).strip()


def split_action(reply: str) -> tuple[str | None, str]:
    """(액션 이름, 정리된 대사)를 돌려준다.

    태그가 없거나, 형식이 깨졌거나, 모르는 이름이면 액션 없음으로 본다. 대사는
    어떤 경우에도 버리지 않는다.
    """
    line = first_turn(reply)
    match = TAG.match(line)
    if not match:
        return None, tidy(line) or line
    rest = tidy(line[match.end() :])
    if not rest:
        # 괄호 덩어리가 대사 전부였다. 떼면 빈 말풍선이 남으니 그냥 대사로 둔다.
        return None, line
    name = match.group(1).rsplit(":", 1)[-1].strip()
    return (name if name in EMOJI else None), rest
