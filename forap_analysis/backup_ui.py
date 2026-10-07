"""Local workspace backup controls shared by the application entry points."""
from datetime import datetime, timezone
import hashlib

import streamlit as st

from .database import Database
from .database_transfer import (
    BackupError, export_database, inspect_backup, restore_database, workspace_revision,
)
from .edit_mode import edit_mode_enabled


def reset_workspace_state(db: Database) -> None:
    revision = workspace_revision(db)
    if st.session_state.get('_workspace_revision', revision) != revision:
        st.session_state.clear()
        st.session_state['edit_mode'] = False
        st.session_state['workspace_page'] = 'Upload & data health'
    st.session_state['_workspace_revision'] = revision


def render_database_transfer(db: Database) -> None:
    with st.expander('Database backup & restore'):
        st.write('Transfer the complete workspace between installations, including all saved snapshots, coding, themes, highlights, notes, settings, and audit history.')
        st.warning('Database backups contain all stored responses and optional email addresses. Keep them private. They are not anonymized report exports.')
        if st.button('Prepare database export', key='prepare_database_export'):
            try:
                st.session_state['_database_export'] = export_database(db)
                st.session_state['_database_export_time'] = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            except (BackupError, OSError) as error:
                st.error(str(error))
        if '_database_export' in st.session_state:
            stamp = st.session_state['_database_export_time']
            st.download_button(
                'Download database (.sqlite3)', st.session_state['_database_export'],
                f'forap_workspace_{stamp}.sqlite3', 'application/vnd.sqlite3',
                key='download_database', on_click='ignore',
            )
            st.caption('This export contains the saved state at preparation time. Prepare it again after further edits.')
        if not edit_mode_enabled(st.session_state):
            st.caption('Enable Edit mode to import a database backup.')
            return
        st.divider()
        st.write('Import replaces the entire current workspace. It does not merge databases. A recovery copy of the current workspace is saved automatically before replacement. Close other app tabs before continuing.')
        uploaded = st.file_uploader('Database backup', type=['sqlite3', 'sqlite', 'db'], key='database_backup_upload')
        if uploaded is None:
            return
        data = uploaded.getvalue()
        fingerprint = hashlib.sha256(data).hexdigest()
        try:
            summary = inspect_backup(data)
        except (BackupError, OSError) as error:
            st.error(str(error))
            return
        st.caption('Backup validated. Counts include inactive records and earlier snapshots where applicable.')
        st.dataframe([
            {'Record type': name.replace('_', ' ').capitalize(), 'Count': count}
            for name, count in summary.rows.items()
        ], hide_index=True, width='stretch')
        st.write(f'Active responses in backup: {summary.active_responses}')
        confirmed = st.checkbox('I understand this will replace the current workspace.', key=f'confirm_restore_{fingerprint}')
        if st.button('Import database', key='import_database', disabled=not confirmed):
            try:
                recovery = restore_database(db, data, expected_sha256=summary.sha256)
            except (BackupError, OSError) as error:
                st.error(str(error))
                return
            st.session_state.clear()
            st.session_state['edit_mode'] = False
            st.session_state['_workspace_revision'] = workspace_revision(db)
            st.session_state['workspace_page'] = 'Upload & data health'
            st.session_state['_database_restore_message'] = f'Database imported. Previous workspace saved at {recovery}.'
            st.rerun()
