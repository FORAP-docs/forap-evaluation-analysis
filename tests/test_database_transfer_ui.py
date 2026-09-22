from pathlib import Path
from streamlit.testing.v1 import AppTest
from forap_analysis.database import Database
from forap_analysis.database_transfer import export_database, inspect_backup, restore_database
from test_respondent_navigation_ui import navigation_database, database_signature


def backup_app(database_path: str, upload_path: str = '') -> None:
    import io
    from pathlib import Path
    import streamlit as st
    import app
    from forap_analysis.database import Database
    get_database = app.get_database
    file_uploader = st.file_uploader
    app.get_database = lambda **kwargs: Database(Path(database_path))
    def upload(label, *args, **kwargs):
        if label == 'Database backup' and upload_path:
            return io.BytesIO(Path(upload_path).read_bytes())
        return file_uploader(label, *args, **kwargs)
    st.file_uploader = upload
    try:
        app.main()
    finally:
        app.get_database = get_database
        st.file_uploader = file_uploader


def start(db, upload=None, edit=False):
    app = AppTest.from_function(backup_app, args=(str(db.path), str(upload) if upload else ''), default_timeout=20)
    app.session_state['workspace_page'] = 'Upload & data health'
    app.session_state['edit_mode'] = edit
    app.run()
    assert not app.exception
    return app


def test_empty_workspace_can_export_without_edit_mode(tmp_path):
    db = Database(tmp_path / 'empty.sqlite3')
    app = start(db)
    app.button(key='prepare_database_export').click().run()
    assert not app.exception
    assert inspect_backup(app.session_state['_database_export']).active_responses == 0
    assert not any(b.key == 'import_database' for b in app.button)


def test_restore_requires_confirmation_and_clears_old_state(navigation_database, tmp_path):
    source, *_ = navigation_database
    uploaded = tmp_path / 'source.sqlite3'
    uploaded.write_bytes(export_database(source))
    target = Database(tmp_path / 'target.sqlite3')
    app = start(target, uploaded, edit=True)
    assert app.button(key='import_database').disabled
    assert target.active_count() == 0
    app.session_state['old_editor_draft'] = 'Should not survive replacement'
    app.checkbox[0].check().run()
    app.button(key='import_database').click().run()
    assert not app.exception
    assert database_signature(target) == database_signature(source)
    assert app.session_state['edit_mode'] is False
    assert 'old_editor_draft' not in app.session_state
    assert any('Database imported' in message.value for message in app.success)


def test_invalid_file_shows_error_without_import_button(tmp_path):
    target = Database(tmp_path / 'target.sqlite3')
    bad = tmp_path / 'bad.sqlite3'
    bad.write_bytes(b'not sqlite')
    app = start(target, bad, edit=True)
    assert app.error
    assert not any(b.key == 'import_database' for b in app.button)


def test_other_session_forgets_stale_edits_after_restore(navigation_database, tmp_path):
    source, *_ = navigation_database
    target = Database(tmp_path / 'target.sqlite3')
    app = start(target, edit=True)
    app.session_state['old_editor_draft'] = 'Stale'
    data = export_database(source)
    restore_database(target, data, expected_sha256=inspect_backup(data).sha256)
    app.run()
    assert not app.exception
    assert 'old_editor_draft' not in app.session_state
    assert app.session_state['edit_mode'] is False
