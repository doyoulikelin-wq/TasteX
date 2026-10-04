"""Regression checks for the actual corpus and retrieval completeness."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tastex.retrieval import FlavorDB, _all_pages, collect_evidence, expand_queries


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "flavor-database" / "flavor.sqlite"
ALIASES = ROOT / "configs" / "search_aliases.json"
KIWI = "ing-f9bfb14ffe98"
JUICE = "ing-6605f67426a6"
BERRY = "ing-c1ff63cfd9ea"
CHILI = "ing-e4fa8473e829"


def ingredient(key, query, reference_id=None, state="unconfirmed", relation="unresolved"):
    return {"key": key, "query": query, "reference_id": reference_id,
            "requested_state": state, "identity_relation": relation}


class RetrievalCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.brief = {"ingredients": [
            ingredient("kiwi", "猕猴桃", KIWI, "果肉冻干粉", "different_state"),
            ingredient("beef", "牛肉", "ing-70099ea01925", "可即食瘦牛肉干", "different_state"),
            ingredient("chili", "红辣椒粉", CHILI, "低辣可即食粉", "unresolved"),
        ]}
        cls.before = hashlib.sha256(DB.read_bytes()).hexdigest()
        cls.bundle = collect_evidence(cls.brief, DB, ALIASES)
        cls.by_key = {i["key"]: i for i in cls.bundle["ingredients"]}

    def test_reviewed_kiwi_alias_rescues_zero_hit_without_identity_merge(self):
        item = self.by_key["kiwi"]
        self.assertEqual(set(item["candidate_ids"]), {KIWI, JUICE})
        self.assertEqual(item["reference_id"], KIWI)
        self.assertEqual(item["identity_relation"], "different_state")
        self.assertNotIn(BERRY, item["candidate_ids"])
        self.assertIn("奇異果", item["expanded_queries"])
        zero = [q for q in self.bundle["queries"] if q["ingredient_key"] == "kiwi"
                and q["operation"] == "search_ingredient" and q["parameters"]["query"] == "猕猴桃"]
        self.assertEqual(len(zero), 1)
        self.assertTrue(zero[0]["zero_hits"])

    def test_p43_processing_context_survives_structured_zero(self):
        item = self.by_key["kiwi"]
        self.assertEqual(item["structured_processing_records"], [])
        page = next(p for p in item["page_hits"] if p["pdf_page"] == 43)
        with FlavorDB(DB) as db:
            self.assertEqual(page["full_text"], db.page(43)["page"]["text"])
        self.assertIn("結締組織", page["full_text"])
        self.assertIn("奇異莓", page["full_text"])
        self.assertIsNone(page["book_page"])
        self.assertEqual(page["interpretation"], "page_context_only_requires_section_and_identity_review")
        gaps = [g for g in self.bundle["gaps"] if g.get("ingredient_key") == "kiwi"]
        self.assertTrue(any(g["kind"] == "no_structured_processing" and g["page_hit_count"] == 29 for g in gaps))

    def test_pages_are_always_searched_even_with_processing_results(self):
        self.assertGreater(len(self.by_key["beef"]["structured_processing_records"]), 0)
        self.assertGreater(len(self.by_key["beef"]["page_hits"]), 100)
        receipt = next(q for q in self.bundle["queries"] if q["ingredient_key"] == "beef"
                       and q["operation"] == "search_page" and q["parameters"]["query"] == "牛肉")
        self.assertGreater(len(receipt["pagination"]), 1)
        self.assertEqual(receipt["returned"], receipt["total"])
        self.assertTrue(receipt["complete"])

    def test_p44_wagyu_direct_pair_remains_directional_not_generic_beef(self):
        pairs = self.by_key["kiwi"]["direct_pairings"]
        self.assertEqual(len(pairs), 33)
        wagyu = [p for p in pairs if p["source_pages"]["pdf_page"] == 44
                 and "和牛" in p["ingredient_names"].values()]
        self.assertEqual(len(wagyu), 1)
        self.assertEqual(wagyu[0]["main_ingredient_id"], KIWI)
        self.assertNotEqual(wagyu[0]["paired_ingredient_id"], "ing-70099ea01925")
        self.assertFalse(any(p["source_pages"]["pdf_page"] == 43 for p in pairs))

    def test_zero_direct_pair_probe_is_not_transitive(self):
        probes = {tuple(p["ingredient_keys"]): p for p in self.bundle["pair_probes"]}
        for keys in [("kiwi", "chili"), ("kiwi", "beef")]:
            self.assertEqual(probes[keys]["total"], 0)
            self.assertTrue(probes[keys]["zero_hits"])
            self.assertEqual(probes[keys]["source_rows"], [])
        self.assertEqual(len(probes), 3)

    def test_profile_preserves_all_variants_and_unknown_with_conflict(self):
        with FlavorDB(DB) as db:
            self.assertEqual(self.by_key["kiwi"]["profile"], db.profile(KIWI))
        sample = collect_evidence({"ingredients": [ingredient("mutton", "水煮羊肉", "ing-34371cf37bc9")]}, DB, ALIASES)
        profile = sample["ingredients"][0]["profile"]
        fruit = profile["categories"][0]
        self.assertEqual((fruit["marked_count"], fruit["unmarked_count"], fruit["unknown_count"]), (1, 4, 1))
        self.assertEqual(fruit["status"], "conflict")
        self.assertTrue(fruit["has_unknown"])
        self.assertTrue(any(None in v["presence"] for v in profile["variants"]))
        self.assertNotIn("canonical", profile)

    def test_context_links_are_separate_and_full_original_evidence_kept(self):
        count = 0
        extra = collect_evidence({"ingredients": [ingredient("oil", "阿贝金纳橄榄油", "ing-010be8291a34")]}, DB, ALIASES)
        with FlavorDB(DB) as db:
            for item in self.bundle["ingredients"] + extra["ingredients"]:
                for link in item["evidence_links"]["name_matched"]:
                    self.assertIn(link["link"]["kind"], ("exact_name", "alias_name"))
                for link in item["evidence_links"]["related_context"]:
                    self.assertEqual(link["link"]["kind"], "related_context")
                    count += 1
                for evidence in item["evidence_records"]:
                    self.assertEqual(evidence["record"], db.evidence(evidence["id"]))
        self.assertGreater(count, 0)

    def test_determinism_and_database_immutability(self):
        again = collect_evidence(copy.deepcopy(self.brief), DB, ALIASES)
        self.assertEqual(again, self.bundle)
        self.assertEqual(hashlib.sha256(DB.read_bytes()).hexdigest(), self.before)
        self.assertEqual(self.bundle["provenance"]["database_sha256"], self.before)
        self.assertNotIn("database", self.bundle["provenance"]["database_stats"])

    def test_alias_formatting_does_not_change_replay(self):
        config = json.loads(ALIASES.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "aliases.json"
            path.write_text(json.dumps(config, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            self.assertEqual(collect_evidence(self.brief, DB, path), self.bundle)

    def test_unselected_candidate_is_not_promoted(self):
        bundle = collect_evidence({"ingredients": [ingredient("kiwi", "猕猴桃")]}, DB, ALIASES)
        item = bundle["ingredients"][0]
        self.assertIsNone(item["reference_id"])
        self.assertIsNone(item["profile"])
        self.assertEqual(len(item["candidates"]), 2)
        self.assertEqual(bundle["pair_probes"], [])
        self.assertTrue(any(g["kind"] == "unresolved_reference" for g in bundle["gaps"]))

    def test_invalid_reference_fails_instead_of_selecting_nearby(self):
        with self.assertRaises(Exception):
            collect_evidence({"ingredients": [ingredient("kiwi", "猕猴桃", "ing-no-such-id")]}, DB, ALIASES)


class RetrievalMechanicsTests(unittest.TestCase):
    def test_all_pages_retains_more_than_one_thousand_results(self):
        records = [{"id": str(i)} for i in range(1234)]
        def fetch(*, limit, offset):
            items = records[offset:offset + limit]
            return {"total": len(records), "items": items, "has_more": offset + len(items) < len(records)}
        found, batches = _all_pages(fetch)
        self.assertEqual(found, records)
        self.assertEqual(len(batches), 13)

    def test_pagination_inconsistency_is_error_not_silent_truncation(self):
        with self.assertRaises(ValueError):
            _all_pages(lambda **kw: {"total": 2, "items": [{"id": "one"}], "has_more": False})
        with self.assertRaises(ValueError):
            _all_pages(lambda **kw: {"total": 1, "items": [], "has_more": True})

    def test_unreviewed_alias_ignored_and_kiwiberry_not_expanded(self):
        config = json.loads(ALIASES.read_text())
        for term in ["奇异莓", "奇異莓", "kiwiberry", "kiwi berry"]:
            expanded, _ = expand_queries(term, config)
            self.assertNotIn("奇異果", expanded)
        config["groups"].append({"key": "unreviewed", "review_status": "pending", "terms": ["foo", "奇異果"]})
        self.assertEqual(expand_queries("foo", config)[0], ["foo"])

    def test_specific_processed_request_kept_while_base_terms_retrieve_context(self):
        config = json.loads(ALIASES.read_text())
        expanded, _ = expand_queries("猕猴桃冻干粉", config)
        self.assertEqual(expanded[0], "猕猴桃冻干粉")
        self.assertIn("奇異果冻干粉", expanded)
        self.assertIn("奇異果", expanded)

    def test_bad_input_does_not_turn_into_all_corpus_query(self):
        for brief in ({"ingredients": []}, {"ingredients": [ingredient("a", " ")]},
                      {"ingredients": [ingredient("a", "x"), ingredient("a", "y")]}):
            with self.assertRaises(ValueError):
                collect_evidence(brief, DB, ALIASES)


if __name__ == "__main__":
    unittest.main()
