"""Numerical completeness, export scope, and privacy boundaries."""
from io import BytesIO
import json
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from forap_analysis.comparisons import background_analysis_specs, run_background_analysis
from forap_analysis.exports import (
    active_codebook, adjust_catalog, build_bundle, comparison_inventory, holm_adjust,
    interpretation_table, rating_distributions, response_coverage, zip_bundle,
)
from forap_analysis.schema import BACKGROUND_FIELDS, CONSTRUCTS, FIELD_BY_KEY, ITEM_FIELDS, OPEN_TEXT_FIELDS


@pytest.fixture
def export_frame():
    rows = []
    for i in range(12):
        row = {f.key: None for f in BACKGROUND_FIELDS}
        row.update({
            "response_id": f"PRIVATE-ID-{i}", "followup_email": "PRIVATE-EMAIL@example.test",
            "timestamp": "PRIVATE-TIMESTAMP", "strengths": "PRIVATE-FREE-TEXT",
            "institution_type": ["A", "B", "C"][i // 4],
            "years_experience": ["Beginner (e.g., <= 5 years)", "Intermediate (e.g., 6-10 years)", "Experienced (e.g., 11+ years)"][i // 4],
            "roles": "Instructor/Teacher" if i < 6 else "Education Researcher",
            "course_levels": "Graduate", "computing_areas": "Software Engineering",
        })
        for field in BACKGROUND_FIELDS:
            if field.scale == "experience":
                row[field.key] = i % 4
        for j, field in enumerate(ITEM_FIELDS):
            row[field.key] = 1 + (i + j) % 5
        rows.append(row)
    return pd.DataFrame(rows)


def test_holm_known_values_missing_ties_and_preserved_order():
    raw = pd.Series([.04, np.nan, .01, .03, .01], index=[7, 6, 5, 4, 3])
    adjusted = holm_adjust(raw)
    assert adjusted.index.equals(raw.index)
    np.testing.assert_allclose(adjusted, [.06, np.nan, .04, .06, .04], equal_nan=True)
    assert holm_adjust(pd.Series([np.nan])).isna().all()
    with pytest.raises(ValueError):
        holm_adjust(pd.Series([1.1]))


def test_family_definition_does_not_depend_on_display_filter():
    raw = pd.DataFrame({"outcome_level": ["item", "item", "construct", "construct"], "raw_p": [.01, .04, .03, np.nan]})
    result = adjust_catalog(raw, "holm")
    assert result["family_size"].eq(3).all()
    assert result.loc[2, "holm_adjusted_p"] == pytest.approx(.06)
    filtered = result[result["outcome_level"].eq("construct")]
    assert filtered.iloc[0]["holm_adjusted_p"] == pytest.approx(.06)
    split = adjust_catalog(raw, "holm", "by_outcome_level")
    assert split.loc[2, "holm_adjusted_p"] == pytest.approx(.03)
    pd.testing.assert_series_equal(raw["raw_p"], result["raw_p"])
    assert adjust_catalog(raw)["holm_adjusted_p"].isna().all()


def test_distribution_denominators_labels_empty_and_absent_items(export_frame):
    frame = export_frame.copy()
    frame.loc[0, "use_adapt"] = np.nan
    frame["clarity_purpose"] = np.nan
    frame = frame.drop(columns=["assessment_rubric"])
    result = rating_distributions(frame)
    assert len(result) == 33 * 5
    adaptation = result[result["key"].eq("use_adapt")]
    assert adaptation["count"].sum() == 11
    assert adaptation["valid_n"].eq(11).all()
    assert adaptation["missing_n"].eq(1).all()
    assert adaptation["percent"].sum() == pytest.approx(100)
    assert adaptation.iloc[-1]["response_label"] == "Strongly Agree"
    assert result[result["key"].eq("instructor_notes")].iloc[-1]["response_label"] == "Extremely useful"
    assert result[result["key"].eq("attribute_domain")].iloc[-1]["response_label"] == "Extremely effective"
    assert result[result["key"].isin(["clarity_purpose", "assessment_rubric"])]["percent"].isna().all()


def test_coverage_uses_nonblank_responses_and_all_respondents():
    frame = pd.DataFrame({"strengths": ["One", "  ", None, "Two"], "weaknesses": ["Three", None, "Four", ""]})
    coverage = response_coverage(frame)
    assert len(coverage) == 11
    assert coverage["nonblank_responses"].sum() == 4
    assert coverage.loc[coverage["question_key"].eq("strengths"), "percent_of_all_respondents"].item() == 50


def test_inventory_keeps_all_candidates_and_all_tukey_pairs(export_frame):
    frame = export_frame.copy()
    # This produces a candidate with only one group and cannot be tested.
    frame["pjbl_taught"] = 1
    inventory = comparison_inventory(frame)
    catalog = inventory["comparisons"]
    assert len(catalog) == len(background_analysis_specs(frame)) * (len(CONSTRUCTS) + len(ITEM_FIELDS))
    assert catalog["test_id"].is_unique
    unavailable = catalog[catalog["predictor"].eq("pjbl_taught")]
    assert unavailable["status"].eq("Not estimable").all()
    assert unavailable["warning"].str.len().gt(0).all()
    assert catalog["raw_p"].ge(.05).any()
    target = catalog[catalog["predictor"].eq("institution_type") & catalog["outcome"].eq("use_adapt")].iloc[0]
    expected = run_background_analysis(frame, FIELD_BY_KEY["institution_type"], "use_adapt", "nominal", None)
    assert target["raw_p"] == pytest.approx(expected["p_value"])
    pairs = inventory["tukey_pairs"].query("test_id == @target.test_id")
    assert len(pairs) == 3
    np.testing.assert_allclose(pairs["tukey_adjusted_p"], expected["posthoc"]["adjusted_p"])
    assert target["df_1"] == 2
    assert target["df_2"] == 9
    assert "response_id" not in catalog


def test_excluded_small_group_and_welch_direction(export_frame):
    frame = export_frame.copy()
    frame["institution_type"] = ["Z"] * 7 + ["A"] * 4 + ["Tiny"]
    inventory = comparison_inventory(frame)
    target = inventory["comparisons"].query("predictor == 'institution_type' and outcome == 'use_adapt'").iloc[0]
    assert target["included_n"] == 11
    assert target["excluded_n"] == 1
    assert target["effect_direction"] == "A minus Z"
    a = frame.loc[frame["institution_type"].eq("A"), "use_adapt"]
    z = frame.loc[frame["institution_type"].eq("Z"), "use_adapt"]
    expected = stats.ttest_ind(a, z, equal_var=False)
    assert target["raw_p"] == pytest.approx(expected.pvalue)
    assert target["df_1"] == pytest.approx(expected.df)
    assert target["mean_difference_ci95_low"] == pytest.approx(expected.confidence_interval().low)
    assert target["mean_difference_ci95_high"] == pytest.approx(expected.confidence_interval().high)
    groups = inventory["comparison_groups"]
    tiny = groups[groups["test_id"].eq(target["test_id"]) & groups["group"].eq("Tiny")].iloc[0]
    assert not tiny["included"]
    assert tiny["valid_n"] == 1
    assert tiny["exclusion_reason"]


def test_active_codebook_and_interpretation_preserve_source_and_label():
    codes = pd.DataFrame([{"id": 1, "name": "Active", "is_active": 1}, {"id": 2, "name": "Archived", "is_active": 0}])
    themes = pd.DataFrame([{"name": "Theme", "code_ids": "1,2"}])
    codebook = active_codebook(codes, themes)
    assert codebook["name"].tolist() == ["Active"]
    assert codebook["theme_uses"].tolist() == ["Theme"]
    evidence = pd.DataFrame([
        {"theme_id": 1, "meaning_unit_id": i, "response_id": rid, "question_key": "clarity_comments",
         "excerpt": "Exact quotation.  Two spaces.", "theme_name": "Theme", "evidence_role": "contextual",
         "unit_note": "Existing interpretation", "evidence_note": "Qualification"}
        for i, rid in enumerate(["original", "inactive"])
    ])
    result = interpretation_table(evidence, {"original": "R19", "inactive": "R3"}, {"original"})
    assert len(result) == 1
    assert result.iloc[0]["respondent"] == "R19"
    assert result.iloc[0]["quotation"] == "Exact quotation.  Two spaces."
    assert result.iloc[0]["descriptive_meaning"] == ""
    assert result.iloc[0]["alternative_explanation"] == ""
    assert "response_id" not in result


def test_bundle_is_separate_files_with_allowlist_no_raw_data(export_frame):
    inventory = comparison_inventory(export_frame)
    inventory["private_responses"] = export_frame
    codes = pd.DataFrame([{"id": 1, "name": "Code", "is_active": 1, "unexpected_secret": "PRIVATE-CODE-FIELD"}])
    themes = pd.DataFrame([{"id": 1, "name": "Theme", "status": "candidate", "unexpected_secret": "PRIVATE-THEME-FIELD"}])
    files = build_bundle(export_frame, codes, themes, inventory, pd.DataFrame(), method="holm")
    contents = b"\n".join(files.values()).decode("utf-8-sig")
    for sentinel in ["PRIVATE-ID-", "PRIVATE-EMAIL", "PRIVATE-TIMESTAMP", "PRIVATE-FREE-TEXT", "PRIVATE-CODE-FIELD", "PRIVATE-THEME-FIELD"]:
        assert sentinel not in contents
    assert "selected_interpretations.csv" not in files
    assert "README.md" in files and "manifest.json" in files
    assert not any(name.endswith(".pdf") for name in files)
    manifest = json.loads(files["manifest.json"])
    assert manifest["settings"]["adjustment"] == "holm"
    assert manifest["respondents_with_written_feedback"] == 12
    catalog = pd.read_csv(BytesIO(files["comparisons.csv"]))
    assert manifest["families"][0]["estimable_tests"] == catalog["raw_p"].notna().sum()
    with ZipFile(BytesIO(zip_bundle(files))) as zipped:
        assert set(zipped.namelist()) == set(files)
        for name in files:
            assert zipped.read(name) == files[name]


def test_empty_codebook_and_empty_coverage_have_headers():
    assert "name" in active_codebook(pd.DataFrame())
    assert len(rating_distributions(pd.DataFrame())) == 165
    assert response_coverage(pd.DataFrame())["nonblank_responses"].sum() == 0
