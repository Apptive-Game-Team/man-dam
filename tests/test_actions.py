import pytest

from app.actions import EMOJI, split_action


def test_no_tag_passes_through():
    assert split_action("아니 그게 말이 되냐고!") == (None, "아니 그게 말이 되냐고!")


def test_tag_is_stripped():
    assert split_action("[액션:츳코미] 아니 그게 말이 되냐고!") == (
        "츳코미",
        "아니 그게 말이 되냐고!",
    )


@pytest.mark.parametrize(
    "line",
    [
        "[츳코미] 뭔 소리야",  # 액션: 접두어를 빼먹음
        "( 액션 : 츳코미 ) 뭔 소리야",  # 괄호와 공백이 제멋대로
        "[액션:츳코미]뭔 소리야",  # 붙여씀
    ],
)
def test_loose_tag_shapes(line):
    # LLM은 형식을 정확히 지키지 않는다. 어느 쪽이든 대사에 남으면 안 된다.
    assert split_action(line) == ("츳코미", "뭔 소리야")


def test_unknown_action_drops_to_none():
    # 모르는 액션이라도 대사는 살고, 태그는 화면에 남지 않는다.
    assert split_action("[액션:공중제비] 뭔 소리야") == (None, "뭔 소리야")


def test_tag_only_line_keeps_text():
    # 떼면 빈 말풍선이 남는다. 그럴 바엔 대사로 둔다.
    assert split_action("[액션:츳코미]") == (None, "[액션:츳코미]")


def test_every_action_has_an_asset():
    from pathlib import Path

    emoji_dir = Path(__file__).resolve().parent.parent / "static" / "emoji"
    for name in EMOJI.values():
        assert (emoji_dir / f"{name}.svg").is_file(), name


def test_name_prefix_is_stripped():
    # 모델이 이름표를 붙이지 말라고 해도 붙인다.
    assert split_action("Claude: 뭔 소리야") == (None, "뭔 소리야")


def test_only_the_first_turn_survives():
    # 한 응답에 여러 턴을 쏟아내면 말풍선 하나에 만담 전체가 들어간다.
    reply = "[액션:츳코미] 뭔 소리야\nGPT: 아니 진짜라니까\nClaude: 됐고"
    assert split_action(reply) == ("츳코미", "뭔 소리야")


def test_mid_sentence_tag_is_removed():
    assert split_action("아니 [액션:당황] 그게 말이 되냐") == (
        None,
        "아니 그게 말이 되냐",
    )
