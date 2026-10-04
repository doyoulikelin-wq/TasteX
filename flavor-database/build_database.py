#!/usr/bin/env python3
"""Build the portable, lossless Flavor SQLite database with Python stdlib only.

Input files are never modified. A complete temporary database is validated before
replacing the destination. Source snapshots retain the exact UTF-8 file text.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import struct
import tempfile
import unicodedata
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
SCHEMA_VERSION = "1.0.0"
BOOK_SOURCE_ID = "B-FOODPAIRING-2021"


def dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def json_cell(value):
    return None if value is None else dump(value)


def hash_bytes(value):
    return hashlib.sha256(value).hexdigest()


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def alias_key(value):
    # No transliteration or identity merging. Existing reviewed aliases are kept.
    return "".join(unicodedata.normalize("NFKC", value).casefold().split())


def insert(db, table, values):
    columns = ",".join(values)
    placeholders = ",".join("?" for _ in values)
    db.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", tuple(values.values()))


def bool_int(value):
    return int(bool(value))


def read_json(path):
    return json.loads(path.read_bytes().decode("utf-8"))


def source_row(source, **extra):
    return dict(id=source["id"], kind=source["kind"], title=source.get("title"),
                journal=source.get("journal"), year=source.get("year"), doi=source.get("doi"),
                url=source.get("url"), relative_path=extra.get("relative_path"),
                sha256=extra.get("sha256"), raw_json=dump(source))


def build(workspace, output):
    studio = workspace / "flavor-studio"
    data_dir = studio / "data"
    catalog = read_json(data_dir / "catalog.json")
    evidence = read_json(data_dir / "evidence-full.json")
    processing = read_json(data_dir / "processing.json")
    artwork = read_json(studio / "assets/manifest.json")
    book_pages_path = workspace / "tmp/pdfs/flavor_source/pages.json"
    book_pages = read_json(book_pages_path)
    ingredient_map = {r["id"]: r for r in catalog["ingredients"]}
    table_map = {r["id"]: r for r in catalog["tables"]}
    source_tables = {r["table_id"]: r for r in evidence["dotSource"]["tables"]}
    source_records = {r["row_id"]: r for r in evidence["dotSource"]["rows"]}
    records = {r["id"]: (ingredient["id"], r)
               for ingredient in catalog["ingredients"] for r in ingredient["records"]}
    if len(records) != sum(len(i["records"]) for i in catalog["ingredients"]):
        raise ValueError("Duplicate source record IDs in catalog")
    if set(records) != set(source_records) or set(table_map) != set(source_tables):
        raise ValueError("Catalog and original dot source coverage do not match")

    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=output.name + ".building-", suffix=".sqlite", dir=output.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    db = None
    try:
        db = sqlite3.connect(temporary)
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("PRAGMA synchronous=FULL")
        db.executescript((HERE / "schema.sql").read_text(encoding="utf-8"))
        db.execute("BEGIN")

        for index, name in enumerate(catalog["categories"]):
            insert(db, "aroma_categories", dict(category_index=index, source_name=name,
                   display_name=catalog["categoryDisplayNames"][index]))
        for ingredient in catalog["ingredients"]:
            insert(db, "ingredients", dict(id=ingredient["id"], original_name=ingredient["name"],
                   display_name=ingredient["displayName"], visual_family=ingredient.get("visualFamily"),
                   recommendation_eligible=bool_int(ingredient["recommendationEligible"]),
                   name_needs_review=bool_int(ingredient["nameNeedsReview"]), example_only=bool_int(ingredient["exampleOnly"]),
                   search_text=ingredient["searchText"], raw_json=dump(ingredient)))
            for alias in dict.fromkeys(ingredient["aliases"]):
                insert(db, "ingredient_aliases", dict(ingredient_id=ingredient["id"], alias=alias, alias_key=alias_key(alias)))
            insert(db, "search_documents", dict(kind="ingredient", id=ingredient["id"], title=ingredient["displayName"], text=ingredient["searchText"]))
        for table in catalog["tables"]:
            insert(db, "source_tables", dict(id=table["id"], main_ingredient_id=table["mainId"],
                   main_record_id=table["mainRecordId"], pdf_page=table.get("pdfPage"), book_page=table.get("bookPage"),
                   is_example=bool_int(table["isExample"]), review_status=table.get("reviewStatus"),
                   raw_json=dump(table), raw_source_json=dump(source_tables[table["id"]])))
        for record_id, (ingredient_id, row) in records.items():
            raw = source_records[record_id]
            if row["presence"] != raw["presence"] or row["sharedWithMain"] != raw["shared_with_main"]:
                raise ValueError(f"Source vector mismatch: {record_id}")
            if len(row["presence"]) != 14 or len(row["sharedWithMain"]) != 14:
                raise ValueError(f"Wrong category count: {record_id}")
            insert(db, "dot_records", dict(id=record_id, ingredient_id=ingredient_id, table_id=row["tableId"],
                   role=row["role"], main_ingredient_id=row.get("mainIngredientId"), pdf_page=row.get("pdfPage"),
                   book_page=row.get("bookPage"), is_example=bool_int(row["isExample"]),
                   identity_eligible=bool_int(row["identityEligible"]), review_status=row.get("reviewStatus"),
                   name_review_status=row.get("nameReviewStatus"), raw_json=dump(row), raw_source_json=dump(raw)))
            for index, (presence, shared) in enumerate(zip(row["presence"], row["sharedWithMain"])):
                insert(db, "dot_values", dict(record_id=record_id, category_index=index, presence=presence, shared_with_main=shared))

        edges = {r["id"]: (r, "catalog_edge") for r in catalog["edges"]}
        if len(edges) != len(catalog["edges"]):
            raise ValueError("Duplicate catalog edges")
        for record_id, (ingredient_id, row) in records.items():
            if row["role"] != "pairing" or record_id in edges:
                continue
            table = table_map[row["tableId"]]
            # Same recovery as engine-full.js; preserve all teaching rows.
            edge = dict(id=record_id, tableId=row["tableId"], mainId=row["mainIngredientId"],
                        pairedId=ingredient_id, shared=row["sharedWithMain"], presence=row["presence"],
                        sourceRef=row["sourceRef"], reviewStatus=row.get("reviewStatus"),
                        mainRecordId=table["mainRecordId"], isExample=row["isExample"],
                        sourceNamesEligible=bool(row["identityEligible"] and table.get("mainNameIdentityEligible") is not False),
                        recommendationEligible=bool(not row["isExample"] and row["identityEligible"] and table.get("recommendationEligible") is not False),
                        originalPairingRecord=row)
            edges[record_id] = (edge, "restored_original_pairing_row")
        for edge, provenance in edges.values():
            table = table_map[edge["tableId"]]
            row = records[edge["id"]][1]
            example = bool(edge.get("isExample") or table["isExample"] or row["isExample"])
            eligible = not example and edge.get("recommendationEligible") is not False
            eligible = eligible and edge.get("sourceNamesEligible") is not False and row["identityEligible"]
            eligible = eligible and table.get("mainNameIdentityEligible") is not False
            eligible = eligible and not ingredient_map[edge["mainId"]]["nameNeedsReview"] and not ingredient_map[edge["pairedId"]]["nameNeedsReview"]
            insert(db, "pairings", dict(id=edge["id"], table_id=edge["tableId"], main_record_id=edge.get("mainRecordId"),
                   paired_record_id=edge["id"], main_ingredient_id=edge["mainId"], paired_ingredient_id=edge["pairedId"],
                   is_example=bool_int(example), recommendation_eligible=bool_int(eligible), provenance_kind=provenance, raw_json=dump(edge)))

        for descriptor in evidence["facets"]["descriptors"]:
            insert(db, "descriptors", dict(id=descriptor["descriptor_id"], category_index=catalog["categories"].index(descriptor["category"]),
                   source_label=descriptor["descriptor"], display_label=descriptor["displayDescriptor"], raw_json=dump(descriptor)))
        for record in evidence["records"]:
            original = record["original"]
            insert(db, "attribute_evidence", dict(id=record["id"], ingredient_name=record.get("ingredientName"),
                   display_ingredient=record.get("displayIngredient"), state=original.get("state"), attribute_type=original.get("attribute_type"),
                   evidence_mode=original.get("evidence_mode"), pdf_page=original.get("pdf_page"), book_page=original.get("book_page"),
                   note=original.get("note"), search_text=record["searchText"], raw_json=dump(record), original_json=dump(original)))
            for ordinal, link in enumerate(record["links"]):
                insert(db, "evidence_links", dict(evidence_id=record["id"], ordinal=ordinal, ingredient_id=link["ingredientId"],
                       link_kind=link["kind"], reason=link.get("reason"), raw_json=dump(link)))
            for domain in dict.fromkeys(record["domains"]):
                insert(db, "evidence_domains", dict(evidence_id=record["id"], domain=domain))
            for ordinal, mention in enumerate(record["descriptorMentions"]):
                insert(db, "descriptor_mentions", dict(evidence_id=record["id"], ordinal=ordinal, descriptor_id=mention["descriptorId"],
                       interpretation=mention["interpretation"], raw_json=dump(mention)))
            insert(db, "search_documents", dict(kind="evidence", id=record["id"], title=record.get("displayIngredient", record["id"]), text=record["searchText"]))
        for ordinal, number in enumerate(evidence["numbers"]):
            insert(db, "reported_numbers", dict(id=f"N{ordinal+1:04d}", evidence_id=number["recordId"], metric=number.get("attribute"),
                   unit=number.get("unit"), value_json=json_cell(number.get("value")), minimum_json=json_cell(number.get("minimum")),
                   maximum_json=json_cell(number.get("maximum")), operator=number.get("operator"), denominator=number.get("denominator"),
                   pdf_page=number.get("pdf_page"), book_page=number.get("book_page"), raw_json=dump(number)))

        pdf_relative = catalog["meta"]["sourcePdf"]
        pdf_path = workspace / pdf_relative
        if not pdf_path.is_file():
            raise FileNotFoundError(f"Original PDF required to record its actual hash: {pdf_path}")
        pdf_sha256 = file_hash(pdf_path)
        book_source = dict(id=BOOK_SOURCE_ID, kind="book", title="食物風味搭配科學", year=2021,
                           edition="繁體中文版", localPdf=pdf_relative, pdfSha256=pdf_sha256,
                           scope="仅索引当前提取的数据，未声称穷尽全书；原 PDF 未嵌入数据库。")
        insert(db, "sources", source_row(book_source, relative_path=pdf_relative, sha256=pdf_sha256))
        for source in processing["references"]:
            extra = dict(relative_path=pdf_relative, sha256=pdf_sha256) if source["kind"] == "book" else {}
            insert(db, "sources", source_row(source, **extra))
        for record in processing["records"]:
            source = record["source"]
            insert(db, "processing_records", dict(id=record["id"], title=record["title"], record_kind=record["recordKind"],
                   before_state=record.get("before"), after_state=record.get("after"), conditions=record.get("conditions"),
                   mechanism=record.get("mechanism"), summary=record.get("summary"), limitations=record.get("limitations"),
                   evidence_level=record.get("evidenceLevel"), source_kind=source["kind"], source_id=source.get("id") or BOOK_SOURCE_ID,
                   search_text=record["searchText"], raw_json=dump(record), source_json=dump(source), original_json=dump(record.get("original"))))
            for ordinal, method in enumerate(record["methodIndexEntries"]):
                insert(db, "processing_methods", dict(processing_id=record["id"], ordinal=ordinal, method_key=method["key"],
                       label=method["label"], original_label=method.get("originalLabel")))
            for ordinal, effect in enumerate(record["normalizedEffects"]):
                insert(db, "processing_effects", dict(processing_id=record["id"], ordinal=ordinal, domain=effect["domain"],
                       label=effect["label"], original_label=effect.get("originalLabel"), direction=effect["direction"],
                       group_key=effect["groupKey"], detail=effect.get("detail"), raw_json=dump(effect)))
            for ordinal, name in enumerate(record["ingredientIndexEntries"]):
                insert(db, "processing_ingredient_names", dict(processing_id=record["id"], ordinal=ordinal,
                       name_key=name["key"], label=name["label"], original_label=name.get("originalLabel")))
            for ordinal, link in enumerate(record["ingredientLinks"]):
                insert(db, "processing_links", dict(processing_id=record["id"], ordinal=ordinal, ingredient_id=link["ingredientId"],
                       link_kind=link["kind"], reason=link.get("reason"), raw_json=dump(link)))
            for evidence_id in dict.fromkeys(source.get("evidenceIds", [])):
                insert(db, "processing_evidence", dict(processing_id=record["id"], evidence_id=evidence_id))
            for ordinal, number in enumerate(record["reportedValues"]):
                insert(db, "processing_numbers", dict(processing_id=record["id"], ordinal=ordinal, metric=number.get("metric", number.get("attribute")),
                       value_json=json_cell(number.get("value")), unit=number.get("unit"), context=number.get("context", number.get("note")),
                       minimum_json=json_cell(number.get("minimum")), maximum_json=json_cell(number.get("maximum")),
                       operator=number.get("operator"), denominator=number.get("denominator"), raw_json=dump(number)))
            insert(db, "search_documents", dict(kind="processing", id=record["id"], title=record["title"], text=record["searchText"]))
        for audit in processing["audit253"]:
            insert(db, "processing_audit", dict(evidence_id=audit["evidenceId"], decision=audit["decision"], reason=audit.get("reason"),
                   record_ids_json=dump(audit["recordIds"]), raw_json=dump(audit)))

        for asset in artwork["assets"]:
            content = (studio / asset["path"]).read_bytes()
            digest = hash_bytes(content)
            if digest != asset["sha256"] or len(content) != asset["bytes"]:
                raise ValueError(f"Asset content differs from original manifest: {asset['id']}")
            insert(db, "assets", dict(id=asset["id"], ingredient_id=asset["id"], relative_path="flavor-studio/"+asset["path"],
                   status=asset["status"], sha256=digest, mime_type="image/svg+xml", byte_size=len(content),
                   width=asset.get("width"), height=asset.get("height"), content=content, raw_json=dump(asset)))
        hero_path = studio / "assets/generated/strawberry-editorial.png"
        content = hero_path.read_bytes()
        if content[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Hero asset is not a PNG")
        width, height = struct.unpack(">II", content[16:24])
        insert(db, "assets", dict(id="hero-strawberry", ingredient_id=None, relative_path=str(hero_path.relative_to(workspace)),
               status="ai_generated_editorial", sha256=hash_bytes(content), mime_type="image/png", byte_size=len(content),
               width=width, height=height, content=content, raw_json=dump(read_json(hero_path.parent / "generation-record.json"))))

        for page in book_pages:
            insert(db, "book_pages", dict(pdf_page=page["pdf_page"], text=page["text"], width=page.get("width"),
                   height=page.get("height"), raw_json=dump(page)))
            insert(db, "search_documents", dict(kind="book_page", id=str(page["pdf_page"]),
                   title=f"PDF 第 {page['pdf_page']} 页", text=page["text"]))

        snapshot_ids = {
            "flavor-studio/data/catalog.json": "catalog", "flavor-studio/data/evidence-full.json": "evidence-full",
            "flavor-studio/data/processing.json": "processing", "flavor-studio/data/processing-book.json": "processing-book",
            "flavor-studio/data/processing-research.json": "processing-research", "flavor-studio/assets/manifest.json": "asset-manifest",
            evidence["coverage"]["sourceFile"]: "attribute-source", evidence["coverage"]["rawDotSourceFile"]: "dot-source",
            "tmp/pdfs/flavor_source/pages.json": "book-pages",
        }
        snapshot_paths = set(data_dir.glob("*.json"))
        snapshot_paths.update(studio / p for p in ["assets/manifest.json", "assets/art-validation.json", "assets/contact-sheet-items.json", "assets/generated/generation-record.json"])
        snapshot_paths.update(workspace / p for p in [evidence["coverage"]["sourceFile"], evidence["coverage"]["rawDotSourceFile"]])
        snapshot_paths.add(book_pages_path)
        snapshots = []
        for path in sorted(snapshot_paths):
            content = path.read_bytes()
            text = content.decode("utf-8")
            parsed = json.loads(text)
            relative = str(path.relative_to(workspace))
            snapshot_id = snapshot_ids.get(relative, "file:" + relative)
            if snapshot_id == "attribute-source" and parsed != evidence["source"]:
                raise ValueError("Original attribute source has changed since evidence build")
            if snapshot_id == "dot-source" and parsed != evidence["dotSource"]:
                raise ValueError("Original dot source has changed since evidence build")
            row = dict(id=snapshot_id, relative_path=relative, sha256=hash_bytes(content), content_json=text)
            insert(db, "source_snapshots", row)
            snapshots.append({k: row[k] for k in ("id", "relative_path", "sha256")})

        # FTS is an accelerator only. LIKE queries must remain usable on systems
        # without trigram FTS5, including two-character Chinese queries.
        fts = dict(available=False, tokenizer=None, fallback="LIKE over search_documents.text")
        try:
            db.execute("CREATE VIRTUAL TABLE search_fts USING fts5(kind UNINDEXED,id UNINDEXED,title,text,content='search_documents',content_rowid='rowid',tokenize='trigram')")
            db.execute("INSERT INTO search_fts(search_fts) VALUES('rebuild')")
            fts.update(available=True, tokenizer="trigram")
        except sqlite3.OperationalError as error:
            fts["reason"] = str(error)

        metadata = {
            "schema_version": SCHEMA_VERSION,
            "database_role": "read_only_agent_evidence_database",
            "scope": "当前工作台数据的无损数据库版本；全书未穷尽提取，论文保存研究摘要与条件而非全部原始实验点。",
            "category_index_base": 0,
            "ordinal_index_base": 0,
            "book_source_id": BOOK_SOURCE_ID,
            "null_semantics": {"dot_values": "SQL NULL=图像无法可靠判断；主行shared_with_main不适用亦为NULL，结合role解读", "numeric_json_columns": "无数值存SQL NULL；完整raw_json保留字段缺失与显式null差异"},
            "identity_policy": "保持原始食材ID独立；别名只用于检索；related_context不等于相同食材，禁止数值转移。",
            "profile_policy": "v_ingredient_aroma_profile使用全部非教学原行，不采用catalog的历史canonical向量。",
            "book_pages_policy": "392页PDF提取文字用于追查原文；不推算印刷页码，提取文字/OCR不能替代原页图像核验。width/height保留原提取单位pt。",
            "pairing_policy": "保留catalog所有9480条关系及10条原教学配料行；推荐资格按engine-full.js的来源、身份及教学规则核定。",
            "asset_policy": "1474个原本地SVG插画加1张ImageGen草莓PNG；不是1474张照片；非感官测量。",
            "json_policy": "raw_json保留完整来源对象语义；source_snapshots.content_json保留原文件UTF-8文本，sha256针对原字节。",
            "catalog_meta": catalog["meta"], "catalog_conflicts": catalog["conflicts"],
            "evidence_coverage": evidence["coverage"], "evidence_policies": evidence["policies"],
            "processing_metrics": processing["metrics"], "processing_labels": processing["labels"],
            "processing_coverage": processing["coverage"], "processing_policies": processing["policies"],
            "processing_normalization": processing["normalization"], "search_features": fts,
        }
        for key, value in metadata.items():
            insert(db, "metadata", dict(key=key, value_json=dump(value)))
        db.commit()
        integrity = db.execute("PRAGMA integrity_check").fetchall()
        foreign_keys = db.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != [("ok",)] or foreign_keys:
            raise ValueError(f"Database integrity check failed: {integrity}; FK: {foreign_keys[:10]}")
        counts = {table: db.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
                  for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'search_fts%' AND name NOT LIKE 'sqlite_%' ORDER BY name")}
        expected = dict(ingredients=len(catalog["ingredients"]), source_tables=len(catalog["tables"]),
                        dot_records=len(source_records), dot_values=len(source_records)*14,
                        pairings=sum(r["role"] == "pairing" for _, r in records.values()),
                        attribute_evidence=len(evidence["records"]), descriptors=len(evidence["facets"]["descriptors"]),
                        reported_numbers=len(evidence["numbers"]), processing_records=len(processing["records"]),
                        processing_audit=len(processing["audit253"]), assets=len(artwork["assets"])+1,book_pages=len(book_pages))
        for key, value in expected.items():
            if counts[key] != value:
                raise ValueError(f"Coverage mismatch for {key}: {counts[key]} != {value}")
        metrics = {
            "recommendation_ingredients": db.execute("SELECT count(*) FROM ingredients WHERE recommendation_eligible=1").fetchone()[0],
            "recommendation_pairings": db.execute("SELECT count(*) FROM v_recommendable_pairings").fetchone()[0],
            "restored_pairings": db.execute("SELECT count(*) FROM pairings WHERE provenance_kind='restored_original_pairing_row'").fetchone()[0],
            "unknown_presence_cells": db.execute("SELECT count(*) FROM dot_values WHERE presence IS NULL").fetchone()[0],
            "teaching_rows": db.execute("SELECT count(*) FROM dot_records WHERE is_example=1").fetchone()[0],
            "processing_method_groups": db.execute("SELECT count(DISTINCT method_key) FROM processing_methods").fetchone()[0],
            "processing_effect_groups": db.execute("SELECT count(DISTINCT group_key) FROM processing_effects").fetchone()[0],
            "processing_ingredient_groups": db.execute("SELECT count(DISTINCT name_key) FROM processing_ingredient_names").fetchone()[0],
            "research_studies": db.execute("SELECT count(*) FROM sources WHERE kind='research'").fetchone()[0],
        }
        db.execute("ANALYZE")
        db.commit()
        db.close()
        db = None
        manifest = {
            "schema_version": SCHEMA_VERSION, "built_at_utc": datetime.now(timezone.utc).isoformat(),
            "database": {"path": output.name, "sha256": file_hash(temporary), "byte_size": temporary.stat().st_size},
            "schema": {"path": "schema.sql", "sha256": file_hash(HERE / "schema.sql")},
            "builder": {"path": "build_database.py", "sha256": file_hash(HERE / "build_database.py")},
            "runtime": {"sqlite_version": sqlite3.sqlite_version, "python_stdlib_only": True, "search": fts},
            "counts": counts, "metrics": metrics, "integrity_check": "ok", "foreign_key_violations": 0,
            "source_snapshots": snapshots,
            "original_pdf": {"relative_path": pdf_relative, "sha256": pdf_sha256, "embedded": False},
            "scope": metadata["scope"], "asset_policy": metadata["asset_policy"],
            "read_only": "Agents should open using URI mode=ro. Database contains no user recipe storage or UI localStorage.",
        }
        manifest_path = output.parent / "manifest.json"
        fd, manifest_temporary_name = tempfile.mkstemp(prefix="manifest.building-", suffix=".json", dir=output.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, output)
        os.replace(manifest_temporary_name, manifest_path)
        return manifest
    except BaseException:
        if db is not None:
            db.close()
        temporary.unlink(missing_ok=True)
        Path(str(temporary) + "-journal").unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=HERE.parent, help="Directory containing flavor-studio and original PDF")
    parser.add_argument("--output", type=Path, default=HERE / "flavor.sqlite", help="Destination database; manifest.json is written beside it")
    args = parser.parse_args()
    manifest = build(args.workspace.resolve(), args.output.resolve())
    print(json.dumps({"database": manifest["database"], "counts": manifest["counts"], "metrics": manifest["metrics"], "integrity_check": "ok"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
