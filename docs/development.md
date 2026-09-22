# Development

## Source layout

| Path | Purpose |
| --- | --- |
| `app.py` | Streamlit pages, editing controls, and downloads |
| `forap_analysis/schema.py` | Questionnaire fields, scales, and category options |
| `forap_analysis/importer.py` | Workbook validation, scoring, and response identifiers |
| `forap_analysis/statistics.py` | Quantitative summaries and comparisons |
| `forap_analysis/database.py` | SQLite storage, snapshots, coding, and audit records |
| `forap_analysis/qualitative.py` | Corpus and qualitative summaries |
| `forap_analysis/charts.py` | Shared chart functions |
| `forap_analysis/highlights.py` | Exact passage validation and rendering |
| `forap_analysis/navigation.py` | Respondent navigation state |
| `forap_analysis/edit_mode.py` | Editing state and draft preservation |
| `tests/` | Statistical, import, database, and interface tests |

## Environment

`pyproject.toml` declares the supported dependency ranges. `requirements-tested.txt` records exact versions from the tested Python environment, including transitive dependencies. It is an environment snapshot, not a hash-verified or cross-platform lockfile. Availability can differ across Python releases and operating systems.

For the recorded versions, create an environment and run:

```bash
python -m pip install -r requirements-tested.txt
python -m pip install -e '.[dev]'
python -m pytest
```

The tests create temporary databases and synthetic inputs. They do not require the study database. Run tests from this repository's root so local imports resolve to this copy of the source.

## Extending the app

For a different questionnaire, update the fields, recognized header text, scales, construct membership, and any questionnaire-specific displays. Add representative synthetic inputs and tests for the revised scoring rules. Changes to parsing or response identity should increment `IMPORT_PIPELINE_VERSION` and account for existing local databases.

Run the test suite after modifying numerical methods, storage, imports, or interface state. Document changes that affect missing-data rules, denominators, statistical tests, or exported results. Use synthetic inputs in examples and bug reports.

The repository contains the reusable application. Study-specific migrations, historical manuscript generators, and private review records are not runtime dependencies.
