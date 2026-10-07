"""Export consistent SQLite backups and restore compatible workspaces atomically."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import threading
from uuid import uuid4

from .database import Database

MAX_BACKUP_BYTES = 50 * 1024 * 1024
_REVISIONS: dict[str, int] = {}
_TRANSFER_LOCK = threading.RLock()


class BackupError(ValueError):
    """A backup cannot safely be used by this version of the application."""


@dataclass(frozen=True)
class BackupSummary:
    sha256: str
    rows: dict[str, int]
    active_responses: int


def workspace_revision(db: Database) -> int:
    return _REVISIONS.get(str(db.path.resolve()), 0)


def _readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    connection.execute('PRAGMA trusted_schema = OFF')
    connection.execute('PRAGMA query_only = ON')
    return connection


def _schema(connection: sqlite3.Connection) -> dict:
    # Only the known application tables are accepted, without executable views
    # or triggers. Column and foreign-key layouts must match this app version.
    if connection.execute("SELECT 1 FROM sqlite_schema WHERE type IN ('view', 'trigger')").fetchone():
        raise BackupError('Database backups containing views or triggers are not supported.')
    tables = connection.execute(
        "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    result = {}
    for (name,) in tables:
        quoted = '"' + name.replace('"', '""') + '"'
        result[name] = (
            tuple(tuple(row) for row in connection.execute(f'PRAGMA table_xinfo({quoted})')),
            tuple(sorted(tuple(row) for row in connection.execute(f'PRAGMA foreign_key_list({quoted})'))),
        )
    return result


@lru_cache(maxsize=1)
def _expected_schema() -> dict:
    with tempfile.TemporaryDirectory(prefix='forap-schema-') as folder:
        reference = Database(Path(folder) / 'reference.sqlite3')
        with closing(_readonly(reference.path)) as connection:
            return _schema(connection)


def _validate(connection: sqlite3.Connection) -> tuple[dict[str, int], int]:
    if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
        raise BackupError('The database failed its SQLite integrity check.')
    if connection.execute('PRAGMA user_version').fetchone()[0] != 0:
        raise BackupError('This database uses an unsupported schema version.')
    if _schema(connection) != _expected_schema():
        raise BackupError('This is not a compatible FORAP workspace. Export a backup from the current app.')
    if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
        raise BackupError('The database contains broken record relationships.')
    rows = {
        name: connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        for name in _expected_schema()
    }
    active = connection.execute('SELECT COUNT(*) FROM responses WHERE is_active=1').fetchone()[0]
    return rows, active


def _save_snapshot(path: Path, target: Path) -> None:
    # The backup API includes committed WAL pages, unlike copying the main file.
    target.touch(mode=0o600, exist_ok=False)
    with closing(_readonly(path)) as source, closing(sqlite3.connect(target)) as destination:
        source.backup(destination)


def export_database(db: Database) -> bytes:
    """Return a self-contained SQLite backup, including private and inactive data."""
    try:
        with tempfile.TemporaryDirectory(prefix='forap-export-') as folder:
            target = Path(folder) / 'workspace.sqlite3'
            _save_snapshot(db.path, target)
            return target.read_bytes()
    except sqlite3.Error as error:
        raise BackupError('The database could not be exported. Try again after other database activity finishes.') from error


def _write_upload(data: bytes, target: Path) -> None:
    if not data.startswith(b'SQLite format 3\x00'):
        raise BackupError('Choose a SQLite database backup exported by FORAP.')
    if len(data) > MAX_BACKUP_BYTES:
        raise BackupError('The database exceeds the 50 MB import limit.')
    target.touch(mode=0o600, exist_ok=False)
    target.write_bytes(data)


def inspect_backup(data: bytes) -> BackupSummary:
    """Validate an uploaded file without changing either workspace."""
    try:
        with tempfile.TemporaryDirectory(prefix='forap-inspect-') as folder:
            candidate = Path(folder) / 'candidate.sqlite3'
            _write_upload(data, candidate)
            with closing(_readonly(candidate)) as connection:
                rows, active = _validate(connection)
        return BackupSummary(hashlib.sha256(data).hexdigest(), rows, active)
    except sqlite3.Error as error:
        raise BackupError('The file is damaged or is not a readable FORAP database backup.') from error


def restore_database(db: Database, data: bytes, *, expected_sha256: str) -> Path:
    """Replace all workspace records in one transaction and retain a recovery copy.

    A write reservation prevents other connections from modifying the target
    between the recovery snapshot and replacement. A failed copy rolls back.
    """
    summary = inspect_backup(data)
    if summary.sha256 != expected_sha256:
        raise BackupError('The selected backup changed. Validate it again before importing.')
    backup_dir = db.path.parent / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    recovery = backup_dir / f'before_restore_{stamp}_{uuid4().hex[:8]}.sqlite3'
    with _TRANSFER_LOCK, tempfile.TemporaryDirectory(prefix='forap-restore-') as folder:
        candidate = Path(folder) / 'candidate.sqlite3'
        _write_upload(data, candidate)
        try:
            with db.connect() as target:
                target.execute('PRAGMA trusted_schema = OFF')
                # Replace the entire relationship graph, then validate it before commit.
                target.execute('PRAGMA foreign_keys = OFF')
                target.execute('BEGIN IMMEDIATE')
                if _schema(target) != _expected_schema():
                    raise BackupError('The current workspace has an unsupported schema. No data were replaced.')
                # A separate read connection sees the committed state while this
                # connection reserves the only writer slot for the full restore.
                _save_snapshot(db.path, recovery)
                with closing(_readonly(recovery)) as saved:
                    if saved.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                        raise BackupError('The recovery backup failed verification. No data were replaced.')
                target.execute('ATTACH DATABASE ? AS incoming', (str(candidate),))
                tables = list(_expected_schema())
                for name in tables:
                    target.execute(f'DELETE FROM main."{name}"')
                for name in tables:
                    target.execute(f'INSERT INTO main."{name}" SELECT * FROM incoming."{name}"')
                target.execute('DELETE FROM main.sqlite_sequence')
                target.execute('INSERT INTO main.sqlite_sequence SELECT * FROM incoming.sqlite_sequence')
                if target.execute('PRAGMA main.foreign_key_check').fetchone() is not None:
                    raise BackupError('The restored records failed relationship checks. No data were replaced.')
            key = str(db.path.resolve())
            _REVISIONS[key] = _REVISIONS.get(key, 0) + 1
        except sqlite3.Error as error:
            raise BackupError('The database could not be restored. The current workspace was not replaced.') from error
    return recovery
