"""The global edit switch hides mutations without removing reading/navigation."""

import pytest

from forap_analysis.schema import BACKGROUND_CATEGORY_OPTIONS, FIELD_BY_KEY
from test_respondent_navigation_ui import (
    database_signature,
    go_back,
    navigation_database,
    open_response,
    start_app,
)


MUTATION_BUTTONS = {
    "Edit", "Delete", "Add coded excerpt", "Save coded excerpt",
    "Add passage", "Remove selected passages", "Reset passage selection", "Save highlights",
    "Create working codes", "Save working code", "Deactivate code",
    "Add theme", "Edit theme", "Save theme", "Attach evidence", "Remove evidence",
    "Save note", "Save mapping", "Activate validated snapshot",
}
EDITOR_EXPANDERS = {
    "Edit highlighted passages", "Add a working code", "Stop using a code", "Attach evidence",
    "Manage categories", "Save this grouping",
}


def assert_view_mode(app):
    assert not app.exception
    assert app.toggle(key="edit_mode").value is False
    assert not (MUTATION_BUTTONS & {button.label for button in app.button})
    assert not (EDITOR_EXPANDERS & {expander.label for expander in app.expander})
    assert not any(toggle.label == "Representative quotation" for toggle in app.toggle)
    assert not app.color_picker
    assert not app.get("file_uploader")


def review_state():
    question = FIELD_BY_KEY["clarity_comments"]
    return {
        "workspace_page": "Thematic analysis",
        "thematic_tab": "Review responses",
        "all_open_text_question": question,
        "all_open_text_active_question": question.key,
        "all_open_text_response_position": 0,
    }


def test_thematic_defaults_to_compact_read_only_and_toggle_restores_editors(navigation_database):
    db, _, _, units, themes = navigation_database
    before = database_signature(db)
    details_key = f"theme_evidence_details_{themes[0]}_{units[0]}"
    app = start_app(db, **review_state(), **{details_key: True})
    assert_view_mode(app)
    assert not app.text_area
    code_table = next(table.value for table in app.dataframe if "Working code" in table.value.columns)
    assert "Open" in code_table.columns
    assert "Color" not in code_table.columns
    assert app.selectbox(key="all_open_text_question")
    assert app.toggle(key=details_key).value is True

    app.toggle(key="edit_mode").set_value(True).run()
    assert not app.exception
    buttons = {button.label for button in app.button}
    assert {"Edit", "Delete", "Add coded excerpt", "Save highlights", "Save working code", "Deactivate code", "Add theme", "Edit theme", "Save note"} <= buttons
    assert app.toggle(key=f"theme_evidence_representative_{themes[0]}_{units[0]}")
    code_table = next(table.value for table in app.dataframe if "Working code" in table.value.columns)
    assert "Color" in code_table.columns

    app.toggle(key="edit_mode").set_value(False).run()
    assert_view_mode(app)
    assert not app.text_area
    assert database_signature(db) == before


def test_global_mode_survives_routes_and_back_uses_current_mode(navigation_database):
    db, respondents, _, _, _ = navigation_database
    before = database_signature(db)
    app = start_app(db, **review_state())
    app.toggle(key="edit_mode").set_value(True).run()
    open_response(app, f"respondent_link_review_all_open_text_{respondents[0]}", respondents[0])
    assert app.toggle(key="edit_mode").value is True
    app.toggle(key="edit_mode").set_value(False).run()
    go_back(app, "Thematic analysis")
    assert_view_mode(app)
    assert app.session_state["thematic_tab"] == "Review responses"
    app.sidebar.radio(key="workspace_page").set_value("Overview").run()
    assert_view_mode(app)
    app.toggle(key="edit_mode").set_value(True).run()
    app.sidebar.radio(key="workspace_page").set_value("Upload & data health").run()
    assert not app.exception
    assert app.toggle(key="edit_mode").value is True
    assert {item.label for item in app.get("file_uploader")} == {"Database backup", "Current Google Forms export"}
    app.toggle(key="edit_mode").set_value(False).run()
    assert_view_mode(app)
    assert database_signature(db) == before


def test_code_dialog_remains_readable_without_highlight_or_color_editors(navigation_database):
    db, _, codes, units, _ = navigation_database
    before = database_signature(db)
    app = start_app(
        db,
        workspace_page="Thematic analysis",
        thematic_tab="Working codes",
        working_code_details_id=codes[0],
        working_code_color_id=codes[0],
    )
    assert_view_mode(app)
    assert app.button(key=f"respondent_link_code_{codes[0]}_{units[0]}")
    assert app.selectbox(key=f"working_code_excerpt_question_{codes[0]}")
    assert app.text_input(key=f"working_code_excerpt_search_{codes[0]}")
    assert not app.text_area
    assert any('class="passage-view"' in item.value for item in app.markdown)
    assert database_signature(db) == before


def test_enabled_mode_can_save_an_excerpt_and_read_only_displays_the_saved_result(navigation_database):
    db, _, _, units, _ = navigation_database
    app = start_app(db, **review_state(), edit_mode=True)
    app.button(key=f"all_open_text_edit_unit_{units[0]}").click().run()
    assert not app.exception
    interpretation = next(item for item in app.text_area if item.label == "Your interpretation")
    interpretation.set_value("A clearer fixture interpretation.").run()
    next(button for button in app.button if button.label == "Save coded excerpt").click().run()
    assert not app.exception
    unit = db.meaning_units().set_index("id").loc[units[0]]
    assert unit["note"] == "A clearer fixture interpretation."
    assert unit["excerpt"] == "Example"
    assert len(db.meaning_units()) == 3
    saved = database_signature(db)
    # AppTest can retain removed editor elements after the save-triggered rerun.
    # Open a fresh reading session for the persisted result; toggle continuity is
    # exercised separately without submitting an editor that removes itself.
    app = start_app(db, **review_state())
    assert_view_mode(app)
    assert any("A clearer fixture interpretation." in item.value for item in app.markdown)
    assert database_signature(db) == saved


def test_toggling_preserves_unsaved_excerpt_highlight_and_note_inputs(navigation_database):
    from forap_analysis.highlights import excerpt_digest

    db, _, codes, units, _ = navigation_database
    before = database_signature(db)
    app = start_app(db, **review_state(), edit_mode=True)
    app.button(key=f"all_open_text_edit_unit_{units[0]}").click().run()
    interpretation = next(item for item in app.text_area if item.label == "Your interpretation")
    interpretation_key = interpretation.key
    interpretation.set_value("Unsaved interpretation.").run()
    phrase_key = f"coding_all_open_text_{units[0]}_{codes[0]}_{excerpt_digest('Example')[:16]}_phrase"
    app.text_area(key=phrase_key).set_value("Exam").run()
    app.text_input(key="edit_memo_title").set_value("Unsaved note title").run()
    app.text_area(key="edit_memo_content").set_value("Unsaved note content.").run()
    app.toggle(key="edit_mode").set_value(False).run()
    assert_view_mode(app)
    assert not app.text_area
    assert database_signature(db) == before
    app.toggle(key="edit_mode").set_value(True).run()
    assert not app.exception
    assert app.text_area(key=interpretation_key).value == "Unsaved interpretation."
    assert app.text_area(key=phrase_key).value == "Exam"
    assert app.text_input(key="edit_memo_title").value == "Unsaved note title"
    assert app.text_area(key="edit_memo_content").value == "Unsaved note content."
    assert database_signature(db) == before


@pytest.mark.parametrize("page", [
    "Overview", "Individual responses", "Items & scales", "Background comparisons",
    "Mixed methods", "Reports & exports", "Upload & data health",
])
def test_every_other_route_has_one_default_read_only_switch(navigation_database, page):
    db, _, _, _, _ = navigation_database
    before = database_signature(db)
    app = start_app(db, workspace_page=page)
    assert_view_mode(app)
    assert sum(toggle.key == "edit_mode" for toggle in app.toggle) == 1
    if page == "Reports & exports":
        assert app.get("download_button")
    if page == "Upload & data health":
        assert any(item.value == "Import history" for item in app.subheader)
    assert database_signature(db) == before


def test_saved_background_groupings_can_be_browsed_without_persisting_selection(navigation_database):
    db, _, _, _, _ = navigation_database
    field = "institution_type"
    groups = [
        {"name": "Example group", "categories": ["Example"]},
        {"name": "Other group", "categories": [BACKGROUND_CATEGORY_OPTIONS[field][0]]},
    ]
    first = db.save_background_grouping(field, "First grouping", groups)
    second = db.save_background_grouping(field, "Second grouping", groups)
    db.select_background_grouping(field, first)
    before = database_signature(db)
    app = start_app(
        db,
        workspace_page="Background comparisons",
        background_comparison_field_remembered=field,
        background_grouping_mode_remembered="Custom",
    )
    assert_view_mode(app)
    selection = next(item for item in app.selectbox if item.label == "Saved grouping")
    assert selection.value == first
    selection.select(second).run()
    assert_view_mode(app)
    assert next(item for item in app.selectbox if item.label == "Saved grouping").value == second
    assert db.selected_background_grouping(field) == first
    assert database_signature(db) == before
