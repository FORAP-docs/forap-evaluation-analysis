# Release validation

## Anonymous review snapshot, 14 October 2026

This snapshot includes the current supplementary-export features and later interface and database compatibility changes. Application code is copied from the current working version, including changes not yet published to the source repository.

- All 207 tests passed in a separate copy of this package on macOS using the existing Python 3.13 environment and installed dependencies. Five NumPy warnings arose from constant-rating fixtures in existing interface tests.
- The supplied synthetic workbook imported 12 fictional respondents with all 33 rating items. All seven construct scores were available, and all eight workspaces opened in Streamlit's application tests. No study codes or themes were loaded.
- A separate end-to-end synthetic check prepared all 13 supplementary export files, verified the ZIP against the separate downloads, confirmed the default raw-p setting, and verified that export preparation left the temporary database unchanged.
- The app opened in the in-app browser on localhost with the synthetic data. The overview and updated supplementary-export controls displayed correctly.
- A wheel built successfully with setuptools 84.0.0 and installed into an isolated target directory. Imports resolved from that installation. Dependencies were reused from the existing environment rather than downloaded into a fresh environment.
- The release archive contains source, documentation, tests, a blank template, and synthetic examples only. Test databases, study responses, contact information, private backups, logs, runtime environments, and Git history are excluded. Local documentation links were checked.

The synthetic workbook is an interface demonstration, not a statistically realistic study sample. Its patterned ratings can produce constant construct scores and negative or undefined reliability estimates. These are not the paper's results. Windows and Linux execution were not tested in this check.

## Version 0.3.0

Validated on 22 September 2026 in the same macOS environment.

- All 195 tests passed, including migration, export, and import of older workspaces containing standalone notes and change logs.
- Legacy standalone notes, audit logs, and code revisions are removed, and unused prior codebook metadata is discarded. Tests confirm deleted marker text is absent from the cleaned SQLite file.
- Questionnaire uploads and response snapshots remain intact. Current responses, codes, excerpts, assignments, highlights, reviews, themes, evidence, and background settings were verified unchanged during local migration.
- Opening an older workspace saves a recovery copy before cleanup. Old uploaded backup files remain unchanged, and their private staging copies are cleaned before import.
- The Notes & history tab and standalone note editor have been removed. Analysis progress remains available.

## Version 0.2.0

Validated on 22 September 2026 in the local macOS environment described below.

- All 192 tests passed, including full database round trips, malformed and incompatible files, recovery backup failures, transaction rollback, write-ahead log export, import confirmation, and session reset.
- A database exported from the preceding local app was imported through the new app's interface. Every stored record and sequence counter matched across the source, backup, and destination.
- All eight workspaces opened successfully using a temporary copy of the migrated database, without changing its application records.
- The source database was retained in a private archive. Study databases and recovery files remain local and excluded from Git.
- A fresh Python 3.13.9 environment was installed from the recorded dependencies on macOS. All 192 tests passed after retiring the previous installation, dependency checks passed, and the app opened successfully in the local browser.

## Initial release

Validated on 21 September 2026 using Python 3.13.9 on macOS and the versions recorded in `requirements-tested.txt`.

- All 173 tests passed in a separate temporary copy of the publication folder.
- The synthetic workbook imported 12 distinct responses across 56 recognized analytical columns without import warnings.
- All eight application workspaces opened with the synthetic responses and no preloaded study coding.
- The blank template contains the expected analytical headers and no response rows.
- The Python wheel built successfully using setuptools 84.0.0.
- Local documentation links resolved successfully.
- The initial publication archive contained no study database, participant exports, personal filesystem paths, or Git history.

Five NumPy runtime warnings occurred in existing interface tests that compute correlations from constant-rating fixtures. The tests completed successfully. No warnings occurred during the synthetic-workbook import.

Windows and Linux execution and independent reproduction of the paper's results were not verified. The study's private inputs and coding decisions are not included. The test suite checks implemented behavior and selected numerical cases, rather than establishing the validity of every possible analysis.
