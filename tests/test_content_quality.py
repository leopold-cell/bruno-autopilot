from __future__ import annotations

from app.llm import extract_json
from app.modules.content.generator import _word_count
from app.modules.content.quality import structural_check


def _good_post() -> dict:
    body = [
        {"type": "p", "text": "word " * 400},
        {"type": "h2", "text": "How to start"},
        {"type": "p", "text": "word " * 320},
        {"type": "ul", "items": ["a tip", "another tip"]},
        {"type": "p", "text": "If you're in crisis call 988 or see a licensed professional."},
    ]
    return {
        "title": "How to Stop Overthinking at Night",
        "slug": "how-to-stop-overthinking-at-night",
        "excerpt": "A short hook.",
        "description": "Meta description.",
        "category": "Anxiety",
        "reading_minutes": 5,
        "tldr": ["Breathe out longer than you breathe in.", "Name the distortion."],
        "body": body,
        "keyword": "how to stop overthinking at night",
    }


def test_good_post_passes_structural():
    assert structural_check(_good_post()) == []


def test_short_post_flagged():
    post = _good_post()
    post["body"] = [{"type": "p", "text": "too short"}]
    issues = structural_check(post)
    assert any("too short" in i or "body too short" in i for i in issues)


def test_banned_language_flagged():
    post = _good_post()
    post["body"].append({"type": "p", "text": "This will cure your anxiety, guaranteed."})
    issues = structural_check(post)
    assert any("overclaiming" in i for i in issues)


def test_missing_crisis_disclaimer_flagged():
    post = _good_post()
    post["body"] = [b for b in post["body"] if "988" not in str(b.get("text", ""))]
    issues = structural_check(post)
    assert any("crisis" in i for i in issues)


def test_invalid_category_flagged():
    post = _good_post()
    post["category"] = "Productivity"
    assert any("invalid category" in i for i in structural_check(post))


def test_word_count_counts_lists_and_text():
    body = [{"type": "p", "text": "one two three"}, {"type": "ul", "items": ["four five", "six"]}]
    assert _word_count(body) == 6


def test_extract_json_handles_fences():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('prefix [1, 2, 3] suffix') == [1, 2, 3]
