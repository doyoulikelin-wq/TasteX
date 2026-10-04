#!/usr/bin/env python3
"""Compare the public query API to source evidence, including cross-filter semantics."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
WORKSPACE = HERE.parent
DATABASE = HERE / "flavor.sqlite"
sys.path.insert(0, str(HERE))
from flavor_db import FlavorDB


class QuerySemantics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = FlavorDB(DATABASE)
        cls.catalog = json.loads((WORKSPACE / "flavor-studio/data/catalog.json").read_bytes())
        cls.processing = json.loads((WORKSPACE / "flavor-studio/data/processing.json").read_bytes())["records"]
        cls.evidence = json.loads((WORKSPACE / "flavor-studio/data/evidence-full.json").read_bytes())["records"]

    @classmethod
    def tearDownClass(cls):
        cls.api.close()

    def ids(self, result):
        self.assertFalse(result["has_more"])
        self.assertEqual(result["total"], len(result["items"]))
        return {r["id"] for r in result["items"]}

    def test_01_every_ingredient_profile_preserves_all_variants(self):
        for ingredient in self.catalog["ingredients"]:
            source = [r for r in ingredient["records"] if not r["isExample"]]
            profile = self.api.profile(ingredient["id"])
            self.assertEqual(profile["record_count"], len(source))
            expected = defaultdict(set)
            for row in source:
                expected[tuple(row["presence"])].add(row["id"])
            self.assertEqual({tuple(v["presence"]): set(v["source_record_ids"]) for v in profile["variants"]}, dict(expected), ingredient["id"])
            self.assertEqual(len(profile["categories"]), 14)
            for index, category in enumerate(profile["categories"]):
                for value, field in [(1, "marked_source_ids"), (0, "unmarked_source_ids"), (None, "unknown_source_ids")]:
                    self.assertEqual(set(category[field]), {r["id"] for r in source if r["presence"][index] == value})
                if not source:
                    self.assertEqual(category["status"], "unknown")
                    self.assertEqual(category["record_count"], 0)
            if ingredient["exampleOnly"]:
                with_examples = self.api.profile(ingredient["id"], include_examples=True)
                self.assertEqual(with_examples["record_count"], len(ingredient["records"]))
            self.assertEqual(self.api.ingredient(ingredient["id"])["ingredient"], ingredient)

    def test_02_full_evidence_and_processing_are_unchanged(self):
        for row in self.evidence:
            self.assertEqual(self.api.evidence(row["id"]), row)
        for row in self.processing:
            self.assertEqual(self.api.processing_record(row["id"]), row)
        all_rows = self.api.processing(limit=1000)
        self.assertEqual({r["id"]: r for r in all_rows["items"]}, {r["id"]: r for r in self.processing})

    def test_03_every_effect_group_jointly_matches_one_effect(self):
        keys = {(e["domain"], e["label"], e["direction"]) for r in self.processing for e in r["normalizedEffects"]}
        for domain, label, direction in keys:
            expected = {r["id"] for r in self.processing if any(
                (e["domain"], e["label"], e["direction"]) == (domain, label, direction) for e in r["normalizedEffects"])}
            actual = self.ids(self.api.processing(domain=domain, effect=label, direction=direction, limit=1000))
            self.assertEqual(actual, expected, (domain, label, direction))
        # Cross all dimensions/directions, including combinations absent in data.
        for domain in {k[0] for k in keys}:
            for direction in {k[2] for k in keys}:
                expected = {r["id"] for r in self.processing if any(e["domain"] == domain and e["direction"] == direction for e in r["normalizedEffects"])}
                self.assertEqual(self.ids(self.api.processing(domain=domain, direction=direction, limit=1000)), expected)

    def test_04_every_method_and_ingredient_name_group(self):
        for field, option in [("methodIndexEntries", "method"), ("ingredientIndexEntries", "ingredient_name")]:
            for key in {e["key"] for r in self.processing for e in r[field]}:
                expected = {r["id"] for r in self.processing if any(e["key"] == key or e["label"] == key for e in r[field])}
                self.assertEqual(self.ids(self.api.processing(**{option: key}, limit=1000)), expected, (option, key))

    def test_05_all_stable_identity_link_kinds_remain_separate(self):
        ingredient_ids = {e["ingredientId"] for r in self.processing for e in r["ingredientLinks"]}
        kinds = {e["kind"] for r in self.processing for e in r["ingredientLinks"]}
        for ingredient_id in ingredient_ids:
            for kind in kinds:
                expected = {r["id"] for r in self.processing if any(e["ingredientId"] == ingredient_id and e["kind"] == kind for e in r["ingredientLinks"])}
                result = self.api.processing(ingredient_id=ingredient_id, link_kind=kind, limit=1000)
                self.assertEqual(self.ids(result), expected)
                for record_id, links in result["matched_ingredient_links"].items():
                    self.assertTrue(links)
                    self.assertTrue(all(e["ingredientId"] == ingredient_id and e["kind"] == kind for e in links))

    def test_06_three_indexes_count_distinct_records_within_filtered_population(self):
        for source_kind in [None, "research", "book"]:
            population = [r for r in self.processing if source_kind is None or r["source"]["kind"] == source_kind]
            for by, field, key_field in [("method", "methodIndexEntries", "key"), ("effect", "normalizedEffects", "groupKey"), ("ingredient", "ingredientIndexEntries", "key")]:
                groups = defaultdict(set)
                association_counts = Counter()
                for record in population:
                    for entry in record[field]:
                        groups[entry[key_field]].add(record["id"])
                        association_counts[entry[key_field]] += 1
                result = self.api.indexes(by=by, source=source_kind, limit=1000)
                self.assertFalse(result["has_more"])
                self.assertEqual(result["total"], len(groups))
                self.assertEqual(set(result["population_record_ids"]), {r["id"] for r in population})
                self.assertEqual({g["key"]: set(g["record_ids"]) for g in result["items"]}, dict(groups))
                for group in result["items"]:
                    self.assertEqual(group["record_count"], len(groups[group["key"]]))
                    self.assertEqual(group["association_count"], association_counts[group["key"]])

    def test_07_same_display_names_never_merge_in_search(self):
        names = Counter(i["displayName"] for i in self.catalog["ingredients"])
        for name, count in names.items():
            if count > 1:
                expected = {i["id"] for i in self.catalog["ingredients"] if i["displayName"] == name}
                actual = self.ids(self.api.search(name, kind="ingredient", limit=1000))
                self.assertTrue(expected <= actual, name)

    def test_08_portable_database_and_module_work_without_sources(self):
        with tempfile.TemporaryDirectory(prefix="flavor-portability-") as name:
            root = Path(name)
            package = root / "moved folder"
            package.mkdir()
            copied = package / "flavor.sqlite"
            shutil.copy2(DATABASE, copied)
            shutil.copy2(HERE / "flavor_db.py", package / "flavor_db.py")
            before = hashlib.sha256(copied.read_bytes()).hexdigest()

            def run(*args):
                result = subprocess.run([sys.executable, str(package / "flavor_db.py"), "--compact", *args], cwd=root, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                return json.loads(result.stdout)

            self.assertEqual(run("stats")["counts"]["ingredients"], len(self.catalog["ingredients"]))
            self.assertTrue(run("search", "大蒜", "--kind", "ingredient")["items"])
            self.assertEqual(run("page", "38")["pdf_page"], 38)
            self.assertEqual(run("indexes", "--by", "effect", "--limit", "1000")["total"], 293)
            target = root / "garlic.svg"
            exported = run("asset", "ing-2053d8521c93", "--out", str(target))
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), exported["sha256"])
            self.assertEqual(hashlib.sha256(copied.read_bytes()).hexdigest(), before)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=WORKSPACE)
    parser.add_argument("--db", type=Path, default=DATABASE)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    WORKSPACE, DATABASE = args.workspace.resolve(), args.db.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(QuerySemantics))
    report = {"suite": "public API source semantics and portability", "tests_run": result.testsRun,
              "failures": len(result.failures), "errors": len(result.errors), "success": result.wasSuccessful(),
              "checks": unittest.defaultTestLoader.getTestCaseNames(QuerySemantics),
              "database_sha256": hashlib.sha256(DATABASE.read_bytes()).hexdigest()}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))
    sys.exit(0 if report["success"] else 1)
