"""Shared background comparison definitions for the UI and complete exports."""
from __future__ import annotations

import pandas as pd

from .schema import BACKGROUND_FIELDS, normalize_text, split_multi
from .statistics import (
    NOT_APPLICABLE_VALUES, group_comparison, multi_select_comparison, ordinal_correlation,
)


def observed_background_categories(frame: pd.DataFrame, field: object) -> pd.Series:
    values = frame[field.key].dropna()
    if field.kind == "multi":
        values = values.map(split_multi).explode().dropna()
    values = values.astype(str).str.strip()
    values = values[values.ne("")]
    return values.value_counts()


def background_analysis_specs(
    frame: pd.DataFrame,
    selected_field: object | None = None,
) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    fields = [selected_field] if selected_field is not None else BACKGROUND_FIELDS
    for field in fields:
        if field.kind == "multi":
            for category in observed_background_categories(frame, field).index.astype(str):
                if normalize_text(category) in NOT_APPLICABLE_VALUES:
                    continue
                specs.append(
                    {
                        "field": field,
                        "analysis_type": "multi",
                        "category": category,
                        "label": f"{field.label}: {category}",
                    }
                )
        elif field.kind == "ordinal":
            specs.append(
                {
                    "field": field,
                    "analysis_type": "ordinal",
                    "category": None,
                    "label": field.label,
                }
            )
        else:
            specs.append(
                {
                    "field": field,
                    "analysis_type": "nominal",
                    "category": None,
                    "label": field.label,
                }
            )
    return specs


def run_background_analysis(
    frame: pd.DataFrame,
    field: object,
    outcome: str,
    analysis_type: str,
    category: str | None,
) -> dict[str, object]:
    if analysis_type == "ordinal":
        return ordinal_correlation(frame, field.key, outcome)
    if analysis_type == "multi" and category is not None:
        return multi_select_comparison(frame, field.key, category, outcome)
    analysis_frame = frame.copy()
    analysis_frame[field.key] = analysis_frame[field.key].map(
        lambda value: pd.NA
        if pd.notna(value) and normalize_text(value) in NOT_APPLICABLE_VALUES
        else value
    )
    return group_comparison(analysis_frame, field.key, outcome)


