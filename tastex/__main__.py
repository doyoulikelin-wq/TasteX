"""Local JSON CLI. Errors go to stderr; every successful result is JSON."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
from .validation import ValidationError, validate_brief
from .workflow import DEFAULT_DB, DEFAULT_ALIASES, ROOT, read_json, run_case, replay, verify_run, file_sha


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValidationError(message)


def parser():
    p = Parser(description=__doc__)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--aliases", type=Path, default=DEFAULT_ALIASES)
    s = p.add_subparsers(dest="command", required=True)
    s.add_parser("doctor")
    q = s.add_parser("validate"); q.add_argument("brief", type=Path)
    q = s.add_parser("run"); q.add_argument("brief", type=Path); q.add_argument("--out", type=Path, required=True)
    q = s.add_parser("replay"); q.add_argument("run_dir", type=Path); q.add_argument("--out", type=Path, required=True)
    q = s.add_parser("verify-run"); q.add_argument("run_dir", type=Path)
    q = s.add_parser("experience"); q.add_argument("--store", type=Path, default=ROOT / "local/experience.sqlite")
    e = q.add_subparsers(dest="action", required=True)
    t = e.add_parser("record"); t.add_argument("observation", type=Path); t.add_argument("--run", type=Path, required=True)
    for action in ("search", "summarize"):
        t = e.add_parser(action); t.add_argument("--scope", required=True, help="JSON object with exact matrix, ingredient_state, process, serving_context")
        if action == "search": t.add_argument("--include-near", action="store_true")
    e.add_parser("verify")
    t = e.add_parser("analyze"); t.add_argument("run_dir", type=Path)
    return p


def doctor(db_path):
    if not db_path.is_file():
        raise ValidationError("Database missing. Run git lfs pull after cloning, or provide --db.")
    with db_path.open("rb") as stream:
        if stream.read(16) != b"SQLite format 3\x00":
            raise ValidationError("Database is not hydrated SQLite (possibly an LFS pointer). Run git lfs pull.")
    with closing(sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = db.execute("PRAGMA foreign_key_check").fetchall()
        counts = {name: db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in ("ingredients", "dot_records", "processing_records", "book_pages", "assets")}
    checksum = file_sha(db_path)
    reference = read_json(ROOT / "flavor-database/manifest.json")
    matched = checksum == reference["database"]["sha256"]
    if integrity != "ok" or foreign_keys or not matched:
        raise ValidationError("Database integrity, references or expected checksum failed")
    return {"ok": True, "database_sha256": checksum, "sqlite_version": sqlite3.sqlite_version, "counts": counts,
            "source_database_read_only": True, "flavor_prediction_validated": False}


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        if args.command == "doctor": result = doctor(args.db)
        elif args.command == "validate":
            result = validate_brief(read_json(args.brief))
            if not result["valid"]:
                print(json.dumps(result, ensure_ascii=False), file=sys.stderr)
                return 1
        elif args.command == "run": result = run_case(args.brief, args.out, db_path=args.db, aliases_path=args.aliases)
        elif args.command == "replay": result = replay(args.run_dir, args.out, db_path=args.db)
        elif args.command == "verify-run": result = {"verified": True, "manifest": verify_run(args.run_dir)}
        else:
            from .experience import ExperienceStore
            if args.action == "record":
                verify_run(args.run)
            with ExperienceStore(args.store) as store:
                if args.action == "record": result = store.record(read_json(args.observation), args.run)
                elif args.action == "verify": result = store.verify()
                elif args.action == "analyze": result = store.analyze(args.run_dir)
                else:
                    scope = json.loads(args.scope)
                    if args.action == "search": result = store.search(scope, include_near=args.include_near)
                    else: result = store.summarize(scope)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, TypeError, KeyError, OverflowError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"error": {"type": type(exc).__name__, "message": str(exc)}}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
