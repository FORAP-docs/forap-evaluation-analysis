import numpy as np
import pandas as pd
import pytest
from scipy import stats

from forap_analysis.schema import BACKGROUND_FIELDS, ITEM_FIELDS
from forap_analysis.statistics import (
    assign_custom_groups,
    corrected_item_total,
    construct_scores,
    construct_summary,
    group_comparison,
    item_summary,
    multi_select_comparison,
    ordinal_correlation,
    tukey_method_name,
)


def sample_frame() -> pd.DataFrame:
    rows = []
    for index in range(12):
        row = {
            "response_id": f"r{index}",
            "institution_type": "University" if index < 6 else "College",
            "years_experience": "6–10" if index % 2 else "11–15",
        }
        for offset, field in enumerate(ITEM_FIELDS):
            row[field.key] = float(3 + ((index + offset) % 3))
        rows.append(row)
    return pd.DataFrame(rows)


def test_descriptive_and_construct_outputs():
    frame = sample_frame()
    items = item_summary(frame)
    constructs = construct_summary(frame)
    scores = construct_scores(frame)
    assert len(items) == len(ITEM_FIELDS)
    assert items["mean"].between(1, 5).all()
    assert constructs["construct"].nunique() == 7
    assert scores.shape[0] == 12


def test_corrected_item_total_correlations_remain_available():
    result = corrected_item_total(sample_frame(), "Clarity")
    clarity_items = [field for field in ITEM_FIELDS if field.construct == "Clarity"]
    assert len(result) == len(clarity_items)
    assert (result["n"] == 12).all()
    assert result["corrected_item_total_r"].notna().all()


def test_group_comparison_is_exploratory_and_bounded():
    result = group_comparison(sample_frame(), "institution_type", "Clarity")
    assert result["test"] == "Welch’s t-test"
    assert 0 <= result["p_value"] <= 1
    assert np.isfinite(result["effect"])
    assert not result["assumptions"].empty
    assert "n" in result["assumptions"]
    assert set(result["assumptions"].loc[result["assumptions"]["group"] != "All groups", "n"]) == {6}


def test_three_groups_use_anova_and_tukey_hsd():
    frame = sample_frame()
    frame["institution_type"] = ["A"] * 4 + ["B"] * 4 + ["C"] * 4
    result = group_comparison(frame, "institution_type", "Clarity")
    assert result["test"] == "One-way ANOVA"
    assert len(result["posthoc"]) == 3
    assert result["posthoc"]["adjusted_p"].between(0, 1).all()
    assert set(result["posthoc"].columns) >= {"n_1", "n_2"}
    assert result["posthoc"][["n_1", "n_2"]].eq(4).all().all()
    assert result["posthoc_method"] == "Tukey HSD"


def test_unequal_groups_label_tukey_kramer_without_changing_calculation():
    frame = sample_frame()
    frame["institution_type"] = ["A"] * 3 + ["B"] * 4 + ["C"] * 5
    result = group_comparison(frame, "institution_type", "clarity_purpose")
    expected = stats.tukey_hsd(*[part["clarity_purpose"].to_numpy() for _, part in frame.groupby("institution_type")])
    assert result["posthoc_method"] == tukey_method_name([3, 4, 5])
    assert "Tukey-Kramer adjustment for unequal group sizes" in result["posthoc_method"]
    assert result["posthoc"].iloc[0]["adjusted_p"] == pytest.approx(expected.pvalue[0, 1])


def test_background_comparison_accepts_an_individual_item():
    frame = sample_frame()
    result = group_comparison(frame, "institution_type", "clarity_purpose")
    assert result["test"] == "Welch’s t-test"
    assert len(result["data"]) == 12


def test_ordered_experience_uses_spearman_correlation():
    frame = sample_frame()
    frame["pjbl_taught"] = [0, 0, 1, 1, 2, 2, 2, 3, 3, 3, 3, 3]
    frame["clarity_purpose"] = frame["pjbl_taught"] + 1
    result = ordinal_correlation(frame, "pjbl_taught", "clarity_purpose")
    assert result["test"] == "Spearman rank correlation"
    assert result["effect_name"] == "Spearman’s ρ"
    assert result["statistic"] > 0.99


def test_years_in_computing_education_uses_ordered_ranks():
    frame = sample_frame()
    frame["years_experience"] = (
        ["Beginner (e.g., <= 5 years)"] * 4
        + ["Intermediate (e.g., 6-10 years)"] * 4
        + ["Experienced (e.g., 11+ years)"] * 4
    )
    frame["clarity_purpose"] = [1] * 4 + [3] * 4 + [5] * 4
    result = ordinal_correlation(frame, "years_experience", "clarity_purpose")
    assert result["test"] == "Spearman rank correlation"
    assert result["statistic"] > 0.99


def test_multi_select_background_uses_selected_vs_not_selected_welch_test():
    frame = sample_frame()
    frame["roles"] = ["Instructor/Teacher"] * 6 + ["Education Researcher"] * 6
    result = multi_select_comparison(frame, "roles", "Instructor/Teacher", "Clarity")
    assert result["test"] == "Welch’s t-test"
    assert set(result["data"]["group"]) == {"Selected", "Not selected"}
    assert result["effect_name"] == "Hedges’ g (Selected vs Not selected)"


def test_multi_select_background_excludes_not_applicable_responses():
    frame = sample_frame()
    frame["roles"] = ["Instructor/Teacher"] * 5 + ["Education Researcher"] * 5 + ["Not applicable"] * 2
    result = multi_select_comparison(frame, "roles", "Instructor/Teacher", "Clarity")
    assert len(result["data"]) == 10
    assert set(result["data"]["group"]) == {"Selected", "Not selected"}


def test_custom_groups_assign_single_category_respondents():
    memberships = pd.Series(
        [("Research university",), ("Teaching-focused",), ("Polytechnic",)]
    )
    assignments = assign_custom_groups(
        memberships,
        {
            "Research university": "Universities",
            "Teaching-focused": "Universities",
            "Polytechnic": "Other institutions",
        },
    )
    assert assignments["group"].tolist() == [
        "Universities",
        "Universities",
        "Other institutions",
    ]
    assert assignments["status"].eq("Assigned").all()


def test_custom_groups_exclude_multiselect_overlap_and_unassigned_values():
    memberships = pd.Series(
        [
            ("Instructor",),
            ("Researcher",),
            ("Instructor", "Researcher"),
            ("Curriculum designer",),
        ]
    )
    assignments = assign_custom_groups(
        memberships,
        {"Instructor": "Teaching", "Researcher": "Research"},
    )
    assert assignments.loc[0, "group"] == "Teaching"
    assert assignments.loc[1, "group"] == "Research"
    assert assignments.loc[2, "status"] == "Overlap"
    assert assignments.loc[3, "status"] == "Unassigned"
    assert pd.isna(assignments.loc[2, "group"])


def test_custom_group_assignments_feed_welch_or_anova_by_group_count():
    frame = sample_frame()
    memberships = pd.Series(
        [("Research",)] * 4 + [("Teaching",)] * 4 + [("Polytechnic",)] * 4,
        index=frame.index,
    )

    two_group_assignments = assign_custom_groups(
        memberships,
        {
            "Research": "Universities",
            "Teaching": "Universities",
            "Polytechnic": "Other institutions",
        },
    )
    two_group_frame = frame.assign(custom_group=two_group_assignments["group"])
    two_group_result = group_comparison(two_group_frame, "custom_group", "Clarity")
    assert two_group_result["test"] == "Welch’s t-test"

    three_group_assignments = assign_custom_groups(
        memberships,
        {
            "Research": "Research universities",
            "Teaching": "Teaching institutions",
            "Polytechnic": "Polytechnics",
        },
    )
    three_group_frame = frame.assign(custom_group=three_group_assignments["group"])
    three_group_result = group_comparison(three_group_frame, "custom_group", "Clarity")
    assert three_group_result["test"] == "One-way ANOVA"
    assert len(three_group_result["posthoc"]) == 3


def test_course_level_preserves_each_selection_and_excludes_not_applicable():
    frame = sample_frame()
    frame["course_levels"] = (
        ["Introductory undergraduate"] * 3
        + ["Introductory undergraduate, Intermediate undergraduate"] * 3
        + ["Advanced undergraduate"] * 3
        + ["Graduate"] * 2
        + ["Not applicable"]
    )
    frame["clarity_purpose"] = [1] * 3 + [2] * 3 + [3] * 3 + [4] * 2 + [5]
    result = multi_select_comparison(frame, "course_levels", "Introductory undergraduate", "clarity_purpose")
    assert result["test"] == "Welch’s t-test"
    assert len(result["data"]) == 11
    assert result["data"]["group"].eq("Selected").sum() == 6
    intermediate = multi_select_comparison(frame, "course_levels", "Intermediate undergraduate", "clarity_purpose")
    assert set(result["data"].index[result["data"]["group"].eq("Selected")]) == set(range(6))
    assert set(intermediate["data"].index[intermediate["data"]["group"].eq("Selected")]) == {3, 4, 5}
    expected = stats.ttest_ind(frame.loc[:5, "clarity_purpose"], frame.loc[6:10, "clarity_purpose"], equal_var=False)
    assert result["p_value"] == pytest.approx(expected.pvalue)
    with pytest.raises(ValueError, match="Multi-select backgrounds require"):
        ordinal_correlation(frame, "course_levels", "clarity_purpose")


def test_construct_requires_half_of_items():
    frame = sample_frame()
    clarity = [field.key for field in ITEM_FIELDS if field.construct == "Clarity"]
    frame.loc[0, clarity[:3]] = np.nan
    scores = construct_scores(frame)
    assert pd.isna(scores.loc[0, "Clarity"])


def test_consent_is_not_a_background_variable():
    assert "consent" not in {field.key for field in BACKGROUND_FIELDS}
