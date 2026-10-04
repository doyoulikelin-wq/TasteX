#!/usr/bin/env python3
"""Merge reviewed processing evidence without replacing source fields or inventing deltas.

Creates the browser dataset and three complete relational index CSVs. All aliases
below are explicit navigation choices; original labels and records are retained.
"""
from __future__ import annotations
import collections
import copy
import csv
import hashlib
import json
import sys
import unicodedata
from pathlib import Path

STUDIO = Path(__file__).resolve().parents[1]
ROOT = STUDIO.parent
DATA = STUDIO / 'data'
sys.path.insert(0, str(ROOT / 'tmp/flavor_catalog_deps'))
from opencc import OpenCC
SIMPLIFY = OpenCC('t2s').convert
TRADITIONAL = OpenCC('s2t').convert

DOMAIN_LABELS = {'aroma': '香气', 'taste': '味觉', 'texture': '质地与口感', 'chemical': '化学成分', 'color': '色泽', 'other': '其他'}
DIRECTION_LABELS = {'increase': '增加', 'decrease': '减少', 'emerge': '形成或出现', 'change': '发生变化', 'no_significant_change': '未发现显著变化', 'conditional': '取决于条件'}
KIND_LABELS = {'change': '变化证据', 'condition_dependency': '条件依赖', 'state_profile': '加工状态描述'}
# These are exact aliases, never substring classifications. Aroma and taste stay separate.
EFFECT_ALIASES = {
    'aroma': {
        '果香': '水果香气', '水果香': '水果香气', '水果香气': '水果香气', '水果气味': '水果香气', '水果': '水果香气',
        '花香': '花卉香气', '花卉香': '花卉香气', '花卉香气': '花卉香气', '花卉气味': '花卉香气', '花卉': '花卉香气',
        '坚果': '坚果香气', '坚果香': '坚果香气', '坚果香气': '坚果香气', '坚果气味': '坚果香气',
        '烘烤': '烘烤香气', '烘烤香': '烘烤香气', '烘烤香气': '烘烤香气', '烘烤气味': '烘烤香气',
        '焦糖': '焦糖香气', '焦糖香': '焦糖香气', '焦糖香气': '焦糖香气', '焦糖气味': '焦糖香气',
        '柑橘': '柑橘香气', '柑橘香': '柑橘香气', '柑橘香气': '柑橘香气', '柑橘气味': '柑橘香气',
        '青绿': '青绿香气', '青绿香': '青绿香气', '青绿香气': '青绿香气', '青绿气味': '青绿香气',
        '硫味': '硫香气', '含硫气味': '硫香气', '硫香气': '硫香气', '硫气味': '硫香气',
        '乳酪': '乳酪香气', '乳酪香': '乳酪香气', '乳酪香气': '乳酪香气', '乳酪气味': '乳酪香气',
    },
    'chemical': {'挥发性化合物': '挥发物'},
    'taste': {'甜': '甜味', '甜度': '甜味', '甜味': '甜味', '鲜味': '鲜味', '鲜': '鲜味', '苦': '苦味', '苦味': '苦味'},
}
METHOD_ALIASES = {'蒸制': '蒸制', '蒸煮': '蒸煮', '水煮': '水煮', '煮沸': '煮沸', '油炸': '油炸', '冷藏储存': '冷藏', '冷藏贮藏': '冷藏'}
# Explicitly reviewed family members, only for RELATED-CONTEXT navigation.
# These entries never assert state equivalence or transfer numerical responses.
FAMILIES = {
    '大蒜': ['大蒜', '蒜', '蒜泥', '蒜末', '烤蒜泥', '黑蒜', '黑蒜泥', '炸大蒜'],
    '番茄': ['番茄', '番茄泥', '新鲜番茄汁', '巴斯德灭菌法番茄汁', '巴氏杀菌番茄汁', '罐头番茄', '樱桃番茄', '橘色番茄', '义大利带藤番茄'],
    '甜菜': ['甜菜', '水煮甜菜', '水煮去皮甜菜', '煎甜菜', '烤甜菜', '烘烤甜菜', '甜菜汁', '甜菜脆片'],
    '胡萝卜': ['胡萝卜', '生胡萝卜', '水煮胡萝卜', '紫胡萝卜'],
    '咖啡': ['咖啡', '咖啡豆', '咖啡粉', '滴滤咖啡', '阿拉比卡咖啡', '现煮阿拉比卡咖啡', '现煮手冲咖啡', '现磨咖啡', '哥伦比亚咖啡', '土耳其咖啡', '烤罗布斯塔咖啡豆', '烤阿拉比卡咖啡豆'],
    '可可': ['可可', '可可豆', '可可豆碎粒', '可可粉', '无糖可可粉', '巧克力', '黑巧克力', '70%黑巧克力'],
    '香草': ['香草', '香草荚', '大溪地香草', '波本香草'],
    '茶': ['茶', '茶叶', '乌龙茶', '中国煎茶', '大吉岭茶', '抹茶', '东方美人茶白毫乌龙', '正山小种茶', '煎茶', '烟熏红茶', '红茶', '绿茶', '茉莉花茶', '蜜香红茶大叶乌龙', '开花茶', '龙井茶'],
    '香菇': ['香菇', '干香菇', '鲜香菇'],
}


def simplify(value):
    return SIMPLIFY(unicodedata.normalize('NFKC', str(value))).strip()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def read(name):
    return json.loads((DATA / name).read_text())


def index_entries(record, index):
    if index == 'method':
        return record['methodIndexEntries']
    if index == 'ingredient':
        return record['ingredientIndexEntries']
    return [{'key': e['groupKey'], 'label': e['normalizedLabel'], 'domain': e['domain'], 'direction': e['direction']} for e in record['normalizedEffects']]


def normalize_record(record, evidence, catalog_by_name, catalog_family):
    result = copy.deepcopy(record)
    result['originalEffects'] = copy.deepcopy(record['effects'])
    result['normalizedEffects'] = []
    for effect in record['effects']:
        domain, direction = effect['domain'], effect['direction']
        label = simplify(effect['label'])
        normalized = EFFECT_ALIASES.get(domain, {}).get(label, label)
        result['normalizedEffects'].append({**copy.deepcopy(effect), 'originalLabel': effect['label'], 'normalizedLabel': normalized, 'label': normalized, 'groupKey': f'{domain}|{normalized}|{direction}', 'normalizationBasis': 'explicit_exact_alias' if label != normalized else 'script_normalization_only'})
    result['methodIndexEntries'] = [{'key': METHOD_ALIASES.get(simplify(name), simplify(name)), 'label': METHOD_ALIASES.get(simplify(name), simplify(name)), 'originalLabel': name} for name in record['methods']]
    result['ingredientIndexEntries'] = [{'key': simplify(name), 'label': simplify(name), 'originalLabel': name} for name in record['ingredientNames']]
    links = []
    for evidence_id in record['source'].get('evidenceIds', []):
        if evidence_id not in evidence:
            raise ValueError(f'{record["id"]}: missing evidence reference {evidence_id}')
        for link in evidence[evidence_id].get('links', []):
            links.append({**copy.deepcopy(link), 'sourceEvidenceId': evidence_id, 'quantitativeTransferAllowed': False})
    for name in record['ingredientNames']:
        for ingredient, match_basis in catalog_by_name.get(simplify(name), []):
            links.append({'ingredientId': ingredient['id'], 'kind': 'exact_name' if ingredient['name'] == name or ingredient['displayName'] == name else 'alias_name', 'reason': '食材原名或显示名称完全匹配（仅简繁及字符形式规范）；加工条件仍须逐条核对', 'matchedName': name, 'nameMatchBasis': match_basis, 'quantitativeTransferAllowed': False})
        for family, names in FAMILIES.items():
            if simplify(name) not in {simplify(n) for n in names}:
                continue
            for ingredient in catalog_family.get(family, []):
                if any(link['ingredientId'] == ingredient['id'] and link['kind'] in ('exact_name', 'alias_name') for link in links):
                    continue
                links.append({'ingredientId': ingredient['id'], 'kind': 'related_context', 'reason': f'人工限定的{family}原料及加工状态索引；来源与当前食材的品种、部位或加工状态可能不同，不认定为同一试样', 'matchedName': name, 'family': family, 'nameMatchBasis': 'explicit_reviewed_family_navigation', 'quantitativeTransferAllowed': False})
    result['ingredientLinks'] = list({canonical(link): link for link in links}.values())
    raw_search = json.dumps(record, ensure_ascii=False)
    navigation_search = json.dumps({'effects': result['normalizedEffects'], 'methods': result['methodIndexEntries'], 'ingredients': result['ingredientIndexEntries'], 'effectLabels': [{'domain': DOMAIN_LABELS[e['domain']], 'direction': DIRECTION_LABELS[e['direction']]} for e in record['effects']], 'recordKindLabel': KIND_LABELS[record['recordKind']], 'sourceKindLabel': '书中证据' if record['source']['kind'] == 'book' else '研究文献'}, ensure_ascii=False)
    search = raw_search + '\n' + navigation_search
    result['searchText'] = '\n'.join(dict.fromkeys([search, SIMPLIFY(search), TRADITIONAL(search)]))
    result['sourceRecordSha256'] = digest(record)
    return result


def csv_export(records, index, filename):
    header = ['索引项', '维度', '变化方向', '记录ID', '标题', '食材', '加工方式', '加工前', '加工后', '适用条件', '变化摘要', '作用机制', '限制', '证据类型', '来源类别', '来源标题', 'PDF页', '书页', 'DOI', '来源网址', '原始测量或书述数值JSON', '完整记录JSON']
    count = 0
    with (DATA / filename).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        for record in records:
            seen = set()
            for entry in index_entries(record, index):
                if entry['key'] in seen:
                    continue
                seen.add(entry['key'])
                source = record['source']
                writer.writerow([entry['label'], DOMAIN_LABELS.get(entry.get('domain'), ''), DIRECTION_LABELS.get(entry.get('direction'), ''), record['id'], record['title'], '；'.join(record['ingredientNames']), '；'.join(record['methods']), record['before'], record['after'], record['conditions'], record['summary'], record['mechanism'], record['limitations'], KIND_LABELS.get(record['recordKind'], record['recordKind']), source['kind'], source.get('title', ''), '；'.join(map(str, source.get('pdfPages', []))), '；'.join(map(str, source.get('bookPages', []))), source.get('doi', ''), source.get('url', ''), json.dumps(record['reportedValues'], ensure_ascii=False), json.dumps({key: value for key, value in record.items() if key != 'searchText'}, ensure_ascii=False)])
                count += 1
    return count


def main():
    book, research = read('processing-book.json'), read('processing-research.json')
    original_records = book['records'] + research['records']
    evidence_data = read('evidence-full.json')
    evidence = {record['id']: record for record in evidence_data['records']}
    catalog = read('catalog.json')
    by_name = collections.defaultdict(list)
    catalog_family = collections.defaultdict(list)
    for ingredient in catalog['ingredients']:
        names = {ingredient['name'], ingredient['displayName']}
        for name in names:
            by_name[simplify(name)].append((ingredient, 'exact_original_or_display_name'))
        for family, names in FAMILIES.items():
            if {simplify(ingredient['name']), simplify(ingredient['displayName'])} & {simplify(n) for n in names}:
                catalog_family[family].append(ingredient)
    ids = []
    for record in original_records:
        ids.append(record['id'])
        for key in ['title', 'ingredientNames', 'methods', 'before', 'after', 'conditions', 'mechanism', 'summary', 'limitations', 'recordKind', 'effects', 'source', 'original', 'reportedValues', 'evidenceLevel']:
            if key not in record:
                raise ValueError(f'{record["id"]}: missing {key}')
        if not record['ingredientNames'] or not record['methods'] or not record['conditions'] or not record['source'].get('title'):
            raise ValueError(f'{record["id"]}: empty names, methods, conditions or source')
        if record['source']['kind'] not in ('book', 'research'):
            raise ValueError(f'{record["id"]}: unknown source kind')
        if record['recordKind'] not in KIND_LABELS:
            raise ValueError(f'{record["id"]}: unknown recordKind')
        for effect in record['effects']:
            if effect['domain'] not in DOMAIN_LABELS or effect['direction'] not in DIRECTION_LABELS:
                raise ValueError(f'{record["id"]}: invalid effect domain/direction')
    if len(ids) != len(set(ids)):
        raise ValueError('Processing record IDs must be globally unique')
    records = [normalize_record(record, evidence, by_name, catalog_family) for record in original_records]
    audit = book.get('audit253', book.get('audit', []))
    evidence_used = sorted({eid for record in records for eid in record['source'].get('evidenceIds', [])})
    studies = {record['source'].get('doi') or record['source'].get('url') or record['source']['title'] for record in records if record['source']['kind'] == 'research'}
    metrics = {
        'records': len(records), 'sourceRecords': len(original_records),
        'bookRecords': sum(record['source']['kind'] == 'book' for record in records),
        'researchRecords': sum(record['source']['kind'] == 'research' for record in records),
        'bookOriginalEvidenceUsed': len(evidence_used),
        'bookSupplementCount': sum(record['source']['kind'] == 'book' and not record['source'].get('evidenceIds') for record in records),
        'researchStudyCount': len(studies), 'originalAuditCount': len(audit),
        **{name: len({entry['key'] for record in records for entry in index_entries(record, index)}) for index, name in [('method', 'methodGroups'), ('effect', 'effectGroups'), ('ingredient', 'ingredientGroups')]},
    }
    result = {
        'schemaVersion': 'processing-evidence-1.0', 'records': records,
        'references': copy.deepcopy(research.get('references', [])), 'audit253': copy.deepcopy(audit),
        'sourceMetadata': {'book': {key: copy.deepcopy(value) for key, value in book.items() if key not in ('records', 'audit253', 'audit')}, 'research': {key: copy.deepcopy(value) for key, value in research.items() if key not in ('records', 'references')}},
        'metrics': metrics,
        'labels': {'domains': DOMAIN_LABELS, 'directions': DIRECTION_LABELS, 'kinds': KIND_LABELS},
        'coverage': {'scope': '当前已提取的 253 条书中证据逐条审核，加上明确列出的书页补充与研究记录；不代表全书或所有文献已穷尽。', 'evidenceIds': evidence_used, 'unlinkedRecordIds': [record['id'] for record in records if not record['ingredientLinks']], 'indexCountPolicy': '一条证据可进入多个加工方式、效果或食材组；每组内按记录 ID 去重。分组数量不等于实验样本量。'},
        'policies': [
            '每条源记录的原字段完整保留；规范标签只用于索引，originalEffects 保留源标签。',
            '相近效果必须具有相同维度和方向；增加、形成、减少及未发现显著变化分别分组。',
            '香气中的甜香、焦糖香等不等于味觉甜度；化学峰面积或挥发物含量不等于感官强度。',
            '未测定、未提供与无显著变化均不替换为 0；不据此模拟风味百分比或生成无依据温时曲线。',
            '食材名称及家族关联仅用于导航，不授权跨品种、原料状态、加工设备或条件转移数值。',
            '按食材索引以来源食材名称形成同名导航组；catalog 稳定 ID 及所有关联仍独立保留，不合并同名食材身份。',
            '加工状态描述不等于前后对照；关联研究的结论需连同原研究条件和证据范围阅读。',
        ],
        'normalization': {'effectAliases': EFFECT_ALIASES, 'methodAliases': METHOD_ALIASES, 'reviewedRelatedFamilies': FAMILIES},
        'inputIntegrity': {'bookSha256': digest(book), 'researchSha256': digest(research), 'originalEvidenceSha256': digest(evidence_data['source']), 'originalDotSha256': digest(evidence_data['dotSource']), 'sourceRecordHashes': {record['id']: digest(record) for record in original_records}},
    }
    csv_files = [('method', '加工索引_加工方式.csv'), ('effect', '加工索引_加工效果.csv'), ('ingredient', '加工索引_食材.csv')]
    result['exports'] = [{'index': index, 'path': f'data/{filename}', 'associationRows': csv_export(records, index, filename)} for index, filename in csv_files]
    (DATA / 'processing.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    (DATA / 'processing-data.js').write_text('window.FLAVOR_PROCESSING=' + json.dumps(result, ensure_ascii=False, separators=(',', ':')) + ';\n')
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
