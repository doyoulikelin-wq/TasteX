#!/usr/bin/env python3
"""Independent, exhaustive source-to-database fidelity checks (standard library).

Run from any directory. Revalidation against source needs the original workspace;
normal database querying does not. This test never writes to the database.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import unittest
from collections import Counter

DB_DIR = Path(__file__).resolve().parents[1]
WORKSPACE = DB_DIR.parent
DATABASE = DB_DIR / "flavor.sqlite"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def unpack(value):
    return json.loads(value) if value is not None else None


class SourceFidelity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = sqlite3.connect(DATABASE.resolve().as_uri() + "?mode=ro", uri=True)
        cls.db.row_factory = sqlite3.Row
        cls.db.execute("PRAGMA query_only=ON")
        cls.catalog = json.loads((WORKSPACE / "flavor-studio/data/catalog.json").read_bytes())
        cls.evidence = json.loads((WORKSPACE / "flavor-studio/data/evidence-full.json").read_bytes())
        cls.processing = json.loads((WORKSPACE / "flavor-studio/data/processing.json").read_bytes())
        cls.asset_manifest = json.loads((WORKSPACE / "flavor-studio/assets/manifest.json").read_bytes())
        cls.records = {r["id"]: (i["id"], r) for i in cls.catalog["ingredients"] for r in i["records"]}

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def rows(self, table):
        return list(self.db.execute("SELECT * FROM " + table))

    def test_01_integrity_and_references(self):
        self.assertEqual(self.db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(list(self.db.execute("PRAGMA foreign_key_check")), [])
        self.assertEqual(self.db.execute("PRAGMA user_version").fetchone()[0], 1)

    def test_02_source_snapshots_exact_bytes(self):
        rows = self.rows("source_snapshots")
        self.assertGreaterEqual(len(rows), 19)
        paths = {r["relative_path"] for r in rows}
        for required in ["flavor-studio/data/catalog.json", "flavor-studio/data/evidence-full.json",
                         "flavor-studio/data/processing.json", "tmp/pdfs/flavor_source/pages.json"]:
            self.assertIn(required, paths)
        for row in rows:
            original = (WORKSPACE / row["relative_path"]).read_bytes()
            self.assertEqual(row["content_json"].encode("utf-8"), original, row["relative_path"])
            self.assertEqual(row["sha256"], digest(original), row["relative_path"])
            json.loads(row["content_json"])

    def test_03_all_ingredient_identities_and_original_fields(self):
        original = {r["id"]: r for r in self.catalog["ingredients"]}
        stored = {r["id"]: r for r in self.rows("ingredients")}
        self.assertEqual(set(stored), set(original))
        for key, source in original.items():
            row = stored[key]
            self.assertEqual(unpack(row["raw_json"]), source, key)
            self.assertEqual(row["original_name"], source["name"])
            self.assertEqual(row["display_name"], source["displayName"])
            self.assertEqual(bool(row["recommendation_eligible"]), source["recommendationEligible"])
            self.assertEqual(bool(row["name_needs_review"]), source["nameNeedsReview"])
            self.assertEqual(bool(row["example_only"]), source["exampleOnly"])
        # Same display names must retain independent stable identities.
        self.assertEqual(Counter(r["display_name"] for r in stored.values()),
                         Counter(r["displayName"] for r in original.values()))
        aliases = {(r["ingredient_id"], r["alias"]) for r in self.rows("ingredient_aliases")}
        self.assertTrue({(i["id"], a) for i in original.values() for a in i["aliases"]} <= aliases)

    def test_04_all_source_tables_and_coordinates(self):
        original = {r["id"]: r for r in self.catalog["tables"]}
        raw = {r["table_id"]: r for r in self.evidence["dotSource"]["tables"]}
        stored = self.rows("source_tables")
        self.assertEqual(len(stored), len(original))
        for row in stored:
            self.assertEqual(unpack(row["raw_json"]), original[row["id"]])
            self.assertEqual(unpack(row["raw_source_json"]), raw[row["id"]])
            self.assertEqual(row["book_page"], original[row["id"]]["bookPage"])

    def test_05_all_dot_records_and_every_cell(self):
        raw = {r["row_id"]: r for r in self.evidence["dotSource"]["rows"]}
        stored = {r["id"]: r for r in self.rows("dot_records")}
        self.assertEqual(set(stored), set(self.records))
        self.assertEqual(set(stored), set(raw))
        for key, (ingredient_id, source) in self.records.items():
            row = stored[key]
            self.assertEqual(row["ingredient_id"], ingredient_id)
            self.assertEqual(unpack(row["raw_json"]), source, key)
            self.assertEqual(unpack(row["raw_source_json"]), raw[key], key)
            self.assertEqual(bool(row["is_example"]), source["isExample"])
            self.assertEqual(bool(row["identity_eligible"]), source["identityEligible"])
        cells = self.rows("dot_values")
        self.assertEqual(len(cells), 14 * len(self.records))
        for cell in cells:
            source = self.records[cell["record_id"]][1]
            index = cell["category_index"]
            self.assertEqual(cell["presence"], source["presence"][index], (cell["record_id"], index))
            self.assertEqual(cell["shared_with_main"], source["sharedWithMain"][index], (cell["record_id"], index))

    def test_06_pairings_keep_every_source_and_teaching_rows(self):
        original = {r["id"]: r for r in self.catalog["edges"]}
        stored = {r["id"]: r for r in self.rows("pairings")}
        paired = {key: value for key, value in self.records.items() if value[1]["role"] != "main"}
        self.assertEqual(set(stored), set(paired))
        for key, source in original.items():
            self.assertEqual(unpack(stored[key]["raw_json"]), source, key)
        for key, row in stored.items():
            ingredient_id, source = paired[key]
            self.assertEqual(row["paired_record_id"], key)
            self.assertEqual(row["paired_ingredient_id"], ingredient_id)
            self.assertEqual(row["main_ingredient_id"], source["mainIngredientId"])
            self.assertEqual(row["table_id"], source["tableId"])
            self.assertEqual(bool(row["is_example"]), source["isExample"])
            if key not in original:
                self.assertTrue(row["is_example"])
                self.assertFalse(row["recommendation_eligible"])
                self.assertEqual(unpack(row["raw_json"])["originalPairingRecord"], source)
        self.assertEqual(len(stored) - len(original), 10)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM v_recommendable_pairings WHERE is_example=1 OR recommendation_eligible=0").fetchone()[0], 0)

    def test_07_attribute_evidence_links_and_descriptors(self):
        original = {r["id"]: r for r in self.evidence["records"]}
        self.assertEqual(len(self.rows("attribute_evidence")), len(original))
        for row in self.rows("attribute_evidence"):
            self.assertEqual(unpack(row["raw_json"]), original[row["id"]])
            self.assertEqual(unpack(row["original_json"]), original[row["id"]]["original"])
        links = self.rows("evidence_links")
        self.assertEqual(len(links), sum(len(r["links"]) for r in original.values()))
        for row in links:
            src = original[row["evidence_id"]]["links"][row["ordinal"]]
            self.assertEqual(unpack(row["raw_json"]), src)
            self.assertEqual(row["ingredient_id"], src["ingredientId"])
            self.assertEqual(row["link_kind"], src["kind"])
        descriptors = {r["descriptor_id"]: r for r in self.evidence["facets"]["descriptors"]}
        self.assertEqual({r["id"]: unpack(r["raw_json"]) for r in self.rows("descriptors")}, descriptors)
        mentions = self.rows("descriptor_mentions")
        self.assertEqual(len(mentions), sum(len(r["descriptorMentions"]) for r in original.values()))
        for row in mentions:
            self.assertEqual(unpack(row["raw_json"]), original[row["evidence_id"]]["descriptorMentions"][row["ordinal"]])
            self.assertEqual(row["interpretation"], "text_mention_only")

    def test_08_numbers_keep_units_bounds_denominators(self):
        stored = sorted(self.rows("reported_numbers"), key=lambda r: r["id"])
        self.assertEqual([unpack(r["raw_json"]) for r in stored], self.evidence["numbers"])
        for row, source in zip(stored, self.evidence["numbers"]):
            for column, key in [("value_json", "value"), ("minimum_json", "minimum"), ("maximum_json", "maximum")]:
                self.assertEqual(unpack(row[column]), source.get(key))
            self.assertEqual(row["unit"], source.get("unit"))
            self.assertEqual(row["operator"], source.get("operator"))
            self.assertEqual(row["denominator"], source.get("denominator"))

    def test_09_processing_records_conditions_sources_and_audit(self):
        original = {r["id"]: r for r in self.processing["records"]}
        stored = {r["id"]: r for r in self.rows("processing_records")}
        self.assertEqual(set(stored), set(original))
        for key, source in original.items():
            row = stored[key]
            self.assertEqual(unpack(row["raw_json"]), source, key)
            self.assertEqual(unpack(row["source_json"]), source["source"])
            self.assertEqual(unpack(row["original_json"]), source["original"])
            for column, field in [("record_kind", "recordKind"), ("before_state", "before"),
                                  ("after_state", "after"), ("conditions", "conditions"),
                                  ("mechanism", "mechanism"), ("limitations", "limitations")]:
                self.assertEqual(row[column], source[field], (key, field))
        self.assertEqual({r["evidence_id"]: unpack(r["raw_json"]) for r in self.rows("processing_audit")},
                         {r["evidenceId"]: r for r in self.processing["audit253"]})

    def test_10_processing_all_associations_effects_and_values(self):
        original = {r["id"]: r for r in self.processing["records"]}
        for table, field in [("processing_effects", "normalizedEffects"), ("processing_links", "ingredientLinks"),
                             ("processing_numbers", "reportedValues")]:
            rows = self.rows(table)
            self.assertEqual(len(rows), sum(len(r[field]) for r in original.values()), table)
            for row in rows:
                source = original[row["processing_id"]][field][row["ordinal"]]
                self.assertEqual(unpack(row["raw_json"]), source, (table, row["processing_id"]))
                if table == "processing_effects":
                    for column, key in [("domain", "domain"), ("direction", "direction"), ("group_key", "groupKey")]:
                        self.assertEqual(row[column], source[key])
                if table == "processing_links":
                    self.assertEqual(row["link_kind"], source["kind"])
        for table, field, key_column in [("processing_methods", "methodIndexEntries", "method_key"),
                                          ("processing_ingredient_names", "ingredientIndexEntries", "name_key")]:
            rows = self.rows(table)
            self.assertEqual(len(rows), sum(len(r[field]) for r in original.values()))
            for row in rows:
                source = original[row["processing_id"]][field][row["ordinal"]]
                self.assertEqual((row[key_column], row["label"], row["original_label"]),
                                 (source["key"], source["label"], source["originalLabel"]))
        for table, key, metric in [("processing_methods", "method_key", "methodGroups"),
                                    ("processing_effects", "group_key", "effectGroups"),
                                    ("processing_ingredient_names", "name_key", "ingredientGroups")]:
            self.assertEqual(len({r[key] for r in self.rows(table)}), self.processing["metrics"][metric])

    def test_11_profile_every_category_unknown_and_conflict(self):
        stored = {(r["ingredient_id"], r["category_index"]): r for r in self.rows("v_ingredient_aroma_profile")}
        expected = 0
        for ingredient in self.catalog["ingredients"]:
            records = [r for r in ingredient["records"] if not r["isExample"]]
            for index in range(14):
                counts = Counter(r["presence"][index] for r in records)
                status = ("conflict" if counts[1] and counts[0] else "unknown" if counts[None] or not records
                          else "marked" if counts[1] else "unmarked")
                row = stored[(ingredient["id"], index)]
                self.assertEqual((row["marked_count"], row["unmarked_count"], row["unknown_count"], row["record_count"], row["status"], bool(row["has_unknown"])),
                                 (counts[1], counts[0], counts[None], len(records), status, bool(counts[None])),
                                 (ingredient["id"], index))
                expected += 1
        self.assertEqual(len(stored), expected)
        self.assertEqual(sum(r["status"] == "conflict" and r["has_unknown"] for r in stored.values()), 3)

    def test_12_all_assets_exact_bytes_and_metadata(self):
        original = {r["id"]: r for r in self.asset_manifest["assets"]}
        stored = self.rows("assets")
        self.assertEqual(len(stored), len(original) + 1)
        for row in stored:
            content = (WORKSPACE / row["relative_path"]).read_bytes()
            self.assertEqual(row["content"], content, row["id"])
            self.assertEqual(row["sha256"], digest(content))
            self.assertEqual(row["byte_size"], len(content))
            if row["id"] in original:
                self.assertEqual(unpack(row["raw_json"]), original[row["id"]])
                self.assertEqual(row["ingredient_id"], row["id"])
                self.assertEqual(row["mime_type"], "image/svg+xml")
            else:
                self.assertEqual(row["id"], "hero-strawberry")
                self.assertIsNone(row["ingredient_id"])
                self.assertEqual(row["mime_type"], "image/png")

    def test_13_all_book_pages_and_external_pdf_hash(self):
        pages = json.loads((WORKSPACE / "tmp/pdfs/flavor_source/pages.json").read_bytes())
        rows = sorted(self.rows("book_pages"), key=lambda r: r["pdf_page"])
        self.assertEqual([unpack(r["raw_json"]) for r in rows], pages)
        for row, source in zip(rows, pages):
            for field in ["pdf_page", "text", "width", "height"]:
                self.assertEqual(row[field], source[field])
        source = self.db.execute("SELECT * FROM sources WHERE relative_path LIKE '%.pdf'").fetchall()
        self.assertEqual(len({r["relative_path"] for r in source}), 1)
        source_hash = digest((WORKSPACE / source[0]["relative_path"]).read_bytes())
        for row in source:
            self.assertEqual(row["sha256"], source_hash)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=WORKSPACE)
    parser.add_argument("--db", type=Path, default=DATABASE)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    WORKSPACE, DATABASE = args.workspace.resolve(), args.db.resolve()
    before = digest(DATABASE.read_bytes())
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SourceFidelity))
    after = digest(DATABASE.read_bytes())
    report = {"suite": "independent source-to-database fidelity", "tests_run": result.testsRun,
              "failures": len(result.failures), "errors": len(result.errors),
              "database_sha256": after, "database_unchanged": before == after,
              "success": result.wasSuccessful() and before == after,
              "checks": [name for name in unittest.defaultTestLoader.getTestCaseNames(SourceFidelity)],
              "scope": "All source records/cells/assets, source snapshots, conditions, link kinds, profiles and references. Fidelity is not scientific validation."}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))
    sys.exit(0 if report["success"] else 1)
