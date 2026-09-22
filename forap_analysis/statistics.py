from __future__ import annotations

import math
import warnings
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from .schema import CONSTRUCTS, FIELD_BY_KEY, ITEM_FIELDS, normalize_text, split_multi


YEARS_EXPERIENCE_RANKS = {
    normalize_text("Beginner (e.g., <= 5 years)"): 0.0,
    normalize_text("Intermediate (e.g., 6-10 years)"): 1.0,
    normalize_text("Experienced (e.g., 11+ years)"): 2.0,
}

NOT_APPLICABLE_VALUES = {
    normalize_text("Not applicable"),
    normalize_text("N/A"),
}


def applicable_multi_options(value: object) -> list[str]:
    if value is None or pd.isna(value):
        return []
    return [
        option
        for option in split_multi(value)
        if normalize_text(option) not in NOT_APPLICABLE_VALUES
    ]


def item_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    total = len(frame)
    for field in ITEM_FIELDS:
        values = pd.to_numeric(frame.get(field.key, pd.Series(dtype=float)), errors="coerce").dropna()
        n = len(values)
        mean = values.mean() if n else np.nan
        sd = values.std(ddof=1) if n > 1 else np.nan
        sem = sd / math.sqrt(n) if n > 1 else np.nan
        critical = stats.t.ppf(0.975, n - 1) if n > 1 else np.nan
        rows.append(
            {
                "key": field.key,
                "construct": field.construct,
                "item": field.label,
                "n": n,
                "missing": total - n,
                "mean": mean,
                "sd": sd,
                "median": values.median() if n else np.nan,
                "q1": values.quantile(0.25) if n else np.nan,
                "q3": values.quantile(0.75) if n else np.nan,
                "top_2_box_pct": values.isin([4, 5]).mean() * 100 if n else np.nan,
                "bottom_2_box_pct": values.isin([1, 2]).mean() * 100 if n else np.nan,
                "ci95_low": mean - critical * sem if n > 1 else np.nan,
                "ci95_high": mean + critical * sem if n > 1 else np.nan,
            }
        )
    return pd.DataFrame(rows)


def construct_scores(frame: pd.DataFrame, minimum_fraction: float = 0.5) -> pd.DataFrame:
    output = pd.DataFrame(index=frame.index)
    if "response_id" in frame:
        output["response_id"] = frame["response_id"]
    for construct in CONSTRUCTS:
        keys = [field.key for field in ITEM_FIELDS if field.construct == construct and field.key in frame]
        values = frame[keys].apply(pd.to_numeric, errors="coerce")
        minimum = max(1, math.ceil(len(keys) * minimum_fraction))
        output[construct] = values.mean(axis=1).where(values.notna().sum(axis=1) >= minimum)
    return output


def construct_summary(frame: pd.DataFrame) -> pd.DataFrame:
    scores = construct_scores(frame)
    rows = []
    for construct in CONSTRUCTS:
        values = scores.get(construct, pd.Series(dtype=float)).dropna()
        rows.append(
            {
                "construct": construct,
                "n": len(values),
                "mean": values.mean() if len(values) else np.nan,
                "sd": values.std(ddof=1) if len(values) > 1 else np.nan,
                "median": values.median() if len(values) else np.nan,
                "iqr": values.quantile(0.75) - values.quantile(0.25) if len(values) else np.nan,
                "alpha": cronbach_alpha(frame, construct),
            }
        )
    return pd.DataFrame(rows)


def cronbach_alpha(frame: pd.DataFrame, construct: str) -> float:
    keys = [field.key for field in ITEM_FIELDS if field.construct == construct and field.key in frame]
    if len(keys) < 2:
        return np.nan
    complete = frame[keys].apply(pd.to_numeric, errors="coerce").dropna()
    if len(complete) < 2:
        return np.nan
    item_variances = complete.var(axis=0, ddof=1).sum()
    total_variance = complete.sum(axis=1).var(ddof=1)
    if not total_variance or np.isnan(total_variance):
        return np.nan
    count = len(keys)
    return float(count / (count - 1) * (1 - item_variances / total_variance))


def corrected_item_total(frame: pd.DataFrame, construct: str) -> pd.DataFrame:
    keys = [field.key for field in ITEM_FIELDS if field.construct == construct and field.key in frame]
    numeric = frame[keys].apply(pd.to_numeric, errors="coerce")
    rows = []
    for key in keys:
        others = numeric.drop(columns=[key]).mean(axis=1)
        valid = pd.concat([numeric[key], others], axis=1).dropna()
        correlation = valid.iloc[:, 0].corr(valid.iloc[:, 1]) if len(valid) >= 3 else np.nan
        rows.append({"item": FIELD_BY_KEY[key].label, "corrected_item_total_r": correlation, "n": len(valid)})
    return pd.DataFrame(rows)


def likert_distribution(frame: pd.DataFrame, construct: str) -> pd.DataFrame:
    rows = []
    for field in ITEM_FIELDS:
        if field.construct != construct or field.key not in frame:
            continue
        values = pd.to_numeric(frame[field.key], errors="coerce").dropna()
        for score in range(1, 6):
            rows.append(
                {
                    "key": field.key,
                    "item": field.label,
                    "score": score,
                    "count": int((values == score).sum()),
                    "percent": float((values == score).mean() * 100) if len(values) else 0.0,
                }
            )
    return pd.DataFrame(rows)


def tukey_method_name(sample_sizes: list[int]) -> str:
    if len(set(sample_sizes)) > 1:
        return "Tukey HSD with the Tukey-Kramer adjustment for unequal group sizes"
    return "Tukey HSD"


def group_comparison(frame: pd.DataFrame, group_key: str, outcome: str) -> dict[str, Any]:
    if outcome in CONSTRUCTS:
        outcome_values = construct_scores(frame)[outcome]
    elif outcome in frame.columns:
        outcome_values = pd.to_numeric(frame[outcome], errors="coerce")
    else:
        raise KeyError(f"Unknown comparison outcome: {outcome}")
    data = pd.DataFrame({"group": frame[group_key], "score": outcome_values}).dropna()
    counts = data.groupby("group", observed=True)["score"].count().sort_values(ascending=False)
    keep = counts[counts >= 2].index
    data = data[data["group"].isin(keep)]
    groups = [(name, values["score"].to_numpy()) for name, values in data.groupby("group", observed=True)]
    result: dict[str, Any] = {
        "data": data,
        "counts": counts.reset_index(name="n"),
        "test": None,
        "statistic": np.nan,
        "p_value": np.nan,
        "effect": np.nan,
        "effect_name": None,
        "warning": "",
        "posthoc": pd.DataFrame(),
        "posthoc_method": None,
        "assumptions": pd.DataFrame(),
    }
    if len(groups) < 2:
        result["warning"] = "At least two groups with two or more responses are required."
        return result
    if len(groups) == 2:
        (name_a, a), (name_b, b) = groups
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            statistic, p_value = stats.ttest_ind(a, b, equal_var=False, alternative="two-sided")
        pooled_variance = (
            ((len(a) - 1) * np.var(a, ddof=1) + (len(b) - 1) * np.var(b, ddof=1))
            / (len(a) + len(b) - 2)
        )
        pooled_sd = math.sqrt(pooled_variance) if pooled_variance > 0 else np.nan
        cohens_d = (np.mean(a) - np.mean(b)) / pooled_sd if pooled_sd else np.nan
        correction = 1 - 3 / (4 * (len(a) + len(b)) - 9)
        effect = cohens_d * correction if not np.isnan(cohens_d) else np.nan
        result.update(
            test="Welch’s t-test",
            statistic=float(statistic),
            p_value=float(p_value),
            effect=float(effect),
            effect_name=f"Hedges’ g ({name_a} vs {name_b})",
        )
    else:
        arrays = [values for _, values in groups]
        statistic, p_value = stats.f_oneway(*arrays)
        all_values = np.concatenate(arrays)
        grand_mean = np.mean(all_values)
        ss_between = sum(len(values) * (np.mean(values) - grand_mean) ** 2 for values in arrays)
        ss_total = sum((value - grand_mean) ** 2 for value in all_values)
        effect = ss_between / ss_total if ss_total > 0 else np.nan
        result.update(
            test="One-way ANOVA",
            statistic=float(statistic),
            p_value=float(p_value),
            effect=float(effect),
            effect_name="eta-squared",
            posthoc_method=tukey_method_name([len(values) for values in arrays]),
        )
        try:
            tukey = stats.tukey_hsd(*arrays)
            interval = tukey.confidence_interval(confidence_level=0.95)
            pairwise = []
            for first in range(len(groups)):
                for second in range(first + 1, len(groups)):
                    pairwise.append(
                        {
                            "group_1": groups[first][0],
                            "group_2": groups[second][0],
                            "n_1": len(groups[first][1]),
                            "n_2": len(groups[second][1]),
                            "mean_difference": float(tukey.statistic[first, second]),
                            "ci95_low": float(interval.low[first, second]),
                            "ci95_high": float(interval.high[first, second]),
                            "adjusted_p": float(tukey.pvalue[first, second]),
                            "different_at_0.05": bool(tukey.pvalue[first, second] < 0.05),
                        }
                    )
            result["posthoc"] = pd.DataFrame(pairwise)
        except ValueError as exc:
            result["warning"] = f"{result['posthoc_method']} could not be estimated: {exc}"

    assumption_rows = []
    if all(len(values) >= 2 for _, values in groups):
        deviations = np.concatenate(
            [np.abs(values - np.median(values)) for _, values in groups]
        )
        if np.var(deviations) > 0:
            levene_statistic, levene_p = stats.levene(*(values for _, values in groups), center="median")
            assumption_rows.append(
                {
                    "check": "Levene/Brown–Forsythe equal-variance check",
                    "group": "All groups",
                    "n": len(data),
                    "statistic": float(levene_statistic),
                    "p_value": float(levene_p),
                }
            )
    for name, values in groups:
        if 3 <= len(values) <= 5000 and np.std(values, ddof=1) > 0:
            shapiro_statistic, shapiro_p = stats.shapiro(values)
            assumption_rows.append(
                {
                    "check": "Shapiro–Wilk normality check",
                    "group": name,
                    "n": len(values),
                    "statistic": float(shapiro_statistic),
                    "p_value": float(shapiro_p),
                }
            )
    result["assumptions"] = pd.DataFrame(assumption_rows)
    if len(data) < 30 or any(len(values) < 5 for _, values in groups):
        result["warning"] = (
            (result["warning"] + " ") if result["warning"] else ""
        ) + "Small group sizes make this exploratory. Check distributions and assumptions, and emphasize effect size rather than the p-value alone."
    return result


def _outcome_values(frame: pd.DataFrame, outcome: str) -> pd.Series:
    if outcome in CONSTRUCTS:
        return construct_scores(frame)[outcome]
    if outcome in frame.columns:
        return pd.to_numeric(frame[outcome], errors="coerce")
    raise KeyError(f"Unknown comparison outcome: {outcome}")


def ordinal_background_scores(frame: pd.DataFrame, predictor_key: str) -> pd.Series:
    values = frame[predictor_key]
    field = FIELD_BY_KEY[predictor_key]
    if field.kind == "multi":
        raise ValueError("Multi-select backgrounds require separate selected-versus-not-selected comparisons.")
    if field.scale == "experience":
        return pd.to_numeric(values, errors="coerce")
    if predictor_key == "years_experience":
        return values.map(
            lambda value: np.nan
            if pd.isna(value)
            else YEARS_EXPERIENCE_RANKS.get(normalize_text(value), np.nan)
        )
    return pd.to_numeric(values, errors="coerce")


def ordinal_correlation(frame: pd.DataFrame, predictor_key: str, outcome: str) -> dict[str, Any]:
    data = pd.DataFrame(
        {
            "group": ordinal_background_scores(frame, predictor_key),
            "score": _outcome_values(frame, outcome),
        }
    ).dropna()
    counts = data.groupby("group", observed=True)["score"].count().reset_index(name="n")
    result: dict[str, Any] = {
        "data": data,
        "counts": counts,
        "test": None,
        "statistic": np.nan,
        "p_value": np.nan,
        "effect": np.nan,
        "effect_name": "Spearman’s ρ",
        "warning": "",
        "posthoc": pd.DataFrame(),
        "assumptions": pd.DataFrame(),
    }
    if len(data) < 3 or data["group"].nunique() < 2:
        result["warning"] = "At least three responses across two ordered levels are required."
        return result
    if data["score"].nunique() < 2:
        result["warning"] = "The outcome has no variation, so a correlation cannot be estimated."
        return result
    statistic, p_value = stats.spearmanr(data["group"], data["score"])
    result.update(
        test="Spearman rank correlation",
        statistic=float(statistic),
        p_value=float(p_value),
        effect=float(statistic),
    )
    if len(data) < 30:
        result["warning"] = "The sample is small; treat the correlation as exploratory."
    return result


def multi_select_comparison(
    frame: pd.DataFrame,
    predictor_key: str,
    category: str,
    outcome: str,
) -> dict[str, Any]:
    source = frame[predictor_key]
    applicable = source.map(applicable_multi_options)
    populated = applicable.map(bool)
    comparison_frame = frame.loc[populated].copy()
    category_key = normalize_text(category)
    comparison_frame["_selection_group"] = applicable.loc[populated].map(
        lambda value: "Selected"
        if category_key in {normalize_text(option) for option in value}
        else "Not selected"
    )
    comparison_frame["_selection_group"] = pd.Categorical(
        comparison_frame["_selection_group"],
        categories=["Selected", "Not selected"],
        ordered=True,
    )
    return group_comparison(comparison_frame, "_selection_group", outcome)


def assign_custom_groups(
    memberships: pd.Series,
    category_to_group: dict[str, str],
) -> pd.DataFrame:
    """Assign each respondent to one mutually exclusive custom group.

    ``memberships`` may contain one category or an iterable of categories. A
    multi-select respondent matching categories assigned to more than one
    group is marked as overlapping and is not assigned to either group.
    """

    normalized_mapping = {
        normalize_text(category): group
        for category, group in category_to_group.items()
        if str(group).strip()
    }

    def respondent_assignment(value: object) -> tuple[object, str]:
        if value is None or (not isinstance(value, (list, tuple, set)) and pd.isna(value)):
            categories: list[object] = []
        elif isinstance(value, (list, tuple, set)):
            categories = list(value)
        else:
            categories = [value]
        groups = {
            normalized_mapping[normalize_text(category)]
            for category in categories
            if normalize_text(category) in normalized_mapping
        }
        if len(groups) == 1:
            return groups.pop(), "Assigned"
        if len(groups) > 1:
            return pd.NA, "Overlap"
        return pd.NA, "Unassigned"

    assignments = memberships.map(respondent_assignment)
    return pd.DataFrame(
        {
            "group": assignments.map(lambda value: value[0]),
            "status": assignments.map(lambda value: value[1]),
        },
        index=memberships.index,
    )
