# Supplementary exports

Open **Reports & exports → Supplementary exports**. Preparing files calculates a fresh reporting snapshot in memory. It does not write to the analysis database. Download separate files or a ZIP containing those same files and one README. No PDF is generated, and nothing is uploaded.

## Files

| File | Contents |
| --- | --- |
| `item_statistics.csv` | Existing item summaries, including top-two and bottom-two percentages and mean intervals |
| `construct_statistics.csv` | Aggregate construct summaries and alpha, without respondent-level scores |
| `rating_distributions.csv` | All five rating categories for every item, scale labels, counts, percentages, valid N, and missing N |
| `written_response_coverage.csv` | Nonblank responses for each of the 11 open-ended questions |
| `active_codebook.csv` | Active code definitions, inclusion and exclusion criteria, and theme uses |
| `theme_documentation.csv` | Current theme descriptions, statuses, implications, and contrasting evidence |
| `comparisons.csv` | All standard background-test candidates, raw results, effect estimates, eligibility status, and optional Holm values |
| `comparison_groups.csv` | Group sizes, included group means and SDs, and small-group exclusions linked by test ID |
| `tukey_pairs.csv` | All computed pairs with Tukey-adjusted p-values and simultaneous intervals, linked to the omnibus result |
| `assumption_checks.csv` | Existing diagnostic checks linked by test ID |
| `comparison_definitions.csv` | Background fields, observed multi-select categories, and analysis types |
| `selected_interpretations.csv` | Optional worksheet containing only explicitly selected theme-evidence rows |
| `manifest.json` | Export time, package and dependency versions, calculation-code fingerprint, settings, category mappings, file hashes, and family sizes |
| `README.md` | File list, definitions, scope, and interpretation limits |

The ordinary **Data export** selector also offers full rating distributions, written-response coverage, and an active codebook. Existing private exports remain available.

## Comparison scope and adjustment

The inventory uses the same background definitions and statistical functions as the app. It crosses each standard background comparison with all 33 items and seven construct averages. Multi-select backgrounds produce one selected-versus-not-selected comparison per observed applicable category. Missing and not-applicable selections do not count as not selected. Custom groupings and mixed-method code/theme tests are outside this inventory.

Every defined candidate remains in the main table. A test with no finite p-value is marked not estimable, with a warning. Categories with fewer than two valid outcome responses are retained in the group table with an exclusion reason. Other omitted responses can have a missing outcome, a missing or inapplicable background, or an unrecognized ordered category.

No across-test adjustment is selected by default. The optional Holm method uses all finite raw main-test p-values within the chosen family definition:

- **All item and construct tests together:** one family across all standard comparisons.
- **Separate families for item tests and construct tests:** one family per outcome level across all standard backgrounds.

These are explicit retrospective sensitivity options, not a reconstruction of a prespecified analysis. Choose the family for a methodological reason before using its result. Raw p-values remain unchanged. Tukey values and diagnostic assumption-check p-values are separate from these main-test families. Preview filtering does not recalculate any family or change downloaded files.

The export adds Welch degrees of freedom and 95% intervals for mean differences using the same samples as the existing tests. The effect direction is explicit. ANOVA degrees of freedom use numerator and denominator columns. Spearman degrees of freedom are blank. There are no added intervals for Hedges' g, eta-squared, or Spearman rho.

The fields `reported_in_paper` and `selection_reason` start as `Not recorded`. Complete them outside the app if needed. The app does not infer which tests were used in the paper. Current mappings and the calculation-code fingerprint identify this export, but do not establish historical analysis provenance.

## Qualitative selections

The active codebook excludes inactive records. It is not automatically labeled final or approved. Theme descriptions and evidence notes are not rewritten by the exporter.

No interpretation examples are selected by default. Select specific evidence rows to create a worksheet. The worksheet preserves the exact quotation, stable respondent label, source question, evidence role, and existing notes. Fields for descriptive meaning, theme interpretation, alternative explanation, and proposed change remain blank for the analyst to complete outside the app. A new interpretation is not inferred from a code label.

Only evidence from currently active respondents is offered. The app's stable respondent mapping supplies R labels, rather than the displayed response order. Coverage counts use nonblank source responses, not coded passages or theme counts. Percentages use the full active sample as their denominator.

## Review and persistence

Preparing files leaves them in the current app session until the inputs or options change. Changes to data, mappings, codes, themes, evidence notes, selected rows, or adjustment settings invalidate the prepared package. Download files locally if they need to be retained after the app closes.

The bundle uses an explicit file list. It does not include the database, emails, timestamps, complete questionnaire responses, respondent-level construct scores, or all coded excerpts. Analyst metadata, category labels, small-group summaries, and selected quotations still require review before sharing. Selecting a quotation is not a declaration that consent permits its publication.

Add the blank questionnaire, historical evaluation materials, or other documents separately. This feature does not determine a conference's supported supplementary formats. The ZIP is a convenience container, and every file is also downloadable on its own.
