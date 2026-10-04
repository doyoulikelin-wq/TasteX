#!/usr/bin/env python3
"""Create a browser-safe ingredient catalogue from the preserved source records.

No dot vectors are averaged, names are never merged, and sharing stays attached
to the source table. Run from any directory with Python 3.10+.
"""
from __future__ import annotations

import collections
import csv
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "outputs/01a0f6ce-570d-7c33-92d8-cba7e50ca147/食材圆点表_本地整理数据.json"
OUT = ROOT / "flavor-studio/data"
sys.path.insert(0, str(ROOT / "tmp/flavor_catalog_deps"))
try:
    from opencc import OpenCC
    SIMPLIFY = OpenCC("t2s").convert
    ALIAS_METHOD = "OpenCC 0.1.7 t2s; search/display only, no identity merging"
except ImportError:
    SIMPLIFY = lambda text: text
    ALIAS_METHOD = "source names only (optional OpenCC unavailable)"

# These spellings are retained as source identities. The flags are a transparent
# text-quality screen, not corrected names or an assertion about the real food.
IDENTITY_REVIEW = {
    "生", "見", "生墓", "期甜菜", "則餅", "煎撃", "用豆", "帕爾馬",
    "(喬利佐香腸抹醬)", "100%頂級伊比利橡實豬", "丁烘烤小牛肉",
    "乾小槩", "乾小樂", "乾小薬", "乾小藥", "乾枝葉", "乾校葉",
    "乾嚎菇", "乾壊菇", "乾螺菇", "乾革澄茄", "則能鳥肉", "則駝鳥肉",
    "同鳩它鳥肉", "助眼牛排", "味酥", "味酬", "味醋", "味醐", "味醜",
    "味酬日本甜米酒", "味醐日本甜米酒", "嚎油", "嚎菇", "墓香花",
    "奶油菖苣", "奶油萬苣", "奶油蒿苣", "奶油髙苣", "奶油黄苣",
    "小寶石芮苣", "小寶石萬苣", "小寶石蒿苣", "小寶石高苣", "小寶石髙苣",
    "年卜拉魚露", "成熟切建乳酪", "圖葉當歸葉", "枝樹蜜", "枝葉茶",
    "校樹", "校樹蜜", "桑植", "桑樞", "榴樋蜜", "樋柑", "橘蘋", "檸橡皮",
    "清燉根椁", "清燉棍椁", "清燉椁", "清燉福椁", "清燉缸魚翅", "清燉紅魚翅",
    "清燉檸檬螺", "清燉檸檬鰻", "漣膚木", "烘烤牒魚", "烘烤紅魚翅",
    "烘烤縹魚", "烘烤繰魚", "烘烤臊魚", "烘烤菱", "烘烤菱辭", "烘烤菱鮮",
    "烘烤菱鯉", "烘烤螺魚", "烘烤驟魚", "烘烤鳏魚", "煽烤大頭菜",
    "煎鴨鶉", "煎鵝鶉", "煎鶴鶉", "熟奶油菌苣", "熟奶油高苣", "熟竟菜粒",
    "熟綠扁显", "熟苔数", "熟苔番", "熟苔豔", "熟蛤蝌", "熟蛤蝴", "熟豆豆",
    "燉檸檬縹", "燉檸檬繰", "燉檸檬螺", "燉檸檬骤", "燉長身鰭", "牡螭",
    "生嚎葉", "生獴葉", "着蓬菜", "著蓬菜", "竟菜籽", "竹災魚", "竹熒魚", "竹英魚",
    "羊萬苣(野苣)", "羊萬苣野苣", "羊蒿苣野苣", "羊高苣野苣", "羊髙苣(野苣)",
    "茴菴香", "茴蕾香", "蒔薇", "蕾香花", "蝮油", "蝮菇", "螺菇",
    "西班牙火服100%頂級伊比利橡實豬", "西班牙火腋100%頂級伊比利橡實豬",
    "西班牙火腿100%頂級伊比^橡實豬", "西班牙火腿doo%頂級伊比利橡實豬",
    "貝&鸵鳥肉", "貝n鳥它鳥肉", "醍魚高湯", "金枕頭榴梗", "金枕頭榴樋", "金枕頭榴機",
    "肯塔基純波本威土忌", "鴿咼湯", "鹹睚魚", "鹹鯉魚", "鹹鰻魚",
}

FAMILIES = [
    ("condiment", "酱料与调味", r"酱|醬|味噌|魚露|鱼露|老抽|油醋|美乃滋|豆豉|泡菜|酸菜|腌渍|醃漬"),
    ("oil", "油脂", r"油|椰子脂"),
    ("alcohol", "酒与发酵饮品", r"酒|威士忌|威土忌|白兰地|白蘭地|伏特加|干邑|西打|气泡|氣泡|生命之水|卡沙夏|金巴利|雅文邑|皮爾森|健力士|蘇維濃|修道院|卡本內|松塞爾|諾托蜜思嘉|馬德拉|白波特"),
    ("vinegar", "醋", r"醋"),
    ("tea_coffee", "茶与咖啡", r"茶|咖啡|通宁水|通寧水|苏打|蘇打|汽水"),
    ("cheese", "乳酪", r"乳酪"),
    ("dairy", "乳品与蛋", r"奶|优格|優格|乳|蛋|克菲爾"),
    ("sweets", "可可与甜味配料", r"巧克力|可可|糖|蜂蜜|树蜜|樹蜜|蕎麥蜜|菜籽蜜|榴樋蜜|酥餅"),
    ("bread_grain", "谷物与烘焙", r"麵包|面包|餅|饼|麵|面|吐司|貝果|貝包|穀|谷|麥|麦|米$|米粒|米粥|米漿|米浆|苔数|苔番|苔豔|爆米花|藜|年糕|塔爾哈納粉|斯佩爾特|糕|酥皮"),
    ("nuts_seeds", "坚果与种子", r"堅果|坚果|核桃|胡桃|腰果|榛果|栗子|開心果|开心果|松子|杏仁|花生|籽|芒果籽|種草|种草"),
    ("mushroom", "菌菇", r"菇|菌|松露"),
    ("meat", "肉类", r"肉|牛|羊|豬|猪|雞|鸡|鴨|鸭|鵝|鹅|鵪|鹌|鶉|鹑|鴿|鸽|火腿|培根|香腸|香肠|薩拉米|腸|肠|里肌|鹿|兔|骨髓|鴕|鸵|斑鳩|斑鸠|鵝|排$"),
    ("seafood", "水产", r"魚|鱼|蝦|虾|蟹|貝|贝|蛤|蠣|蚝|牡螭|海膽|海胆|鱒|鮭|鰻|鱈|鰈|鯛|鱸|虹鳟|烏賊|乌贼|淡菜|海臘|海腊|螺"),
    ("seaweed", "海藻", r"藻|海帶|海带|昆布|裙帶|裙带|海苔"),
    ("citrus", "柑橘", r"柑|橘|橙|柚|檸檬|柠檬|萊姆|莱姆|青檸|青柠|佛手柑|夏蜜|日向夏|夏橙"),
    ("fruit", "水果", r"莓|果|瓜|荔枝|龍眼|龙眼|梨|桃|杏|李子|梅|蕉|芒果|葡萄|木瓜|鳳梨|凤梨|楊桃|杨桃|柿子|榴|紅毛丹|红毛丹|蓮霧|莲雾|番荔枝|枸杞|棗|枣|山竹|布阿蘇|巴庫里|卡姆果|日曬|羅望子|罗望子|格里歐汀|斐濟|斐济|甜瓜|蜜瓜|嘉寶|釋迦|椰子|覆盆子|枇杷|山桑子|酸漿|酸浆|岩高蘭"),
    ("flowers", "食用花", r"花|玫瑰|薰衣草|洋甘菊|母菊"),
    ("spice", "香辛料", r"椒|薑|姜|芥末|辣根|孜然|豆蔻|桂皮|肉桂|八角|丁香|番紅花|番红花|香草|零陵|華澄茄|华澄茄|高良|鹽膚木|盐肤木|茴香籽"),
    ("herb", "香草与叶片", r"葉|叶|草|薄荷|羅勒|罗勒|芹|蒔蘿|莳萝|紫蘇|紫苏|馬鬱蘭|马郁兰|龍蒿|龙蒿|當歸|当归|香茅|芫荽|茴香|迷迭香|百里香|鼠尾|香桃|月桂|松針|松针|樹艾|树艾|苦艾|蒔薇"),
    ("vegetable", "蔬菜与豆类", r"菜|豆|薯|芋|蔥|葱|蒜|蔔|卜|芥|筍|笋|瓜|茄|甘藍|甘蓝|蘆筍|芦笋|蔬|韭|秋葵|防風|防风|蘿|萝|番茄|番薯|番藷|朝鮮薊|朝鲜蓟|薊|蓟|木薯|仙人掌|大黃|大黄|橄欖|橄榄|大頭|大头|甜玉米|鷹嘴|鹰嘴|苣|竹|百合|蕪|芜|甜菜"),
    ("smoke", "烟熏材料", r"煙|烟"),
    ("insect", "可食用昆虫", r"蟲|虫|蟻|蚁"),
]

# Specific food identity takes priority over substrings such as "酪梨", "小牛",
# "山羊乳酪", "南瓜籽", "辣椒", "香檳", and "櫻桃番茄".
PRIORITY = [
    # Specific food phrases precede generic animal/fungus words.
    ("dairy", r"巴斯德滅菌法山羊奶|巴斯德灭菌法山羊奶"),
    ("insect", r"麵包蟲|面包虫|切葉蟻|切叶蚁"),
    ("cheese", r"乳酪"),
    ("oil", r"橄欖油|橄榄油|籽油|花生油|榛果油|椰子脂|豬油|猪油|融化奶油|澄清奶油|^奶油$"),
    ("dairy", r"鮮奶油|鲜奶油|酸奶油|奶油乳酪|牛奶|羊奶|水牛奶|優格|优格|煉乳|炼乳|^蛋|水煮蛋|炒蛋|生蛋|克菲爾"),
    ("vinegar", r"醋$"),
    ("alcohol", r"酒|威士忌|白蘭地|白兰地|伏特加|干邑|香檳$|香槟$|^西打$|蘋果西打|苹果西打"),
    ("tea_coffee", r"咖啡|茶$|汽水$|苏打水$|蘇打水$|通寧水|通宁水"),
    ("sweets", r"蜂蜜|樹蜜|树蜜|糖$|糖漿|糖浆|巧克力|可可粉|可可豆|糖蜜"),
    ("nuts_seeds", r"堅果|坚果|核桃|胡桃|腰果|榛果|開心果|开心果|花生$|杏仁|葵花籽|芝麻籽|南瓜籽|大麻籽|芒果籽|奇亞籽|奇亚籽|罂粟籽|蒼白莖藜籽"),
    ("fruit", r"兔眼藍莓|兔眼蓝莓"),
    ("spice", r"肉桂|肉豆蔻|桂皮|印度長胡椒|印度长胡椒"),
    ("vegetable", r"巴斯德滅菌法番茄汁|巴斯德灭菌法番茄汁"),
    ("mushroom", r"菇|菌|松露|松茸"),
    ("seaweed", r"藻|海帶|海带|昆布|裙帶|裙带|海苔"),
    ("condiment", r"醬|酱|味噌|魚露|鱼露|美乃滋|老抽|泡菜|酸菜"),
    ("vegetable", r"番茄|南瓜|冬瓜|佛手瓜|櫛瓜|栉瓜|黃瓜|黄瓜|小黃瓜|小黄瓜|大豆|綠豆|绿豆|黑豆$|紅豆|红豆|扁豆|豌豆|蠶豆|蚕豆|豆腐|蕪菁|芜菁|蘿蔔|萝卜|蔥|葱|馬鈴薯|马铃薯|番薯|番藷|苣|甘藍|甘蓝|甜玉米|朝鮮薊|朝鲜蓟|蘆筍|芦笋|大頭菜|大头菜|^芹菜|^甜菜|芹菜根|香芹根|仙人掌葉|仙人掌叶|小白菜|花椰菜|青花菜|青花筍|青花笋"),
    ("herb", r"生蠔葉|生蚝叶|天竺葵|檸檬茶樹|柠檬茶树|檸檬香桃木|柠檬香桃木|檸檬馬鞭草|柠檬马鞭草|青檸葉|青柠叶|黑醋栗葉|黑醋栗叶|咖哩葉|咖哩叶|紅酸模|红酸模|苜蓿芽|茵陳蒿|歐白芷|欧白芷|葛縷子|葛缕子|菖蒲根|桑根"),
    ("spice", r"山葵"),
    ("flowers", r"千日菊"),
    ("alcohol", r"奇美藍比利時烈愛爾|芙內布蘭卡"),
    ("vegetable", r"黑皮波羅門參"),
    ("seafood", r"魚|鱼|蝦|虾|蟹|蛤|扇貝|扇贝|鮭|鯉|鱸|鱈|鯛|鰻|鰈|鯖|鲨|鯊|鮃|海膽|海胆|牡蠣|牡蛎|淡菜|烏賊|乌贼|虹鱒|虹鳟"),
    ("meat", r"肉|牛排|羊排|豬排|猪排|火腿|培根|香腸|香肠|薩拉米|萨拉米|鴨|鸭|雞|鸡|鴿|鸽|鵝|鹅|鵪|鹌|鶉|鹑|骨髓|斑鳩|斑鸠|^和牛$|^安格斯牛$"),
]
FAMILY_LABEL = {key: label for key, label, _ in FAMILIES} | {"other": "待分类"}


def family(name: str) -> str:
    for key, pattern in PRIORITY:
        if re.search(pattern, name):
            return key
    for key, _, pattern in FAMILIES:
        if re.search(pattern, name):
            return key
    return "other"


def ingredient_id(name: str) -> str:
    return "ing-" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]


def search_normalize(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", unicodedata.normalize("NFKC", text)).lower()


def source_ref(row: dict) -> dict:
    return {"tableId": row["table_id"], "rowId": row["row_id"],
            "pdfPage": row["pdf_page"], "bookPage": row["printed_page"]}


def canonical_record(rows: list[dict]) -> tuple[dict, str]:
    real = [r for r in rows if r["pdf_page"] != 38]
    candidates = real or rows
    complete_mains = [r for r in candidates if r["role"] == "main" and r["dot_review_status"] == "complete_visual_review"]
    mains = [r for r in candidates if r["role"] == "main"]
    if complete_mains:
        pool, reason = complete_mains, "fully_visual_reviewed_main_record"
    elif mains:
        pool, reason = mains, "source_main_record"
    else:
        pool, reason = candidates, "most_frequent_exact_source_vector"
    counts = collections.Counter(tuple(r["presence"]) for r in pool)
    chosen = sorted(pool, key=lambda r: (-counts[tuple(r["presence"])],
                    r["presence"].count(None), r["dot_review_status"] != "complete_visual_review",
                    r["pdf_page"], r["row_id"]))[0]
    return chosen, reason if real else "teaching_example_only"


def main() -> None:
    source_bytes = SOURCE.read_bytes()
    data = json.loads(source_bytes)
    categories = data["categories"]
    grouped = collections.defaultdict(list)
    for row in data["rows"]:
        grouped[row["name_raw"]].append(row)
    names = sorted(grouped)
    id_map = {name: ingredient_id(name) for name in names}
    assert len(set(id_map.values())) == len(names)
    # Corrections are strictly row-scoped: no edit to the immutable source file,
    # original name identity, aroma vector, or unreviewed matching occurrences.
    original_rows = {row["row_id"]: row for row in data["rows"]}
    main_record_by_table = {row["table_id"]: row["row_id"] for row in data["rows"] if row["role"] == "main"}
    review_path = OUT / "name-display-corrections.json"
    name_reviews = json.loads(review_path.read_text()) if review_path.exists() else {}
    review_by_record = {}
    for bucket in ("corrections", "confirmedUnchanged", "unresolved"):
        for review in name_reviews.get(bucket, []):
            row_id = review["recordId"]
            source_row = original_rows[row_id]
            assert review["id"] == id_map[source_row["name_raw"]]
            assert review["originalName"] == source_row["name_raw"]
            assert review["sourceRef"] == source_ref(source_row)
            assert review["sourceImageViewed"] is True
            assert review.get("appliesToAllRecords") is False
            assert row_id not in review_by_record
            if bucket != "unresolved":
                assert review.get("correctedName", "").strip()
            review_by_record[row_id] = {**review, "reviewBucket": bucket}
    record_identity_eligible = {}
    ingredients = []
    conflicts = []
    edge_list = []
    tables = []
    for table in data["tables"]:
        is_example = table["pdf_page"] == 38
        tables.append({"id": table["table_id"], "mainId": id_map[table["main_ingredient_raw"]],
                       "mainName": table["main_ingredient_raw"], "pdfPage": table["pdf_page"],
                       "bookPage": table["printed_page"], "rowCount": table["row_count"],
                       "reviewStatus": table["review_status"], "isExample": is_example,
                       "recommendationEligible": not is_example})
    for name in names:
        raw_records = grouped[name]
        chosen, reason = canonical_record(raw_records)
        real = [r for r in raw_records if r["pdf_page"] != 38]
        actual_vectors = collections.Counter(tuple(r["presence"]) for r in real)
        conflict_indices = [i for i in range(14) if {r["presence"][i] for r in real if r["presence"][i] is not None} == {0, 1}]
        unknown_indices = [i for i, value in enumerate(chosen["presence"]) if value is None]
        all_unknown = [i for i in range(14) if any(r["presence"][i] is None for r in real)]
        name_verified = any(r.get("name_review_status") == "visual_reviewed" for r in raw_records)
        canonical_name_review = review_by_record.get(chosen["row_id"])
        canonical_name_resolved = bool(canonical_name_review and canonical_name_review["reviewBucket"] != "unresolved")
        corrected_source_name = canonical_name_review["correctedName"] if canonical_name_resolved else name
        display_name = SIMPLIFY(corrected_source_name)
        name_review = name in IDENTITY_REVIEW and not canonical_name_resolved
        reasons = [canonical_name_review.get("note", "名称仍待核对") if canonical_name_review else
                   "名称疑似残缺或 OCR 字形异常，保留原文，需对照原图确认身份"] if name_review else []
        scoped_reviews = [review_by_record[r["row_id"]] for r in raw_records if r["row_id"] in review_by_record]
        nav_family = family(corrected_source_name)
        records = []
        for row in raw_records:
            scoped_review = review_by_record.get(row["row_id"])
            scoped_resolved = bool(scoped_review and scoped_review["reviewBucket"] != "unresolved")
            record_identity_eligible[row["row_id"]] = name not in IDENTITY_REVIEW or scoped_resolved
            rec = {"id": row["row_id"], "tableId": row["table_id"], "pdfPage": row["pdf_page"],
                   "bookPage": row["printed_page"], "role": row["role"],
                   "name": row["name_raw"], "rawName": row["name_raw"],
                   "displayName": SIMPLIFY(scoped_review["correctedName"] if scoped_resolved else row["name_raw"]),
                   "presence": row["presence"], "sharedWithMain": row["shared_with_main"],
                   "mainIngredientId": id_map[row["main_ingredient_raw"]],
                   "reviewStatus": row["dot_review_status"],
                   "nameReviewStatus": scoped_review["reviewStatus"] if scoped_review else row.get("name_review_status", "source_ocr"),
                   "originalNameReviewStatus": row.get("name_review_status", "source_ocr"),
                   "nameNeedsReview": not record_identity_eligible[row["row_id"]],
                   "identityEligible": record_identity_eligible[row["row_id"]],
                   "sourceRef": source_ref(row), "isExample": row["pdf_page"] == 38}
            if scoped_review:
                rec["nameSourceReview"] = scoped_review
            records.append(rec)
            if row["role"] == "pairing" and row["pdf_page"] != 38:
                edge_list.append({"id": row["row_id"], "tableId": row["table_id"],
                                  "mainId": id_map[row["main_ingredient_raw"]], "pairedId": id_map[name],
                                  "sharedCategories": [categories[i] for i, val in enumerate(row["shared_with_main"]) if val == 1],
                                  "sharedCategoryIndices": [i for i, val in enumerate(row["shared_with_main"]) if val == 1],
                                  "unknownSharedCategories": [categories[i] for i, val in enumerate(row["shared_with_main"]) if val is None],
                                  "shared": row["shared_with_main"], "presence": row["presence"],
                                  "sourceRef": source_ref(row), "reviewStatus": row["dot_review_status"]})
        aliases = list(dict.fromkeys([name, SIMPLIFY(name), corrected_source_name, display_name]))
        item = {"id": id_map[name], "name": name, "displayName": display_name, "aliases": aliases,
                "searchText": " ".join(aliases + [search_normalize(a) for a in aliases]),
                "visualFamily": nav_family, "visualFamilyLabel": FAMILY_LABEL[nav_family],
                "visualFamilyBasis": "specific_name_keywords_before_generic_words; navigation/art inference only; uses canonical reviewed name when available",
                "image": "assets/ingredients/" + id_map[name] + ".svg",
                "presence": chosen["presence"], "canonical": {"presence": chosen["presence"],
                   "recordId": chosen["row_id"], "selectionReason": reason, "sourceRef": source_ref(chosen),
                   "reviewStatus": chosen["dot_review_status"], "sourceName": name,
                   "displayName": display_name, "nameReviewStatus": canonical_name_review["reviewStatus"] if canonical_name_review else chosen.get("name_review_status", "source_ocr")},
                "sourceRef": source_ref(chosen), "variantCount": len(actual_vectors),
                "conflictCategories": [categories[i] for i in conflict_indices], "conflictCategoryIndices": conflict_indices,
                "unknownCategories": [categories[i] for i in unknown_indices], "unknownCategoryIndices": unknown_indices,
                "anyRecordUnknownCategories": [categories[i] for i in all_unknown],
                "recordCount": len(raw_records), "sourceRecordCount": len(real),
                "mainRecordCount": sum(r["role"] == "main" for r in real), "records": records,
                "nameVisuallyReviewed": name_verified or canonical_name_resolved, "nameNeedsReview": name_review,
                "canonicalNameVisuallyReviewed": bool(canonical_name_review),
                "allSameNameRecordsReviewed": all(r["row_id"] in review_by_record for r in raw_records),
                "remainingUnreviewedSuspectNameRecords": sum(not record_identity_eligible[r["row_id"]] for r in raw_records),
                "nameReviewReasons": reasons, "exampleOnly": not real,
                "recommendationEligible": bool(real) and not name_review}
        if scoped_reviews:
            item["displayNameCorrections"] = scoped_reviews
            item["nameReviewScope"] = "Only listed recordId rows were visually reviewed. The ingredient display follows the canonical record; other matching raw-name records keep their original names and review states."
            item["canonical"]["nameSourceReview"] = canonical_name_review
        ingredients.append(item)
        if conflict_indices or all_unknown:
            conflicts.append({"ingredientId": id_map[name], "name": name, "displayName": display_name,
                              "recordCount": len(real), "variantCount": len(actual_vectors),
                              "conflictCategories": item["conflictCategories"],
                              "anyRecordUnknownCategories": item["anyRecordUnknownCategories"],
                              "canonicalRecordId": chosen["row_id"], "canonicalReason": reason,
                              "variants": [{"presence": list(vector), "recordCount": count,
                                            "recordIds": [r["row_id"] for r in real if tuple(r["presence"]) == vector]}
                                           for vector, count in actual_vectors.most_common()]})
    eligible_ids = {i["id"] for i in ingredients if i["recommendationEligible"]}
    for table in tables:
        main_record_id = main_record_by_table[table["id"]]
        main_review = review_by_record.get(main_record_id)
        table["mainRecordId"] = main_record_id
        table["mainDisplayName"] = SIMPLIFY(main_review["correctedName"] if main_review and main_review["reviewBucket"] != "unresolved" else table["mainName"])
        table["mainNameIdentityEligible"] = record_identity_eligible[main_record_id]
        table["recommendationEligible"] = (not table["isExample"] and table["mainId"] in eligible_ids
                                              and table["mainNameIdentityEligible"])
    for edge in edge_list:
        main_record_id = main_record_by_table[edge["tableId"]]
        edge["mainRecordId"] = main_record_id
        edge["sourceNamesEligible"] = record_identity_eligible[edge["id"]] and record_identity_eligible[main_record_id]
        edge["recommendationEligible"] = (edge["mainId"] in eligible_ids and edge["pairedId"] in eligible_ids
                                          and edge["sourceNamesEligible"])
    summary = {"ingredients": len(ingredients), "sourceRecords": len(data["rows"]),
               "tables": len(tables), "sourceChapterTables": sum(not t["isExample"] for t in tables),
               "recommendationTables": sum(t["recommendationEligible"] for t in tables),
               "exampleTables": sum(t["isExample"] for t in tables), "sourceEdges": len(edge_list),
               "recommendationEdges": sum(e["recommendationEligible"] for e in edge_list),
               "recommendationIngredients": len(eligible_ids),
               "conflictingIngredients": sum(bool(i["conflictCategories"]) for i in ingredients),
               "multiVectorIngredients": sum(i["variantCount"] > 1 for i in ingredients),
               "nameReviewIngredients": sum(i["nameNeedsReview"] for i in ingredients),
               "canonicalNamesSourceReviewed": len(review_by_record),
               "canonicalNamesCorrected": len(name_reviews.get("corrections", [])),
               "canonicalNamesConfirmedUnchanged": len(name_reviews.get("confirmedUnchanged", [])),
               "canonicalNamesUnresolved": len(name_reviews.get("unresolved", [])),
               "unresolvedOrUnreviewedSuspectNameRecords": sum(not v for v in record_identity_eligible.values()),
               "canonicalUnknownCells": sum(len(i["unknownCategories"]) for i in ingredients),
               "sourceUnknownCells": sum(r["presence"].count(None) for r in data["rows"]),
               "visualFamilies": dict(collections.Counter(i["visualFamily"] for i in ingredients))}
    result = {"meta": {"schemaVersion": "1.1.0", "sourceFile": str(SOURCE.relative_to(ROOT)),
                "sourcePdf": Path(data["source_pdf"]).name, "sourceSha256": hashlib.sha256(source_bytes).hexdigest(),
                "summary": summary, "semantics": data["semantics"],
                "aliasMethod": ALIAS_METHOD,
                "identityPolicy": "Exact raw source names remain distinct. Simplified aliases affect display and search only.",
                "canonicalPolicy": "Prefer visually reviewed main rows, then main rows, then the most frequent exact source vector. Always select a real source record; never average vectors.",
                "examplePolicy": "PDF page 38 is retained as a teaching example and excluded from recommendation vectors, counts, and all edges.",
                "relationPolicy": "Shared aroma marks apply only between a table's main ingredient and its paired row. They do not propagate to other tables or combinations.",
                "chartPolicy": "Charts may count category marks or coverage; they must not describe them as intensity, concentration, sensory contribution, or recipe proportion.",
                "nameReviewPolicy": "Corrections and unchanged confirmations apply only to explicitly reviewed recordId rows. Ingredient display uses the canonical row's reviewed name; raw identities, IDs, and all other occurrences remain unchanged. Unresolved canonical names are excluded; pairing edges additionally require both exact source names to be eligible.",
                "visualFamilyPolicy": "Keyword-derived browse/art grouping only; not a verified taxonomy or substitute for ingredient identity.",
                "recipePolicy": "Generated combinations are test candidates, not validated recipes, dose recommendations, safety assessments, or predictions of liking."},
              "categories": categories, "categoryDisplayNames": [SIMPLIFY(c) for c in categories],
              "visualFamilies": [{"id": key, "label": label} for key, label in FAMILY_LABEL.items()],
              "ingredients": ingredients, "tables": tables, "edges": edge_list, "conflicts": conflicts}
    OUT.mkdir(parents=True, exist_ok=True)
    compact = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    (OUT / "catalog.json").write_text(compact, encoding="utf-8")
    (OUT / "data.js").write_text("window.FLAVOR_DATA=" + compact.replace("</", "<\\/") + ";\n", encoding="utf-8")
    name_fields = ["id", "name", "displayName", "visualFamily", "visualFamilyLabel", "image",
                   "nameNeedsReview", "recommendationEligible", "nameVisuallyReviewed", "recordCount", "sourceRef"]
    name_items = [{k: item[k] for k in name_fields} for item in ingredients]
    (OUT / "names.json").write_text(json.dumps(name_items, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "name-review-needed.json").write_text(json.dumps([
        {"id": item["id"], "name": item["name"], "displayName": item["displayName"],
         "reasons": item["nameReviewReasons"], "nameVisuallyReviewed": item["nameVisuallyReviewed"],
         "sourceRef": item["sourceRef"], "recordCount": item["recordCount"],
         "records": [{"id": rec["id"], "role": rec["role"], "sourceRef": rec["sourceRef"],
                      "nameReviewStatus": rec["nameReviewStatus"]} for rec in item["records"]]}
        for item in ingredients if item["nameNeedsReview"]], ensure_ascii=False, indent=2), encoding="utf-8")
    with (OUT / "names.tsv").open("w", encoding="utf-8-sig", newline="") as f:
        fields = [f for f in name_fields if f != "sourceRef"]
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows({k: item[k] for k in fields} for item in ingredients)
    (OUT / "conflicts.json").write_text(json.dumps(conflicts, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "catalog_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
