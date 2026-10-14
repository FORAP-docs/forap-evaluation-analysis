"""Compatibility definitions for workspaces created before change logs were removed."""
from __future__ import annotations

import sqlite3

LEGACY_HISTORY_SQL = {
    "code_revisions": """
        CREATE TABLE code_revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code_id INTEGER NOT NULL,
            codebook_version_id INTEGER,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            inclusion_criteria TEXT NOT NULL DEFAULT '',
            exclusion_criteria TEXT NOT NULL DEFAULT '',
            domain TEXT NOT NULL DEFAULT '',
            code_type TEXT NOT NULL DEFAULT 'Topic',
            parent_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(code_id) REFERENCES codes(id),
            FOREIGN KEY(codebook_version_id) REFERENCES codebook_versions(id)
        );
    """,
    "memos": """
        CREATE TABLE memos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            scope TEXT NOT NULL DEFAULT 'study',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """,
    "audit_log": """
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            occurred_at TEXT NOT NULL,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT,
            details_json TEXT NOT NULL DEFAULT '{}'
        );
    """,
}


def discard_legacy_history(connection: sqlite3.Connection) -> None:
    """Remove change logs while preserving questionnaire upload snapshots."""
    for table in LEGACY_HISTORY_SQL:
        connection.execute(f'DROP TABLE IF EXISTS "{table}"')
    # Retain the current codebook and any metadata referenced by saved codes.
    connection.execute("""DELETE FROM codebook_versions
        WHERE id != (SELECT MAX(id) FROM codebook_versions)
        AND id NOT IN (SELECT codebook_version_id FROM codes WHERE codebook_version_id IS NOT NULL)""")
