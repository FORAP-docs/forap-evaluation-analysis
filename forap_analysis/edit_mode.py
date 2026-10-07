"""Keep unsaved editor inputs when the interface switches to read-only mode.

This is session-local UI convenience, not authorization. Call the change handler
from the Edit mode toggle callback, before Streamlit renders or cleans up widgets.
Only declared editor inputs are saved; navigation and actions are never replayed.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from copy import deepcopy
import re
from typing import Any

from .schema import BACKGROUND_FIELDS


_DRAFTS_KEY = "_edit_mode_saved_drafts"
_EDITOR_KEYS = frozenset({
    "active_meaning_unit_editor",
    "edit_code_name",
    "edit_code_description",
    "edit_code_inclusion",
    "edit_code_exclusion",
    "edit_codebook_label",
    "edit_codebook_description",
    "edit_memo_title",
    "edit_memo_content",
})
_HIGHLIGHT_PREFIX = (
    r"(?:code_popup|coding_all_open_text|theme|mixed|integration|all_open_text)_.+"
)
_BACKGROUND_FIELD = "(?:" + "|".join(re.escape(field.key) for field in BACKGROUND_FIELDS) + ")"
_EDITOR_PATTERNS = tuple(re.compile(pattern) for pattern in (
    r"edit_theme_(?:\d+|new)_(?:name|description|status|constructs|codes|contrasting|implication)",
    r"edit_theme_evidence_\d+_(?:unit|role|note)",
    # The final component is a saved excerpt ID or the new-excerpt editor.
    r"all_open_text_unit_(?:codes|excerpt|note)_all_open_text:[^:]+:[^:]+_(?:\d+|new)",
    # These are selectors *inside* the passage editor, not navigation controls.
    _HIGHLIGHT_PREFIX + r"_edit_code",
    _HIGHLIGHT_PREFIX + r"_\d+_[0-9a-f]{16}_"
    r"(?:draft|phrase|status|note|remove_selection|occurrence_[0-9a-f]{12})",
    r"custom_group_count_" + _BACKGROUND_FIELD,
    r"custom_group_name_" + _BACKGROUND_FIELD + r"_\d+",
    r"custom_group_" + _BACKGROUND_FIELD + r"_save_name",
))


def _is_editor_key(key: object) -> bool:
    return isinstance(key, str) and (
        key in _EDITOR_KEYS
        or any(pattern.fullmatch(key) for pattern in _EDITOR_PATTERNS)
    )


def edit_mode_enabled(state: MutableMapping[str, Any]) -> bool:
    """Start in read-only mode unless the Edit mode toggle is explicitly on."""
    return state.get("edit_mode", False) is True


def handle_edit_mode_change(state: MutableMapping[str, Any]) -> None:
    """Stash editor drafts on disable and restore them on enable, without I/O.

    The stash is consumed when restored, so a later cancelled editor is not
    revived from an older edit session. Repeated disable calls retain already
    hidden drafts. Values are copied on both capture and restore.
    """
    saved = state.get(_DRAFTS_KEY, {})
    if not isinstance(saved, Mapping):
        saved = {}
    if edit_mode_enabled(state):
        state.pop(_DRAFTS_KEY, None)
        for key, value in saved.items():
            # Recheck the allowlist even for a pre-existing or modified stash.
            if _is_editor_key(key):
                state[key] = deepcopy(value)
        return

    drafts = {key: deepcopy(value) for key, value in saved.items() if _is_editor_key(key)}
    drafts.update({key: deepcopy(value) for key, value in state.items() if _is_editor_key(key)})
    state[_DRAFTS_KEY] = drafts
    # Unlike a details dialog, this dialog writes immediately when a colour is picked.
    state.pop("working_code_color_id", None)
