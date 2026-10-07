from copy import deepcopy

import pytest

from forap_analysis.edit_mode import edit_mode_enabled, handle_edit_mode_change


def toggle(state, enabled):
    state["edit_mode"] = enabled
    handle_edit_mode_change(state)


def test_default_is_read_only_without_mutating_state():
    state = {}
    assert not edit_mode_enabled(state)
    assert state == {}
    assert edit_mode_enabled({"edit_mode": True})
    assert not edit_mode_enabled({"edit_mode": False})


@pytest.mark.parametrize("value", [None, "false", "true", 0, 1, [], {}])
def test_only_an_explicit_enabled_toggle_turns_edit_mode_on(value):
    assert not edit_mode_enabled({"edit_mode": value})


def test_off_on_restores_declared_forms_after_widget_cleanup():
    drafts = {
        "edit_code_name": "Plain name",
        "edit_code_description": "A definition.",
        "edit_code_inclusion": "Include direct statements.",
        "edit_code_exclusion": "Exclude unrelated points.",
        "edit_codebook_label": "Next version",
        "edit_codebook_description": "A working version.",
        "edit_memo_title": "Review note",
        "edit_memo_content": "Check this excerpt.",
        "edit_theme_new_name": "A new theme",
        "edit_theme_new_description": "A draft account.",
        "edit_theme_12_status": "candidate",
        "edit_theme_12_constructs": ["Clarity"],
        "edit_theme_12_codes": [51, 53],
        "edit_theme_12_contrasting": "A different view.",
        "edit_theme_12_implication": "Show an example.",
        "edit_theme_evidence_12_unit": 311,
        "edit_theme_evidence_12_role": "contextual",
        "edit_theme_evidence_12_note": "This sets a limit.",
    }
    state = deepcopy(drafts)
    toggle(state, False)
    for key in drafts:
        state.pop(key)  # Streamlit drops widgets hidden in read-only mode.
    toggle(state, True)
    assert all(state[key] == value for key, value in drafts.items())


def test_meaning_unit_and_highlight_editor_drafts_survive_toggle():
    prefix = "code_popup_94_370_94_abcdef0123456789"
    drafts = {
        "active_meaning_unit_editor": "all_open_text:unit:370",
        "all_open_text_unit_codes_all_open_text:clarity_comments:uuid_370": [94],
        "all_open_text_unit_excerpt_all_open_text:clarity_comments:uuid_370": "Exact words",
        "all_open_text_unit_note_all_open_text:clarity_comments:uuid_new": "Unsaved interpretation",
        "code_popup_94_370_edit_code": 94,
        "coding_all_open_text_370_edit_code": 94,
        "theme_12_370_94_abcdef0123456789_phrase": "Exact words",
        "integration_12_370_94_abcdef0123456789_note": "An unsaved note",
        "mixed_Working code_94_370_0_94_abcdef0123456789_status": "needs_review",
        f"{prefix}_draft": [(0, 5), (12, 20)],
        f"{prefix}_phrase": "ethics",
        f"{prefix}_status": "needs_review",
        f"{prefix}_note": "Check this",
        f"{prefix}_remove_selection": [(0, 5)],
        f"{prefix}_occurrence_a123456789bc": 1,
    }
    state = deepcopy(drafts)
    toggle(state, False)
    for key in drafts:
        state.pop(key)
    toggle(state, True)
    assert all(state[key] == value for key, value in drafts.items())


def test_capture_and_restore_both_deepcopy_mutable_drafts():
    codes = [51]
    state = {"edit_theme_12_codes": codes}
    toggle(state, False)
    saved = state["_edit_mode_saved_drafts"]
    codes.append(99)
    assert saved["edit_theme_12_codes"] == [51]
    state.pop("edit_theme_12_codes")
    toggle(state, True)
    assert state["edit_theme_12_codes"] == [51]
    state["edit_theme_12_codes"].append(53)
    assert saved["edit_theme_12_codes"] == [51]
    assert "_edit_mode_saved_drafts" not in state


def test_custom_group_form_inputs_survive_without_replaying_selection_or_editor_delta():
    drafts = {
        "custom_group_count_years_experience": 3,
        "custom_group_name_years_experience_0": "New instructors",
        "custom_group_name_years_experience_1": "Experienced instructors",
        "custom_group_years_experience_save_name": "Experience comparison",
        "custom_group_count_roles": 2,
        "custom_group_roles_save_name": "Role groups",
    }
    non_drafts = {
        "custom_group_years_experience_saved_selection": 12,
        "custom_group_years_experience_active_selection": 12,
        "custom_group_years_experience_pending_selection": 12,
        "custom_group_years_experience_save": True,
        "custom_group_years_experience_delete": True,
        "custom_group_assignments_years_experience_2": {"edited_rows": {0: {"Group": "New"}}},
        "custom_group_count_years_experience_submit": True,
    }
    assignments = {"respondent-a": "Group 1"}
    state = {**drafts, **non_drafts, "custom_group_years_experience_assignments": assignments}
    toggle(state, False)
    for key in (*drafts, *non_drafts):
        state.pop(key)
    toggle(state, True)
    assert all(state[key] == value for key, value in drafts.items())
    assert not any(key in state for key in non_drafts)
    assert state["custom_group_years_experience_assignments"] is assignments


def test_disable_clears_only_color_dialog_trigger_not_details_or_navigation():
    state = {
        "working_code_color_id": 94,
        "working_code_details_id": 94,
        "workspace_page": "Thematic analysis",
        "thematic_tab": "Working codes",
    }
    toggle(state, False)
    assert "working_code_color_id" not in state
    assert state["working_code_details_id"] == 94
    assert state["workspace_page"] == "Thematic analysis"
    assert state["thematic_tab"] == "Working codes"


def test_navigation_auto_save_and_action_state_is_never_restored():
    prefix = "code_popup_94_370_94_abcdef0123456789"
    forbidden = {
        "workspace_page": "Thematic analysis",
        "thematic_tab": "Working codes",
        "individual_response_selection": "old-uuid",
        "all_open_text_question": "clarity_comments",
        "all_open_text_response_position": 8,
        "selected_theme_id": 12,
        "theme_detail_selection": 12,
        "mixed_methods_code": 94,
        "integration_theme": 12,
        "_response_navigation_pending": {"action": "back"},
        "_response_navigation_history": [{"view": {"workspace_page": "Overview"}}],
        "working_code_details_id": 94,
        "working_code_details_click": True,
        "working_code_color_value_94": "#0f62fe",
        "theme_evidence_representative_12_370": True,
        "theme_evidence_details_12_370": True,
        "code_popup_94_370_view": 94,
        "all_open_text_save_unit_all_open_text:clarity_comments:uuid_370": True,
        "all_open_text_delete_unit_370": True,
        "edit_code_save": True,
        "edit_code_delete": True,
        "edit_theme_12_save": True,
        "edit_theme_new_submit": True,
        "edit_theme_evidence_12_submit": True,
        "FormSubmitter:theme_editor-Save": True,
        f"{prefix}_original": "Readonly excerpt",
        f"{prefix}_add": True,
        f"{prefix}_remove": True,
        f"{prefix}_save": True,
        f"{prefix}_reset": True,
        f"{prefix}_button": True,
    }
    state = deepcopy(forbidden)
    state["edit_code_name"] = "Keep this draft"
    toggle(state, False)
    for key in forbidden:
        state.pop(key, None)
    state["workspace_page"] = "Overview"
    toggle(state, True)
    assert state["workspace_page"] == "Overview"
    assert not any(key in state for key in forbidden if key != "workspace_page")
    assert state["edit_code_name"] == "Keep this draft"
    assert state["edit_mode"] is True


def test_restoration_rechecks_allowlist_and_does_not_replay_poisoned_stash():
    state = {"_edit_mode_saved_drafts": {
        "edit_mode": False,
        "workspace_page": "Upload & data health",
        "working_code_color_id": 94,
        "theme_evidence_representative_12_370": True,
        "edit_theme_12_delete": True,
        "edit_code_name": "Safe draft",
    }}
    toggle(state, True)
    assert state == {"edit_mode": True, "edit_code_name": "Safe draft"}


def test_repeated_disable_preserves_hidden_drafts_but_consumed_stash_does_not_revive_cancelled_editor():
    state = {"active_meaning_unit_editor": "all_open_text:unit:370", "edit_memo_content": "Draft"}
    toggle(state, False)
    state.pop("active_meaning_unit_editor")
    state.pop("edit_memo_content")
    toggle(state, False)
    toggle(state, True)
    assert state["edit_memo_content"] == "Draft"
    state.pop("active_meaning_unit_editor")  # Cancelled while editing is enabled.
    toggle(state, False)
    toggle(state, True)
    assert "active_meaning_unit_editor" not in state


def test_unrelated_objects_and_navigation_are_not_copied():
    class NotCopyable:
        def __deepcopy__(self, memo):
            raise AssertionError("Unrelated object should not be copied")

    database = NotCopyable()
    navigation = {"action": "back"}
    state = {"database": database, "import_preview": NotCopyable(), "_response_navigation_pending": navigation}
    toggle(state, False)
    toggle(state, True)
    assert state["database"] is database
    assert state["_response_navigation_pending"] is navigation


def test_enabling_without_stash_and_malformed_stash_are_safe():
    state = {"edit_code_name": "Current value"}
    toggle(state, True)
    assert state["edit_code_name"] == "Current value"
    state["_edit_mode_saved_drafts"] = None
    toggle(state, False)
    state.pop("edit_code_name")
    toggle(state, True)
    assert state["edit_code_name"] == "Current value"
