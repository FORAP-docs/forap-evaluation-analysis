# Analysis methods

The questionnaire groups rating items into seven constructs: clarity, completeness, overall usefulness, instructor support, student support, assessment support, and project attributes. Field membership and response scales are defined in `forap_analysis/schema.py`.

## Quantitative summaries

Item summaries use available responses and report valid counts, missing counts, means, sample standard deviations, medians, quartiles, and 95% t-based confidence intervals for the mean. Top-two and bottom-two percentages use valid responses as their denominator. Confidence intervals are not truncated to the rating scale.

A respondent's construct score is the mean of the available construct items when at least half are answered, rounding the required item count upward. Cronbach's alpha uses complete cases within each construct. Corrected item-total correlations compare an item with the mean of the other available items in that construct and require at least three paired observations. These correlations can therefore use different cases from alpha.

## Comparisons

Two-group comparisons use Welch t-tests and report Hedges' g. Comparisons with three or more eligible groups use ordinary one-way ANOVA and eta-squared. Groups with fewer than two observations are excluded from the inferential test. The analysis function also computes Tukey HSD comparisons, using the Tukey-Kramer adjustment for unequal group sizes. The interface displays significant pairs after an ANOVA p-value below .05.

Multi-select categories are examined as selected versus not selected. Ordered experience measures use Spearman correlations. Mixed-method comparisons contrast respondents with linked coded feedback against other respondents. Absence of linked feedback does not establish absence of that view.

Tests across separate outcomes and background categories are exploratory and are not adjusted as one multiple-testing family. Tukey comparisons have their own within-analysis adjustment. Report group sizes, distributions, assumptions, uncertainty, and effect sizes alongside p-values. Internal consistency does not establish that a construct is unidimensional.

## Qualitative work

The analyst defines codes, selects exact excerpts, assigns codes, develops themes, and links evidence. Several passages and codes may belong to one response. Highlights annotate exact text without changing the quotation. Review labels record workflow status and do not establish independent validation.

Respondent counts and excerpt counts describe different units. Repeated excerpts from the same respondent should not be treated as independent participants. Theme-evidence counts describe the links selected by the analyst and are not automatically prevalence estimates.

The app supports analysis and record keeping. Interpretations, methodological choices, and final reporting remain the analyst's responsibility. Original study inputs and coding decisions are not distributed with this software.
