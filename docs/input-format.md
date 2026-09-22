# Input format

The importer reads the first worksheet of an `.xlsx` workbook. Row 1 must contain unique column headers. Each following row represents one response. Use the supplied blank template for new files.

## Columns

The questionnaire defines 57 fields: 56 analytical columns and one optional follow-up email column. All analytical headers must be present, even when individual answers are blank. The email header may be omitted. See [data dictionary](data-dictionary.md).

Headers may use the exact field keys in the template or the recognized questionnaire text shown in the dictionary. Header matching ignores letter case and normalizes whitespace. Missing or ambiguous required headers prevent import. Additional unrecognized columns are reported and excluded.

## Values

- **Timestamp:** an Excel date/time or a parseable date/time string. Retain timestamps when exporting cumulative responses. If a timestamp is missing or unreadable, the importer uses a content-derived identifier and reports a warning.
- **Consent:** `I consent`, `Consent`, or `Yes` are recognized affirmative values. Other values generate a warning. The importer does not automatically exclude those rows. Apply the appropriate participation criteria before importing study data.
- **Agreement:** integers 1 through 5 or `Strongly disagree`, `Disagree`, `Neutral`, `Agree`, `Strongly agree`.
- **Usefulness:** integers 1 through 5 or `Not useful`, `Slightly useful`, `Moderately useful`, `Very useful`, `Extremely useful`.
- **Effectiveness:** integers 1 through 5 or `Not effective`, `Slightly effective`, `Moderately effective`, `Very effective`, `Extremely effective`.
- **PjBL experience:** integers 0 through 3 or `None`, `Limited`, `Moderate`, `Extensive`.
- **Multiple selections:** separate choices with commas or semicolons. Category names should not contain those separators.
- **Open-ended text:** plain text, including line breaks. Leave unanswered cells blank.
- **Follow-up email:** optional. Omit this column when contact details are not needed.

Blank ratings are treated as missing. Unrecognized or out-of-range rating values are set to missing and reported in the import warnings. Use the documented integer categories, even though the current numeric parser accepts fractional values within the scale bounds.

Years-of-experience categories used for ordered comparisons are `Beginner (e.g., <= 5 years)`, `Intermediate (e.g., 6-10 years)`, and `Experienced (e.g., 11+ years)`. The app also provides background-category mappings and saved groupings.

## Imports and response identity

Upload cumulative exports containing all responses intended for the active analysis. Activation replaces the active snapshot and retains previous snapshots. Responses absent from the new export become inactive. The interface requires confirmation if the incoming workbook has fewer rows.

The same workbook cannot be activated twice under the same importer version. Response identifiers normally derive from submission timestamps. Duplicate timestamps additionally use response content. Editing a timestamp, or editing content for a response without a unique timestamp, can therefore create a new identity. Inspect new, changed, and absent counts before activation.

Keep demonstration and research databases separate. Importing real responses over the synthetic example does not remove the synthetic snapshot from history.
