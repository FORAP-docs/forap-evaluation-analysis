"""Public examples exercise the same import path as uploaded workbooks."""

from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from forap_analysis.database import Database
from forap_analysis.importer import preview_workbook
from forap_analysis.schema import CONSTRUCTS, FIELDS, ITEM_FIELDS
from forap_analysis.statistics import construct_scores, item_summary
from test_respondent_navigation_ui import navigation_app


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_synthetic_example_import_and_analysis(tmp_path):
    path = EXAMPLES / "synthetic_responses.xlsx"
    preview = preview_workbook(path.read_bytes(), path.name)
    assert preview.valid
    assert not preview.warnings
    assert len(preview.frame) == 12
    assert len(preview.mapping) == len(FIELDS) - 1
    assert "followup_email" not in preview.frame
    assert preview.frame["response_id"].nunique() == 12
    database = Database(tmp_path / "synthetic.sqlite3")
    result = database.activate_import(preview)
    assert result["inserted"] == 12
    frame = database.active_data()
    assert len(item_summary(frame)) == len(ITEM_FIELDS)
    scores = construct_scores(frame)
    assert scores[list(CONSTRUCTS)].notna().all().all()
    assert scores[list(CONSTRUCTS)].ge(1).all().all()
    assert scores[list(CONSTRUCTS)].le(5).all().all()


def test_blank_template_has_required_headers_without_participant_rows():
    path = EXAMPLES / "response_template.xlsx"
    frame = pd.read_excel(path)
    assert frame.empty
    assert frame.columns.tolist() == [field.key for field in FIELDS if not field.pii]
    preview = preview_workbook(path.read_bytes(), path.name)
    assert preview.valid
    assert preview.frame.empty
    assert preview.warnings == ["The workbook contains headers but no responses."]


@pytest.mark.parametrize("page", [
    "Overview", "Individual responses", "Items & scales", "Background comparisons",
    "Thematic analysis", "Mixed methods", "Reports & exports", "Upload & data health",
])
def test_example_opens_each_workspace_without_study_coding(tmp_path, page):
    path = EXAMPLES / "synthetic_responses.xlsx"
    database = Database(tmp_path / "example-ui.sqlite3")
    database.activate_import(preview_workbook(path.read_bytes(), path.name))
    app = AppTest.from_function(navigation_app, args=(str(database.path),))
    app.session_state["workspace_page"] = page
    app.run(timeout=20)
    assert not app.exception
