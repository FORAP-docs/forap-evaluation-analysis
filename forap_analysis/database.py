from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterator

import pandas as pd

from .importer import ImportPreview
from .schema import FIELDS


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "forap_analysis.sqlite3"


class Database:
    def __init__(self, path: str | Path = DEFAULT_DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS imports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_hash TEXT NOT NULL UNIQUE,
                    filename TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    row_count INTEGER NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 0,
                    warnings_json TEXT NOT NULL DEFAULT '[]'
                );
                CREATE TABLE IF NOT EXISTS responses (
                    response_id TEXT PRIMARY KEY,
                    row_hash TEXT NOT NULL,
                    timestamp TEXT,
                    data_json TEXT NOT NULL,
                    pii_json TEXT NOT NULL DEFAULT '{}',
                    first_seen_import_id INTEGER NOT NULL,
                    last_seen_import_id INTEGER NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY(first_seen_import_id) REFERENCES imports(id),
                    FOREIGN KEY(last_seen_import_id) REFERENCES imports(id)
                );
                CREATE TABLE IF NOT EXISTS response_snapshots (
                    import_id INTEGER NOT NULL,
                    response_id TEXT NOT NULL,
                    row_hash TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    pii_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY(import_id, response_id),
                    FOREIGN KEY(import_id) REFERENCES imports(id)
                );
                CREATE TABLE IF NOT EXISTS codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL DEFAULT '',
                    inclusion_criteria TEXT NOT NULL DEFAULT '',
                    exclusion_criteria TEXT NOT NULL DEFAULT '',
                    color TEXT NOT NULL DEFAULT '#0f62fe',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS codebook_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'draft',
                    description TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    frozen_at TEXT
                );
                CREATE TABLE IF NOT EXISTS code_revisions (
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
                CREATE TABLE IF NOT EXISTS themes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS theme_codes (
                    theme_id INTEGER NOT NULL,
                    code_id INTEGER NOT NULL,
                    PRIMARY KEY(theme_id, code_id),
                    FOREIGN KEY(theme_id) REFERENCES themes(id) ON DELETE CASCADE,
                    FOREIGN KEY(code_id) REFERENCES codes(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS codings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    response_id TEXT NOT NULL,
                    question_key TEXT NOT NULL,
                    code_id INTEGER NOT NULL,
                    excerpt TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(response_id, question_key, code_id),
                    FOREIGN KEY(code_id) REFERENCES codes(id)
                );
                CREATE TABLE IF NOT EXISTS meaning_units (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    response_id TEXT NOT NULL,
                    question_key TEXT NOT NULL,
                    excerpt TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    is_pilot INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(response_id, question_key, excerpt)
                );
                CREATE TABLE IF NOT EXISTS meaning_unit_codes (
                    meaning_unit_id INTEGER NOT NULL,
                    code_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(meaning_unit_id, code_id),
                    FOREIGN KEY(meaning_unit_id) REFERENCES meaning_units(id) ON DELETE CASCADE,
                    FOREIGN KEY(code_id) REFERENCES codes(id)
                );
                CREATE TABLE IF NOT EXISTS meaning_unit_code_highlight_reviews (
                    meaning_unit_id INTEGER NOT NULL,
                    code_id INTEGER NOT NULL,
                    excerpt_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('reviewed', 'needs_review')),
                    review_note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(meaning_unit_id, code_id),
                    FOREIGN KEY(meaning_unit_id, code_id)
                        REFERENCES meaning_unit_codes(meaning_unit_id, code_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS meaning_unit_code_highlights (
                    meaning_unit_id INTEGER NOT NULL,
                    code_id INTEGER NOT NULL,
                    start_offset INTEGER NOT NULL CHECK(start_offset >= 0),
                    end_offset INTEGER NOT NULL CHECK(end_offset > start_offset),
                    PRIMARY KEY(meaning_unit_id, code_id, start_offset, end_offset),
                    FOREIGN KEY(meaning_unit_id, code_id)
                        REFERENCES meaning_unit_code_highlight_reviews(meaning_unit_id, code_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS theme_evidence (
                    theme_id INTEGER NOT NULL,
                    meaning_unit_id INTEGER NOT NULL,
                    evidence_role TEXT NOT NULL DEFAULT 'supporting',
                    note TEXT NOT NULL DEFAULT '',
                    is_representative INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(theme_id, meaning_unit_id),
                    FOREIGN KEY(theme_id) REFERENCES themes(id) ON DELETE CASCADE,
                    FOREIGN KEY(meaning_unit_id) REFERENCES meaning_units(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS memos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    scope TEXT NOT NULL DEFAULT 'study',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS background_category_mappings (
                    field_key TEXT NOT NULL,
                    source_value TEXT NOT NULL COLLATE NOCASE,
                    canonical_value TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(field_key, source_value)
                );
                CREATE TABLE IF NOT EXISTS background_groupings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    field_key TEXT NOT NULL,
                    name TEXT NOT NULL COLLATE NOCASE,
                    groups_json TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'user',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(field_key, name)
                );
                CREATE TABLE IF NOT EXISTS background_grouping_selections (
                    field_key TEXT PRIMARY KEY,
                    grouping_id INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(grouping_id) REFERENCES background_groupings(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    occurred_at TEXT NOT NULL,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT,
                    details_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_responses_active ON responses(is_active);
                CREATE INDEX IF NOT EXISTS idx_codings_question ON codings(question_key);
                CREATE INDEX IF NOT EXISTS idx_meaning_units_question_response
                    ON meaning_units(question_key, response_id);
                CREATE INDEX IF NOT EXISTS idx_meaning_unit_codes_code
                    ON meaning_unit_codes(code_id);
                CREATE INDEX IF NOT EXISTS idx_theme_evidence_role
                    ON theme_evidence(theme_id, evidence_role);
                """
            )
            self._ensure_column(connection, "codes", "parent_id", "INTEGER")
            self._ensure_column(connection, "codes", "domain", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "codes", "code_type", "TEXT NOT NULL DEFAULT 'Topic'")
            self._ensure_column(connection, "codes", "codebook_version_id", "INTEGER")
            self._ensure_column(connection, "themes", "status", "TEXT NOT NULL DEFAULT 'candidate'")
            self._ensure_column(connection, "themes", "linked_constructs_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(connection, "themes", "implication", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "themes", "contrasting_evidence", "TEXT NOT NULL DEFAULT ''")
            connection.execute("PRAGMA optimize")

    @staticmethod
    def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {
            str(row["name"])
            for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _audit(self, connection: sqlite3.Connection, action: str, entity_type: str, entity_id: Any, details: dict[str, Any] | None = None) -> None:
        connection.execute(
            "INSERT INTO audit_log(occurred_at, action, entity_type, entity_id, details_json) VALUES (?, ?, ?, ?, ?)",
            (self._now(), action, entity_type, str(entity_id) if entity_id is not None else None, json.dumps(details or {})),
        )

    def import_exists(self, file_hash: str) -> bool:
        with self.connect() as connection:
            return connection.execute("SELECT 1 FROM imports WHERE file_hash = ?", (file_hash,)).fetchone() is not None

    def active_count(self) -> int:
        with self.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS n FROM responses WHERE is_active = 1").fetchone()
            return int(row["n"])

    def activate_import(self, preview: ImportPreview) -> dict[str, int]:
        if not preview.valid or preview.frame is None:
            raise ValueError("Only a valid import preview can be activated.")
        with self.connect() as connection:
            existing = connection.execute("SELECT id FROM imports WHERE file_hash = ?", (preview.file_hash,)).fetchone()
            if existing:
                raise ValueError("This exact workbook has already been imported.")
            now = self._now()
            cursor = connection.execute(
                "INSERT INTO imports(file_hash, filename, imported_at, row_count, warnings_json) VALUES (?, ?, ?, ?, ?)",
                (preview.file_hash, preview.filename, now, len(preview.frame), json.dumps(preview.warnings)),
            )
            import_id = int(cursor.lastrowid)
            connection.execute("UPDATE imports SET is_active = 0")
            connection.execute("UPDATE imports SET is_active = 1 WHERE id = ?", (import_id,))
            connection.execute("UPDATE responses SET is_active = 0")
            inserted = updated = unchanged = 0
            for record in preview.frame.to_dict(orient="records"):
                record = {
                    key: (
                        None
                        if value is None
                        or (not isinstance(value, (list, dict)) and bool(pd.isna(value)))
                        else value
                    )
                    for key, value in record.items()
                }
                response_id = str(record.pop("response_id"))
                row_hash = str(record.pop("row_hash"))
                email = record.pop("followup_email", None)
                data_json = json.dumps(record, ensure_ascii=False, allow_nan=False)
                pii_json = json.dumps({"followup_email": email} if email else {})
                current = connection.execute(
                    "SELECT row_hash FROM responses WHERE response_id = ?", (response_id,)
                ).fetchone()
                if current is None:
                    inserted += 1
                    connection.execute(
                        """INSERT INTO responses(response_id, row_hash, timestamp, data_json, pii_json,
                           first_seen_import_id, last_seen_import_id, is_active)
                           VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
                        (response_id, row_hash, record.get("timestamp"), data_json, pii_json, import_id, import_id),
                    )
                else:
                    changed = current["row_hash"] != row_hash
                    updated += int(changed)
                    unchanged += int(not changed)
                    connection.execute(
                        """UPDATE responses SET row_hash = ?, timestamp = ?, data_json = ?, pii_json = ?,
                           last_seen_import_id = ?, is_active = 1 WHERE response_id = ?""",
                        (row_hash, record.get("timestamp"), data_json, pii_json, import_id, response_id),
                    )
                connection.execute(
                    "INSERT INTO response_snapshots(import_id, response_id, row_hash, data_json, pii_json) VALUES (?, ?, ?, ?, ?)",
                    (import_id, response_id, row_hash, data_json, pii_json),
                )
            self._audit(connection, "activate", "import", import_id, {"filename": preview.filename, "rows": len(preview.frame)})
            return {"import_id": import_id, "inserted": inserted, "updated": updated, "unchanged": unchanged}

    def active_data(self) -> pd.DataFrame:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT response_id, data_json FROM responses WHERE is_active = 1 ORDER BY timestamp, response_id"
            ).fetchall()
        records = [{"response_id": row["response_id"], **json.loads(row["data_json"])} for row in rows]
        columns = ["response_id", *[field.key for field in FIELDS if not field.pii]]
        return pd.DataFrame(records, columns=columns)

    def background_mappings(self, field_key: str | None = None) -> pd.DataFrame:
        query = "SELECT * FROM background_category_mappings"
        params: tuple[Any, ...] = ()
        if field_key:
            query += " WHERE field_key=?"
            params = (field_key,)
        query += " ORDER BY field_key, source_value"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return pd.DataFrame([dict(row) for row in rows])

    def save_background_mapping(self, field_key: str, source_value: str, canonical_value: str) -> None:
        field_key = field_key.strip()
        source_value = source_value.strip()
        canonical_value = canonical_value.strip()
        if not field_key or not source_value or not canonical_value:
            raise ValueError("A background question, source category, and analysis category are required.")
        if source_value.casefold() == canonical_value.casefold():
            self.delete_background_mapping(field_key, source_value)
            return
        now = self._now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO background_category_mappings(
                       field_key, source_value, canonical_value, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(field_key, source_value) DO UPDATE SET
                       canonical_value=excluded.canonical_value,
                       updated_at=excluded.updated_at""",
                (field_key, source_value, canonical_value, now, now),
            )
            self._audit(
                connection,
                "set_mapping",
                "background_category",
                f"{field_key}:{source_value}",
                {"field_key": field_key, "source_value": source_value, "canonical_value": canonical_value},
            )

    def delete_background_mapping(self, field_key: str, source_value: str) -> None:
        field_key = field_key.strip()
        source_value = source_value.strip()
        with self.connect() as connection:
            deleted = connection.execute(
                "DELETE FROM background_category_mappings WHERE field_key=? AND source_value=?",
                (field_key, source_value),
            ).rowcount
            if deleted:
                self._audit(
                    connection,
                    "remove_mapping",
                    "background_category",
                    f"{field_key}:{source_value}",
                    {"field_key": field_key, "source_value": source_value},
                )

    def background_groupings(self, field_key: str | None = None) -> pd.DataFrame:
        query = "SELECT * FROM background_groupings"
        params: tuple[Any, ...] = ()
        if field_key:
            query += " WHERE field_key=?"
            params = (field_key,)
        query += " ORDER BY field_key, name"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        records = []
        for row in rows:
            record = dict(row)
            try:
                record["groups"] = json.loads(str(record["groups_json"]))
            except (TypeError, json.JSONDecodeError):
                record["groups"] = []
            records.append(record)
        return pd.DataFrame(records)

    @staticmethod
    def _validated_background_groups(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not 2 <= len(groups) <= 5:
            raise ValueError("A saved grouping must contain between two and five groups.")
        normalized: list[dict[str, Any]] = []
        names: set[str] = set()
        assigned_categories: set[str] = set()
        for group in groups:
            name = str(group.get("name", "")).strip()
            if not name:
                raise ValueError("Every saved group needs a name.")
            name_key = name.casefold()
            if name_key in names:
                raise ValueError("Saved group names must be different.")
            names.add(name_key)
            categories: list[str] = []
            for value in group.get("categories", []):
                category = str(value).strip()
                if not category:
                    continue
                category_key = category.casefold()
                if category_key in assigned_categories:
                    raise ValueError("A background category can belong to only one saved group.")
                assigned_categories.add(category_key)
                categories.append(category)
            if not categories:
                raise ValueError(f"Assign at least one background category to {name}.")
            normalized.append({"name": name, "categories": categories})
        return normalized

    def save_background_grouping(
        self,
        field_key: str,
        name: str,
        groups: list[dict[str, Any]],
        grouping_id: int | None = None,
        source: str = "user",
    ) -> int:
        field_key = field_key.strip()
        name = name.strip()
        source = source.strip() or "user"
        if not field_key or not name:
            raise ValueError("A background question and grouping name are required.")
        normalized = self._validated_background_groups(groups)
        groups_json = json.dumps(normalized, ensure_ascii=False)
        now = self._now()
        with self.connect() as connection:
            try:
                if grouping_id is None:
                    cursor = connection.execute(
                        """INSERT INTO background_groupings(
                               field_key, name, groups_json, source, created_at, updated_at
                           ) VALUES (?, ?, ?, ?, ?, ?)""",
                        (field_key, name, groups_json, source, now, now),
                    )
                    saved_id = int(cursor.lastrowid)
                    action = "create"
                else:
                    existing = connection.execute(
                        "SELECT id FROM background_groupings WHERE id=?", (int(grouping_id),)
                    ).fetchone()
                    if existing is None:
                        raise ValueError("The selected saved grouping no longer exists.")
                    connection.execute(
                        """UPDATE background_groupings
                           SET field_key=?, name=?, groups_json=?, source=?, updated_at=?
                           WHERE id=?""",
                        (field_key, name, groups_json, source, now, int(grouping_id)),
                    )
                    saved_id = int(grouping_id)
                    action = "update"
            except sqlite3.IntegrityError as error:
                raise ValueError(
                    "A saved grouping with this name already exists for this background question."
                ) from error
            self._audit(
                connection,
                action,
                "background_grouping",
                saved_id,
                {"field_key": field_key, "name": name, "groups": normalized},
            )
            return saved_id

    def delete_background_grouping(self, grouping_id: int) -> None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT field_key, name FROM background_groupings WHERE id=?",
                (int(grouping_id),),
            ).fetchone()
            if row is None:
                return
            connection.execute(
                "DELETE FROM background_groupings WHERE id=?", (int(grouping_id),)
            )
            self._audit(
                connection,
                "delete",
                "background_grouping",
                int(grouping_id),
                {"field_key": row["field_key"], "name": row["name"]},
            )

    def selected_background_grouping(self, field_key: str) -> int | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT s.grouping_id
                   FROM background_grouping_selections s
                   JOIN background_groupings g ON g.id=s.grouping_id
                   WHERE s.field_key=? AND g.field_key=?""",
                (field_key.strip(), field_key.strip()),
            ).fetchone()
        return int(row["grouping_id"]) if row is not None else None

    def select_background_grouping(
        self,
        field_key: str,
        grouping_id: int | None,
    ) -> None:
        field_key = field_key.strip()
        with self.connect() as connection:
            if grouping_id is None:
                connection.execute(
                    "DELETE FROM background_grouping_selections WHERE field_key=?",
                    (field_key,),
                )
                self._audit(
                    connection,
                    "clear_selection",
                    "background_grouping",
                    None,
                    {"field_key": field_key},
                )
                return
            grouping = connection.execute(
                "SELECT id FROM background_groupings WHERE id=? AND field_key=?",
                (int(grouping_id), field_key),
            ).fetchone()
            if grouping is None:
                raise ValueError("The selected grouping does not belong to this background question.")
            connection.execute(
                """INSERT INTO background_grouping_selections(field_key, grouping_id, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(field_key) DO UPDATE SET
                       grouping_id=excluded.grouping_id,
                       updated_at=excluded.updated_at""",
                (field_key, int(grouping_id), self._now()),
            )
            self._audit(
                connection,
                "select",
                "background_grouping",
                int(grouping_id),
                {"field_key": field_key},
            )

    def active_hashes(self) -> dict[str, str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT response_id, row_hash FROM responses WHERE is_active = 1"
            ).fetchall()
        return {str(row["response_id"]): str(row["row_hash"]) for row in rows}

    def respondent_labels(self) -> dict[str, str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT response_id FROM responses ORDER BY first_seen_import_id, rowid"
            ).fetchall()
        return {str(row["response_id"]): f"R{index}" for index, row in enumerate(rows, start=1)}

    def import_history(self) -> pd.DataFrame:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT id, filename, imported_at, row_count, is_active, warnings_json FROM imports ORDER BY id DESC"
            ).fetchall()
        return pd.DataFrame([dict(row) for row in rows])

    def codes(self, active_only: bool = True) -> pd.DataFrame:
        query = """SELECT c.*, p.name AS parent_name, v.label AS version_label
                   FROM codes c
                   LEFT JOIN codes p ON p.id = c.parent_id
                   LEFT JOIN codebook_versions v ON v.id = c.codebook_version_id"""
        query += " WHERE c.is_active = 1" if active_only else ""
        query += " ORDER BY c.domain, CASE c.code_type WHEN 'Domain' THEN 0 ELSE 1 END, c.name"
        with self.connect() as connection:
            rows = connection.execute(query).fetchall()
        records = [dict(row) for row in rows]
        # Keep domain headings first while ordering names such as XC2 before XC10.
        records.sort(
            key=lambda code: (
                code["domain"],
                code["code_type"] != "Domain",
                tuple(
                    int(part) if index % 2 else part
                    for index, part in enumerate(re.split(r"([0-9]+)", code["name"]))
                ),
            )
        )
        return pd.DataFrame(records)

    def codebook_versions(self) -> pd.DataFrame:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM codebook_versions ORDER BY id DESC"
            ).fetchall()
        return pd.DataFrame([dict(row) for row in rows])

    def current_codebook_version(self) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM codebook_versions ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def create_codebook_version(self, label: str, description: str = "", status: str = "draft") -> int:
        now = self._now()
        with self.connect() as connection:
            current = connection.execute(
                "SELECT id FROM codebook_versions WHERE label=?", (label.strip(),)
            ).fetchone()
            if current:
                return int(current["id"])
            cursor = connection.execute(
                "INSERT INTO codebook_versions(label, status, description, created_at) VALUES (?, ?, ?, ?)",
                (label.strip(), status, description, now),
            )
            version_id = int(cursor.lastrowid)
            self._audit(connection, "create", "codebook_version", version_id, {"label": label.strip()})
            return version_id

    def freeze_codebook_version(self, version_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE codebook_versions SET status='frozen', frozen_at=? WHERE id=?",
                (self._now(), version_id),
            )
            self._audit(connection, "freeze", "codebook_version", version_id)

    def save_code(
        self,
        name: str,
        description: str,
        inclusion: str,
        exclusion: str,
        color: str = "#0f62fe",
        *,
        parent_id: int | None = None,
        domain: str = "",
        code_type: str = "Topic",
        codebook_version_id: int | None = None,
    ) -> int:
        now = self._now()
        with self.connect() as connection:
            current = connection.execute("SELECT id FROM codes WHERE name = ?", (name.strip(),)).fetchone()
            if current:
                code_id = int(current["id"])
                connection.execute(
                    """UPDATE codes SET description=?, inclusion_criteria=?, exclusion_criteria=?, color=?,
                       parent_id=?, domain=?, code_type=?, codebook_version_id=?, is_active=1, updated_at=?
                       WHERE id=?""",
                    (description, inclusion, exclusion, color, parent_id, domain, code_type, codebook_version_id, now, code_id),
                )
                action = "update"
            else:
                cursor = connection.execute(
                    """INSERT INTO codes(name, description, inclusion_criteria, exclusion_criteria, color,
                       parent_id, domain, code_type, codebook_version_id, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (name.strip(), description, inclusion, exclusion, color, parent_id, domain, code_type, codebook_version_id, now, now),
                )
                code_id = int(cursor.lastrowid)
                action = "create"
            connection.execute(
                """INSERT INTO code_revisions(code_id, codebook_version_id, name, description,
                   inclusion_criteria, exclusion_criteria, domain, code_type, parent_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (code_id, codebook_version_id, name.strip(), description, inclusion, exclusion, domain, code_type, parent_id, now),
            )
            self._audit(connection, action, "code", code_id, {"name": name.strip()})
            return code_id

    def deactivate_code(self, code_id: int) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE codes SET is_active=0, updated_at=? WHERE id=?", (self._now(), code_id))
            self._audit(connection, "deactivate", "code", code_id)

    def update_code_color(self, code_id: int, color: str) -> None:
        normalized = color.strip().lower()
        if len(normalized) != 7 or not normalized.startswith("#"):
            raise ValueError("Code colors must use the #RRGGBB format.")
        try:
            int(normalized[1:], 16)
        except ValueError as error:
            raise ValueError("Code colors must use the #RRGGBB format.") from error

        with self.connect() as connection:
            current = connection.execute(
                "SELECT name, color FROM codes WHERE id=?", (code_id,)
            ).fetchone()
            if current is None:
                raise ValueError("The selected working code no longer exists.")
            if str(current["color"]).lower() == normalized:
                return
            connection.execute(
                "UPDATE codes SET color=?, updated_at=? WHERE id=?",
                (normalized, self._now(), code_id),
            )
            self._audit(
                connection,
                "update_color",
                "code",
                code_id,
                {"name": current["name"], "from": current["color"], "to": normalized},
            )

    def codings(self, question_key: str | None = None) -> pd.DataFrame:
        query = """WITH all_codings AS (
                       SELECT cg.id, cg.response_id, cg.question_key, cg.code_id, cg.excerpt, cg.note,
                              cg.created_at, cg.updated_at, NULL AS meaning_unit_id, 0 AS is_pilot,
                              'legacy' AS source
                       FROM codings cg
                       UNION ALL
                       SELECT muc.rowid AS id, mu.response_id, mu.question_key, muc.code_id, mu.excerpt, mu.note,
                              mu.created_at, mu.updated_at, mu.id AS meaning_unit_id, mu.is_pilot,
                              'meaning_unit' AS source
                       FROM meaning_units mu
                       JOIN meaning_unit_codes muc ON muc.meaning_unit_id=mu.id
                   )
                   SELECT ac.*, c.name AS code_name, c.color, c.domain, c.code_type
                   FROM all_codings ac
                   JOIN codes c ON c.id = ac.code_id"""
        params: tuple[Any, ...] = ()
        if question_key:
            query += " WHERE ac.question_key = ?"
            params = (question_key,)
        query += " ORDER BY ac.updated_at DESC, ac.id DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return pd.DataFrame([dict(row) for row in rows])

    def meaning_units(self, question_key: str | None = None, response_id: str | None = None) -> pd.DataFrame:
        conditions: list[str] = []
        params: list[Any] = []
        if question_key:
            conditions.append("mu.question_key=?")
            params.append(question_key)
        if response_id:
            conditions.append("mu.response_id=?")
            params.append(response_id)
        query = """SELECT mu.*, GROUP_CONCAT(c.name, ' | ') AS code_names,
                          GROUP_CONCAT(c.id, ',') AS code_ids
                   FROM meaning_units mu
                   LEFT JOIN meaning_unit_codes muc ON muc.meaning_unit_id=mu.id
                   LEFT JOIN codes c ON c.id=muc.code_id"""
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " GROUP BY mu.id ORDER BY mu.question_key, mu.response_id, mu.id"
        with self.connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return pd.DataFrame([dict(row) for row in rows])

    def save_meaning_unit(
        self,
        response_id: str,
        question_key: str,
        excerpt: str,
        code_ids: list[int],
        note: str = "",
        is_pilot: bool = False,
        unit_id: int | None = None,
    ) -> int:
        excerpt = excerpt.strip()
        if not excerpt:
            raise ValueError("A meaning-unit excerpt is required.")
        now = self._now()
        with self.connect() as connection:
            if unit_id is None:
                current = connection.execute(
                    "SELECT id FROM meaning_units WHERE response_id=? AND question_key=? AND excerpt=?",
                    (response_id, question_key, excerpt),
                ).fetchone()
                if current:
                    unit_id = int(current["id"])
                    connection.execute(
                        "UPDATE meaning_units SET note=?, is_pilot=?, updated_at=? WHERE id=?",
                        (note, int(is_pilot), now, unit_id),
                    )
                    action = "update"
                else:
                    cursor = connection.execute(
                        """INSERT INTO meaning_units(response_id, question_key, excerpt, note, is_pilot,
                           created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (response_id, question_key, excerpt, note, int(is_pilot), now, now),
                    )
                    unit_id = int(cursor.lastrowid)
                    action = "create"
            else:
                previous = connection.execute(
                    "SELECT response_id,question_key,excerpt FROM meaning_units WHERE id=?", (unit_id,)
                ).fetchone()
                if previous is None:
                    raise ValueError("The excerpt no longer exists.")
                if tuple(previous) != (response_id, question_key, excerpt):
                    connection.execute(
                        "DELETE FROM meaning_unit_code_highlight_reviews WHERE meaning_unit_id=?", (unit_id,)
                    )
                connection.execute(
                    """UPDATE meaning_units SET response_id=?, question_key=?, excerpt=?, note=?,
                       is_pilot=?, updated_at=? WHERE id=?""",
                    (response_id, question_key, excerpt, note, int(is_pilot), now, unit_id),
                )
                action = "update"
            # Retain highlights when only the interpretation or other codes change.
            existing = {int(row[0]) for row in connection.execute(
                "SELECT code_id FROM meaning_unit_codes WHERE meaning_unit_id=?", (unit_id,)
            )}
            selected = {int(code_id) for code_id in code_ids}
            connection.executemany(
                "DELETE FROM meaning_unit_codes WHERE meaning_unit_id=? AND code_id=?",
                [(unit_id, code_id) for code_id in existing - selected],
            )
            connection.executemany(
                "INSERT INTO meaning_unit_codes(meaning_unit_id, code_id, created_at) VALUES (?, ?, ?)",
                [(unit_id, code_id, now) for code_id in sorted(selected - existing)],
            )
            self._audit(
                connection,
                action,
                "meaning_unit",
                unit_id,
                {"response_id": response_id, "question": question_key, "code_ids": sorted(set(code_ids)), "is_pilot": bool(is_pilot)},
            )
            return unit_id

    def delete_meaning_unit(self, unit_id: int) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM meaning_units WHERE id=?", (unit_id,))
            self._audit(connection, "delete", "meaning_unit", unit_id)

    def highlight_reviews(self, meaning_unit_id: int | None = None) -> pd.DataFrame:
        """Return every assigned pair, including assignments not yet highlighted."""
        columns = ["meaning_unit_id", "code_id", "code_name", "color", "excerpt",
                   "status", "review_note", "excerpt_sha256"]
        query = """SELECT m.meaning_unit_id,m.code_id,c.name AS code_name,c.color,u.excerpt,
                          COALESCE(r.status,'unreviewed') AS status,
                          COALESCE(r.review_note,'') AS review_note,
                          COALESCE(r.excerpt_sha256,'') AS excerpt_sha256
                   FROM meaning_unit_codes m JOIN meaning_units u ON u.id=m.meaning_unit_id
                   JOIN codes c ON c.id=m.code_id
                   LEFT JOIN meaning_unit_code_highlight_reviews r
                   ON r.meaning_unit_id=m.meaning_unit_id AND r.code_id=m.code_id"""
        params = ()
        if meaning_unit_id is not None:
            query += " WHERE m.meaning_unit_id=?"
            params = (int(meaning_unit_id),)
        query += " ORDER BY m.meaning_unit_id,m.code_id"
        with self.connect() as connection:
            records = [dict(row) for row in connection.execute(query, params)]
        for record in records:
            digest = hashlib.sha256(record["excerpt"].encode()).hexdigest()
            if record["excerpt_sha256"] and record["excerpt_sha256"] != digest:
                record.update(status="needs_review", review_note="The excerpt changed. Review its highlighted passages again.")
        return pd.DataFrame(records, columns=columns)

    def code_highlights(self, meaning_unit_id: int | None = None) -> pd.DataFrame:
        """Read exact ranges with current code names/colours; hide stale ranges."""
        columns = ["meaning_unit_id", "code_id", "start_offset", "end_offset", "code_name",
                   "color", "excerpt", "excerpt_sha256", "status", "review_note"]
        query = """SELECT h.*,c.name AS code_name,c.color,u.excerpt,r.excerpt_sha256,
                          r.status,r.review_note
                   FROM meaning_unit_code_highlights h
                   JOIN meaning_unit_code_highlight_reviews r
                     ON r.meaning_unit_id=h.meaning_unit_id AND r.code_id=h.code_id
                   JOIN meaning_units u ON u.id=h.meaning_unit_id
                   JOIN codes c ON c.id=h.code_id"""
        params = ()
        if meaning_unit_id is not None:
            query += " WHERE h.meaning_unit_id=?"
            params = (int(meaning_unit_id),)
        query += " ORDER BY h.meaning_unit_id,h.start_offset,h.end_offset,h.code_id"
        with self.connect() as connection:
            records = [dict(row) for row in connection.execute(query, params)]
        valid = [row for row in records if row["excerpt_sha256"] == hashlib.sha256(row["excerpt"].encode()).hexdigest()
                 and 0 <= row["start_offset"] < row["end_offset"] <= len(row["excerpt"])]
        return pd.DataFrame(valid, columns=columns)

    def _save_code_highlights(
        self, connection: sqlite3.Connection, meaning_unit_id: int, code_id: int,
        spans: list[tuple[int, int]], *, status: str = "reviewed", note: str = "",
        expected_excerpt: str | None = None,
    ) -> None:
        row = connection.execute(
            """SELECT u.excerpt FROM meaning_units u JOIN meaning_unit_codes m
               ON m.meaning_unit_id=u.id WHERE u.id=? AND m.code_id=?""", (meaning_unit_id, code_id)
        ).fetchone()
        if row is None:
            raise ValueError("This code is not assigned to the excerpt.")
        excerpt = row[0]
        if expected_excerpt is not None and excerpt != expected_excerpt:
            raise ValueError("The excerpt changed. Reload it before saving highlights.")
        if status not in {"reviewed", "needs_review"}:
            raise ValueError("Choose reviewed or needs_review.")
        normalized = []
        for span in spans:
            if len(span) != 2 or any(type(value) is not int for value in span):
                raise ValueError("Highlight positions must be whole-number start/end pairs.")
            start, end = span
            if not 0 <= start < end <= len(excerpt) or not excerpt[start:end].strip():
                raise ValueError("Each highlight must select actual text inside this excerpt.")
            normalized.append((start, end))
        normalized = sorted(set(normalized))
        if any(left[1] > right[0] for left, right in zip(normalized, normalized[1:])):
            raise ValueError("Highlights for the same code must not overlap; combine those passages.")
        if status == "reviewed" and not normalized:
            raise ValueError("Select at least one passage, or mark this assignment as needing review.")
        stamp = self._now()
        digest = hashlib.sha256(excerpt.encode()).hexdigest()
        connection.execute(
            """INSERT INTO meaning_unit_code_highlight_reviews
               (meaning_unit_id,code_id,excerpt_sha256,status,review_note,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?) ON CONFLICT(meaning_unit_id,code_id) DO UPDATE SET
               excerpt_sha256=excluded.excerpt_sha256,status=excluded.status,
               review_note=excluded.review_note,updated_at=excluded.updated_at""",
            (meaning_unit_id, code_id, digest, status, note.strip(), stamp, stamp),
        )
        connection.execute("DELETE FROM meaning_unit_code_highlights WHERE meaning_unit_id=? AND code_id=?", (meaning_unit_id, code_id))
        connection.executemany(
            "INSERT INTO meaning_unit_code_highlights(meaning_unit_id,code_id,start_offset,end_offset) VALUES (?,?,?,?)",
            [(meaning_unit_id, code_id, start, end) for start, end in normalized],
        )
        self._audit(connection, "set_highlights", "meaning_unit", meaning_unit_id,
                    {"code_id": code_id, "spans": normalized, "status": status, "note": note.strip(), "excerpt_sha256": digest})

    def save_code_highlights(
        self, meaning_unit_id: int, code_id: int, spans: list[tuple[int, int]], *,
        status: str = "reviewed", note: str = "", expected_excerpt: str | None = None,
    ) -> None:
        with self.connect() as connection:
            self._save_code_highlights(connection, meaning_unit_id, code_id, spans, status=status,
                                       note=note, expected_excerpt=expected_excerpt)

    def set_response_codes(self, response_id: str, question_key: str, code_ids: list[int], excerpt: str = "", note: str = "") -> None:
        now = self._now()
        with self.connect() as connection:
            existing = {
                int(row["code_id"])
                for row in connection.execute(
                    "SELECT code_id FROM codings WHERE response_id=? AND question_key=?", (response_id, question_key)
                ).fetchall()
            }
            selected = set(code_ids)
            for code_id in existing - selected:
                connection.execute(
                    "DELETE FROM codings WHERE response_id=? AND question_key=? AND code_id=?",
                    (response_id, question_key, code_id),
                )
            for code_id in selected:
                connection.execute(
                    """INSERT INTO codings(response_id, question_key, code_id, excerpt, note, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(response_id, question_key, code_id)
                       DO UPDATE SET excerpt=excluded.excerpt, note=excluded.note, updated_at=excluded.updated_at""",
                    (response_id, question_key, code_id, excerpt, note, now, now),
                )
            self._audit(connection, "set_codes", "response", response_id, {"question": question_key, "code_ids": sorted(selected)})

    def themes(self) -> pd.DataFrame:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT t.*, GROUP_CONCAT(c.name, ', ') AS codes, GROUP_CONCAT(c.id, ',') AS code_ids,
                          (SELECT COUNT(*) FROM theme_evidence te WHERE te.theme_id=t.id) AS evidence_units,
                          (SELECT COUNT(DISTINCT mu.response_id)
                           FROM theme_evidence te
                           JOIN meaning_units mu ON mu.id=te.meaning_unit_id
                           WHERE te.theme_id=t.id) AS respondents
                   FROM themes t
                   LEFT JOIN theme_codes tc ON tc.theme_id=t.id
                   LEFT JOIN codes c ON c.id=tc.code_id
                   GROUP BY t.id ORDER BY t.name"""
            ).fetchall()
        return pd.DataFrame([dict(row) for row in rows])

    def theme_codings(self) -> pd.DataFrame:
        with self.connect() as connection:
            rows = connection.execute(
                """WITH all_codings AS (
                       SELECT response_id, question_key, code_id, excerpt, note FROM codings
                       UNION ALL
                       SELECT mu.response_id, mu.question_key, muc.code_id, mu.excerpt, mu.note
                       FROM meaning_units mu
                       JOIN meaning_unit_codes muc ON muc.meaning_unit_id=mu.id
                   )
                   SELECT DISTINCT t.id AS theme_id, t.name AS theme_name, cg.response_id,
                          cg.question_key, c.id AS code_id, c.name AS code_name, cg.excerpt, cg.note
                   FROM themes t
                   JOIN theme_codes tc ON tc.theme_id=t.id
                   JOIN codes c ON c.id=tc.code_id
                   JOIN all_codings cg ON cg.code_id=c.id
                   ORDER BY t.name, cg.question_key, cg.response_id"""
            ).fetchall()
        return pd.DataFrame([dict(row) for row in rows])

    def save_theme(
        self,
        name: str,
        description: str,
        code_ids: list[int],
        *,
        theme_id: int | None = None,
        status: str = "candidate",
        linked_constructs: list[str] | None = None,
        implication: str = "",
        contrasting_evidence: str = "",
    ) -> int:
        now = self._now()
        constructs_json = json.dumps(linked_constructs or [], ensure_ascii=False)
        with self.connect() as connection:
            if theme_id is None:
                current = connection.execute("SELECT id FROM themes WHERE name=?", (name.strip(),)).fetchone()
            else:
                current = connection.execute("SELECT id FROM themes WHERE id=?", (theme_id,)).fetchone()
            if current:
                saved_theme_id = int(current["id"])
                connection.execute(
                    """UPDATE themes SET name=?, description=?, status=?, linked_constructs_json=?, implication=?,
                       contrasting_evidence=?, updated_at=? WHERE id=?""",
                    (name.strip(), description, status, constructs_json, implication, contrasting_evidence, now, saved_theme_id),
                )
                action = "update"
            else:
                cursor = connection.execute(
                    """INSERT INTO themes(name, description, status, linked_constructs_json, implication,
                       contrasting_evidence, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (name.strip(), description, status, constructs_json, implication, contrasting_evidence, now, now),
                )
                saved_theme_id = int(cursor.lastrowid)
                action = "create"
            connection.execute("DELETE FROM theme_codes WHERE theme_id=?", (saved_theme_id,))
            connection.executemany(
                "INSERT INTO theme_codes(theme_id, code_id) VALUES (?, ?)",
                [(saved_theme_id, code_id) for code_id in code_ids],
            )
            self._audit(
                connection,
                action,
                "theme",
                saved_theme_id,
                {
                    "name": name.strip(),
                    "code_ids": code_ids,
                    "status": status,
                    "linked_constructs": linked_constructs or [],
                },
            )
            return saved_theme_id

    def delete_theme(self, theme_id: int) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM themes WHERE id=?", (theme_id,))
            self._audit(connection, "delete", "theme", theme_id)

    def theme_evidence(self, theme_id: int | None = None) -> pd.DataFrame:
        query = """SELECT te.theme_id, t.name AS theme_name, te.meaning_unit_id, te.evidence_role,
                          te.note AS evidence_note, te.is_representative, mu.response_id,
                          mu.question_key, mu.excerpt, mu.note AS unit_note,
                          GROUP_CONCAT(c.name, ' | ') AS code_names
                   FROM theme_evidence te
                   JOIN themes t ON t.id=te.theme_id
                   JOIN meaning_units mu ON mu.id=te.meaning_unit_id
                   LEFT JOIN meaning_unit_codes muc ON muc.meaning_unit_id=mu.id
                   LEFT JOIN codes c ON c.id=muc.code_id"""
        params: tuple[Any, ...] = ()
        if theme_id is not None:
            query += " WHERE te.theme_id=?"
            params = (theme_id,)
        query += " GROUP BY te.theme_id, te.meaning_unit_id ORDER BY t.name, te.evidence_role, mu.question_key, mu.response_id"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return pd.DataFrame([dict(row) for row in rows])

    def save_theme_evidence(
        self,
        theme_id: int,
        meaning_unit_id: int,
        evidence_role: str = "supporting",
        note: str = "",
        is_representative: bool = False,
    ) -> None:
        now = self._now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO theme_evidence(theme_id, meaning_unit_id, evidence_role, note,
                   is_representative, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(theme_id, meaning_unit_id) DO UPDATE SET
                   evidence_role=excluded.evidence_role, note=excluded.note,
                   is_representative=excluded.is_representative, updated_at=excluded.updated_at""",
                (theme_id, meaning_unit_id, evidence_role, note, int(is_representative), now, now),
            )
            self._audit(
                connection,
                "set_evidence",
                "theme",
                theme_id,
                {
                    "meaning_unit_id": meaning_unit_id,
                    "evidence_role": evidence_role,
                    "is_representative": bool(is_representative),
                },
            )

    def delete_theme_evidence(self, theme_id: int, meaning_unit_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM theme_evidence WHERE theme_id=? AND meaning_unit_id=?",
                (theme_id, meaning_unit_id),
            )
            self._audit(
                connection,
                "remove_evidence",
                "theme",
                theme_id,
                {"meaning_unit_id": meaning_unit_id},
            )

    def reset_qualitative_analysis(self) -> dict[str, int]:
        tables = {
            "codes": "codes",
            "codebook_versions": "codebook_versions",
            "meaning_units": "meaning_units",
            "code_assignments": "meaning_unit_codes",
            "legacy_codings": "codings",
            "themes": "themes",
            "theme_evidence": "theme_evidence",
            "qualitative_memos": "memos",
        }
        with self.connect() as connection:
            counts = {
                label: int(connection.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
                for label, table in tables.items()
            }
            connection.execute("DELETE FROM theme_evidence")
            connection.execute("DELETE FROM theme_codes")
            connection.execute("DELETE FROM themes")
            connection.execute("DELETE FROM meaning_unit_codes")
            connection.execute("DELETE FROM meaning_units")
            connection.execute("DELETE FROM codings")
            connection.execute("DELETE FROM code_revisions")
            connection.execute("DELETE FROM codes")
            connection.execute("DELETE FROM codebook_versions")
            connection.execute(
                "DELETE FROM memos WHERE scope IN ('qualitative', 'rating-linked', 'theme development', 'integration', 'decision')"
            )
            connection.execute(
                """DELETE FROM audit_log
                   WHERE entity_type IN ('code', 'codebook_version', 'meaning_unit', 'theme', 'memo')
                      OR action='set_codes'"""
            )
            connection.execute(
                """DELETE FROM sqlite_sequence
                   WHERE name IN ('codes', 'codebook_versions', 'code_revisions', 'meaning_units',
                                  'codings', 'themes', 'memos')"""
            )
            self._audit(connection, "reset", "qualitative_workspace", None, counts)
            connection.execute("PRAGMA optimize")
        return counts

    def memos(self) -> pd.DataFrame:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM memos ORDER BY updated_at DESC").fetchall()
        return pd.DataFrame([dict(row) for row in rows])

    def save_memo(self, title: str, content: str, scope: str = "study") -> int:
        now = self._now()
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO memos(title, content, scope, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (title.strip(), content, scope, now, now),
            )
            memo_id = int(cursor.lastrowid)
            self._audit(connection, "create", "memo", memo_id, {"title": title.strip()})
            return memo_id

    def audit_log(self) -> pd.DataFrame:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM audit_log ORDER BY id DESC").fetchall()
        return pd.DataFrame([dict(row) for row in rows])
