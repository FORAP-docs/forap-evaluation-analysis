from pathlib import Path
import sqlite3

from forap_analysis.database import Database
from forap_analysis.importer import preview_workbook
from test_importer import workbook_bytes


def test_import_activation_and_privacy_separation(tmp_path: Path):
    database = Database(tmp_path / "test.sqlite3")
    preview = preview_workbook(workbook_bytes(), "responses.xlsx")
    result = database.activate_import(preview)
    assert result["inserted"] == 2
    assert database.active_count() == 2
    analytic = database.active_data()
    assert "followup_email" not in analytic.columns
    assert database.import_exists(preview.file_hash)


def test_later_cumulative_snapshot_reconciles_rows(tmp_path: Path):
    database = Database(tmp_path / "test.sqlite3")
    first = preview_workbook(workbook_bytes(2), "responses-2.xlsx")
    second = preview_workbook(workbook_bytes(3), "responses-3.xlsx")
    database.activate_import(first)
    initial_labels = database.respondent_labels()
    result = database.activate_import(second)
    assert result == {"import_id": 2, "inserted": 1, "updated": 0, "unchanged": 2}
    assert database.active_count() == 3
    assert len(database.import_history()) == 2
    updated_labels = database.respondent_labels()
    assert list(initial_labels.values()) == ["R1", "R2"]
    assert all(updated_labels[response_id] == label for response_id, label in initial_labels.items())
    assert list(updated_labels.values()) == ["R1", "R2", "R3"]


def test_code_theme_coding_and_audit(tmp_path: Path):
    database = Database(tmp_path / "test.sqlite3")
    preview = preview_workbook(workbook_bytes(), "responses.xlsx")
    database.activate_import(preview)
    response_id = database.active_data().iloc[0]["response_id"]
    code_id = database.save_code("Adaptability", "Mentions adaptation", "Adaptation", "", "#0f62fe")
    database.set_response_codes(response_id, "suggestions", [code_id], "adapt to context", "Strong example")
    theme_id = database.save_theme("Adoption readiness", "Conditions for practical reuse", [code_id])
    assert len(database.codings("suggestions")) == 1
    assert theme_id in database.theme_codings()["theme_id"].tolist()


def test_codes_sort_numbered_names_naturally_and_filter_inactive(tmp_path: Path):
    database = Database(tmp_path / "test.sqlite3")
    for name in ["XC11 - Eleven", "XC2 - Two", "XC10 - Ten", "XC1 - One"]:
        database.save_code(name, "", "", "", domain="Cross-cutting")
    inactive_id = database.save_code("XC3 - Three", "", "", "", domain="Cross-cutting")
    database.deactivate_code(inactive_id)

    assert database.codes()["name"].tolist() == [
        "XC1 - One", "XC2 - Two", "XC10 - Ten", "XC11 - Eleven"
    ]
    assert database.codes(active_only=False)["name"].tolist() == [
        "XC1 - One", "XC2 - Two", "XC3 - Three", "XC10 - Ten", "XC11 - Eleven"
    ]


def test_codes_keep_domain_and_type_priority_with_joined_metadata(tmp_path: Path):
    database = Database(tmp_path / "test.sqlite3")
    version_id = database.create_codebook_version("Ordering test")
    parent_id = database.save_code(
        "Z domain heading", "", "", "", domain="B", code_type="Domain"
    )
    for name, domain in [
        ("XC10 - Ten", "B"),
        ("ST10 - Ten", "A"),
        ("XC2 - Two", "B"),
        ("ST2 - Two", "A"),
    ]:
        database.save_code(
            name, "", "", "", domain=domain, parent_id=parent_id,
            codebook_version_id=version_id,
        )

    codes = database.codes()
    assert codes["name"].tolist() == [
        "ST2 - Two", "ST10 - Ten", "Z domain heading", "XC2 - Two", "XC10 - Ten"
    ]
    children = codes.loc[codes["code_type"] != "Domain"]
    assert set(children["parent_name"]) == {"Z domain heading"}
    assert set(children["version_label"]) == {"Ordering test"}
    assert codes.index.tolist() == list(range(len(codes)))


def test_codes_sort_arbitrary_names_and_handle_empty_codebook(tmp_path: Path):
    database = Database(tmp_path / "test.sqlite3")
    assert database.codes().empty
    for name in ["Zebra", "General issue 10", "Alpha", "General issue 2", "Scope"]:
        database.save_code(name, "", "", "")

    assert database.codes()["name"].tolist() == [
        "Alpha", "General issue 2", "General issue 10", "Scope", "Zebra"
    ]


def test_editing_theme_name_updates_existing_theme(tmp_path: Path):
    database = Database(tmp_path / "analysis.sqlite3")
    database.initialize()
    code_id = database.save_code("Reusable projects", "Projects can be reused", "", "")
    theme_id = database.save_theme("Initial theme", "Initial statement", [code_id])

    updated_id = database.save_theme(
        "Refined theme",
        "Refined statement",
        [code_id],
        theme_id=theme_id,
        status="reviewed",
    )

    themes = database.themes()
    assert updated_id == theme_id
    assert len(themes) == 1
    assert themes.iloc[0]["name"] == "Refined theme"
    assert themes.iloc[0]["description"] == "Refined statement"
    assert themes.iloc[0]["status"] == "reviewed"
    assert len(database.audit_log()) >= 3


def test_updating_code_color_preserves_code_and_assignments(tmp_path: Path):
    database = Database(tmp_path / "test.sqlite3")
    database.activate_import(preview_workbook(workbook_bytes(), "responses.xlsx"))
    response_id = database.active_data().iloc[0]["response_id"]
    code_id = database.save_code("Adaptability", "Mentions adaptation", "Adaptation", "", "#0f62fe")
    database.set_response_codes(response_id, "suggestions", [code_id], "adapt to context")

    database.update_code_color(code_id, "#198038")

    code = database.codes().set_index("id").loc[code_id]
    assert code["color"] == "#198038"
    coding = database.codings("suggestions").iloc[0]
    assert coding["code_id"] == code_id
    assert coding["color"] == "#198038"
    assert "update_color" in database.audit_log()["action"].tolist()


def test_updating_code_color_rejects_invalid_values(tmp_path: Path):
    database = Database(tmp_path / "test.sqlite3")
    code_id = database.save_code("Adaptability", "", "", "")

    try:
        database.update_code_color(code_id, "blue")
    except ValueError as error:
        assert "#RRGGBB" in str(error)
    else:
        raise AssertionError("Invalid code colors should be rejected.")


def test_background_category_mappings_are_persistent_and_removable(tmp_path: Path):
    database = Database(tmp_path / "test.sqlite3")

    database.save_background_mapping(
        "computing_areas",
        "Distributed Computing",
        "Systems / Networking / Cloud Computing",
    )
    database.save_background_mapping(
        "computing_areas",
        "distributed computing",
        "Distributed systems",
    )

    mappings = database.background_mappings("computing_areas")
    assert len(mappings) == 1
    assert mappings.iloc[0]["source_value"] == "Distributed Computing"
    assert mappings.iloc[0]["canonical_value"] == "Distributed systems"

    database.delete_background_mapping("computing_areas", "DISTRIBUTED COMPUTING")
    assert database.background_mappings("computing_areas").empty
    assert {"set_mapping", "remove_mapping"}.issubset(set(database.audit_log()["action"]))


def test_background_groupings_can_be_saved_updated_and_deleted(tmp_path: Path):
    database = Database(tmp_path / "test.sqlite3")
    grouping_id = database.save_background_grouping(
        "institution_type",
        "University context",
        [
            {
                "name": "University institutions",
                "categories": ["Research university", "Teaching-focused college or university"],
            },
            {
                "name": "Other institutions",
                "categories": ["Polytechnic / institute of technology"],
            },
        ],
    )

    saved = database.background_groupings("institution_type")
    assert len(saved) == 1
    assert saved.iloc[0]["id"] == grouping_id
    assert saved.iloc[0]["groups"][0]["name"] == "University institutions"

    updated_id = database.save_background_grouping(
        "institution_type",
        "Institution emphasis",
        [
            {"name": "Research", "categories": ["Research university"]},
            {
                "name": "Teaching and applied",
                "categories": [
                    "Teaching-focused college or university",
                    "Polytechnic / institute of technology",
                ],
            },
        ],
        grouping_id=grouping_id,
    )
    assert updated_id == grouping_id
    assert database.background_groupings("institution_type").iloc[0]["name"] == "Institution emphasis"

    database.select_background_grouping("institution_type", grouping_id)
    assert database.selected_background_grouping("institution_type") == grouping_id

    database.delete_background_grouping(grouping_id)
    assert database.background_groupings("institution_type").empty
    assert database.selected_background_grouping("institution_type") is None
    assert {"create", "update", "delete"}.issubset(
        set(database.audit_log()["action"])
    )


def test_background_groupings_reject_duplicate_category_assignments(tmp_path: Path):
    database = Database(tmp_path / "test.sqlite3")

    try:
        database.save_background_grouping(
            "roles",
            "Overlapping definition",
            [
                {"name": "Teaching", "categories": ["Instructor"]},
                {"name": "Research", "categories": ["Instructor"]},
            ],
        )
    except ValueError as error:
        assert "only one" in str(error)
    else:
        raise AssertionError("A category should not be saved in more than one group.")


def test_hierarchical_codebook_and_multiple_meaning_units(tmp_path: Path):
    database = Database(tmp_path / "test.sqlite3")
    preview = preview_workbook(workbook_bytes(), "responses.xlsx")
    database.activate_import(preview)
    response_id = database.active_data().iloc[0]["response_id"]
    version_id = database.create_codebook_version("Working codebook 1", "Working version")
    parent_id = database.save_code(
        "Implementation readiness",
        "Adoption conditions",
        "",
        "",
        code_type="Domain",
        domain="Implementation readiness",
        codebook_version_id=version_id,
    )
    code_id = database.save_code(
        "Technology requirements",
        "Hardware and software needs",
        "Mentions infrastructure",
        "",
        parent_id=parent_id,
        domain="Implementation readiness",
        code_type="Topic",
        codebook_version_id=version_id,
    )
    first_id = database.save_meaning_unit(
        response_id,
        "suggestions",
        "first exact idea",
        [code_id],
        "First note",
        is_pilot=True,
    )
    second_id = database.save_meaning_unit(
        response_id,
        "suggestions",
        "second exact idea",
        [code_id],
        "Second note",
        is_pilot=True,
    )
    assert first_id != second_id
    units = database.meaning_units("suggestions", response_id)
    assert len(units) == 2
    assert set(units["code_names"]) == {"Technology requirements"}
    combined = database.codings("suggestions")
    assert len(combined) == 2
    assert set(combined["source"]) == {"meaning_unit"}
    assert set(combined["meaning_unit_id"].astype(int)) == {first_id, second_id}

    theme_id = database.save_theme("Operational feasibility", "Readiness for adoption", [code_id])
    themed = database.theme_codings()
    assert theme_id in themed["theme_id"].tolist()
    assert themed["response_id"].nunique() == 1


def test_existing_database_is_migrated_without_losing_codes(tmp_path: Path):
    path = tmp_path / "legacy.sqlite3"
    now = "2026-01-01T00:00:00+00:00"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """CREATE TABLE codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                inclusion_criteria TEXT NOT NULL DEFAULT '',
                exclusion_criteria TEXT NOT NULL DEFAULT '',
                color TEXT NOT NULL DEFAULT '#0f62fe',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            "INSERT INTO codes(name, created_at, updated_at) VALUES ('Existing code', ?, ?)",
            (now, now),
        )
    database = Database(path)
    codes = database.codes()
    assert codes.iloc[0]["name"] == "Existing code"
    assert {"parent_id", "domain", "code_type", "codebook_version_id"}.issubset(codes.columns)
    with database.connect() as connection:
        tables = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_schema WHERE type='table'").fetchall()
        }
    assert {
        "codebook_versions",
        "code_revisions",
        "meaning_units",
        "meaning_unit_codes",
        "background_groupings",
        "background_grouping_selections",
    }.issubset(tables)


def test_theme_evidence_and_qualitative_reset_preserve_responses(tmp_path: Path):
    database = Database(tmp_path / "test.sqlite3")
    database.activate_import(preview_workbook(workbook_bytes(), "responses.xlsx"))
    response_id = database.active_data().iloc[0]["response_id"]
    version_id = database.create_codebook_version("Working codebook 1")
    code_id = database.save_code(
        "Practical examples",
        "Requests concrete examples",
        "Mentions examples",
        "",
        codebook_version_id=version_id,
    )
    unit_id = database.save_meaning_unit(
        response_id,
        "suggestions",
        "exact suggestion",
        [code_id],
    )
    theme_id = database.save_theme(
        "Practical demonstration supports adoption",
        "Experts need concrete demonstrations before adoption.",
        [code_id],
        linked_constructs=["Overall usefulness"],
        implication="Add complete worked examples.",
        contrasting_evidence="Some experts already found the structure useful.",
    )
    database.save_theme_evidence(theme_id, unit_id, "supporting", "Clear example", True)
    evidence = database.theme_evidence(theme_id)
    assert len(evidence) == 1
    assert evidence.iloc[0]["is_representative"] == 1
    assert database.themes().iloc[0]["respondents"] == 1

    removed = database.reset_qualitative_analysis()
    assert removed["codes"] == 1
    assert removed["meaning_units"] == 1
    assert removed["themes"] == 1
    assert database.active_count() == 2
    assert database.codes().empty
    assert database.meaning_units().empty
    assert database.themes().empty
