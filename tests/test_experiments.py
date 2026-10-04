"""Scientific-design invariants; all fixture values remain unobserved."""

import copy
import itertools
import json
from pathlib import Path
import unittest

from tastex.experiments import build_design


ROOT = Path(__file__).resolve().parents[1]


class DesignTests(unittest.TestCase):
    def setUp(self):
        self.brief = json.loads((ROOT / "cases/kiwi-jerky/brief.json").read_text())
        self.design = build_design(self.brief)

    def test_every_factor_combination_and_untouched_control(self):
        cells = self.design["cells"]
        factual = [c for c in cells if c["kind"] == "factorial"]
        self.assertEqual({tuple(c["factor_levels_g"][k] for k in ("kiwi", "chili")) for c in factual},
                         set(itertools.product([0, 3, 5], [0, 0.1])))
        native = [c for c in cells if c["kind"] == "native_control"]
        self.assertEqual(len(native), 1)
        self.assertEqual(native[0]["planned_sample_masses_g"], {"base": 50, "kiwi": 0, "chili": 0, "water": 0})
        self.assertTrue(all(c["planned_sample_masses_g"]["water"] == .5 for c in factual))

    def test_mass_balance_and_totals(self):
        self.assertEqual(self.design["metrics"]["planned_material_totals_g"],
                         {"base": 700, "kiwi": 16, "chili": .3, "water": 6})
        for cell in self.design["cells"]:
            self.assertAlmostEqual(sum(cell["planned_sample_masses_g"].values()), cell["total_sample_mass_g"])
            for key, grams in cell["masses_per_basis_g"].items():
                self.assertEqual(cell["planned_sample_masses_g"][key], grams/2)

    def test_no_fabricated_actuals_and_no_assigned_blind_identity(self):
        template = self.design["template"]
        for field in ("observation_id", "run_id", "batch_id", "cell_id", "participant_id", "observed_at"):
            self.assertIsNone(template[field])
        for field in ("ratings", "actual_masses_g", "material_lots"):
            self.assertTrue(all(value is None for value in template[field].values()))
        self.assertTrue(all(c["outcomes"] is None for c in self.design["cells"]))
        self.assertTrue(all(c["estimated_value"] is None for c in self.design["contrasts"]))
        self.assertTrue(all(self.design["scope"].values()))
        self.assertEqual(self.design["scope"], template["scope"])

    def test_determinism_does_not_mutate_brief(self):
        saved = copy.deepcopy(self.brief)
        self.assertEqual(build_design(self.brief), self.design)
        self.assertEqual(self.brief, saved)
        json.dumps(self.design, allow_nan=False)

    def test_batches_are_complete_unique_blinded_permutations(self):
        self.assertEqual(self.design["blinding_algorithm"], "sha256_rank_v1")
        ids = {c["id"] for c in self.design["cells"]}
        self.assertEqual(len(ids), 7)
        self.assertEqual(len(self.design["batches"]), 2)
        for batch in self.design["batches"]:
            self.assertEqual(set(batch["cell_ids"]), ids)
            self.assertEqual(len(batch["cell_ids"]), len(ids))
            self.assertEqual([p["cell_id"] for p in batch["presentation"]], batch["cell_ids"])
            self.assertEqual([p["position"] for p in batch["presentation"]], list(range(1, 8)))
            self.assertEqual(len({p["blind_code"] for p in batch["presentation"]}), 7)
            self.assertTrue(all(100 <= int(p["blind_code"]) <= 999 for p in batch["presentation"]))
        self.assertNotEqual(self.design["batches"][0]["presentation"], self.design["batches"][1]["presentation"])

    def test_seed_changes_blinding_not_formula(self):
        changed = copy.deepcopy(self.brief)
        changed["design"]["seed"] += 1
        result = build_design(changed)
        self.assertEqual(result["cells"], self.design["cells"])
        self.assertNotEqual(result["batches"], self.design["batches"])

    def test_scope_distinguishes_processing_protocol_and_time(self):
        for mutate in (lambda b: b["design"].update(wait_minutes=60),
                       lambda b: b["design"]["preparation_notes"].append("仅测试：不同热处理协议")):
            b = copy.deepcopy(self.brief)
            mutate(b)
            result = build_design(b)
            self.assertNotEqual(result["scope"]["process"], self.design["scope"]["process"])
            self.assertEqual(result["scope"]["matrix"], self.design["scope"]["matrix"])
            self.assertEqual(result["scope"]["ingredient_state"], self.design["scope"]["ingredient_state"])
        protocol = json.loads(self.design["scope"]["process"])
        self.assertEqual(protocol["wait_minutes"], 10)
        self.assertEqual(protocol["route_id"], "rte-powder-postcoat")
        self.assertEqual(len(protocol["preparation_notes_sha256"]), 64)

    def test_contrasts_identify_single_effects_and_interactions(self):
        by_id = {c["id"]: c for c in self.design["cells"]}
        contrasts = self.design["contrasts"]
        self.assertEqual(len(contrasts), 10)
        for contrast in contrasts:
            self.assertEqual(sum(t["weight"] for t in contrast["terms"]), 0)
            self.assertTrue(all(t["cell_id"] in by_id for t in contrast["terms"]))
            if contrast["kind"] == "simple_factor_effect":
                high, low = [by_id[t["cell_id"]]["factor_levels_g"] for t in contrast["terms"]]
                self.assertEqual([k for k in high if high[k] != low[k]], [contrast["factor"]])
            elif contrast["kind"] == "factorial_difference_in_differences":
                # Additive artificial fixture must cancel; product fixture must not.
                additive = sum(t["weight"] * sum(by_id[t["cell_id"]]["factor_levels_g"].values()) for t in contrast["terms"])
                interaction = sum(t["weight"] * by_id[t["cell_id"]]["factor_levels_g"]["kiwi"] * by_id[t["cell_id"]]["factor_levels_g"]["chili"] for t in contrast["terms"])
                self.assertAlmostEqual(additive, 0)
                self.assertGreater(interaction, 0)
        wet = next(c for c in contrasts if c["kind"] == "native_vs_constants_control")
        self.assertEqual(wet["changed_constant_masses_g_per_basis"], {"water": 1})

    def test_invalid_mass_values_rejected(self):
        for bad in (-1, True, float("nan"), float("inf"), "0.1", 10**1000):
            for target in ("sample_base_g", "basis_g", "wait_minutes"):
                with self.subTest(bad=bad, target=target):
                    b = copy.deepcopy(self.brief)
                    b["design"][target] = bad
                    with self.assertRaises(ValueError):
                        build_design(b)
            b = copy.deepcopy(self.brief)
            b["design"]["factors"][0]["levels_g"][1] = bad
            with self.assertRaises(ValueError):
                build_design(b)
        for target in ("sample_base_g", "basis_g"):
            b = copy.deepcopy(self.brief)
            b["design"][target] = 0
            with self.assertRaises(ValueError):
                build_design(b)
        b = copy.deepcopy(self.brief)
        b["design"]["sample_base_g"] = 1e308
        b["design"]["factors"][0]["levels_g"][1] = 1e308
        with self.assertRaises(ValueError):
            build_design(b)

    def test_ambiguous_keys_and_levels_rejected(self):
        mutations = [
            lambda b: b["ingredients"].append(dict(b["ingredients"][0])),
            lambda b: b["design"]["constants"].append({"key": "kiwi", "grams_per_basis": 1}),
            lambda b: b["design"]["factors"][0].update(levels_g=[0, 0]),
            lambda b: b["design"]["factors"][0].update(levels_g=[0]),
            lambda b: b["design"].update(base_key="absent"),
            lambda b: b["design"].update(dimensions=["x", "x"]),
            lambda b: b["routes"][1].update(status="selected_for_screening"),
            lambda b: b["design"].update(native_control="true"),
        ]
        for mutate in mutations:
            b = copy.deepcopy(self.brief)
            mutate(b)
            with self.assertRaises(ValueError):
                build_design(b)

    def test_invalid_batches_and_seed_rejected(self):
        for field, values in (("planned_batches", [0, -1, 1.5, True, 101]), ("seed", [True, 1.2, "42"])):
            for value in values:
                b = copy.deepcopy(self.brief)
                b["design"][field] = value
                with self.assertRaises(ValueError):
                    build_design(b)

    def test_transfer_fixture_does_not_carry_meat_doses_or_materials(self):
        brief = json.loads((ROOT / "benchmarks/transfer-brief.json").read_text())
        self.assertEqual(brief["product"]["development_stage"], "synthetic_spec_not_recipe_not_tasted")
        design = build_design(brief)
        self.assertEqual(design["metrics"]["factorial_cells"], 4)
        self.assertEqual(design["metrics"]["native_control_cells"], 0)
        self.assertEqual(design["metrics"]["planned_base_total_g"], 200)
        self.assertEqual(set(design["template"]["actual_masses_g"]), {"yogurt", "strawberry", "lemon"})
        self.assertEqual(set(design["template"]["ratings"]), {"strawberry_identity", "sourness", "overall_fit"})
        self.assertEqual(design["template"]["origin"], "synthetic_test")
        high = next(c for c in design["cells"] if c["factor_levels_g"] == {"strawberry": .8, "lemon": .4})
        self.assertEqual(high["planned_sample_masses_g"], {"yogurt": 25, "strawberry": .1, "lemon": .05})
        self.assertNotEqual(design["scope"]["matrix"], self.design["scope"]["matrix"])

    def test_single_factor_and_three_factors_generalize(self):
        for count in (1, 3):
            b = copy.deepcopy(self.brief)
            if count == 1:
                b["design"]["factors"] = b["design"]["factors"][:1]
                b["design"]["constants"].append({"key": "chili", "grams_per_basis": 0})
            else:
                b["design"]["constants"] = []
                b["design"]["factors"].append({"key": "water", "levels_g": [0, 1], "origin": "hypothesis", "rationale": "test-only"})
            d = build_design(b)
            self.assertEqual(d["metrics"]["factorial_cells"], 3 if count == 1 else 12)
            for contrast in d["contrasts"]:
                self.assertEqual(sum(t["weight"] for t in contrast["terms"]), 0)


if __name__ == "__main__":
    unittest.main()
