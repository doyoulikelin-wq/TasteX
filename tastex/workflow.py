"""Deterministic, replayable evidence-to-experiment runs with immutable outputs."""
from __future__ import annotations
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import tempfile

from . import __version__
from .validation import ValidationError, require_valid

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "flavor-database/flavor.sqlite"
DEFAULT_ALIASES = ROOT / "configs/search_aliases.json"


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValidationError("Duplicate JSON key: " + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValidationError("Non-finite JSON constant: " + x)))


def source_fingerprint():
    files = sorted((ROOT / "tastex").glob("*.py")) + [ROOT / "flavor-database/flavor_db.py"]
    return sha(encoded({str(p.relative_to(ROOT)): file_sha(p) for p in files}))


def _cell_id(cell):
    return cell.get("id", cell.get("cell_id"))


def _safe(value):
    return str(value).replace("|", "\\|").replace("<", "&lt;").replace(">", "&gt;").replace("\n", " / ")


def audit_references(brief, evidence):
    """Bind route references to retained records, never certify their claims."""
    available = {}
    for ingredient in evidence["ingredients"]:
        for field in ("evidence_records", "structured_processing_records", "direct_pairings"):
            for item in ingredient.get(field, []):
                available[item["id"]] = {"kind": field, "snapshot": item}
        for page in ingredient.get("page_hits", []):
            available["book_pages:" + str(page["pdf_page"])] = {"kind": "page_text", "snapshot": page}
    for key, value in brief.get("external_evidence", {}).items():
        available[key] = {"kind": "external_snapshot_not_refetched", "snapshot": value}
    results = []
    for route in brief["routes"]:
        for ref in route["evidence_refs"]:
            results.append({"route_id": route["id"], "reference": ref,
                            "status": "retained_reference" if ref in available else "unresolved_reference",
                            "source": available.get(ref),
                            "meaning": "A retained citation is inspectable context, not validation of the proposed route or dose."})
    return results


def make_report(brief, validation, evidence, design, run_id):
    lines = [f"# {brief['product']['name']} · {brief['case_id']} {brief['revision']}", "",
             f"运行 ID：`{run_id}`。工作流版本：{__version__}。", "",
             "**这是来源驱动的候选筛选与实验计划。尚未制作、试吃或验证风味效果。**", "",
             "## 需求与交付范围", "", _safe(brief["request_text"]), "",
             f"基质：{_safe(brief['product']['matrix'])}；当前阶段：{_safe(brief['product']['development_stage'])}；目标场景：{_safe(brief['product']['intended_use'])}。", "",
             "| 目标 | 意图 | 参照物 | 验收条件 |", "|---|---|---|---|"]
    for target in brief["targets"]:
        lines.append("| " + " | ".join(_safe(target.get(k) if target.get(k) is not None else "待校准") for k in ("dimension", "intent", "reference", "acceptance")) + " |")
    lines += ["", "## 候选路线比较", "", "| 路线 | 状态 | 采用/暂缓理由 | 局限 |", "|---|---|---|---|"]
    for route in brief["routes"]:
        lines.append("| " + " | ".join(_safe(v) for v in (route["title"], route["status"], route["rationale"], "；".join(route["limitations"]))) + " |")
    lines += ["", "所有参数原始来由保存在 brief.json：user/source/hypothesis 分列。路线理由是显式输入，本工具不把书中类别标记换成最优克数。", "",
              "## 检索记录与证据边界", "", "完整输入、所有命中和零结果、全部来源版本及页文本保存在 evidence.json；报告不以摘要替代原始证据。", "",
              "| 材料 | 请求状态 | 参照身份 | 状态关系 |", "|---|---|---|---|"]
    for item in brief["ingredients"]:
        lines.append("| " + " | ".join(_safe(item.get(k) if item.get(k) is not None else "未映射") for k in ("label", "requested_state", "reference_id", "identity_relation")) + " |")
    lines += ["", "实际检索覆盖（命中数不代表独立研究数或证据强度）：", "",
              "| 材料键 | 来源圆点行 / 版本 | 属性记录 | 结构化加工记录 | 全文命中页 |", "|---|---|---|---|---|"]
    for item in evidence["ingredients"]:
        profile = item.get("profile") or {}
        lines.append("| " + " | ".join(_safe(v) for v in (item["key"], f"{profile.get('record_count', 0)} / {profile.get('variant_count', 0)}",
                     len(item["evidence_records"]), len(item["structured_processing_records"]),
                     len(item["page_hits"]))) + " |")
    lines += ["", "当前材料参照 ID 之间的直接配对查询：", ""]
    for probe in evidence.get("pair_probes", []):
        lines.append(f"- {' × '.join(probe['ingredient_keys'])}：{probe['total']} 条；未命中仍是未知，不等于不相容。所有命中保留原始方向。")
    lines += ["", "路线引用核对：", ""]
    for reference in evidence.get("route_references", []):
        lines.append(f"- `{reference['route_id']}` → `{reference['reference']}`：{reference['status']}。")
    lines += ["", "页面命中只表示文字出现，不证明该页的每个图表都以此食材为主体。跨加工状态、相关语境和间接配对不升级成成品实测。", "",
              "检索发现的缺口：", ""]
    gaps = evidence.get("gaps", [])
    for gap in gaps:
        lines.append("- " + _safe(json.dumps(gap, ensure_ascii=False) if isinstance(gap, dict) else gap))
    if not gaps:
        lines.append("- 当前检索规则未产生缺口标记；这不代表证据穷尽或成品已获验证。")
    lines += ["", "## 因子试验与对照", "",
              f"所有设计量以 {brief['design']['basis_g']} g 制好的基底为分母；每单元使用 {brief['design']['sample_base_g']} g 基底。", "",
              f"计划 {len(design['cells'])} 个单元、{len(design['batches'])} 个独立制备批次；实际制作记录尚为空。", "",
              "| 单元 | 类型 | 计划称量 g |", "|---|---|---|"]
    for cell in design["cells"]:
        masses = cell.get("planned_sample_masses_g", {})
        lines.append("| " + " | ".join(_safe(v) for v in (_cell_id(cell), cell.get("kind", cell.get("type", "factorial")), json.dumps(masses, ensure_ascii=False, sort_keys=True))) + " |")
    lines += ["", "随机盲码与呈样顺序由指定 seed 生成。设计者保留 design.json 的解码表；试吃者使用 tasting-sheet.md，避免提前看配方。", "",
              "预设比较：", ""]
    for contrast in design.get("contrasts", []):
        lines.append("- " + _safe(json.dumps(contrast, ensure_ascii=False) if isinstance(contrast, dict) else contrast))
    lines += ["", "解释范围：", ""]
    for limitation in design.get("analysis_limits", []):
        lines.append("- " + _safe(limitation))
    for note in brief["design"]["preparation_notes"]:
        lines.append("- " + _safe(note))
    lines += ["", "## 未解决条件", ""]
    for item in validation["unresolved"]:
        lines.append(f"- `{item['path']}`：{_safe(item['impact'])}")
    for item in validation["warnings"] + design.get("warnings", []):
        lines.append("- " + _safe(json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else item))
    lines += ["", "## 经验回填与复验", "",
              "1. 保留原料批次、实际称量、制备批次、匿名试吃者、自由描述和每项评分。未知仍填 null。",
              "2. 复制 observation-template.json，填写真实结果后用 experience record 追加到独立经验库；不要把模板当结果导入。",
              "3. 成功、失败和意见分歧都保留；纠错用 supersedes 追加，旧记录不覆盖。",
              "4. 默认只查询完全匹配的基质/材料状态/工艺/食用情境。相近情境仅作参考，不能自动迁移剂量或结论。",
              "5. 重复制备、不同批次和不同试吃者分别计数；单次评价不升级为普遍规则。", "",
              "manifest.json 和 events.jsonl 记录输入摘要及确定性步骤；用 replay 重放并比较文件摘要。哈希一致说明输入与记录一致，不证明真实发生了试吃。", ""]
    return "\n".join(lines)


def tasting_sheet(brief, design):
    lines = ["# 盲评记录表", "", "先记录未提示时的气味与味道，再填写评分。强度项0=没有、10=极强；辨识度、硬度和目标符合度使用各自锚点，组织者在自由描述后提供。此量表是项目记录工具。",
             "先不要查阅 report.md、brief.json 或 design.json，以免看到食材与配方提示。真实评分尚未填写。", ""]
    for batch in design["batches"]:
        lines += [f"## 制备批次 {_safe(batch.get('id', batch.get('batch_id')))}", "", "试吃者匿名编号：________；日期时间：________", "",
                  "| 顺序 | 样品代码 | 未提示时的自由描述 | 分项评分/偏好/余味 |", "|---|---|---|---|"]
        for index, item in enumerate(batch.get("presentation", []), 1):
            lines.append(f"| {index} | {_safe(item['blind_code'])} | 待填写 | 待填写 |")
    lines += ["", "评分维度由组织者在自由描述完成后提供。准备者须先确认所有样品的食用适用性、参与者过敏信息和样品要求。", ""]
    return "\n".join(lines)


def run_case(brief_path, out_dir, *, db_path=DEFAULT_DB, aliases_path=DEFAULT_ALIASES):
    from .retrieval import collect_evidence
    from .experiments import build_design
    brief_path, out_dir = Path(brief_path).resolve(), Path(out_dir).absolute()
    db_path, aliases_path = Path(db_path).resolve(), Path(aliases_path).resolve()
    if out_dir.exists():
        raise ValidationError("Run destination already exists; choose a new directory to preserve history")
    brief = read_json(brief_path)
    validation = require_valid(brief)
    aliases = read_json(aliases_path)
    db_hash = file_sha(db_path)
    inputs = {"brief_sha256": sha(encoded(brief)), "database_sha256": db_hash,
              "config_sha256": sha(encoded(aliases)), "workflow_fingerprint": source_fingerprint(), "workflow_version": __version__}
    run_id = "run-" + sha(encoded(inputs))[:24]
    evidence = collect_evidence(brief, db_path, aliases_path)
    if evidence.get("provenance", {}).get("aliases_sha256") != inputs["config_sha256"]:
        raise ValidationError("Alias configuration changed during retrieval")
    evidence["route_references"] = audit_references(brief, evidence)
    for reference in evidence["route_references"]:
        if reference["status"] == "unresolved_reference":
            evidence["gaps"].append({"kind": "unresolved_route_reference", "route_id": reference["route_id"],
                                     "reference": reference["reference"], "meaning": "Not retained in this evidence bundle; cannot count as checked support."})
    if file_sha(db_path) != db_hash:
        raise ValidationError("Source database changed during retrieval")
    design = build_design(brief)
    template = dict(design["template"])
    template["run_id"] = run_id
    design["template"] = template
    events = [
        {"sequence": 1, "event": "brief_validated", "details": validation},
        {"sequence": 2, "event": "aliases_and_source_queries_completed", "details": {"queries": len(evidence.get("queries", [])), "gaps": evidence.get("gaps", [])}},
        {"sequence": 3, "event": "routes_compared", "details": {"routes": [{"id": r["id"], "status": r["status"], "rationale": r["rationale"]} for r in brief["routes"]]}},
        {"sequence": 4, "event": "factorial_plan_generated", "details": {"cells": len(design["cells"]), "planned_batches": len(design["batches"])}},
        {"sequence": 5, "event": "awaiting_real_observations", "details": {"actual_tastings": 0, "flavor_validated": False}},
    ]
    payloads = {"brief.json": encoded(brief), "aliases.json": encoded(aliases), "validation.json": encoded(validation),
                "evidence.json": encoded(evidence), "design.json": encoded(design), "observation-template.json": encoded(template),
                "report.md": make_report(brief, validation, evidence, design, run_id).encode("utf-8"),
                "tasting-sheet.md": tasting_sheet(brief, design).encode("utf-8"),
                "events.jsonl": ("\n".join(json.dumps(e, ensure_ascii=False, sort_keys=True, allow_nan=False) for e in events) + "\n").encode("utf-8")}
    manifest = {"schema_version": "1.0", "run_id": run_id, "case_id": brief["case_id"], "revision": brief["revision"], **inputs,
                "input_paths": {"database": "flavor-database/flavor.sqlite", "brief": "brief.json", "aliases": "aliases.json"},
                "artifacts": {name: sha(data) for name, data in sorted(payloads.items())},
                "status": "awaiting_real_observations", "claims": {"sensory_validated": False, "shelf_life_validated": False}}
    payloads["manifest.json"] = encoded(manifest)
    if source_fingerprint() != inputs["workflow_fingerprint"]:
        raise ValidationError("Workflow implementation changed during execution")
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".tastex-run-", dir=out_dir.parent))
    try:
        for name, data in payloads.items():
            (temporary / name).write_bytes(data)
        if out_dir.exists():
            raise ValidationError("Destination appeared during execution; refusing to overwrite")
        os.rename(temporary, out_dir)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"run_id": run_id, "output": str(out_dir), "cells": len(design["cells"]), "planned_batches": len(design["batches"]),
            "unresolved_count": len(validation["unresolved"]), "status": "awaiting_real_observations", "database_unchanged": True}


def verify_run(run_dir):
    run_dir = Path(run_dir).resolve()
    manifest = read_json(run_dir / "manifest.json")
    if manifest.get("schema_version") != "1.0" or not isinstance(manifest.get("artifacts"), dict):
        raise ValidationError("Invalid run manifest")
    for key in ("brief_sha256", "database_sha256", "config_sha256", "workflow_fingerprint"):
        if not isinstance(manifest.get(key), str) or not re.fullmatch(r"[a-f0-9]{64}", manifest[key]):
            raise ValidationError("Invalid manifest SHA256: " + key)
    required = {"brief.json", "aliases.json", "evidence.json", "design.json", "observation-template.json", "events.jsonl", "report.md", "tasting-sheet.md", "validation.json"}
    if not required <= set(manifest["artifacts"]):
        raise ValidationError("Incomplete run artifact manifest")
    for name, expected in manifest["artifacts"].items():
        if not isinstance(name, str) or Path(name).name != name:
            raise ValidationError("Unsafe run artifact path")
        path = run_dir / name
        if path.is_symlink() or not path.is_file():
            raise ValidationError("Missing or unsafe run artifact: " + name)
        if file_sha(path) != expected:
            raise ValidationError("Run artifact hash mismatch: " + name)
    brief = read_json(run_dir / "brief.json")
    require_valid(brief)
    if any(manifest.get(k) != brief[k] for k in ("case_id", "revision")):
        raise ValidationError("Manifest case/revision mismatch")
    if file_sha(run_dir / "brief.json") != manifest.get("brief_sha256") or file_sha(run_dir / "aliases.json") != manifest.get("config_sha256"):
        raise ValidationError("Run input hash mismatch")
    inputs = {key: manifest[key] for key in ("brief_sha256", "database_sha256", "config_sha256", "workflow_fingerprint", "workflow_version")}
    if "run-" + sha(encoded(inputs))[:24] != manifest.get("run_id"):
        raise ValidationError("Run identity mismatch")
    return manifest


def replay(run_dir, out_dir, *, db_path=DEFAULT_DB):
    original = verify_run(run_dir)
    if file_sha(db_path) != original["database_sha256"]:
        raise ValidationError("Replay requires the exact original database bytes")
    if source_fingerprint() != original["workflow_fingerprint"]:
        raise ValidationError("Replay requires the original workflow implementation; check out the recorded Git version")
    result = run_case(Path(run_dir) / "brief.json", out_dir, db_path=db_path, aliases_path=Path(run_dir) / "aliases.json")
    reproduced = verify_run(out_dir)
    differences = [name for name, value in original["artifacts"].items() if reproduced["artifacts"].get(name) != value]
    if original["run_id"] != reproduced["run_id"] or differences:
        raise ValidationError("Replay diverged: " + ", ".join(differences))
    return {**result, "exact_replay": True, "verified_artifacts": len(original["artifacts"])}
