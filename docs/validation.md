# Release validation

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
