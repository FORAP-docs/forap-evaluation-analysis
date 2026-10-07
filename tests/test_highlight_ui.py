from streamlit.testing.v1 import AppTest


def highlight_app(edit_mode=False):
    import pandas as pd
    import streamlit as st
    from app import render_excerpt_highlights
    from forap_analysis.highlights import excerpt_digest

    st.session_state.setdefault("edit_mode", edit_mode)
    excerpt = "Alpha 🙂 and Alpha <tag>."
    digest = excerpt_digest(excerpt)

    class FixtureDatabase:
        def codes(self, active_only=True):
            return self.highlight_reviews().rename(columns={"code_id": "id", "code_name": "name"})

        def highlight_reviews(self, unit_id=None):
            saved = st.session_state.get("saved", {})
            return pd.DataFrame([
                {
                    "meaning_unit_id": 10, "code_id": code_id,
                    "code_name": f"Code {code_id}", "color": color, "excerpt": excerpt,
                    "excerpt_sha256": digest,
                    "status": saved[code_id]["status"] if code_id in saved else default,
                    "review_note": saved[code_id]["note"] if code_id in saved else "",
                }
                for code_id, color, default in [(1, "#8a3ffc", "reviewed"), (2, "#8a3ffc", "unreviewed")]
            ])

        def code_highlights(self, unit_id=None):
            saved = st.session_state.get("saved", {})
            reviews = self.highlight_reviews()
            rows = []
            for _, review in reviews.iterrows():
                code_id = int(review["code_id"])
                spans = saved[code_id]["spans"] if code_id in saved else ([(0, 5)] if code_id == 1 else [])
                rows.extend({**review.to_dict(), "start_offset": start, "end_offset": end} for start, end in spans)
            return pd.DataFrame(rows, columns=[*reviews.columns, "start_offset", "end_offset"])

        def save_code_highlights(self, unit_id, code_id, spans, *, status, note, expected_excerpt):
            if st.session_state.get("simulate_stale"):
                raise ValueError("The excerpt changed. Reload it before saving highlights.")
            assert unit_id == 10 and expected_excerpt == excerpt
            saved = st.session_state.setdefault("saved", {})
            saved[code_id] = {"spans": spans, "status": status, "note": note, "expected_excerpt": expected_excerpt}

    db = FixtureDatabase()
    if st.session_state.get("legacy_mode"):
        render_excerpt_highlights(db, None, excerpt, "legacy_fixture", fallback_code_names="Code 1 | Code 2")
        return
    if st.session_state.get("dialog_mode"):
        @st.dialog("Excerpt details", width="large")
        def dialog():
            render_excerpt_highlights(db, 10, excerpt, "fixture", in_dialog=True)

        if st.button("Open excerpt"):
            st.session_state["fixture_dialog_open"] = True
        if st.session_state.get("fixture_dialog_open"):
            dialog()
    else:
        with st.expander("Evidence", expanded=True):
            render_excerpt_highlights(db, 10, excerpt, "fixture")


def element(app, kind, label):
    return next(item for item in getattr(app, kind) if item.label == label)


def test_shared_view_has_no_filter_or_top_legend_and_one_set_of_bottom_tags():
    app = AppTest.from_function(highlight_app).run()
    assert not app.exception
    assert not any(item.label == "Highlight view" for item in app.selectbox)
    rendered = next(item.value for item in app.markdown if 'class="passage-view"' in item.value)
    assert "passage-legend" not in rendered and "<sup" not in rendered
    badges = [item.value for item in app.markdown if 'class="code-badges"' in item.value]
    assert len(badges) == 1
    assert "Code 1" in badges[0] and "Code 2" in badges[0]
    assert "Not reviewed yet" in badges[0]
    values = [item.value for item in app.markdown]
    assert values.index(rendered) < values.index(badges[0])
    assert not app.text_area
    assert not any(item.label == "Edit highlighted passages" for item in app.expander)
    assert not any(item.label == "Save highlights" for item in app.button)


def test_same_group_shades_match_passages_tags_and_editor_preview():
    import re
    from forap_analysis.highlights import code_display_colors

    app = AppTest.from_function(highlight_app, args=(True,))
    app.session_state["saved"] = {
        1: {"spans": [(0, 5)], "status": "reviewed", "note": ""},
        2: {"spans": [(2, 7)], "status": "reviewed", "note": ""},
    }
    app.run()
    assert not app.exception
    palette = code_display_colors([
        {"id": 1, "color": "#8a3ffc"}, {"id": 2, "color": "#8a3ffc"},
    ])
    assert palette[1] != palette[2]
    quotes = [item.value for item in app.markdown if 'class="passage-view"' in item.value]
    assert 'data-code-ids="1,2"' in quotes[0]
    for color in palette.values():
        assert color in quotes[0]
    badges = next(item.value for item in app.markdown if 'class="code-badges"' in item.value)
    assert re.findall(r'--code-color:(#[0-9a-fA-F]{6})', badges) == list(palette.values())
    assert palette[1] in quotes[1]
    element(app, "selectbox", "Code to highlight").select(2).run()
    quotes = [item.value for item in app.markdown if 'class="passage-view"' in item.value]
    assert palette[2] in quotes[1]
    assert 'data-code-ids="1,2"' in quotes[0]


def test_legacy_excerpt_keeps_one_set_of_tags_without_guessing_highlights():
    app = AppTest.from_function(highlight_app)
    app.session_state["legacy_mode"] = True
    app.run()
    assert not app.exception
    badges = [item.value for item in app.markdown if 'class="code-badges"' in item.value]
    assert len(badges) == 1 and "Code 1" in badges[0] and "Code 2" in badges[0]
    assert not any('<mark' in item.value for item in app.markdown)
    assert not app.selectbox


def test_editor_adds_selected_repeat_and_saves_multiple_exact_passages():
    app = AppTest.from_function(highlight_app, args=(True,)).run()
    element(app, "text_area", "Exact words to highlight").set_value("Alpha").run()
    assert len(element(app, "selectbox", "Which occurrence?").options) == 2
    element(app, "selectbox", "Which occurrence?").select(1).run()
    element(app, "button", "Add passage").click().run()
    assert not app.exception
    element(app, "button", "Save highlights").click().run()
    assert not app.exception
    saved = app.session_state["saved"][1]
    assert saved["spans"] == [(0, 5), (12, 17)]
    assert saved["expected_excerpt"] == "Alpha 🙂 and Alpha <tag>."
    assert saved["status"] == "reviewed"


def test_editor_saves_needs_review_without_guessing_a_passage():
    app = AppTest.from_function(highlight_app, args=(True,)).run()
    element(app, "selectbox", "Code to highlight").select(2).run()
    element(app, "radio", "Highlight review").set_value("reviewed").run()
    element(app, "button", "Save highlights").click().run()
    assert any("Select at least one passage" in item.value for item in app.error)
    element(app, "radio", "Highlight review").set_value("needs_review").run()
    element(app, "text_area", "Highlight review note").set_value("Check the fit.").run()
    element(app, "button", "Save highlights").click().run()
    assert not app.exception
    assert app.session_state["saved"][2]["spans"] == []
    assert app.session_state["saved"][2]["note"] == "Check the fit."
    badges = next(item.value for item in app.markdown if 'class="code-badges"' in item.value)
    assert "Needs review" in badges and "Check the fit." in badges


def test_phrase_mismatch_and_stale_save_are_visible_errors():
    app = AppTest.from_function(highlight_app, args=(True,)).run()
    element(app, "text_area", "Exact words to highlight").set_value("missing words").run()
    assert element(app, "button", "Add passage").disabled
    assert app.warning
    app.session_state["simulate_stale"] = True
    element(app, "button", "Save highlights").click().run()
    assert not app.exception
    assert any("excerpt changed" in item.value for item in app.error)


def test_editor_works_inside_existing_dialog_without_nested_dialog():
    app = AppTest.from_function(highlight_app, args=(True,))
    app.session_state["dialog_mode"] = True
    app.run()
    element(app, "button", "Open excerpt").click().run()
    assert not app.exception
    element(app, "text_area", "Exact words to highlight").set_value("🙂").run()
    element(app, "button", "Add passage").click().run()
    assert not app.exception
    element(app, "button", "Save highlights").click().run()
    assert not app.exception
    assert app.session_state["saved"][1]["spans"] == [(0, 5), (6, 7)]


def test_editor_can_remove_and_reset_passages():
    app = AppTest.from_function(highlight_app, args=(True,)).run()
    element(app, "multiselect", "Passages to remove").set_value([(0, 5)]).run()
    element(app, "button", "Remove selected passages").click().run()
    assert not app.exception
    assert not app.multiselect
    element(app, "button", "Reset passage selection").click().run()
    assert element(app, "multiselect", "Passages to remove").options == ["Characters 1 to 5: Alpha"]


def test_editor_can_save_overlapping_evidence_for_another_code():
    app = AppTest.from_function(highlight_app, args=(True,)).run()
    element(app, "selectbox", "Code to highlight").select(2).run()
    element(app, "text_area", "Exact words to highlight").set_value("pha 🙂").run()
    element(app, "button", "Add passage").click().run()
    element(app, "radio", "Highlight review").set_value("reviewed").run()
    element(app, "button", "Save highlights").click().run()
    assert not app.exception
    assert app.session_state["saved"][2]["spans"] == [(2, 7)]
    assert any('data-code-ids="1,2"' in item.value for item in app.markdown)


def database_highlight_app(path, unit_id):
    from forap_analysis.database import Database
    from app import render_excerpt_highlights

    db = Database(path)
    excerpt = str(db.meaning_units().set_index("id").loc[unit_id, "excerpt"])
    render_excerpt_highlights(db, unit_id, excerpt, "database_fixture")


def test_ui_round_trip_with_real_temporary_database_preserves_coding(tmp_path):
    from forap_analysis.database import Database
    from forap_analysis.importer import preview_workbook
    from test_importer import workbook_bytes

    path = tmp_path / "ui.sqlite3"
    db = Database(path)
    db.activate_import(preview_workbook(workbook_bytes(), "fixture.xlsx"))
    respondent = db.active_data().iloc[0]
    code_id = db.save_code("Example code", "Definition", "Include", "Exclude", "#007d79")
    excerpt = str(respondent["strengths"])
    unit_id = db.save_meaning_unit(str(respondent["response_id"]), "strengths", excerpt, [code_id], "Original interpretation")
    before_units = db.meaning_units().to_json()
    before_codings = db.codings().to_json()
    app = AppTest.from_function(database_highlight_app, args=(str(path), unit_id))
    app.session_state["edit_mode"] = True
    app.run()
    assert not app.exception
    element(app, "text_area", "Exact words to highlight").set_value(excerpt).run()
    element(app, "button", "Add passage").click().run()
    element(app, "radio", "Highlight review").set_value("reviewed").run()
    element(app, "button", "Save highlights").click().run()
    assert not app.exception
    saved = db.code_highlights(unit_id)
    assert saved[["start_offset", "end_offset"]].values.tolist() == [[0, len(excerpt)]]
    assert db.meaning_units().to_json() == before_units
    assert db.codings().to_json() == before_codings
    db.update_code_color(code_id, "#da1e28")
    app.run()
    assert any("#da1e28" in item.value for item in app.markdown)
