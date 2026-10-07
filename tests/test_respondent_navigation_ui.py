"""Exercise respondent links against actual app views and a disposable database."""

import sqlite3
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from forap_analysis.database import Database
from forap_analysis.importer import preview_workbook
from forap_analysis.schema import FIELD_BY_KEY
from test_importer import workbook_bytes


def navigation_app(database_path: str) -> None:
    import app
    from pathlib import Path
    from forap_analysis.database import Database

    original_database = app.get_database
    app.get_database = lambda **kwargs: Database(Path(database_path))
    try:
        app.main()
    finally:
        app.get_database = original_database


@pytest.fixture
def navigation_database(tmp_path: Path):
    db = Database(tmp_path / "navigation.sqlite3")
    db.activate_import(preview_workbook(workbook_bytes(3), "responses.xlsx"))
    respondents = db.active_data()["response_id"].astype(str).tolist()
    version = db.create_codebook_version("Navigation fixture")
    codes = [
        db.save_code(
            f"CL{number} - Fixture {number}", "Fixture definition.",
            "Include a relevant comment.", "Exclude other comments.",
            codebook_version_id=version,
        )
        for number in (1, 2)
    ]
    units = [
        db.save_meaning_unit(respondents[0], "clarity_comments", "Example", [codes[0]], "First interpretation."),
        db.save_meaning_unit(respondents[1], "completeness_comments", "Example", [codes[0]], "Target interpretation."),
        db.save_meaning_unit(respondents[2], "clarity_comments", "Example", [codes[1]], "Third interpretation."),
    ]
    themes = [
        db.save_theme(f"Fixture theme {number}", "A fixture theme.", [codes[number - 1]])
        for number in (1, 2)
    ]
    db.save_theme_evidence(themes[0], units[0], "supporting")
    db.save_theme_evidence(themes[1], units[1], "contextual", "Context note.", True)
    db.save_theme_evidence(themes[1], units[2], "supporting")
    return db, respondents, codes, units, themes


def database_signature(db: Database) -> tuple:
    # SQLite may create/update its own optimizer statistics when Database opens.
    # Compare every application table, including audit and revision records.
    with sqlite3.connect(db.path) as connection:
        tables = connection.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return tuple(
            (name, schema, tuple(connection.execute(f'SELECT * FROM "{name}" ORDER BY rowid')))
            for name, schema in tables
        )


def start_app(db: Database, **state) -> AppTest:
    app = AppTest.from_function(navigation_app, args=(str(db.path),), default_timeout=20)
    for key, value in state.items():
        app.session_state[key] = value
    app.run()
    assert not app.exception
    return app


def open_response(app: AppTest, button_key: str, expected_id: str) -> None:
    app.button(key=button_key).click().run()
    assert not app.exception
    assert app.sidebar.radio(key="workspace_page").value == "Individual responses"
    assert app.selectbox(key="individual_response_selection").value == expected_id
    assert app.button(key="response_navigation_back")


def go_back(app: AppTest, expected_page: str) -> None:
    app.button(key="response_navigation_back").click().run()
    assert not app.exception
    assert app.sidebar.radio(key="workspace_page").value == expected_page


def test_code_dialog_link_and_back_restore_filtered_dialog_without_writes(navigation_database):
    db, respondents, codes, units, _ = navigation_database
    before = database_signature(db)
    code = codes[0]
    question = FIELD_BY_KEY["completeness_comments"].label
    app = start_app(
        db,
        workspace_page="Thematic analysis",
        thematic_tab="Working codes",
        working_code_details_id=code,
        **{
            f"working_code_excerpt_question_{code}": question,
            f"working_code_excerpt_search_{code}": "Target",
        },
    )
    assert app.selectbox(key=f"working_code_excerpt_question_{code}").value == question
    assert app.text_input(key=f"working_code_excerpt_search_{code}").value == "Target"
    open_response(app, f"respondent_link_code_{code}_{units[1]}", respondents[1])
    go_back(app, "Thematic analysis")
    assert app.session_state["thematic_tab"] == "Working codes"
    assert app.selectbox(key=f"working_code_excerpt_question_{code}").value == question
    assert app.text_input(key=f"working_code_excerpt_search_{code}").value == "Target"
    assert app.button(key=f"respondent_link_code_{code}_{units[1]}").label == "R2"
    assert not any(button.key == f"respondent_link_code_{code}_{units[0]}" for button in app.button)
    assert database_signature(db) == before


def test_review_link_back_preserves_question_position_after_previous_next(navigation_database):
    db, respondents, _, _, _ = navigation_database
    before = database_signature(db)
    question = FIELD_BY_KEY["completeness_comments"]
    app = start_app(
        db,
        workspace_page="Thematic analysis",
        thematic_tab="Review responses",
        all_open_text_question=question,
        all_open_text_active_question=question.key,
        all_open_text_response_position=1,
    )
    open_response(app, f"respondent_link_review_all_open_text_{respondents[1]}", respondents[1])
    app.button(key="individual_response_next").click().run()
    assert not app.exception
    assert app.selectbox(key="individual_response_selection").value == respondents[2]
    app.button(key="individual_response_previous").click().run()
    assert app.selectbox(key="individual_response_selection").value == respondents[1]
    go_back(app, "Thematic analysis")
    assert app.session_state["thematic_tab"] == "Review responses"
    assert app.selectbox(key="all_open_text_question").value == question
    assert app.session_state["all_open_text_response_position"] == 1
    assert app.button(key=f"respondent_link_review_all_open_text_{respondents[1]}").label == "R2"
    assert database_signature(db) == before


def test_theme_link_back_preserves_selected_theme_and_evidence_details(navigation_database):
    db, respondents, _, units, themes = navigation_database
    before = database_signature(db)
    theme, unit = themes[1], units[1]
    details_key = f"theme_evidence_details_{theme}_{unit}"
    group_key = f"theme_evidence_group_{theme}_contextual"
    app = start_app(
        db,
        workspace_page="Thematic analysis",
        thematic_tab="Build themes",
        theme_detail_selection=theme,
        selected_theme_id=theme,
        **{details_key: True, group_key: True},
    )
    assert app.toggle(key=details_key).value is True
    open_response(app, f"respondent_link_theme_{theme}_{unit}", respondents[1])
    go_back(app, "Thematic analysis")
    assert app.session_state["thematic_tab"] == "Build themes"
    assert app.selectbox(key="theme_detail_selection").value == theme
    assert app.toggle(key=details_key).value is True
    assert app.session_state[group_key] is True
    assert not any(toggle.key == f"theme_evidence_representative_{theme}_{unit}" for toggle in app.toggle)
    assert any("Representative quotation" in item.value for item in app.markdown)
    assert database_signature(db) == before


def test_mixed_methods_link_back_preserves_code_lens_and_evidence_expander(navigation_database):
    db, respondents, codes, units, _ = navigation_database
    before = database_signature(db)
    code, unit = codes[1], units[2]
    group_key = f"mixed_evidence_group_Working code_{code}_all"
    rows_key = f"mixed_methods_selected_rows_Working code_{code}"
    app = start_app(
        db,
        workspace_page="Mixed methods",
        mixed_methods_lens="Working code",
        mixed_methods_code=code,
        **{group_key: True, rows_key: [1]},
    )
    assert app.session_state[rows_key] == [1]
    assert any(heading.value == "Completeness" for heading in app.subheader)
    button_key = next(
        button.key for button in app.button
        if button.key and button.key.startswith(f"respondent_link_mixed_Working code_{code}_{unit}_")
    )
    open_response(app, button_key, respondents[2])
    go_back(app, "Mixed methods")
    assert app.selectbox(key="mixed_methods_lens").value == "Working code"
    assert app.selectbox(key="mixed_methods_code").value == code
    assert app.session_state[group_key] is True
    assert app.session_state[rows_key] == [1]
    assert any(heading.value == "Completeness" for heading in app.subheader)
    assert app.button(key=button_key).label == "R3"
    assert database_signature(db) == before


def test_inactive_respondent_link_warns_instead_of_opening_first_active_record(navigation_database):
    db, respondents, codes, units, _ = navigation_database
    # This is fixture setup, not an action performed by the navigation UI.
    with db.connect() as connection:
        connection.execute("UPDATE responses SET is_active=0 WHERE response_id=?", (respondents[1],))
    before = database_signature(db)
    code = codes[0]
    app = start_app(
        db,
        workspace_page="Thematic analysis",
        thematic_tab="Working codes",
        working_code_details_id=code,
    )
    app.button(key=f"respondent_link_code_{code}_{units[1]}").click().run()
    assert not app.exception
    assert app.sidebar.radio(key="workspace_page").value == "Individual responses"
    assert any("not available in the active snapshot" in warning.value for warning in app.warning)
    assert not any(selectbox.key == "individual_response_selection" for selectbox in app.selectbox)
    assert app.session_state["individual_response_selection"] == respondents[1]
    go_back(app, "Thematic analysis")
    assert app.button(key=f"respondent_link_code_{code}_{units[1]}").label == "R2"
    assert database_signature(db) == before


def test_individual_page_uses_stable_ids_with_gaps_in_respondent_numbers(navigation_database):
    db, respondents, _, _, _ = navigation_database
    with db.connect() as connection:
        connection.execute("UPDATE responses SET is_active=0 WHERE response_id=?", (respondents[1],))
    before = database_signature(db)
    app = start_app(db, workspace_page="Individual responses", individual_response_selection=respondents[2])
    selection = app.selectbox(key="individual_response_selection")
    assert selection.options == ["R1", "R3"]
    assert selection.value == respondents[2]
    assert not any(button.key == "response_navigation_back" for button in app.button)
    app.button(key="individual_response_previous").click().run()
    assert app.selectbox(key="individual_response_selection").value == respondents[0]
    app.button(key="individual_response_next").click().run()
    assert app.selectbox(key="individual_response_selection").value == respondents[2]
    assert not app.exception
    assert database_signature(db) == before


def test_review_roundtrip_keeps_unsaved_highlight_input(navigation_database):
    from forap_analysis.highlights import excerpt_digest

    db, respondents, codes, units, _ = navigation_database
    before = database_signature(db)
    unit, code = units[0], codes[0]
    phrase_key = f"coding_all_open_text_{unit}_{code}_{excerpt_digest('Example')[:16]}_phrase"
    question = FIELD_BY_KEY["clarity_comments"]
    app = start_app(
        db,
        edit_mode=True,
        workspace_page="Thematic analysis",
        thematic_tab="Review responses",
        all_open_text_question=question,
        all_open_text_active_question=question.key,
        all_open_text_response_position=0,
    )
    app.text_area(key=phrase_key).set_value("Exam").run()
    open_response(app, f"respondent_link_review_all_open_text_{respondents[0]}", respondents[0])
    go_back(app, "Thematic analysis")
    assert app.text_area(key=phrase_key).value == "Exam"
    assert database_signature(db) == before
