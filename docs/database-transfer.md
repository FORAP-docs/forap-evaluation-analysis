# Database backup and transfer

Use **Upload & data health → Database backup & restore** to move a complete workspace between installations. CSV exports and questionnaire uploads do not include the saved coding or other workspace records.

## Transfer to another installation

1. Finish saving edits in the source app. Select **Prepare database export**, then download the `.sqlite3` file.
2. Keep the original installation and database until you have verified the transfer.
3. Start the destination app and close any other tabs for that installation.
4. Open the backup controls, enable **Edit mode**, and upload the exported file.
5. Review the validation result, active response count, and per-table counts. Confirm replacement and select **Import database**.
6. Check response totals, code definitions, coded excerpts, highlights, themes and evidence, notes, and background groupings in the destination app.

The original installation is not modified by export. The destination saves its existing state under `data/backups/` before replacing its records. The success message identifies the recovery file. To undo a transfer, import that file through the same controls.

## What is preserved

All application tables are transferred, including inactive responses and earlier questionnaire snapshots, optional contact fields, codebook versions and revisions, evidence links, review notes, saved background mappings and groupings, and the audit log. Record IDs and SQLite sequence counters are retained. No extra study coding or fabricated responses are created during transfer.

The export is a consistent SQLite backup, including committed changes held in a write-ahead log. It contains saved database records only. Unsaved editor drafts, Python environments, application source files, and Streamlit settings are not included. A prepared download stays at its preparation-time state until you prepare a new one.

## Validation and recovery

Before import, the app checks the file format, SQLite integrity, supported schema, and foreign-key relationships. It rejects unknown tables, columns, views, triggers, and unsupported schema versions. Files must be at most 50 MB. After creating and checking a recovery backup, all application records are replaced within one transaction and their relationships checked before commit. If validation, recovery backup creation, or replacement fails, the previous records remain intact.

Database backups and recovery files include private response text and optional email addresses. They are not anonymized and must not be committed to the public repository. The supplied ignore rules exclude the live database and its recovery folder.
