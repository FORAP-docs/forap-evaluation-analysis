"""Separate-file and ZIP downloads for a draft supplementary package."""
from __future__ import annotations

import hashlib
import json

import pandas as pd
import streamlit as st

from .exports import (
    FAMILY_OPTIONS, analysis_digest, build_bundle, comparison_inventory, csv_bytes,
    frame_digest, implementation_digest, interpretation_table, zip_bundle,
)


def render_supplement_exports(db, frame: pd.DataFrame) -> None:
    st.divider()
    st.subheader("Supplementary exports")
    st.caption(
        "Prepare separate CSV files with a README and a version manifest. "
        "Download them individually or together as a ZIP. No PDF is generated."
    )
    codes, themes = db.codes(active_only=False), db.themes()
    mappings = db.background_mappings()
    evidence = db.theme_evidence()
    worksheet = interpretation_table(
        evidence, db.respondent_labels(), set(frame["response_id"].astype(str)),
    )
    left, right = st.columns(2)
    with left:
        method = st.selectbox(
            "Across-test adjustment", ["none", "holm"],
            format_func=lambda value: {"none": "None (raw p-values)", "holm": "Holm sensitivity analysis"}[value],
            key="supplement_adjustment",
        )
    with right:
        family = st.selectbox(
            "Comparison families", list(FAMILY_OPTIONS),
            format_func=FAMILY_OPTIONS.get, key="supplement_family",
            help="The family is fixed before preview filtering. Only finite main-test p-values enter Holm.",
        )
    st.caption(
        "Includes standard background comparisons across all items and constructs using current category mappings. "
        "Custom groupings and mixed-method tests are outside this inventory. "
        "This is a fresh calculation, not the historical analysis record."
    )
    if method == "holm":
        st.info(
            "Holm will be added as a retrospective sensitivity analysis. Original p-values and "
            "Tukey-adjusted pairwise results remain separate. This does not change existing analysis views."
        )
    selected = []
    with st.expander("Choose interpretation examples (optional)"):
        st.caption(
            "Select the evidence rows to include. No quotations are selected by default. "
            "The worksheet preserves existing notes and leaves new interpretation fields blank for you to complete."
        )
        labels = {
            row["evidence_id"]: f"{row['respondent']} · {row['theme']} · {row['source_question']} · {row['evidence_id']}"
            for row in worksheet.to_dict("records")
        }
        # Remove selections whose evidence was deleted since the last run.
        if "supplement_evidence" in st.session_state:
            st.session_state["supplement_evidence"] = [
                item for item in st.session_state["supplement_evidence"] if item in labels
            ]
        selected = st.multiselect(
            "Evidence to export", list(labels), format_func=labels.get,
            key="supplement_evidence",
        )
        chosen = worksheet[worksheet["evidence_id"].isin(selected)]
        if not chosen.empty:
            st.dataframe(chosen, hide_index=True, width="stretch")
            st.download_button(
                "Download selected interpretation worksheet (.csv)", csv_bytes(chosen),
                "forap_selected_interpretations.csv", "text/csv", key="supplement_interpretation_download",
            )

    signature_parts = [
        analysis_digest(frame), frame_digest(frame), implementation_digest(),
        *[frame_digest(table) for table in (codes, themes, mappings, worksheet)],
        method, family, sorted(selected),
    ]
    signature = hashlib.sha256(json.dumps(signature_parts).encode()).hexdigest()
    current = st.session_state.get("supplement_prepared")
    if current and current["signature"] != signature:
        st.session_state.pop("supplement_prepared", None)
        current = None
        st.info("The data, notes, or export options changed. Prepare the files again to use the current version.")
    if st.button("Prepare export files", type="primary", key="supplement_prepare"):
        with st.spinner("Calculating the complete comparison inventory and preparing files…"):
            inventory = comparison_inventory(frame)
            files = build_bundle(
                frame, codes, themes, inventory, mappings,
                method=method, family=family,
                selected_interpretations=worksheet[worksheet["evidence_id"].isin(selected)],
            )
            current = {"signature": signature, "files": files, "zip": zip_bundle(files)}
            st.session_state["supplement_prepared"] = current
    if not current:
        return

    files = current["files"]
    st.success(f"Prepared {len(files)} separate files. Review the contents before sharing.")
    st.download_button(
        "Download all files (.zip)", current["zip"], "forap_supplementary_exports.zip",
        "application/zip", key="supplement_zip_download",
    )
    filename = st.selectbox("Individual file", list(files), key="supplement_file")
    mime = "text/csv" if filename.endswith(".csv") else "application/json" if filename.endswith(".json") else "text/markdown"
    st.download_button(
        "Download this file", files[filename], filename, mime, key="supplement_file_download",
    )
    if filename.endswith(".csv"):
        from io import BytesIO
        table = pd.read_csv(BytesIO(files[filename]))
        if filename == "comparisons.csv":
            level = st.selectbox("Preview outcome level", ["All", "construct", "item"], key="supplement_preview_level")
            if level != "All":
                table = table.loc[table["outcome_level"].eq(level)]
            st.caption("Preview filters do not change downloads, adjustment families, or adjusted p-values.")
        st.dataframe(table, hide_index=True, width="stretch")
    elif filename.endswith(".md"):
        st.markdown(files[filename].decode())
    else:
        st.json(json.loads(files[filename]))
