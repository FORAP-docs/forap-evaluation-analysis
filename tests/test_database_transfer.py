from contextlib import contextmanager
from pathlib import Path
import sqlite3
import pytest
from forap_analysis.database import Database
from forap_analysis.database_transfer import BackupError, export_database, inspect_backup, restore_database, workspace_revision
from test_respondent_navigation_ui import navigation_database, database_signature


def test_full_workspace_round_trip_and_recovery(navigation_database, tmp_path):
    source, *_ = navigation_database
    with source.connect() as c:
        c.execute("INSERT INTO memos(title,content,scope,created_at,updated_at) VALUES ('Private note','Preserve me','study','now','now')")
        c.execute("UPDATE responses SET pii_json = ?", ('{"email":"synthetic@example.test"}',))
        c.execute("UPDATE imports SET is_active=0 WHERE id=1")
    before = database_signature(source)
    data = export_database(source)
    summary = inspect_backup(data)
    target = Database(tmp_path / 'target.sqlite3')
    target.save_code('Target-only code', '', '', '')
    previous = database_signature(target)
    recovery = restore_database(target, data, expected_sha256=summary.sha256)
    assert database_signature(target) == before
    assert database_signature(source) == before
    assert database_signature(Database(recovery)) == previous
    assert workspace_revision(target) == 1
    with target.connect() as c, source.connect() as s:
        assert c.execute('SELECT * FROM sqlite_sequence ORDER BY name').fetchall() == s.execute('SELECT * FROM sqlite_sequence ORDER BY name').fetchall()
    assert inspect_backup(export_database(target)).rows == summary.rows


def test_export_includes_committed_wal_without_changing_source(tmp_path):
    db = Database(tmp_path / 'wal.sqlite3')
    with sqlite3.connect(db.path) as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.execute("INSERT INTO memos(title,content,scope,created_at,updated_at) VALUES ('WAL note','Saved','study','now','now')")
        c.commit()
        assert Path(str(db.path) + '-wal').stat().st_size > 0
        assert inspect_backup(export_database(db)).rows['memos'] == 1


@pytest.mark.parametrize('bad', [b'', b'not a database', b'SQLite format 3\x00' + b'broken'])
def test_invalid_upload_does_not_modify_destination(tmp_path, bad):
    db = Database(tmp_path / 'target.sqlite3')
    before = database_signature(db)
    with pytest.raises(BackupError):
        restore_database(db, bad, expected_sha256='wrong')
    assert database_signature(db) == before
    assert not (tmp_path / 'backups').exists()


def test_changed_file_requires_new_validation(navigation_database, tmp_path):
    source, *_ = navigation_database
    target = Database(tmp_path / 'target.sqlite3')
    before = database_signature(target)
    with pytest.raises(BackupError, match='changed'):
        restore_database(target, export_database(source), expected_sha256='stale')
    assert database_signature(target) == before


@pytest.mark.parametrize('sql', [
    'CREATE TABLE extra_table (id INTEGER)',
    'ALTER TABLE memos ADD COLUMN unexpected TEXT',
    'CREATE VIEW hidden_view AS SELECT * FROM responses',
    "CREATE TRIGGER surprise AFTER INSERT ON memos BEGIN DELETE FROM responses; END",
    'PRAGMA user_version=999',
    "INSERT INTO theme_codes(theme_id,code_id) VALUES (999,999)",
])
def test_incompatible_or_broken_backup_rejected(tmp_path, sql):
    db = Database(tmp_path / 'source.sqlite3')
    with sqlite3.connect(db.path) as c:
        c.execute(sql)
    with pytest.raises(BackupError):
        inspect_backup(export_database(db))


def test_unrelated_sqlite_file_rejected(tmp_path):
    path = tmp_path / 'other.sqlite3'
    with sqlite3.connect(path) as c:
        c.execute('CREATE TABLE unrelated (x TEXT)')
    with pytest.raises(BackupError):
        inspect_backup(path.read_bytes())


def test_recovery_failure_preserves_destination(navigation_database, tmp_path, monkeypatch):
    import forap_analysis.database_transfer as transfer
    source, *_ = navigation_database
    target = Database(tmp_path / 'target.sqlite3')
    data = export_database(source)
    before = database_signature(target)
    def fail(*args):
        raise OSError('No space for recovery backup')
    monkeypatch.setattr(transfer, '_save_snapshot', fail)
    with pytest.raises(OSError):
        restore_database(target, data, expected_sha256=inspect_backup(data).sha256)
    assert database_signature(target) == before
    assert workspace_revision(target) == 0


def test_copy_failure_rolls_back_all_tables(navigation_database, tmp_path, monkeypatch):
    source, *_ = navigation_database
    target = Database(tmp_path / 'target.sqlite3')
    target.save_code('Keep this', '', '', '')
    before = database_signature(target)
    data = export_database(source)
    original_connect = target.connect
    class FailingConnection:
        def __init__(self, connection):
            self.connection = connection
        def execute(self, sql, *args):
            if sql.startswith('INSERT INTO main."meaning_units"'):
                raise sqlite3.OperationalError('Simulated write failure')
            return self.connection.execute(sql, *args)
    @contextmanager
    def failing_connect():
        with original_connect() as c:
            yield FailingConnection(c)
    monkeypatch.setattr(target, 'connect', failing_connect)
    with pytest.raises(BackupError):
        restore_database(target, data, expected_sha256=inspect_backup(data).sha256)
    assert database_signature(target) == before
    assert workspace_revision(target) == 0
    recovery = next((tmp_path / 'backups').glob('*.sqlite3'))
    assert database_signature(Database(recovery)) == before
