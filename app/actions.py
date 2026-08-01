"""대사 앞에 붙은 액션 태그를 떼어낸다.

LLM은 `[액션:츳코미] 아니 그게 말이 되냐고!` 형태로 뱉는다. 태그는 이모티콘
으로 바뀌고, 대사에는 남지 않는다.
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

PROMPT_RULE = """- 리액션이 큰 대사에는 맨 앞에 액션 태그를 붙인다. 형식은 `[액션:이름]` 하나뿐이다.
- 쓸 수 있는 이름: {names}. 목록에 없는 이름은 쓰지 않는다.
- 매번 붙이지 마라. 진짜 세게 치는 대사에만 붙인다.""".format(names=", ".join(EMOJI))


def split_action(line: str) -> tuple[str | None, str]:
    """(액션 이름, 태그를 뗀 대사)를 돌려준다.

    태그가 없거나, 형식이 깨졌거나, 모르는 이름이면 액션 없음으로 본다. 대사는
    어떤 경우에도 버리지 않는다.
    """
    match = TAG.match(line)
    if not match:
        return None, line.strip()
    rest = line[match.end() :].strip()
    if not rest:
        # 괄호 덩어리가 대사 전부였다. 떼면 빈 말풍선이 남으니 그냥 대사로 둔다.
        return None, line.strip()
    name = match.group(1).rsplit(":", 1)[-1].strip()
    return (name if name in EMOJI else None), rest
