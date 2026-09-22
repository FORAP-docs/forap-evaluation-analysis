import pandas as pd

from app import (
    respondent_construct_sections,
    respondent_rating_context,
    response_background_value,
    response_rating_label,
    working_code_excerpt_catalog,
)
from forap_analysis.database import Database
from forap_analysis.qualitative import corpus_inventory, question_metadata, role_totals
from forap_analysis.schema import FIELD_BY_KEY, ITEM_FIELDS
from forap_analysis.importer import preview_workbook
from test_importer import workbook_bytes


def fully_rated_row(score: float = 4.0) -> pd.Series:
    return pd.Series({field.key: score for field in ITEM_FIELDS})


def test_individual_response_uses_questionnaire_scale_labels():
    assert response_rating_label(FIELD_BY_KEY["clarity_purpose"], 5) == "Strongly Agree"
    assert response_rating_label(FIELD_BY_KEY["instructor_overview"], 3) == "Moderately useful"
    assert response_rating_label(FIELD_BY_KEY["attribute_greenfield"], None) == "Not rated"


def test_individual_response_groups_every_rating_by_construct():
    sections = respondent_construct_sections(fully_rated_row())
    assert [section["construct"] for section in sections] == list(
        dict.fromkeys(field.construct for field in ITEM_FIELDS)
    )
    assert sum(section["total"] for section in sections) == len(ITEM_FIELDS)
    assert all(section["mean"] == 4.0 for section in sections)
    assert all(section["answered"] == section["total"] for section in sections)


def test_individual_response_formats_experience_and_multi_select_background():
    assert response_background_value(FIELD_BY_KEY["pjbl_taught"], 2) == "Moderate"
    assert response_background_value(
        FIELD_BY_KEY["roles"],
        "Instructor/Teacher; Education Researcher",
    ) == "Instructor/Teacher, Education Researcher"


def test_construct_comment_includes_related_item_ratings():
    summary, ratings = respondent_rating_context(fully_rated_row(), "clarity_comments")
    assert summary == "Clarity mean: 4.00/5"
    assert len(ratings) == 5
    assert {label for label, _ in ratings} == {
        field.label for field in ITEM_FIELDS if field.construct == "Clarity"
    }


def test_general_comment_includes_seven_construct_means():
    summary, ratings = respondent_rating_context(fully_rated_row(), "strengths")
    assert summary == "Construct means"
    assert len(ratings) == 7
    assert all(value == 4.0 for _, value in ratings)


def test_question_roles_separate_rating_linked_bridge_and_overall_feedback():
    assert question_metadata("clarity_comments")["role"] == "Rating-linked"
    assert question_metadata("missing_components")["role"] == "Bridge"
    assert question_metadata("strengths")["role"] == "Overall feedback"


def test_working_code_excerpt_catalog_returns_unique_selected_excerpts_with_all_codes():
    codings = pd.DataFrame(
        [
            {
                "id": 1,
                "meaning_unit_id": 10,
                "response_id": "response-a",
                "question_key": "strengths",
                "code_id": 3,
                "code_name": "Project reuse and adaptation",
                "excerpt": "A reusable project package.",
                "note": "Reuse is stated directly.",
            },
            {
                "id": 2,
                "meaning_unit_id": 10,
                "response_id": "response-a",
                "question_key": "strengths",
                "code_id": 1,
                "code_name": "Consistent project packaging",
                "excerpt": "A reusable project package.",
                "note": "Reuse is stated directly.",
            },
            {
                "id": 3,
                "meaning_unit_id": 11,
                "response_id": "response-b",
                "question_key": "weaknesses",
                "code_id": 1,
                "code_name": "Consistent project packaging",
                "excerpt": "Packaging alone is not enough.",
                "note": "A boundary of packaging.",
            },
        ]
    )

    catalog = working_code_excerpt_catalog(
        codings,
        3,
        {"response-a": "R1", "response-b": "R2"},
    )

    assert len(catalog) == 1
    assert catalog.iloc[0]["Respondent"] == "R1"
    assert catalog.iloc[0]["Question"] == FIELD_BY_KEY["strengths"].label
    assert catalog.iloc[0]["excerpt"] == "A reusable project package."
    assert catalog.iloc[0]["code_names"] == (
        "Project reuse and adaptation | Consistent project packaging"
    )


def test_corpus_inventory_covers_every_open_text_prompt(tmp_path):
    database = Database(tmp_path / "test.sqlite3")
    database.activate_import(preview_workbook(workbook_bytes(), "responses.xlsx"))
    inventory = corpus_inventory(database.active_data(), database)
    assert len(inventory) == 11
    assert inventory["Non-empty responses"].ge(0).all()
    assert inventory["Coverage"].between(0, 1).all()
    assert set(inventory["Analysis role"]) == {"Rating-linked", "Bridge", "Overall feedback"}
    totals = role_totals(database.active_data())
    assert totals["rating_linked_respondents"] >= 0
    assert totals["overall_feedback_respondents"] >= 0
