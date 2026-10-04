"""Deterministic screening plans; no sensory observations are generated here."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from decimal import Decimal


def _number(value, label, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or value < 0 or (positive and value == 0):
        raise ValueError(f"{label} must be finite and {'positive' if positive else 'nonnegative'}")
    return value


def _scaled(value, numerator, denominator):
    """Avoid binary float artefacts in small gram quantities in exported plans."""
    result = float(Decimal(str(value)) * Decimal(str(numerator)) / Decimal(str(denominator)))
    return _number(result, "scaled mass")


def _total(masses):
    result = float(sum((Decimal(str(x)) for x in masses.values()), Decimal(0)))
    return _number(result, "total mass")


def _cell_id(kind, masses):
    payload = json.dumps([kind, masses], sort_keys=True, separators=(",", ":"))
    return "cell-" + hashlib.sha256(payload.encode()).hexdigest()[:12]


def _seeded_rank(seed, batch, purpose, value):
    """Version-independent seeded pseudorandom ordering, not a security secret."""
    payload = json.dumps(["TasteX-blinding-v1", seed, batch, purpose, value],
                         ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).digest()


def _contrasts(cells, factors):
    factorial = [c for c in cells if c["kind"] == "factorial"]
    by_levels = {tuple(c["factor_levels_g"][f["key"]] for f in factors): c for c in factorial}
    out = []
    for index, factor in enumerate(factors):
        baseline = min(factor["levels_g"])
        others = [i for i in range(len(factors)) if i != index]
        for context in itertools.product(*(factors[i]["levels_g"] for i in others)):
            low = [None] * len(factors)
            for i, value in zip(others, context):
                low[i] = value
            low[index] = baseline
            for value in sorted(factor["levels_g"]):
                if value == baseline:
                    continue
                high = list(low)
                high[index] = value
                out.append({
                    "id": f"contrast-{len(out)+1:03d}", "kind": "simple_factor_effect",
                    "question": f"在其他配料水平相同时，{factor['key']} 从 {baseline} g 增至 {value} g / 基准份，对各评分的差异是什么？",
                    "factor": factor["key"], "from_g_per_basis": baseline,
                    "to_g_per_basis": value,
                    "held_factors_g_per_basis": {factors[i]["key"]: low[i] for i in others},
                    "terms": [{"cell_id": by_levels[tuple(high)]["id"], "weight": 1},
                              {"cell_id": by_levels[tuple(low)]["id"], "weight": -1}],
                    "estimated_value": None,
                })
    for a, b in itertools.combinations(range(len(factors)), 2):
        fa, fb = factors[a], factors[b]
        amin, bmin = min(fa["levels_g"]), min(fb["levels_g"])
        others = [i for i in range(len(factors)) if i not in (a, b)]
        for context in itertools.product(*(factors[i]["levels_g"] for i in others)):
            for ahi, bhi in itertools.product([x for x in fa["levels_g"] if x != amin],
                                             [x for x in fb["levels_g"] if x != bmin]):
                terms = []
                for av, bv, weight in ((ahi, bhi, 1), (amin, bhi, -1),
                                       (ahi, bmin, -1), (amin, bmin, 1)):
                    values = [None] * len(factors)
                    for i, value in zip(others, context):
                        values[i] = value
                    values[a], values[b] = av, bv
                    terms.append({"cell_id": by_levels[tuple(values)]["id"], "weight": weight})
                out.append({
                    "id": f"contrast-{len(out)+1:03d}", "kind": "factorial_difference_in_differences",
                    "question": f"{fa['key']} 的高低水平差异是否随 {fb['key']} 的水平改变？",
                    "factors": [fa["key"], fb["key"]], "terms": terms,
                    "held_factors_g_per_basis": {factors[i]["key"]: v for i, v in zip(others, context)},
                    "interpretation": "同一评分尺度的差中之差；待有配对观察才估计，不是已证实的协同/掩盖机制。",
                    "estimated_value": None,
                })
    native = next((c for c in cells if c["kind"] == "native_control"), None)
    zero = next((c for c in factorial if all(x == 0 for x in c["factor_levels_g"].values())), None)
    if native and zero:
        differing_constants = {k: v for k, v in zero["masses_per_basis_g"].items()
                               if v != native["masses_per_basis_g"][k]}
        out.append({
            "id": f"contrast-{len(out)+1:03d}", "kind": "native_vs_constants_control",
            "question": "仅添加固定配料并执行相应处理，相比原样基底有何差异？",
            "changed_constant_masses_g_per_basis": differing_constants,
            "terms": [{"cell_id": zero["id"], "weight": 1}, {"cell_id": native["id"], "weight": -1}],
            "interpretation": "若固定配料只有水，可估计此润湿处理的整体差异；不推广为独立水活度、保存期或分子机制。",
            "estimated_value": None,
        })
    return out


def build_design(brief):
    """Build a complete factorial + optional untouched-base control.

    A plan is deterministic and contains null placeholders for every actual
    measurement. ``planned_sample_masses_g`` must never be treated as weighed data.
    Full brief/source validation is performed by the calling workflow; numeric,
    factorial and ingredient-key invariants are defended here as well.
    """
    design = brief["design"]
    basis = _number(design["basis_g"], "basis_g", positive=True)
    sample = _number(design["sample_base_g"], "sample_base_g", positive=True)
    wait = _number(design["wait_minutes"], "wait_minutes")
    factors = design["factors"]
    constants = design.get("constants", [])
    ingredients = brief["ingredients"]
    keys = [item["key"] for item in ingredients]
    if any(not isinstance(k, str) or not k.strip() for k in keys) or len(set(keys)) != len(keys):
        raise ValueError("ingredient keys must be nonempty and unique")
    base = design["base_key"]
    used = [base] + [f["key"] for f in factors] + [c["key"] for c in constants]
    if len(set(used)) != len(used) or set(used) != set(keys):
        raise ValueError("every ingredient key must occur exactly once as base, factor or constant")
    if not factors:
        raise ValueError("at least one factor is required")
    factor_count = 1
    for factor in factors:
        levels = factor["levels_g"]
        if len(levels) < 2:
            raise ValueError("each factor requires at least two levels")
        for value in levels:
            _number(value, f"factor {factor['key']} level")
        if len(set(levels)) != len(levels):
            raise ValueError("factor levels must be unique")
        factor_count *= len(levels)
    if factor_count + bool(design.get("native_control")) > 900:
        raise ValueError("plan exceeds 900 unique three-digit blind codes per batch")
    for constant in constants:
        _number(constant["grams_per_basis"], f"constant {constant['key']}")
    batch_count = design["planned_batches"]
    if isinstance(batch_count, bool) or not isinstance(batch_count, int) or not 1 <= batch_count <= 100:
        raise ValueError("planned_batches must be an integer between 1 and 100")
    seed = design["seed"]
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    dims = design["dimensions"]
    if not dims or any(not isinstance(x, str) or not x.strip() for x in dims) or len(set(dims)) != len(dims):
        raise ValueError("dimensions must be nonempty unique names")
    routes = [r for r in brief["routes"] if r["status"] == "selected_for_screening"]
    if len(routes) != 1:
        raise ValueError("select exactly one route for a screening design")
    if not isinstance(design.get("native_control", False), bool):
        raise ValueError("native_control must be boolean")

    cells = []
    for levels in itertools.product(*(f["levels_g"] for f in factors)):
        levels_by_key = {f["key"]: value for f, value in zip(factors, levels)}
        masses = {key: 0 for key in keys}
        masses[base] = basis
        masses.update(levels_by_key)
        masses.update({c["key"]: c["grams_per_basis"] for c in constants})
        cells.append({"id": _cell_id("factorial", masses), "kind": "factorial",
                      "factor_levels_g": levels_by_key, "masses_per_basis_g": masses})
    if design.get("native_control"):
        masses = {key: (basis if key == base else 0) for key in keys}
        cells.append({"id": _cell_id("native_control", masses), "kind": "native_control",
                      "factor_levels_g": {f["key"]: 0 for f in factors}, "masses_per_basis_g": masses})
    for cell in cells:
        cell["planned_sample_masses_g"] = {key: _scaled(value, sample, basis)
                                           for key, value in cell["masses_per_basis_g"].items()}
        cell["total_sample_mass_g"] = _total(cell["planned_sample_masses_g"])
        cell["total_mass_g_per_basis"] = _total(cell["masses_per_basis_g"])
        cell["quantity_status"] = "planned_not_weighed"
        cell["outcomes"] = None
    batches = []
    for index in range(batch_count):
        ids = sorted((c["id"] for c in cells),
                     key=lambda cell_id: _seeded_rank(seed, index+1, "order", cell_id))
        codes = sorted(range(100, 1000),
                       key=lambda code: _seeded_rank(seed, index+1, "blind-code", code))[:len(ids)]
        batches.append({"id": f"batch-{index+1:02d}", "status": "planned_not_prepared",
                        "cell_ids": ids,
                        "presentation": [{"position": p+1, "blind_code": str(code), "cell_id": cell}
                                         for p, (cell, code) in enumerate(zip(ids, codes))],
                        "actual_prepared_at": None, "actual_operator_id": None,
                        "material_lots": {key: None for key in keys}})
    protocol = {"route_id": routes[0]["id"], "wait_minutes": wait,
                "preparation_notes_sha256": hashlib.sha256(json.dumps(
                    design.get("preparation_notes", []), ensure_ascii=False,
                    separators=(",", ":")).encode()).hexdigest()}
    scope = {
        "matrix": brief["product"]["matrix"],
        "ingredient_state": "; ".join(f"{i['key']}={i['requested_state']}" for i in ingredients),
        "process": json.dumps(protocol, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        "serving_context": brief["product"]["intended_use"],
    }
    warnings = [
        "所有配料克数是筛选设计，不是实称值、最佳比例或感官预测。",
        "随机呈样降低固定顺序偏差，但没有实现完整顺序平衡，也不能消除前样味觉残留和提示效应。",
        "盲码映射含配方身份，应由制样者保管；自行制样者不能视为完全盲评。",
        "不同批次应独立称量制备；同一锅分装或同一样重复评分不构成独立制备批次。",
        f"静置 {wait} 分钟是统一待观察条件，未证明为最优处理时间。",
    ]
    if batch_count < 2:
        warnings.append("仅计划一个制备批次，不能检验跨批次一致性。")
    if design.get("native_control") and not any(all(v == 0 for v in c["factor_levels_g"].values())
                                                for c in cells if c["kind"] == "factorial"):
        warnings.append("因子没有共同零水平，原样对照不能单独识别固定配料/润湿处理的影响。")
    if any(0 < g < 0.1 for c in cells for g in c["planned_sample_masses_g"].values()):
        warnings.append("包含小于 0.1 g 的配料：显示分度不等于称量准确度；记录校验和实际读数，设备不能可靠称量时等比例放大整样。")
    template = {
        "schema_version": "1.0", "observation_id": None,
        "case_id": brief["case_id"], "revision": brief["revision"], "run_id": None,
        "batch_id": None, "cell_id": None, "participant_id": None, "observed_at": None,
        "scope": scope, "material_lots": {key: None for key in keys},
        "actual_masses_g": {key: None for key in keys},
        "ratings": {dim: None for dim in dims}, "scale": {"min": 0, "max": 10},
        "free_description": None, "disposition": "not_evaluated", "notes": None,
        "origin": ("synthetic_test" if brief["product"]["development_stage"].startswith("synthetic")
                   else "human_observed"), "supersedes": None,
    }
    return {
        "schema_version": "1.0", "status": "design_only_not_tasted", "basis_g": basis,
        "sample_base_g": sample, "base_key": base, "selected_route_id": routes[0]["id"],
        "seed": seed, "blinding_algorithm": "sha256_rank_v1", "wait_minutes": wait,
        "scope": scope, "cells": cells, "batches": batches,
        "metrics": {"factorial_cells": factor_count, "native_control_cells": int(bool(design.get("native_control"))),
                    "cells_per_batch": len(cells), "planned_batches": batch_count,
                    "planned_samples": len(cells)*batch_count,
                    "planned_base_total_g": _scaled(sample, len(cells)*batch_count, 1),
                    "planned_material_totals_g": {key: _scaled(_total({c["id"]: c["planned_sample_masses_g"][key]
                                                                       for c in cells}), batch_count, 1) for key in keys},
                    "actual_samples": None, "actual_participants": None, "sensory_results": None},
        "warnings": warnings, "template": template, "contrasts": _contrasts(cells, factors),
        "analysis_limits": [
            "仅在同一批次、同一试吃者、相同维度且所需样品评分齐全时计算对比；未评分保持 null。",
            "将每个制备批次的对比单独报告，再查看重复方向；不把多人评分或多口试吃当成独立制备批次。",
            "原料批次或状态改变时需记录适用范围；剂量改变会同时改变糖、酸、固形物等，不能归因为纯香气效应。",
            "两批小试不足以确认人群偏好、统计显著性、分子机制、货架期或商品化稳定性。",
            "未指定目标参照或接受线时只能报告观察和用户选择，不能自动宣布符合全部用户目标。",
        ],
    }
