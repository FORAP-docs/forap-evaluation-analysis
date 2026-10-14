"""Legacy history is removed without changing the saved analysis or uploads."""
from contextlib import closing
import sqlite3
from types import SimpleNamespace

from forap_analysis.database import Database
from forap_analysis.database_history import LEGACY_HISTORY_SQL
from forap_analysis.database_transfer import export_database, inspect_backup, restore_database
from test_respondent_navigation_ui import navigation_database


MARKER = 'PRIVATE_HISTORY_MARKER_7ea02c /Users/example/private/old-plan.json'


def records(path):
    with closing(sqlite3.connect(path)) as connection:
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ) if row[0] not in LEGACY_HISTORY_SQL and row[0] != 'codebook_versions']
        return {table: connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall() for table in tables}


def add_legacy_history(db):
    with db.connect() as connection:
        for sql in LEGACY_HISTORY_SQL.values():
            connection.execute(sql)
        connection.execute("INSERT INTO memos(title,content,created_at,updated_at) VALUES ('Old note',?,'now','now')", (MARKER,))
        connection.execute("INSERT INTO audit_log(occurred_at,action,entity_type,details_json) VALUES ('now','update','code',?)", (MARKER,))
        connection.execute("INSERT INTO code_revisions(code_id,name,description,created_at) SELECT id,name,?,'now' FROM codes LIMIT 1", (MARKER,))
        connection.execute("INSERT INTO codebook_versions(id,label,description,created_at) VALUES (0,'Unused prior version',?,'now')", (MARKER,))
        connection.execute('PRAGMA user_version=0')


def assert_clean(path):
    assert MARKER.encode() not in path.read_bytes()
    with closing(sqlite3.connect(path)) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_schema WHERE type='table'")}
        assert not tables.intersection(LEGACY_HISTORY_SQL)
        assert connection.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
        assert not connection.execute('PRAGMA foreign_key_check').fetchall()
        assert connection.execute('SELECT COUNT(*) FROM codebook_versions WHERE id=0').fetchone()[0] == 0


def test_upgrade_preserves_analysis_and_uploads_and_stops_recording_history(navigation_database):
    db, *_ = navigation_database
    before = records(db.path)
    add_legacy_history(db)
    db = Database(db.path)
    assert records(db.path) == before
    assert_clean(db.path)
    recovery = next((db.path.parent / 'backups').glob('before_history_removal_*.sqlite3'))
    assert MARKER.encode() in recovery.read_bytes()
    db.save_code('New current code', 'Current definition', '', '')
    db.save_code('New current code', 'Updated definition', '', '')
    assert_clean(db.path)
    clean_export = db.path.parent / 'clean-export.sqlite3'
    clean_export.write_bytes(export_database(db))
    assert_clean(clean_export)


def test_legacy_import_excludes_history_and_preserves_source(navigation_database, tmp_path):
    source, *_ = navigation_database
    before = records(source.path)
    add_legacy_history(source)
    data = source.path.read_bytes()
    summary = inspect_backup(data)
    assert not set(summary.rows).intersection(LEGACY_HISTORY_SQL)
    target = Database(tmp_path / 'destination.sqlite3')
    restore_database(target, data, expected_sha256=summary.sha256)
    assert records(target.path) == before
    assert source.path.read_bytes() == data
    assert_clean(target.path)


def test_export_strips_legacy_history_without_modifying_source(navigation_database, tmp_path):
    source, *_ = navigation_database
    before = records(source.path)
    add_legacy_history(source)
    source_bytes = source.path.read_bytes()
    data = export_database(SimpleNamespace(path=source.path))
    output = tmp_path / 'export.sqlite3'
    output.write_bytes(data)
    assert records(output) == before
    assert source.path.read_bytes() == source_bytes
    assert_clean(output)
