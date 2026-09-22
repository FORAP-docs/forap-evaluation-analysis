from copy import deepcopy

import pytest

from forap_analysis.navigation import (
    MAX_HISTORY,
    apply_pending_navigation,
    back_label,
    request_back,
    request_response,
)


def open_response(state, response_id="stable-response-83", **kwargs):
    assert request_response(state, response_id, **kwargs)
    assert apply_pending_navigation(state)
    assert state["workspace_page"] == "Individual responses"
    assert state["individual_response_selection"] == response_id


def go_back(state):
    assert request_back(state)
    assert apply_pending_navigation(state)


def test_open_uses_stable_id_and_queues_widget_changes_until_next_run():
    state = {"workspace_page": "Thematic analysis", "thematic_tab": "Working codes"}
    assert request_response(state, "response-uuid-not-R83")
    assert state["workspace_page"] == "Thematic analysis"
    assert "individual_response_selection" not in state
    assert apply_pending_navigation(state)
    assert state["individual_response_selection"] == "response-uuid-not-R83"
    assert back_label(state) == "Back to Working codes"
    assert not apply_pending_navigation(state)


@pytest.mark.parametrize("response_id", ["", "  ", None, 83])
def test_invalid_response_ids_do_not_change_state(response_id):
    state = {"workspace_page": "Overview"}
    with pytest.raises(ValueError, match="stable response ID"):
        request_response(state, response_id)
    assert state == {"workspace_page": "Overview"}


def test_back_restores_review_question_position_and_discarded_widget_keys():
    state = {
        "workspace_page": "Thematic analysis",
        "thematic_tab": "Review responses",
        "all_open_text_question": {"key": "clarity_comments"},
        "all_open_text_active_question": "clarity_comments",
        "all_open_text_response_position": 7,
    }
    expected = deepcopy(state)
    open_response(state)
    for key in tuple(expected):
        state.pop(key, None)  # Streamlit removes widgets not rendered on the new page.
    state["workspace_page"] = "Individual responses"
    go_back(state)
    assert all(state[key] == value for key, value in expected.items())
    assert "individual_response_selection" not in state
    assert back_label(state) is None


def test_snapshot_copies_mutable_values_and_only_known_origin_metadata():
    rows = [2]
    origin = {"label": "Selected evidence", "unrelated": ["not needed"]}
    state = {"workspace_page": "Mixed methods", "mixed_methods_selected_rows_Theme_4": rows}
    assert request_response(state, "response-83", origin=origin)
    rows.append(3)
    origin["label"] = "Changed"
    assert apply_pending_navigation(state)
    assert back_label(state) == "Back to Selected evidence"
    go_back(state)
    assert state["mixed_methods_selected_rows_Theme_4"] == [2]


def test_back_restores_code_dialog_and_its_filters_once():
    state = {
        "workspace_page": "Thematic analysis",
        "thematic_tab": "Working codes",
        "working_code_details_id": 94,
        "working_code_excerpt_question_94": "Completeness",
        "working_code_excerpt_search_94": "ethics",
    }
    open_response(state, origin={"dialog_code_id": 94, "label": "XC7 excerpts"})
    assert "working_code_details_id" not in state
    assert back_label(state) == "Back to XC7 excerpts"
    state.pop("working_code_excerpt_question_94")
    state.pop("working_code_excerpt_search_94")
    go_back(state)
    assert state.pop("working_code_details_id") == 94
    assert state["working_code_excerpt_question_94"] == "Completeness"
    assert state["working_code_excerpt_search_94"] == "ethics"
    assert not apply_pending_navigation(state)
    assert "working_code_details_id" not in state


def test_back_preserves_theme_mixed_filters_and_open_evidence_groups():
    state = {
        "workspace_page": "Mixed methods",
        "mixed_methods_lens": "Working code",
        "mixed_methods_code": 94,
        "mixed_methods_theme": 5,
        "theme_detail_selection": 3,
        "selected_theme_id": 3,
        "theme_evidence_group_3_contrasting": True,
        "theme_evidence_details_3_17": True,
        "mixed_evidence_group_Working code_94_all": True,
        "mixed_evidence_group_Theme_5_contextual": True,
        "mixed_methods_selected_rows_Working code_94": [3],
        "integration_theme": 3,
        "integration_construct": "Clarity",
    }
    expected = deepcopy(state)
    open_response(state)
    for key in tuple(expected):
        state.pop(key, None)
    go_back(state)
    assert all(state[key] == value for key, value in expected.items())


def test_back_keeps_editor_drafts_without_replaying_save_or_toggle_actions():
    prefix = "code_popup_94_370_94_abcdef0123456789"
    preserved = {
        "active_meaning_unit_editor": "all_open_text:unit:370",
        "all_open_text_unit_codes_all_open_text:clarity:uuid_370": [94],
        "all_open_text_unit_excerpt_all_open_text:clarity:uuid_370": "Exact words",
        "all_open_text_unit_note_all_open_text:clarity:uuid_370": "Unsaved note",
        "code_popup_94_370_edit_code": 94,
        "coding_all_open_text_370_edit_code": 94,
        "coding_all_open_text_370_94_abcdef0123456789_phrase": "Exact words",
        f"{prefix}_draft": [(0, 5)],
        f"{prefix}_phrase": "ethics",
        f"{prefix}_status": "needs_review",
        f"{prefix}_note": "Check this",
        f"{prefix}_remove_selection": [(0, 5)],
        f"{prefix}_occurrence_a123456789bc": 0,
    }
    actions = {
        "working_code_details_click": {"row": 2},
        "mixed_methods_catalog_Working code_94": {"selection": {"rows": [3]}},
        "theme_evidence_representative_3_17": True,
        "all_open_text_save_unit_all_open_text:clarity:uuid_370": True,
        "all_open_text_delete_unit_370": True,
        "all_open_text_clarity_previous": True,
        "coding_all_open_text_370_94_abcdef0123456789_save": True,
        f"{prefix}_add": True,
        f"{prefix}_remove": True,
        f"{prefix}_save": True,
        f"{prefix}_reset": True,
        f"{prefix}_original": "Readonly excerpt",
    }
    state = {"workspace_page": "Thematic analysis", **deepcopy(preserved), **actions}
    open_response(state)
    for key in (*preserved, *actions):
        state.pop(key)
    go_back(state)
    assert all(state[key] == value for key, value in preserved.items())
    assert not any(key in state for key in actions)


def test_unrelated_large_objects_are_not_copied_or_changed():
    class NotCopyable:
        def __deepcopy__(self, memo):
            raise AssertionError("Unrelated object should not be copied")

    database = NotCopyable()
    state = {"db": database, "import_preview": NotCopyable(), "individual_response_next": True}
    open_response(state)
    state["individual_response_next"] = False
    go_back(state)
    assert state["workspace_page"] == "Overview"
    assert state["db"] is database
    assert state["individual_response_next"] is False


def test_empty_back_and_same_response_are_noops():
    state = {"workspace_page": "Individual responses", "individual_response_selection": "uuid"}
    expected = dict(state)
    assert back_label(state) is None
    assert not request_back(state)
    assert not apply_pending_navigation(state)
    assert not request_response(state, "uuid")
    assert state == expected


def test_two_dialog_roundtrips_return_to_each_current_origin():
    state = {"workspace_page": "Thematic analysis", "thematic_tab": "Working codes"}
    for code_id, response_id, search in [(94, "uuid-a", "ethics"), (51, "uuid-b", "relationships")]:
        state[f"working_code_excerpt_search_{code_id}"] = search
        open_response(state, response_id, origin={"dialog_code_id": code_id})
        go_back(state)
        assert state.pop("working_code_details_id") == code_id
        assert state[f"working_code_excerpt_search_{code_id}"] == search
        assert state["workspace_page"] == "Thematic analysis"
        assert state["thematic_tab"] == "Working codes"
        assert back_label(state) is None


def test_nested_navigation_returns_in_last_in_first_out_order():
    state = {"workspace_page": "Thematic analysis", "thematic_tab": "Build themes"}
    open_response(state, "uuid-a")
    open_response(state, "uuid-b")
    assert back_label(state) == "Back to Individual responses"
    go_back(state)
    assert state["individual_response_selection"] == "uuid-a"
    assert back_label(state) == "Back to Build themes"
    go_back(state)
    assert state["workspace_page"] == "Thematic analysis"
    assert back_label(state) is None


def test_history_is_bounded_and_session_local():
    state = {"workspace_page": "Overview"}
    for index in range(MAX_HISTORY + 5):
        open_response(state, f"uuid-{index}")
    for _ in range(MAX_HISTORY):
        go_back(state)
    assert state["individual_response_selection"] == "uuid-4"
    assert not request_back(state)
    assert back_label({}) is None
