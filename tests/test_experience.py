"""Temporary, explicitly fabricated unit fixtures; never a sensory data release."""
import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tastex.experience import ExperienceError, ExperienceStore, FIELDS, _validate_shape


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_run(root, run_id="run-fixture-1"):
    root.mkdir(parents=True, exist_ok=True)
    scope = {"matrix": "finished lean beef jerky", "ingredient_state": "kiwi=freeze-dried powder", "process": "surface-coating", "serving_context": "immediate tasting"}
    masses = {"base": 20, "kiwi": 0.6, "chili": 0.02, "water": 0.2}
    brief = json.loads((Path(__file__).parents[1] / "cases/kiwi-jerky/brief.json").read_text())
    brief.update(case_id="fixture-case", revision="r2", request_text="Fabricated unit test only: " + run_id)
    brief["design"]["dimensions"] = ["kiwi", "sweet", "spicy", "bitter", "greasy"]
    for target, dimension in zip(brief["targets"], brief["design"]["dimensions"]):
        target["dimension"] = dimension
    design = {"cells": [{"id": "C1", "planned_sample_masses_g": masses},
                         {"id": "C2", "planned_sample_masses_g": {**masses, "kiwi": 0.3}}],
              "batches": [{"id": name, "cell_ids": ["C1", "C2"]} for name in ["B1", "B2"]],
              "contrasts": [{"id": "contrast-001", "kind": "simple_factor_effect", "question": "Fixture low-minus-high contrast", "terms": [{"cell_id": "C2", "weight": 1}, {"cell_id": "C1", "weight": -1}], "estimated_value": None}]}
    template = {"case_id": "fixture-case", "revision": "r2", "run_id": run_id, "scope": scope}
    for name, data in [("brief.json", brief), ("design.json", design), ("observation-template.json", template)]:
        (root / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name in ["aliases.json", "evidence.json", "validation.json"]:
        (root / name).write_text("{}\n")
    for name in ["report.md", "tasting-sheet.md", "events.jsonl"]:
        (root / name).write_text("Temporary fixture only.\n")
    from tastex.workflow import encoded, sha
    inputs = {"database_sha256": "a" * 64, "config_sha256": digest(root / "aliases.json"),
              "brief_sha256": digest(root / "brief.json"), "workflow_fingerprint": "c" * 64, "workflow_version": "fixture-1"}
    run_id = "run-" + sha(encoded(inputs))[:24]
    template["run_id"] = run_id
    (root / "observation-template.json").write_text(json.dumps(template))
    manifest = {"schema_version": "1.0", "case_id": "fixture-case", "revision": "r2", "run_id": run_id, **inputs,
                "artifacts": {name: digest(root / name) for name in ["brief.json", "design.json", "observation-template.json", "aliases.json", "evidence.json", "validation.json", "report.md", "tasting-sheet.md", "events.jsonl"]}}
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return {"schema_version": "1.0", "observation_id": "fixture-observation-1", "case_id": "fixture-case", "revision": "r2", "run_id": run_id,
            "batch_id": "B1", "cell_id": "C1", "participant_id": "fixture-participant-1", "observed_at": "2026-10-05T13:00:00+08:00",
            "scope": scope, "material_lots": {k: f"fictional-test-lot-{k}" for k in masses}, "actual_masses_g": masses,
            "ratings": {"kiwi": 4, "sweet": 2, "spicy": 2, "bitter": 0, "greasy": 0}, "scale": {"min": 0, "max": 10},
            "free_description": "Fabricated unit-test input only.", "notes": "Not a human tasting; isolated temporary test.",
            "disposition": "acceptable", "origin": "human_observed", "supersedes": None}


class ExperienceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.run = self.root / "run"
        self.obs = make_run(self.run)
        self.store = ExperienceStore(self.root / "experience.sqlite")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def modify_manifest(self, change):
        path = self.run / "manifest.json"
        data = json.loads(path.read_text())
        change(data)
        path.write_text(json.dumps(data))

    def reseal_run(self):
        from tastex.workflow import encoded, sha
        path = self.run / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["brief_sha256"] = digest(self.run / "brief.json")
        manifest["config_sha256"] = digest(self.run / "aliases.json")
        inputs = {key: manifest[key] for key in ("brief_sha256", "database_sha256", "config_sha256", "workflow_fingerprint", "workflow_version")}
        manifest["run_id"] = "run-" + sha(encoded(inputs))[:24]
        template_path = self.run / "observation-template.json"
        template = json.loads(template_path.read_text())
        template["run_id"] = manifest["run_id"]
        template_path.write_text(json.dumps(template))
        manifest["artifacts"] = {name: digest(self.run / name) for name in manifest["artifacts"]}
        path.write_text(json.dumps(manifest))
        return manifest["run_id"]

    def test_empty_store_is_not_experience(self):
        result = self.store.summarize({})
        self.assertEqual(result["observation_count"], 0)
        self.assertEqual(result["quality_stage"], "no_observations")
        self.assertEqual(result["conditions"], [])
        self.assertTrue(self.store.verify()["ok"])

    def test_valid_write_idempotency_and_source_association(self):
        written = self.store.record(self.obs, self.run)
        self.assertEqual(written["status"], "recorded")
        self.assertEqual(self.store.record(copy.deepcopy(self.obs), self.run)["status"], "already_recorded")
        self.assertEqual(self.store.verify()["event_count"], 1)
        result = self.store.search(self.obs["scope"])["exact"][0]
        self.assertEqual(result["provenance"]["database_sha256"], "a" * 64)
        self.assertEqual(result["provenance"]["manifest_sha256"], digest(self.run / "manifest.json"))

    def test_duplicate_id_with_changed_content_fails(self):
        self.store.record(self.obs, self.run)
        self.obs["ratings"]["kiwi"] = 8
        with self.assertRaisesRegex(ExperienceError, "different content"):
            self.store.record(self.obs, self.run)

    def test_duplicate_sample_needs_explicit_correction(self):
        self.store.record(self.obs, self.run)
        self.obs["observation_id"] = "second-fixture"
        with self.assertRaisesRegex(ExperienceError, "supersedes"):
            self.store.record(self.obs, self.run)

    def test_correction_is_appended_latest_only_and_original_remains(self):
        first = self.store.record(self.obs, self.run)
        revised = {**self.obs, "observation_id": "corrected-fixture", "supersedes": self.obs["observation_id"], "ratings": {**self.obs["ratings"], "kiwi": 6}}
        self.store.record(revised, self.run)
        found = self.store.search({})
        self.assertEqual(found["counts"]["superseded_excluded"], 1)
        self.assertEqual(len(found["exact"]), 1)
        self.assertEqual(found["exact"][0]["observation"]["ratings"]["kiwi"], 6)
        row = self.store.connection.execute("SELECT event_hash FROM observations WHERE seq=1").fetchone()
        self.assertEqual(row[0], first["event_sha256"])
        with self.assertRaisesRegex(ExperienceError, "latest"):
            self.store.record({**revised, "observation_id": "stale-correction"}, self.run)

    def test_unknown_and_cross_participant_corrections_fail(self):
        with self.assertRaisesRegex(ExperienceError, "unknown observation"):
            self.store.record({**self.obs, "supersedes": "absent"}, self.run)
        self.store.record(self.obs, self.run)
        with self.assertRaisesRegex(ExperienceError, "cannot cross"):
            self.store.record({**self.obs, "observation_id": "bad-fix", "participant_id": "another", "supersedes": self.obs["observation_id"]}, self.run)

    def test_cross_run_correction_is_not_a_match(self):
        self.store.record(self.obs, self.run)
        other = make_run(self.root / "other", run_id="another-run")
        other.update(observation_id="cross-run-fix", supersedes=self.obs["observation_id"])
        with self.assertRaisesRegex(ExperienceError, "cannot cross"):
            self.store.record(other, self.root / "other")

    def test_append_only_triggers(self):
        self.store.record(self.obs, self.run)
        for query in ["DELETE FROM observations", "UPDATE observations SET origin='synthetic_test'", "DELETE FROM experience_metadata"]:
            with self.subTest(query=query), self.assertRaises(sqlite3.IntegrityError):
                self.store.connection.execute(query)
        self.assertTrue(self.store.verify()["ok"])

    def test_artifact_and_brief_hash_tampering_rejected(self):
        (self.run / "brief.json").write_text("{}")
        with self.assertRaisesRegex(ExperienceError, "hash mismatch"):
            self.store.record(self.obs, self.run)

    def test_manifest_brief_hash_must_agree(self):
        self.modify_manifest(lambda m: m.update(brief_sha256="c" * 64))
        with self.assertRaisesRegex(ExperienceError, "brief hash"):
            self.store.record(self.obs, self.run)

    def test_manifest_must_cover_template(self):
        self.modify_manifest(lambda m: m["artifacts"].pop("observation-template.json"))
        with self.assertRaisesRegex(ExperienceError, "must cover"):
            self.store.record(self.obs, self.run)

    def test_path_traversal_rejected_before_read(self):
        self.modify_manifest(lambda m: m["artifacts"].update({"../private.json": "a" * 64}))
        with self.assertRaisesRegex(ExperienceError, "unsafe artifact"):
            self.store.record(self.obs, self.run)

    def test_symlink_artifact_rejected(self):
        target = self.root / "outside.json"
        target.write_text("{}")
        (self.run / "external.json").symlink_to(target)
        self.modify_manifest(lambda m: m["artifacts"].update({"external.json": digest(target)}))
        with self.assertRaisesRegex(ExperienceError, "escape|symlink"):
            self.store.record(self.obs, self.run)

    def test_invalid_database_hash_rejected(self):
        self.modify_manifest(lambda m: m.update(database_sha256="not-a-database-hash"))
        with self.assertRaisesRegex(ExperienceError, "SHA-256"):
            self.store.record(self.obs, self.run)

    def test_invalid_identifiers_dates_and_placeholders_rejected(self):
        for patch in [{"participant_id": "待填写"}, {"observed_at": "2026-10-05"}, {"participant_id": "null"}, {"participant_id": " p "}, {"observed_at": "2026-10-05T10:00:00"}, {"participant_id": ""}]:
            with self.subTest(patch=patch), self.assertRaises(ExperienceError):
                self.store.record({**self.obs, **patch}, self.run)

    def test_finite_ratings_and_complete_dimensions(self):
        for value in [-1, 10.1, True, float("inf"), float("nan"), "5"]:
            altered = copy.deepcopy(self.obs)
            altered["ratings"]["kiwi"] = value
            with self.subTest(value=value), self.assertRaises(ExperienceError):
                self.store.record(altered, self.run)
        altered = copy.deepcopy(self.obs)
        del altered["ratings"]["bitter"]
        with self.assertRaisesRegex(ExperienceError, "all design dimensions"):
            self.store.record(altered, self.run)

    def test_material_keys_lots_and_actual_masses(self):
        mutations = [lambda o: o["actual_masses_g"].pop("water"),
                     lambda o: o["material_lots"].pop("kiwi"),
                     lambda o: o["actual_masses_g"].update(base=0),
                     lambda o: o["actual_masses_g"].update(kiwi=float("nan")),
                     lambda o: o["material_lots"].update(kiwi="TBD"),
                     lambda o: o["material_lots"].update(unplanned="lot")]
        for mutation in mutations:
            altered = copy.deepcopy(self.obs)
            mutation(altered)
            with self.subTest(altered=altered), self.assertRaises(ExperienceError):
                self.store.record(altered, self.run)

    def test_zero_actual_ingredient_does_not_require_lot(self):
        self.obs["actual_masses_g"]["chili"] = 0
        self.obs["material_lots"].pop("chili")
        result = self.store.record(self.obs, self.run)
        self.assertAlmostEqual(result["mass_deviations_g"]["chili"], -0.02)

    def test_unknown_cell_batch_and_changed_scope_rejected(self):
        for patch in [{"cell_id": "unknown-cell"}, {"batch_id": "unknown-batch"}, {"scope": {**self.obs["scope"], "matrix": "pork"}}, {"run_id": "other"}]:
            with self.subTest(patch=patch), self.assertRaises(ExperienceError):
                self.store.record({**self.obs, **patch}, self.run)

    def test_search_exact_scope_and_explicit_near(self):
        self.store.record(self.obs, self.run)
        query = {**self.obs["scope"], "matrix": "pork"}
        self.assertEqual(self.store.search(query)["counts"]["exact"], 0)
        self.assertEqual(self.store.search(query)["near"], [])
        near = self.store.search(query, include_near=True)["near"]
        self.assertEqual(near[0]["match_kind"], "near")
        self.assertEqual(near[0]["mismatched_fields"], ["matrix"])
        with self.assertRaisesRegex(ExperienceError, "query scope"):
            self.store.search({"unrecognized": "value"})

    def test_one_batch_many_people_does_not_mean_repeated(self):
        self.store.record(self.obs, self.run)
        other = {**self.obs, "observation_id": "person-2", "participant_id": "P2", "ratings": {**self.obs["ratings"], "kiwi": 8}, "disposition": "reject"}
        self.store.record(other, self.run)
        condition = self.store.summarize({})["conditions"][0]
        self.assertEqual(condition["quality_stage"], "observed_one_batch")
        self.assertEqual(condition["recorded_batch_count"], 1)
        self.assertEqual(condition["participant_count"], 2)
        self.assertEqual(condition["ratings"]["kiwi"]["range"], 4)
        self.assertTrue(condition["accept_reject_disagreement"])

    def test_two_batches_are_repeated_but_not_generalized(self):
        self.store.record(self.obs, self.run)
        self.store.record({**self.obs, "observation_id": "batch-2", "batch_id": "B2"}, self.run)
        condition = self.store.summarize({})["conditions"][0]
        self.assertEqual(condition["quality_stage"], "repeated_not_generalized")
        self.assertEqual(condition["rated_batch_count"], 2)

    def test_missing_ratings_are_not_zero_or_numeric_evidence(self):
        self.obs["ratings"] = {key: None for key in self.obs["ratings"]}
        self.store.record(self.obs, self.run)
        condition = self.store.summarize({})["conditions"][0]
        self.assertEqual(condition["quality_stage"], "no_numeric_ratings")
        self.assertIsNone(condition["ratings"]["bitter"]["minimum"])
        self.assertEqual(condition["ratings"]["bitter"]["missing"], 1)

    def test_same_scope_different_cells_and_doses_not_pooled(self):
        self.store.record(self.obs, self.run)
        self.store.record({**self.obs, "observation_id": "different-dose", "cell_id": "C2", "actual_masses_g": {**self.obs["actual_masses_g"], "kiwi": 0.3}}, self.run)
        self.store.record({**self.obs, "observation_id": "weighing-deviation", "participant_id": "P2", "actual_masses_g": {**self.obs["actual_masses_g"], "kiwi": 0.61}}, self.run)
        summary = self.store.summarize({})
        self.assertEqual(summary["condition_count"], 3)
        self.assertEqual(summary["observation_count"], 3)

    def test_synthetic_only_explicit_temp_and_excluded(self):
        synthetic = {**self.obs, "origin": "synthetic_test"}
        with self.assertRaisesRegex(ExperienceError, "test mode"):
            self.store.record(synthetic, self.run)
        with ExperienceStore(self.root / "synthetic.sqlite", allow_synthetic=True) as isolated:
            isolated.record(synthetic, self.run)
            self.assertEqual(isolated.search({})["counts"]["synthetic_excluded"], 1)
            self.assertEqual(isolated.summarize({})["quality_stage"], "no_observations")
        with self.assertRaisesRegex(ExperienceError, "temporary"):
            ExperienceStore(Path.cwd() / "should-never-exist.sqlite", allow_synthetic=True)

    def test_tampering_detected_and_further_recording_blocked(self):
        self.store.record(self.obs, self.run)
        self.store.connection.execute("DROP TRIGGER observations_no_update")
        self.store.connection.execute("UPDATE observations SET event_hash=?", ("c" * 64,))
        self.assertFalse(self.store.verify()["ok"])
        with self.assertRaisesRegex(ExperienceError, "integrity"):
            self.store.search({})
        with self.assertRaisesRegex(ExperienceError, "integrity"):
            self.store.record({**self.obs, "observation_id": "blocked", "participant_id": "P2"}, self.run)

    def test_schema_required_fields_align_with_runtime(self):
        schema = json.loads((Path(__file__).parents[1] / "schemas/observation.schema.json").read_text())
        self.assertEqual(set(schema["required"]), FIELDS)
        self.assertFalse(schema["additionalProperties"])
        _validate_shape(self.obs)
        with self.assertRaisesRegex(ExperienceError, "fields mismatch"):
            _validate_shape({**self.obs, "unreviewed_field": "x"})

    def test_null_lot_is_allowed_only_for_zero_actual_mass(self):
        bad = copy.deepcopy(self.obs)
        bad["material_lots"]["chili"] = None
        with self.assertRaisesRegex(ExperienceError, "lot required"):
            self.store.record(bad, self.run)
        bad["actual_masses_g"]["chili"] = 0
        self.assertEqual(self.store.record(bad, self.run)["status"], "recorded")

    def test_other_database_cannot_be_used_as_store(self):
        path = self.root / "source.sqlite"
        conn = sqlite3.connect(path)
        try:
            conn.execute("CREATE TABLE source_data(id INTEGER)")
        finally:
            conn.close()
        before = digest(path)
        with self.assertRaisesRegex(ExperienceError, "not an experience store"):
            ExperienceStore(path)
        self.assertEqual(digest(path), before)

    def pair(self, first=None, second=None):
        a = copy.deepcopy(first or self.obs)
        b = copy.deepcopy(second or self.obs)
        b.update(observation_id="paired-fixture-2", cell_id="C2")
        b["actual_masses_g"]["kiwi"] = 0.3
        b["ratings"]["kiwi"] = 3
        self.store.record(a, self.run)
        self.store.record(b, self.run)
        return a, b

    def test_analysis_empty_returns_no_measurements(self):
        result = self.store.analyze(self.run)
        self.assertEqual(result["status"], "no_observations")
        self.assertEqual(result["calculated_dimension_contrast_count"], 0)
        self.assertTrue(all(batch["paired_results"] == [] for batch in result["batches"]))

    def test_analysis_complete_pair_uses_signed_design_weights(self):
        self.pair()
        result = self.store.analyze(self.run)
        pair = result["batches"][0]["paired_results"][0]
        self.assertEqual(pair["ratings"]["kiwi"]["value"], -1)
        self.assertEqual(pair["ratings"]["sweet"]["value"], 0)
        self.assertEqual(result["calculated_dimension_contrast_count"], 5)
        self.assertEqual(result["batches"][1]["status"], "no_observations")

    def test_analysis_missing_rating_is_not_imputed(self):
        second = copy.deepcopy(self.obs)
        second["ratings"]["bitter"] = None
        self.pair(second=second)
        result = self.store.analyze(self.run)
        rating = result["batches"][0]["paired_results"][0]["ratings"]["bitter"]
        self.assertIsNone(rating["value"])
        self.assertEqual(rating["missing_rating_cell_ids"], ["C2"])
        self.assertEqual(result["calculated_dimension_contrast_count"], 4)

    def test_analysis_never_pairs_different_participants_or_batches(self):
        for changed_field in ("participant_id", "batch_id"):
            with self.subTest(changed_field=changed_field), ExperienceStore(":memory:") as store:
                first, second = copy.deepcopy(self.obs), copy.deepcopy(self.obs)
                second.update(observation_id="other-cell", cell_id="C2")
                second["actual_masses_g"]["kiwi"] = 0.3
                second[changed_field] = "P2" if changed_field == "participant_id" else "B2"
                store.record(first, self.run)
                store.record(second, self.run)
                self.assertEqual(store.analyze(self.run)["calculated_dimension_contrast_count"], 0)

    def test_analysis_blocks_nonaligned_formulation_and_shared_lot(self):
        for reason in ("nonproportional_actual_masses", "material_lot_changed_within_contrast"):
            with self.subTest(reason=reason), ExperienceStore(":memory:") as store:
                first, second = copy.deepcopy(self.obs), copy.deepcopy(self.obs)
                second.update(observation_id="other-cell", cell_id="C2")
                second["actual_masses_g"]["kiwi"] = 0.3
                if reason == "nonproportional_actual_masses":
                    second["actual_masses_g"]["chili"] = 0.021
                else:
                    second["material_lots"]["base"] = "different-base-lot"
                store.record(first, self.run)
                store.record(second, self.run)
                result = store.analyze(self.run)
                self.assertEqual(result["calculated_dimension_contrast_count"], 0)
                self.assertIn(reason, [p["kind"] for p in result["batches"][0]["paired_results"][0]["blocked_reasons"]])

    def test_analysis_common_scale_allowed_but_mixed_scale_blocked(self):
        for scale_second in (2, 3):
            with self.subTest(scale_second=scale_second), ExperienceStore(":memory:") as store:
                first, second = copy.deepcopy(self.obs), copy.deepcopy(self.obs)
                second.update(observation_id="other-cell", cell_id="C2")
                second["actual_masses_g"]["kiwi"] = 0.3
                first["actual_masses_g"] = {key: mass * 2 for key, mass in first["actual_masses_g"].items()}
                second["actual_masses_g"] = {key: mass * scale_second for key, mass in second["actual_masses_g"].items()}
                store.record(first, self.run)
                store.record(second, self.run)
                self.assertEqual(store.analyze(self.run)["calculated_dimension_contrast_count"], 5 if scale_second == 2 else 0)

    def test_analysis_uses_latest_correction(self):
        _, second = self.pair()
        second = {**second, "observation_id": "corrected-pair", "supersedes": second["observation_id"], "ratings": {**second["ratings"], "kiwi": 8}}
        self.store.record(second, self.run)
        result = self.store.analyze(self.run)
        self.assertEqual(result["batches"][0]["paired_results"][0]["ratings"]["kiwi"]["value"], 4)
        self.assertEqual(result["observation_count"], 2)

    def test_analysis_changed_run_artifacts_are_not_same_provenance(self):
        self.pair()
        (self.run / "report.md").write_text("Different persisted run content")
        self.modify_manifest(lambda m: m["artifacts"].update({"report.md": digest(self.run / "report.md")}))
        result = self.store.analyze(self.run)
        self.assertEqual(result["observation_count"], 0)
        self.assertEqual(len(result["excluded"]["provenance_mismatch_ids"]), 2)

    def test_synthetic_run_cannot_be_relabeled_as_human(self):
        brief_path = self.run / "brief.json"
        brief = json.loads(brief_path.read_text())
        brief["product"]["development_stage"] = "synthetic_spec_not_recipe_not_tasted"
        brief_path.write_text(json.dumps(brief))
        self.obs["run_id"] = self.reseal_run()
        with self.assertRaisesRegex(ExperienceError, "cannot be relabeled"):
            self.store.record(self.obs, self.run)
        self.obs["origin"] = "synthetic_test"
        with ExperienceStore(self.root / "isolated.sqlite", allow_synthetic=True) as isolated:
            self.assertEqual(isolated.record(self.obs, self.run)["status"], "recorded")
            self.assertEqual(isolated.analyze(self.run)["observation_count"], 0)

    def test_python_record_checks_content_derived_run_identity(self):
        self.obs["run_id"] = "run-forged"
        template_path = self.run / "observation-template.json"
        template = json.loads(template_path.read_text())
        template["run_id"] = self.obs["run_id"]
        template_path.write_text(json.dumps(template))
        self.modify_manifest(lambda m: m.update(run_id=self.obs["run_id"], artifacts={**m["artifacts"], "observation-template.json": digest(template_path)}))
        with self.assertRaisesRegex(ExperienceError, "identity mismatch"):
            self.store.record(self.obs, self.run)


if __name__ == "__main__":
    unittest.main()
