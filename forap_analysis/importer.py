from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
from typing import Any

import numpy as np
import pandas as pd

from .schema import FIELDS, FIELD_BY_KEY, SCALE_MAPS, normalize_text


IMPORT_PIPELINE_VERSION = "3"


@dataclass
class ImportPreview:
    filename: str
    file_hash: str
    source_file_hash: str = ""
    frame: pd.DataFrame | None = None
    mapping: dict[str, str] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    unexpected_columns: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return self.frame is not None and not self.errors


def _resolve_columns(columns: list[object]) -> tuple[dict[str, str], list[str], list[str]]:
    normalized = {str(column): normalize_text(column) for column in columns}
    mapping: dict[str, str] = {}
    missing: list[str] = []
    used: set[str] = set()
    for expected in FIELDS:
        hint = normalize_text(expected.match)
        candidates = [
            original
            for original, cleaned in normalized.items()
            if (cleaned == expected.key or hint in cleaned) and original not in used
        ]
        if len(candidates) == 1:
            mapping[expected.key] = candidates[0]
            used.add(candidates[0])
        elif not expected.pii or candidates:
            missing.append(expected.key)
    unexpected = [str(column) for column in columns if str(column) not in used]
    return mapping, missing, unexpected


def _clean_scalar(value: Any) -> Any:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    text = str(value).strip()
    return text or None


def _score(value: Any, scale: str) -> float | None:
    cleaned = _clean_scalar(value)
    if cleaned is None:
        return None
    if isinstance(cleaned, (int, float)):
        number = float(cleaned)
    else:
        normalized = normalize_text(cleaned)
        if normalized in SCALE_MAPS[scale]:
            number = float(SCALE_MAPS[scale][normalized])
        else:
            try:
                number = float(normalized)
            except ValueError:
                return None
    upper = 5 if scale != "experience" else 3
    lower = 1 if scale != "experience" else 0
    return number if lower <= number <= upper else None


def _normalize_frame(raw: pd.DataFrame, mapping: dict[str, str]) -> tuple[pd.DataFrame, list[str]]:
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    invalid_counts: dict[str, int] = {}
    for _, source in raw.iterrows():
        row: dict[str, Any] = {}
        for key, column in mapping.items():
            spec = FIELD_BY_KEY[key]
            raw_value = source[column]
            if spec.scale:
                value = _score(raw_value, spec.scale)
                if _clean_scalar(raw_value) is not None and value is None:
                    invalid_counts[key] = invalid_counts.get(key, 0) + 1
                row[key] = value
            else:
                row[key] = _clean_scalar(raw_value)
        rows.append(row)
    normalized = pd.DataFrame(rows)
    if "timestamp" in normalized:
        parsed = pd.to_datetime(normalized["timestamp"], errors="coerce")
        bad = int(parsed.isna().sum())
        if bad:
            warnings.append(f"{bad} response(s) have an unreadable or missing timestamp; a content-based ID will be used.")
        normalized["timestamp"] = parsed.map(lambda value: value.isoformat() if pd.notna(value) else None)
    for key, count in invalid_counts.items():
        warnings.append(f"{count} value(s) for {FIELD_BY_KEY[key].label} were outside the expected scale and set to missing.")
    if normalized.empty:
        warnings.append("The workbook contains headers but no responses.")
    normalized = _add_response_ids(normalized)
    return normalized, warnings


def _add_response_ids(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    content_columns = [column for column in result.columns if column != "followup_email"]
    hashes: list[str] = []
    bases: list[str] = []
    for _, row in result.iterrows():
        payload = json.dumps(
            {column: _clean_scalar(row.get(column)) for column in content_columns},
            sort_keys=True,
            ensure_ascii=False,
        )
        row_hash = sha256(payload.encode("utf-8")).hexdigest()
        timestamp = row.get("timestamp")
        base = f"timestamp:{timestamp}" if timestamp else f"content:{row_hash}"
        hashes.append(row_hash)
        bases.append(base)
    counts = pd.Series(bases).value_counts().to_dict() if bases else {}
    response_ids = [
        sha256((base if counts.get(base, 0) == 1 else f"{base}:{row_hash}").encode("utf-8")).hexdigest()[:20]
        for base, row_hash in zip(bases, hashes)
    ]
    result.insert(0, "response_id", response_ids)
    result.insert(1, "row_hash", hashes)
    return result


def preview_workbook(contents: bytes, filename: str) -> ImportPreview:
    source_file_hash = sha256(contents).hexdigest()
    import_hash = sha256(
        f"{IMPORT_PIPELINE_VERSION}:{source_file_hash}".encode("utf-8")
    ).hexdigest()
    preview = ImportPreview(
        filename=filename,
        file_hash=import_hash,
        source_file_hash=source_file_hash,
    )
    try:
        raw = pd.read_excel(
            BytesIO(contents),
            sheet_name=0,
            dtype=object,
            keep_default_na=False,
        )
    except Exception as exc:  # pandas/openpyxl provide the useful detail
        preview.errors.append(f"The workbook could not be read: {exc}")
        return preview
    mapping, missing, unexpected = _resolve_columns(list(raw.columns))
    preview.mapping = mapping
    preview.missing_fields = missing
    preview.unexpected_columns = unexpected
    if missing:
        labels = ", ".join(FIELD_BY_KEY[key].label for key in missing)
        preview.errors.append(f"Required questionnaire columns were not recognized: {labels}.")
        return preview
    frame, warnings = _normalize_frame(raw, mapping)
    preview.frame = frame
    preview.warnings.extend(warnings)
    if unexpected:
        preview.warnings.append(
            f"{len(unexpected)} additional column(s) were not imported. Review them before activating the snapshot."
        )
    if "consent" in frame:
        consent = frame["consent"].map(normalize_text)
        nonconsent = int((~consent.isin({"consent", "i consent", "yes"})).sum())
        if nonconsent:
            preview.warnings.append(f"{nonconsent} response(s) do not contain a recognized affirmative consent value.")
    return preview
