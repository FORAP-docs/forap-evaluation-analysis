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
- Working codes, exact excerpts, passage highlights, themes, analytic notes, and an audit log.
- Mixed-method displays connecting coded evidence and ratings.
- CSV and Markdown exports for further analysis and reporting.

See [analysis methods](docs/analysis-methods.md) for scoring rules and interpretation limits.

## Local storage and data sharing

The app creates `data/forap_analysis.sqlite3` inside this repository folder. Imports, coding, notes, and earlier snapshots persist there. Back up the database to preserve your work. **Edit mode** controls which editing tools are visible. It is not authentication.

Optional follow-up emails are stored in separate fields in the same local database and excluded from analytical views and downloads. The database is not encrypted by the app. Exported responses can still contain timestamps, background information, and identifying text. Review exports before sharing them.

The supplied Git ignore rules exclude databases, private inputs, exports, logs, and local environments. Only the two synthetic/template workbooks are allowed through the spreadsheet ignore rule. No study data are needed to install or try the app. Access to the original inputs and coding decisions would be needed to reproduce the paper's numerical and qualitative results.

To switch from demonstration data to a real study, stop the app and move the demonstration database to a separate backup location. Restart the app to create an empty database. Activating a new workbook alone retains older snapshots.

## Development

```bash
python -m pip install -e '.[dev]'
python -m pytest
```

On Windows, use `.venv\Scripts\python.exe` for both commands. The [development guide](docs/development.md) describes the modules and the recorded dependency environment in `requirements-tested.txt`.

## License

The application is provided under the [MIT License](LICENSE). This license covers the code and supplied synthetic examples. It does not grant rights to any participant data loaded separately.
