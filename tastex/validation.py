"""Dependency-free structural and semantic validation of experimental briefs."""
from __future__ import annotations
import math
import re


class ValidationError(ValueError):
    pass


def validate_brief(brief: dict) -> dict:
    errors, warnings, unresolved = [], [], []

    def error(path, message):
        errors.append({"path": path, "message": message})

    def text(value, path):
        if not isinstance(value, str) or not value.strip():
            error(path, "Expected a non-empty string")
            return False
        return True

    def number(value, path, *, positive=False):
        try:
            good = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
        except OverflowError:
            good = False
        if not good or (value <= 0 if positive else value < 0):
            error(path, "Expected a finite " + ("positive" if positive else "nonnegative") + " number")
            return False
        return True

    def enum(value, path, allowed):
        if value not in allowed:
            error(path, "Expected one of " + ", ".join(allowed))

    def objects(value, path, *, allow_empty=False):
        if not isinstance(value, list) or (not value and not allow_empty):
            error(path, "Expected a " + ("" if allow_empty else "non-empty ") + "list")
            return []
        for i, item in enumerate(value):
            if not isinstance(item, dict):
                error(f"{path}[{i}]", "Expected an object")
        return [item for item in value if isinstance(item, dict)]

    if not isinstance(brief, dict):
        return {"valid": False, "errors": [{"path": "$", "message": "Expected object"}], "warnings": [], "unresolved": []}
    if brief.get("schema_version") != "1.0":
        error("schema_version", "Supported schema version is 1.0")
    external = brief.get("external_evidence", {})
    if not isinstance(external, dict) or not all(isinstance(k, str) and k.strip() and isinstance(v, dict) for k, v in external.items()):
        error("external_evidence", "Expected a mapping of reference names to retained source objects")
    for field in ("case_id", "revision", "request_text"):
        text(brief.get(field), field)
    for field in ("case_id", "revision"):
        value = brief.get(field)
        if isinstance(value, str) and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", value):
            error(field, "Use a portable identifier, not a path")
    product = brief.get("product")
    if not isinstance(product, dict):
        error("product", "Expected an object")
        product = {}
    for field in ("name", "matrix", "development_stage", "intended_use"):
        text(product.get(field), "product." + field)
    if "storage_requirement" not in product:
        error("product.storage_requirement", "Declare the requirement explicitly, null if unconfirmed")
    elif product["storage_requirement"] is None:
        unresolved.append({"path": "product.storage_requirement", "impact": "No storage or shelf-life claim can be made."})
    else:
        text(product["storage_requirement"], "product.storage_requirement")

    targets = objects(brief.get("targets"), "targets")
    target_names = []
    for i, target in enumerate(targets):
        path = f"targets[{i}]"
        for key in ("dimension", "intent"):
            text(target.get(key), path + "." + key)
        target_names.append(target.get("dimension"))
        for key in ("reference", "acceptance"):
            if key not in target:
                error(path + "." + key, "Use explicit null for an unconfirmed criterion")
            elif target[key] is None:
                unresolved.append({"path": path + "." + key, "impact": "Preference needs user calibration; do not invent a pass threshold."})
        if target.get("reference") is not None:
            text(target["reference"], path + ".reference")
        if target.get("acceptance") is not None and not isinstance(target["acceptance"], dict):
            error(path + ".acceptance", "Expected object or null")
        elif target.get("acceptance") == {}:
            error(path + ".acceptance", "Empty acceptance is ambiguous; use null until calibrated")
    if len([v for v in target_names if isinstance(v, str)]) != len(set(v for v in target_names if isinstance(v, str))):
        error("targets", "Duplicate dimensions")

    ingredients = objects(brief.get("ingredients"), "ingredients")
    keys = []
    for i, item in enumerate(ingredients):
        path = f"ingredients[{i}]"
        for key in ("key", "label", "query", "requested_state", "role"):
            text(item.get(key), path + "." + key)
        keys.append(item.get("key"))
        enum(item.get("identity_relation"), path + ".identity_relation", ("exact", "different_state", "unresolved"))
        ref = item.get("reference_id")
        if "reference_id" not in item:
            error(path + ".reference_id", "Required; null means unresolved")
        elif ref is not None and (not isinstance(ref, str) or not re.fullmatch(r"ing-[a-f0-9]{12}", ref)):
            error(path + ".reference_id", "Expected stable ingredient ID or null")
        if item.get("identity_relation") == "exact" and ref is None:
            error(path + ".identity_relation", "Exact identity requires a reference ID")
        if item.get("identity_relation") != "exact":
            unresolved.append({"path": path, "impact": "Requested material is not asserted to equal the source ingredient state."})
    valid_keys = [v for v in keys if isinstance(v, str)]
    if len(valid_keys) != len(set(valid_keys)):
        error("ingredients", "Duplicate ingredient keys")

    for field in ("constraints", "assumptions"):
        items = objects(brief.get(field), field, allow_empty=True)
        identifiers = []
        for i, item in enumerate(items):
            path = f"{field}[{i}]"
            for key in ("id", "text"):
                text(item.get(key), path + "." + key)
            identifiers.append(item.get("id"))
            enum(item.get("status"), path + ".status", ("confirmed", "assumed", "unresolved"))
            if field == "constraints":
                enum(item.get("kind"), path + ".kind", ("hard", "preference"))
            else:
                text(item.get("consequence"), path + ".consequence")
            if item.get("status") != "confirmed":
                unresolved.append({"path": path, "impact": item.get("consequence", item.get("text"))})
        identifier_strings = [v for v in identifiers if isinstance(v, str)]
        if len(identifier_strings) != len(set(identifier_strings)):
            error(field, "Duplicate identifiers")

    routes = objects(brief.get("routes"), "routes")
    if sum(r.get("status") == "selected_for_screening" for r in routes) != 1:
        error("routes", "Select exactly one route for this screening run")
    if len(routes) < 2:
        warnings.append({"path": "routes", "message": "Only one route is documented; alternative comparison is incomplete."})
    route_ids = []
    for i, route in enumerate(routes):
        path = f"routes[{i}]"
        for key in ("id", "title", "rationale"):
            text(route.get(key), path + "." + key)
        route_ids.append(route.get("id"))
        enum(route.get("status"), path + ".status", ("selected_for_screening", "alternative", "deferred"))
        for field in ("advantages", "limitations", "evidence_refs"):
            if not isinstance(route.get(field), list) or not all(isinstance(v, str) and v.strip() for v in route.get(field, [])):
                error(path + "." + field, "Expected list of non-empty strings")
        for j, parameter in enumerate(objects(route.get("parameters"), path + ".parameters", allow_empty=True)):
            p = f"{path}.parameters[{j}]"
            for key in ("name", "unit", "basis"):
                text(parameter.get(key), p + "." + key)
            enum(parameter.get("origin"), p + ".origin", ("user", "source", "hypothesis"))
            value = parameter.get("value")
            if "value" not in parameter:
                error(p + ".value", "Required, use null if unknown")
            elif value is not None and (isinstance(value, bool) or not isinstance(value, (int, float, str))):
                error(p + ".value", "Expected number, string or null")
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                try:
                    finite = math.isfinite(value)
                except OverflowError:
                    finite = False
                if not finite:
                    error(p + ".value", "Non-finite or unrepresentable values are not allowed")
    route_strings = [v for v in route_ids if isinstance(v, str)]
    if len(route_strings) != len(set(route_strings)):
        error("routes", "Duplicate route IDs")

    design = brief.get("design")
    if not isinstance(design, dict):
        error("design", "Expected object")
        design = {}
    for key in ("basis_g", "sample_base_g"):
        number(design.get(key), "design." + key, positive=True)
    number(design.get("wait_minutes"), "design.wait_minutes")
    if design.get("base_key") not in valid_keys:
        error("design.base_key", "Must reference an ingredient key")
    if not isinstance(design.get("native_control"), bool):
        error("design.native_control", "Expected boolean")
    for key in ("planned_batches", "seed"):
        value = design.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            error("design." + key, "Expected integer")
    batches = design.get("planned_batches")
    if isinstance(batches, int) and not isinstance(batches, bool) and not 1 <= batches <= 100:
        error("design.planned_batches", "Must be between 1 and 100")
    factor_keys, combination_count = [], 1
    for i, factor in enumerate(objects(design.get("factors"), "design.factors")):
        path = f"design.factors[{i}]"
        key = factor.get("key")
        factor_keys.append(key)
        if key not in valid_keys or key == design.get("base_key"):
            error(path + ".key", "Must reference a non-base ingredient key")
        enum(factor.get("origin"), path + ".origin", ("hypothesis", "source", "user"))
        text(factor.get("rationale"), path + ".rationale")
        levels = factor.get("levels_g")
        if not isinstance(levels, list) or not 2 <= len(levels) <= 20:
            error(path + ".levels_g", "Supply 2 to 20 levels")
            continue
        combination_count *= len(levels)
        for j, value in enumerate(levels):
            number(value, path + f".levels_g[{j}]")
        if all(isinstance(v, (int, float)) for v in levels) and len(set(levels)) != len(levels):
            error(path + ".levels_g", "Duplicate levels")
    constant_keys = []
    for i, constant in enumerate(objects(design.get("constants"), "design.constants", allow_empty=True)):
        key = constant.get("key")
        constant_keys.append(key)
        if key not in valid_keys or key == design.get("base_key"):
            error(f"design.constants[{i}].key", "Must reference a non-base ingredient key")
        number(constant.get("grams_per_basis"), f"design.constants[{i}].grams_per_basis")
    used = factor_keys + constant_keys
    used_strings = [v for v in used if isinstance(v, str)]
    if len(used_strings) != len(set(used_strings)):
        error("design", "Factor and constant keys must be unique and disjoint")
    if set(used_strings + ([design["base_key"]] if isinstance(design.get("base_key"), str) else [])) != set(valid_keys):
        error("design", "Every ingredient must occur exactly once as base, factor or constant")
    if combination_count > 512:
        error("design.factors", "More than 512 cells; split the screening stages explicitly")
    dims = design.get("dimensions")
    if not isinstance(dims, list) or not dims or not all(isinstance(d, str) and d.strip() for d in dims):
        error("design.dimensions", "Expected non-empty list of dimension names")
    elif len(dims) != len(set(dims)):
        error("design.dimensions", "Duplicate dimensions")
    elif any(t not in dims for t in target_names):
        error("design.dimensions", "Must include all user target dimensions")
    notes = design.get("preparation_notes")
    if not isinstance(notes, list) or not all(isinstance(v, str) and v.strip() for v in notes):
        error("design.preparation_notes", "Expected list of non-empty strings")
    return {"valid": not errors, "errors": errors, "warnings": warnings, "unresolved": unresolved,
            "meaning": "Input consistency only. Valid input does not validate flavor, safety or shelf-life."}


def require_valid(brief):
    result = validate_brief(brief)
    if not result["valid"]:
        raise ValidationError("; ".join(e["path"] + ": " + e["message"] for e in result["errors"]))
    return result
