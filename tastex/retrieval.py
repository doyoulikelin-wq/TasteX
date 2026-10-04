"""Deterministic, source-preserving retrieval for TasteX.

Retrieval is deliberately a recall operation, not an automatic identity resolver or
flavor scorer. Only an explicit brief reference_id selects the source identity.
All query pages are consumed; page snippets supplement, never replace, full text.
"""
from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import re
from typing import Any, Callable


_API_PATH = Path(__file__).resolve().parents[1] / "flavor-database" / "flavor_db.py"
_SPEC = importlib.util.spec_from_file_location("tastex_source_flavor_db", _API_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError("Cannot load the source database read-only API")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
FlavorDB = _MODULE.FlavorDB

PAGE_SIZE = 100
SEMANTICS = {
    "identity": "Reviewed aliases expand search only. Different IDs, varieties and processing states are never merged. An explicit reference ID is not proof that the requested material is equivalent.",
    "profile": "All formal source variants are retained. 0 means unmarked, null means unknown; neither is measured absence. Category counts are not sensory intensity. No canonical vector is used.",
    "context_links": "related_context links are listed separately; name matches still require condition and state review. No quantitative transfer is authorized.",
    "page_mentions": "Extracted page text is context, not diagram verification. A page can discuss several different ingredients. A hit is not an ingredient-specific fact or a direct pairing.",
    "pairings": "Only direct stored source rows are returned with their original direction. There is no transitive inference and no conversion into taste preference or success probability.",
    "negative_search": "Zero hits describe the present query and imported dataset; they do not prove absence in the book, literature or food itself.",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unique(values: list) -> list:
    return list(dict.fromkeys(values))


def _matches_term(query: str, term: str) -> bool:
    # ASCII word boundaries prevent e.g. 'kiwiberry' from expanding as 'kiwi'.
    if term.isascii():
        return re.search(r"(?<![A-Za-z0-9_])" + re.escape(term) + r"(?![A-Za-z0-9_])", query, re.I) is not None
    return term in query


def expand_queries(query: str, config: dict) -> tuple[list[str], list[dict]]:
    """Return original query, reviewed literal variants, and expansion provenance."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Ingredient query must be a non-empty string")
    query = query.strip()
    expanded = [query]
    applied = []
    for group in config.get("groups", []):
        if group.get("review_status") != "reviewed":
            continue
        terms = group.get("terms", [])
        if not isinstance(terms, list) or not all(isinstance(t, str) and t for t in terms):
            raise ValueError("Reviewed alias terms must be non-empty strings")
        matched = [term for term in terms if _matches_term(query, term)]
        if not matched:
            continue
        # If the request names an explicitly different identity (e.g. kiwi berry),
        # do not broaden it into the reference fruit automatically.
        blocked = [term for term in group.get("do_not_equate", [])
                   if term.casefold() == query.casefold() and ("莓" in term or "berry" in term.casefold())]
        if blocked:
            continue
        applied.append({"key": group["key"], "matched_terms": matched,
                        "scope": group.get("scope"), "basis": group.get("basis"),
                        "do_not_equate": group.get("do_not_equate", [])})
        # Preserve specific requests and also search reviewed base terms for
        # context. Both are navigation, not an assertion of state equivalence.
        for source in matched:
            for target in terms:
                expanded.append(re.sub(re.escape(source), lambda _m: target, query, flags=re.I))
        expanded.extend(terms)
    return _unique(expanded), applied


def _all_pages(fetch: Callable[..., dict], **kwargs: Any) -> tuple[list, list[dict]]:
    """Exhaust a paginated read API and fail rather than silently lose results."""
    items, batches = [], []
    offset = 0
    expected_total = None
    while True:
        result = fetch(limit=PAGE_SIZE, offset=offset, **kwargs)
        total = result["total"]
        if expected_total is None:
            expected_total = total
        elif expected_total != total:
            raise ValueError("Result count changed during read-only retrieval")
        batch = result["items"]
        batches.append({"offset": offset, "returned": len(batch), "total": total})
        items.extend(batch)
        if not result["has_more"]:
            break
        if not batch:
            raise ValueError("Paginated API reports more results but made no progress")
        offset += len(batch)
    if len(items) != expected_total:
        raise ValueError("Incomplete retrieval: returned count differs from reported total")
    return items, batches


def _group_links(links: list[dict]) -> dict:
    result = {"name_matched": [], "related_context": [], "other": []}
    for item in links:
        kind = item["link"].get("kind")
        key = "name_matched" if kind in ("exact_name", "alias_name") else "related_context" if kind == "related_context" else "other"
        result[key].append(item)
    return result


def _snippets(text: str, terms: list[str], radius: int = 85) -> list[dict]:
    """First occurrence per literal term for display; complete text is elsewhere."""
    result = []
    for term in terms:
        match = re.search(re.escape(term), text, re.I)
        if match:
            start, end = max(0, match.start() - radius), min(len(text), match.end() + radius)
            result.append({"term": term, "start": start, "end": end, "text": text[start:end],
                           "purpose": "display_excerpt_only"})
    return result


def collect_evidence(brief: dict, db_path: str | Path, aliases_path: str | Path) -> dict:
    """Collect complete source evidence without changing the immutable database.

    Query logs include zero results and pagination receipts. Reference-linked
    evidence is distinct from query-mentioned context. Source page text is kept
    in full, even when structured processing already has matches.
    """
    db_path, aliases_path = Path(db_path), Path(aliases_path)
    config = json.loads(aliases_path.read_text(encoding="utf-8"))
    if config.get("schema_version") != "1.0":
        raise ValueError("Unsupported search alias configuration schema")
    ingredients = brief.get("ingredients", [])
    if not ingredients:
        raise ValueError("Brief must contain at least one ingredient")
    keys = [item.get("key") for item in ingredients]
    if any(not isinstance(key, str) or not key for key in keys) or len(keys) != len(set(keys)):
        raise ValueError("Ingredient keys must be non-empty and unique")
    result = {"schema_version": "1.0", "ingredients": [], "queries": [], "gaps": [],
              "pair_probes": [], "provenance": {}, "semantics": SEMANTICS}
    with FlavorDB(db_path) as db:
        stats = db.stats()
        stats.pop("database", None)  # host-specific absolute paths break replay.
        integrity = [r[0] for r in db.connection.execute("PRAGMA integrity_check")]
        foreign_keys = [list(r) for r in db.connection.execute("PRAGMA foreign_key_check")]
        if integrity != ["ok"] or foreign_keys:
            raise ValueError("Source database integrity check failed")
        config_bytes = (json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        result["provenance"] = {"database_sha256": _sha256(db_path), "aliases_sha256": hashlib.sha256(config_bytes).hexdigest(),
            "alias_hash_basis": "UTF-8 JSON with sorted keys, indent=2, ensure_ascii=False, allow_nan=False, final newline; formatting-independent configuration identity",
            "database_schema_version": stats["schema_version"], "database_stats": stats,
            "integrity_check": integrity, "foreign_key_violations": foreign_keys,
            "alias_policy": config.get("policy"), "retrieval_version": "1.0",
            "source_scope": "Current imported source corpus; neither exhaustive literature search nor independent sensory validation."}

        def log(key: str, operation: str, params: dict, records: list, batches: list, ids: list) -> None:
            result["queries"].append({"ingredient_key": key, "operation": operation, "parameters": params,
                "total": len(records), "returned": len(records), "zero_hits": not records,
                "complete": True, "result_ids": ids, "pagination": batches})

        for item in ingredients:
            key, query = item["key"], item["query"]
            expanded, applied = expand_queries(query, config)
            ref = item.get("reference_id")
            entry = {"key": key, "input_query": query, "expanded_queries": expanded,
                "alias_expansions": applied, "candidate_ids": [], "candidates": [],
                "reference_id": ref, "requested_state": item.get("requested_state"),
                "identity_relation": item.get("identity_relation", "unresolved"),
                "reference_selection": "explicit_brief_reference" if ref else "unresolved_no_automatic_selection",
                "profile": None, "evidence_links": _group_links([]), "processing_links": _group_links([]),
                "evidence_records": [], "structured_processing_records": [], "page_hits": [],
                "direct_pairings": [], "retrieval_notes": []}
            matched_candidates: dict[str, list[str]] = {}
            evidence_hits: dict[str, list[str]] = {}
            processing_hits: dict[str, list[str]] = {}
            page_hits: dict[int, list[str]] = {}
            # Each query always reaches all four layers, including page text.
            for term in expanded:
                for kind in ("ingredient", "evidence", "page"):
                    hits, batches = _all_pages(db.search, query=term, kind=kind)
                    log(key, "search_" + kind, {"query": term}, hits, batches, [h["id"] for h in hits])
                    target = {"ingredient": matched_candidates, "evidence": evidence_hits, "page": page_hits}[kind]
                    for hit in hits:
                        hit_id = int(hit["id"]) if kind == "page" else hit["id"]
                        target.setdefault(hit_id, []).append(term)
                hits, batches = _all_pages(db.processing, query=term)
                log(key, "processing_text", {"query": term}, hits, batches, [h["id"] for h in hits])
                for hit in hits:
                    processing_hits.setdefault(hit["id"], []).append(term)

            for candidate_id in sorted(matched_candidates):
                row = db.connection.execute("SELECT * FROM ingredients WHERE id=?", (candidate_id,)).fetchone()
                raw = json.loads(row["raw_json"])
                entry["candidates"].append({"id": candidate_id, "source_name": row["original_name"],
                    "display_name": row["display_name"], "aliases": raw.get("aliases", []),
                    "recommendation_eligible": bool(row["recommendation_eligible"]),
                    "name_needs_review": bool(row["name_needs_review"]), "example_only": bool(row["example_only"]),
                    "matched_queries": _unique(matched_candidates[candidate_id]),
                    "identity_status": "explicit_reference_still_check_state" if candidate_id == ref else "unresolved_search_candidate",
                    "scope": "Search-text match only; separate IDs remain separate. Inspect source name and requested state before use."})
            entry["candidate_ids"] = [c["id"] for c in entry["candidates"]]
            if not entry["candidate_ids"]:
                result["gaps"].append({"ingredient_key": key, "kind": "no_ingredient_search_hits",
                    "detail": "No identity matches in this search; absence of evidence is not evidence of absence."})
            if ref:
                reference = db.ingredient(ref)  # invalid explicit IDs fail loudly.
                entry["reference_identity"] = {"id": ref, "source_name": reference["ingredient"]["name"],
                    "display_name": reference["ingredient"]["displayName"],
                    "recommendation_eligible": reference["ingredient"].get("recommendationEligible"),
                    "name_needs_review": reference["ingredient"].get("nameNeedsReview")}
                entry["profile"] = reference["profile"]
                entry["evidence_links"] = _group_links(reference["evidence_links"])
                entry["processing_links"] = _group_links(reference["processing_links"])
                log(key, "reference_evidence_links", {"ingredient_id": ref}, reference["evidence_links"], [],
                    [link["evidence"]["id"] for link in reference["evidence_links"]])
                for link in reference["evidence_links"]:
                    evidence_hits.setdefault(link["evidence"]["id"], [])
                links, batches = _all_pages(db.processing, ingredient_id=ref)
                log(key, "processing_reference", {"ingredient_id": ref}, links, batches, [p["id"] for p in links])
                for linked in links:
                    processing_hits.setdefault(linked["id"], [])
                pairings, batches = _all_pages(db.pairs, ingredient_id=ref, include_excluded=True)
                for pair in pairings:
                    table = db.connection.execute("SELECT pdf_page,book_page FROM source_tables WHERE id=?", (pair["table_id"],)).fetchone()
                    names = db.connection.execute("SELECT id,display_name FROM ingredients WHERE id IN (?,?) ORDER BY id",
                        (pair["main_ingredient_id"], pair["paired_ingredient_id"])).fetchall()
                    pair["source_pages"] = dict(table)
                    pair["ingredient_names"] = {r["id"]: r["display_name"] for r in names}
                log(key, "direct_pairings", {"ingredient_id": ref, "include_excluded": True}, pairings, batches, [p["id"] for p in pairings])
                entry["direct_pairings"] = pairings
                if ref not in matched_candidates:
                    result["gaps"].append({"ingredient_key": key, "kind": "reference_not_in_name_search",
                        "reference_id": ref, "detail": "The explicit reference is valid but no expanded query found it; identity correspondence needs review."})
            else:
                result["gaps"].append({"ingredient_key": key, "kind": "unresolved_reference",
                    "detail": "No source ID selected; candidates are not silently treated as the requested material."})

            for evidence_id in sorted(evidence_hits):
                record = db.evidence(evidence_id)
                matching_links = [link for link in record.get("links", []) if link.get("ingredientId") == ref] if ref else []
                entry["evidence_records"].append({"id": evidence_id, "matched_queries": _unique(evidence_hits[evidence_id]),
                    "matching_reference_links": matching_links, "record": record,
                    "interpretation": "Source evidence; query mentions and related_context are not identity-equivalent facts."})
            for processing_id in sorted(processing_hits):
                record = db.processing_record(processing_id)
                matching_links = [link for link in record.get("ingredientLinks", []) if link.get("ingredientId") == ref] if ref else []
                entry["structured_processing_records"].append({"id": processing_id,
                    "matched_queries": _unique(processing_hits[processing_id]), "matching_reference_links": matching_links,
                    "record": record, "interpretation": "Preserve source record_kind, all conditions and limitations; a mention does not establish an effect in the requested product."})
            for pdf_page in sorted(page_hits):
                page = db.page(pdf_page)
                text = page["page"]["text"]
                entry["page_hits"].append({"pdf_page": pdf_page, "book_page": None,
                    "book_page_policy": "Not inferred from PDF page offset; use explicit structured evidence or inspect the original page.",
                    "matched_queries": _unique(page_hits[pdf_page]), "full_text": text,
                    "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "page": page["page"], "display_excerpts": _snippets(text, _unique(page_hits[pdf_page])),
                    "interpretation": "page_context_only_requires_section_and_identity_review", "semantics": page["semantics"]})
            if not entry["structured_processing_records"]:
                result["gaps"].append({"ingredient_key": key, "kind": "no_structured_processing",
                    "page_hit_count": len(entry["page_hits"]),
                    "detail": "Structured processing retrieval has zero hits. Page text was still searched in full; absence in the processing layer cannot rule out source discussion."})
            if entry["identity_relation"] != "exact":
                result["gaps"].append({"ingredient_key": key, "kind": "state_or_identity_transfer_unvalidated",
                    "reference_id": ref, "requested_state": entry["requested_state"], "identity_relation": entry["identity_relation"],
                    "detail": "Source reference does not validate the actual ingredient batch, requested processing state, flavor intensity or dosage."})
            if entry["profile"]:
                uncertain = [c for c in entry["profile"]["categories"] if c["status"] in ("conflict", "unknown") or c["has_unknown"]]
                if uncertain:
                    result["gaps"].append({"ingredient_key": key, "kind": "profile_uncertainty",
                        "categories": [{k: c[k] for k in ("category_index", "display_name", "status", "unknown_count", "has_unknown")} for c in uncertain],
                        "detail": "Conflicts and unknowns are retained together; do not average or fill them."})
            entry["retrieval_notes"] = [SEMANTICS["identity"], SEMANTICS["context_links"], SEMANTICS["page_mentions"]]
            result["ingredients"].append(entry)

        references = [i for i in result["ingredients"] if i["reference_id"]]
        for left, right in itertools.combinations(references, 2):
            pairings, batches = _all_pages(db.pairs, ingredient_id=left["reference_id"], with_id=right["reference_id"], include_excluded=True)
            probe = {"ingredient_keys": [left["key"], right["key"]],
                "reference_ids": [left["reference_id"], right["reference_id"]],
                "identity_relations": [left["identity_relation"], right["identity_relation"]],
                "total": len(pairings), "zero_hits": not pairings, "source_rows": pairings,
                "recommendable_source_count": sum(bool(p["recommendation_eligible"]) and not p["is_example"] for p in pairings),
                "interpretation": SEMANTICS["pairings"]}
            result["pair_probes"].append(probe)
            log("|".join(probe["ingredient_keys"]), "direct_pair_probe",
                {"ingredient_id": left["reference_id"], "with_id": right["reference_id"], "include_excluded": True},
                pairings, batches, [p["id"] for p in pairings])
            if not pairings:
                result["gaps"].append({"ingredient_keys": probe["ingredient_keys"], "kind": "no_direct_pair_evidence",
                    "reference_ids": probe["reference_ids"],
                    "detail": "No direct source row found for these exact IDs. Other varieties, states or indirect paths do not establish this pair."})
    return result
