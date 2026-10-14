"""Exercise supplementary controls against a disposable analysis database."""
from io import BytesIO
import json

import pandas as pd

from test_respondent_navigation_ui import database_signature, navigation_database, start_app


def test_prepare_filter_and_download_do_not_change_database(navigation_database):
    db, _, _, _, _ = navigation_database
    before = database_signature(db)
    app = start_app(db, workspace_page="Reports & exports")
    assert not app.exception
    options = app.selectbox(key="report_data_export").options
    assert any("rating distributions" in option.lower() for option in options)
    assert any("active codebook" in option.lower() for option in options)
    app.selectbox(key="supplement_adjustment").select("holm").run()
    app.button(key="supplement_prepare").click().run(timeout=60)
    assert not app.exception
    prepared = app.session_state["supplement_prepared"]
    assert "selected_interpretations.csv" not in prepared["files"]
    manifest = json.loads(prepared["files"]["manifest.json"])
    assert manifest["settings"]["adjustment"] == "holm"
    app.selectbox(key="supplement_file").select("comparisons.csv").run()
    app.selectbox(key="supplement_preview_level").select("construct").run()
    assert not app.exception
    assert app.session_state["supplement_prepared"]["files"] == prepared["files"]
    assert database_signature(db) == before
    app.selectbox(key="supplement_adjustment").select("none").run()
    assert "supplement_prepared" not in app.session_state
    assert database_signature(db) == before


def test_selected_quote_and_current_notes_invalidate_old_bundle(navigation_database):
    db, respondents, _, units, themes = navigation_database
    before = database_signature(db)
    app = start_app(db, workspace_page="Reports & exports")
    evidence_id = f"T{themes[0]}-E{units[0]}"
    app.multiselect(key="supplement_evidence").select(evidence_id).run()
    app.button(key="supplement_prepare").click().run(timeout=60)
    assert not app.exception
    files = app.session_state["supplement_prepared"]["files"]
    table = pd.read_csv(BytesIO(files["selected_interpretations.csv"]))
    assert len(table) == 1
    assert table.iloc[0]["respondent"] == db.respondent_labels()[respondents[0]]
    assert table.iloc[0]["quotation"] == "Example"
    assert database_signature(db) == before
    # Simulate a later analyst edit through the normal database API.
    db.save_theme_evidence(themes[0], units[0], "contextual", "Updated note")
    app.run()
    assert not app.exception
    assert "supplement_prepared" not in app.session_state
