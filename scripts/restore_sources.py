#!/usr/bin/env python3
"""Restore exact embedded source snapshots (and optional assets) to an explicit directory.

Never restores the original PDF, writes the source database, or grants rights to
source content. Existing files and unsafe paths are rejected before any writes.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "flavor-database" / "flavor.sqlite"


def safe_destination(root: Path, relative_path: str) -> Path:
    """Reject traversal, absolute/drive paths, and any existing symlink component."""
    if not isinstance(relative_path, str) or not relative_path or "\\" in relative_path or "\0" in relative_path:
        raise ValueError("Invalid relative path")
    path = PurePosixPath(relative_path)
    if path.is_absolute() or re.match(r"^[A-Za-z]:", relative_path) or any(p in ("..", ".") for p in relative_path.split("/")):
        raise ValueError(f"Unsafe source path: {relative_path}")
    if any(not p for p in relative_path.split("/")):
        raise ValueError(f"Empty source path component: {relative_path}")
    root = root.resolve()
    target = root.joinpath(*path.parts)
    cursor = root
    for part in path.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"Symlink destination is not allowed: {relative_path}")
    if not target.resolve().is_relative_to(root):
        raise ValueError(f"Source path escapes destination: {relative_path}")
    return target


def restore_sources(db_path: str | Path, target_dir: str | Path, *, include_assets: bool = False,
                    dry_run: bool = False) -> dict:
    """Restore using exclusive file creation; preflight the complete plan first."""
    db_path = Path(db_path).resolve()
    if not db_path.is_file():
        raise ValueError("Source database does not exist")
    target_dir = Path(target_dir).expanduser().resolve()
    if target_dir.exists() and not target_dir.is_dir():
        raise ValueError("Target must be a directory")
    plan = []
    with closing(sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        for row in db.execute("SELECT id,relative_path,sha256,content_json FROM source_snapshots ORDER BY relative_path"):
            data = row["content_json"].encode("utf-8")
            json.loads(data)  # require valid JSON while retaining original bytes.
            plan.append({"kind": "source_snapshot", "id": row["id"], "relative_path": row["relative_path"],
                         "sha256": row["sha256"], "data": data})
        if include_assets:
            for row in db.execute("SELECT id,relative_path,sha256,content,byte_size FROM assets ORDER BY relative_path"):
                if len(row["content"]) != row["byte_size"]:
                    raise ValueError(f"Asset byte length differs: {row['id']}")
                plan.append({"kind": "asset", "id": row["id"], "relative_path": row["relative_path"],
                             "sha256": row["sha256"], "data": row["content"]})
    seen = set()
    for item in plan:
        relative = item["relative_path"]
        if relative.lower().endswith(".pdf"):
            raise ValueError("PDF restoration is not supported")
        destination = safe_destination(target_dir, relative)
        if destination in seen:
            raise ValueError(f"Duplicate destination: {relative}")
        seen.add(destination)
        if destination.exists():
            raise FileExistsError(f"Refusing to overwrite existing file: {relative}")
        if hashlib.sha256(item["data"]).hexdigest() != item["sha256"]:
            raise ValueError(f"Embedded content hash differs: {item['id']}")
        for parent in destination.parents:
            if parent == target_dir:
                break
            if parent.exists() and not parent.is_dir():
                raise ValueError(f"Destination parent is not a directory: {relative}")
    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)
        for item in plan:
            destination = safe_destination(target_dir, item["relative_path"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Recheck after mkdir; exclusive creation also rejects a leaf symlink.
            destination = safe_destination(target_dir, item["relative_path"])
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            flags |= getattr(os, "O_NOFOLLOW", 0)
            with os.fdopen(os.open(destination, flags, 0o644), "wb") as handle:
                handle.write(item["data"])
    return {"success": True, "dry_run": dry_run, "target": str(target_dir),
            "source_snapshots": sum(i["kind"] == "source_snapshot" for i in plan),
            "assets": sum(i["kind"] == "asset" for i in plan),
            "total_bytes": sum(len(i["data"]) for i in plan), "original_pdf_restored": False,
            "files": [{k: v for k, v in item.items() if k != "data"} for item in plan],
            "scope": "Byte-exact restoration of embedded source copies; no independent extraction validation or source-content license is granted."}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="Explicit destination directory; existing files are never overwritten")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--assets", action="store_true", help="Also restore embedded local image assets")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(restore_sources(args.db, args.target, include_assets=args.assets, dry_run=args.dry_run), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, sqlite3.Error) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
