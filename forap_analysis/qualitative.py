from __future__ import annotations

from typing import Any

import pandas as pd

from .database import Database
from .schema import OPEN_TEXT_FIELDS


RATING_LINKED_KEYS = (
    "clarity_comments",
    "missing_components",
    "completeness_comments",
    "usefulness_comments",
    "instructor_comments",
    "student_comments",
    "assessment_comments",
    "attribute_comments",
)

OVERALL_FEEDBACK_KEYS = ("strengths", "weaknesses", "suggestions")
BRIDGE_KEYS = ("missing_components",)

QUESTION_METADATA: dict[str, dict[str, str]] = {
    "clarity_comments": {
        "role": "Rating-linked",
        "linked_area": "Clarity",
        "purpose": "Explain why experts gave their clarity ratings.",
    },
    "missing_components": {
        "role": "Bridge",
        "linked_area": "Completeness",
        "purpose": "Explain completeness ratings and identify issues that may contribute to overarching themes.",
    },
    "completeness_comments": {
        "role": "Rating-linked",
        "linked_area": "Completeness",
        "purpose": "Explain why experts gave their completeness ratings.",
    },
    "usefulness_comments": {
        "role": "Rating-linked",
        "linked_area": "Overall usefulness",
        "purpose": "Explain conditions behind design, reuse, adaptation, and adoption ratings.",
    },
    "instructor_comments": {
        "role": "Rating-linked",
        "linked_area": "Instructor support",
        "purpose": "Explain ratings of the instructor-support package.",
    },
    "student_comments": {
        "role": "Rating-linked",
        "linked_area": "Student support",
        "purpose": "Explain ratings of the student-support package.",
    },
    "assessment_comments": {
        "role": "Rating-linked",
        "linked_area": "Assessment support",
        "purpose": "Explain ratings of the assessment-support package.",
    },
    "attribute_comments": {
        "role": "Rating-linked",
        "linked_area": "Project attributes",
        "purpose": "Explain ratings of project attributes and their usefulness for project selection.",
    },
    "strengths": {
        "role": "Overall feedback",
        "linked_area": "Whole framework",
        "purpose": "Primary thematic evidence about FORAP's perceived strengths.",
    },
    "weaknesses": {
        "role": "Overall feedback",
        "linked_area": "Whole framework",
        "purpose": "Primary thematic evidence about limitations, risks, and disagreement.",
    },
    "suggestions": {
        "role": "Overall feedback",
        "linked_area": "Whole framework",
        "purpose": "Primary thematic evidence about revisions and additions.",
    },
}


def question_metadata(question_key: str) -> dict[str, str]:
    return QUESTION_METADATA.get(
        question_key,
        {"role": "Other", "linked_area": "Whole framework", "purpose": "Open-ended evidence."},
    )


def corpus_inventory(frame: pd.DataFrame, db: Database) -> pd.DataFrame:
    units = db.meaning_units()
    codings = db.codings()
    records: list[dict[str, Any]] = []
    total = len(frame)
    for field in OPEN_TEXT_FIELDS:
        present = frame[field.key].fillna("").astype(str).str.strip().ne("")
        question_units = units[units["question_key"] == field.key] if not units.empty else pd.DataFrame()
        question_codings = codings[codings["question_key"] == field.key] if not codings.empty else pd.DataFrame()
        metadata = question_metadata(field.key)
        records.append(
            {
                "Question": field.label,
                "Analysis role": metadata["role"],
                "Linked area": metadata["linked_area"],
                "Purpose": metadata["purpose"],
                "Non-empty responses": int(present.sum()),
                "Coverage": float(present.mean()) if total else 0.0,
                "Coded respondents": int(question_codings["response_id"].nunique()) if not question_codings.empty else 0,
                "Coded excerpts": len(question_units),
            }
        )
    return pd.DataFrame(records)


def role_totals(frame: pd.DataFrame) -> dict[str, int]:
    def respondent_count(keys: tuple[str, ...]) -> int:
        if frame.empty:
            return 0
        present = pd.DataFrame(
            {
                key: frame[key].fillna("").astype(str).str.strip().ne("")
                for key in keys
            }
        )
        return int(present.any(axis=1).sum())

    return {
        "rating_linked_question_responses": int(
            sum(frame[key].fillna("").astype(str).str.strip().ne("").sum() for key in RATING_LINKED_KEYS)
        ),
        "overall_feedback_question_responses": int(
            sum(frame[key].fillna("").astype(str).str.strip().ne("").sum() for key in OVERALL_FEEDBACK_KEYS)
        ),
        "rating_linked_respondents": respondent_count(RATING_LINKED_KEYS),
        "overall_feedback_respondents": respondent_count(OVERALL_FEEDBACK_KEYS),
    }
