"""Theme comparisons respect selected evidence despite shared working codes."""

from test_respondent_navigation_ui import (
    database_signature,
    navigation_database,
    start_app,
)


def linked_count(app):
    return int(next(item.value for item in app.metric if item.label == "Linked respondents"))


def test_theme_comparison_uses_selected_evidence_not_every_shared_code(navigation_database):
    db, _, codes, _, themes = navigation_database
    before = database_signature(db)
    app = start_app(
        db, workspace_page="Mixed methods", mixed_methods_lens="Theme",
        mixed_methods_theme=themes[0],
    )
    # Two respondents share this theme's code, but only one quote was selected.
    assert linked_count(app) == 1
    app.selectbox(key="mixed_methods_theme").select(themes[1]).run()
    assert not app.exception
    # Selected contextual evidence from a different code also belongs to this theme.
    assert linked_count(app) == 2
    app.selectbox(key="mixed_methods_lens").select("Working code").run()
    app.selectbox(key="mixed_methods_code").select(codes[0]).run()
    assert not app.exception
    assert linked_count(app) == 2
    assert database_signature(db) == before
