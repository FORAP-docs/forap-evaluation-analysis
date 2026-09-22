import hashlib

import pytest

from forap_analysis.database import Database


@pytest.fixture
def coded(tmp_path):
    db = Database(tmp_path / "highlights.sqlite3")
    a = db.save_code("AT3 - Project requirements", "", "", "", "#b28600")
    b = db.save_code("AS8 - Assessment tools", "", "", "", "#0f62fe")
    text = "LMS resources, assessment tools, and required staffing."
    unit = db.save_meaning_unit("response-a", "assessment_comments", text, [a, b])
    return db, unit, a, b, text


def test_highlights_are_per_assignment_and_use_current_colors(coded):
    db, unit, a, b, text = coded
    assert set(db.highlight_reviews(unit)["status"]) == {"unreviewed"}
    start = text.index("required staffing")
    db.save_code_highlights(unit, a, [(start, start + len("required staffing"))], expected_excerpt=text)
    db.save_code_highlights(unit, b, [(0, len("LMS resources, assessment tools"))])
    rows = db.code_highlights(unit)
    assert len(rows) == 2
    assert set(rows["excerpt_sha256"]) == {hashlib.sha256(text.encode()).hexdigest()}
    assert all(row.excerpt[row.start_offset:row.end_offset] for row in rows.itertuples())
    db.update_code_color(a, "#123456")
    assert db.code_highlights(unit).set_index("code_id").loc[a, "color"] == "#123456"
    with db.connect() as connection:
        connection.execute("UPDATE codes SET name='AT3 - Same code renamed' WHERE id=?", (a,))
    assert db.code_highlights(unit).set_index("code_id").loc[a, "code_name"] == "AT3 - Same code renamed"


@pytest.mark.parametrize("spans", [[(-1, 4)], [(0, 999)], [(4, 4)], [(0, 6), (4, 8)], [(True, 3)], [(0.0, 4)], [(3, 4)]])
def test_invalid_ranges_rejected_without_changing_saved_highlights(coded, spans):
    db, unit, a, _, text = coded
    db.save_code_highlights(unit, a, [(0, 3)])
    before = db.code_highlights(unit).to_dict("records")
    with pytest.raises(ValueError):
        db.save_code_highlights(unit, a, spans, expected_excerpt=text)
    assert db.code_highlights(unit).to_dict("records") == before


def test_empty_highlights_require_review_status_and_assigned_code(coded):
    db, unit, a, _, _ = coded
    with pytest.raises(ValueError):
        db.save_code_highlights(unit, a, [])
    db.save_code_highlights(unit, a, [], status="needs_review", note="No direct support in this excerpt.")
    assert db.code_highlights(unit).empty
    assert db.highlight_reviews(unit).set_index("code_id").loc[a, "status"] == "needs_review"
    with pytest.raises(ValueError):
        db.save_code_highlights(unit, 999, [(0, 3)])
    with pytest.raises(ValueError):
        db.save_code_highlights(unit, a, [(0, 3)], status="invalid")


def test_notes_preserve_spans_removed_codes_cascade_and_new_codes_are_unreviewed(coded):
    db, unit, a, b, text = coded
    db.save_code_highlights(unit, a, [(0, 3)])
    db.save_code_highlights(unit, b, [(0, 3)])  # Cross-code overlap is permitted.
    db.save_meaning_unit("response-a", "assessment_comments", text, [a, b], note="Revised note", unit_id=unit)
    assert len(db.code_highlights(unit)) == 2
    db.save_meaning_unit("response-a", "assessment_comments", text, [a], unit_id=unit)
    assert db.code_highlights(unit)["code_id"].tolist() == [a]
    db.save_meaning_unit("response-a", "assessment_comments", text, [a, b], unit_id=unit)
    assert db.highlight_reviews(unit).set_index("code_id").loc[b, "status"] == "unreviewed"
    assert len(db.code_highlights(unit)) == 1


def test_source_edit_invalidates_ranges_and_stale_editor_cannot_save(coded):
    db, unit, a, b, text = coded
    db.save_code_highlights(unit, a, [(0, 3)])
    db.save_meaning_unit("response-a", "assessment_comments", text + " More context.", [a, b], unit_id=unit)
    assert db.code_highlights(unit).empty
    assert set(db.highlight_reviews(unit)["status"]) == {"unreviewed"}
    with pytest.raises(ValueError, match="changed"):
        db.save_code_highlights(unit, a, [(0, 3)], expected_excerpt=text)


def test_direct_text_change_hides_stale_offsets(coded):
    db, unit, a, _, text = coded
    db.save_code_highlights(unit, a, [(0, 3)])
    with db.connect() as connection:
        connection.execute("UPDATE meaning_units SET excerpt=? WHERE id=?", ("New " + text, unit))
    assert db.code_highlights(unit).empty
    assert db.highlight_reviews(unit).set_index("code_id").loc[a, "status"] == "needs_review"


def test_unicode_repeated_text_and_multiple_spans(coded):
    db, unit, a, _, _ = coded
    text = "é🙂 tools and tools"
    db.save_meaning_unit("response-a", "assessment_comments", text, [a], unit_id=unit)
    db.save_code_highlights(unit, a, [(0, 2), (13, 18)], expected_excerpt=text)
    rows = db.code_highlights(unit)
    assert [r.excerpt[r.start_offset:r.end_offset] for r in rows.itertuples()] == ["é🙂", "tools"]


def test_deleting_excerpt_or_reset_cascades_highlights(coded):
    db, unit, a, _, _ = coded
    db.save_code_highlights(unit, a, [(0, 3)])
    db.delete_meaning_unit(unit)
    assert db.code_highlights().empty and db.highlight_reviews().empty
    unit = db.save_meaning_unit("response-a", "strengths", "New excerpt", [a])
    db.save_code_highlights(unit, a, [(0, 3)])
    db.reset_qualitative_analysis()
    assert db.code_highlights().empty and db.highlight_reviews().empty
    with db.connect() as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
