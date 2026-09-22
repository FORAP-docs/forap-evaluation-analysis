"""Browsing imports and saved background groups must not edit analysis data."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from forap_analysis.database import Database
from test_respondent_navigation_ui import database_signature


def background_app(database_path: str, field_key: str, values: list[str], panel: str):
    from pathlib import Path

    import pandas as pd
    import streamlit as st

    import app
    from forap_analysis.database import Database
    from forap_analysis.schema import FIELD_BY_KEY

    db = Database(Path(database_path))
    if panel == "upload":
        app.render_upload(db)
        return
    st.toggle("Edit mode", key="edit_mode", on_change=app.change_edit_mode)
    field = FIELD_BY_KEY[field_key]
    frame = pd.DataFrame({field_key: values})
    if panel == "mapping":
        app.render_background_mapping_panel(db, frame, field, st.container())
        return
    result = app.render_custom_group_builder(db, frame, field)
    st.session_state["result"] = None if result is None else result.fillna("Excluded").tolist()


def run_panel(db, field_key="institution_type", values=None, panel="groups"):
    app = AppTest.from_function(
        background_app,
        args=(str(db.path), field_key, values or [], panel),
        default_timeout=20,
    ).run()
    assert not app.exception
    return app


def save_groups(db, name="Institutions", field="institution_type", first="Research university", second="Teaching-focused college or university"):
    return db.save_background_grouping(
        field, name,
        [{"name": "First", "categories": [first]}, {"name": "Second", "categories": [second]}],
    )


def test_upload_view_keeps_history_and_metrics_without_uploader(tmp_path: Path):
    db = Database(tmp_path / "upload.sqlite3")
    before = database_signature(db)
    app = run_panel(db, panel="upload")
    assert len(app.metric) == 3
    assert any(item.value == "Import history" for item in app.subheader)
    assert not app.get("file_uploader")
    assert [item.key for item in app.button] == ["prepare_database_export"]
    assert database_signature(db) == before
    app.toggle(key="edit_mode").set_value(True).run()
    assert not app.exception
    assert {item.label for item in app.get("file_uploader")} == {"Database backup", "Current Google Forms export"}


def test_category_mapping_is_hidden_until_edit_mode(tmp_path: Path):
    db = Database(tmp_path / "mapping.sqlite3")
    before = database_signature(db)
    app = run_panel(db, values=["Research university"], panel="mapping")
    assert not app.expander
    assert not app.button
    assert database_signature(db) == before
    app.toggle(key="edit_mode").set_value(True).run()
    assert not app.exception
    assert any(item.label == "Manage categories" for item in app.expander)
    assert any(item.label == "Save mapping" for item in app.button)


def test_saved_groups_can_be_browsed_without_persisting_selection(tmp_path: Path):
    db = Database(tmp_path / "groups.sqlite3")
    first = save_groups(db)
    second = save_groups(db, "Alternative")
    db.select_background_grouping("institution_type", first)
    before = database_signature(db)
    app = run_panel(
        db,
        values=["Research university"] * 3 + ["Teaching-focused college or university"] * 3,
    )
    assert app.session_state["result"] == ["First"] * 3 + ["Second"] * 3
    assert not app.button
    assert not app.text_input
    assert not app.get("data_editor")
    app.selectbox(key="custom_group_institution_type_view_saved_selection").select(second).run()
    assert not app.exception
    assert app.session_state["custom_group_institution_type_view_selection"] == second
    assert db.selected_background_grouping("institution_type") == first
    assert database_signature(db) == before
    app.toggle(key="edit_mode").set_value(True).run()
    assert not app.exception
    assert any(item.label == "Save as new" for item in app.button)
    assert any(item.label == "Update saved grouping" for item in app.button)
    assert app.text_input
    assert app.selectbox(key="custom_group_institution_type_saved_selection").value == second
    assert database_signature(db) == before
    app.toggle(key="edit_mode").set_value(False).run()
    assert not app.exception
    assert app.selectbox(key="custom_group_institution_type_view_saved_selection").value == second
    app.toggle(key="edit_mode").set_value(True).run()
    assert not app.exception
    assert app.selectbox(key="custom_group_institution_type_saved_selection").value == second
    assert database_signature(db) == before


def test_custom_group_draft_survives_view_mode_without_saving(tmp_path: Path):
    db = Database(tmp_path / "draft.sqlite3")
    saved = save_groups(db)
    db.select_background_grouping("institution_type", saved)
    before = database_signature(db)
    app = run_panel(
        db,
        values=["Research university"] * 3 + ["Teaching-focused college or university"] * 3,
    )
    app.toggle(key="edit_mode").set_value(True).run()
    assert not app.exception
    app.text_input(key="custom_group_name_institution_type_0").set_value("Draft group name").run()
    app.text_input(key="custom_group_institution_type_save_name").set_value("Unsaved grouping name").run()
    assert not app.exception
    app.toggle(key="edit_mode").set_value(False).run()
    assert not app.exception
    assert not app.text_input
    app.toggle(key="edit_mode").set_value(True).run()
    assert not app.exception
    assert app.text_input(key="custom_group_name_institution_type_0").value == "Draft group name"
    assert app.text_input(key="custom_group_institution_type_save_name").value == "Unsaved grouping name"
    assert database_signature(db) == before


def test_saved_multi_select_groups_exclude_overlapping_memberships(tmp_path: Path):
    db = Database(tmp_path / "roles.sqlite3")
    save_groups(db, field="roles", first="Instructor", second="Researcher")
    before = database_signature(db)
    app = run_panel(db, "roles", ["Instructor", "Instructor", "Researcher", "Researcher", "Instructor, Researcher"])
    assert app.session_state["result"] == ["First", "First", "Second", "Second", "Excluded"]
    assert any("1 matched more than one group" in item.value for item in app.caption)
    assert database_signature(db) == before


def test_incomplete_saved_group_draft_is_not_reloaded_on_mode_change(tmp_path: Path):
    db = Database(tmp_path / "incomplete-draft.sqlite3")
    saved = save_groups(db)
    db.select_background_grouping("institution_type", saved)
    before = database_signature(db)
    app = run_panel(
        db,
        values=["Research university"] * 3 + ["Teaching-focused college or university"] * 3,
    )
    app.toggle(key="edit_mode").set_value(True).run()
    app.selectbox(key="custom_group_count_institution_type").select(3).run()
    assert not app.exception
    app.text_input(key="custom_group_name_institution_type_2").set_value("Unassigned draft group").run()
    assert not app.exception
    assert app.session_state["result"] is None
    app.toggle(key="edit_mode").set_value(False).run()
    app.toggle(key="edit_mode").set_value(True).run()
    assert not app.exception
    assert app.selectbox(key="custom_group_count_institution_type").value == 3
    assert app.text_input(key="custom_group_name_institution_type_2").value == "Unassigned draft group"
    assert database_signature(db) == before


def test_saved_groups_require_two_respondents_each(tmp_path: Path):
    db = Database(tmp_path / "small.sqlite3")
    save_groups(db)
    before = database_signature(db)
    app = run_panel(db, values=["Research university", "Research university", "Teaching-focused college or university"])
    assert app.session_state["result"] is None
    assert any("at least two respondents" in item.value for item in app.warning)
    assert database_signature(db) == before


def test_empty_saved_group_list_does_not_show_builder(tmp_path: Path):
    db = Database(tmp_path / "empty.sqlite3")
    before = database_signature(db)
    app = run_panel(db, values=["Research university"])
    assert app.session_state["result"] is None
    assert any("No saved groupings" in item.value for item in app.caption)
    assert not app.selectbox
    assert not app.text_input
    assert not app.button
    assert database_signature(db) == before


def test_saved_groups_with_unavailable_categories_cannot_be_analyzed(tmp_path: Path):
    db = Database(tmp_path / "unavailable.sqlite3")
    save_groups(db, second="Retired institution category")
    before = database_signature(db)
    app = run_panel(db, values=["Research university"] * 3)
    assert app.session_state["result"] is None
    assert any("needs an available background category" in item.value for item in app.info)
    assert any("not present in the current data" in item.value for item in app.caption)
    assert database_signature(db) == before
