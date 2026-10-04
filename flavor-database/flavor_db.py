#!/usr/bin/env python3
"""Read-only, standard-library API and JSON CLI for the local flavor evidence database.

The database is evidence storage, not an intensity predictor. Source JSON, explicit
unknowns and independent source variants remain accessible. See AGENTS.md.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import time
from typing import Any

DEFAULT_DB = Path(__file__).with_name("flavor.sqlite")
DEFAULT_LIMIT = 50
MAX_LIMIT = 1000
MAX_SQL_LIMIT = 10000
SEMANTICS = (
    "Source dots encode source markings only: 1=marked, 0=unmarked, null=unknown. "
    "They are not concentration, sensory intensity, chemical absence, preference, or a recipe outcome. "
    "Large dots/shared_with_main apply only to that source table's ingredient pair. "
    "Name/context links do not authorize transferring measurements or process effects."
)
PROCESSING_FILTER_NAMES = (
    "query", "ingredient_id", "ingredient_name", "link_kind", "method", "effect", "domain", "direction", "source", "kind"
)


class FlavorDBError(Exception):
    """A caller-facing input or data lookup error."""


def _load(value: str | None) -> Any:
    return json.loads(value) if value is not None else None


def _like(query: str) -> str:
    """A literal substring LIKE pattern; %, _ and backslash are not wildcards."""
    return "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _pagination(limit: int, offset: int, maximum: int = MAX_LIMIT) -> tuple[int, int]:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= maximum:
        raise FlavorDBError(f"limit must be an integer from 1 to {maximum}")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise FlavorDBError("offset must be a non-negative integer")
    return limit, offset


def _page(items: list, total: int, limit: int, offset: int, **extra: Any) -> dict:
    return {
        "total": total, "limit": limit, "offset": offset, "returned": len(items),
        "has_more": offset + len(items) < total,
        "truncated": offset > 0 or offset + len(items) < total,
        "items": items, **extra,
    }


def _json_default(value: Any) -> dict:
    if isinstance(value, bytes):
        # Generic SQL may explicitly select a BLOB. Keep it JSON-compatible;
        # ordinary asset commands never return the image content implicitly.
        return {"encoding": "base64", "byte_size": len(value), "data": base64.b64encode(value).decode("ascii")}
    raise TypeError(f"Cannot encode {type(value).__name__}")


class FlavorDB:
    """A read-only connection. Use as ``with FlavorDB() as db: ...``.

    Public methods return JSON-serializable dictionaries. List methods always
    disclose pagination; profile returns every source variant without a mean.
    """

    def __init__(self, path: str | Path = DEFAULT_DB, *, sql_timeout: float = 5.0):
        self.path = Path(path).expanduser().resolve()
        if not self.path.is_file():
            raise FlavorDBError(f"Database does not exist: {self.path}")
        if not isinstance(sql_timeout, (int, float)) or not 0 < sql_timeout <= 60:
            raise FlavorDBError("sql_timeout must be greater than 0 and at most 60 seconds")
        self.sql_timeout = float(sql_timeout)
        self.connection = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=3)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA query_only=ON")
        # Extension loading is off by default. Explicitly keep it off when
        # supported, and also deny its SQL function in the query authorizer.
        try:
            self.connection.enable_load_extension(False)
        except (AttributeError, sqlite3.NotSupportedError):
            pass

    def __enter__(self) -> "FlavorDB":
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def close(self) -> None:
        self.connection.close()

    def _one(self, sql: str, params: tuple | list = ()) -> sqlite3.Row | None:
        return self.connection.execute(sql, params).fetchone()

    def _require_ingredient(self, ingredient_id: str) -> sqlite3.Row:
        row = self._one("SELECT * FROM ingredients WHERE id=?", (ingredient_id,))
        if row is None:
            raise FlavorDBError(f"Unknown ingredient ID: {ingredient_id}")
        return row

    def metadata(self, key: str | None = None) -> dict:
        if key is not None:
            row = self._one("SELECT value_json FROM metadata WHERE key=?", (key,))
            if row is None:
                raise FlavorDBError(f"Unknown metadata key: {key}")
            return {"key": key, "value": _load(row[0])}
        return {row["key"]: _load(row["value_json"]) for row in self.connection.execute("SELECT key,value_json FROM metadata ORDER BY key")}

    def stats(self) -> dict:
        tables = (
            "ingredients", "ingredient_aliases", "aroma_categories", "descriptors", "source_tables", "dot_records", "dot_values",
            "pairings", "attribute_evidence", "evidence_links", "reported_numbers", "processing_records", "processing_methods",
            "processing_effects", "processing_ingredient_names", "processing_links", "processing_numbers", "processing_audit", "sources", "assets", "source_snapshots", "book_pages",
        )
        counts = {name: self._one(f"SELECT COUNT(*) FROM {name}")[0] for name in tables}
        counts["recommendable_pairings"] = self._one("SELECT COUNT(*) FROM v_recommendable_pairings")[0]
        counts["processing_method_groups"] = self._one("SELECT COUNT(DISTINCT method_key) FROM processing_methods")[0]
        counts["processing_effect_groups"] = self._one("SELECT COUNT(DISTINCT group_key) FROM processing_effects")[0]
        counts["processing_ingredient_groups"] = self._one("SELECT COUNT(DISTINCT name_key) FROM processing_ingredient_names")[0]
        return {
            "database": str(self.path), "schema_version": self._one("PRAGMA user_version")[0], "counts": counts,
            "scope": "All data present in the imported local source snapshots; this does not claim exhaustive extraction of the PDF, independent scientific verification, or complete experimental raw datasets.",
            "semantics": SEMANTICS,
            "metadata_summary": {k: v for k, v in self.metadata().items() if k in ("schema_version", "scope", "null_semantics", "identity_policy", "profile_policy", "book_pages_policy", "pairing_policy", "asset_policy", "json_policy", "evidence_coverage", "processing_metrics", "processing_coverage", "processing_policies")},
            "metadata_keys": [r[0] for r in self.connection.execute("SELECT key FROM metadata ORDER BY key")],
        }

    def search(self, query: str, *, kind: str = "all", limit: int = DEFAULT_LIMIT, offset: int = 0) -> dict:
        limit, offset = _pagination(limit, offset)
        if kind not in ("all", "ingredient", "evidence", "processing", "page"):
            raise FlavorDBError("kind must be ingredient, evidence, processing, page, or all")
        where = "text LIKE ? ESCAPE '\\'"
        params: list[Any] = [_like(query)]
        if kind != "all":
            where += " AND kind=?"
            params.append("book_page" if kind == "page" else kind)
        total = self._one(f"SELECT COUNT(*) FROM search_documents WHERE {where}", params)[0]
        rows = self.connection.execute(
            f"SELECT kind,id,title FROM search_documents WHERE {where} ORDER BY kind,CASE WHEN kind='book_page' THEN CAST(id AS INTEGER) END,id LIMIT ? OFFSET ?", params + [limit, offset]
        ).fetchall()
        items = [{**dict(row), "kind": "page" if row["kind"] == "book_page" else row["kind"]} for row in rows]
        return _page(items, total, limit, offset, query=query, kind=kind,
                     matching="Literal substring over imported bilingual search text; a mention is not proof of attribute presence.")

    def page(self, pdf_page: int) -> dict:
        if isinstance(pdf_page, bool) or not isinstance(pdf_page, int) or pdf_page < 1:
            raise FlavorDBError("pdf_page must be a positive one-based PDF page number")
        row = self._one("SELECT raw_json FROM book_pages WHERE pdf_page=?", (pdf_page,))
        if row is None:
            raise FlavorDBError(f"Unknown PDF page: {pdf_page}")
        return {"pdf_page": pdf_page, "page": _load(row[0]),
                "semantics": "Extracted text from the numbered PDF page. Text extraction is not visual verification of diagrams/tables, and no printed book-page number is inferred."}

    def profile(self, ingredient_id: str, *, include_examples: bool = False) -> dict:
        ingredient = self._require_ingredient(ingredient_id)
        all_rows = self.connection.execute("SELECT * FROM dot_records WHERE ingredient_id=? ORDER BY id", (ingredient_id,)).fetchall()
        rows = [r for r in all_rows if include_examples or not r["is_example"]]
        values = self.connection.execute(
            "SELECT v.record_id,v.category_index,v.presence FROM dot_values v JOIN dot_records r ON r.id=v.record_id WHERE r.ingredient_id=? ORDER BY v.record_id,v.category_index", (ingredient_id,)
        ).fetchall()
        vectors: dict[str, list] = {r["id"]: [None] * 14 for r in all_rows}
        for v in values:
            vectors[v["record_id"]][v["category_index"]] = v["presence"]
        variants: dict[tuple, dict] = {}
        for row in rows:
            key = tuple(vectors[row["id"]])
            if key not in variants:
                variants[key] = {"presence": list(key), "source_record_ids": [], "source_refs": [], "record_count": 0}
            v = variants[key]
            v["source_record_ids"].append(row["id"])
            v["source_refs"].append({"table_id": row["table_id"], "record_id": row["id"], "pdf_page": row["pdf_page"], "book_page": row["book_page"]})
            v["record_count"] += 1
        categories = []
        for cat in self.connection.execute("SELECT * FROM aroma_categories ORDER BY category_index"):
            i = cat["category_index"]
            marked = [r["id"] for r in rows if vectors[r["id"]][i] == 1]
            unmarked = [r["id"] for r in rows if vectors[r["id"]][i] == 0]
            unknown = [r["id"] for r in rows if vectors[r["id"]][i] is None]
            status = "conflict" if marked and unmarked else "unknown" if unknown or not rows else "marked" if marked else "unmarked"
            categories.append({
                **dict(cat), "marked_count": len(marked), "unmarked_count": len(unmarked), "unknown_count": len(unknown),
                "record_count": len(rows), "status": status, "has_unknown": bool(unknown),
                "marked_source_ids": marked, "unmarked_source_ids": unmarked, "unknown_source_ids": unknown,
            })
        return {
            "ingredient_id": ingredient_id, "original_name": ingredient["original_name"], "display_name": ingredient["display_name"],
            "include_examples": include_examples, "source_record_count": len(all_rows), "record_count": len(rows),
            "excluded_example_ids": [r["id"] for r in all_rows if not include_examples and r["is_example"]],
            "source_record_ids": [r["id"] for r in rows], "variant_count": len(variants), "variants": list(variants.values()),
            "categories": categories, "source_records": [_load(r["raw_json"]) for r in rows],
            "basis": "all_selected_source_rows_without_canonical_fallback", "semantics": SEMANTICS,
        }

    def ingredient(self, ingredient_id: str) -> dict:
        row = self._require_ingredient(ingredient_id)
        links = self.connection.execute(
            "SELECT l.raw_json,e.id,e.ingredient_name,e.display_ingredient,e.state,e.attribute_type,e.pdf_page,e.book_page FROM evidence_links l JOIN attribute_evidence e ON e.id=l.evidence_id WHERE l.ingredient_id=? ORDER BY e.id,l.ordinal", (ingredient_id,)
        ).fetchall()
        processing = self.connection.execute(
            "SELECT l.raw_json,p.id,p.title,p.record_kind,p.source_kind FROM processing_links l JOIN processing_records p ON p.id=l.processing_id WHERE l.ingredient_id=? ORDER BY p.id,l.ordinal", (ingredient_id,)
        ).fetchall()
        return {
            "ingredient": _load(row["raw_json"]), "profile": self.profile(ingredient_id),
            "evidence_links": [{"evidence": {k: r[k] for k in r.keys() if k != "raw_json"}, "link": _load(r["raw_json"])} for r in links],
            "processing_links": [{"processing": {k: r[k] for k in r.keys() if k != "raw_json"}, "link": _load(r["raw_json"])} for r in processing],
            "assets": [self._asset_meta(r) for r in self.connection.execute("SELECT id,ingredient_id,relative_path,status,sha256,mime_type,byte_size,width,height,raw_json FROM assets WHERE ingredient_id=? ORDER BY id", (ingredient_id,))],
            "semantics": SEMANTICS,
        }

    def evidence(self, evidence_id: str) -> dict:
        row = self._one("SELECT raw_json FROM attribute_evidence WHERE id=?", (evidence_id,))
        if row is None:
            raise FlavorDBError(f"Unknown evidence ID: {evidence_id}")
        return _load(row[0])

    def pairs(self, ingredient_id: str, *, with_id: str | None = None, include_excluded: bool = False,
              limit: int = DEFAULT_LIMIT, offset: int = 0) -> dict:
        self._require_ingredient(ingredient_id)
        limit, offset = _pagination(limit, offset)
        where = "(main_ingredient_id=? OR paired_ingredient_id=?)"
        params: list[Any] = [ingredient_id, ingredient_id]
        if with_id is not None:
            self._require_ingredient(with_id)
            # A direct source row must explicitly name both IDs; no transitive
            # graph paths or category overlap become pair evidence.
            where = "((main_ingredient_id=? AND paired_ingredient_id=?) OR (main_ingredient_id=? AND paired_ingredient_id=?))"
            params = [ingredient_id, with_id, with_id, ingredient_id]
        all_total = self._one(f"SELECT COUNT(*) FROM pairings WHERE {where}", params)[0]
        if not include_excluded:
            where += " AND recommendation_eligible=1 AND is_example=0"
        total = self._one(f"SELECT COUNT(*) FROM pairings WHERE {where}", params)[0]
        rows = self.connection.execute(f"SELECT * FROM pairings WHERE {where} ORDER BY id LIMIT ? OFFSET ?", params + [limit, offset]).fetchall()
        items = [{**{k: r[k] for k in r.keys() if k != "raw_json"}, "record": _load(r["raw_json"])} for r in rows]
        return _page(items, total, limit, offset, ingredient_id=ingredient_id, with_id=with_id,
                     include_excluded=include_excluded, all_direct_source_rows=all_total, excluded_rows=all_total - total,
                     semantics="Direct table rows only. Shared dots refer to that table pair, not intensity, preference, causation, or a transitive relationship.")

    @staticmethod
    def _processing_where(*, query: str = "", ingredient_id: str | None = None, ingredient_name: str | None = None,
                          link_kind: str | list[str] | None = None, method: str | None = None, effect: str | None = None,
                          domain: str | None = None, direction: str | None = None, source: str | None = None,
                          kind: str | None = None) -> tuple[str, list]:
        terms = ["1=1"]
        params: list[Any] = []
        if query:
            terms.append("p.search_text LIKE ? ESCAPE '\\'")
            params.append(_like(query))
        if source is not None:
            if source not in ("book", "research"):
                raise FlavorDBError("source must be book or research")
            terms.append("p.source_kind=?")
            params.append(source)
        if kind is not None:
            if kind not in ("change", "condition_dependency", "state_profile"):
                raise FlavorDBError("kind must be change, condition_dependency, or state_profile")
            terms.append("p.record_kind=?")
            params.append(kind)
        if ingredient_id is not None or link_kind is not None:
            sub = ["l.processing_id=p.id"]
            if ingredient_id is not None:
                sub.append("l.ingredient_id=?")
                params.append(ingredient_id)
            if link_kind is not None:
                kinds = [link_kind] if isinstance(link_kind, str) else link_kind
                if not isinstance(kinds, list) or not kinds or not all(isinstance(k, str) and k for k in kinds):
                    raise FlavorDBError("link_kind must be a non-empty string or list of non-empty strings")
                sub.append("l.link_kind IN (" + ",".join("?" for _ in kinds) + ")")
                params.extend(kinds)
            terms.append("EXISTS (SELECT 1 FROM processing_links l WHERE " + " AND ".join(sub) + ")")
        if ingredient_name is not None:
            terms.append("EXISTS (SELECT 1 FROM processing_ingredient_names n WHERE n.processing_id=p.id AND (n.name_key=? OR n.label=?))")
            params.extend([ingredient_name, ingredient_name])
        if method is not None:
            terms.append("EXISTS (SELECT 1 FROM processing_methods m WHERE m.processing_id=p.id AND (m.method_key=? OR m.label=?))")
            params.extend([method, method])
        if effect is not None or domain is not None or direction is not None:
            sub = ["e.processing_id=p.id"]
            if effect is not None:
                sub.append("(e.group_key=? OR e.label=?)")
                params.extend([effect, effect])
            if domain is not None:
                sub.append("e.domain=?")
                params.append(domain)
            if direction is not None:
                sub.append("e.direction=?")
                params.append(direction)
            terms.append("EXISTS (SELECT 1 FROM processing_effects e WHERE " + " AND ".join(sub) + ")")
        return " AND ".join(terms), params

    def processing(self, *, query: str = "", ingredient_id: str | None = None, ingredient_name: str | None = None,
                   link_kind: str | list[str] | None = None, method: str | None = None, effect: str | None = None,
                   domain: str | None = None, direction: str | None = None, source: str | None = None,
                   kind: str | None = None, limit: int = DEFAULT_LIMIT, offset: int = 0) -> dict:
        filters = {k: v for k, v in locals().items() if k in PROCESSING_FILTER_NAMES}
        limit, offset = _pagination(limit, offset)
        if ingredient_id is not None:
            self._require_ingredient(ingredient_id)
        where, params = self._processing_where(**filters)
        total = self._one(f"SELECT COUNT(*) FROM processing_records p WHERE {where}", params)[0]
        rows = self.connection.execute(f"SELECT p.raw_json FROM processing_records p WHERE {where} ORDER BY p.id LIMIT ? OFFSET ?", params + [limit, offset]).fetchall()
        items = [_load(r[0]) for r in rows]
        matched_links = {}
        if ingredient_id is not None:
            allowed_kinds = ([link_kind] if isinstance(link_kind, str) else link_kind)
            for item in items:
                matched_links[item["id"]] = [link for link in item.get("ingredientLinks", [])
                    if link.get("ingredientId") == ingredient_id and (allowed_kinds is None or link.get("kind") in allowed_kinds)]
        return _page(items, total, limit, offset, filters=filters, matched_ingredient_links=matched_links,
                     ingredient_link_scope="All stored link kinds, including related_context, unless link_kind is explicitly limited. Matching links are listed separately; no quantitative transfer is authorized.",
                     semantics="Filters select whole records; every effect and condition is retained. Context links are not equivalent ingredient identities or permissions to transfer effects.")

    def processing_record(self, record_id: str) -> dict:
        row = self._one("SELECT raw_json FROM processing_records WHERE id=?", (record_id,))
        if row is None:
            raise FlavorDBError(f"Unknown processing record ID: {record_id}")
        return _load(row[0])

    def indexes(self, *, by: str, limit: int = DEFAULT_LIMIT, offset: int = 0, **filters: Any) -> dict:
        limit, offset = _pagination(limit, offset)
        if by not in ("method", "effect", "ingredient"):
            raise FlavorDBError("by must be method, effect, or ingredient")
        unexpected = set(filters) - set(PROCESSING_FILTER_NAMES)
        if unexpected:
            raise FlavorDBError("Unknown filters: " + ", ".join(sorted(unexpected)))
        if filters.get("ingredient_id") is not None:
            self._require_ingredient(filters["ingredient_id"])
        where, params = self._processing_where(**filters)
        population = [r[0] for r in self.connection.execute(f"SELECT p.id FROM processing_records p WHERE {where} ORDER BY p.id", params)]
        table, key_col = {"method": ("processing_methods", "method_key"), "effect": ("processing_effects", "group_key"), "ingredient": ("processing_ingredient_names", "name_key")}[by]
        extra = ",x.domain,x.direction" if by == "effect" else ""
        rows = self.connection.execute(
            f"SELECT x.{key_col} AS key,x.label,x.original_label,x.processing_id{extra} FROM {table} x JOIN processing_records p ON p.id=x.processing_id WHERE {where} ORDER BY x.{key_col},p.id,x.ordinal", params
        ).fetchall()
        groups: dict[str, dict] = {}
        for row in rows:
            key = row["key"]
            if key not in groups:
                groups[key] = {"key": key, "label": row["label"], "original_labels": [], "record_ids": [], "association_count": 0}
                if by == "effect":
                    groups[key].update(domain=row["domain"], direction=row["direction"])
            group = groups[key]
            group["association_count"] += 1
            if row["processing_id"] not in group["record_ids"]:
                group["record_ids"].append(row["processing_id"])
            if row["original_label"] is not None and row["original_label"] not in group["original_labels"]:
                group["original_labels"].append(row["original_label"])
        for group in groups.values():
            group["record_count"] = len(group["record_ids"])
        all_items = list(groups.values())
        return _page(all_items[offset:offset + limit], len(all_items), limit, offset, by=by, filters=filters,
                     population_record_count=len(population), population_record_ids=population,
                     association_count=len(rows), group_membership_count=sum(g["record_count"] for g in all_items),
                     semantics="Groups describe all index entries of the filtered record population. Each record is counted once within a group; groups overlap and their counts must not be summed as unique records.")

    @staticmethod
    def _asset_meta(row: sqlite3.Row) -> dict:
        return {**{k: row[k] for k in row.keys() if k not in ("content", "raw_json")}, "source_metadata": _load(row["raw_json"])}

    def asset(self, asset_or_ingredient_id: str, *, out: str | Path | None = None, force: bool = False) -> dict:
        columns = "id,ingredient_id,relative_path,status,sha256,mime_type,byte_size,width,height,raw_json"
        row = self._one(f"SELECT {columns} FROM assets WHERE id=?", (asset_or_ingredient_id,))
        if row is None:
            rows = self.connection.execute(f"SELECT {columns} FROM assets WHERE ingredient_id=? ORDER BY id", (asset_or_ingredient_id,)).fetchall()
            if len(rows) > 1:
                raise FlavorDBError("More than one asset is linked to this ingredient; use an exact asset ID from ingredient().assets")
            row = rows[0] if rows else None
        if row is None:
            raise FlavorDBError(f"Unknown asset or ingredient ID: {asset_or_ingredient_id}")
        result = self._asset_meta(row)
        if out is not None:
            target = Path(out).expanduser().absolute()
            if target.resolve() == self.path:
                raise FlavorDBError("Refusing to overwrite the database with an asset")
            if not target.parent.is_dir():
                raise FlavorDBError(f"Output directory does not exist: {target.parent}")
            if target.exists() and not force:
                raise FlavorDBError(f"Output already exists (use force=True / --force to replace): {target}")
            blob = self._one("SELECT content FROM assets WHERE id=?", (row["id"],))[0]
            if hashlib.sha256(blob).hexdigest() != row["sha256"]:
                raise FlavorDBError("Asset content hash does not match stored SHA-256")
            with target.open("wb" if force else "xb") as handle:
                handle.write(blob)
            result["output_path"] = str(target)
            result["written_bytes"] = len(blob)
        return result

    def source_snapshot(self, snapshot_id: str | None = None) -> dict:
        if snapshot_id is None:
            rows = self.connection.execute("SELECT id,relative_path,sha256 FROM source_snapshots ORDER BY id").fetchall()
            return {"total": len(rows), "items": [dict(r) for r in rows], "content_included": False}
        row = self._one("SELECT * FROM source_snapshots WHERE id=?", (snapshot_id,))
        if row is None:
            raise FlavorDBError(f"Unknown source snapshot ID: {snapshot_id}")
        return {"id": row["id"], "relative_path": row["relative_path"], "sha256": row["sha256"], "content": _load(row["content_json"])}

    @contextmanager
    def _restricted_sql(self):
        # Python 3.10 cannot reliably remove an authorizer with
        # set_authorizer(None). Isolate arbitrary SQL on a short-lived read-only
        # connection, leaving the regular API connection untouched on success,
        # denial and timeout. Closing also disposes of the progress callback.
        connection = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=3)
        deadline = time.monotonic() + self.sql_timeout
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
        unsafe_functions = {"load_extension", "readfile", "writefile", "edit", "shell", "eval", "fts3_tokenizer"}

        def authorizer(action, arg1, arg2, _database, _trigger):
            if action not in allowed:
                return sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_FUNCTION and (arg2 or arg1 or "").lower() in unsafe_functions:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            try:
                connection.enable_load_extension(False)
            except (AttributeError, sqlite3.NotSupportedError):
                pass
            connection.set_authorizer(authorizer)
            connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            yield connection
        finally:
            connection.close()

    def sql(self, query: str, *, params: list | dict | tuple | None = None, limit: int = 100) -> dict:
        limit, _ = _pagination(limit, 0, MAX_SQL_LIMIT)
        # The authorizer is the security boundary. This prefix check also keeps
        # confusing read-only-but-non-SELECT statements out of the public API.
        stripped = re.sub(r"\A(?:\s+|--[^\n]*(?:\n|$)|/\*.*?\*/)*", "", query, flags=re.S)
        if not re.match(r"\A(?:SELECT|WITH)\b", stripped, flags=re.I):
            raise FlavorDBError("Only a single SELECT or WITH ... SELECT statement is accepted")
        if params is None:
            params = []
        if not isinstance(params, (list, tuple, dict)):
            raise FlavorDBError("params must be a JSON array or object")
        with self._restricted_sql() as connection:
            try:
                cursor = connection.execute(query, params)
            except sqlite3.Warning as exc:
                # sqlite3.Warning is not a subclass of sqlite3.Error. Python
                # 3.10 uses it for multiple statements; newer Python versions
                # raise ProgrammingError. Normalize this API/CLI boundary.
                raise sqlite3.ProgrammingError(str(exc)) from exc
            if cursor.description is None:
                raise FlavorDBError("Query must return rows")
            columns = [col[0] for col in cursor.description]
            # Preserve duplicate column names without silently losing values.
            duplicate_columns = len(columns) != len(set(columns))
            rows = cursor.fetchmany(limit + 1)
            has_more = len(rows) > limit
            rows = rows[:limit]
            def json_value(value):
                return _json_default(value) if isinstance(value, bytes) else value
            items = [[json_value(v) for v in row] if duplicate_columns else {k: json_value(row[k]) for k in row.keys()} for row in rows]
        return {
            "columns": columns, "row_format": "array" if duplicate_columns else "object", "items": items,
            "returned": len(items), "limit": limit, "has_more": has_more, "truncated": has_more,
            "total": None, "total_note": "Not counted; has_more indicates whether the output limit was reached with additional rows.",
            "read_only": True, "timeout_seconds": self.sql_timeout,
        }


class JSONArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise FlavorDBError(message)


def _add_pagination(parser, default=DEFAULT_LIMIT):
    parser.add_argument("--limit", type=int, default=default)
    parser.add_argument("--offset", type=int, default=0)


def _add_processing_filters(parser):
    parser.add_argument("--query", default="", help="Literal substring in complete imported processing search text")
    parser.add_argument("--ingredient-id", help="Catalog ID; links can be exact, alias or related context")
    parser.add_argument("--ingredient-name", help="Exact key or label from the ingredient processing index")
    parser.add_argument("--link-kind", action="append", help="Exact processing link kind; repeat for OR, e.g. exact_name and alias_name")
    parser.add_argument("--method", help="Exact method index key or label")
    parser.add_argument("--effect", help="Exact effect group key or normalized label")
    parser.add_argument("--domain", help="Exact effect domain")
    parser.add_argument("--direction", help="Exact effect direction, jointly matched with domain/effect on one effect row")
    parser.add_argument("--source", choices=("book", "research"))
    parser.add_argument("--kind", choices=("change", "condition_dependency", "state_profile"))
    _add_pagination(parser)


def parser() -> argparse.ArgumentParser:
    p = JSONArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite database path; defaults next to this module")
    p.add_argument("--compact", action="store_true", help="Emit compact JSON")
    p.add_argument("--sql-timeout", type=float, default=5.0, help="Maximum seconds for custom SQL, 0 < n <= 60")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("stats", help="Counts, scope, metadata and interpretation boundaries")
    s = sub.add_parser("search", help="Search literal text without wildcard expansion")
    s.add_argument("query")
    s.add_argument("--kind", choices=("all", "ingredient", "evidence", "processing", "page"), default="all")
    _add_pagination(s)
    s = sub.add_parser("page", help="Extracted text for one PDF page; not visual verification")
    s.add_argument("pdf_page", type=int)
    s = sub.add_parser("ingredient", help="Full imported ingredient, all-source profile and evidence/context links")
    s.add_argument("ingredient_id")
    s = sub.add_parser("profile", help="All 14 categories, unknowns, conflicts and every distinct source vector")
    s.add_argument("ingredient_id")
    s.add_argument("--include-examples", action="store_true")
    s = sub.add_parser("evidence", help="Complete source evidence record, including original JSON")
    s.add_argument("evidence_id")
    s = sub.add_parser("pairs", help="Direct source pairing rows; default excludes ineligible/teaching rows")
    s.add_argument("ingredient_id")
    s.add_argument("--with-id")
    s.add_argument("--include-excluded", action="store_true")
    _add_pagination(s)
    s = sub.add_parser("processing", help="Filter processing records, preserving all effects and conditions")
    _add_processing_filters(s)
    s = sub.add_parser("processing-record", help="Complete processing record by ID")
    s.add_argument("record_id")
    s = sub.add_parser("indexes", help="Three cross-indexes for the same filtered processing population")
    s.add_argument("--by", choices=("method", "effect", "ingredient"), required=True)
    _add_processing_filters(s)
    s = sub.add_parser("asset", help="Asset metadata; export image only when --out is explicit")
    s.add_argument("asset_or_ingredient_id")
    s.add_argument("--out", type=Path)
    s.add_argument("--force", action="store_true")
    s = sub.add_parser("source-snapshot", help="List snapshots, or return a complete imported source JSON by ID")
    s.add_argument("snapshot_id", nargs="?")
    s = sub.add_parser("metadata", help="All metadata, or one JSON value by key")
    s.add_argument("key", nargs="?")
    s = sub.add_parser("sql", help="Bounded read-only SELECT/CTE with bound parameters; no extensions or ATTACH")
    group = s.add_mutually_exclusive_group(required=True)
    group.add_argument("--query")
    group.add_argument("--file", type=Path)
    s.add_argument("--params", default="[]", help="JSON array for ? parameters or object for named parameters")
    s.add_argument("--limit", type=int, default=100, help="Maximum returned rows (1..10000)")
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        args = vars(parser().parse_args(argv))
        command = args.pop("command").replace("-", "_")
        db_path = args.pop("db")
        compact = args.pop("compact")
        timeout = args.pop("sql_timeout")
        if command == "sql":
            file_path = args.pop("file")
            if file_path is not None:
                args["query"] = file_path.read_text(encoding="utf-8")
            args["params"] = json.loads(args["params"])
        with FlavorDB(db_path, sql_timeout=timeout) as db:
            result = getattr(db, command)(**args)
        print(json.dumps(result, ensure_ascii=False, indent=None if compact else 2, allow_nan=False, default=_json_default))
        return 0
    except (FlavorDBError, sqlite3.Error, OSError, ValueError, TypeError) as exc:
        print(json.dumps({"error": {"type": type(exc).__name__, "message": str(exc)}}, ensure_ascii=False), file=sys.stderr)
        return 1
    except BrokenPipeError:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
