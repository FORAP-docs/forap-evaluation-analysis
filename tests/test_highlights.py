import colorsys
from html.parser import HTMLParser

import pytest

from forap_analysis.highlights import (
    code_display_colors,
    exact_occurrences,
    excerpt_digest,
    highlight_review_states,
    normalize_passages,
    render_highlighted_excerpt,
    safe_code_color,
)


def row(text, code_id=1, start=0, end=None, **overrides):
    return {
        "code_id": code_id, "code_name": f"Code {code_id}", "color": "#007d79",
        "start_offset": start, "end_offset": len(text) if end is None else end,
        "excerpt": text, "excerpt_sha256": excerpt_digest(text),
        "status": "reviewed", "review_note": "", **overrides,
    }


class PassageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_text = False
        self.in_reference = False
        self.parts = []
        self.mark_attributes = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "div" and values.get("class") == "passage-text":
            self.in_text = True
        if tag == "sup":
            self.in_reference = True
        if tag == "mark":
            self.mark_attributes.append(values)

    def handle_endtag(self, tag):
        if tag == "sup":
            self.in_reference = False
        if tag == "div":
            self.in_text = False

    def handle_data(self, data):
        if self.in_text and not self.in_reference:
            self.parts.append(data)


def test_renderer_escapes_quotes_code_names_notes_and_css():
    text = '<script>alert("x")</script> & words'
    item = row(text, code_name='<img src=x onerror="bad()">', color='red; background:url(evil)', review_note='" onclick="bad()')
    output = render_highlighted_excerpt(text, [item])
    assert "<script>" not in output and "<img " not in output
    assert "&lt;script&gt;" in output and "&lt;img" in output
    assert ' onclick="bad()' not in output and "url(evil)" not in output
    assert "#0f62fe" in output
    parser = PassageText()
    parser.feed(output)
    assert "".join(parser.parts) == text


def test_unicode_overlap_preserves_text_and_labels_both_codes():
    text = "A🙂 café\nend"
    spans = [row(text, 1, 1, 7), row(text, 2, 3, len(text), color="#9f1853")]
    output = render_highlighted_excerpt(text, spans)
    parser = PassageText()
    parser.feed(output)
    assert "".join(parser.parts) == text
    overlap = [attrs for attrs in parser.mark_attributes if attrs["data-code-ids"] == "1,2"]
    assert overlap
    assert all("Code 1; Code 2" in attrs["title"] for attrs in overlap)
    assert "passage-code-ref" not in output
    assert "<sup" not in output
    assert "passage-legend" not in output
    assert "#9f1853" in overlap[0]["style"]
    assert "#007d79" in overlap[0]["style"]
    assert overlap[0]["tabindex"] == "0"


def test_all_codes_are_shown_once_without_extra_controls_or_labels():
    text = "first and second"
    output = render_highlighted_excerpt(text, [row(text, 1, 0, 5), row(text, 2, 10, 16)])
    assert 'data-code-ids="2"' in output and 'data-code-ids="1"' in output
    assert "passage-legend" not in output and "passage-code-ref" not in output
    assert "<select" not in output and "<sup" not in output
    parser = PassageText()
    parser.feed(output)
    assert "".join(parser.parts) == text


@pytest.mark.parametrize("start,end", [(-1, 2), (0, 99), (2, 2), (3, 1), (True, 2), (0.5, 2), (None, 2)])
def test_invalid_ranges_are_not_drawn(start, end):
    spans = [row("hello", start=start, end=end)]
    output = render_highlighted_excerpt("hello", spans)
    assert "<mark " not in output
    states = highlight_review_states("hello", spans)
    assert states[1]["state"] == "Invalid passage - review needed"
    assert states[1]["needs_attention"]
    assert states[1]["status"] == "needs_review"


def test_stale_ranges_are_not_guessed_or_drawn():
    old = row("old text")
    output = render_highlighted_excerpt("new text", [old])
    assert "<mark " not in output
    assert "Text changed" in highlight_review_states("new text", [old])[1]["state"]
    assert "new text" in output


def test_unreviewed_assignment_remains_visible_without_automatic_highlight():
    review = row("hello", status="unreviewed", excerpt_sha256="")
    output = render_highlighted_excerpt("hello", [], [review])
    states = highlight_review_states("hello", [], [review])
    assert states[1]["state"] == "Not reviewed yet"
    assert states[1]["name"] == "Code 1"
    assert states[1]["needs_attention"]
    assert "<mark " not in output
    assert "Code 1" not in output


def test_empty_results_are_safe_and_plain_quotes_have_no_extra_labels():
    assert 'class="passage-text"></div>' in render_highlighted_excerpt("", [])
    output = render_highlighted_excerpt("hello", [])
    assert "hello" in output and "<mark " not in output
    assert "Code" not in output
    assert highlight_review_states("hello", []) == {}


def test_current_code_color_is_used_without_rewriting_ranges():
    span = row("hello", color="#198038")
    assert "#198038" in render_highlighted_excerpt("hello", [span])
    span["color"] = "#da1e28"
    assert "#da1e28" in render_highlighted_excerpt("hello", [span])
    assert safe_code_color('"') == "#0f62fe"


def test_same_group_shades_are_distinct_and_keep_the_base_hue():
    codes = [{"id": code_id, "color": "#6929c4"} for code_id in range(1, 13)]
    colors = code_display_colors(codes)
    assert len(set(colors.values())) == len(codes)
    assert colors[1] == "#6929c4"
    base_hue = colorsys.rgb_to_hls(0x69 / 255, 0x29 / 255, 0xc4 / 255)[0]
    for color in colors.values():
        rgb = tuple(int(color[index:index + 2], 16) / 255 for index in (1, 3, 5))
        hue = colorsys.rgb_to_hls(*rgb)[0]
        assert abs(hue - base_hue) < 0.005
    first_lightness = colorsys.rgb_to_hls(*(int(colors[1][index:index + 2], 16) / 255 for index in (1, 3, 5)))[1]
    second_lightness = colorsys.rgb_to_hls(*(int(colors[2][index:index + 2], 16) / 255 for index in (1, 3, 5)))[1]
    assert abs(first_lightness - second_lightness) > 0.20


def test_display_colors_ignore_codebook_order_names_and_colour_case():
    codes = [
        {"code_id": 9, "code_name": "Old name", "color": "#6929C4"},
        {"code_id": 2, "color": "#6929c4"},
        {"code_id": 5, "color": "#198038"},
    ]
    expected = code_display_colors(codes)
    codes[0]["code_name"] = "New name"
    assert code_display_colors(reversed(codes)) == expected
    assert expected[2] != expected[9]
    assert expected[5] == "#198038"


def test_display_colors_handle_bad_values_and_grayscale():
    colors = code_display_colors([
        {"id": 1, "color": 'red; background:url(evil)'},
        {"id": 2, "color": "#0f62fe"},
        {"id": 3, "color": "#000000"},
        {"id": 4, "color": "#000000"},
        {"id": True, "color": "#ffffff"},
        {"id": "not an id", "color": "#ffffff"},
    ])
    assert set(colors) == {1, 2, 3, 4}
    assert colors[1] == "#0f62fe"
    assert colors[1] != colors[2]
    assert colors[3] != colors[4]
    assert colors[4][1:3] == colors[4][3:5] == colors[4][5:7]


def test_same_group_overlaps_have_both_shades_and_stay_consistent_across_excerpts():
    text = "first and second"
    spans = [row(text, 1, 0, 9), row(text, 2, 6, 16)]
    colors = code_display_colors([{"id": 1, "color": "#007d79"}, {"id": 2, "color": "#007d79"}])
    output = render_highlighted_excerpt(text, spans, display_colors=colors)
    parser = PassageText()
    parser.feed(output)
    overlap = next(attrs for attrs in parser.mark_attributes if attrs["data-code-ids"] == "1,2")
    assert colors[1] in overlap["style"] and colors[2] in overlap["style"]
    assert "0 calc(100% - 0px),0 calc(100% - 3px)" in overlap["style"]
    assert "".join(parser.parts) == text
    isolated_excerpt = render_highlighted_excerpt(text, spans[1:], display_colors=colors)
    assert colors[2] in isolated_excerpt
    assert colors[1] not in isolated_excerpt


def test_display_color_overrides_are_sanitized():
    output = render_highlighted_excerpt("hello", [row("hello")], display_colors={1: "red;background:url(evil)"})
    assert "url(evil)" not in output
    assert "#0f62fe" in output


def test_review_details_are_exposed_for_existing_tags_and_flagged_hover():
    span = row("hello", status="needs_review", review_note="Only partly supported.")
    states = highlight_review_states("hello", [span])
    assert states[1] == {
        "name": "Code 1", "state": "Needs review", "note": "Only partly supported.",
        "status": "needs_review", "tooltip": "Code 1: Needs review. Only partly supported.",
        "needs_attention": True,
    }
    output = render_highlighted_excerpt("hello", [span])
    assert "Needs review. Only partly supported." in output
    assert "passage-legend" not in output
    reviewed = highlight_review_states("hello", [row("hello")])[1]
    assert reviewed["state"] == "Reviewed"
    assert not reviewed["needs_attention"]


def test_review_with_no_span_is_flagged_without_inventing_a_highlight():
    review = row("hello", status="reviewed")
    state = highlight_review_states("hello", [], [review])[1]
    assert state["state"] == "No passage saved - review needed"
    assert state["status"] == "needs_review"
    assert state["needs_attention"]
    assert "<mark " not in render_highlighted_excerpt("hello", [], [review])


def test_stale_review_blocks_even_individually_valid_spans():
    span = row("hello")
    review = row("hello", excerpt_sha256=excerpt_digest("old text"))
    output = render_highlighted_excerpt("hello", [span], [review])
    assert "<mark " not in output
    assert "Text changed" in highlight_review_states("hello", [span], [review])[1]["state"]


def test_exact_phrase_lookup_handles_unicode_repetition_and_spaces():
    assert exact_occurrences("🙂 café; café", "café") == [(2, 6), (8, 12)]
    assert exact_occurrences("banana", "ana") == [(1, 4), (3, 6)]
    assert exact_occurrences(" café ", " café ") == [(0, 6)]
    assert exact_occurrences("hello", "Hello") == []
    assert exact_occurrences("hello", "") == []
    assert exact_occurrences("hello ", " ") == []


def test_same_code_passages_merge_only_when_touching_or_overlapping():
    assert normalize_passages("abcdefghij", [(3, 5), (0, 3), (0, 3), (7, 9)]) == [(0, 5), (7, 9)]
    with pytest.raises(ValueError):
        normalize_passages("abc", [(0, 4)])
    with pytest.raises(ValueError):
        normalize_passages("a b", [(1, 2)])
