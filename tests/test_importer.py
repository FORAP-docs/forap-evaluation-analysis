from io import BytesIO
from hashlib import sha256

import pandas as pd

from forap_analysis.importer import preview_workbook
from forap_analysis.schema import FIELDS, FIELD_BY_KEY


def workbook_bytes(rows: int = 2) -> bytes:
    values = {}
    for field in FIELDS:
        if field.key == "timestamp":
            values[field.match] = [f"2026-01-0{index + 1} 10:00:00" for index in range(rows)]
        elif field.scale == "agreement":
            values[field.match] = ["Agree"] * rows
        elif field.scale == "usefulness":
            values[field.match] = ["Very useful"] * rows
        elif field.scale == "effectiveness":
            values[field.match] = ["Very effective"] * rows
        elif field.scale == "experience":
            values[field.match] = ["Moderate"] * rows
        elif field.key == "followup_email":
            values[field.match] = ["person@example.edu"] * rows
        else:
            values[field.match] = ["Example"] * rows
    buffer = BytesIO()
    pd.DataFrame(values).to_excel(buffer, index=False)
    return buffer.getvalue()


def test_preview_maps_and_scores_all_fields():
    contents = workbook_bytes()
    preview = preview_workbook(contents, "responses.xlsx")
    assert preview.valid
    assert preview.source_file_hash == sha256(contents).hexdigest()
    assert preview.file_hash != preview.source_file_hash
    assert len(preview.mapping) == 57
    assert len(preview.frame) == 2
    assert preview.frame["clarity_purpose"].tolist() == [4.0, 4.0]
    assert preview.frame["instructor_overview"].tolist() == [4.0, 4.0]
    assert preview.frame["attribute_duration"].tolist() == [4.0, 4.0]
    assert preview.frame["pjbl_taught"].tolist() == [2.0, 2.0]
    assert preview.frame["response_id"].nunique() == 2


def test_preview_rejects_missing_questionnaire_column():
    contents = workbook_bytes()
    raw = pd.read_excel(BytesIO(contents)).drop(columns=[FIELDS[20].match])
    buffer = BytesIO()
    raw.to_excel(buffer, index=False)
    preview = preview_workbook(buffer.getvalue(), "broken.xlsx")
    assert not preview.valid
    assert "complete_reusable" in preview.missing_fields


def test_preview_preserves_none_as_an_experience_response():
    raw = pd.read_excel(BytesIO(workbook_bytes(1)), keep_default_na=False)
    column = FIELD_BY_KEY["pjbl_researched"].match
    raw.loc[0, column] = "None"
    buffer = BytesIO()
    raw.to_excel(buffer, index=False)

    preview = preview_workbook(buffer.getvalue(), "responses.xlsx")

    assert preview.valid
    assert preview.frame.loc[0, "pjbl_researched"] == 0.0
