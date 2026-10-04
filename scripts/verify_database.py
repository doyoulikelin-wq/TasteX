#!/usr/bin/env python3
"""Self-contained verification of the database and its embedded source snapshots.

No original PDF, extracted-image directory or old workspace is required. Reuses
the existing exhaustive mapping tests, replacing external-file checks with
embedded-snapshot checks. Internal fidelity is not scientific validation.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import sqlite3
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "flavor-database" / "flavor.sqlite"


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_database(db_path: str | Path = DEFAULT_DB, manifest_path: str | Path | None = None) -> dict:
    db_path = Path(db_path).resolve()
    manifest_path = Path(manifest_path).resolve() if manifest_path else db_path.with_name("manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    before = sha_file(db_path)
    spec = importlib.util.spec_from_file_location("tastex_legacy_source_fidelity", ROOT / "flavor-database" / "tests" / "test_database.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot import the bundled source mapping checks")
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)

    class EmbeddedSourceFidelity(legacy.SourceFidelity):
        @classmethod
        def setUpClass(cls):
            cls.db = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
            cls.addClassCleanup(cls.db.close)
            cls.db.row_factory = sqlite3.Row
            cls.db.execute("PRAGMA query_only=ON")
            cls.snapshots = {r["id"]: r for r in cls.db.execute("SELECT * FROM source_snapshots ORDER BY id")}
            cls.catalog = json.loads(cls.snapshots["catalog"]["content_json"])
            cls.evidence = json.loads(cls.snapshots["evidence-full"]["content_json"])
            cls.processing = json.loads(cls.snapshots["processing"]["content_json"])
            cls.asset_manifest = json.loads(cls.snapshots["asset-manifest"]["content_json"])
            cls.records = {r["id"]: (i["id"], r) for i in cls.catalog["ingredients"] for r in i["records"]}

        def test_02_source_snapshots_exact_bytes(self):
            expected = {row["id"]: row for row in manifest["source_snapshots"]}
            self.assertEqual(set(self.snapshots), set(expected))
            self.assertEqual(len(self.snapshots), 19)
            for key, row in self.snapshots.items():
                content = row["content_json"].encode("utf-8")
                self.assertEqual(hashlib.sha256(content).hexdigest(), row["sha256"], key)
                self.assertEqual({k: row[k] for k in ("id", "relative_path", "sha256")}, expected[key])
                json.loads(content)
            self.assertEqual(json.loads(self.snapshots["attribute-source"]["content_json"]), self.evidence["source"])
            self.assertEqual(json.loads(self.snapshots["dot-source"]["content_json"]), self.evidence["dotSource"])

        def test_12_all_assets_exact_bytes_and_metadata(self):
            expected = {a["id"]: a for a in self.asset_manifest["assets"]}
            assets = self.rows("assets")
            self.assertEqual(len(assets), len(expected) + 1)
            for row in assets:
                self.assertEqual(hashlib.sha256(row["content"]).hexdigest(), row["sha256"], row["id"])
                self.assertEqual(len(row["content"]), row["byte_size"])
                if row["id"] in expected:
                    source = expected[row["id"]]
                    self.assertEqual(json.loads(row["raw_json"]), source)
                    self.assertEqual(row["sha256"], source["sha256"])
                    self.assertEqual(row["byte_size"], source["bytes"])
                    self.assertEqual(row["relative_path"], "flavor-studio/" + source["path"])
                    self.assertEqual(row["ingredient_id"], row["id"])
                    self.assertEqual(row["mime_type"], "image/svg+xml")
                else:
                    self.assertEqual(row["id"], "hero-strawberry")
                    self.assertEqual(row["mime_type"], "image/png")
                    self.assertIsNone(row["ingredient_id"])
                    self.assertTrue(row["content"].startswith(b"\x89PNG\r\n\x1a\n"))
                    self.assertEqual(json.loads(row["raw_json"]), json.loads(self.snapshots["file:flavor-studio/assets/generated/generation-record.json"]["content_json"]))

        def test_13_all_book_pages_and_external_pdf_hash(self):
            pages = json.loads(self.snapshots["book-pages"]["content_json"])
            rows = sorted(self.rows("book_pages"), key=lambda r: r["pdf_page"])
            self.assertEqual([json.loads(r["raw_json"]) for r in rows], pages)
            for row, source in zip(rows, pages):
                for field in ("pdf_page", "text", "width", "height"):
                    self.assertEqual(row[field], source[field])
            # This validates stored references only; it does not re-hash a PDF.
            self.assertFalse(manifest["original_pdf"]["embedded"])
            sources = self.db.execute("SELECT * FROM sources WHERE relative_path LIKE '%.pdf'").fetchall()
            self.assertGreater(len(sources), 0)
            for row in sources:
                self.assertEqual(row["sha256"], manifest["original_pdf"]["sha256"])
                self.assertEqual(row["relative_path"], manifest["original_pdf"]["relative_path"])

        def test_14_manifest_sha_counts_and_metrics(self):
            self.assertEqual(before, manifest["database"]["sha256"])
            self.assertEqual(db_path.stat().st_size, manifest["database"]["byte_size"])
            for item in ("schema", "builder"):
                path = Path(manifest[item]["path"])
                self.assertFalse(path.is_absolute())
                self.assertNotIn("..", path.parts)
                self.assertEqual(sha_file(manifest_path.parent / path), manifest[item]["sha256"])
            tables = [r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'search_fts%' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            self.assertEqual(set(tables), set(manifest["counts"]))
            for table in tables:
                self.assertTrue(re.fullmatch(r"[a-z_]+", table))
                self.assertEqual(self.db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0], manifest["counts"][table], table)
            queries = {
                "recommendation_ingredients": "SELECT COUNT(*) FROM ingredients WHERE recommendation_eligible=1",
                "recommendation_pairings": "SELECT COUNT(*) FROM v_recommendable_pairings",
                "restored_pairings": "SELECT COUNT(*) FROM pairings WHERE provenance_kind='restored_original_pairing_row'",
                "unknown_presence_cells": "SELECT COUNT(*) FROM dot_values WHERE presence IS NULL",
                "teaching_rows": "SELECT COUNT(*) FROM dot_records WHERE is_example=1",
                "processing_method_groups": "SELECT COUNT(DISTINCT method_key) FROM processing_methods",
                "processing_effect_groups": "SELECT COUNT(DISTINCT group_key) FROM processing_effects",
                "processing_ingredient_groups": "SELECT COUNT(DISTINCT name_key) FROM processing_ingredient_names",
                "research_studies": "SELECT COUNT(*) FROM sources WHERE kind='research'"}
            self.assertEqual(set(queries), set(manifest["metrics"]))
            for key, query in queries.items():
                self.assertEqual(self.db.execute(query).fetchone()[0], manifest["metrics"][key], key)

        def test_15_search_documents_are_complete_source_text(self):
            expected = {("ingredient", r["id"]): (r["displayName"], r["searchText"]) for r in self.catalog["ingredients"]}
            expected.update({("evidence", r["id"]): (r.get("displayIngredient", r["id"]), r["searchText"]) for r in self.evidence["records"]})
            expected.update({("processing", r["id"]): (r["title"], r["searchText"]) for r in self.processing["records"]})
            expected.update({("book_page", str(r["pdf_page"])): (f"PDF 第 {r['pdf_page']} 页", r["text"]) for r in json.loads(self.snapshots["book-pages"]["content_json"])})
            actual = {(r["kind"], r["id"]): (r["title"], r["text"]) for r in self.rows("search_documents")}
            self.assertEqual(actual, expected)

        def test_16_auxiliary_mapping_and_source_references(self):
            evidence = {r["id"]: r for r in self.evidence["records"]}
            self.assertEqual({(r["evidence_id"], r["domain"]) for r in self.rows("evidence_domains")},
                             {(key, domain) for key, record in evidence.items() for domain in record["domains"]})
            self.assertEqual({(r["processing_id"], r["evidence_id"]) for r in self.rows("processing_evidence")},
                             {(r["id"], eid) for r in self.processing["records"] for eid in r["source"].get("evidenceIds", [])})
            stored = {r["id"]: r for r in self.rows("sources")}
            for source in self.processing["references"]:
                self.assertEqual(json.loads(stored[source["id"]]["raw_json"]), source)
            categories = sorted(self.rows("aroma_categories"), key=lambda r: r["category_index"])
            self.assertEqual([r["source_name"] for r in categories], self.catalog["categories"])
            self.assertEqual([r["display_name"] for r in categories], self.catalog["categoryDisplayNames"])
            for row in self.rows("processing_numbers"):
                source = json.loads(row["raw_json"])
                for column, field in (("value_json", "value"), ("minimum_json", "minimum"), ("maximum_json", "maximum")):
                    self.assertEqual(json.loads(row[column]) if row[column] is not None else None, source.get(field))
                for field in ("unit", "operator", "denominator"):
                    self.assertEqual(row[field], source.get(field))

    stream = io.StringIO()
    names = unittest.defaultTestLoader.getTestCaseNames(EmbeddedSourceFidelity)
    outcome = unittest.TextTestRunner(stream=stream, verbosity=0).run(unittest.defaultTestLoader.loadTestsFromTestCase(EmbeddedSourceFidelity))
    after = sha_file(db_path)
    failures = [{"test": case.id().split(".")[-1], "detail": detail[-4000:]} for case, detail in outcome.failures + outcome.errors]
    return {"success": outcome.wasSuccessful() and before == after, "tests_run": outcome.testsRun,
            "checks": names, "failures": failures, "database_sha256": after, "database_unchanged": before == after,
            "source_snapshot_count": len(manifest["source_snapshots"]), "original_pdf_rechecked": False,
            "scope": "Database and embedded source copies agree at hash, record, cell, mapping and asset levels. This does not independently validate extraction, source claims, diagram interpretation, or sensory outcomes."}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    try:
        report = verify_database(args.db, args.manifest)
        content = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            with args.report.open("x", encoding="utf-8") as handle:
                handle.write(content)
        print(content, end="")
        return 0 if report["success"] else 1
    except (OSError, ValueError, sqlite3.Error) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
