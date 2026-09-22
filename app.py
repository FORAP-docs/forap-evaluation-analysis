from __future__ import annotations

import html
import json

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit.errors import StreamlitAPIException

from forap_analysis.charts import (
    SCORE_COLORS, SCALE_LABELS, divergent_likert_figure,
    EXPERIENCE_EXPORT_CONFIG, pjbl_experience_figure,
)
from forap_analysis.database import Database
from forap_analysis.edit_mode import (
    edit_mode_enabled as state_edit_mode_enabled,
    handle_edit_mode_change,
)
from forap_analysis.highlights import (
    code_display_colors,
    exact_occurrences,
    excerpt_digest,
    highlight_review_states,
    normalize_passages,
    render_highlighted_excerpt,
)
from forap_analysis.importer import (
    IMPORT_PIPELINE_VERSION,
    ImportPreview,
    preview_workbook,
)
from forap_analysis.navigation import (
    apply_pending_navigation,
    back_label,
    request_back,
    request_response,
)
from forap_analysis.qualitative import (
    BRIDGE_KEYS,
    OVERALL_FEEDBACK_KEYS,
    RATING_LINKED_KEYS,
    corpus_inventory,
    role_totals,
)
from forap_analysis.schema import (
    BACKGROUND_CATEGORY_OPTIONS,
    BACKGROUND_FIELDS,
    CONSTRUCTS,
    FIELD_BY_KEY,
    ITEM_FIELDS,
    OPEN_TEXT_FIELDS,
    normalize_text,
    split_multi,
)
from forap_analysis.statistics import (
    NOT_APPLICABLE_VALUES,
    assign_custom_groups,
    construct_scores,
    construct_summary,
    corrected_item_total,
    group_comparison,
    item_summary,
    likert_distribution,
    multi_select_comparison,
    ordinal_background_scores,
    ordinal_correlation,
)


st.set_page_config(page_title="FORAP Evaluation Analysis", page_icon="📊", layout="wide")


CODE_BADGE_COLORS = (
    "#0f62fe",
    "#007d79",
    "#8a3ffc",
    "#a56eff",
    "#005d5d",
    "#9f1853",
    "#b28600",
    "#da1e28",
    "#198038",
    "#0043ce",
)

CHART_PALETTE = (
    "#0f62fe",
    "#007d79",
    "#8a3ffc",
    "#d02670",
    "#b28600",
    "#198038",
    "#fa4d56",
)
CONSTRUCT_COLORS = {
    construct: CHART_PALETTE[index % len(CHART_PALETTE)]
    for index, construct in enumerate(CONSTRUCTS)
}
EVIDENCE_ROLE_ORDER = {"supporting": 0, "contextual": 1, "contrasting": 2}


@st.cache_resource
def get_database(schema_revision: str = "excerpt-highlights-v1") -> Database:
    # A new revision replaces cached objects from before a database/API upgrade.
    return Database()


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #f4f4f4; }
        [data-testid="stMainBlockContainer"] {
            padding: 3.75rem 2.5rem 5rem !important;
        }
        [data-testid="stSidebar"] {
            background: #161616;
            border-right: 1px solid #393939;
        }
        [data-testid="stSidebar"] * { color: #f4f4f4; }
        [data-testid="stSidebarHeader"] {
            height: 2.75rem !important;
            margin-bottom: .25rem !important;
        }
        [data-testid="stSidebarUserContent"] {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-bottom: 3rem !important;
        }
        [data-testid="stSidebar"] div[role="radiogroup"] {
            gap: .25rem;
        }
        [data-testid="stSidebar"] div[role="radiogroup"] > label {
            width: 100%;
            min-height: 2.7rem;
            margin: 0;
            padding: .65rem .75rem;
            background: transparent;
            border-left: 3px solid transparent;
            transition: background .12s ease, border-color .12s ease;
        }
        [data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
            background: #262626;
        }
        [data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
            background: #262626;
            border-left-color: #4589ff;
        }
        [data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p {
            color: #ffffff !important;
            font-weight: 650;
        }
        [data-testid="stSidebar"] div[role="radiogroup"] > label:last-child {
            position: relative;
            margin-top: 2rem;
        }
        [data-testid="stSidebar"] div[role="radiogroup"] > label:last-child::before {
            content: "Data";
            position: absolute;
            top: -1.45rem;
            left: .2rem;
            color: #8d8d8d;
            font-size: .62rem;
            font-weight: 700;
            letter-spacing: .12em;
            text-transform: uppercase;
        }
        [data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child {
            display: none;
        }
        .sidebar-brand {
            padding: .15rem 0 1.15rem;
            margin-bottom: 1rem;
            border-bottom: 1px solid #393939;
        }
        .sidebar-brand-mark {
            color: #78a9ff !important;
            font-size: .72rem;
            font-weight: 700;
            letter-spacing: .14em;
        }
        .sidebar-brand-title {
            color: #ffffff !important;
            font-size: 1.25rem;
            font-weight: 600;
            line-height: 1.2;
            margin-top: .2rem;
        }
        .sidebar-brand-copy {
            color: #c6c6c6 !important;
            font-size: .76rem;
            line-height: 1.45;
            margin-top: .4rem;
        }
        .sidebar-section-label {
            color: #8d8d8d !important;
            font-size: .68rem;
            font-weight: 700;
            letter-spacing: .12em;
            text-transform: uppercase;
            margin: 0 0 .45rem .2rem;
        }
        .sidebar-status {
            border-top: 1px solid #393939;
            margin-top: 1.25rem;
            padding: 1rem .2rem 0;
        }
        .sidebar-status strong {
            color: #f4f4f4 !important;
            display: block;
            font-size: .76rem;
            margin-bottom: .2rem;
        }
        .sidebar-status span {
            color: #8d8d8d !important;
            display: block;
            font-size: .7rem;
            line-height: 1.45;
            overflow-wrap: anywhere;
        }
        .forap-title { color: #0f62fe; font-size: 2.25rem; font-weight: 500; letter-spacing: -.03em; line-height: 1.1; margin: .25rem 0 .5rem; }
        .forap-subtitle { color: #525252; width: 100%; max-width: none; margin-bottom: 1.5rem; }
        .privacy-note { background: #e8f0ff; border-left: 4px solid #0f62fe; padding: .8rem 1rem; color: #161616; }
        div[data-testid="stMetric"] { background: white; border-top: 3px solid #0f62fe; padding: .75rem; }
        div[data-testid="stForm"] { background: white; border: 1px solid #e0e0e0; padding: 1rem; }
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: white;
            border-color: #c6c6c6 !important;
            border-radius: 0 !important;
        }
        .stButton > button,
        .stDownloadButton > button {
            min-height: 2.5rem;
            border-radius: 0 !important;
            font-weight: 600;
        }
        [data-testid="stTextInputRootElement"],
        [data-testid="stTextAreaRootElement"] {
            background: white !important;
            border: 1px solid #8d8d8d !important;
            border-radius: 0 !important;
            box-shadow: none !important;
        }
        [data-testid="stTextInputRootElement"]:hover,
        [data-testid="stTextAreaRootElement"]:hover {
            border-color: #525252 !important;
        }
        [data-testid="stTextInputRootElement"]:focus-within,
        [data-testid="stTextAreaRootElement"]:focus-within {
            border-color: #0f62fe !important;
            box-shadow: inset 0 0 0 1px #0f62fe !important;
        }
        [data-testid="stSelectbox"] *:has(> [role="combobox"]),
        [data-testid="stMultiSelect"] [data-baseweb="select"] > div {
            background: white !important;
            border: 1px solid #8d8d8d !important;
            border-radius: 0 !important;
            box-shadow: none !important;
        }
        [data-testid="stSelectbox"] *:has(> [role="combobox"]):hover,
        [data-testid="stMultiSelect"] [data-baseweb="select"] > div:hover {
            border-color: #525252 !important;
        }
        [data-testid="stSelectbox"] *:has(> [role="combobox"]):focus-within,
        [data-testid="stMultiSelect"] [data-baseweb="select"] > div:focus-within {
            border-color: #0f62fe !important;
            box-shadow: inset 0 0 0 1px #0f62fe !important;
        }
        [data-baseweb="tab-list"] {
            flex-wrap: wrap !important;
            overflow: visible !important;
            row-gap: .25rem;
        }
        [data-baseweb="tab-list"] > button {
            flex: 0 0 auto !important;
        }
        .response-card { background: white; border: 1px solid #c6c6c6; border-left: 5px solid #0f62fe; padding: 1.2rem 1.25rem; margin: .6rem 0 1rem; font-size: 1.02rem; line-height: 1.6; }
        .response-position { text-align: center; font-size: 1.05rem; font-weight: 650; padding-top: .45rem; }
        .response-heading-row { display: flex; flex-wrap: wrap; align-items: center; gap: .3rem; margin: .15rem 0 .8rem; }
        .response-heading-title { color: #161616; font-size: 1.35rem; font-weight: 650; line-height: 1.25; margin-right: .1rem; }
        .response-coding-status { color: #525252; font-size: .76rem; }
        .response-meta-badge { background: #e8f0ff; color: #161616; border: 1px solid #a6c8ff; border-radius: 999px; padding: .18rem .45rem; font-size: .72rem; line-height: 1.3; }
        .response-meta-badge strong { color: #0043ce; font-weight: 650; }
        .respondent-badge { background: #161616; color: #ffffff; border: 1px solid #161616; border-radius: 999px; padding: .2rem .5rem; font-size: .75rem; font-weight: 650; line-height: 1.3; white-space: nowrap; }
        [class*="st-key-respondent_link_"] button {
            background: #161616; color: #ffffff; border: 1px solid #161616;
            border-radius: 999px; padding: .2rem .55rem; min-height: 1.65rem;
        }
        [class*="st-key-respondent_link_"] button p { font-size: .78rem; font-weight: 650; }
        [class*="st-key-respondent_link_"] button:hover {
            background: #0043ce; border-color: #0043ce; color: #ffffff;
        }
        [class*="st-key-respondent_link_"] button:focus-visible {
            outline: 2px solid #0f62fe; outline-offset: 3px;
        }
        .evidence-role-badge { border: 1px solid; border-radius: 999px; padding: .2rem .5rem; font-size: .75rem; font-weight: 650; line-height: 1.3; white-space: nowrap; }
        .evidence-role-supporting { background: #defbe6; border-color: #24a148; color: #0e6027; }
        .evidence-role-contextual { background: #e8f0ff; border-color: #4589ff; color: #0043ce; }
        .evidence-role-contrasting { background: #fff1f1; border-color: #da1e28; color: #a2191f; }
        .evidence-question-badge { background: #f2f4f8; border: 1px solid #8d8d8d; border-radius: 2px; color: #393939; padding: .2rem .5rem; font-size: .75rem; line-height: 1.3; white-space: nowrap; }
        .evidence-question-badge strong { color: #161616; font-weight: 650; }
        .representative-badge { background: #fff8e1; border: 1px solid #b28600; border-radius: 999px; color: #6f4b00; padding: .2rem .5rem; font-size: .75rem; font-weight: 650; line-height: 1.3; white-space: nowrap; }
        .coded-excerpt { background: #f8f8f8; border-left: 4px solid #8a3ffc; padding: .85rem 1rem; margin: .45rem 0 .65rem; }
        .passage-view { background: #f8f8f8; border-left: 3px solid #c6c6c6; padding: .75rem 1rem; margin: .4rem 0 .6rem; }
        .passage-text { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.85; color: #161616; }
        .passage-highlight { color: inherit; box-decoration-break: clone; -webkit-box-decoration-break: clone; }
        .passage-highlight:focus { outline: 2px solid #161616; outline-offset: 2px; }
        .code-badges { display: flex; flex-wrap: wrap; gap: .35rem; margin: .35rem 0 .65rem; overflow: visible; position: relative; }
        .code-badge { background: var(--code-tint, #f6f2ff); color: var(--code-color, #6929c4); border: 1px solid var(--code-color, #be95ff); border-radius: 999px; padding: .2rem .55rem; font-size: .78rem; font-weight: 600; line-height: 1.35; }
        .excerpt-code-badge { color: #262626; border-bottom-width: 3px; }
        .code-badge-review { font-weight: 400; }
        .code-badge[data-tooltip] { cursor: help; position: relative; }
        .code-badge[data-tooltip]::after {
            background: #161616;
            border: 1px solid #525252;
            box-shadow: 0 4px 14px rgba(0, 0, 0, .24);
            color: #ffffff;
            content: attr(data-tooltip);
            font-size: .76rem;
            font-weight: 400;
            left: 0;
            line-height: 1.45;
            max-width: min(28rem, 70vw);
            min-width: 18rem;
            opacity: 0;
            padding: .7rem .8rem;
            pointer-events: none;
            position: absolute;
            top: calc(100% + .45rem);
            transform: translateY(-.2rem);
            transition: opacity .12s ease, transform .12s ease, visibility .12s ease;
            visibility: hidden;
            white-space: pre-line;
            z-index: 10000;
        }
        .code-badge[data-tooltip]:hover::after,
        .code-badge[data-tooltip]:focus-visible::after {
            opacity: 1;
            transform: translateY(0);
            visibility: visible;
        }
        .code-badge-empty { background: #f4f4f4; color: #6f6f6f; border-color: #c6c6c6; }
        .rating-strip { display: flex; flex-wrap: wrap; align-items: center; gap: .4rem; margin: .25rem 0 .8rem; }
        .rating-summary { background: #0f62fe; color: white; padding: .3rem .55rem; font-size: .82rem; font-weight: 600; }
        .rating-chip { background: #e8f0ff; color: #161616; border: 1px solid #a6c8ff; padding: .28rem .48rem; font-size: .78rem; }
        .rating-chip strong { color: #0043ce; }
        .individual-response-summary {
            align-items: center;
            background: #ffffff;
            border-left: 4px solid #0f62fe;
            display: flex;
            flex-wrap: wrap;
            gap: .55rem;
            margin: .25rem 0 1rem;
            padding: .75rem 1rem;
        }
        .individual-response-summary-text { color: #525252; font-size: .82rem; }
        .individual-section {
            background: #ffffff;
            border: 1px solid #c6c6c6;
            margin: 0 0 1rem;
        }
        .individual-section-heading {
            align-items: baseline;
            border-bottom: 1px solid #e0e0e0;
            display: flex;
            justify-content: space-between;
            gap: .75rem;
            padding: .8rem 1rem;
        }
        .individual-section-title { color: #161616; font-size: 1rem; font-weight: 650; }
        .individual-section-stat { color: #6f6f6f; font-size: .76rem; white-space: nowrap; }
        .individual-rating-row {
            align-items: center;
            border-bottom: 1px solid #e0e0e0;
            display: grid;
            gap: .8rem;
            grid-template-columns: minmax(0, 1fr) auto;
            padding: .65rem 1rem;
        }
        .individual-rating-row:last-child { border-bottom: 0; }
        .individual-rating-item { color: #393939; font-size: .84rem; line-height: 1.35; }
        .individual-rating-value {
            border: 1px solid var(--rating-color);
            color: var(--rating-text, #161616);
            font-size: .76rem;
            font-weight: 650;
            min-width: 8.8rem;
            padding: .25rem .45rem;
            text-align: center;
            white-space: nowrap;
        }
        .individual-rating-missing {
            background: #f4f4f4;
            border-color: #c6c6c6;
            color: #6f6f6f;
        }
        .individual-profile { background: #ffffff; border: 1px solid #c6c6c6; margin-bottom: 1rem; }
        .individual-profile-title { border-bottom: 1px solid #e0e0e0; font-size: 1rem; font-weight: 650; padding: .8rem 1rem; }
        .individual-profile-row { border-bottom: 1px solid #e0e0e0; padding: .65rem 1rem; }
        .individual-profile-row:last-child { border-bottom: 0; }
        .individual-profile-label { color: #6f6f6f; font-size: .7rem; font-weight: 650; letter-spacing: .04em; margin-bottom: .25rem; text-transform: uppercase; }
        .individual-profile-value { color: #262626; font-size: .84rem; line-height: 1.45; overflow-wrap: anywhere; }
        .individual-text-card { background: #ffffff; border: 1px solid #c6c6c6; margin-bottom: .75rem; padding: .85rem 1rem; }
        .individual-text-question { color: #393939; font-size: .78rem; font-weight: 650; margin-bottom: .4rem; }
        .individual-text-answer { color: #161616; font-size: .9rem; line-height: 1.55; white-space: pre-wrap; }
        .individual-text-empty { color: #8d8d8d; font-style: italic; }
        .frequency-list { border-top: 1px solid #e0e0e0; margin: .35rem 0 .75rem; }
        .frequency-row { display: flex; align-items: flex-start; justify-content: space-between; gap: .65rem; border-bottom: 1px solid #e0e0e0; padding: .55rem 0; }
        .frequency-label { color: #393939; font-size: .8rem; line-height: 1.35; overflow-wrap: anywhere; }
        .frequency-count { background: #161616; color: #ffffff; border-radius: 999px; min-width: 1.75rem; padding: .12rem .42rem; text-align: center; font-size: .75rem; font-weight: 650; }
        .small-note { color: #6f6f6f; font-size: .82rem; }
        @media (max-width: 900px) {
            [data-testid="stMainBlockContainer"] {
                padding: 3.75rem 1rem 4rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def edit_mode_enabled() -> bool:
    return state_edit_mode_enabled(st.session_state)


def change_edit_mode() -> None:
    handle_edit_mode_change(st.session_state)


def page_header(title: str, subtitle: str) -> None:
    with st.container(key="workspace_header"):
        title_col, mode_col = st.columns([4, 1], vertical_alignment="center")
        title_col.markdown(
            f'<div class="forap-title">{html.escape(title)}</div>',
            unsafe_allow_html=True,
        )
        mode_col.toggle(
            "Edit mode",
            key="edit_mode",
            on_change=change_edit_mode,
            help="Show editing controls across the workspace. When off, you can still browse, filter and download without changing analysis data.",
        )
        st.markdown(
            f'<div class="forap-subtitle">{html.escape(subtitle)}</div>',
            unsafe_allow_html=True,
        )


def dataframe_csv(frame: pd.DataFrame) -> bytes:
    safe = frame.copy()
    for column in safe.select_dtypes(include=["object", "string"]).columns:
        safe[column] = safe[column].map(
            lambda value: f"'{value}"
            if isinstance(value, str) and value.startswith(("=", "+", "-", "@"))
            else value
        )
    return safe.to_csv(index=False).encode("utf-8")


def respondent_labels_for_frame(frame: pd.DataFrame) -> dict[str, str]:
    if "response_id" not in frame:
        return {}
    return {
        str(response_id): f"R{index}"
        for index, response_id in enumerate(frame["response_id"].astype(str), start=1)
    }


def database_respondent_labels(db: Database) -> dict[str, str]:
    label_method = getattr(db, "respondent_labels", None)
    if callable(label_method):
        return label_method()
    return respondent_labels_for_frame(db.active_data())


def respondent_label(response_id: object, labels: dict[str, str]) -> str:
    return labels.get(str(response_id), "R?")


def respondent_badge(label: str) -> str:
    return f'<span class="respondent-badge">{html.escape(label)}</span>'


def open_respondent(response_id: str, origin: dict | None = None) -> None:
    request_response(st.session_state, response_id, origin=origin)


def return_from_respondent() -> None:
    request_back(st.session_state)


def render_respondent_heading(
    response_id: object,
    label: str,
    metadata: str,
    *,
    key: str,
    origin: dict | None = None,
) -> None:
    """Render one compact, keyboard-accessible respondent link beside metadata."""
    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
        if st.button(
            label,
            key=f"respondent_link_{key}",
            help=f"View {label}'s full individual response",
            on_click=open_respondent,
            args=(str(response_id), origin),
        ):
            # A click inside a dialog normally reruns only that fragment.
            # Navigation must close it and render the destination workspace.
            st.rerun(scope="app")
        st.markdown(
            f'<div class="response-heading-row" style="margin:0">{metadata}</div>',
            unsafe_allow_html=True,
        )


def render_response_back_navigation() -> None:
    label = back_label(st.session_state)
    if label:
        st.button(
            label,
            icon=":material/arrow_back:",
            key="response_navigation_back",
            on_click=return_from_respondent,
        )


def evidence_role_badge(role: object) -> str:
    label = str(role).strip().title() or "Evidence"
    role_class = str(role).strip().casefold()
    if role_class not in {"supporting", "contextual", "contrasting"}:
        role_class = "contextual"
    return (
        f'<span class="evidence-role-badge evidence-role-{role_class}">'
        f'{html.escape(label)}</span>'
    )


def order_theme_evidence_for_display(evidence: pd.DataFrame) -> pd.DataFrame:
    if evidence.empty or "evidence_role" not in evidence:
        return evidence.copy()
    ordered = evidence.copy()
    ordered["_role_key"] = (
        ordered["evidence_role"].fillna("").astype(str).str.strip().str.casefold()
    )
    ordered.loc[
        ~ordered["_role_key"].isin(EVIDENCE_ROLE_ORDER),
        "_role_key",
    ] = "contextual"
    ordered["_role_order"] = ordered["_role_key"].map(EVIDENCE_ROLE_ORDER)
    representative_values = (
        ordered["is_representative"]
        if "is_representative" in ordered
        else pd.Series(0, index=ordered.index)
    )
    ordered["_representative"] = pd.to_numeric(
        representative_values,
        errors="coerce",
    ).fillna(0).astype(int)
    tie_breakers = [
        column
        for column in ["question_key", "response_id", "meaning_unit_id"]
        if column in ordered
    ]
    return ordered.sort_values(
        ["_role_order", "_representative", *tie_breakers],
        ascending=[True, False, *([True] * len(tie_breakers))],
        kind="stable",
    )


def evidence_question_badge(question: object) -> str:
    return (
        '<span class="evidence-question-badge"><strong>Question:</strong>&nbsp;'
        f'{html.escape(str(question))}</span>'
    )


def representative_badge() -> str:
    return '<span class="representative-badge">Representative quotation</span>'


def replace_response_ids(frame: pd.DataFrame, labels: dict[str, str]) -> pd.DataFrame:
    output = frame.copy()
    if "response_id" not in output:
        return output
    position = output.columns.get_loc("response_id")
    values = output.pop("response_id").map(lambda value: respondent_label(value, labels))
    output.insert(position, "Respondent", values)
    return output


def fmt(value: object, digits: int = 2) -> str:
    try:
        return "—" if pd.isna(value) else f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def sentence_case_option(value: object) -> str:
    text = str(value)
    return text[:1].upper() + text[1:] if text else text


def response_rating_label(field: object, value: object) -> str:
    """Return the questionnaire wording for one stored numeric rating."""
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        return "Not rated"
    if pd.isna(value):
        return "Not rated"
    labels = SCALE_LABELS.get(field.scale or "", {})
    return sentence_case_option(labels.get(score, str(score)))


def response_background_value(field: object, value: object) -> str:
    """Format one background answer using the labels shown elsewhere in the app."""
    if pd.isna(value) or str(value).strip() == "":
        return "Missing"
    if field.scale == "experience":
        return background_category_label(field, value)
    if field.kind == "multi":
        categories = split_multi(value)
        return ", ".join(categories) if categories else "Missing"
    return str(value)


def respondent_construct_sections(row: pd.Series) -> list[dict[str, object]]:
    """Build a stable, reporting-friendly view of every rating in one response."""
    sections: list[dict[str, object]] = []
    for construct in CONSTRUCTS:
        ratings: list[dict[str, object]] = []
        scores: list[float] = []
        for field in ITEM_FIELDS:
            if field.construct != construct:
                continue
            value = row.get(field.key)
            score = None
            if pd.notna(value):
                try:
                    score = float(value)
                except (TypeError, ValueError):
                    score = None
            if score is not None:
                scores.append(score)
            ratings.append(
                {
                    "key": field.key,
                    "item": field.label,
                    "label": response_rating_label(field, value),
                    "score": score,
                }
            )
        sections.append(
            {
                "construct": construct,
                "mean": sum(scores) / len(scores) if scores else None,
                "answered": len(scores),
                "total": len(ratings),
                "ratings": ratings,
            }
        )
    return sections


OPEN_TEXT_CONSTRUCT = {
    "clarity_comments": "Clarity",
    "missing_components": "Completeness",
    "completeness_comments": "Completeness",
    "usefulness_comments": "Overall usefulness",
    "instructor_comments": "Instructor support",
    "student_comments": "Student support",
    "assessment_comments": "Assessment support",
    "attribute_comments": "Project attributes",
}

ALL_QUALITATIVE_KEYS = tuple(
    dict.fromkeys((*OVERALL_FEEDBACK_KEYS, *BRIDGE_KEYS, *RATING_LINKED_KEYS))
)


def respondent_rating_context(row: pd.Series, question_key: str) -> tuple[str, list[tuple[str, float]]]:
    construct = OPEN_TEXT_CONSTRUCT.get(question_key)
    if construct:
        fields = [field for field in ITEM_FIELDS if field.construct == construct]
        ratings = [
            (field.label, float(row[field.key]))
            for field in fields
            if field.key in row and pd.notna(row[field.key])
        ]
        mean = sum(value for _, value in ratings) / len(ratings) if ratings else float("nan")
        summary = f"{construct} mean: {mean:.2f}/5" if ratings else ""
        return summary, ratings

    construct_means: list[tuple[str, float]] = []
    for name in CONSTRUCTS:
        fields = [field for field in ITEM_FIELDS if field.construct == name]
        values = [float(row[field.key]) for field in fields if field.key in row and pd.notna(row[field.key])]
        minimum = max(1, (len(fields) + 1) // 2)
        if len(values) >= minimum:
            construct_means.append((name, sum(values) / len(values)))
    return "Construct means", construct_means


def render_rating_context(row: pd.Series, question_key: str) -> None:
    summary, ratings = respondent_rating_context(row, question_key)
    if not ratings:
        return
    chips = "".join(
        f'<span class="rating-chip" title="{html.escape(label, quote=True)}">'
        f'{html.escape(label)}: <strong>{value:.1f}/5</strong></span>'
        for label, value in ratings
    )
    st.markdown(
        f'<div class="rating-strip"><span class="rating-summary">{html.escape(summary)}</span>{chips}</div>',
        unsafe_allow_html=True,
    )


def suggested_code_color(name: str) -> str:
    position = sum((index + 1) * ord(character) for index, character in enumerate(name.strip()))
    return CODE_BADGE_COLORS[position % len(CODE_BADGE_COLORS)]


def badge_tint(color: str) -> str:
    safe = color if len(color) == 7 and color.startswith("#") else "#6929c4"
    try:
        red, green, blue = (int(safe[index : index + 2], 16) for index in (1, 3, 5))
    except ValueError:
        red, green, blue = (105, 41, 196)
    blend = lambda channel: round(0.10 * channel + 0.90 * 255)
    return f"rgb({blend(red)}, {blend(green)}, {blend(blue)})"


def code_tooltip_lookup(codes: pd.DataFrame) -> dict[str, dict[str, str]]:
    if codes.empty:
        return {}
    return {
        str(row["name"]): {
            "definition": str(row.get("description", "") or "").strip(),
            "include": str(row.get("inclusion_criteria", "") or "").strip(),
            "exclude": str(row.get("exclusion_criteria", "") or "").strip(),
        }
        for _, row in codes.iterrows()
    }


def render_code_badges(
    code_names: object,
    color_lookup: dict[str, str] | None = None,
    detail_lookup: dict[str, dict[str, str]] | None = None,
    *,
    review_lookup: dict[str, dict[str, object]] | None = None,
    excerpt_tags: bool = False,
) -> None:
    names = [name.strip() for name in str(code_names or "").split(" | ") if name.strip()]
    if names:
        badges = ""
        for name in names:
            color = str((color_lookup or {}).get(name) or suggested_code_color(name))
            if not (len(color) == 7 and color.startswith("#")):
                color = suggested_code_color(name)
            details = (detail_lookup or {}).get(name, {})
            tooltip_parts = []
            if details.get("definition"):
                tooltip_parts.append(f"Definition: {details['definition']}")
            if details.get("include"):
                tooltip_parts.append(f"Include when: {details['include']}")
            if details.get("exclude"):
                tooltip_parts.append(f"Exclude when: {details['exclude']}")
            review = (review_lookup or {}).get(name, {})
            if review.get("state"):
                tooltip_parts.append(f"Highlight review: {review['state']}")
            if review.get("note"):
                tooltip_parts.append(str(review["note"]))
            tooltip = "\n".join(tooltip_parts)
            tooltip_attribute = (
                f' data-tooltip="{html.escape(tooltip, quote=True)}" '
                f'aria-label="{html.escape(tooltip, quote=True)}" tabindex="0"'
                if tooltip
                else ""
            )
            review_label = (
                f'<span class="code-badge-review"> · {html.escape(str(review["state"]))}</span>'
                if review.get("needs_attention") else ""
            )
            badge_class = "code-badge excerpt-code-badge" if excerpt_tags else "code-badge"
            badges += (
                f'<span class="{badge_class}" style="--code-color:{html.escape(color, quote=True)};'
                f'--code-tint:{badge_tint(color)}"{tooltip_attribute}>{html.escape(name)}{review_label}</span>'
            )
    else:
        badges = '<span class="code-badge code-badge-empty">No code assigned</span>'
    st.markdown(f'<div class="code-badges">{badges}</div>', unsafe_allow_html=True)


def render_highlight_editor(
    db: Database,
    unit_id: int,
    excerpt: str,
    spans: pd.DataFrame,
    reviews: pd.DataFrame,
    key: str,
    *,
    in_dialog: bool = False,
    display_colors: dict[int, str] | None = None,
) -> None:
    """Edit passage annotations without editing quotations or code assignments."""
    if not edit_mode_enabled() or reviews.empty:
        return

    def refresh() -> None:
        if in_dialog:
            try:
                st.rerun(scope="fragment")
            except StreamlitAPIException:
                # A dialog may also be rendered during a full-app rerun.
                pass
        st.rerun()

    with st.expander("Edit highlighted passages"):
        review_index = reviews.drop_duplicates("code_id").set_index("code_id")
        code_ids = [int(value) for value in review_index.index]
        selected = st.selectbox(
            "Code to highlight",
            code_ids,
            format_func=lambda value: str(review_index.loc[value, "code_name"]),
            key=f"{key}_edit_code",
        )
        review = review_index.loc[selected]
        state_prefix = f"{key}_{selected}_{excerpt_digest(excerpt)[:16]}"
        draft_key = f"{state_prefix}_draft"
        selected_rows = spans[spans["code_id"].eq(selected)] if not spans.empty else spans
        saved = normalize_passages(
            excerpt,
            [(int(row["start_offset"]), int(row["end_offset"])) for _, row in selected_rows.iterrows()],
        )
        if draft_key not in st.session_state:
            st.session_state[draft_key] = saved
        st.caption(
            "Copy the exact words that support this code. Add more than one passage if needed. "
            "This changes highlights only, not the excerpt or its assigned codes."
        )
        st.text_area(
            "Original excerpt (copy exact words)", excerpt,
            height=100, disabled=True, key=f"{state_prefix}_original",
        )
        phrase = st.text_area(
            "Exact words to highlight",
            height=75,
            key=f"{state_prefix}_phrase",
            help="Keep the original wording, punctuation and spaces. You can copy from the excerpt above.",
        )
        occurrences = exact_occurrences(excerpt, phrase)
        occurrence = None
        if occurrences:
            def occurrence_label(index: int) -> str:
                start, end = occurrences[index]
                context = excerpt[max(0, start - 25):min(len(excerpt), end + 25)].replace("\n", " ")
                return f"Occurrence {index + 1} - characters {start + 1} to {end}: {context}"

            occurrence = st.selectbox(
                "Which occurrence?",
                range(len(occurrences)),
                format_func=occurrence_label,
                key=f"{state_prefix}_occurrence_{excerpt_digest(phrase)[:12]}",
            )
        elif phrase:
            st.warning("Those exact words were not found. Check the wording, punctuation and spaces.")
        if st.button("Add passage", key=f"{state_prefix}_add", disabled=occurrence is None):
            st.session_state[draft_key] = normalize_passages(
                excerpt, [*st.session_state[draft_key], occurrences[occurrence]],
            )
            refresh()

        draft = st.session_state[draft_key]
        if draft:
            remove = st.multiselect(
                "Passages to remove",
                draft,
                format_func=lambda span: f"Characters {span[0] + 1} to {span[1]}: {excerpt[span[0]:span[1]]}",
                key=f"{state_prefix}_remove_selection",
            )
            if st.button("Remove selected passages", key=f"{state_prefix}_remove", disabled=not remove):
                st.session_state[draft_key] = [span for span in draft if span not in remove]
                refresh()
        else:
            st.caption("No passage selected. Nothing will be highlighted for this code yet.")
        status = st.radio(
            "Highlight review",
            ["reviewed", "needs_review"],
            index=0 if review["status"] == "reviewed" else 1,
            format_func=lambda value: "Reviewed" if value == "reviewed" else "Needs review",
            horizontal=True,
            key=f"{state_prefix}_status",
            help="Reviewed requires at least one exact passage. Needs review can be saved without a passage.",
        )
        note = st.text_area(
            "Highlight review note",
            str(review.get("review_note") or ""),
            height=75,
            key=f"{state_prefix}_note",
            help="Optional note about the evidence selection, separate from the excerpt interpretation.",
        )
        preview_review = {
            "code_id": int(selected), "code_name": str(review["code_name"]),
            "color": review["color"], "status": status, "review_note": note,
            "excerpt_sha256": excerpt_digest(excerpt),
        }
        preview_spans = [
            {**preview_review, "start_offset": start, "end_offset": end}
            for start, end in draft
        ]
        st.caption("Preview - unsaved passage selection")
        st.markdown(
            render_highlighted_excerpt(excerpt, preview_spans, [preview_review], display_colors=display_colors),
            unsafe_allow_html=True,
        )
        save, reset = st.columns(2)
        if save.button("Save highlights", type="primary", key=f"{state_prefix}_save"):
            if status == "reviewed" and not draft:
                st.error("Select at least one passage, or mark this code as Needs review.")
            else:
                try:
                    db.save_code_highlights(
                        unit_id, int(selected), draft, status=status, note=note,
                        expected_excerpt=excerpt,
                    )
                except ValueError as error:
                    st.error(str(error))
                else:
                    st.session_state.pop(draft_key, None)
                    refresh()
        if reset.button("Reset passage selection", key=f"{state_prefix}_reset"):
            st.session_state[draft_key] = saved
            refresh()


def render_excerpt_highlights(
    db: Database,
    meaning_unit_id: object,
    excerpt: str,
    key: str,
    *,
    in_dialog: bool = False,
    fallback_code_names: str = "",
) -> None:
    """Shared highlighted evidence display used by every coded-excerpt surface."""
    if meaning_unit_id is None or pd.isna(meaning_unit_id):
        st.markdown(f'<div class="coded-excerpt">{html.escape(excerpt)}</div>', unsafe_allow_html=True)
        if fallback_code_names:
            all_codes = db.codes(active_only=False)
            palette = code_display_colors(all_codes.to_dict("records"))
            colors = {str(row["name"]): palette[int(row["id"])] for _, row in all_codes.iterrows()}
            render_code_badges(
                fallback_code_names, colors, code_tooltip_lookup(all_codes), excerpt_tags=True,
            )
        st.caption("Passage highlights are available for saved coded excerpts.")
        return
    unit_id = int(meaning_unit_id)
    spans = db.code_highlights(unit_id)
    reviews = db.highlight_reviews(unit_id)
    all_codes = db.codes(active_only=False)
    display_colors = code_display_colors(all_codes.to_dict("records"))
    span_rows = spans.to_dict("records")
    review_rows = reviews.to_dict("records")
    st.markdown(
        render_highlighted_excerpt(excerpt, span_rows, review_rows, display_colors=display_colors),
        unsafe_allow_html=True,
    )
    states = highlight_review_states(excerpt, span_rows, review_rows)
    names = [str(row["code_name"]) for row in review_rows]
    colors = {str(row["code_name"]): display_colors.get(int(row["code_id"]), row["color"]) for row in review_rows}
    review_lookup = {str(row["code_name"]): states.get(int(row["code_id"]), {}) for row in review_rows}
    render_code_badges(
        " | ".join(names), colors, code_tooltip_lookup(all_codes),
        review_lookup=review_lookup, excerpt_tags=True,
    )
    render_highlight_editor(
        db, unit_id, excerpt, spans, reviews, key,
        in_dialog=in_dialog, display_colors=display_colors,
    )


@st.dialog("Code color", on_dismiss="rerun")
def render_code_color_dialog(db: Database, code: pd.Series) -> None:
    if not edit_mode_enabled():
        return
    name = str(code["name"])
    current_color = str(code["color"] or suggested_code_color(name))
    picker_key = f"working_code_color_value_{int(code['id'])}"

    def save_selected_color() -> None:
        if edit_mode_enabled():
            db.update_code_color(int(code["id"]), str(st.session_state[picker_key]))

    selected_color = str(st.session_state.get(picker_key, current_color))
    render_code_badges(name, {name: selected_color})
    st.color_picker(
        "Color",
        value=current_color,
        key=picker_key,
        label_visibility="collapsed",
        on_change=save_selected_color,
    )


def working_code_excerpt_catalog(
    codings: pd.DataFrame,
    code_id: int,
    labels: dict[str, str],
) -> pd.DataFrame:
    columns = [
        "meaning_unit_id",
        "response_id",
        "Respondent",
        "question_key",
        "Question",
        "excerpt",
        "note",
        "code_names",
    ]
    if codings.empty or "code_id" not in codings:
        return pd.DataFrame(columns=columns)

    prepared = codings.copy()
    prepared["code_id"] = pd.to_numeric(prepared["code_id"], errors="coerce")
    prepared["response_id"] = prepared["response_id"].astype(str)
    prepared["question_key"] = prepared["question_key"].astype(str)
    prepared["excerpt"] = prepared["excerpt"].fillna("").astype(str)
    selected = prepared[
        prepared["code_id"].eq(int(code_id))
        & prepared["excerpt"].str.strip().ne("")
    ].copy()
    if selected.empty:
        return pd.DataFrame(columns=columns)

    identity = ["response_id", "question_key", "excerpt"]
    code_names = (
        prepared[prepared["excerpt"].str.strip().ne("")]
        .groupby(identity, dropna=False)["code_name"]
        .agg(
            lambda values: " | ".join(
                dict.fromkeys(
                    str(value).strip()
                    for value in values
                    if str(value).strip()
                    and str(value).strip().casefold() != "nan"
                )
            )
        )
        .rename("code_names")
        .reset_index()
    )
    selected = selected.sort_values(
        [
            column
            for column in ["question_key", "response_id", "meaning_unit_id", "id"]
            if column in selected
        ],
        kind="stable",
    ).drop_duplicates(subset=identity, keep="first")
    selected = selected.merge(code_names, on=identity, how="left")
    selected["Respondent"] = selected["response_id"].map(
        lambda value: respondent_label(value, labels)
    )
    selected["Question"] = selected["question_key"].map(
        lambda key: FIELD_BY_KEY[key].label
        if key in FIELD_BY_KEY
        else sentence_case_option(key)
    )
    if "meaning_unit_id" not in selected:
        selected["meaning_unit_id"] = pd.NA
    if "note" not in selected:
        selected["note"] = ""
    selected["_respondent_order"] = (
        selected["Respondent"].str.extract(r"(\d+)")[0].fillna("0").astype(int)
    )
    question_order = {
        field.key: index for index, field in enumerate(OPEN_TEXT_FIELDS)
    }
    selected["_question_order"] = (
        selected["question_key"]
        .map(question_order)
        .fillna(len(question_order))
        .astype(int)
    )
    return selected.sort_values(
        ["_question_order", "_respondent_order", "excerpt"],
        kind="stable",
    )[columns].reset_index(drop=True)


@st.dialog("Working code and excerpts", width="large")
def render_working_code_details_dialog(db: Database, code: pd.Series) -> None:
    name = str(code.get("name", code.get("Working code", "Working code")))
    color = str(code["color"] or suggested_code_color(name))
    render_code_badges(name, {name: color})
    respondents = int(code.get("Respondents", 0))
    excerpts = int(code.get("Excerpts", 0))
    st.caption(
        f"{respondents} respondent{'s' if respondents != 1 else ''} · "
        f"{excerpts} coded excerpt{'s' if excerpts != 1 else ''}"
    )
    st.markdown("**Definition**")
    st.write(str(code.get("description", code.get("Definition", ""))).strip() or "—")
    st.markdown("**Include when**")
    st.write(str(code.get("inclusion_criteria", "")).strip() or "—")
    st.markdown("**Exclude when**")
    st.write(str(code.get("exclusion_criteria", "")).strip() or "—")

    st.divider()
    st.subheader("Coded excerpts")
    catalog = working_code_excerpt_catalog(
        db.codings(),
        int(code["id"]),
        database_respondent_labels(db),
    )
    if catalog.empty:
        st.info("No coded excerpts currently use this working code.")
        return

    question_options = [
        "All questions",
        *catalog["Question"].drop_duplicates().tolist(),
    ]
    filter_col, search_col = st.columns([1, 1.5], gap="medium")
    selected_question = filter_col.selectbox(
        "Question",
        question_options,
        key=f"working_code_excerpt_question_{int(code['id'])}",
    )
    search_text = search_col.text_input(
        "Search excerpts",
        placeholder="Search exact excerpts or interpretations",
        key=f"working_code_excerpt_search_{int(code['id'])}",
    ).strip()

    filtered = catalog.copy()
    if selected_question != "All questions":
        filtered = filtered[filtered["Question"].eq(selected_question)]
    if search_text:
        searchable = (
            filtered["excerpt"].fillna("").astype(str)
            + " "
            + filtered["note"].fillna("").astype(str)
        )
        filtered = filtered[
            searchable.str.contains(search_text, case=False, regex=False)
        ]

    st.caption(
        f"Showing {len(filtered)} of {len(catalog)} excerpt"
        f"{'s' if len(catalog) != 1 else ''}."
    )
    if filtered.empty:
        st.info("No excerpts match the current filters.")
        return

    for _, item in filtered.iterrows():
        with st.container(border=True):
            render_respondent_heading(
                item["response_id"], str(item["Respondent"]),
                evidence_question_badge(item["Question"]),
                key=f"code_{int(code['id'])}_{item['meaning_unit_id']}",
                origin={"dialog_code_id": int(code["id"]), "label": f"{name.split(' - ', 1)[0]} excerpts"},
            )
            render_excerpt_highlights(
                db, item["meaning_unit_id"], str(item["excerpt"]),
                f"code_popup_{int(code['id'])}_{item['meaning_unit_id']}",
                in_dialog=True,
                fallback_code_names=str(item["code_names"]),
            )
            note = "" if pd.isna(item["note"]) else str(item["note"]).strip()
            if note:
                st.markdown("**Interpretation**")
                st.write(note)


def require_data(db: Database) -> pd.DataFrame | None:
    frame = db.active_data()
    if frame.empty:
        st.info("No active response snapshot yet. Start on **Upload & data health** and activate a Google Forms export.")
        return None
    return apply_background_category_mappings(frame, db.background_mappings())


def apply_background_category_mappings(frame: pd.DataFrame, mappings: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or mappings.empty:
        return frame
    mapped = frame.copy()
    for field in BACKGROUND_FIELDS:
        if field.key not in mapped:
            continue
        field_mappings = mappings[mappings["field_key"] == field.key]
        if field_mappings.empty:
            continue
        lookup = {
            normalize_text(row["source_value"]): str(row["canonical_value"]).strip()
            for _, row in field_mappings.iterrows()
        }
        if field.kind == "multi":
            def map_multi_value(value: object) -> object:
                if pd.isna(value):
                    return value
                categories = [lookup.get(normalize_text(category), category) for category in split_multi(value)]
                return "; ".join(dict.fromkeys(categories))

            mapped[field.key] = mapped[field.key].map(map_multi_value)
        else:
            mapped[field.key] = mapped[field.key].map(
                lambda value: value
                if pd.isna(value)
                else lookup.get(normalize_text(value), value)
            )
    return mapped


def render_upload(db: Database) -> None:
    page_header(
        "Upload & data health",
        "Validate a Google Forms Excel export before activating it as the current analysis snapshot. Earlier snapshots remain in SQLite.",
    )
    st.markdown(
        '<div class="privacy-note"><strong>Privacy default:</strong> optional follow-up emails are separated from analysis data and never appear in dashboards or exports.</div>',
        unsafe_allow_html=True,
    )
    active_count = db.active_count()
    history = db.import_history()
    c1, c2, c3 = st.columns(3)
    c1.metric("Active responses", active_count)
    c2.metric("Saved snapshots", len(history))
    c3.metric("Questionnaire fields", 57)

    uploaded = None
    if edit_mode_enabled():
        uploaded = st.file_uploader("Current Google Forms export", type=["xlsx"], help="Upload a compatible .xlsx export or a workbook using the example template.")
    else:
        st.caption("Enable Edit mode to upload and activate a new snapshot.")
    if uploaded is not None:
        fingerprint = f"{IMPORT_PIPELINE_VERSION}:{uploaded.name}:{uploaded.size}"
        if st.session_state.get("preview_fingerprint") != fingerprint:
            with st.spinner("Reading and validating the workbook…"):
                st.session_state["import_preview"] = preview_workbook(uploaded.getvalue(), uploaded.name)
                st.session_state["preview_fingerprint"] = fingerprint
        preview: ImportPreview = st.session_state["import_preview"]
        if preview.errors:
            for error in preview.errors:
                st.error(error)
        else:
            assert preview.frame is not None
            st.success(f"Recognized {len(preview.mapping)} questionnaire columns and {len(preview.frame)} response rows.")
            for warning in preview.warnings:
                st.warning(warning)
            prior = db.active_hashes()
            incoming = dict(zip(preview.frame["response_id"], preview.frame["row_hash"]))
            new_ids = incoming.keys() - prior.keys()
            removed_ids = prior.keys() - incoming.keys()
            changed_ids = {key for key in incoming.keys() & prior.keys() if incoming[key] != prior[key]}
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Rows in file", len(incoming))
            d2.metric("New", len(new_ids))
            d3.metric("Changed", len(changed_ids))
            d4.metric("Absent vs active", len(removed_ids))
            with st.expander("Validation details"):
                st.write(f"File fingerprint: `{preview.source_file_hash[:16]}…`")
                st.write(f"Importer version: `{IMPORT_PIPELINE_VERSION}`")
                st.write(f"Mapped columns: {len(preview.mapping)}")
                if preview.unexpected_columns:
                    st.write("Unmapped columns:", preview.unexpected_columns)
                preview_display = replace_response_ids(
                    preview.frame.drop(columns=["followup_email"], errors="ignore").head(8),
                    respondent_labels_for_frame(preview.frame),
                )
                st.dataframe(
                    preview_display,
                    width="stretch",
                    hide_index=True,
                )
            duplicate = db.import_exists(preview.file_hash)
            shrinking = active_count > 0 and len(preview.frame) < active_count
            confirmed = True
            if shrinking:
                confirmed = st.checkbox(
                    "I understand this file has fewer responses than the active snapshot and want to activate it anyway."
                )
            if st.button("Activate validated snapshot", type="primary", disabled=duplicate or not confirmed):
                result = db.activate_import(preview)
                st.session_state.pop("import_preview", None)
                st.session_state.pop("preview_fingerprint", None)
                st.success(
                    f"Snapshot {result['import_id']} activated: {result['inserted']} new, "
                    f"{result['updated']} changed, {result['unchanged']} unchanged."
                )
                st.rerun()
            if duplicate:
                st.info("This exact workbook is already in the import history; no duplicate snapshot will be created.")

    st.subheader("Import history")
    if history.empty:
        st.caption("No imports yet.")
    else:
        display = history.drop(columns=["warnings_json"], errors="ignore").copy()
        display["is_active"] = display["is_active"].map({1: "Active", 0: "Archived"})
        st.dataframe(display, width="stretch", hide_index=True)


def render_overview(db: Database) -> None:
    page_header(
        "Overview",
        "Review response coverage, background composition, and construct-level ratings. Treat findings as exploratory while the sample remains small.",
    )
    frame = require_data(db)
    if frame is None:
        return
    summary = construct_summary(frame)
    c1, c2 = st.columns(2)
    c1.metric("Responses in view", len(frame))
    c2.metric("Rated constructs", len(CONSTRUCTS))
    if len(frame) < 30:
        st.warning("The current sample is small. Report distributions and effect sizes, avoid broad population claims, and interpret p-values cautiously.")
    left, right = st.columns([1.35, 1])
    with left:
        ordered_summary = summary.sort_values("mean")
        chart = px.bar(
            ordered_summary,
            x="mean",
            y="construct",
            orientation="h",
            error_x="sd",
            range_x=[1, 5],
            labels={"mean": "Mean rating (1–5)", "construct": ""},
            color="construct",
            color_discrete_map=CONSTRUCT_COLORS,
            title="Construct ratings",
        )
        chart.update_layout(height=430, plot_bgcolor="white", paper_bgcolor="white", showlegend=False)
        st.plotly_chart(chart, width="stretch")
    with right:
        institution = frame["institution_type"].fillna("Missing").value_counts().reset_index()
        institution.columns = ["Institution", "Responses"]
        fig = px.bar(
            institution,
            x="Institution",
            y="Responses",
            color="Institution",
            text="Responses",
            title="Institution mix",
            color_discrete_sequence=CHART_PALETTE[1:],
        )
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(
            height=430,
            plot_bgcolor="white",
            paper_bgcolor="white",
            showlegend=False,
            xaxis_title="",
            yaxis_title="Responses",
        )
        fig.update_xaxes(tickangle=-20)
        fig.update_yaxes(dtick=1, rangemode="tozero")
        st.plotly_chart(fig, width="stretch")
    st.subheader("PjBL experience by activity")
    st.plotly_chart(
        pjbl_experience_figure(frame), width="stretch", theme=None,
        config=EXPERIENCE_EXPORT_CONFIG, key="pjbl_experience_chart",
    )
    st.caption(
        "Colours distinguish all four experience levels. Labels show the combined "
        "percentage on each side. Adoption refers to projects developed by others."
    )
    st.subheader("Construct summary")
    st.dataframe(summary.round(3), width="stretch", hide_index=True)


def render_individual_responses(db: Database) -> None:
    page_header(
        "Individual responses",
        "Select an anonymous respondent to review their background, ratings, and open-ended answers together.",
    )
    frame = require_data(db)
    if frame is None:
        return

    labels = database_respondent_labels(db)
    active_records = [
        (respondent_label(response_id, labels), str(response_id))
        for response_id in frame["response_id"].astype(str)
    ]

    def label_order(item: tuple[str, str]) -> tuple[int, str]:
        label = item[0]
        try:
            return int(label.removeprefix("R")), label
        except ValueError:
            return 10**9, label

    active_records.sort(key=label_order)
    response_ids = {label: response_id for label, response_id in active_records}
    response_labels = list(response_ids)
    ordered_ids = list(response_ids.values())
    selection_key = "individual_response_selection"
    # Stable IDs keep navigation correct even when some R numbers are inactive.
    selected = st.session_state.get(selection_key)
    if selected in response_ids:  # Upgrade a selection from the earlier UI.
        st.session_state[selection_key] = response_ids[selected]
    elif selected is None:
        st.session_state[selection_key] = ordered_ids[0]
    elif selected not in ordered_ids:
        st.warning("This respondent is not available in the active snapshot. Use Back to return to your previous view.")
        if st.button("Choose an available respondent", key="individual_response_choose_available"):
            st.session_state.pop(selection_key, None)
            st.rerun()
        return

    def move_selection(offset: int) -> None:
        current = st.session_state.get(selection_key, ordered_ids[0])
        index = ordered_ids.index(current) if current in ordered_ids else 0
        st.session_state[selection_key] = ordered_ids[
            max(0, min(len(ordered_ids) - 1, index + offset))
        ]

    current_index = ordered_ids.index(st.session_state[selection_key])
    previous_col, select_col, position_col, next_col = st.columns([1, 2.4, 1, 1])
    previous_col.button(
        "← Previous",
        key="individual_response_previous",
        on_click=move_selection,
        args=(-1,),
        disabled=current_index == 0,
        width="stretch",
    )
    selected_id = select_col.selectbox(
        "Respondent",
        ordered_ids,
        format_func=lambda response_id: respondent_label(response_id, labels),
        key=selection_key,
    )
    position_col.markdown(
        f'<div class="response-position">{current_index + 1} of {len(response_labels)}</div>',
        unsafe_allow_html=True,
    )
    next_col.button(
        "Next →",
        key="individual_response_next",
        on_click=move_selection,
        args=(1,),
        disabled=current_index == len(response_labels) - 1,
        width="stretch",
    )

    selected_label = respondent_label(selected_id, labels)
    selected_rows = frame[frame["response_id"].astype(str) == selected_id]
    if selected_rows.empty:
        st.error("This respondent is not available in the active snapshot.")
        return
    row = selected_rows.iloc[0]
    sections = respondent_construct_sections(row)
    rated_count = sum(int(section["answered"]) for section in sections)
    answered_text_count = sum(
        pd.notna(row.get(field.key)) and bool(str(row.get(field.key)).strip())
        for field in OPEN_TEXT_FIELDS
    )
    submitted = pd.to_datetime(row.get("timestamp"), errors="coerce")
    submitted_text = (
        f"Submitted {submitted.strftime('%B %d, %Y at %I:%M %p')}"
        if pd.notna(submitted)
        else "Submission time unavailable"
    )
    st.markdown(
        '<div class="individual-response-summary">'
        f'{respondent_badge(selected_label)}'
        f'<span class="individual-response-summary-text">{html.escape(submitted_text)}</span>'
        f'<span class="individual-response-summary-text">{rated_count} of {len(ITEM_FIELDS)} ratings answered</span>'
        f'<span class="individual-response-summary-text">{answered_text_count} of {len(OPEN_TEXT_FIELDS)} open-ended questions answered</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    ratings_panel, details_panel = st.columns([3.25, 1.4], gap="large")
    with ratings_panel:
        st.subheader("Ratings")
        for section in sections:
            mean = section["mean"]
            mean_text = f'Mean {float(mean):.2f}/5' if mean is not None else "No ratings"
            rows = []
            for rating in section["ratings"]:
                score = rating["score"]
                if score is None:
                    value_markup = (
                        '<span class="individual-rating-value individual-rating-missing">Not rated</span>'
                    )
                else:
                    numeric_score = int(float(score))
                    color = SCORE_COLORS.get(numeric_score, "#c6c6c6")
                    text_color = "#ffffff" if numeric_score in {1, 5} else "#161616"
                    value_markup = (
                        '<span class="individual-rating-value" '
                        f'style="--rating-color:{color};--rating-text:{text_color};background:{color}">'
                        f'{html.escape(str(rating["label"]))} · {float(score):.0f}/5</span>'
                    )
                rows.append(
                    '<div class="individual-rating-row">'
                    f'<span class="individual-rating-item">{html.escape(str(rating["item"]))}</span>'
                    f'{value_markup}</div>'
                )
            st.markdown(
                '<div class="individual-section">'
                '<div class="individual-section-heading">'
                f'<span class="individual-section-title">{html.escape(str(section["construct"]))}</span>'
                f'<span class="individual-section-stat">{html.escape(mean_text)}</span>'
                '</div>'
                f'{"".join(rows)}</div>',
                unsafe_allow_html=True,
            )

    with details_panel:
        background_rows = []
        for field in BACKGROUND_FIELDS:
            value = response_background_value(field, row.get(field.key))
            background_rows.append(
                '<div class="individual-profile-row">'
                f'<div class="individual-profile-label">{html.escape(field.label)}</div>'
                f'<div class="individual-profile-value">{html.escape(value)}</div>'
                '</div>'
            )
        st.markdown(
            '<div class="individual-profile">'
            '<div class="individual-profile-title">Background</div>'
            f'{"".join(background_rows)}</div>',
            unsafe_allow_html=True,
        )

        st.subheader("Open-ended responses")
        for field in OPEN_TEXT_FIELDS:
            value = row.get(field.key)
            has_response = pd.notna(value) and bool(str(value).strip())
            answer = str(value).strip() if has_response else "No response"
            answer_class = "individual-text-answer" if has_response else "individual-text-answer individual-text-empty"
            st.markdown(
                '<div class="individual-text-card">'
                f'<div class="individual-text-question">{html.escape(field.label)}</div>'
                f'<div class="{answer_class}">{html.escape(answer)}</div>'
                '</div>',
                unsafe_allow_html=True,
            )


def render_items(db: Database) -> None:
    page_header(
        "Items & scales",
        "Inspect Likert distributions, descriptive statistics, internal consistency, and item–total relationships for each proposed construct.",
    )
    frame = require_data(db)
    if frame is None:
        return
    full_summary = item_summary(frame)
    construct_statistics = construct_summary(frame).set_index("construct")
    main_panel, side_panel = st.columns([3.8, 1.15], gap="large")
    controls = side_panel.container(border=True)
    construct = controls.selectbox(
        "Construct",
        CONSTRUCTS,
        format_func=sentence_case_option,
        key="items_scale_construct",
    )
    alpha = construct_statistics.loc[construct, "alpha"]
    controls.metric(
        "Cronbach’s α",
        fmt(alpha, 3),
        help="Computed using complete cases for the selected construct.",
    )
    with controls.expander("Reliability note"):
        if pd.isna(alpha):
            st.write("Not enough complete cases or variation to estimate alpha.")
        elif alpha < 0.70:
            st.write("Below the common .70 reference point. Review the item–total correlations.")
        else:
            st.write("Meets the common .70 reference point.")

    dist = likert_distribution(frame, construct)
    with main_panel:
        if not dist.empty:
            scale = FIELD_BY_KEY[str(dist.iloc[0]["key"])].scale or "agreement"
            fig = divergent_likert_figure(dist, construct, scale)
            st.plotly_chart(fig, width="stretch")
        selected = full_summary[full_summary["construct"] == construct].drop(columns=["key", "construct"])
        with st.expander("Item statistics"):
            st.dataframe(
                selected.round(3),
                width="stretch",
                hide_index=True,
                height=38 + 35 * len(selected),
            )
        with st.expander("Corrected item–total correlations"):
            correlations = corrected_item_total(frame, construct).round(3)
            st.dataframe(
                correlations,
                width="stretch",
                hide_index=True,
                height=38 + 35 * len(correlations),
            )


def background_category_label(field: object, value: object) -> str:
    if field.key == "course_levels":
        # One-to-one display aliases also preserve existing saved group labels.
        return {
            "Introductory undergraduate": "Introductory",
            "Intermediate undergraduate": "Intermediate",
            "Advanced undergraduate": "Advanced",
        }.get(str(value), str(value))
    if field.key == "years_experience":
        try:
            score = float(value)
        except (TypeError, ValueError):
            return str(value)
        return {
            0.0: "Beginner (≤5 years)",
            1.0: "Intermediate (6–10 years)",
            2.0: "Experienced (11+ years)",
        }.get(score, str(value))
    if field.scale == "experience":
        try:
            score = float(value)
        except (TypeError, ValueError):
            return str(value)
        return {
            0.0: "None",
            1.0: "Limited",
            2.0: "Moderate",
            3.0: "Extensive",
        }.get(score, str(value))
    return str(value)


def background_frequency(frame: pd.DataFrame, field: object) -> pd.DataFrame:
    if field.kind == "multi":
        populated = frame[field.key].dropna().map(split_multi).explode().dropna()
        counts = populated.value_counts().rename_axis("category").reset_index(name="responses")
        missing = int(frame[field.key].isna().sum())
        if missing:
            counts = pd.concat(
                [counts, pd.DataFrame([{"category": "Missing", "responses": missing}])],
                ignore_index=True,
            )
    else:
        values = frame[field.key].copy()
        values = values.map(
            lambda value: value if pd.isna(value) else background_category_label(field, value)
        )
        counts = values.fillna("Missing").value_counts().rename_axis("category").reset_index(name="responses")

    expected_categories: list[str] = []
    if field.scale == "experience":
        expected_categories = ["None", "Limited", "Moderate", "Extensive"]
    elif field.key == "years_experience":
        expected_categories = [
            "Beginner (≤5 years)",
            "Intermediate (6–10 years)",
            "Experienced (11+ years)",
        ]
    else:
        expected_categories = list(BACKGROUND_CATEGORY_OPTIONS.get(field.key, ()))

    observed = set(counts["category"].astype(str))
    zero_categories = [
        category for category in expected_categories if category not in observed
    ]
    if zero_categories:
        counts = pd.concat(
            [
                counts,
                pd.DataFrame(
                    {
                        "category": zero_categories,
                        "responses": [0] * len(zero_categories),
                    }
                ),
            ],
            ignore_index=True,
        )
    return counts.sort_values(["responses", "category"], ascending=[False, True])


def background_display_label(field: object) -> str:
    return {
        "roles": "Roles in computing education",
        "computing_areas": "PjBL computing areas",
    }.get(field.key, field.label)


def observed_background_categories(frame: pd.DataFrame, field: object) -> pd.Series:
    values = frame[field.key].dropna()
    if field.kind == "multi":
        values = values.map(split_multi).explode().dropna()
    values = values.astype(str).str.strip()
    values = values[values.ne("")]
    return values.value_counts()


def render_background_frequency_panel(
    frame: pd.DataFrame,
    field: object,
    panel: object,
) -> None:
    panel.markdown("**Frequency**")
    panel.caption(background_display_label(field))
    counts = background_frequency(frame, field)
    rows = "".join(
        f'<div class="frequency-row"><span class="frequency-label">{html.escape(str(row["category"]))}</span>'
        f'<span class="frequency-count">{int(row["responses"])}</span></div>'
        for _, row in counts.iterrows()
    )
    panel.markdown(
        f'<div class="frequency-list">{rows}</div>',
        unsafe_allow_html=True,
    )
    if field.kind == "multi":
        panel.caption("Multi-select totals can exceed the number of respondents.")


def render_background_mapping_panel(
    db: Database,
    raw_frame: pd.DataFrame,
    field: object,
    panel: object,
) -> None:
    if not edit_mode_enabled() or field.kind not in {"category", "multi"}:
        return
    with panel.expander("Manage categories"):
        st.caption(background_display_label(field))
        counts = observed_background_categories(raw_frame, field)
        if counts.empty:
            st.caption("No categories are available for this question.")
            return

        mappings = db.background_mappings(field.key)
        mapping_lookup = (
            {
                normalize_text(row["source_value"]): str(row["canonical_value"])
                for _, row in mappings.iterrows()
            }
            if not mappings.empty
            else {}
        )
        configured = list(BACKGROUND_CATEGORY_OPTIONS.get(field.key, ()))
        configured_keys = {normalize_text(value) for value in configured}
        raw_categories = counts.index.astype(str).tolist()
        custom_categories = [
            value for value in raw_categories if normalize_text(value) not in configured_keys
        ]
        standard_categories = [value for value in raw_categories if value not in custom_categories]
        source_options = [*custom_categories, *standard_categories]

        category_table = pd.DataFrame(
            {
                "Raw category": raw_categories,
                "Analysis category": [
                    mapping_lookup.get(normalize_text(value), value) for value in raw_categories
                ],
                "Responses": [int(counts[value]) for value in raw_categories],
            }
        )
        st.dataframe(
            category_table,
            width="stretch",
            hide_index=True,
            height=38 + 35 * len(category_table),
            column_config={"Responses": st.column_config.NumberColumn(format="%d", width="small")},
        )

        source_value = st.selectbox(
            "Raw category",
            source_options,
            format_func=lambda value: f"{sentence_case_option(value)} ({int(counts[value])})",
            key=f"background_mapping_source_{field.key}",
        )
        current_destination = mapping_lookup.get(normalize_text(source_value), source_value)
        saved_destinations = mappings["canonical_value"].astype(str).tolist() if not mappings.empty else []
        destination_candidates = [
            *configured,
            *saved_destinations,
            *raw_categories,
            current_destination,
        ]
        destinations = list(dict.fromkeys(value for value in destination_candidates if value.strip()))
        create_new = "Create new category…"
        destination_value = st.selectbox(
            "Analysis category",
            [*destinations, create_new],
            index=destinations.index(current_destination),
            format_func=sentence_case_option,
            key=f"background_mapping_destination_{field.key}_{normalize_text(source_value)}",
        )
        if destination_value == create_new:
            destination_value = st.text_input(
                "New category",
                key=f"background_mapping_new_{field.key}_{normalize_text(source_value)}",
            ).strip()

        save_col, remove_col = st.columns(2)
        if save_col.button(
            "Save mapping",
            type="primary",
            width="stretch",
            key=f"save_background_mapping_{field.key}_{normalize_text(source_value)}",
        ):
            if destination_value:
                db.save_background_mapping(field.key, source_value, destination_value)
                st.rerun()
            else:
                st.error("Enter a category name.")
        has_mapping = normalize_text(source_value) in mapping_lookup
        if remove_col.button(
            "Remove",
            width="stretch",
            disabled=not has_mapping,
            key=f"remove_background_mapping_{field.key}_{normalize_text(source_value)}",
        ):
            db.delete_background_mapping(field.key, source_value)
            st.rerun()


def custom_background_memberships(
    frame: pd.DataFrame,
    field: object,
) -> tuple[pd.Series, pd.DataFrame]:
    """Return respondent categories and the categories available to group."""
    if field.key == "years_experience" or field.scale == "experience":
        ranked = ordinal_background_scores(frame, field.key)
        memberships = ranked.map(
            lambda value: ()
            if pd.isna(value)
            else (background_category_label(field, value),)
        )
        if field.key == "years_experience":
            expected = [background_category_label(field, value) for value in (0, 1, 2)]
        else:
            expected = [background_category_label(field, value) for value in (0, 1, 2, 3)]
    elif field.kind == "multi":
        memberships = frame[field.key].map(
            lambda value: tuple(
                background_category_label(field, category)
                for category in split_multi(value)
                if normalize_text(category) not in NOT_APPLICABLE_VALUES
            )
            if pd.notna(value)
            else ()
        )
        expected = [
            background_category_label(field, category)
            for category in BACKGROUND_CATEGORY_OPTIONS.get(field.key, ())
            if normalize_text(category) not in NOT_APPLICABLE_VALUES
        ]
    else:
        memberships = frame[field.key].map(
            lambda value: ()
            if pd.isna(value) or normalize_text(value) in NOT_APPLICABLE_VALUES
            else (background_category_label(field, value),)
        )
        expected = [
            category
            for category in BACKGROUND_CATEGORY_OPTIONS.get(field.key, ())
            if normalize_text(category) not in NOT_APPLICABLE_VALUES
        ]

    observed = memberships.explode().dropna().astype(str)
    observed = observed[observed.str.strip().ne("")]
    counts = observed.value_counts()
    categories = list(dict.fromkeys([*expected, *counts.index.astype(str).tolist()]))
    category_table = pd.DataFrame(
        {
            "Category": categories,
            "Responses": [int(counts.get(category, 0)) for category in categories],
        }
    )
    return memberships, category_table


def render_saved_background_grouping(
    db: Database,
    field: object,
    memberships: pd.Series,
    categories: pd.DataFrame,
    saved_by_id: dict,
) -> pd.Series | None:
    """Use saved groups without changing their definitions or persisted selection."""
    if not saved_by_id:
        st.caption("No saved groupings. Enable Edit mode to create one.")
        return None

    prefix = f"custom_group_{field.key}"
    selection_key = f"{prefix}_view_saved_selection"
    saved_options = [int(value) for value in saved_by_id]
    remembered = st.session_state.get(
        f"{prefix}_view_selection",
        st.session_state.get(
            f"{prefix}_saved_selection", db.selected_background_grouping(field.key)
        ),
    )
    if (
        st.session_state.get(selection_key) not in saved_options
        or remembered in saved_options and st.session_state.get(selection_key) != remembered
    ):
        st.session_state[selection_key] = (
            int(remembered) if remembered in saved_options else saved_options[0]
        )

    def remember_selection() -> None:
        selected = int(st.session_state[selection_key])
        st.session_state[f"{prefix}_view_selection"] = selected
        st.session_state[f"{prefix}_pending_selection"] = selected

    selected_id = st.selectbox(
        "Saved grouping",
        saved_options,
        format_func=lambda value: str(saved_by_id[int(value)]["name"]),
        key=selection_key,
        on_change=remember_selection,
    )
    st.session_state[f"{prefix}_view_selection"] = int(selected_id)
    saved_groups = list(saved_by_id[int(selected_id)].get("groups", []))
    names = [str(group.get("name", "")).strip() for group in saved_groups]
    if not 2 <= len(names) <= 5 or any(not name for name in names):
        st.warning("This grouping needs two to five named groups. Enable Edit mode to update it.")
        return None
    if len({normalize_text(name) for name in names}) != len(names):
        st.warning("Custom group names must be different. Enable Edit mode to update them.")
        return None

    available = set(categories["Category"].astype(str))
    category_to_group = {
        str(category): name
        for name, group in zip(names, saved_groups)
        for category in group.get("categories", [])
        if str(category) in available
    }
    unavailable = sorted(
        {
            str(category)
            for group in saved_groups
            for category in group.get("categories", [])
        }
        - available
    )
    with st.expander("Grouping details"):
        display = categories.copy()
        display["Group"] = display["Category"].map(category_to_group).fillna("Exclude")
        st.dataframe(display, width="stretch", hide_index=True)
        if unavailable:
            st.caption(
                f"{len(unavailable)} saved categor{'y is' if len(unavailable) == 1 else 'ies are'} "
                "not present in the current data and will remain unused."
            )
    if any(name not in category_to_group.values() for name in names):
        st.info("Every custom group needs an available background category. Enable Edit mode to update this grouping.")
        return None

    assignments = assign_custom_groups(memberships, category_to_group)
    group_sizes = assignments["group"].value_counts()
    overlap_count = int(assignments["status"].eq("Overlap").sum())
    unassigned_count = int(assignments["status"].eq("Unassigned").sum())
    size_text = " · ".join(f"{name}: {int(group_sizes.get(name, 0))}" for name in names)
    st.markdown(f"**Respondents assigned:** {size_text}")
    exclusions = []
    if overlap_count:
        exclusions.append(f"{overlap_count} matched more than one group")
    if unassigned_count:
        exclusions.append(f"{unassigned_count} unassigned")
    if exclusions:
        st.caption("Excluded: " + " · ".join(exclusions))
    if field.kind == "multi":
        st.caption(
            "For this multi-select background, a respondent matching categories in more than one custom group is excluded so the groups remain independent."
        )
    too_small = [name for name in names if int(group_sizes.get(name, 0)) < 2]
    if too_small:
        st.warning(
            "Each analyzed group needs at least two respondents. Increase or combine: "
            + ", ".join(too_small)
            + "."
        )
        return None
    small = [name for name in names if int(group_sizes.get(name, 0)) < 5]
    if small:
        st.warning("Small custom groups make the analysis exploratory: " + ", ".join(small) + ".")
    return assignments["group"]


def render_custom_group_builder(
    db: Database,
    frame: pd.DataFrame,
    field: object,
) -> pd.Series | None:
    memberships, categories = custom_background_memberships(frame, field)
    if categories.empty:
        st.info("No background categories are available to group.")
        return None

    prefix = f"custom_group_{field.key}"
    saved_groupings = db.background_groupings(field.key)
    saved_by_id = (
        saved_groupings.set_index("id").to_dict(orient="index")
        if not saved_groupings.empty
        else {}
    )
    if not edit_mode_enabled():
        return render_saved_background_grouping(db, field, memberships, categories, saved_by_id)
    selection_key = f"{prefix}_saved_selection"
    label_selection = st.session_state.get(
        f"{prefix}_pending_selection",
        st.session_state.get(
            selection_key,
            st.session_state.get(
                f"{prefix}_active_selection", db.selected_background_grouping(field.key) or 0
            ),
        ),
    )
    try:
        label_selection = int(label_selection)
    except (TypeError, ValueError):
        label_selection = 0
    active_grouping_name = (
        str(saved_by_id[label_selection]["name"])
        if label_selection in saved_by_id
        else "New grouping"
    )
    builder = st.expander(
        f"Grouping setup · {active_grouping_name}",
        expanded=False,
    )
    with builder:
        saved_options = [0, *[int(value) for value in saved_groupings.get("id", [])]]
        pending_selection = st.session_state.pop(f"{prefix}_pending_selection", None)
        if pending_selection is not None:
            st.session_state[selection_key] = (
                int(pending_selection) if int(pending_selection) in saved_options else 0
            )
        elif selection_key not in st.session_state:
            remembered = st.session_state.get(
                f"{prefix}_active_selection", db.selected_background_grouping(field.key)
            )
            st.session_state[selection_key] = (
                int(remembered) if remembered in saved_by_id else 0
            )

        saved_col, delete_col = st.columns([3.3, 0.7], vertical_alignment="bottom")
        selected_saved_id = saved_col.selectbox(
            "Saved grouping",
            saved_options,
            format_func=lambda value: (
                "New grouping"
                if int(value) == 0
                else str(saved_by_id[int(value)]["name"])
            ),
            key=selection_key,
        )
        if int(selected_saved_id) != 0:
            st.session_state[f"{prefix}_view_selection"] = int(selected_saved_id)
        delete_clicked = delete_col.button(
            "Delete",
            disabled=int(selected_saved_id) == 0,
            width="stretch",
            key=f"{prefix}_delete",
        )
        if delete_clicked:
            db.delete_background_grouping(int(selected_saved_id))
            st.session_state[f"{prefix}_pending_selection"] = 0
            st.session_state[f"{prefix}_active_selection"] = -1
            st.session_state[f"{prefix}_message"] = "Saved grouping deleted."
            st.rerun()

        category_signature = abs(hash(tuple(categories["Category"].astype(str))))
        active_selection = int(st.session_state.get(f"{prefix}_active_selection", -1))
        saved_widget_state_missing = int(selected_saved_id) != 0 and (
            f"custom_group_count_{field.key}" not in st.session_state
            or f"custom_group_name_{field.key}_0" not in st.session_state
        )
        if active_selection != int(selected_saved_id) or saved_widget_state_missing:
            if int(selected_saved_id) == 0:
                st.session_state[f"custom_group_count_{field.key}"] = 2
                for index in range(5):
                    st.session_state.pop(f"custom_group_name_{field.key}_{index}", None)
                st.session_state[f"{prefix}_assignments"] = {}
                st.session_state[f"{prefix}_save_name"] = ""
                st.session_state.pop(f"{prefix}_loaded_id", None)
                st.session_state[f"{prefix}_editor_revision"] = int(
                    st.session_state.get(f"{prefix}_editor_revision", 0)
                ) + 1
            else:
                saved = saved_by_id[int(selected_saved_id)]
                saved_groups = list(saved.get("groups", []))
                st.session_state[f"custom_group_count_{field.key}"] = len(saved_groups)
                loaded_assignments: dict[str, str] = {}
                for index, group in enumerate(saved_groups):
                    group_id = f"Group {index + 1}"
                    st.session_state[f"custom_group_name_{field.key}_{index}"] = str(
                        group.get("name", group_id)
                    )
                    for category in group.get("categories", []):
                        loaded_assignments[str(category)] = group_id
                st.session_state[f"{prefix}_assignments"] = loaded_assignments
                st.session_state[f"{prefix}_editor_revision"] = int(
                    st.session_state.get(f"{prefix}_editor_revision", 0)
                ) + 1
                st.session_state[f"{prefix}_save_name"] = str(saved["name"])
                st.session_state[f"{prefix}_loaded_id"] = int(selected_saved_id)
                current_categories = set(categories["Category"].astype(str))
                unavailable = sorted(set(loaded_assignments) - current_categories)
                if unavailable:
                    st.session_state[f"{prefix}_load_warning"] = (
                        f"{len(unavailable)} saved categor{'y is' if len(unavailable) == 1 else 'ies are'} "
                        "not present in the current data and will remain unused."
                    )
            st.session_state[f"{prefix}_active_selection"] = int(selected_saved_id)

        message = st.session_state.pop(f"{prefix}_message", None)
        if message:
            st.success(str(message))
        load_warning = st.session_state.pop(f"{prefix}_load_warning", None)
        if load_warning:
            st.warning(str(load_warning))

        title_col, count_col = st.columns([3, 1], vertical_alignment="bottom")
        title_col.markdown("**Build custom groups**")
        group_count = count_col.selectbox(
            "Number of groups",
            [2, 3, 4, 5],
            key=f"custom_group_count_{field.key}",
        )
        group_ids = [f"Group {index + 1}" for index in range(group_count)]
        names: list[str] = []
        for start in range(0, group_count, 3):
            name_columns = st.columns(min(3, group_count - start))
            for offset, column in enumerate(name_columns):
                index = start + offset
                name_key = f"custom_group_name_{field.key}_{index}"
                if name_key not in st.session_state:
                    st.session_state[name_key] = group_ids[index]
                names.append(
                    column.text_input(
                        f"{group_ids[index]} name",
                        key=name_key,
                    ).strip()
                )

        assignment_table = categories.copy()
        draft_assignments = st.session_state.get(f"{prefix}_assignments", {})
        assignment_table["Assign to"] = assignment_table["Category"].map(
            lambda category: (
                str(draft_assignments.get(str(category), "Exclude"))
                if str(draft_assignments.get(str(category), "Exclude")) in group_ids
                else "Exclude"
            )
        )
        editor_revision = int(st.session_state.get(f"{prefix}_editor_revision", 0))
        edited = st.data_editor(
            assignment_table,
            width="stretch",
            hide_index=True,
            height=38 + 35 * len(assignment_table),
            disabled=["Category", "Responses"],
            key=(
                f"custom_group_assignments_{field.key}_{group_count}_"
                f"{category_signature}_{editor_revision}"
            ),
            column_config={
                "Category": st.column_config.TextColumn(width="large"),
                "Responses": st.column_config.NumberColumn(format="%d", width="small"),
                "Assign to": st.column_config.SelectboxColumn(
                    options=["Exclude", *group_ids],
                    required=True,
                    width="medium",
                ),
            },
        )
        st.session_state[f"{prefix}_assignments"] = {
            str(row["Category"]): str(row["Assign to"])
            for _, row in edited.iterrows()
            if str(row["Assign to"]) in group_ids
        }

        if any(not name for name in names):
            st.warning("Give every custom group a name.")
            return None
        if len({normalize_text(name) for name in names}) != len(names):
            st.warning("Custom group names must be different.")
            return None

        id_to_name = dict(zip(group_ids, names))
        selected_rows = edited[edited["Assign to"].isin(group_ids)]
        category_to_group = {
            str(row["Category"]): id_to_name[str(row["Assign to"])]
            for _, row in selected_rows.iterrows()
        }
        assigned_ids = set(selected_rows["Assign to"].astype(str))
        missing_groups = [group_id for group_id in group_ids if group_id not in assigned_ids]
        if missing_groups:
            st.info("Assign at least one background category to every custom group.")
            return None

        assignments = assign_custom_groups(memberships, category_to_group)
        group_sizes = assignments["group"].value_counts()
        overlap_count = int(assignments["status"].eq("Overlap").sum())
        unassigned_count = int(assignments["status"].eq("Unassigned").sum())
        size_text = " · ".join(
            f"{name}: {int(group_sizes.get(name, 0))}" for name in names
        )
        st.markdown(f"**Respondents assigned:** {size_text}")
        exclusions = []
        if overlap_count:
            exclusions.append(f"{overlap_count} matched more than one group")
        if unassigned_count:
            exclusions.append(f"{unassigned_count} unassigned")
        if exclusions:
            st.caption("Excluded: " + " · ".join(exclusions))
        if field.kind == "multi":
            st.caption(
                "For this multi-select background, a respondent matching categories in more than one custom group is excluded so the groups remain independent."
            )

        too_small = [name for name in names if int(group_sizes.get(name, 0)) < 2]
        if too_small:
            st.warning(
                "Each analyzed group needs at least two respondents. Increase or combine: "
                + ", ".join(too_small)
                + "."
            )
            return None
        small = [name for name in names if int(group_sizes.get(name, 0)) < 5]
        if small:
            st.warning(
                "Small custom groups make the analysis exploratory: " + ", ".join(small) + "."
            )

        groups_definition = [
            {
                "name": id_to_name[group_id],
                "categories": selected_rows.loc[
                    selected_rows["Assign to"].eq(group_id), "Category"
                ].astype(str).tolist(),
            }
            for group_id in group_ids
        ]
        grouping_name = st.text_input(
            "Grouping name",
            placeholder="For example, university versus other institutions",
            key=f"{prefix}_save_name",
        ).strip()
        save_col, update_col = st.columns(2)
        if save_col.button(
            "Save as new",
            type="primary",
            width="stretch",
            key=f"{prefix}_save_new",
        ):
            try:
                saved_id = db.save_background_grouping(
                    field.key,
                    grouping_name,
                    groups_definition,
                )
                db.select_background_grouping(field.key, saved_id)
                st.session_state[f"{prefix}_loaded_id"] = saved_id
                st.session_state[f"{prefix}_active_selection"] = saved_id
                st.session_state[f"{prefix}_pending_selection"] = saved_id
                st.session_state[f"{prefix}_message"] = f"Saved “{grouping_name}”."
                st.rerun()
            except ValueError as error:
                st.error(str(error))

        loaded_id = st.session_state.get(f"{prefix}_loaded_id")
        loaded_exists = loaded_id in saved_by_id
        if update_col.button(
            "Update saved grouping",
            width="stretch",
            disabled=not loaded_exists,
            help=(
                "Update the loaded grouping, including its name."
                if loaded_exists
                else "Load a saved grouping before updating it."
            ),
            key=f"{prefix}_update",
        ):
            try:
                db.save_background_grouping(
                    field.key,
                    grouping_name,
                    groups_definition,
                    grouping_id=int(loaded_id),
                )
                db.select_background_grouping(field.key, int(loaded_id))
                st.session_state[f"{prefix}_pending_selection"] = int(loaded_id)
                st.session_state[f"{prefix}_message"] = f"Updated “{grouping_name}”."
                st.rerun()
            except ValueError as error:
                st.error(str(error))
    return assignments["group"]


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


def background_group_counts(
    comparison: dict[str, object],
    field: object,
    custom_groups: bool = False,
) -> dict[str, str]:
    """Return compact background-level counts for the comparison table."""
    counts = comparison["counts"]
    if not isinstance(counts, pd.DataFrame) or counts.empty:
        return {}
    data = comparison["data"]
    included = (
        {str(value) for value in data["group"].dropna().unique()}
        if isinstance(data, pd.DataFrame) and not data.empty
        else set()
    )
    values: dict[str, str] = {}
    excluded_total = 0
    for _, row in counts.iterrows():
        group = row["group"]
        label = str(group) if custom_groups else background_category_label(field, group)
        label = {
            "Beginner (≤5 years)": "Beginner",
            "Intermediate (6–10 years)": "Intermediate",
            "Experienced (11+ years)": "Experienced",
            "Polytechnic / institute of technology": "Poly.",
            "Research university": "Research",
            "Teaching-focused college or university": "Teaching",
            "Earlier career (≤10 years)": "Earlier career",
            "Other institution types": "Other institutions",
            "Introductory or intermediate": "Intro./intermediate",
            "Advanced or graduate": "Advanced/graduate",
            "None or limited": "None/limited",
            "Moderate or extensive": "Moderate/extensive",
            "Government / nonprofit organization": "Gov./nonprofit",
            "Independent researcher / consultant": "Independent",
            "Community college / two-year college": "Community college",
            "Industry / private sector": "Industry",
        }.get(label, label)
        is_included = str(group) in included
        count = int(row["n"])
        if not is_included and field.kind == "category" and not custom_groups:
            excluded_total += count
            continue
        values[label] = f"{count}{'' if is_included else '†'}"
    if excluded_total:
        values["Excluded"] = f"{excluded_total}†"
    return values


def collapse_background_catalog(
    catalog: pd.DataFrame,
    outcome_heading: str,
) -> pd.DataFrame:
    """Collapse multi-select category tests into one selectable row per outcome."""
    rows: list[dict[str, object]] = []
    grouped = catalog.groupby(["background_key", "outcome_key"], sort=False, dropna=False)
    for (background_key, _), comparisons in grouped:
        field = FIELD_BY_KEY[str(background_key)]
        if field.kind == "multi":
            collapsed_label = {
                "roles": "Roles in computing education",
                "computing_areas": "PjBL computing areas",
            }.get(field.key, field.label)
            p_values = pd.to_numeric(comparisons["Raw p"], errors="coerce")
            significant = comparisons[p_values < 0.05]
            significant_categories = significant["category"].dropna().astype(str).tolist()
            rows.append(
                {
                    "background_key": field.key,
                    "analysis_type": "multi_group",
                    "category": None,
                    "outcome_key": comparisons.iloc[0]["outcome_key"],
                    "Background": collapsed_label,
                    outcome_heading: comparisons.iloc[0][outcome_heading],
                    "Basis": f"{len(comparisons)} {field.label.lower()}s",
                    "N": int(comparisons["N"].max()),
                    "Test": "Welch t-tests",
                    "p-value": float("nan"),
                    "Finding": f"{len(significant_categories)} of {len(comparisons)}" if significant_categories else "—",
                    "Result": "Significant" if significant_categories else "Not significant",
                }
            )
            continue

        comparison = comparisons.iloc[0]
        is_significant = comparison["Result"] == "Significant"
        rows.append(
            {
                **comparison.to_dict(),
                "Basis": f"{int(comparison['Levels'])} levels",
                "p-value": comparison["Raw p"],
                "Finding": "Significant" if is_significant else "—",
            }
        )
    return pd.DataFrame(rows)


def render_background_outcome_comparisons(
    frame: pd.DataFrame,
    selected_field: object,
    outcomes: list[tuple[str, str]],
    outcome_heading: str,
    key_prefix: str,
    custom_groups: pd.Series | None = None,
) -> None:
    catalog_rows = []
    with st.spinner(
        f"Calculating {background_display_label(selected_field).lower()} comparisons…"
    ):
        if custom_groups is not None:
            for outcome_key, outcome_label in outcomes:
                analysis_frame = frame.copy()
                analysis_frame["_custom_group"] = custom_groups.reindex(frame.index)
                comparison = group_comparison(analysis_frame, "_custom_group", outcome_key)
                catalog_rows.append(
                    {
                        "background_key": selected_field.key,
                        "analysis_type": "custom",
                        "category": None,
                        "outcome_key": outcome_key,
                        "Category": "Custom groups",
                        outcome_heading: outcome_label,
                        "Levels": int(comparison["data"]["group"].nunique()) if not comparison["data"].empty else 0,
                        "N": len(comparison["data"]),
                        "Group counts": background_group_counts(
                            comparison,
                            selected_field,
                            custom_groups=True,
                        ),
                        "Test": {
                            "Welch’s t-test": "Welch t",
                            "One-way ANOVA": "ANOVA",
                        }.get(comparison["test"], "Not estimable"),
                        "Statistic": comparison["statistic"],
                        "Raw p": comparison["p_value"],
                        "Effect": comparison["effect"],
                        "Effect measure": comparison["effect_name"] or "—",
                        "Warning": comparison["warning"],
                    }
                )
        else:
            analysis_specs = background_analysis_specs(frame, selected_field)
            for spec in analysis_specs:
                field = spec["field"]
                for outcome_key, outcome_label in outcomes:
                    comparison = run_background_analysis(
                        frame,
                        field,
                        outcome_key,
                        str(spec["analysis_type"]),
                        spec["category"],
                    )
                    catalog_rows.append(
                        {
                            "background_key": field.key,
                            "analysis_type": spec["analysis_type"],
                            "category": spec["category"],
                            "outcome_key": outcome_key,
                            "Category": spec["category"] or "All levels",
                            outcome_heading: outcome_label,
                            "Levels": int(comparison["data"]["group"].nunique()) if not comparison["data"].empty else 0,
                            "N": len(comparison["data"]),
                            "Group counts": background_group_counts(comparison, field),
                            "Test": {
                                "Spearman rank correlation": "Spearman ρ",
                                "Welch’s t-test": "Welch t",
                                "One-way ANOVA": "ANOVA",
                            }.get(comparison["test"], "Not estimable"),
                            "Statistic": comparison["statistic"],
                            "Raw p": comparison["p_value"],
                            "Effect": comparison["effect"],
                            "Effect measure": comparison["effect_name"] or "—",
                            "Warning": comparison["warning"],
                        }
                    )
    catalog = pd.DataFrame(catalog_rows)
    if catalog.empty:
        st.info("No comparisons can be calculated for this background question.")
        return

    catalog["Result"] = "—"
    catalog.loc[catalog["Raw p"] < 0.05, "Result"] = "Significant"
    catalog.loc[catalog["Raw p"].isna(), "Result"] = "Not estimable"
    catalog["Effect size"] = catalog.apply(
        lambda row: (
            f"g = {fmt(row['Effect'], 3)}"
            if row["Test"] == "Welch t" and pd.notna(row["Effect"])
            else f"η² = {fmt(row['Effect'], 3)}"
            if row["Test"] == "ANOVA" and pd.notna(row["Effect"])
            else "—"
        ),
        axis=1,
    )
    display_label = background_display_label(selected_field)
    heading_label = f"Custom {display_label.lower()} groups" if custom_groups is not None else display_label
    st.subheader(f"{heading_label} × {outcome_heading.lower()}")
    analysis_note = (
        " The selected categories are analyzed as mutually exclusive custom groups."
        if custom_groups is not None
        else " Each category is tested separately as selected versus not selected."
        if selected_field.kind == "multi"
        else ""
    )
    group_size_note = (
        " The Valid group n column shows valid outcome responses in each background level or comparison group; "
        "† means the group was excluded because it had fewer than two valid responses."
    )
    st.caption(
        "The Statistic column reports Spearman ρ, Welch t, or ANOVA F according to the Test column. "
        f"Green indicates a raw p-value below .05.{group_size_note}{analysis_note}"
    )
    display_columns = []
    if custom_groups is None and selected_field.kind == "multi":
        display_columns.append("Category")
    display_columns.append(outcome_heading)
    count_labels: list[str] = []
    for values in catalog["Group counts"]:
        for label in values:
            if label not in count_labels:
                count_labels.append(label)
    preferred_order = [] if custom_groups is not None else {
        "years_experience": ["Beginner", "Intermediate", "Experienced"],
        "institution_type": ["Research", "Teaching", "Poly.", "Excluded"],
    }.get(
        selected_field.key,
        ["None", "Limited", "Moderate", "Extensive"]
        if selected_field.scale == "experience"
        else ["Selected", "Not selected"],
    )
    count_labels.sort(
        key=lambda label: (
            preferred_order.index(label) if label in preferred_order else len(preferred_order),
            label,
        )
    )
    catalog["Valid group n"] = catalog["Group counts"].map(
        lambda values: " · ".join(
            f"{label} {values.get(label, '0')}" for label in count_labels
        )
    )
    display_columns.append("Valid group n")
    display_columns.extend(["Test", "Statistic", "Raw p"])
    display_catalog = catalog[display_columns].rename(
        columns={"Raw p": "p-value"}
    )
    display_catalog["Statistic"] = display_catalog["Statistic"].map(
        lambda value: fmt(value, 3)
    )
    display_catalog["p-value"] = display_catalog["p-value"].map(
        lambda value: fmt(value, 4)
    )

    def comparison_row_color(row: pd.Series) -> list[str]:
        try:
            significant = float(row["p-value"]) < 0.05
        except (TypeError, ValueError):
            significant = False
        if significant:
            color = "background-color: #a7f0ba; color: #0e6027; font-weight: 600"
        else:
            color = ""
        return [color] * len(row)

    styled_catalog = display_catalog.style.apply(comparison_row_color, axis=1)
    st.markdown(
        "<span style='background:#a7f0ba;color:#0e6027;padding:.2rem .45rem;font-weight:600'>Green: p &lt; .05</span>",
        unsafe_allow_html=True,
    )
    selection = st.dataframe(
        styled_catalog,
        width="stretch",
        height=(len(display_catalog) + 1) * 36 + 3,
        row_height=36,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key=f"{key_prefix}_{selected_field.key}_comparison_catalog",
        column_config={
            "Category": st.column_config.TextColumn(width=160),
            outcome_heading: st.column_config.TextColumn(width=150),
            "Test": st.column_config.TextColumn(width=85),
            "Statistic": st.column_config.TextColumn(
                "ρ / t / F",
                width=62,
                help="Spearman rho, Welch t, or ANOVA F, as identified in the Test column.",
            ),
            "p-value": st.column_config.TextColumn(width=62),
            "Valid group n": st.column_config.TextColumn(
                width=290,
                help="Valid responses used for this outcome in every background level or comparison group. † means fewer than two responses, so that group was excluded from the test.",
            ),
        },
    )
    selected_rows = selection.selection.rows
    if not selected_rows:
        st.caption("Select a comparison to view its distribution and details.")
        return

    selected = catalog.iloc[selected_rows[0]]
    group_field = selected_field
    analysis_type = str(selected["analysis_type"])
    category = selected["category"] if pd.notna(selected["category"]) else None
    background_label = heading_label
    if category is not None:
        background_label = f"{display_label}: {category}"
    outcome_key = selected["outcome_key"]
    outcome_label = selected[outcome_heading]
    st.divider()
    st.subheader(f"{background_label} × {outcome_label}")

    if custom_groups is not None:
        analysis_frame = frame.copy()
        analysis_frame["_custom_group"] = custom_groups.reindex(frame.index)
        result = group_comparison(analysis_frame, "_custom_group", outcome_key)
        group_label = lambda value: str(value)
    else:
        result = run_background_analysis(
            frame,
            group_field,
            outcome_key,
            analysis_type,
            category,
        )
        group_label = lambda value: background_category_label(group_field, value)
    data = result["data"]
    show_tukey = (
        result["test"] == "One-way ANOVA"
        and pd.notna(result["p_value"])
        and float(result["p_value"]) < 0.05
        and not result["posthoc"].empty
    )
    if not data.empty:
        plot_data = data.copy()
        plot_data["group"] = plot_data["group"].map(group_label)
        if analysis_type == "ordinal":
            plot_data["rank"] = data["group"].to_numpy()
            fig = px.scatter(
                plot_data,
                x="rank",
                y="score",
                range_y=[1, 5],
                labels={"rank": group_field.label, "score": f"{outcome_label} score"},
                color_discrete_sequence=[CHART_PALETTE[0]],
            )
            level_labels = (
                plot_data[["rank", "group"]]
                .drop_duplicates()
                .sort_values("rank")
            )
            fig.update_xaxes(
                tickmode="array",
                tickvals=level_labels["rank"].tolist(),
                ticktext=level_labels["group"].tolist(),
            )
            fig.update_traces(marker=dict(size=10, opacity=0.7))
        else:
            fig = px.box(
                plot_data,
                x="group",
                y="score",
                color="group",
                points="all",
                range_y=[1, 5],
                labels={"group": background_label, "score": f"{outcome_label} score"},
                color_discrete_sequence=CHART_PALETTE,
            )
            fig.update_layout(showlegend=False)
        fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig, width="stretch")
    with st.expander("View statistical test results"):
        st.markdown(f"**{background_label} × {outcome_label}**")
        if result["warning"]:
            st.warning(result["warning"])
        if result["test"]:
            statistic_label = {
                "Welch’s t-test": "Welch t",
                "One-way ANOVA": "ANOVA F",
                "Spearman rank correlation": "Spearman ρ",
            }[result["test"]]
            if result["test"] == "Spearman rank correlation":
                statistic_col, p_col, n_col = st.columns(3)
                statistic_col.metric(statistic_label, fmt(result["statistic"], 3))
                p_col.metric("p-value", fmt(result["p_value"], 4))
                n_col.metric("N", len(result["data"]))
            else:
                effect_label = "Hedges’ g" if result["test"] == "Welch’s t-test" else "η²"
                statistic_col, p_col, effect_col, n_col = st.columns(4)
                statistic_col.metric(statistic_label, fmt(result["statistic"], 3))
                p_col.metric("p-value", fmt(result["p_value"], 4))
                effect_col.metric(effect_label, fmt(result["effect"], 3))
                n_col.metric("N", len(result["data"]))

        st.markdown("**Responses by level**" if analysis_type == "ordinal" else "**Group sizes**")
        counts = result["counts"].rename(columns={"group": "Group", "n": "N"})
        counts["Group"] = counts["Group"].map(group_label)
        st.dataframe(
            counts,
            width="stretch",
            hide_index=True,
            height=38 + 35 * len(counts),
            column_config={"N": st.column_config.NumberColumn(format="%d", width="small")},
        )

        if not result["assumptions"].empty:
            st.markdown("**Assumption checks**")
            assumptions = result["assumptions"].copy()
            assumptions["group"] = assumptions["group"].map(group_label)
            assumptions = assumptions.rename(
                columns={
                    "check": "Check",
                    "group": "Group",
                    "n": "N",
                    "statistic": "Statistic",
                    "p_value": "p-value",
                }
            ).round(4)
            st.dataframe(
                assumptions,
                width="stretch",
                hide_index=True,
                height=38 + 35 * len(assumptions),
                column_config={
                    "Check": st.column_config.TextColumn(width=230),
                    "Group": st.column_config.TextColumn(width=180),
                    "N": st.column_config.NumberColumn(format="%d", width=45),
                    "Statistic": st.column_config.NumberColumn(format="%.4f", width=72),
                    "p-value": st.column_config.NumberColumn(format="%.4f", width=72),
                },
            )

        if show_tukey:
            significant_pairs = result["posthoc"][result["posthoc"]["different_at_0.05"]]
            if not significant_pairs.empty:
                tukey_display = pd.DataFrame(
                    {
                        "Group 1": significant_pairs["group_1"].map(
                            group_label
                        ),
                        "Group 2": significant_pairs["group_2"].map(
                            group_label
                        ),
                        "N 1": significant_pairs["n_1"].astype(int),
                        "N 2": significant_pairs["n_2"].astype(int),
                        "Mean difference": significant_pairs["mean_difference"],
                        "95% CI": significant_pairs.apply(
                            lambda row: f"{fmt(row['ci95_low'], 3)} to {fmt(row['ci95_high'], 3)}",
                            axis=1,
                        ),
                        "Adjusted p": significant_pairs["adjusted_p"],
                    }
                )
                st.markdown(f"**Significant pairwise comparisons ({len(tukey_display)})**")
                st.caption(
                    f"{result['posthoc_method']}. Only significant pairs are shown. "
                    "N 1 and N 2 correspond to Group 1 and Group 2. "
                    "These p-values are adjusted for all pairwise comparisons within this analysis."
                )
                st.dataframe(
                    tukey_display,
                    width="stretch",
                    hide_index=True,
                    height=38 + 35 * len(tukey_display),
                    column_config={
                        "Group 1": st.column_config.TextColumn(width=130),
                        "Group 2": st.column_config.TextColumn(width=130),
                        "N 1": st.column_config.NumberColumn(format="%d", width=45),
                        "N 2": st.column_config.NumberColumn(format="%d", width=45),
                        "Mean difference": st.column_config.NumberColumn(format="%.3f", width=88),
                        "95% CI": st.column_config.TextColumn(width=130),
                        "Adjusted p": st.column_config.NumberColumn(format="%.4f", width=68),
                    },
                )


def render_background_rating_comparisons(
    frame: pd.DataFrame,
    selected_field: object,
    custom_groups: pd.Series | None = None,
) -> None:
    render_background_outcome_comparisons(
        frame,
        selected_field,
        [(construct, construct) for construct in CONSTRUCTS],
        "Scale",
        "custom_background_construct" if custom_groups is not None else "background_construct",
        custom_groups,
    )


def render_background_item_comparisons(
    frame: pd.DataFrame,
    selected_field: object,
    construct: str,
    custom_groups: pd.Series | None = None,
) -> None:
    fields = [field for field in ITEM_FIELDS if field.construct == construct]
    render_background_outcome_comparisons(
        frame,
        selected_field,
        [(field.key, field.label) for field in fields],
        "Item",
        f"custom_background_item_{construct}" if custom_groups is not None else f"background_item_{construct}",
        custom_groups,
    )


def render_comparisons(db: Database) -> None:
    page_header(
        "Background comparisons",
        "Compare one respondent background at a time with construct scores or individual items using the appropriate statistical test.",
    )
    raw_frame = db.active_data()
    frame = require_data(db)
    if frame is None:
        return

    field_keys = [field.key for field in BACKGROUND_FIELDS]
    remembered_field_key = str(
        st.session_state.get("background_comparison_field_remembered", field_keys[0])
    )
    if remembered_field_key not in field_keys:
        remembered_field_key = field_keys[0]
    selected_field_key = st.pills(
        "Background",
        field_keys,
        default=remembered_field_key,
        format_func=lambda key: background_display_label(FIELD_BY_KEY[key]),
        key="background_comparison_field",
    )
    selected_field = FIELD_BY_KEY[selected_field_key or BACKGROUND_FIELDS[0].key]
    st.session_state["background_comparison_field_remembered"] = selected_field.key

    main_panel, side_panel = st.columns([4.2, 1.15], gap="large")
    controls = side_panel.container(border=True)
    render_background_frequency_panel(frame, selected_field, controls)
    render_background_mapping_panel(db, raw_frame, selected_field, controls)
    with main_panel:
        compare_control, construct_control, grouping_control = st.columns(
            [1.45, 1, 0.85],
            gap="medium",
            vertical_alignment="bottom",
        )
        comparison_options = ["Construct scores", "Individual items"]
        remembered_comparison_level = str(
            st.session_state.get(
                "background_comparison_level_remembered",
                comparison_options[0],
            )
        )
        if remembered_comparison_level not in comparison_options:
            remembered_comparison_level = comparison_options[0]
        comparison_level = compare_control.segmented_control(
            "Compare",
            comparison_options,
            default=remembered_comparison_level,
            key="background_comparison_level",
        )
        st.session_state["background_comparison_level_remembered"] = comparison_level
        remembered_grouping_id = db.selected_background_grouping(selected_field.key)
        grouping_options = ["Standard", "Custom"]
        remembered_grouping_mode = str(
            st.session_state.get(
                "background_grouping_mode_remembered",
                "Custom" if remembered_grouping_id is not None else "Standard",
            )
        )
        if remembered_grouping_mode not in grouping_options:
            remembered_grouping_mode = "Standard"
        grouping_mode = grouping_control.selectbox(
            "Grouping",
            grouping_options,
            index=grouping_options.index(remembered_grouping_mode),
            key="background_grouping_mode",
        )
        st.session_state["background_grouping_mode_remembered"] = grouping_mode
        construct = None
        if comparison_level == "Individual items":
            construct = construct_control.selectbox(
                "Construct",
                CONSTRUCTS,
                format_func=sentence_case_option,
                key="background_item_construct",
            )

        custom_groups = None
        if grouping_mode == "Custom":
            custom_groups = render_custom_group_builder(db, frame, selected_field)
            if custom_groups is None:
                return

        if comparison_level == "Construct scores":
            render_background_rating_comparisons(frame, selected_field, custom_groups)
        else:
            render_background_item_comparisons(frame, selected_field, str(construct), custom_groups)


def qualitative_fields(keys: tuple[str, ...]) -> list[object]:
    by_key = {field.key: field for field in OPEN_TEXT_FIELDS}
    return [by_key[key] for key in keys if key in by_key]


def render_meaning_unit_workspace(
    db: Database,
    frame: pd.DataFrame,
    question_keys: tuple[str, ...],
    workspace_key: str,
) -> None:
    editing = edit_mode_enabled()
    questions = qualitative_fields(question_keys)
    respondent_labels = database_respondent_labels(db)
    response_panel, question_panel = st.columns([3.75, 1.1], gap="large")
    question = question_panel.selectbox(
        "Open-ended question",
        questions,
        format_func=lambda field: sentence_case_option(field.label),
        key=f"{workspace_key}_question",
    )
    available = frame[
        frame[question.key].notna() & frame[question.key].astype(str).str.strip().ne("")
    ].copy().reset_index(drop=True)
    if available.empty:
        response_panel.caption("No responses to this question in the current filtered snapshot.")
        return

    question_state_key = f"{workspace_key}_active_question"
    position_key = f"{workspace_key}_response_position"
    if st.session_state.get(question_state_key) != question.key:
        st.session_state[question_state_key] = question.key
        st.session_state[position_key] = 0
        active_editor = st.session_state.get("active_meaning_unit_editor")
        if isinstance(active_editor, str) and active_editor.startswith(f"{workspace_key}:"):
            st.session_state.pop("active_meaning_unit_editor", None)

    active_codes = db.codes()
    assignable_codes = active_codes[active_codes["code_type"] != "Domain"] if not active_codes.empty else pd.DataFrame()
    code_colors = active_codes.set_index("name")["color"].astype(str).to_dict() if not active_codes.empty else {}
    code_tooltips = code_tooltip_lookup(active_codes)
    units = db.meaning_units(question_key=question.key)
    coded_ids = set(units["response_id"]) if not units.empty else set()
    coded_count = len(coded_ids.intersection(set(available["response_id"].astype(str))))
    question_panel.caption(
        f"{len(available)} responses · {coded_count} coded · "
        f"{len(units)} coded excerpt{'s' if len(units) != 1 else ''}"
    )
    if editing and assignable_codes.empty:
        question_panel.warning("Create at least one working code before adding coded excerpts.")

    position = min(max(int(st.session_state.get(position_key, 0)), 0), len(available) - 1)
    st.session_state[position_key] = position
    previous_col, position_col, next_col = response_panel.columns([1, 3, 1])
    if previous_col.button(
        "← Previous",
        disabled=position == 0,
        width="stretch",
        key=f"{workspace_key}_{question.key}_previous",
    ):
        st.session_state[position_key] = position - 1
        st.session_state.pop("active_meaning_unit_editor", None)
        st.rerun()
    position_col.markdown(
        f'<div class="response-position">Response {position + 1} of {len(available)}</div>',
        unsafe_allow_html=True,
    )
    if next_col.button(
        "Next →",
        disabled=position == len(available) - 1,
        width="stretch",
        key=f"{workspace_key}_{question.key}_next",
    ):
        st.session_state[position_key] = position + 1
        st.session_state.pop("active_meaning_unit_editor", None)
        st.rerun()
    response_panel.progress((position + 1) / len(available))

    row = available.iloc[position]
    response_key = str(row["response_id"])
    editor_key = f"{workspace_key}:{question.key}:{response_key}"
    current_units = units[units["response_id"] == response_key] if not units.empty else pd.DataFrame()
    with response_panel.container(border=True):
        status = (
            f"Coded · {len(current_units)} excerpt{'s' if len(current_units) != 1 else ''}"
            if response_key in coded_ids
            else "Not coded yet"
        )
        institution_value = row.get("institution_type")
        institution = (
            "Not provided"
            if pd.isna(institution_value) or not str(institution_value).strip()
            else str(institution_value)
        )
        experience_value = row.get("years_experience")
        experience = (
            "Not provided"
            if pd.isna(experience_value) or not str(experience_value).strip()
            else str(experience_value)
        )
        render_respondent_heading(
            response_key, respondent_label(response_key, respondent_labels),
            f'<span class="response-heading-title">Response {position + 1}</span>'
            f'<span class="response-coding-status">{html.escape(status)}</span>'
            f'<span class="response-meta-badge"><strong>Institution</strong>&nbsp; {html.escape(institution)}</span>'
            f'<span class="response-meta-badge"><strong>Experience</strong>&nbsp; {html.escape(experience)}</span>',
            key=f"review_{workspace_key}_{response_key}",
        )
        st.markdown(
            f'<div class="response-card">{html.escape(str(row[question.key]))}</div>',
            unsafe_allow_html=True,
        )
        with st.expander("View this respondent's related ratings"):
            render_rating_context(row, question.key)
        if not current_units.empty:
            st.markdown("#### Coded excerpts from this response")
            for excerpt_number, (_, unit) in enumerate(current_units.iterrows(), start=1):
                unit_id = int(unit["id"])
                with st.container(border=True):
                    st.markdown(f"**Excerpt {excerpt_number}**")
                    render_excerpt_highlights(
                        db, unit_id, str(unit["excerpt"]), f"coding_{workspace_key}_{unit_id}",
                    )
                    if str(unit["note"] or "").strip():
                        st.markdown(f"**Interpretation:** {unit['note']}")
                    if editing:
                        edit_col, delete_col, _ = st.columns([1, 1, 4])
                        if edit_col.button("Edit", key=f"{workspace_key}_edit_unit_{unit_id}"):
                            st.session_state["active_meaning_unit_editor"] = f"{workspace_key}:unit:{unit_id}"
                        if delete_col.button("Delete", key=f"{workspace_key}_delete_unit_{unit_id}"):
                            db.delete_meaning_unit(unit_id)
                            st.rerun()
        if editing and not assignable_codes.empty and st.button("Add coded excerpt", key=f"{workspace_key}_add_unit_{editor_key}"):
            st.session_state["active_meaning_unit_editor"] = f"{workspace_key}:new:{editor_key}"

        active_editor = st.session_state.get("active_meaning_unit_editor")
        editing_unit = None
        if isinstance(active_editor, str) and active_editor.startswith(f"{workspace_key}:unit:") and not current_units.empty:
            edit_id = int(active_editor.rsplit(":", 1)[1])
            matches = current_units[current_units["id"] == edit_id]
            if not matches.empty:
                editing_unit = matches.iloc[0]
        editor_is_here = active_editor == f"{workspace_key}:new:{editor_key}" or editing_unit is not None
        if editing and not assignable_codes.empty and editor_is_here:
            selected_ids: list[int] = []
            excerpt_default = ""
            note_default = ""
            if editing_unit is not None:
                selected_ids = [int(value) for value in str(editing_unit["code_ids"] or "").split(",") if value]
                excerpt_default = str(editing_unit["excerpt"])
                note_default = str(editing_unit["note"] or "")
            code_options = assignable_codes["id"].astype(int).tolist()
            suffix = int(editing_unit["id"]) if editing_unit is not None else "new"
            chosen = st.multiselect(
                "Working codes",
                code_options,
                default=[code_id for code_id in selected_ids if code_id in code_options],
                format_func=lambda code_id: sentence_case_option(
                    assignable_codes.set_index("id").loc[code_id, "name"]
                ),
                help="Choose every working code that clearly applies to this excerpt.",
                key=f"{workspace_key}_unit_codes_{editor_key}_{suffix}",
            )
            excerpt = st.text_area(
                "Exact excerpt from the response",
                excerpt_default,
                help="Copy the shortest exact passage that expresses one coherent idea. Keep the participant's wording unchanged.",
                key=f"{workspace_key}_unit_excerpt_{editor_key}_{suffix}",
            )
            note = st.text_area(
                "Your interpretation",
                note_default,
                help="Explain what this passage means for the analysis without changing the exact quotation.",
                key=f"{workspace_key}_unit_note_{editor_key}_{suffix}",
            )
            save_col, cancel_col, _ = st.columns([1, 1, 4])
            if save_col.button("Save coded excerpt", type="primary", key=f"{workspace_key}_save_unit_{editor_key}_{suffix}"):
                if excerpt.strip() and excerpt.strip() in str(row[question.key]):
                    db.save_meaning_unit(
                        response_key,
                        question.key,
                        excerpt,
                        [int(value) for value in chosen],
                        note,
                        unit_id=int(editing_unit["id"]) if editing_unit is not None else None,
                    )
                    st.session_state.pop("active_meaning_unit_editor", None)
                    st.rerun()
                elif not excerpt.strip():
                    st.error("Copy an exact excerpt from the response.")
                else:
                    st.error("The excerpt must match the response exactly.")
            if cancel_col.button("Cancel", key=f"{workspace_key}_cancel_unit_{editor_key}_{suffix}"):
                st.session_state.pop("active_meaning_unit_editor", None)
                st.rerun()

    bottom_previous, bottom_position, bottom_next = response_panel.columns([1, 3, 1])
    if bottom_previous.button(
        "← Previous response",
        disabled=position == 0,
        width="stretch",
        key=f"{workspace_key}_{question.key}_bottom_previous",
    ):
        st.session_state[position_key] = position - 1
        st.session_state.pop("active_meaning_unit_editor", None)
        st.rerun()
    bottom_position.caption(f"Response {position + 1} of {len(available)}")
    if bottom_next.button(
        "Next response →",
        disabled=position == len(available) - 1,
        width="stretch",
        key=f"{workspace_key}_{question.key}_bottom_next",
    ):
        st.session_state[position_key] = position + 1
        st.session_state.pop("active_meaning_unit_editor", None)
        st.rerun()

    coded = db.codings(question.key)
    if not coded.empty:
        with question_panel.expander("View coding summary for this question"):
            frequency = (
                coded.groupby("code_name", dropna=False)
                .agg(Respondents=("response_id", "nunique"), coded_excerpts=("meaning_unit_id", "nunique"))
                .reset_index()
                .rename(columns={"code_name": "Working code", "coded_excerpts": "Coded excerpts"})
                .sort_values(["Respondents", "Coded excerpts", "Working code"], ascending=[False, False, True])
            )
            for _, summary_row in frequency.iterrows():
                render_code_badges(summary_row["Working code"], code_colors, code_tooltips)
                st.caption(
                    f"{int(summary_row['Respondents'])} respondent{'s' if int(summary_row['Respondents']) != 1 else ''} · "
                    f"{int(summary_row['Coded excerpts'])} excerpt{'s' if int(summary_row['Coded excerpts']) != 1 else ''}"
                )


def render_codebook_workspace(db: Database) -> None:
    editing = edit_mode_enabled()
    version = db.current_codebook_version()
    if version is None:
        if not editing:
            st.caption("No working-code set yet. Enable Edit mode to create one.")
            return
        st.caption("Create a set of working codes before coding responses.")
        with st.form("new_codebook_version"):
            label = st.text_input("Name", "Working codes 1", key="edit_codebook_label")
            description = st.text_area("Purpose", "Evolving working codes for the FORAP open-ended responses.", key="edit_codebook_description")
            if st.form_submit_button("Create working codes", type="primary"):
                if label.strip():
                    db.create_codebook_version(label, description)
                    st.rerun()
        return

    st.caption(f"Current set: {version['label']} · {version['status'].title()}")
    codes = db.codes().reset_index(drop=True)
    if not codes.empty:
        codings = db.codings()
        if codings.empty:
            counts = pd.DataFrame(columns=["id", "Respondents", "Excerpts"])
        else:
            counts = (
                codings.groupby("code_id", as_index=False)
                .agg(
                    Respondents=("response_id", "nunique"),
                    Excerpts=("meaning_unit_id", "nunique"),
                )
                .rename(columns={"code_id": "id"})
            )
        display_codes = codes.merge(counts, on="id", how="left", sort=False)
        display_codes[["Respondents", "Excerpts"]] = (
            display_codes[["Respondents", "Excerpts"]].fillna(0).astype(int)
        )
        display_codes["Color"] = ":material/palette:"
        display_codes["Open"] = ":material/visibility:"
        display_codes = display_codes.rename(
            columns={
                "name": "Working code",
                "description": "Definition",
            }
        )
        columns = ["Working code", *(["Color"] if editing else []), "Definition", "Respondents", "Excerpts", "Open"]
        code_table = display_codes[columns]

        def style_code_name(row: pd.Series) -> pd.Series:
            styles = pd.Series("", index=row.index)
            raw_color = str(display_codes.loc[row.name, "color"] or "")
            color = raw_color if len(raw_color) == 7 and raw_color.startswith("#") else suggested_code_color(str(row["Working code"]))
            styles["Working code"] = (
                f"background-color: {badge_tint(color)}; color: {color}; "
                f"font-weight: 650; border-left: 4px solid {color};"
            )
            return styles

        styled_codes = code_table.style.apply(style_code_name, axis=1)

        def open_code_color_dialog() -> None:
            if not edit_mode_enabled():
                return
            click = st.session_state.get("working_code_color_click")
            if click is not None:
                code_id = int(display_codes.iloc[int(click["row"])]["id"])
                st.session_state.pop(f"working_code_color_value_{code_id}", None)
                st.session_state["working_code_color_id"] = code_id

        def open_code_details_dialog() -> None:
            click = st.session_state.get("working_code_details_click")
            if click is not None:
                st.session_state["working_code_details_id"] = int(
                    display_codes.iloc[int(click["row"])]["id"]
                )

        st.dataframe(
            styled_codes,
            width="stretch",
            hide_index=True,
            height=38 + 35 * len(display_codes),
            column_config={
                "Color": st.column_config.ButtonColumn(
                    "",
                    width="small",
                    type="tertiary",
                    on_click=open_code_color_dialog,
                    key="working_code_color_click",
                ) if editing else None,
                "Respondents": st.column_config.NumberColumn("Respondents", format="%d", width="small"),
                "Excerpts": st.column_config.NumberColumn("Excerpts", format="%d", width="small"),
                "Open": st.column_config.ButtonColumn(
                    "View",
                    width="small",
                    type="tertiary",
                    help="Open this code and view every coded excerpt.",
                    on_click=open_code_details_dialog,
                    key="working_code_details_click",
                ),
            },
        )
        selected_color_code_id = st.session_state.pop("working_code_color_id", None)
        if editing and selected_color_code_id is not None:
            selected = codes[codes["id"] == int(selected_color_code_id)]
            if not selected.empty:
                render_code_color_dialog(db, selected.iloc[0])
        selected_details_code_id = st.session_state.pop("working_code_details_id", None)
        if selected_details_code_id is not None:
            selected = display_codes[display_codes["id"] == int(selected_details_code_id)]
            if not selected.empty:
                render_working_code_details_dialog(db, selected.iloc[0])
    else:
        st.caption("No working codes have been created yet.")

    if not editing:
        return
    with st.expander("Add a working code", expanded=codes.empty):
        with st.form("code_form", clear_on_submit=True):
            name = st.text_input("Code name", key="edit_code_name")
            description = st.text_area("What this code captures", key="edit_code_description")
            inclusion = st.text_area("Use this code when…", key="edit_code_inclusion")
            exclusion = st.text_area("Do not use this code when…", key="edit_code_exclusion")
            if st.form_submit_button("Save working code", type="primary"):
                if name.strip():
                    db.save_code(
                        name,
                        description,
                        inclusion,
                        exclusion,
                        suggested_code_color(name),
                        domain="Working codes",
                        code_type="Working code",
                        codebook_version_id=int(version["id"]),
                    )
                    st.rerun()
                else:
                    st.error("A code name is required.")

    active_codes = db.codes()
    assignable = active_codes[active_codes["code_type"] != "Domain"] if not active_codes.empty else pd.DataFrame()
    if not assignable.empty:
        with st.expander("Stop using a code"):
            selected = st.selectbox(
                "Working code",
                assignable["id"].astype(int).tolist(),
                format_func=lambda code_id: sentence_case_option(
                    assignable.set_index("id").loc[code_id, "name"]
                ),
            )
            if st.button("Deactivate code"):
                db.deactivate_code(int(selected))
                st.rerun()


def parsed_constructs(value: object) -> list[str]:
    try:
        parsed = json.loads(str(value or "[]"))
        return [str(item) for item in parsed] if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def theme_reporting_table(db: Database) -> pd.DataFrame:
    themes = db.themes()
    if themes.empty:
        return pd.DataFrame()
    evidence = db.theme_evidence()
    records: list[dict[str, object]] = []
    for _, theme in themes.iterrows():
        theme_evidence = evidence[evidence["theme_id"] == theme["id"]] if not evidence.empty else pd.DataFrame()
        questions = sorted(
            {
                FIELD_BY_KEY[key].label if key in FIELD_BY_KEY else str(key)
                for key in theme_evidence.get("question_key", pd.Series(dtype=str)).dropna().astype(str)
            }
        )
        records.append(
            {
                "Theme": theme["name"],
                "Status": str(theme["status"]).title(),
                "Theme statement": theme["description"],
                "Respondents": int(theme_evidence["response_id"].nunique()) if not theme_evidence.empty else 0,
                "Coded excerpts": len(theme_evidence),
                "Source questions": "; ".join(questions),
                "Linked constructs": "; ".join(parsed_constructs(theme["linked_constructs_json"])),
                "Contrasting evidence": theme["contrasting_evidence"],
                "Implication for FORAP": theme["implication"],
            }
        )
    return pd.DataFrame(records)


def render_theme_development(db: Database, frame: pd.DataFrame) -> None:
    editing = edit_mode_enabled()
    themes = db.themes()
    codes = db.codes()
    respondent_labels = database_respondent_labels(db)
    code_colors = codes.set_index("name")["color"].astype(str).to_dict() if not codes.empty else {}
    code_tooltips = code_tooltip_lookup(codes)
    assignable = codes[codes["code_type"] != "Domain"] if not codes.empty else pd.DataFrame()

    @st.dialog("Theme", width="large")
    def render_theme_editor(theme_id: int | None = None) -> None:
        if not edit_mode_enabled():
            return
        form_prefix = f"edit_theme_{theme_id or 'new'}"
        selected_theme = None
        if theme_id is not None and not themes.empty:
            matching = themes[themes["id"].astype(int) == int(theme_id)]
            if not matching.empty:
                selected_theme = matching.iloc[0]
        default_status = str(selected_theme["status"]) if selected_theme is not None else "candidate"
        default_constructs = parsed_constructs(selected_theme["linked_constructs_json"]) if selected_theme is not None else []
        default_code_ids = [
            int(value)
            for value in str(selected_theme.get("code_ids", "") if selected_theme is not None else "").split(",")
            if value and value != "nan"
        ]
        with st.form(f"theme_form_{theme_id or 'new'}"):
            theme_name = st.text_input("Theme name", str(selected_theme["name"]) if selected_theme is not None else "", key=f"{form_prefix}_name")
            theme_description = st.text_area(
                "Theme statement",
                str(selected_theme["description"]) if selected_theme is not None else "",
                key=f"{form_prefix}_description",
            )
            status_options = ["candidate", "reviewed", "final"]
            status = st.selectbox(
                "Status",
                status_options,
                index=status_options.index(default_status) if default_status in status_options else 0,
                format_func=sentence_case_option,
                key=f"{form_prefix}_status",
            )
            linked_constructs = st.multiselect(
                "Related FORAP constructs",
                list(CONSTRUCTS),
                default=default_constructs,
                format_func=sentence_case_option,
                key=f"{form_prefix}_constructs",
            )
            assignable_ids = set(assignable["id"].astype(int)) if not assignable.empty else set()
            theme_codes = st.multiselect(
                "Codes contributing to this theme",
                assignable["id"].astype(int).tolist() if not assignable.empty else [],
                default=[code_id for code_id in default_code_ids if code_id in assignable_ids],
                format_func=lambda code_id: sentence_case_option(
                    assignable.set_index("id").loc[code_id, "name"]
                ),
                key=f"{form_prefix}_codes",
            )
            contrasting = st.text_area(
                "Contrasting evidence",
                str(selected_theme["contrasting_evidence"]) if selected_theme is not None else "",
                key=f"{form_prefix}_contrasting",
            )
            implication = st.text_area(
                "Implication for FORAP",
                str(selected_theme["implication"]) if selected_theme is not None else "",
                key=f"{form_prefix}_implication",
            )
            if st.form_submit_button("Save theme", type="primary"):
                if theme_name.strip() and theme_description.strip():
                    db.save_theme(
                        theme_name,
                        theme_description,
                        [int(value) for value in theme_codes],
                        theme_id=theme_id,
                        status=status,
                        linked_constructs=list(linked_constructs),
                        implication=implication,
                        contrasting_evidence=contrasting,
                    )
                    st.rerun()
                else:
                    st.error("A theme name and theme statement are required.")

    st.subheader("Themes")
    if themes.empty:
        st.caption("No themes have been created yet.")
        if editing:
            if st.button("Add theme", width="stretch"):
                render_theme_editor()
        return

    details_panel, evidence_panel = st.columns([1.15, 2], gap="large")

    with details_panel:
        st.markdown("#### Theme details")
        theme_ids = themes["id"].astype(int).tolist()
        remembered_theme_id = int(st.session_state.get("selected_theme_id", theme_ids[0]))
        if remembered_theme_id not in set(theme_ids):
            remembered_theme_id = theme_ids[0]
        selected_theme_id = st.selectbox(
            "Theme",
            theme_ids,
            index=theme_ids.index(remembered_theme_id),
            format_func=lambda theme_id: sentence_case_option(
                themes.set_index("id").loc[theme_id, "name"]
            ),
            key="theme_detail_selection",
        )
        st.session_state["selected_theme_id"] = selected_theme_id
        selected_theme = themes.set_index("id").loc[selected_theme_id]
        evidence = db.theme_evidence(selected_theme_id)
        respondent_count = int(evidence["response_id"].nunique()) if not evidence.empty else 0
        st.caption(
            f"{str(selected_theme['status']).title()} · {respondent_count} respondents · "
            f"{len(evidence)} evidence excerpts"
        )
        st.markdown(f"### {html.escape(str(selected_theme['name']))}")
        st.markdown("**Theme statement**")
        st.write(selected_theme["description"])
        st.markdown("**Codes**")
        theme_code_ids = [
            int(value)
            for value in str(selected_theme.get("code_ids", "") or "").split(",")
            if value and value != "nan"
        ]
        code_names_by_id = codes.set_index("id")["name"].astype(str).to_dict()
        theme_code_names = " | ".join(
            code_names_by_id[code_id]
            for code_id in theme_code_ids
            if code_id in code_names_by_id
        )
        render_code_badges(theme_code_names, code_colors, code_tooltips)
        linked_constructs = parsed_constructs(selected_theme["linked_constructs_json"])
        if linked_constructs:
            st.markdown("**Related FORAP constructs**")
            st.write(" · ".join(linked_constructs))
        if str(selected_theme["contrasting_evidence"] or "").strip():
            st.markdown("**Contrasting evidence**")
            st.write(selected_theme["contrasting_evidence"])
        if str(selected_theme["implication"] or "").strip():
            st.markdown("**Implication for FORAP**")
            st.write(selected_theme["implication"])
        if editing:
            edit_action, add_action = st.columns(2)
            with edit_action:
                if st.button("Edit theme", width="stretch"):
                    render_theme_editor(selected_theme_id)
            with add_action:
                if st.button("Add theme", width="stretch"):
                    render_theme_editor()

    with evidence_panel:
        st.subheader("Evidence")
        if not evidence.empty:
            ordered_evidence = order_theme_evidence_for_display(evidence)
            for role_key in EVIDENCE_ROLE_ORDER:
                role_evidence = ordered_evidence[
                    ordered_evidence["_role_key"].eq(role_key)
                ]
                if role_evidence.empty:
                    continue
                role = role_key.title()
                with st.expander(
                    f"{role} ({len(role_evidence)})",
                    expanded=role_key == "supporting",
                    key=f"theme_evidence_group_{selected_theme_id}_{role_key}",
                    on_change="rerun",
                ):
                    for _, item in role_evidence.iterrows():
                        evidence_group = FIELD_BY_KEY[item["question_key"]].label
                        is_representative = bool(int(item["is_representative"]))
                        representative_meta = representative_badge() if is_representative else ""
                        with st.container(border=True):
                            render_excerpt_highlights(
                                db, item["meaning_unit_id"], str(item["excerpt"]),
                                f"theme_{selected_theme_id}_{int(item['meaning_unit_id'])}",
                            )
                            meta_col, details_col = st.columns(
                                [5, 1.35],
                                gap="small",
                                vertical_alignment="center",
                            )
                            with meta_col:
                                render_respondent_heading(
                                    item["response_id"], respondent_label(item["response_id"], respondent_labels),
                                    f'{evidence_role_badge(role)}'
                                    f'{evidence_question_badge(evidence_group)}'
                                    f'{representative_meta}',
                                    key=f"theme_{selected_theme_id}_{int(item['meaning_unit_id'])}",
                                )
                            with details_col:
                                show_details = st.toggle(
                                    "Show details",
                                    key=f"theme_evidence_details_{selected_theme_id}_{int(item['meaning_unit_id'])}",
                                )
                            if show_details:
                                representative = st.toggle(
                                    "Representative quotation",
                                    value=is_representative,
                                    key=f"theme_evidence_representative_{selected_theme_id}_{int(item['meaning_unit_id'])}",
                                    help="Include this excerpt among the quotations used to report the theme.",
                                ) if editing else is_representative
                                if editing and representative != is_representative:
                                    evidence_note = "" if pd.isna(item["evidence_note"]) else str(item["evidence_note"])
                                    db.save_theme_evidence(
                                        selected_theme_id,
                                        int(item["meaning_unit_id"]),
                                        str(item["evidence_role"]),
                                        evidence_note,
                                        representative,
                                    )
                                    st.rerun()
                                if str(item["evidence_note"] or "").strip():
                                    st.caption(f"Evidence note: {item['evidence_note']}")
                                respondent = frame[
                                    frame["response_id"].astype(str) == str(item["response_id"])
                                ]
                                if not respondent.empty:
                                    render_rating_context(
                                        respondent.iloc[0],
                                        str(item["question_key"]),
                                    )
                                if editing and st.button(
                                    "Remove evidence",
                                    key=f"remove_theme_evidence_{selected_theme_id}_{int(item['meaning_unit_id'])}",
                                ):
                                    db.delete_theme_evidence(
                                        selected_theme_id,
                                        int(item["meaning_unit_id"]),
                                    )
                                    st.rerun()
        else:
            st.caption("No evidence has been attached to this theme yet.")

        if not editing:
            return
        with st.expander("Attach evidence"):
            units = db.meaning_units()
            if not units.empty:
                units = units[
                    units["code_names"].fillna("").astype(str).str.strip().ne("")
                ]
            existing_unit_ids = set(evidence["meaning_unit_id"].astype(int)) if not evidence.empty else set()
            eligible = units[~units["id"].astype(int).isin(existing_unit_ids)] if not units.empty else pd.DataFrame()
            if eligible.empty:
                st.caption("No additional coded excerpts are available.")
            else:
                eligible_index = eligible.set_index("id")
                unit_id = st.selectbox(
                    "Coded excerpt",
                    eligible["id"].astype(int).tolist(),
                    format_func=lambda value: (
                        f"{sentence_case_option(FIELD_BY_KEY[eligible_index.loc[value, 'question_key']].label)} · "
                        f"{respondent_label(eligible_index.loc[value, 'response_id'], respondent_labels)} · "
                        f"{str(eligible_index.loc[value, 'excerpt'])[:120]}"
                    ),
                    key=f"edit_theme_evidence_{selected_theme_id}_unit",
                )
                with st.form(f"theme_evidence_form_{selected_theme_id}", clear_on_submit=True):
                    evidence_role = st.selectbox(
                        "Evidence role",
                        ["supporting", "contrasting", "contextual"],
                        format_func=sentence_case_option,
                        key=f"edit_theme_evidence_{selected_theme_id}_role",
                    )
                    evidence_note = st.text_area("Why this excerpt matters to the theme", key=f"edit_theme_evidence_{selected_theme_id}_note")
                    if st.form_submit_button("Attach evidence", type="primary"):
                        db.save_theme_evidence(selected_theme_id, int(unit_id), evidence_role, evidence_note, False)
                        st.rerun()


def render_integration_reporting(db: Database, frame: pd.DataFrame) -> None:
    respondent_labels = database_respondent_labels(db)
    summary = theme_reporting_table(db)
    if summary.empty:
        st.caption("Theme reporting becomes available after a theme has been created.")
        return
    st.subheader("Reporting-ready thematic summary")
    st.dataframe(summary, width="stretch", hide_index=True, height=38 + 35 * len(summary))
    st.download_button(
        "Download thematic summary (.csv)",
        dataframe_csv(summary),
        "forap_thematic_summary.csv",
        "text/csv",
    )

    themes = db.themes()
    theme_id = st.selectbox(
        "Theme for quantitative–qualitative integration",
        themes["id"].astype(int).tolist(),
        format_func=lambda value: sentence_case_option(
            themes.set_index("id").loc[value, "name"]
        ),
        key="integration_theme",
    )
    theme = themes.set_index("id").loc[theme_id]
    evidence = db.theme_evidence(theme_id)
    if evidence.empty:
        st.caption("Attach coded excerpts before connecting this theme with ratings.")
        return
    linked = parsed_constructs(theme["linked_constructs_json"])
    outcome = st.selectbox(
        "Related construct",
        linked or list(CONSTRUCTS),
        format_func=sentence_case_option,
        key="integration_construct",
    )
    included = set(evidence["response_id"].astype(str))
    scores = construct_scores(frame)
    joint = pd.DataFrame({"response_id": frame["response_id"].astype(str), "score": scores[outcome]})
    joint["Respondent"] = joint["response_id"].map(lambda value: respondent_label(value, respondent_labels))
    joint["Evidence group"] = joint["response_id"].map(
        lambda value: "Contributed evidence to theme" if value in included else "No attached evidence"
    )
    joint = joint.dropna(subset=["score"])
    figure = px.box(
        joint,
        x="Evidence group",
        y="score",
        color="Evidence group",
        points="all",
        range_y=[1, 5],
        labels={"score": outcome},
        color_discrete_sequence=["#8a3ffc", "#007d79"],
        hover_name="Respondent",
    )
    figure.update_layout(plot_bgcolor="white", paper_bgcolor="white", showlegend=False)
    st.plotly_chart(figure, width="stretch")
    display = joint.groupby("Evidence group")["score"].agg(["count", "mean", "median", "std"]).reset_index()
    st.dataframe(display.round(3), width="stretch", hide_index=True)
    st.caption(
        "This is a descriptive joint display. It helps explain ratings; it is not a test that the theme caused a rating difference, "
        "and uncoded comments must not be treated as absence of the theme."
    )

    st.subheader("Selected quotations and rating context")
    selected_quotes = evidence[evidence["is_representative"] == 1]
    if selected_quotes.empty:
        selected_quotes = evidence
        st.caption("No representative quotations are marked, so all attached evidence is shown.")
    for _, item in selected_quotes.iterrows():
        with st.container(border=True):
            quote_meta = f"{str(item['evidence_role']).title()} · {FIELD_BY_KEY[item['question_key']].label}"
            render_respondent_heading(
                item["response_id"], respondent_label(item["response_id"], respondent_labels),
                f'<span class="response-coding-status">{html.escape(quote_meta)}</span>',
                key=f"integration_{theme_id}_{int(item['meaning_unit_id'])}",
            )
            render_excerpt_highlights(
                db, item["meaning_unit_id"], str(item["excerpt"]),
                f"integration_{theme_id}_{int(item['meaning_unit_id'])}",
            )
            respondent = frame[frame["response_id"].astype(str) == str(item["response_id"])]
            if not respondent.empty:
                render_rating_context(respondent.iloc[0], str(item["question_key"]))


def render_memos_workspace(db: Database) -> None:
    st.markdown("### Analysis notes")
    st.caption("Use notes to record decisions, early patterns, questions, and reflections as the analysis develops.")
    if edit_mode_enabled():
        with st.form("memo_form", clear_on_submit=True):
            memo_title = st.text_input("Note title", key="edit_memo_title")
            memo_content = st.text_area("Note", height=180, key="edit_memo_content")
            if st.form_submit_button("Save note", type="primary"):
                if memo_title.strip() and memo_content.strip():
                    db.save_memo(memo_title, memo_content, "qualitative")
                    st.rerun()
                else:
                    st.error("A title and note are required.")
    memos = db.memos()
    if not memos.empty:
        st.subheader("Saved notes")
        for _, memo in memos.iterrows():
            with st.container(border=True):
                st.markdown(f"#### {memo['title']}")
                st.caption(str(memo["updated_at"]))
                st.write(memo["content"])
    with st.expander("View detailed change history"):
        audit = db.audit_log()
        audit_display = audit.drop(columns=["details_json"], errors="ignore").copy()
        if {"entity_type", "entity_id"}.issubset(audit_display.columns):
            labels = database_respondent_labels(db)
            response_rows = audit_display["entity_type"].eq("response")
            audit_display.loc[response_rows, "entity_id"] = audit_display.loc[response_rows, "entity_id"].map(
                lambda value: respondent_label(value, labels)
            )
        st.dataframe(audit_display, width="stretch", hide_index=True)


def render_thematic(db: Database) -> None:
    page_header(
        "Thematic analysis",
        "Review responses, apply plain-language working codes, and develop themes across the open-ended feedback.",
    )
    frame = require_data(db)
    if frame is None:
        return
    review_tab, codebook_tab, themes_tab, notes_tab = st.tabs(
        ["Review responses", "Working codes", "Build themes", "Notes & history"],
        key="thematic_tab",
        on_change="rerun",
    )
    with review_tab:
        render_meaning_unit_workspace(db, frame, ALL_QUALITATIVE_KEYS, "all_open_text")
    with codebook_tab:
        render_codebook_workspace(db)
    with themes_tab:
        render_theme_development(db, frame)
    with notes_tab:
        with st.expander("View analysis progress"):
            inventory = corpus_inventory(frame, db)
            totals = role_totals(frame)
            units = db.meaning_units()
            themes = db.themes()
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Open-ended questions", len(OPEN_TEXT_FIELDS))
            m2.metric("Answers received", int(inventory["Non-empty responses"].sum()))
            m3.metric("Respondents with coded excerpts", int(units["response_id"].nunique()) if not units.empty else 0)
            m4.metric("Themes", len(themes))
            r1, r2 = st.columns(2)
            r1.metric("Respondents with rating explanations", totals["rating_linked_respondents"])
            r2.metric("Respondents with overall feedback", totals["overall_feedback_respondents"])
            inventory_display = inventory.copy()
            inventory_display["Coverage"] = inventory_display["Coverage"].map(lambda value: f"{value:.0%}")
            st.dataframe(inventory_display, width="stretch", hide_index=True, height=38 + 35 * len(inventory_display))
            st.caption("Respondent counts describe coverage. Coded-excerpt counts describe the analysis work.")
        render_memos_workspace(db)


def mixed_methods_catalog(frame: pd.DataFrame, included: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    linked_group = "Linked feedback"
    other_group = "Other respondents"
    comparison_frame = frame.copy()
    response_ids = comparison_frame["response_id"].astype(str)
    included = {str(value) for value in included}
    comparison_frame["_qualitative_group"] = response_ids.map(
        lambda value: linked_group if value in included else other_group
    )
    scores = construct_scores(comparison_frame)
    rows: list[dict[str, object]] = []
    for construct in CONSTRUCTS:
        joint = pd.DataFrame(
            {
                "group": comparison_frame["_qualitative_group"],
                "score": pd.to_numeric(scores[construct], errors="coerce"),
            }
        ).dropna(subset=["score"])
        linked_scores = joint.loc[joint["group"] == linked_group, "score"]
        other_scores = joint.loc[joint["group"] == other_group, "score"]
        comparison = group_comparison(comparison_frame, "_qualitative_group", construct)
        p_value = comparison["p_value"]
        if comparison["test"]:
            result = "Significant" if pd.notna(p_value) and float(p_value) < 0.05 else "Not significant"
        else:
            result = "Not estimable"
        rows.append(
            {
                "Construct": construct,
                "Linked N": len(linked_scores),
                "Linked mean": linked_scores.mean() if len(linked_scores) else float("nan"),
                "Other N": len(other_scores),
                "Other mean": other_scores.mean() if len(other_scores) else float("nan"),
                "Difference": (
                    linked_scores.mean() - other_scores.mean()
                    if len(linked_scores) and len(other_scores)
                    else float("nan")
                ),
                "p-value": p_value,
                "Hedges’ g": comparison["effect"],
                "Result": result,
            }
        )
    return pd.DataFrame(rows), comparison_frame


def render_mixed_methods(db: Database) -> None:
    page_header(
        "Mixed methods",
        "Connect construct ratings with qualitative findings linked to a selected theme or working code.",
    )
    frame = require_data(db)
    if frame is None:
        return
    respondent_labels = database_respondent_labels(db)
    codes = db.codes()
    codes = codes[(codes["code_type"] != "Domain") & (codes["is_active"] == 1)] if not codes.empty else codes
    themes = db.themes()
    main_panel, side_panel = st.columns([3.8, 1.15], gap="large")
    controls = side_panel.container(border=True)
    mode = controls.selectbox(
        "Analyze",
        ["Theme", "Working code"],
        format_func=sentence_case_option,
        key="mixed_methods_lens",
    )

    if mode == "Working code":
        if codes.empty:
            controls.caption("No active working codes are available.")
            return
        code_index = codes.set_index("id")
        selected_id = controls.selectbox(
            "Working code",
            codes["id"].astype(int).tolist(),
            format_func=lambda value: sentence_case_option(code_index.loc[value, "name"]),
            key="mixed_methods_code",
        )
        selected = code_index.loc[selected_id]
        lens_name = str(selected["name"])
        codings = db.codings()
        linked_codings = codings[codings["code_id"] == selected_id] if not codings.empty else pd.DataFrame()
        included = set(linked_codings["response_id"].astype(str)) if not linked_codings.empty else set()
        excerpts = linked_codings
        with controls.expander("Working-code definition"):
            st.write(str(selected["description"]) or "No definition recorded.")
    else:
        if themes.empty:
            controls.caption("No themes are available.")
            return
        theme_index = themes.set_index("id")
        selected_id = controls.selectbox(
            "Theme",
            themes["id"].astype(int).tolist(),
            format_func=lambda value: sentence_case_option(theme_index.loc[value, "name"]),
            key="mixed_methods_theme",
        )
        selected = theme_index.loc[selected_id]
        lens_name = str(selected["name"])
        theme_codings = db.theme_codings()
        linked_codings = (
            theme_codings[theme_codings["theme_id"] == selected_id]
            if not theme_codings.empty
            else pd.DataFrame()
        )
        included = set(linked_codings["response_id"].astype(str)) if not linked_codings.empty else set()
        excerpts = db.theme_evidence(int(selected_id))
        with controls.expander("Theme details"):
            st.write(str(selected["description"]) or "No description recorded.")
            if str(selected["implication"]).strip():
                st.markdown("**Implication**")
                st.write(str(selected["implication"]))

    controls.metric("Linked respondents", len(included))
    controls.caption(f"{len(included)} of {len(frame)} responses contain coded feedback linked to this selection.")

    catalog, comparison_frame = mixed_methods_catalog(frame, included)
    display = catalog.copy()

    def integration_row_color(row: pd.Series) -> list[str]:
        color = (
            "background-color: #a7f0ba; color: #0e6027; font-weight: 600"
            if row["Result"] == "Significant"
            else ""
        )
        return [color] * len(row)

    with main_panel:
        st.subheader(f"{mode}: {lens_name}")
        st.caption(
            "Construct ratings for respondents with linked qualitative feedback and other respondents. "
            "Select a construct to view its distribution and test details."
        )
        remembered_rows_key = f"mixed_methods_selected_rows_{mode}_{selected_id}"
        remembered_rows = [
            int(index) for index in st.session_state.get(remembered_rows_key, [])
            if 0 <= int(index) < len(display)
        ]
        selection = st.dataframe(
            display.style.apply(integration_row_color, axis=1),
            width="stretch",
            height=(len(display) + 1) * 36 + 3,
            row_height=36,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key=f"mixed_methods_catalog_{mode}_{selected_id}",
            selection_default={"selection": {"rows": remembered_rows}},
            column_config={
                "Construct": st.column_config.TextColumn(width="medium"),
                "Linked N": st.column_config.NumberColumn(format="%d", width="small"),
                "Linked mean": st.column_config.NumberColumn(format="%.2f", width="small"),
                "Other N": st.column_config.NumberColumn(format="%d", width="small"),
                "Other mean": st.column_config.NumberColumn(format="%.2f", width="small"),
                "Difference": st.column_config.NumberColumn(format="%.2f", width="small"),
                "p-value": st.column_config.NumberColumn(format="%.4f", width="small"),
                "Hedges’ g": st.column_config.NumberColumn(format="%.3f", width="small"),
                "Result": st.column_config.TextColumn(width="medium"),
            },
        )
        selected_rows = selection.selection.rows
        st.session_state[remembered_rows_key] = list(selected_rows)
        if not selected_rows:
            st.caption("Select a construct row to view the individual ratings and test details.")
        else:
            selected_row = catalog.iloc[selected_rows[0]]
            outcome = str(selected_row["Construct"])
            scores = construct_scores(comparison_frame)
            joint = pd.DataFrame(
                {
                    "response_id": comparison_frame["response_id"].astype(str),
                    "score": scores[outcome],
                    "Feedback group": comparison_frame["_qualitative_group"],
                }
            ).dropna(subset=["score"])
            joint["Respondent"] = joint["response_id"].map(
                lambda value: respondent_label(value, respondent_labels)
            )
            st.divider()
            st.subheader(outcome)
            figure = px.box(
                joint,
                x="Feedback group",
                y="score",
                color="Feedback group",
                points="all",
                range_y=[1, 5],
                labels={"score": f"{outcome} score"},
                category_orders={"Feedback group": ["Linked feedback", "Other respondents"]},
                color_discrete_map={"Linked feedback": "#8a3ffc", "Other respondents": "#007d79"},
                hover_name="Respondent",
            )
            figure.update_layout(plot_bgcolor="white", paper_bgcolor="white", showlegend=False)
            st.plotly_chart(figure, width="stretch")

            result = group_comparison(comparison_frame, "_qualitative_group", outcome)
            controls.divider()
            controls.markdown("**Selected comparison**")
            controls.write(outcome)
            if result["test"]:
                controls.metric("p-value", fmt(result["p_value"], 4))
                controls.caption(
                    f"Welch’s t-test · difference {fmt(selected_row['Difference'], 3)} · "
                    f"Hedges’ g {fmt(result['effect'], 3)}"
                )
            else:
                controls.caption(str(result["warning"]) or "The comparison could not be estimated.")
            with controls.expander("Test details"):
                st.write(f"Linked feedback: N = {int(selected_row['Linked N'])}, mean = {fmt(selected_row['Linked mean'])}")
                st.write(f"Other respondents: N = {int(selected_row['Other N'])}, mean = {fmt(selected_row['Other mean'])}")
                if result["warning"]:
                    st.caption(str(result["warning"]))
                st.caption("Exploratory comparison; p-values are unadjusted across the seven constructs.")

        if not excerpts.empty:
            evidence_label = "theme evidence" if mode == "Theme" else "coded excerpts"
            evidence_rows = excerpts.drop_duplicates(
                subset=[
                    column
                    for column in ["response_id", "question_key", "excerpt"]
                    if column in excerpts
                ]
            )

            def render_compact_evidence(rows: pd.DataFrame) -> None:
                for _, item in rows.iterrows():
                    question_key = str(item.get("question_key", ""))
                    question_label = FIELD_BY_KEY[question_key].label if question_key in FIELD_BY_KEY else question_key
                    code_names = str(item.get("code_names", item.get("code_name", "")))
                    role = str(item.get("evidence_role", "")).strip().title()
                    details = " · ".join(value for value in [question_label, role] if value and value != "nan")
                    render_respondent_heading(
                        item["response_id"], respondent_label(item["response_id"], respondent_labels),
                        f'<span class="response-coding-status">{html.escape(details)}</span>',
                        key=f"mixed_{mode}_{selected_id}_{item.get('meaning_unit_id')}_{item.name}",
                    )
                    render_excerpt_highlights(
                        db, item.get("meaning_unit_id"), str(item["excerpt"]),
                        f"mixed_{mode}_{selected_id}_{item.get('meaning_unit_id')}_{item.name}",
                        fallback_code_names=code_names,
                    )

            if mode == "Theme":
                st.markdown(f"#### Theme evidence ({len(evidence_rows)})")
                ordered_rows = order_theme_evidence_for_display(evidence_rows)
                for role_key in EVIDENCE_ROLE_ORDER:
                    role_rows = ordered_rows[ordered_rows["_role_key"].eq(role_key)]
                    if role_rows.empty:
                        continue
                    with st.expander(
                        f"{role_key.title()} ({len(role_rows)})",
                        expanded=role_key == "supporting",
                        key=f"mixed_evidence_group_{mode}_{selected_id}_{role_key}",
                        on_change="rerun",
                    ):
                        render_compact_evidence(role_rows)
            else:
                with st.expander(
                    f"View {evidence_label} ({len(evidence_rows)})",
                    key=f"mixed_evidence_group_{mode}_{selected_id}_all",
                    on_change="rerun",
                ):
                    render_compact_evidence(evidence_rows)

    controls.caption(
        "Other respondents means no linked coded feedback was identified; it does not prove that the view was absent."
    )


def make_markdown_report(frame: pd.DataFrame, db: Database) -> str:
    summary = construct_summary(frame)
    lines = [
        "# FORAP Expert Evaluation: Analysis Snapshot",
        "",
        f"Active responses: **{len(frame)}**",
        "",
        "> Interpret all findings in light of the current sample size and sampling design.",
        "",
        "## Construct summary",
        "",
        "| Construct | N | Mean | SD | Median | Cronbach’s α |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in summary.iterrows():
        lines.append(f"| {row['construct']} | {int(row['n'])} | {fmt(row['mean'])} | {fmt(row['sd'])} | {fmt(row['median'])} | {fmt(row['alpha'], 3)} |")
    codes = db.codes()
    assignable_codes = codes[codes["code_type"] != "Domain"] if not codes.empty else codes
    codings = db.codings()
    units = db.meaning_units()
    themes = db.themes()
    evidence = db.theme_evidence()
    version = db.current_codebook_version()
    lines.extend(
        [
            "",
            "## Qualitative progress",
            "",
            f"Working-code set: **{version['label']} ({version['status']})**  " if version else "Working-code set: **Not set**  ",
            f"Active working codes: **{len(assignable_codes)}**  ",
            f"Coded excerpts: **{len(units)}**  ",
            f"Respondents with coded excerpts: **{units['response_id'].nunique() if not units.empty else 0}**  ",
            f"Code assignments: **{len(codings)}**  ",
            f"Candidate, reviewed, or final themes: **{len(themes)}**  ",
            f"Explicit theme-evidence links: **{len(evidence)}**",
            "",
            "## Method notes",
            "",
            "- Composite scores use a respondent’s item mean when at least half of the construct items are present.",
            "- Internal consistency uses complete cases within each construct.",
            "- Qualitative frequency is interpreted primarily as unique respondents mentioning a code or theme, not excerpt count.",
            "- Optional follow-up emails are excluded.",
            "",
        ]
    )
    return "\n".join(lines)


def render_reports(db: Database) -> None:
    page_header(
        "Reports & exports",
        "Preview the current analysis snapshot and download reporting or analysis-ready files without exposing follow-up emails.",
    )
    frame = require_data(db)
    if frame is None:
        return
    respondent_labels = database_respondent_labels(db)
    summary = item_summary(frame)
    scores = construct_scores(frame)
    codes = db.codes(active_only=False)
    codings = db.codings()
    units = db.meaning_units()
    themes = db.themes()
    theme_evidence = db.theme_evidence()
    thematic_summary = theme_reporting_table(db)
    report = make_markdown_report(frame, db)
    response_export = replace_response_ids(frame, respondent_labels)
    score_export = replace_response_ids(scores, respondent_labels)
    unit_export = replace_response_ids(units, respondent_labels)
    coding_export = replace_response_ids(codings, respondent_labels)
    evidence_export = replace_response_ids(theme_evidence, respondent_labels)
    exports: dict[str, tuple[pd.DataFrame, str, str]] = {
        "Data · Normalized responses": (
            response_export,
            "forap_responses.csv",
            "Response-level data with respondent labels. Review timestamps and free text before sharing.",
        ),
        "Data · Item statistics": (
            summary,
            "forap_item_statistics.csv",
            "Descriptive statistics and confidence intervals for questionnaire items.",
        ),
        "Data · Construct scores": (
            score_export,
            "forap_construct_scores.csv",
            "Respondent-level composite scores for the seven constructs.",
        ),
        "Qualitative · Working codes": (
            codes,
            "forap_working_codes.csv",
            "The working-code definitions and settings.",
        ),
        "Qualitative · Coded excerpts": (
            unit_export,
            "forap_coded_excerpts.csv",
            "The excerpts created during coding.",
        ),
        "Qualitative · Code assignments": (
            coding_export,
            "forap_codings.csv",
            "Links between excerpts, respondents, questions, and working codes.",
        ),
        "Qualitative · Highlight passages": (
            db.code_highlights(),
            "forap_code_highlight_passages.csv",
            "Exact highlighted passages by excerpt and code, with zero-based Unicode start and exclusive end positions.",
        ),
        "Qualitative · Highlight reviews": (
            db.highlight_reviews(),
            "forap_code_highlight_reviews.csv",
            "Every code assignment's highlight review status and note, including assignments not yet reviewed.",
        ),
        "Qualitative · Themes": (
            themes,
            "forap_themes.csv",
            "Theme names, descriptions, status, and implications.",
        ),
        "Qualitative · Theme evidence": (
            evidence_export,
            "forap_theme_evidence.csv",
            "Supporting, contextual, and contrasting evidence attached to themes.",
        ),
        "Qualitative · Thematic summary": (
            thematic_summary,
            "forap_thematic_summary.csv",
            "A reporting-ready summary of the themes and their evidence counts.",
        ),
    }

    main_panel, side_panel = st.columns([3.8, 1.15], gap="large")
    controls = side_panel.container(border=True)
    controls.markdown("**Downloads**")
    controls.download_button(
        "Analysis snapshot (.md)",
        report.encode("utf-8"),
        "forap_analysis_snapshot.md",
        "text/markdown",
        type="primary",
        width="stretch",
    )
    controls.divider()
    selected_export = controls.selectbox(
        "Data export",
        list(exports),
        format_func=sentence_case_option,
        key="report_data_export",
    )
    export_frame, export_filename, export_description = exports[selected_export]
    controls.download_button(
        "Download selected (.csv)",
        dataframe_csv(export_frame),
        export_filename,
        "text/csv",
        width="stretch",
        disabled=export_frame.empty,
    )
    controls.caption(export_description)
    controls.caption(f"{len(export_frame)} rows")
    controls.divider()
    controls.caption(f"{len(frame)} responses · {len(themes)} themes · {len(units)} coded excerpts")

    with main_panel:
        st.subheader("Analysis snapshot")
        preview = st.container(border=True)
        with preview:
            st.markdown(report)
        if not thematic_summary.empty:
            with st.expander("View thematic summary table"):
                st.dataframe(
                    thematic_summary,
                    width="stretch",
                    hide_index=True,
                    height=38 + 35 * len(thematic_summary),
                )


def main() -> None:
    # Restore navigation before Streamlit instantiates any keyed widgets.
    apply_pending_navigation(st.session_state)
    inject_styles()
    db = get_database(schema_revision="excerpt-highlights-v1")
    st.sidebar.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-brand-mark">FORAP</div>
            <div class="sidebar-brand-title">Evaluation Analysis</div>
            <div class="sidebar-brand-copy">Local expert-evaluation analysis</div>
        </div>
        <div class="sidebar-section-label">Workspace</div>
        """,
        unsafe_allow_html=True,
    )
    page = st.sidebar.radio(
        "Workspace",
        [
            "Overview",
            "Individual responses",
            "Items & scales",
            "Background comparisons",
            "Thematic analysis",
            "Mixed methods",
            "Reports & exports",
            "Upload & data health",
        ],
        label_visibility="collapsed",
        key="workspace_page",
    )
    st.sidebar.markdown(
        f"""
        <div class="sidebar-status">
            <strong>Local workspace</strong>
            <span>{html.escape(db.path.name)}<br>No network services</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    routes = {
        "Upload & data health": render_upload,
        "Overview": render_overview,
        "Individual responses": render_individual_responses,
        "Items & scales": render_items,
        "Background comparisons": render_comparisons,
        "Thematic analysis": render_thematic,
        "Mixed methods": render_mixed_methods,
        "Reports & exports": render_reports,
    }
    if page == "Individual responses":
        render_response_back_navigation()
    routes[page](db)


if __name__ == "__main__":
    main()
