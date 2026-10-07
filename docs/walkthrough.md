# Example walkthrough

The 12 rows in `examples/synthetic_responses.xlsx` are fictional. Ratings follow deterministic patterns for interface testing. Background categories and comments are invented. No participant responses or study estimates were used to construct them. The scores are not intended to model a population or support statistical conclusions.

## Import and explore

Start the app, choose **Upload & data health**, enable **Edit mode**, and upload the synthetic workbook. The preview should recognize 56 columns and 12 rows without validation warnings. Select **Activate validated snapshot**.

Open **Overview** for background distributions and construct summaries. **Items & scales** shows item distributions and internal consistency. **Background comparisons** allows exploratory comparisons using the supplied fictional background categories.

## Try qualitative coding

In **Thematic analysis**, enable **Edit mode** and create a working code named `Worked examples`. Give it a definition such as `Requests for concrete examples of how to use a project package`.

Find a synthetic comment containing `Add a worked example of adapting a project.` Select the exact sentence as an excerpt and assign the code. Open the code's excerpt view to inspect its evidence and try the passage-highlighting controls.

Create a theme named `Examples help explain adaptation` and attach that excerpt as supporting evidence. This is a demonstration interpretation, not a finding from the study. Open **Mixed methods** to inspect how coded responses can be connected to ratings. The application does not infer codes or themes from uploaded text.

## Export and start a separate analysis

Use **Reports & exports** to download an item summary or the working codebook. Response and excerpt downloads may contain all the text you entered, so inspect them before sharing.

When finished, stop the server. Move `data/forap_analysis.sqlite3` to a separate demonstration backup location before starting a real study. The next launch creates an empty database. Retain the backup if you want to revisit the example coding exercise.
