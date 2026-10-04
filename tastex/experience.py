"""Append-only sensory observations, separate from the source evidence database.

Hashes establish internal consistency, not that a human actually tasted a sample.
No third-party libraries are required.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import tempfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path, PurePosixPath


SCHEMA_VERSION = "1.0"
SCOPE_KEYS = ("matrix", "ingredient_state", "process", "serving_context")
ID_KEYS = ("observation_id", "case_id", "revision", "run_id", "batch_id", "cell_id", "participant_id")
FIELDS = set(ID_KEYS) | {"schema_version", "observed_at", "scope", "material_lots", "actual_masses_g", "ratings", "scale", "free_description", "disposition", "notes", "origin", "supersedes"}
PLACEHOLDERS = {"unknown", "null", "none", "n/a", "na", "tbd", "todo", "待填", "待填写", "未填写", "未提供", "未知", "请输入"}
FILTER_KEYS = set(SCOPE_KEYS) | set(ID_KEYS) - {"observation_id"}
ZERO_HASH = "0" * 64


class ExperienceError(ValueError):
    """An observation, run or ledger failed validation."""


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def _text(value, label, nonempty=True):
    if not isinstance(value, str):
        raise ExperienceError(f"{label} must be a string")
    if nonempty and (not value.strip() or value != value.strip() or value.casefold() in PLACEHOLDERS or "待填" in value):
        raise ExperienceError(f"{label} must contain an actual value, not a placeholder")
    if "\x00" in value:
        raise ExperienceError(f"{label} contains a null byte")
    return value


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
        raise ExperienceError(f"{label} must be a finite nonnegative number")
    return value


def _hash(value, label):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ExperienceError(f"{label} must be a lowercase SHA-256")
    return value


def _load_json(path):
    try:
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ExperienceError(f"duplicate JSON field: {key}")
                result[key] = value
            return result
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique,
                          parse_constant=lambda x: (_ for _ in ()).throw(ExperienceError(f"invalid JSON number {x}")))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExperienceError(f"cannot read {path.name}: {exc}") from exc


def _safe_artifact(root, name):
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise ExperienceError("invalid artifact path")
    relative = PurePosixPath(name)
    if relative.is_absolute() or ".." in relative.parts or name != relative.as_posix() or ":" in name:
        raise ExperienceError(f"unsafe artifact path: {name}")
    path = root.joinpath(*relative.parts)
    if not path.resolve().is_relative_to(root) or any(part.is_symlink() for part in [path, *path.parents] if part != root and part.is_relative_to(root)):
        raise ExperienceError(f"artifact must not escape the run or use a symlink: {name}")
    if not path.is_file():
        raise ExperienceError(f"missing artifact: {name}")
    return path


def _validate_shape(obs):
    if not isinstance(obs, dict) or set(obs) != FIELDS:
        missing = sorted(FIELDS - set(obs)) if isinstance(obs, dict) else sorted(FIELDS)
        extra = sorted(set(obs) - FIELDS, key=str) if isinstance(obs, dict) else []
        raise ExperienceError(f"observation fields mismatch; missing={missing}; extra={extra}")
    if obs["schema_version"] != SCHEMA_VERSION:
        raise ExperienceError("unsupported observation schema_version")
    for key in ID_KEYS:
        _text(obs[key], key)
    _text(obs["observed_at"], "observed_at")
    try:
        stamp = datetime.fromisoformat(obs["observed_at"].replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("timezone missing")
    except ValueError as exc:
        raise ExperienceError("observed_at must be an ISO-8601 timestamp with timezone") from exc
    if not isinstance(obs["scope"], dict) or set(obs["scope"]) != set(SCOPE_KEYS):
        raise ExperienceError("scope must contain exactly matrix, ingredient_state, process, serving_context")
    for key in SCOPE_KEYS:
        _text(obs["scope"][key], f"scope.{key}")
    for field in ("material_lots", "actual_masses_g", "ratings"):
        if not isinstance(obs[field], dict):
            raise ExperienceError(f"{field} must be an object")
        for key in obs[field]:
            _text(key, f"{field} key")
    for key, value in obs["material_lots"].items():
        if value is not None:
            _text(value, f"material_lots.{key}")
    for key, value in obs["actual_masses_g"].items():
        _number(value, f"actual_masses_g.{key}")
    for key, value in obs["ratings"].items():
        if value is not None:
            if _number(value, f"ratings.{key}") > 10:
                raise ExperienceError(f"ratings.{key} must be within 0..10")
    if not isinstance(obs["scale"], dict) or set(obs["scale"]) != {"min", "max"} or isinstance(obs["scale"]["min"], bool) or isinstance(obs["scale"]["max"], bool) or obs["scale"] != {"min": 0, "max": 10}:
        raise ExperienceError("scale must be {min: 0, max: 10}")
    for key in ("free_description", "notes"):
        _text(obs[key], key, nonempty=False)
    if not isinstance(obs["disposition"], str) or obs["disposition"] not in {"acceptable", "reject", "mixed", "not_evaluated"}:
        raise ExperienceError("invalid disposition")
    if not isinstance(obs["origin"], str) or obs["origin"] not in {"human_observed", "synthetic_test"}:
        raise ExperienceError("invalid origin")
    if obs["supersedes"] is not None:
        _text(obs["supersedes"], "supersedes")
        if obs["supersedes"] == obs["observation_id"]:
            raise ExperienceError("an observation cannot supersede itself")
    canonical(obs)  # Refuse nested NaN, infinities and non-JSON inputs.


def _validate_run(obs, run_dir):
    root = Path(run_dir).resolve()
    if not root.is_dir():
        raise ExperienceError("run_dir is not a directory")
    manifest_path = _safe_artifact(root, "manifest.json")
    manifest = _load_json(manifest_path)
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA_VERSION:
        raise ExperienceError("invalid manifest schema")
    for key in ("run_id", "case_id", "revision"):
        if manifest.get(key) != obs[key]:
            raise ExperienceError(f"observation {key} does not match manifest")
    for key in ("database_sha256", "config_sha256", "brief_sha256"):
        _hash(manifest.get(key), key)
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not {"brief.json", "design.json", "observation-template.json"}.issubset(artifacts):
        raise ExperienceError("manifest must cover brief, design and observation-template")
    for name, digest in artifacts.items():
        _hash(digest, f"artifacts.{name}")
        if sha(_safe_artifact(root, name).read_bytes()) != digest:
            raise ExperienceError(f"artifact hash mismatch: {name}")
    if artifacts["brief.json"] != manifest["brief_sha256"]:
        raise ExperienceError("manifest brief hash disagrees with artifact hash")
    # Keep Python and CLI consumers on the same full run verification contract.
    from .workflow import verify_run
    try:
        verify_run(root)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        raise ExperienceError(f"run verification failed: {exc}") from exc
    brief, design, template = (_load_json(root / name) for name in ("brief.json", "design.json", "observation-template.json"))
    if not all(isinstance(value, dict) for value in (brief, design, template)):
        raise ExperienceError("brief, design and template must be JSON objects")
    stage = brief.get("product", {}).get("development_stage", "")
    if (isinstance(stage, str) and stage.startswith("synthetic")) or template.get("origin") == "synthetic_test":
        if obs["origin"] != "synthetic_test":
            raise ExperienceError("a synthetic demonstration run cannot be relabeled human_observed")
    for key in ("case_id", "revision"):
        if brief.get(key) != obs[key]:
            raise ExperienceError(f"observation {key} does not match brief")
    for key in ("run_id", "case_id", "revision"):
        if template.get(key) != obs[key]:
            raise ExperienceError(f"observation {key} does not match persisted template")
    if template.get("scope") != obs["scope"]:
        raise ExperienceError("observation scope differs from the planned run; create a revised run")
    cells = [item for item in design.get("cells", []) if item.get("id") == obs["cell_id"]]
    batches = [item for item in design.get("batches", []) if item.get("id") == obs["batch_id"]]
    if len(cells) != 1 or len(batches) != 1 or obs["cell_id"] not in batches[0].get("cell_ids", []):
        raise ExperienceError("unknown or ambiguous batch/cell in design")
    cell = cells[0]
    planned = cell.get("planned_sample_masses_g")
    ingredient_keys = {i["key"] for i in brief.get("ingredients", [])}
    if not isinstance(planned, dict) or not planned or not set(planned).issubset(ingredient_keys):
        raise ExperienceError("invalid planned sample masses or ingredient identities")
    for key, value in planned.items():
        _number(value, f"planned_sample_masses_g.{key}")
    if set(obs["actual_masses_g"]) != set(planned):
        raise ExperienceError("actual_masses_g must contain every planned ingredient key, including zeros")
    if not set(obs["material_lots"]).issubset(planned):
        raise ExperienceError("material_lots contains an unknown ingredient")
    for key, value in obs["actual_masses_g"].items():
        if value > 0 and (key not in obs["material_lots"] or obs["material_lots"][key] is None):
            raise ExperienceError(f"material lot required for nonzero {key}")
    base_key = brief.get("design", {}).get("base_key")
    if base_key not in obs["actual_masses_g"] or obs["actual_masses_g"][base_key] <= 0:
        raise ExperienceError("actual base mass must be greater than zero")
    dimensions = brief.get("design", {}).get("dimensions")
    if not isinstance(dimensions, list) or not dimensions or len(set(dimensions)) != len(dimensions) or set(obs["ratings"]) != set(dimensions):
        raise ExperienceError("ratings must contain all design dimensions, with explicit null for missing ratings")
    condition = {"scope": obs["scope"], "run_id": obs["run_id"], "cell_id": obs["cell_id"],
                 "planned_sample_masses_g": planned, "actual_masses_g": {k: float(v) for k, v in obs["actual_masses_g"].items()}}
    return {"manifest_sha256": sha(manifest_path.read_bytes()), "database_sha256": manifest["database_sha256"],
            "artifacts": artifacts, "condition": condition, "condition_sha256": sha(canonical(condition).encode()),
            "mass_deviations_g": {k: obs["actual_masses_g"][k] - v for k, v in planned.items() if obs["actual_masses_g"][k] != v},
            "source_verification": "run_artifacts_verified_database_hash_reference_only"}


class ExperienceStore:
    def __init__(self, path, allow_synthetic=False):
        self.allow_synthetic = bool(allow_synthetic)
        self.path = str(path)
        if self.path != ":memory:":
            resolved = Path(path).resolve()
            if self.allow_synthetic and not resolved.is_relative_to(Path(tempfile.gettempdir()).resolve()):
                raise ExperienceError("synthetic mode requires an isolated database under the system temporary directory")
            resolved.parent.mkdir(parents=True, exist_ok=True)
            self.path = str(resolved)
        self.connection = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        try:
            self._initialize()
        except BaseException:
            self.connection.close()
            raise

    def _initialize(self):
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        tables = {r[0] for r in self.connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'")}
        if tables and tables != {"experience_metadata", "observations"}:
            raise ExperienceError("refusing to modify a database that is not an experience store")
        if tables:
            version = self.connection.execute("SELECT value FROM experience_metadata WHERE key='schema_version'").fetchone()
            if version is None or version[0] != SCHEMA_VERSION:
                raise ExperienceError("unsupported experience database schema")
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS experience_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT OR IGNORE INTO experience_metadata VALUES ('schema_version','1.0');
        CREATE TABLE IF NOT EXISTS observations (
          seq INTEGER PRIMARY KEY AUTOINCREMENT,
          observation_id TEXT NOT NULL UNIQUE,
          run_id TEXT NOT NULL,
          origin TEXT NOT NULL CHECK(origin IN ('human_observed','synthetic_test')),
          supersedes TEXT UNIQUE REFERENCES observations(observation_id),
          observation_json TEXT NOT NULL,
          provenance_json TEXT NOT NULL,
          previous_hash TEXT NOT NULL,
          event_hash TEXT NOT NULL UNIQUE
        );
        CREATE TRIGGER IF NOT EXISTS observations_no_update BEFORE UPDATE ON observations BEGIN SELECT RAISE(ABORT,'append-only ledger'); END;
        CREATE TRIGGER IF NOT EXISTS observations_no_delete BEFORE DELETE ON observations BEGIN SELECT RAISE(ABORT,'append-only ledger'); END;
        CREATE TRIGGER IF NOT EXISTS metadata_no_update BEFORE UPDATE ON experience_metadata BEGIN SELECT RAISE(ABORT,'immutable schema metadata'); END;
        CREATE TRIGGER IF NOT EXISTS metadata_no_delete BEFORE DELETE ON experience_metadata BEGIN SELECT RAISE(ABORT,'immutable schema metadata'); END;
        """)
        version = self.connection.execute("SELECT value FROM experience_metadata WHERE key='schema_version'").fetchone()
        if version is None or version[0] != SCHEMA_VERSION:
            raise ExperienceError("unsupported experience database schema")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        self.connection.close()

    @staticmethod
    def _event_hash(seq, observation, provenance, previous_hash):
        return sha(canonical({"seq": seq, "observation": observation, "provenance": provenance, "previous_hash": previous_hash}).encode())

    def verify(self):
        previous = ZERO_HASH
        errors = []
        rows = self.connection.execute("SELECT * FROM observations ORDER BY seq").fetchall()
        seen = {}
        for expected_seq, row in enumerate(rows, 1):
            try:
                obs, provenance = json.loads(row["observation_json"]), json.loads(row["provenance_json"])
                _validate_shape(obs)
                if row["seq"] != expected_seq or row["previous_hash"] != previous:
                    errors.append(f"sequence/hash link mismatch at {row['seq']}")
                if any(row[key] != obs[key] for key in ("observation_id", "run_id", "origin", "supersedes")):
                    errors.append(f"indexed fields mismatch at {row['seq']}")
                if row["event_hash"] != self._event_hash(row["seq"], obs, provenance, row["previous_hash"]):
                    errors.append(f"event hash mismatch at {row['seq']}")
                if obs["supersedes"] is not None and obs["supersedes"] not in seen:
                    errors.append(f"invalid correction chain at {row['seq']}")
                seen[obs["observation_id"]] = obs
            except (ValueError, TypeError, KeyError) as exc:
                errors.append(f"invalid event {row['seq']}: {exc}")
            previous = row["event_hash"]
        return {"ok": not errors, "event_count": len(rows), "head_sha256": previous, "errors": errors,
                "assurance": "internal consistency only; not proof of human tasting or independent batches"}

    def record(self, observation, run_dir):
        _validate_shape(observation)
        if observation["origin"] == "synthetic_test" and not self.allow_synthetic:
            raise ExperienceError("synthetic observations require explicit isolated test mode")
        provenance = _validate_run(observation, run_dir)
        payload = canonical(observation)
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            state = self.verify()
            if not state["ok"]:
                raise ExperienceError("experience ledger integrity failed: " + "; ".join(state["errors"]))
            existing = self.connection.execute("SELECT * FROM observations WHERE observation_id=?", (observation["observation_id"],)).fetchone()
            if existing:
                if existing["observation_json"] != payload or existing["provenance_json"] != canonical(provenance):
                    raise ExperienceError("observation_id already exists with different content or run provenance")
                self.connection.execute("COMMIT")
                return {"status": "already_recorded", "observation_id": observation["observation_id"], "seq": existing["seq"], "event_sha256": existing["event_hash"]}
            parent_id = observation["supersedes"]
            if parent_id is not None:
                parent = self.connection.execute("SELECT observation_json FROM observations WHERE observation_id=?", (parent_id,)).fetchone()
                if parent is None:
                    raise ExperienceError("supersedes references an unknown observation")
                previous = json.loads(parent[0])
                immutable_scope = ("case_id", "revision", "run_id", "batch_id", "cell_id", "participant_id", "scope", "origin")
                if any(previous[key] != observation[key] for key in immutable_scope):
                    raise ExperienceError("correction cannot cross run, sample, participant, origin or scope")
                if self.connection.execute("SELECT 1 FROM observations WHERE supersedes=?", (parent_id,)).fetchone():
                    raise ExperienceError("correction must supersede the latest observation, not an older revision")
            else:
                # One latest rating per participant/sample. Retastes require a new planned batch/run.
                current = self._current(include_synthetic=True)
                for entry in current:
                    other = entry["observation"]
                    if all(other[key] == observation[key] for key in ("run_id", "batch_id", "cell_id", "participant_id", "origin")):
                        raise ExperienceError("participant/sample already recorded; use supersedes for a correction")
            seq = state["event_count"] + 1
            event_hash = self._event_hash(seq, observation, provenance, state["head_sha256"])
            self.connection.execute("INSERT INTO observations(seq,observation_id,run_id,origin,supersedes,observation_json,provenance_json,previous_hash,event_hash) VALUES(?,?,?,?,?,?,?,?,?)",
                (seq, observation["observation_id"], observation["run_id"], observation["origin"], parent_id, payload, canonical(provenance), state["head_sha256"], event_hash))
            self.connection.execute("COMMIT")
            return {"status": "recorded", "observation_id": observation["observation_id"], "seq": seq, "event_sha256": event_hash,
                    "mass_deviations_g": provenance["mass_deviations_g"]}
        except Exception:
            self.connection.execute("ROLLBACK")
            raise

    def _current(self, include_synthetic=False):
        rows = self.connection.execute("SELECT o.* FROM observations o WHERE NOT EXISTS(SELECT 1 FROM observations n WHERE n.supersedes=o.observation_id) ORDER BY o.seq").fetchall()
        return [{"observation": json.loads(row["observation_json"]), "provenance": json.loads(row["provenance_json"]),
                 "event_sha256": row["event_hash"]} for row in rows if include_synthetic or row["origin"] == "human_observed"]

    def search(self, scope, include_near=False):
        if not isinstance(scope, dict) or not set(scope).issubset(FILTER_KEYS):
            raise ExperienceError(f"query scope accepts only {sorted(FILTER_KEYS)}")
        for key, value in scope.items():
            _text(value, f"query scope.{key}")
        integrity = self.verify()
        if not integrity["ok"]:
            raise ExperienceError("experience ledger integrity failed")
        exact, near = [], []
        all_current = self._current(include_synthetic=True)
        for item in all_current:
            obs = item["observation"]
            if obs["origin"] != "human_observed":
                continue
            mismatches = [key for key, value in scope.items() if (obs["scope"].get(key) if key in SCOPE_KEYS else obs.get(key)) != value]
            tagged = {**item, "match_kind": "near" if mismatches else "exact", "mismatched_fields": mismatches}
            if not mismatches:
                exact.append(tagged)
            elif include_near and len(mismatches) < len(scope):
                near.append(tagged)
        return {"scope": dict(scope), "scope_is_complete": set(SCOPE_KEYS).issubset(scope), "match_policy": "exact supplied fields; no implicit state or recipe transfer",
                "exact": exact, "near": near, "counts": {"exact": len(exact), "near": len(near),
                    "synthetic_excluded": sum(x["observation"]["origin"] == "synthetic_test" for x in all_current),
                    "superseded_excluded": integrity["event_count"] - len(all_current)},
                "ledger_head_sha256": integrity["head_sha256"]}

    def summarize(self, scope):
        found = self.search(scope)
        groups = defaultdict(list)
        for item in found["exact"]:
            groups[item["provenance"]["condition_sha256"]].append(item)
        conditions = []
        for fingerprint, entries in sorted(groups.items()):
            observations = [entry["observation"] for entry in entries]
            batches = sorted({(o["run_id"], o["batch_id"]) for o in observations})
            dimensions = sorted(set().union(*(o["ratings"] for o in observations)))
            ratings = {}
            for dim in dimensions:
                values = [o["ratings"][dim] for o in observations if o["ratings"].get(dim) is not None]
                ratings[dim] = {"count": len(values), "missing": len(observations) - len(values),
                                "minimum": min(values) if values else None, "maximum": max(values) if values else None,
                                "range": max(values) - min(values) if values else None,
                                "values_by_observation": [{"observation_id": o["observation_id"], "batch_id": o["batch_id"], "participant_id": o["participant_id"], "value": o["ratings"].get(dim)} for o in observations]}
            dispositions = Counter(o["disposition"] for o in observations)
            evaluated = [o for o in observations if any(value is not None for value in o["ratings"].values())]
            evaluated_batches = {(o["run_id"], o["batch_id"]) for o in evaluated}
            stage = "no_numeric_ratings" if not evaluated else "repeated_not_generalized" if len(evaluated_batches) >= 2 else "observed_one_batch"
            conditions.append({"condition_sha256": fingerprint, **entries[0]["provenance"]["condition"],
                "quality_stage": stage, "observation_count": len(observations), "participant_count": len({o["participant_id"] for o in observations}),
                "recorded_batch_count": len(batches), "rated_batch_count": len(evaluated_batches), "batches": [{"run_id": r, "batch_id": b} for r, b in batches],
                "material_lot_combinations": [json.loads(value) for value in sorted({canonical(o["material_lots"]) for o in observations})],
                "ratings": ratings, "dispositions": dict(sorted(dispositions.items())),
                "accept_reject_disagreement": dispositions["acceptable"] > 0 and dispositions["reject"] > 0,
                "descriptions": [{"observation_id": o["observation_id"], "free_description": o["free_description"], "notes": o["notes"]} for o in observations],
                "mass_deviations_g": entries[0]["provenance"]["mass_deviations_g"]})
        return {"scope": found["scope"], "scope_is_complete": found["scope_is_complete"], "observation_count": len(found["exact"]),
                "condition_count": len(conditions), "conditions": conditions, "excluded": found["counts"],
                "quality_stage": "no_observations" if not conditions else "descriptive_only",
                "ledger_head_sha256": found["ledger_head_sha256"],
                "limits": ["Human-observed labels are declarations, not independently verified tasting.",
                           "Different run/cell/actual masses are never pooled into one recipe effect.",
                           "Participants from one batch do not constitute independent preparation batches.",
                           "Batch identifiers do not prove independent preparation; repeated does not mean generalized.",
                           "Ranges and disagreement are descriptive; no causal, safety or shelf-life rule is inferred.",
                           "The hash chain detects inconsistency, not deliberate complete rewriting or truncation without an external trusted head."]}

    def analyze(self, run_dir):
        """Evaluate planned contrasts only for complete, compatible paired observations.

        Every participant and preparation batch remains separate. A computed
        difference is descriptive, not a statistical or causal claim.
        """
        from .workflow import verify_run
        run_dir = Path(run_dir).resolve()
        try:
            manifest = verify_run(run_dir)
        except (ValueError, TypeError, KeyError, OSError) as exc:
            raise ExperienceError(f"run verification failed: {exc}") from exc
        design = _load_json(run_dir / "design.json")
        brief = _load_json(run_dir / "brief.json")
        cells = {cell["id"]: cell for cell in design["cells"]}
        dimensions = brief["design"]["dimensions"]
        found = self.search({"run_id": manifest["run_id"]})
        matches = []
        provenance_mismatch_ids = []
        run_manifest_sha256 = sha((run_dir / "manifest.json").read_bytes())
        for entry in found["exact"]:
            if entry["provenance"]["manifest_sha256"] != run_manifest_sha256:
                provenance_mismatch_ids.append(entry["observation"]["observation_id"])
            else:
                matches.append(entry["observation"])
        by_pair = defaultdict(lambda: defaultdict(list))
        for obs in matches:
            by_pair[(obs["batch_id"], obs["participant_id"])][obs["cell_id"]].append(obs)
        contrasts = design.get("contrasts", [])
        for contrast in contrasts:
            terms = contrast.get("terms", [])
            if not terms or len({term.get("cell_id") for term in terms}) != len(terms):
                raise ExperienceError("contrast terms must contain unique cell IDs")
            for term in terms:
                weight = term.get("weight")
                if term.get("cell_id") not in cells or isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight):
                    raise ExperienceError("invalid contrast cell or weight")
        batches, calculated_count = [], 0
        for batch in design["batches"]:
            participants = sorted(participant for b, participant in by_pair if b == batch["id"])
            paired_results = []
            for participant in participants:
                observed = by_pair[(batch["id"], participant)]
                for contrast in contrasts:
                    selected = {}
                    problems = []
                    for term in contrast["terms"]:
                        cell_id = term["cell_id"]
                        values = observed.get(cell_id, [])
                        if len(values) != 1:
                            problems.append({"kind": "missing_cell" if not values else "duplicate_cell", "cell_id": cell_id})
                        else:
                            selected[cell_id] = values[0]
                    scales = {}
                    lots = defaultdict(set)
                    for cell_id, obs in selected.items():
                        planned = cells[cell_id]["planned_sample_masses_g"]
                        ratios = []
                        for key, value in planned.items():
                            actual = obs["actual_masses_g"][key]
                            if value == 0:
                                if actual != 0:
                                    problems.append({"kind": "unexpected_nonzero_ingredient", "cell_id": cell_id, "ingredient_key": key})
                            else:
                                ratios.append(actual / value)
                            if actual > 0:
                                lots[key].add(obs["material_lots"][key])
                        compatible = bool(ratios) and ratios[0] > 0 and all(math.isfinite(ratio) and math.isclose(ratio, ratios[0], rel_tol=1e-9, abs_tol=1e-12) for ratio in ratios)
                        if not compatible:
                            problems.append({"kind": "nonproportional_actual_masses", "cell_id": cell_id})
                        else:
                            scales[cell_id] = ratios[0]
                    if scales and any(not math.isclose(value, next(iter(scales.values())), rel_tol=1e-9, abs_tol=1e-12) for value in scales.values()):
                        problems.append({"kind": "different_sample_scale_multipliers"})
                    for key, values in lots.items():
                        if len(values) > 1:
                            problems.append({"kind": "material_lot_changed_within_contrast", "ingredient_key": key})
                    ratings = {}
                    for dimension in dimensions:
                        missing = [cell_id for cell_id, obs in selected.items() if obs["ratings"].get(dimension) is None]
                        value = None
                        if not problems and not missing:
                            try:
                                value = math.fsum(term["weight"] * selected[term["cell_id"]]["ratings"][dimension] for term in contrast["terms"])
                            except OverflowError:
                                value = None
                            if value is not None and not math.isfinite(value):
                                value = None
                            if value is not None:
                                calculated_count += 1
                        ratings[dimension] = {"value": value, "status": "calculated_descriptive_difference" if value is not None else "incomplete_or_incompatible", "missing_rating_cell_ids": missing}
                    paired_results.append({"participant_id": participant, "contrast_id": contrast["id"], "kind": contrast["kind"],
                        "question": contrast.get("question"), "terms": contrast["terms"], "ratings": ratings, "blocked_reasons": problems,
                        "scale_multipliers": scales,
                        "observations": [{"cell_id": cell_id, "observation_id": obs["observation_id"], "observed_at": obs["observed_at"]} for cell_id, obs in sorted(selected.items())]})
            batches.append({"batch_id": batch["id"], "participant_count": len(participants), "status": "observations_present" if participants else "no_observations", "paired_results": paired_results})
        return {"run_id": manifest["run_id"], "status": "no_observations" if not matches else "descriptive_paired_contrasts_only",
            "observation_count": len(matches), "calculated_dimension_contrast_count": calculated_count, "batches": batches,
            "excluded": {**found["counts"], "provenance_mismatch_ids": provenance_mismatch_ids},
            "manifest_sha256": run_manifest_sha256, "ledger_head_sha256": found["ledger_head_sha256"],
            "limits": ["Only current human-labeled observations from the exact persisted run are eligible.",
                       "No pooling across participants or preparation batches; missing scores stay null.",
                       "All ingredients must follow one common scaling multiplier within and across contrast cells; changed shared material lots block comparison.",
                       "Relative tolerance 1e-9 and absolute tolerance 1e-12 handle arithmetic only, not weighing accuracy.",
                       "Actual elapsed preparation/rest times, operator and tasting session are not structured fields in v1; record them in notes and review before interpretation.",
                       "A difference-in-differences is a score contrast, not proof of molecular synergy, statistical significance or generalized preference.",
                       "Scaling preserves formulation ratios, not necessarily preparation geometry or flavor release."]}
