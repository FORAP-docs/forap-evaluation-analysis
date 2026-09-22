# Release validation

Validated on 21 September 2026 using Python 3.13.9 on macOS and the versions recorded in `requirements-tested.txt`.

- All 173 tests passed in a separate temporary copy of the publication folder.
- The synthetic workbook imported 12 distinct responses across 56 recognized analytical columns without import warnings.
- All eight application workspaces opened with the synthetic responses and no preloaded study coding.
- The blank template contains the expected analytical headers and no response rows.
- The Python wheel built successfully using setuptools 84.0.0.
- Local documentation links resolved successfully.
- The publication folder contains no study database, participant exports, personal filesystem paths, or Git history.

Five NumPy runtime warnings occurred in existing interface tests that compute correlations from constant-rating fixtures. The tests completed successfully. No warnings occurred during the synthetic-workbook import.

Windows and Linux execution, installation into a newly downloaded dependency environment, and reproduction of the paper's results were not verified. The study's private inputs and coding decisions are not included. The test suite checks implemented behavior and selected numerical cases, rather than establishing the validity of every possible analysis.
