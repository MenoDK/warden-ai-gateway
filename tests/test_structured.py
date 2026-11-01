import pytest

from ai_core.gateway.structured import StructuredOutputError, parse_json_lenient


def test_plain_json() -> None:
    parsed = parse_json_lenient('{"a": 1}')
    assert parsed.value == {"a": 1} and not parsed.repaired


def test_markdown_fence() -> None:
    parsed = parse_json_lenient('Here you go:\n```json\n{"a": [1, 2]}\n```\nHope it helps')
    assert parsed.value == {"a": [1, 2]} and not parsed.repaired


def test_prose_around_the_object() -> None:
    parsed = parse_json_lenient('Sure! {"ok": true} Let me know.')
    assert parsed.value == {"ok": True} and not parsed.repaired


@pytest.mark.parametrize(
    ("truncated", "expected"),
    [
        ('{"a": 1, "b": [1, 2', {"a": 1, "b": [1, 2]}),
        ('{"a": "hello wor', {"a": "hello wor"}),
        ('{"a": 1, "b":', {"a": 1}),
        ('{"a": 1, "b"', {"a": 1}),
        ('{"a": 1, "b', {"a": 1}),
        ('{"a": 1,', {"a": 1}),
        ('{"a": {"b": {"c": "x"', {"a": {"b": {"c": "x"}}}),
        ('```json\n{"items": ["a", "b"', {"items": ["a", "b"]}),
        ('{"list": ["one", "tw', {"list": ["one", "tw"]}),
        ('{"a": "line\\', {"a": "line"}),
    ],
)
def test_repairs_truncated_output(truncated: str, expected: dict[str, object]) -> None:
    parsed = parse_json_lenient(truncated)
    assert parsed.value == expected
    assert parsed.repaired, "a salvaged result must be flagged"


def test_top_level_array() -> None:
    assert parse_json_lenient("[1, 2, 3]").value == [1, 2, 3]


@pytest.mark.parametrize("garbage", ["", "   ", "no json at all", "plain: text, here"])
def test_unrecoverable_text_raises(garbage: str) -> None:
    with pytest.raises(StructuredOutputError):
        parse_json_lenient(garbage)


def test_scalars_are_not_accepted() -> None:
    with pytest.raises(StructuredOutputError):
        parse_json_lenient("42")
