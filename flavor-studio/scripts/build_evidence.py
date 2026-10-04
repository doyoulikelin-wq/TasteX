#!/usr/bin/env python3
"""Preserve the complete extracted evidence object and add navigation indexes.

Derived links and text mentions do not modify source statements or become
quantitative ingredient attributes. No evidence is dropped when linking fails.
"""
from __future__ import annotations

import collections
import copy
import functools
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

STUDIO = Path(__file__).resolve().parents[1]
ROOT = STUDIO.parent
INPUT = ROOT / "output/flavor/食材风味属性_结构化数据.json"
DOT_INPUT = ROOT / "outputs/01a0f6ce-570d-7c33-92d8-cba7e50ca147/食材圆点表_本地整理数据.json"
CATALOG = STUDIO / "data/catalog.json"
OUT = STUDIO / "data"
sys.path.insert(0, str(ROOT / "tmp/flavor_catalog_deps"))
try:
    from opencc import OpenCC
    SIMPLIFY = OpenCC("t2s").convert
except ImportError as exc:
    raise SystemExit("需要已有的 OpenCC 搜索转换依赖；未生成不完整的简繁索引。") from exc

DOMAIN_LABELS = {
    "aroma": "香气与细分描述", "compound": "分子与化学类别", "taste": "味觉",
    "texture": "质地与口感", "chemesthesis": "辣感与口腔刺激", "process": "加工与状态变化",
    "numeric": "书述数值", "context": "品种、部位与条件", "composition": "组成信息",
}
PROCESS_PATTERNS = {
    "烘烤": r"烘烤|炉烤|网烤|干烤|油烤|烤", "水煮": r"水煮|煮熟|烹熟|烹煮|煮稠",
    "煎": r"煎", "油炸": r"油炸|炸", "蒸": r"蒸", "清炖": r"炖",
    "干燥": r"干燥|晒干|干制|(?:^|[；;、，,/ ])干(?=[\u4e00-\u9fff])",
    "烟熏": r"烟熏", "发酵": r"发酵", "熟成": r"熟成|桶陈|陈放|陈酿",
    "捣碎研磨": r"捣碎|搗碎|剁碎|研磨|磨粉|制泥|成泥|机械乳化|机械搅拌",
    "熟制": r"^熟$|熟食|烹熟|煮熟",
    "切开": r"切开|切片", "加热": r"加热", "去皮": r"去皮|漂白",
    "醃制": r"腌制|腌渍|盐水|碱液|干盐", "榨汁": r"榨汁|果汁|汁$",
    "未成熟": r"未成熟|未熟", "原料新鲜": r"新鲜|生食|^生$|^生姜$|生肉",
    "成熟": r"^成熟(?!度)|过熟|表皮开始褐变",
}
NAME_PROCESS_PATTERNS = {
    **PROCESS_PATTERNS,
    "干燥": r"^干|干燥|晒干|干制|干香蕉",
    "捣碎研磨": r"泥|粉|末|研磨",
    "榨汁": r"汁|浆",
    "熟制": r"^熟|烤|煮|煎|炸|蒸|炖",
    "成熟": r"^成熟|过熟",
}
PART_PATTERNS = {"果皮": r"果皮|瓜皮|^皮$", "叶": r"叶", "种子": r"种子|籽", "树皮": r"树皮"}


@functools.lru_cache(maxsize=30000)
def norm(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", SIMPLIFY(str(value)))).casefold()


def text_leaves(value, path=""):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from text_leaves(child, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from text_leaves(child, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def count_leaves(value) -> int:
    if isinstance(value, dict):
        return sum(count_leaves(v) for v in value.values())
    if isinstance(value, list):
        return sum(count_leaves(v) for v in value)
    return 1


def context_scope(evidence: dict, ingredient: dict) -> dict:
    """Conservative scope checks; missing named state is not silently inferred."""
    source_name = norm(evidence["ingredient"])
    state = norm(evidence.get("state", ""))
    target = norm(ingredient["displayName"])
    # A comparison's second food is not an asserted treatment of its first food.
    focus = re.split(r"[；;]|相对|对照|与.*比较", state, maxsplit=1)[0]
    required = [key for key, pattern in PROCESS_PATTERNS.items() if re.search(pattern, focus)]
    encoded = [key for key, pattern in NAME_PROCESS_PATTERNS.items() if re.search(pattern, target)]
    missing = [key for key in required if key != "原料新鲜" and key not in encoded]
    parts = [key for key, pattern in PART_PATTERNS.items() if re.search(pattern, focus)]
    missing_parts = [key for key in parts if not re.search(PART_PATTERNS[key], target)]
    comparison = bool(re.search(r"生与熟|新鲜相对熟成|新鲜或晒干|水煮与|水煮或|成熟与未成熟|未去皮与去皮|嫩煎相对|冷萃与热萃|完整与切开", state))
    detailed_condition = bool(re.search(r"\d.*(?:°|℃|周|月|年|小时|天)|低温|高温|长期|温水|过熟|采收后熟化", state))
    source_qualifier = bool(re.search(r"^(?:白色|黑松露|阿尔巴白松露|绿豆蔻|黑豆蔻|金枕头|松塞尔白酒|伦敦干琴酒|哈拉里品种|阿贝金纳初榨品种|法兰朵初榨品种|阿芳素|海顿|杜隆多|亚历山大卢卡斯|会议梨|中国煎茶|蜜香红茶|龙井|大吉岭红茶)$", focus))
    variant_not_encoded = source_qualifier and focus not in target
    fresh_mismatch = "原料新鲜" in required and bool(set(encoded) & {"烘烤", "水煮", "煎", "油炸", "蒸", "清炖", "干燥", "烟熏", "发酵", "加热"})
    problems = []
    if comparison: problems.append("证据比较多个处理/成熟状态")
    if missing: problems.append("目标名称未编码证据状态：" + "、".join(missing))
    if missing_parts: problems.append("目标名称未编码证据部位：" + "、".join(missing_parts))
    if detailed_condition: problems.append("证据另有具体温度、时长或成熟条件，目标名称未完整编码")
    if variant_not_encoded: problems.append("证据限定的品种/产品尚未由目标名称确认")
    if fresh_mismatch: problems.append("新鲜/生状态与目标加工名称不一致")
    if ingredient.get("nameNeedsReview"): problems.append("食材代表名称仍待源图核实")
    return {"status": "requires_context_review" if problems else "no_explicit_conflict_detected",
            "reasons": problems, "sourceState": evidence.get("state"),
            "sourceIngredient": evidence["ingredient"], "targetDisplayName": ingredient["displayName"],
            "quantitativeTransferAllowed": False,
            "note": "即使名称相同，也必须保留原文的品种、部位、加工、分母和测定语境；此索引不授权转移数值。"}


def make_links(evidence: dict, ingredients: list[dict]) -> list[dict]:
    original_name = evidence["ingredient"]
    source_name = norm(original_name)
    state = norm(evidence.get("state", ""))
    links = []
    for ingredient in ingredients:
        raw_exact = original_name == ingredient["name"]
        aliases = list(dict.fromkeys([ingredient["name"], ingredient["displayName"], *ingredient.get("aliases", [])]))
        matched_aliases = [a for a in aliases if norm(a) == source_name]
        scope = context_scope(evidence, ingredient) if raw_exact or matched_aliases else None
        if raw_exact or matched_aliases:
            basis = "exact_name" if raw_exact else "alias_name"
            kind = basis if not scope["reasons"] else "related_context"
            reason = ("原始食材名称完全一致" if raw_exact else "与目录现有别名或简繁等价名称一致")
            if scope["reasons"]: reason += "；" + "；".join(scope["reasons"])
            links.append({"ingredientId": ingredient["id"], "kind": kind, "reason": reason,
                          "nameMatchBasis": basis, "matchedAliases": matched_aliases,
                          "contextScope": scope, "quantitativeTransferAllowed": False})
            continue
        # Substrings and labels appearing in a comparison are navigation hints,
        # never equality claims or automatically transferable ingredient values.
        related_aliases = [a for a in aliases if (source_name and (source_name in norm(a) or norm(a) in source_name))]
        state_mentions = [a for a in aliases if len(norm(a)) >= 2 and norm(a) in state]
        if related_aliases or state_mentions:
            reasons = []
            if related_aliases: reasons.append("名称存在子串或上下位文字关系，未认定为同一食材")
            if state_mentions: reasons.append("名称在条件/比较状态中被提及，未认定为原属性主体")
            links.append({"ingredientId": ingredient["id"], "kind": "related_context", "reason": "；".join(reasons),
                          "nameMatchBasis": "substring_or_state_mention", "matchedAliases": list(dict.fromkeys(related_aliases + state_mentions)),
                          "contextScope": {"status": "related_only", "sourceState": evidence.get("state"),
                                           "quantitativeTransferAllowed": False},
                          "quantitativeTransferAllowed": False})
    return sorted(links, key=lambda item: ({"exact_name": 0, "alias_name": 1, "related_context": 2}[item["kind"]], item["ingredientId"]))


def record_domains(evidence: dict, numeric_ids: set[str]) -> tuple[list[str], dict]:
    typ = evidence.get("attribute_type", "").lower()
    searchable = SIMPLIFY(" ".join(text for _, text in text_leaves(evidence)))
    rules = {
        "aroma": "aroma" in typ or "flavor" in typ or "figure" in typ,
        "compound": "compound" in typ or "chemical" in typ or bool(re.search(r"分子|化合物|酯类|醛类|内酯|吡嗪|硫醇", searchable)),
        "taste": "taste" in typ or bool(re.search(r"酸味|苦味|甜味|咸味|鲜味|较苦|较不咸|微甜|又酸又苦", searchable)),
        "texture": "texture" in typ or bool(re.search(r"质地|口感|脆硬|酥脆|绵密|奶油质地", searchable)),
        "chemesthesis": "pungency" in typ or bool(re.search(r"SHU|辣感|辣劲|清凉|麻感|姜辣素", searchable)),
        "process": any(part in typ for part in ("process", "state_change", "state_taxonomy", "age_dependency", "maturity")),
        "numeric": evidence["evidence_id"] in numeric_ids or any(part in typ for part in ("numeric", "fraction", "percentage", "explicit_", "reported_overlap")),
        "context": any(part in typ for part in ("dependency", "dependence", "context", "relative", "comparison", "matrix", "conflict", "taxonomy")),
        "composition": typ == "explicit_composition",
    }
    domains = [key for key in DOMAIN_LABELS if rules[key]] or ["context"]
    return domains, {"basis": "attribute_type_and_text_mentions_for_navigation_only", "sourceAttributeType": typ,
                     "note": "主题标签只说明原文涉及该领域，不将否定、比较、例子或条件叙述转换为属性存在事实。"}


def main() -> None:
    raw = INPUT.read_bytes()
    source = json.loads(raw)
    dot_raw = DOT_INPUT.read_bytes()
    dot_source = json.loads(dot_raw)
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    assert len(source["evidence"]) == 253 and len(source["taxonomy"]) == 70 and len(source["reported_numeric_values"]) == 24
    numeric_ids = {item["evidence_id"] for item in source["reported_numeric_values"]}
    records = []
    domains_index = collections.defaultdict(list)
    ingredient_index = collections.defaultdict(list)
    descriptor_index = collections.defaultdict(list)
    descriptor_terms = {term["descriptor_id"]: norm(term["descriptor"]) for term in source["taxonomy"]}
    for original in source["evidence"]:
        record_id = original["evidence_id"]
        leaves = list(text_leaves(original))
        normalized_leaves = [(path, norm(text)) for path, text in leaves]
        domains, domain_basis = record_domains(original, numeric_ids)
        links = make_links(original, catalog["ingredients"])
        mentions = []
        for descriptor in source["taxonomy"]:
            term = descriptor_terms[descriptor["descriptor_id"]]
            paths = [path for path, text in normalized_leaves if term in text]
            if paths:
                mention = {"descriptorId": descriptor["descriptor_id"], "descriptor": descriptor["descriptor"],
                           "category": descriptor["category"], "fieldPaths": paths, "interpretation": "text_mention_only"}
                mentions.append(mention)
                descriptor_index[descriptor["descriptor_id"]].append(record_id)
        original_text = json.dumps(original, ensure_ascii=False, indent=2)
        record = {"id": record_id, "original": copy.deepcopy(original),
                  "ingredientName": original["ingredient"], "state": original.get("state"),
                  "displayIngredient": SIMPLIFY(original["ingredient"]), "displayState": SIMPLIFY(original.get("state", "")),
                  "searchText": original_text + "\n" + SIMPLIFY(original_text),
                  "links": links, "domains": domains, "domainBasis": domain_basis,
                  "descriptorMentions": mentions, "mentionPolicy": "检索命中只表示提及，包含否定、对比、例子和条件，不表示该属性存在。",
                  "sourceRef": {"pdfPage": original.get("pdf_page"), "bookPage": original.get("book_page"), "evidenceId": record_id}}
        records.append(record)
        for domain in domains: domains_index[domain].append(record_id)
        for link in links:
            ingredient_index[link["ingredientId"]].append({"recordId": record_id, "kind": link["kind"],
                                                         "quantitativeTransferAllowed": False})
    numbers = [{**copy.deepcopy(item), "recordId": item["evidence_id"]} for item in source["reported_numeric_values"]]
    facets_descriptors = [{**copy.deepcopy(item), "original": copy.deepcopy(item),
                          "displayDescriptor": SIMPLIFY(item["descriptor"]),
                          "mentionedInRecordIds": descriptor_index[item["descriptor_id"]],
                          "mentionCount": len(descriptor_index[item["descriptor_id"]]),
                          "interpretation": "text_mention_only"} for item in source["taxonomy"]]
    grouped_categories = collections.defaultdict(list)
    for item in source["taxonomy"]: grouped_categories[item["category_id"]].append(item)
    facets_categories = [{"id": key, "category": values[0]["category"], "categoryOrder": values[0]["category_order"],
                          "descriptorIds": [value["descriptor_id"] for value in values]} for key, values in grouped_categories.items()]
    link_counts = collections.Counter(link["kind"] for record in records for link in record["links"])
    coverage = {"sourceEvidenceRecords": len(source["evidence"]), "includedEvidenceRecords": len(records),
                "sourceDescriptors": len(source["taxonomy"]), "includedDescriptors": len(facets_descriptors),
                "sourceNumericValues": len(source["reported_numeric_values"]), "includedNumericValues": len(numbers),
                "sourceCategories": len(grouped_categories), "sourceFields": list(source),
                "recordsWithExactOrAliasNameLinks": sum(any(link["kind"] != "related_context" for link in r["links"]) for r in records),
                "recordsWithRelatedContextOnly": sum(bool(r["links"]) and all(link["kind"] == "related_context" for link in r["links"]) for r in records),
                "recordsWithoutIngredientLinks": [r["id"] for r in records if not r["links"]],
                "linkCounts": dict(link_counts), "sourceSha256": hashlib.sha256(raw).hexdigest(),
                "rawDotRows": len(dot_source["rows"]), "rawDotTables": len(dot_source["tables"]),
                "rawDotSourceFields": list(dot_source), "rawDotSourceSha256": hashlib.sha256(dot_raw).hexdigest(),
                "rawDotSourceFile": str(DOT_INPUT.relative_to(ROOT)),
                "sourceFile": str(INPUT.relative_to(ROOT)), "catalogFile": "data/catalog.json",
                "scope": "完整保留既有提取文件全部内容，不代表已把整本书的所有正文、图表逐项提取完毕。",
                "quantitativePolicy": "所有书述数值保留原单位、分母、条件与注释；没有把缺失补0，没有把文字强制变成标量。"}
    result = {"schemaVersion": "1.0.0", "source": copy.deepcopy(source), "dotSource": copy.deepcopy(dot_source), "records": records,
              "numbers": numbers, "coverage": coverage,
              "facets": {"domains": [{"id": key, "label": label, "recordIds": domains_index[key],
                                        "count": len(domains_index[key]), "interpretation": "navigation_topic_only"}
                                       for key, label in DOMAIN_LABELS.items()],
                         "descriptors": facets_descriptors, "categories": facets_categories,
                         "numericUnits": sorted({str(item.get("unit")) for item in numbers if item.get("unit") is not None})},
              "indexes": {"ingredientRecords": dict(ingredient_index), "descriptorMentions": dict(descriptor_index)},
              "policies": {"losslessSource": "source 与原属性 JSON、dotSource 与原圆点 JSON 完整逐字段一致。original 对象保存对应证据的全部字段。",
                           "historicalReferences": "历史绝对文件路径仅作为出处原样保留；构建过程不读取、不执行其中引用的文件。",
                           "nameLinks": "exact_name/alias_name 仅是有范围限制的名称关联；状态、部位或上下位文字关系仅 related_context。任何关联都不自动授权转移数值。",
                           "search": "全文与描述词检索只表示原文提及；不区分或隐去否定、示例、比较，必须阅读原文。",
                           "context": "不把烘烤、鲜食、果皮、果肉、品种、熟成年限及配方条件混为一个通用属性。",
                           "unmatched": "无法关联圆点表食材的证据仍完整收录，可独立检索。"}}
    OUT.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    (OUT / "evidence-full.json").write_text(payload, encoding="utf-8")
    (OUT / "evidence-full.js").write_text("window.FLAVOR_EVIDENCE=" + payload.replace("</", "<\\/") + ";\n", encoding="utf-8")
    # Read back deliverables and compare canonical JSON so booleans, zeroes,
    # missing fields, nulls, arrays, and strings remain type/value-exact.
    written = json.loads((OUT / "evidence-full.json").read_text(encoding="utf-8"))
    assert canonical_json(written["source"]) == canonical_json(source)
    assert canonical_json(written["dotSource"]) == canonical_json(dot_source)
    assert len(written["dotSource"]["rows"]) == 10439
    assert len(written["records"]) == len(source["evidence"]) == 253
    for original, record in zip(source["evidence"], written["records"]):
        assert record["id"] == original["evidence_id"]
        assert canonical_json(record["original"]) == canonical_json(original)
    for original, number in zip(source["reported_numeric_values"], written["numbers"]):
        assert number["recordId"] == original["evidence_id"]
        assert canonical_json({key: value for key, value in number.items() if key != "recordId"}) == canonical_json(original)
    for original, descriptor in zip(source["taxonomy"], written["facets"]["descriptors"]):
        assert canonical_json(descriptor["original"]) == canonical_json(original)
    js = (OUT / "evidence-full.js").read_text(encoding="utf-8")
    assert canonical_json(json.loads(js.removeprefix("window.FLAVOR_EVIDENCE=").strip().removesuffix(";"))) == canonical_json(written)
    report = {"status": "passed", "sourceSha256": coverage["sourceSha256"],
              "sourceCanonicalSha256": digest(source), "deliveredSourceCanonicalSha256": digest(written["source"]),
              "dotSourceSha256": coverage["rawDotSourceSha256"], "dotSourceCanonicalSha256": digest(dot_source),
              "deliveredDotSourceCanonicalSha256": digest(written["dotSource"]),
              "rawDotRowsFieldwiseEqual": len(dot_source["rows"]), "rawDotTablesFieldwiseEqual": len(dot_source["tables"]),
              "allDotSourceFieldsPreserved": list(dot_source), "dotSourceLeafValuesPreserved": count_leaves(dot_source),
              "sourceLeafValuesPreserved": count_leaves(source), "allTopLevelFieldsPreserved": list(source),
              "evidenceRecordsFieldwiseEqual": 253, "taxonomyRowsFieldwiseEqual": 70,
              "numericRowsFieldwiseEqual": 24, "noRecordsDroppedForMissingLinks": True,
              "javascriptMatchesJson": True, "sourceFileNotModified": hashlib.sha256(INPUT.read_bytes()).hexdigest() == coverage["sourceSha256"],
              "dotSourceFileNotModified": hashlib.sha256(DOT_INPUT.read_bytes()).hexdigest() == coverage["rawDotSourceSha256"],
              "derivedLinkCounts": dict(link_counts), "scope": "无损性已自动核验；辅助名称/主题关联是可解释索引，不是新的实验或身份验证。"}
    qa = STUDIO / "qa"
    qa.mkdir(exist_ok=True)
    (qa / "evidence-integrity.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"coverage": coverage, "integrity": report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
