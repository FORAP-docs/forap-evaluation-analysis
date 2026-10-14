"""Read-only reporting outputs. No database writes or participant-data bundles."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import platform
import warnings
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
import pandas as pd
import scipy

from . import __version__
from .charts import SCALE_LABELS
from .comparisons import background_analysis_specs, run_background_analysis
from .schema import BACKGROUND_FIELDS, CONSTRUCTS, FIELD_BY_KEY, ITEM_FIELDS, OPEN_TEXT_FIELDS
from .statistics import construct_summary, item_summary, likert_distribution, YEARS_EXPERIENCE_RANKS

EXPORT_VERSION = "1.0"
FAMILY_OPTIONS = {
    "all_main_tests": "All item and construct tests together",
    "by_outcome_level": "Separate families for item tests and construct tests",
}
CODE_COLUMNS = [
    "id", "name", "description", "inclusion_criteria", "exclusion_criteria",
    "domain", "code_type", "parent_name", "version_label", "is_active",
]
THEME_COLUMNS = [
    "id", "name", "description", "status", "linked_constructs_json", "implication",
    "contrasting_evidence", "codes",
]
INTERPRETATION_COLUMNS = [
    "evidence_id", "respondent", "source_question", "quotation", "code_names",
    "theme", "evidence_role", "existing_unit_note", "existing_theme_note",
    "descriptive_meaning", "theme_interpretation", "alternative_explanation", "proposed_change",
]


def csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8-sig")


def frame_digest(frame: pd.DataFrame) -> str:
    return hashlib.sha256(frame.to_json(orient="split", date_format="iso").encode()).hexdigest()


def analysis_digest(frame: pd.DataFrame) -> str:
    # No emails, timestamps, free text, or raw respondent IDs in the fingerprint input.
    columns = [f.key for f in (*BACKGROUND_FIELDS, *ITEM_FIELDS)]
    return frame_digest(frame.reindex(columns=columns).reset_index(drop=True))


def implementation_digest() -> str:
    """Identify the exact calculation code, including uncommitted local changes."""
    root = Path(__file__).parent
    digest = hashlib.sha256()
    for name in ("exports.py", "comparisons.py", "statistics.py", "schema.py", "charts.py"):
        digest.update(name.encode())
        digest.update((root / name).read_bytes())
    return digest.hexdigest()


def rating_distributions(frame: pd.DataFrame) -> pd.DataFrame:
    summaries = item_summary(frame).set_index("key")
    rows = []
    for construct in CONSTRUCTS:
        # Reuse the dashboard calculation, including empty/missing item columns.
        complete = frame.reindex(columns=[f.key for f in ITEM_FIELDS])
        distribution = likert_distribution(complete, construct)
        for row in distribution.to_dict("records"):
            field = FIELD_BY_KEY[row["key"]]
            summary = summaries.loc[field.key]
            rows.append({
                **row, "construct": construct, "scale": field.scale,
                "response_label": SCALE_LABELS[field.scale][row["score"]],
                "valid_n": int(summary["n"]), "missing_n": int(summary["missing"]),
                "total_n": len(frame),
                # Undefined percentage when there are no valid responses.
                "percent": row["percent"] if summary["n"] else np.nan,
            })
    return pd.DataFrame(rows)


def response_coverage(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for field in OPEN_TEXT_FIELDS:
        values = frame.get(field.key, pd.Series(index=frame.index, dtype=object))
        nonblank = values.fillna("").astype(str).str.strip().ne("")
        n = int(nonblank.sum())
        rows.append({"question_key": field.key, "question": field.label,
                     "nonblank_responses": n, "total_respondents": len(frame),
                     "percent_of_all_respondents": 100 * n / len(frame) if len(frame) else np.nan})
    return pd.DataFrame(rows)


def active_codebook(codes: pd.DataFrame, themes: pd.DataFrame | None = None) -> pd.DataFrame:
    selected = codes.loc[codes["is_active"].eq(1)] if "is_active" in codes else codes.iloc[:0]
    result = selected.reindex(columns=CODE_COLUMNS).copy()
    uses: dict[int, list[str]] = {}
    if themes is not None:
        for row in themes.to_dict("records"):
            for code_id in str(row.get("code_ids") or "").split(","):
                if code_id.strip().isdigit():
                    uses.setdefault(int(code_id), []).append(str(row["name"]))
    result["theme_uses"] = result["id"].map(lambda code_id: " | ".join(uses.get(int(code_id), [])))
    result["export_status"] = "Active working code, not automatically finalized"
    return result


def interpretation_table(evidence: pd.DataFrame, labels: dict[str, str], active_ids: set[str]) -> pd.DataFrame:
    """Prepare a worksheet, leaving new interpretations to the analyst."""
    rows = []
    for row in evidence.to_dict("records"):
        response_id = str(row["response_id"])
        if response_id not in active_ids:
            continue
        if response_id not in labels:
            raise ValueError("An evidence row has no stable respondent label.")
        key = row["question_key"]
        rows.append({
            "evidence_id": f"T{row['theme_id']}-E{row['meaning_unit_id']}",
            "respondent": labels[response_id],
            "source_question": FIELD_BY_KEY[key].label if key in FIELD_BY_KEY else key,
            "quotation": row["excerpt"], "code_names": row.get("code_names", ""),
            "theme": row["theme_name"], "evidence_role": row["evidence_role"],
            "existing_unit_note": row.get("unit_note", ""),
            "existing_theme_note": row.get("evidence_note", ""),
            "descriptive_meaning": "", "theme_interpretation": "",
            "alternative_explanation": "", "proposed_change": "",
        })
    return pd.DataFrame(rows, columns=INTERPRETATION_COLUMNS)


def holm_adjust(p_values: pd.Series) -> pd.Series:
    """Holm step-down adjustment across finite p-values in a fixed family."""
    values = pd.to_numeric(p_values, errors="coerce").to_numpy(dtype=float)
    finite = np.isfinite(values)
    if ((values[finite] < 0) | (values[finite] > 1)).any():
        raise ValueError("P-values must be between zero and one.")
    positions = np.flatnonzero(finite)
    ordered = positions[np.argsort(values[positions], kind="stable")]
    adjusted = np.full(len(values), np.nan)
    adjusted[ordered] = np.minimum(1, np.maximum.accumulate(values[ordered] * np.arange(len(ordered), 0, -1)))
    return pd.Series(adjusted, index=p_values.index)


def adjust_catalog(catalog: pd.DataFrame, method: str = "none", family: str = "all_main_tests") -> pd.DataFrame:
    if method not in {"none", "holm"} or family not in FAMILY_OPTIONS:
        raise ValueError("Unknown adjustment method or family definition.")
    result = catalog.copy()
    result["family_id"] = result["outcome_level"] if family == "by_outcome_level" else "all_main_tests"
    result["adjustment_method"] = method
    result["family_size"] = 0
    result["holm_adjusted_p"] = np.nan
    for _, group in result.groupby("family_id", sort=False):
        valid = np.isfinite(pd.to_numeric(group["raw_p"], errors="coerce"))
        result.loc[group.index, "family_size"] = int(valid.sum())
        if method == "holm":
            result.loc[group.index, "holm_adjusted_p"] = holm_adjust(group["raw_p"])
    return result


def comparison_inventory(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Current mapped standard comparisons, never a historical execution log.

    Custom groupings and mixed-method code/theme comparisons are not this family.
    Every defined candidate remains present, including non-estimable candidates.
    """
    outcomes = [(c, c, "construct") for c in CONSTRUCTS] + [(f.key, f.label, "item") for f in ITEM_FIELDS]
    rows, groups, pairs, assumptions = [], [], [], []
    specs = background_analysis_specs(frame)
    spec_rows = [{"predictor": s["field"].key, "analysis_type": s["analysis_type"],
                  "category": s["category"] or "", "label": s["label"]} for s in specs]
    for spec in specs:
        field = spec["field"]
        for outcome, label, level in outcomes:
            identity = [field.key, spec["analysis_type"], spec["category"], level, outcome]
            test_id = "test_" + hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:20]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                result = run_background_analysis(frame, field, outcome, str(spec["analysis_type"]), spec["category"])
            data = result["data"]
            finite_p = bool(np.isfinite(result["p_value"]))
            included = set(data["group"].dropna())
            group_data = []
            for record in result["counts"].to_dict("records"):
                name, n = record["group"], int(record["n"])
                values = data.loc[data["group"].eq(name), "score"]
                is_included = name in included
                group_data.append((name, values))
                groups.append({"test_id": test_id, "group": str(name), "valid_n": n,
                               "included": is_included, "mean": values.mean() if is_included else np.nan,
                               "sd": values.std(ddof=1) if len(values) > 1 else np.nan,
                               "exclusion_reason": "" if is_included else "Fewer than two valid responses"})
            valid_groups = [(name, values) for name, values in group_data if len(values)]
            df1, df2, mean_difference, ci_low, ci_high = (np.nan,) * 5
            direction = "Higher ordered background level versus higher outcome" if spec["analysis_type"] == "ordinal" else ""
            if result["test"] == "Welch’s t-test" and len(valid_groups) == 2:
                (name_a, a), (name_b, b) = valid_groups
                # Counts are sorted by N, but g follows the order in result['data'].
                ordered = [(name, part["score"]) for name, part in data.groupby("group", observed=True)]
                (name_a, a), (name_b, b) = ordered
                direction = f"{name_a} minus {name_b}"
                mean_difference = float(a.mean() - b.mean())
                va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
                denominator = va**2 / (len(a) - 1) + vb**2 / (len(b) - 1)
                if denominator > 0:
                    df1 = (va + vb)**2 / denominator
                    margin = scipy.stats.t.ppf(.975, df1) * math.sqrt(va + vb)
                    ci_low, ci_high = mean_difference - margin, mean_difference + margin
            elif result["test"] == "One-way ANOVA":
                df1, df2 = len(included) - 1, len(data) - len(included)
            warning = result["warning"]
            if not finite_p and not warning:
                warning = "P-value is undefined for these data (for example, constant values)."
            scale = FIELD_BY_KEY[outcome].scale if level == "item" else next(f.scale for f in ITEM_FIELDS if f.construct == outcome)
            rows.append({
                "test_id": test_id, "predictor": field.key, "predictor_label": field.label,
                "analysis_type": spec["analysis_type"], "category": spec["category"] or "",
                "outcome": outcome, "outcome_label": label, "outcome_level": level, "response_scale": scale,
                "total_n": len(frame), "included_n": len(data), "excluded_n": len(frame) - len(data),
                "test": result["test"] or "Not estimable", "statistic": result["statistic"],
                "df_1": df1, "df_2": df2, "raw_p": result["p_value"],
                "effect": result["effect"], "effect_measure": result["effect_name"] or "",
                "effect_direction": direction, "mean_difference": mean_difference,
                "mean_difference_ci95_low": ci_low, "mean_difference_ci95_high": ci_high,
                "status": "Estimable" if finite_p else "Not estimable", "warning": warning,
                "reported_in_paper": "Not recorded", "selection_reason": "Not recorded",
            })
            for pair in result["posthoc"].to_dict("records"):
                pairs.append({"test_id": test_id, **{k: v for k, v in pair.items() if k != "adjusted_p"},
                              "tukey_adjusted_p": pair["adjusted_p"], "method": result["posthoc_method"],
                              "omnibus_raw_p": result["p_value"],
                              "omnibus_raw_p_below_05": finite_p and result["p_value"] < .05})
            for assumption in result["assumptions"].to_dict("records"):
                assumptions.append({"test_id": test_id, **assumption})
    return {
        "comparisons": pd.DataFrame(rows),
        "comparison_groups": pd.DataFrame(groups, columns=["test_id", "group", "valid_n", "included", "mean", "sd", "exclusion_reason"]),
        "tukey_pairs": pd.DataFrame(pairs, columns=["test_id", "group_1", "group_2", "n_1", "n_2", "mean_difference", "ci95_low", "ci95_high", "different_at_0.05", "tukey_adjusted_p", "method", "omnibus_raw_p", "omnibus_raw_p_below_05"]),
        "assumption_checks": pd.DataFrame(assumptions, columns=["test_id", "check", "group", "n", "statistic", "p_value"]),
        "comparison_definitions": pd.DataFrame(spec_rows),
    }


def build_bundle(
    frame: pd.DataFrame, codes: pd.DataFrame, themes: pd.DataFrame,
    inventory: dict[str, pd.DataFrame], mappings: pd.DataFrame,
    *, method: str = "none", family: str = "all_main_tests",
    selected_interpretations: pd.DataFrame | None = None,
) -> dict[str, bytes]:
    """Explicit file list. Existing private exports are never swept into a bundle."""
    catalog = adjust_catalog(inventory["comparisons"], method, family)
    tables = {
        "item_statistics.csv": item_summary(frame),
        "construct_statistics.csv": construct_summary(frame),
        "rating_distributions.csv": rating_distributions(frame),
        "written_response_coverage.csv": response_coverage(frame),
        "active_codebook.csv": active_codebook(codes, themes),
        "theme_documentation.csv": themes.reindex(columns=THEME_COLUMNS),
        "comparisons.csv": catalog,
        **{f"{name}.csv": inventory[name] for name in ("comparison_groups", "tukey_pairs", "assumption_checks", "comparison_definitions")},
    }
    if selected_interpretations is not None and not selected_interpretations.empty:
        tables["selected_interpretations.csv"] = selected_interpretations.reindex(columns=INTERPRETATION_COLUMNS)
    files = {name: csv_bytes(table) for name, table in tables.items()}
    mapping_records = mappings.reindex(columns=["field_key", "source_value", "canonical_value"]).fillna("").to_dict("records")
    written = frame.reindex(columns=[f.key for f in OPEN_TEXT_FIELDS]).fillna("").astype(str)
    unique_writers = int(written.apply(lambda col: col.str.strip().ne("")).any(axis=1).sum())
    config = {
        "export_schema_version": EXPORT_VERSION, "app_version": __version__,
        "implementation_sha256": implementation_digest(), "analysis_input_sha256": analysis_digest(frame),
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "provenance": "Fresh calculation from the current active data and mappings, not a historical execution record",
        "release_status": "Draft for author review, not uploaded or automatically approved for publication",
        "runtime": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__, "scipy": scipy.__version__},
        "respondents": len(frame), "respondents_with_written_feedback": unique_writers,
        "written_responses": int(response_coverage(frame)["nonblank_responses"].sum()),
        "category_mapping_sha256": hashlib.sha256(json.dumps(mapping_records, sort_keys=True).encode()).hexdigest(),
        "category_mappings": mapping_records,
        "years_experience_ranks": YEARS_EXPERIENCE_RANKS,
        "settings": {"minimum_group_n": 2, "construct_minimum_item_fraction": .5,
                     "multi_select": "Selected versus not selected among respondents with an applicable selection",
                     "ordered_predictors": "Spearman rank correlation", "two_groups": "Two-sided Welch t-test",
                     "three_or_more_groups": "One-way ANOVA with all computed Tukey pairs",
                     "adjustment": method, "family_definition": family, "adjustment_status": "Optional retrospective sensitivity analysis" if method == "holm" else "No across-test adjustment",
                     "custom_groupings_included": False, "mixed_methods_tests_included": False},
        "families": [{"id": str(name), "candidate_tests": len(group), "estimable_tests": int(group["raw_p"].map(np.isfinite).sum())} for name, group in catalog.groupby("family_id")],
        "files": [{"name": name, "rows": len(tables[name]), "sha256": hashlib.sha256(content).hexdigest()} for name, content in files.items()],
    }
    files["manifest.json"] = (json.dumps(config, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    listing = "\n".join(f"- `{name}`: {len(table)} rows." for name, table in tables.items())
    files["README.md"] = f"""# FORAP analysis exports

Draft generated {config['exported_at_utc']}. Files are UTF-8 CSV, Markdown, and JSON. No PDF is generated.
Each file can be used separately. The ZIP is only a convenient download container.

## Contents

{listing}
- `manifest.json`: versions, exact settings, current category mappings, file hashes, and analysis fingerprint.

## Reading the results

Rating percentages use each item's valid N. Missing responses are shown separately. Empty items have undefined percentages.
Top-two percentages are scores 4 and 5. Their meaning depends on the response scale, whose labels are in `rating_distributions.csv`.
Written-response percentages use all {len(frame)} respondents. {unique_writers} provided at least one nonblank written response.
These counts are not code frequencies or theme prevalence.

The comparison inventory is newly calculated using current mappings. It is not evidence of which tests were run historically or selected for the paper.
All standard background fields are crossed with all 33 items and seven constructs. Multi-select categories are tested separately.
Custom groupings and mixed-method code/theme comparisons are outside this inventory. Observed multi-select categories with no applicable responses generate no candidate.
Non-estimable candidates remain in `comparisons.csv`. `comparison_groups.csv` includes small groups excluded from tests.
Other excluded rows have a missing or inapplicable background, an unrecognized ordered level, or a missing outcome.
`reported_in_paper` and `selection_reason` are unfilled reporting fields, not reconstructed historical decisions.

Across-test adjustment: **{method}**. Family definition: **{FAMILY_OPTIONS[family]}**.
Holm, when selected, uses every finite raw main-test p-value in each defined family before any preview filters.
Non-estimable candidates do not enter that adjustment. This sensitivity analysis is retrospective.
Raw p-values are preserved. Tukey-adjusted p-values remain separate and are not inputs to Holm.
All computed Tukey pairs are exported, even when the omnibus raw p-value is not below .05. The omnibus flag lets readers apply that interpretation rule.
Assumption-check p-values are diagnostic and outside the main-test adjustment families.
Welch mean differences and Hedges' g follow the stated group order. Welch intervals describe mean differences, not uncertainty in g.
ANOVA df_1 and df_2 are numerator and denominator degrees of freedom. Welch uses df_1. Spearman degrees of freedom are left blank.
Small samples, overlapping backgrounds, and multiple comparisons limit interpretation. An adjusted p-value does not remove these limitations.

## Qualitative material and release review

Only active codes are included in the codebook. Active does not mean finalized. Existing theme statuses and interpretation qualifications are retained.
Theme/code metadata may contain analyst prose and requires review before sharing.
An interpretation worksheet is included only if rows were explicitly selected. Existing notes are preserved, and new interpretation fields are left blank for the analyst.
The selected rows are a review draft, not a declaration that publication consent has been checked.
Full responses, respondent-level scores, emails, timestamps, and the database are not bundled.
Review category labels, small-group summaries, selected quotations, notes, and metadata before publication.
This package contains results and settings, not the respondent-level data required to reproduce the study exactly.
The questionnaire and historical evaluation materials must be supplied separately. Nothing is uploaded by this export.
""".encode()
    return files


def zip_bundle(files: dict[str, bytes]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, content in files.items():
            if Path(name).name != name:
                raise ValueError("Bundle filenames must not contain paths.")
            archive.writestr(name, content)
    return output.getvalue()
