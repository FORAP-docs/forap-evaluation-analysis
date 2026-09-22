"""Session-only respondent navigation, independent of Streamlit and the database.

Callbacks queue a transition; the app applies it before creating any widgets.
Only declared view state is copied, so Back cannot replay a button or a database
write. The saved snapshot also survives Streamlit cleaning up hidden widgets.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from copy import deepcopy
from numbers import Integral
import re
from typing import Any


MAX_HISTORY = 20
_HISTORY_KEY = "_response_navigation_history"
_PENDING_KEY = "_response_navigation_pending"

_VIEW_KEYS = frozenset({
    "workspace_page",
    "individual_response_selection",
    "thematic_tab",
    "all_open_text_question",
    "all_open_text_active_question",
    "all_open_text_response_position",
    "active_meaning_unit_editor",
    "theme_detail_selection",
    "selected_theme_id",
    "mixed_methods_lens",
    "mixed_methods_code",
    "mixed_methods_theme",
    "integration_theme",
    "integration_construct",
})
_VIEW_PATTERNS = tuple(re.compile(pattern) for pattern in (
    r"working_code_excerpt_(?:question|search)_\d+",
    r"theme_evidence_group_\d+_(?:supporting|contextual|contrasting)",
    r"theme_evidence_details_\d+_\d+",
    r"mixed_evidence_group_(?:Theme|Working code)_\d+_(?:supporting|contextual|contrasting|all)",
    r"mixed_methods_selected_rows_(?:Theme|Working code)_\d+",
    r"all_open_text_unit_(?:codes|excerpt|note)_.+",
    r"(?:code_popup|coding_all_open_text|theme|mixed|integration|all_open_text)_.+_"
    r"(?:edit_code|draft|phrase|status|note|remove_selection|occurrence_[0-9a-f]+)",
))


def _is_view_key(key: object) -> bool:
    return isinstance(key, str) and (
        key in _VIEW_KEYS or any(pattern.fullmatch(key) for pattern in _VIEW_PATTERNS)
    )


def _capture(state: MutableMapping[str, Any], origin: dict | None) -> dict[str, Any]:
    view = {key: deepcopy(value) for key, value in state.items() if _is_view_key(key)}
    view.setdefault("workspace_page", "Overview")
    source = origin or {}
    location: dict[str, Any] = {}
    if isinstance(source.get("label"), str) and source["label"].strip():
        location["label"] = source["label"].strip()
    dialog_code_id = source.get("dialog_code_id")
    if isinstance(dialog_code_id, Integral) and not isinstance(dialog_code_id, bool) and dialog_code_id > 0:
        location["dialog_code_id"] = int(dialog_code_id)
    return {"view": view, "origin": location}


def request_response(
    state: MutableMapping[str, Any],
    response_id: str,
    *,
    origin: dict | None = None,
) -> bool:
    """Queue opening an exact database response ID and remember this location.

    ``origin`` may supply a human-readable ``label`` and ``dialog_code_id``.
    Respondent labels such as R1 are display text, not navigation identifiers.
    The caller must resolve them to the stable response ID before calling this.
    """
    if not isinstance(response_id, str) or not response_id.strip():
        raise ValueError("A non-empty stable response ID is required.")
    if (
        state.get("workspace_page") == "Individual responses"
        and state.get("individual_response_selection") == response_id
    ):
        return False
    state[_PENDING_KEY] = {
        "action": "response",
        "response_id": response_id,
        "return_to": _capture(state, origin),
    }
    return True


def request_back(state: MutableMapping[str, Any]) -> bool:
    """Queue returning to the most recent saved location, if one exists."""
    if not state.get(_HISTORY_KEY):
        return False
    state[_PENDING_KEY] = {"action": "back"}
    return True


def apply_pending_navigation(state: MutableMapping[str, Any]) -> bool:
    """Apply one queued transition before widgets render; never touch the DB."""
    pending = state.pop(_PENDING_KEY, None)
    if not pending:
        return False
    history = list(state.get(_HISTORY_KEY, []))
    if pending["action"] == "response":
        history.append(pending["return_to"])
        state[_HISTORY_KEY] = history[-MAX_HISTORY:]
        state["workspace_page"] = "Individual responses"
        state["individual_response_selection"] = pending["response_id"]
        # This is a one-shot dialog trigger, not a view setting.
        state.pop("working_code_details_id", None)
        state.pop("working_code_color_id", None)
        return True
    if pending["action"] == "back" and history:
        location = history.pop()
        for key in list(state):
            if _is_view_key(key):
                del state[key]
        state.update(deepcopy(location["view"]))
        state[_HISTORY_KEY] = history
        state.pop("working_code_details_id", None)
        state.pop("working_code_color_id", None)
        dialog_code_id = location["origin"].get("dialog_code_id")
        if dialog_code_id is not None:
            state["working_code_details_id"] = dialog_code_id
        return True
    return False


def back_label(state: MutableMapping[str, Any]) -> str | None:
    """Describe the next Back destination without changing navigation state."""
    history = state.get(_HISTORY_KEY, [])
    if not history:
        return None
    location = history[-1]
    label = location["origin"].get("label")
    if not label:
        view = location["view"]
        label = view.get("workspace_page", "Overview")
        if label == "Thematic analysis":
            label = view.get("thematic_tab", "Thematic analysis")
    return f"Back to {label}"
