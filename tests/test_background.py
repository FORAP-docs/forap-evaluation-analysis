import pandas as pd

from app import background_analysis_specs, background_frequency, custom_background_memberships
from forap_analysis.statistics import assign_custom_groups
from forap_analysis.schema import BACKGROUND_FIELDS, FIELD_BY_KEY


def test_multi_select_background_frequency_expands_all_options():
    frame = pd.DataFrame({"roles": ["Instructor, Researcher", "Instructor", None]})
    counts = background_frequency(frame, FIELD_BY_KEY["roles"]).set_index("category")["responses"]
    assert counts["Instructor"] == 2
    assert counts["Researcher"] == 1
    assert counts["Missing"] == 1


def test_experience_frequency_uses_readable_labels():
    frame = pd.DataFrame({"pjbl_taught": [3.0, 2.0, 3.0, None]})
    counts = background_frequency(frame, FIELD_BY_KEY["pjbl_taught"])
    assert set(counts["category"]) == {
        "None",
        "Limited",
        "Moderate",
        "Extensive",
        "Missing",
    }


def test_experience_frequency_includes_unobserved_options_with_zero_counts():
    frame = pd.DataFrame({"pjbl_taught": [3.0, 2.0, 3.0]})
    counts = background_frequency(frame, FIELD_BY_KEY["pjbl_taught"]).set_index("category")
    assert set(counts.index) == {"None", "Limited", "Moderate", "Extensive"}
    assert counts.loc["None", "responses"] == 0
    assert counts.loc["Limited", "responses"] == 0


def test_course_level_has_separate_multi_select_background_analyses():
    frame = pd.DataFrame(
        {
            field.key: [None]
            for field in BACKGROUND_FIELDS
        }
    )
    frame["course_levels"] = ["Introductory undergraduate, Intermediate undergraduate"]
    specs = [spec for spec in background_analysis_specs(frame) if spec["field"].key == "course_levels"]
    assert len(specs) == 2
    assert {spec["analysis_type"] for spec in specs} == {"multi"}
    assert {spec["category"] for spec in specs} == {
        "Introductory undergraduate", "Intermediate undergraduate",
    }


def test_course_custom_groups_keep_all_selections_and_existing_display_labels():
    frame = pd.DataFrame({"course_levels": [
        "Introductory undergraduate, Graduate", "Graduate",
        "Introductory undergraduate, Intermediate undergraduate", "Not applicable", None,
    ]})
    memberships, _ = custom_background_memberships(frame, FIELD_BY_KEY["course_levels"])
    assert memberships.tolist() == [
        ("Introductory", "Graduate"), ("Graduate",),
        ("Introductory", "Intermediate"), (), (),
    ]
    assignments = assign_custom_groups(memberships, {
        "Introductory": "Lower", "Intermediate": "Lower", "Graduate": "Higher",
    })
    assert assignments["status"].tolist() == ["Overlap", "Assigned", "Assigned", "Unassigned", "Unassigned"]
    assert assignments["group"].fillna("Excluded").tolist() == ["Excluded", "Higher", "Lower", "Excluded", "Excluded"]


def test_role_and_area_use_individual_multi_select_comparisons():
    frame = pd.DataFrame({field.key: [None] for field in BACKGROUND_FIELDS})
    frame["roles"] = ["Instructor/Teacher, Education Researcher"]
    frame["computing_areas"] = ["Software Engineering"]
    specs = background_analysis_specs(frame)
    role_specs = [spec for spec in specs if spec["field"].key == "roles"]
    area_specs = [spec for spec in specs if spec["field"].key == "computing_areas"]
    assert {spec["category"] for spec in role_specs} == {
        "Instructor/Teacher",
        "Education Researcher",
    }
    assert {spec["analysis_type"] for spec in role_specs} == {"multi"}
    assert {spec["category"] for spec in area_specs} == {"Software Engineering"}
