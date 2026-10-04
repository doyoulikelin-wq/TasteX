"""Portable restoration and independent embedded-source fidelity checks."""
from __future__ import annotations

import hashlib
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from scripts.restore_sources import restore_sources, safe_destination
from scripts.verify_database import verify_database

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "flavor-database" / "flavor.sqlite"
MANIFEST = DB.with_name("manifest.json")


class SourcePortabilityTests(unittest.TestCase):
    def test_self_contained_fidelity(self):
        report = verify_database(DB, MANIFEST)
        self.assertTrue(report["success"], report["failures"])
        self.assertEqual(report["tests_run"], 16)
        self.assertEqual(report["source_snapshot_count"], 19)
        self.assertTrue(report["database_unchanged"])
        self.assertFalse(report["original_pdf_rechecked"])

    def test_restore_all_snapshots_exact_bytes_without_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "restored"
            report = restore_sources(DB, target)
            self.assertEqual(report["source_snapshots"], 19)
            self.assertEqual(report["assets"], 0)
            with closing(sqlite3.connect(DB.as_uri() + "?mode=ro", uri=True)) as db:
                for path, digest, content in db.execute("SELECT relative_path,sha256,content_json FROM source_snapshots"):
                    data = (target / path).read_bytes()
                    self.assertEqual(data, content.encode("utf-8"))
                    self.assertEqual(hashlib.sha256(data).hexdigest(), digest)
            self.assertEqual(len(list(target.rglob("*.json"))), 19)
            self.assertEqual(list(target.rglob("*.pdf")), [])

    def test_existing_file_rejected_before_any_other_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            occupied = target / "tmp/pdfs/flavor_source/pages.json"
            occupied.parent.mkdir(parents=True)
            occupied.write_bytes(b"keep existing")
            with self.assertRaises(FileExistsError):
                restore_sources(DB, target)
            self.assertEqual(occupied.read_bytes(), b"keep existing")
            self.assertEqual([p for p in target.rglob("*") if p.is_file()], [occupied])

    def test_optional_assets_are_exact_and_dry_run_does_not_create_target(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "restore"
            preview = restore_sources(DB, target, include_assets=True, dry_run=True)
            self.assertEqual(preview["assets"], 1475)
            self.assertFalse(target.exists())
            report = restore_sources(DB, target, include_assets=True)
            self.assertEqual(report["assets"], 1475)
            with closing(sqlite3.connect(DB.as_uri() + "?mode=ro", uri=True)) as db:
                for relative, digest, content in db.execute("SELECT relative_path,sha256,content FROM assets"):
                    data = (target / relative).read_bytes()
                    self.assertEqual(data, content)
                    self.assertEqual(hashlib.sha256(data).hexdigest(), digest)

    def test_unsafe_paths_and_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target"
            target.mkdir()
            for path in ["../escape.json", "/tmp/escape.json", "C:/escape.json", "a/../escape.json", "a\\escape.json", "a//b.json", "./b.json"]:
                with self.subTest(path=path), self.assertRaises(ValueError):
                    safe_destination(target, path)
            outside = Path(directory) / "outside"
            outside.mkdir()
            (target / "link").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                safe_destination(target, "link/escape.json")
            self.assertEqual(list(outside.iterdir()), [])

    def test_corrupt_embedded_snapshot_rejected_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "bad.sqlite"
            with closing(sqlite3.connect(db_path)) as db, db:
                db.execute("CREATE TABLE source_snapshots(id,relative_path,sha256,content_json)")
                db.execute("INSERT INTO source_snapshots VALUES(?,?,?,?)", ("bad", "source.json", "0" * 64, "{}"))
            target = Path(directory) / "restored"
            with self.assertRaises(ValueError):
                restore_sources(db_path, target)
            self.assertFalse(target.exists())

    def test_changed_cell_is_detected_even_if_manifest_database_hash_updated(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            copied = target / "flavor.sqlite"
            shutil.copyfile(DB, copied)
            for name in ("schema.sql", "build_database.py"):
                shutil.copyfile(DB.parent / name, target / name)
            with closing(sqlite3.connect(copied)) as db, db:
                row_id, category, value = db.execute("SELECT record_id,category_index,presence FROM dot_values WHERE presence IS NOT NULL LIMIT 1").fetchone()
                db.execute("UPDATE dot_values SET presence=? WHERE record_id=? AND category_index=?", (1 - value, row_id, category))
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
            manifest["database"]["sha256"] = hashlib.sha256(copied.read_bytes()).hexdigest()
            (target / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            report = verify_database(copied, target / "manifest.json")
            self.assertFalse(report["success"])
            failed = {f["test"] for f in report["failures"]}
            self.assertIn("test_05_all_dot_records_and_every_cell", failed)
            self.assertTrue(report["database_unchanged"])


if __name__ == "__main__":
    unittest.main()
