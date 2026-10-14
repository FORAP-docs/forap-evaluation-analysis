# FORAP Evaluation Analysis

A local application for examining expert-evaluation questionnaires about FORAP (Framework for Organizing Reusable and Adaptable PjBL Projects). It combines quantitative summaries, qualitative coding, and mixed-method displays in a Streamlit interface.

This repository provides the analysis software and synthetic examples. Participant responses, study coding decisions, and the paper's results are not included. The example data demonstrate the interface and do not reproduce the study findings.

## Quick start

Requires Python 3.11 or later. Run these commands from the downloaded repository folder.

**macOS or Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m streamlit run app.py
```

**Windows PowerShell**

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe -m streamlit run app.py
```

Open <http://127.0.0.1:8501> in a browser. Stop the server with `Ctrl+C`. Internet access is needed to install dependencies. Analysis runs locally after installation. On macOS, `start.command` provides a launcher from the repository folder.

## Try the example

1. Start the app and select **Upload & data health**.
2. Enable **Edit mode** at the top of the workspace.
3. Upload [`examples/synthetic_responses.xlsx`](examples/synthetic_responses.xlsx).
4. Review the validation summary, then select **Activate validated snapshot**.
5. Open **Overview**, **Items & scales**, or **Background comparisons** to explore the 12 synthetic responses.
6. In **Thematic analysis**, create working codes and assign them to passages. Add themes and evidence to explore **Mixed methods**.

Codes, themes, and interpretations are entered by the analyst. Importing a workbook does not generate them automatically. See the [walkthrough](docs/walkthrough.md) for an example coding exercise.

## Load your own data

Use [`examples/response_template.xlsx`](examples/response_template.xlsx), or a compatible Google Forms Excel export. Keep one response per row and column headers in the first row of the first worksheet. The app accepts the template's field keys and recognized questionnaire wording.

The [input guide](docs/input-format.md) explains required columns, rating scales, missing values, and cumulative imports. The [data dictionary](docs/data-dictionary.md) lists each field. The follow-up email column may be omitted or left blank.

This app implements a specific questionnaire. Using another instrument requires updating its field definitions, scales, and analysis logic. Renaming unrelated survey columns to match this template does not make the instruments equivalent.

## Analysis features

- Item distributions, descriptive statistics, confidence intervals, and construct scores.
- Cronbach's alpha and corrected item-total correlations.
- Background comparisons using Welch t-tests, one-way ANOVA with Tukey follow-up comparisons, and Spearman correlations.
- Working codes, exact excerpts, passage highlights, and themes.
- Mixed-method displays connecting coded evidence and ratings.
- CSV and Markdown exports for further analysis and reporting.
- Complete comparison and rating-distribution exports, optional Holm sensitivity analysis, and separate supplementary files with a README, available individually or as a ZIP.

See [analysis methods](docs/analysis-methods.md) for scoring rules and interpretation limits.

### Prepare supplementary files

Open **Reports & exports → Supplementary exports**. Choose whether to add Holm-adjusted p-values and whether the family includes all main tests together or separates item and construct tests. Leave the adjustment set to **None** to export raw results only. Optionally select specific theme-evidence rows for an interpretation worksheet, then select **Prepare export files**.

Download each CSV, the README, and the JSON manifest individually, or download them together as a ZIP. These are separate editable files, not a PDF. The package uses the current data and category mappings, so it is not a record of which analyses were performed historically. Existing response-level and working-code exports remain available separately.

See [export contents and settings](docs/supplementary-exports.md) for the file list, comparison families, and interpretation worksheet. Preparing an export does not change the database or publish anything.

## Local storage and data sharing

The app creates `data/forap_analysis.sqlite3` inside this repository folder. Imports, coding, and earlier snapshots persist there. Back up the database to preserve your work. **Edit mode** controls which editing tools are visible. It is not authentication.

The app does not store standalone notes, change logs, or previous code revisions. Opening an older workspace removes these records after saving a private recovery copy under `data/backups/before_history_removal_*.sqlite3`. Unused prior codebook metadata is also removed. Questionnaire upload snapshots, current analysis records, and notes attached to excerpts, highlights, and theme evidence are preserved. Older recovery files still contain their original contents.

Optional follow-up emails are stored in separate fields in the same local database and excluded from analytical views and report downloads. Full database backups include them. The database is not encrypted by the app. Exported responses can still contain timestamps, background information, and identifying text. Review exports before sharing them.

The supplied Git ignore rules exclude databases, private inputs, exports, logs, and local environments. Only the two synthetic/template workbooks are allowed through the spreadsheet ignore rule. No study data are needed to install or try the app. Access to the original inputs and coding decisions would be needed to reproduce the paper's numerical and qualitative results.

## Back up or transfer a workspace

Open **Upload & data health → Database backup & restore**.

1. In the source installation, select **Prepare database export**, then **Download database (.sqlite3)**.
2. In the destination installation, open the same section and enable **Edit mode**.
3. Upload the database backup and review its validation summary and record counts.
4. Confirm replacement and select **Import database**. The app reloads in view mode.

A database backup includes all saved response snapshots, optional email addresses, working codes, coded excerpts, highlights and reviews, themes and evidence, their attached analytical notes, and background settings. Standalone notes, change logs, and previous code revisions are excluded from exports and from older backups during import. **Keep these files private. They are not anonymized exports.** Prepare a new export after making further changes.

Import replaces the entire workspace rather than combining databases. Before replacement, the app saves the previous database under `data/backups/before_restore_*.sqlite3`. Import that recovery file through the same controls to return to the earlier workspace. Invalid or incompatible backups are rejected, and replacement runs in a transaction so failed imports leave the current workspace intact. Close other app tabs before importing. Unsaved form entries and local software settings are not part of a database backup.

The importer accepts compatible FORAP SQLite backups up to 50 MB. Arbitrary SQLite files and unsupported schema versions are not accepted. See the [transfer guide](docs/database-transfer.md) for migration and verification steps.

To start a new empty study without restoring a backup, stop the app and move its current database to a private backup location. Restart the app to create an empty database. Activating a new workbook alone retains older snapshots.

## Development

```bash
python -m pip install -e '.[dev]'
python -m pytest
```

On Windows, use `.venv\Scripts\python.exe` for both commands. The [development guide](docs/development.md) describes the modules and the recorded dependency environment in `requirements-tested.txt`.

## License

The application is provided under the [MIT License](LICENSE). This license covers the code and supplied synthetic examples. It does not grant rights to any participant data loaded separately.
