'use strict';
// Run after build_processing.py. These checks target provenance and index semantics.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { create } = require('../processing-engine.js');
const dataDir = path.join(__dirname, '../data');
const load = name => JSON.parse(fs.readFileSync(path.join(dataDir, name), 'utf8'));
const tests = [];
function test(name, work) { work(); tests.push(name); console.log(`PASS ${name}`); }
function effect(domain, label, direction) { return { domain, label, normalizedLabel: label, direction, detail: '保留条件', groupKey: `${domain}|${label}|${direction}` }; }
function rec(id, extra = {}) {
  return { id, title: id, ingredientNames: ['甲食材'], methods: ['水煮'], recordKind: 'change', source: { kind: 'book', title: '书' }, conditions: '100 °C；时间未说明', effects: [effect('aroma', '甜香', 'increase')], normalizedEffects: [effect('aroma', '甜香', 'increase')], reportedValues: [{ metric: '强度', value: null, unit: null, context: '未测定' }], ...extra };
}
const fixture = { records: [
  rec('a', { ingredientNames: ['甲食材', '乙食材'], methods: ['水煮', '蒸'], searchText: '甲 乙 水煮 蒸 100 °C 甜香 上升', ingredientLinks: [{ ingredientId: 'catalog-a', kind: 'exact_name' }, { ingredientId: 'catalog-a', kind: 'related_context' }] }),
  rec('b', { normalizedEffects: [effect('taste', '甜香', 'increase')], searchText: '甲 水煮 甜香 味觉', source: { kind: 'research', title: '论文' } }),
  rec('c', { normalizedEffects: [effect('aroma', '甜香', 'decrease')], searchText: '甲 甜香 下降' }),
  rec('d', { normalizedEffects: [effect('aroma', '甜香', 'emerge')], searchText: '甲 甜香 形成' }),
  rec('e', { normalizedEffects: [effect('aroma', '甜香', 'no_significant_change')], recordKind: 'condition_dependency', searchText: '甲 滴滤 温度 未发现显著变化 null' }),
  rec('f', { methods: ['水煮', '水煮'], normalizedEffects: [effect('aroma', '甜香', 'increase'), effect('aroma', '甜香', 'increase')], searchText: '甲 甜香 上升' }),
] };
const baseline = JSON.stringify(fixture);
const engine = create(fixture);

test('effects retain domain and direction boundaries, including emergence and null effects', () => {
  const groups = engine.groups('effect');
  assert.equal(groups.length, 5);
  assert.equal(groups.find(g => g.key === 'aroma|甜香|increase').records.length, 2);
  assert.equal(groups.find(g => g.key === 'taste|甜香|increase').records.length, 1);
  assert.equal(groups.find(g => g.direction === 'no_significant_change').records[0].id, 'e');
});

test('multi-membership indexes deduplicate each source record within a group', () => {
  const methods = engine.groups('method');
  assert.equal(methods.find(g => g.key === '水煮').recordIds.length, 6);
  assert.equal(methods.find(g => g.key === '蒸').recordIds.length, 1);
  const ingredients = engine.groups('ingredient');
  assert.equal(ingredients.find(g => g.label === '甲食材').records.length, 6);
  assert.equal(ingredients.find(g => g.label === '乙食材').records.length, 1);
});

test('all index views and selection use the same filtered population', () => {
  const selected = engine.selection({ query: '甲 甜香', source: 'research', domain: 'taste', index: 'method', groupKey: '水煮' });
  assert.deepEqual(selected.records.map(r => r.id), ['b']);
  assert.deepEqual(selected.population.map(r => r.id), ['b']);
  assert.deepEqual(selected.groups.flatMap(g => g.recordIds), ['b']);
  assert.equal(engine.filter({ query: '甲 缺失词' }).length, 0);
  assert.equal(engine.filter({ kind: 'condition_dependency' })[0].id, 'e');
  assert.equal(engine.filter({ query: '未发现显著变化' })[0].id, 'e');
  assert.equal(engine.selection({ source: 'research', groupKey: '蒸' }).records.length, 0);
});

test('ingredient context retains all link kinds without multiplying records', () => {
  const linked = engine.forIngredient('catalog-a');
  assert.equal(linked.length, 1);
  assert.deepEqual(linked[0].linkKinds, ['exact_name', 'related_context']);
  assert.equal(linked[0].matchingLinks.length, 2);
  assert.equal(engine.forIngredient('missing').length, 0);
});

test('unknown measurements remain null and indexes never mutate source records', () => {
  assert.equal(engine.filter()[0].reportedValues[0].value, null);
  assert.equal(engine.filter()[0].reportedValues[0].unit, null);
  assert.equal(JSON.stringify(fixture), baseline);
  assert.throws(() => engine.groups('bad-index'), /Unknown/);
  assert.throws(() => create({ records: [rec('same'), rec('same')] }), /duplicate/);
});

if (fs.existsSync(path.join(dataDir, 'processing.json'))) {
  const data = load('processing.json');
  const book = load('processing-book.json');
  const research = load('processing-research.json');
  const evidence = load('evidence-full.json');
  const allOriginal = [...book.records, ...research.records];
  const live = create(data);
  test('every merged source record retains every original field exactly', () => {
    assert.equal(data.records.length, allOriginal.length);
    const merged = new Map(data.records.map(r => [r.id, r]));
    for (const record of allOriginal) {
      const target = merged.get(record.id); assert.ok(target, record.id);
      for (const [key, value] of Object.entries(record)) assert.deepEqual(target[key], value, `${record.id}.${key}`);
      assert.deepEqual(target.originalEffects, record.effects);
    }
  });
  test('the processing audit covers all 253 original evidence records once', () => {
    assert.ok(Array.isArray(data.audit253));
    assert.equal(data.audit253.length, 253);
    const audited = data.audit253.map(row => row.evidenceId || row.evidence_id || row.id);
    assert.equal(new Set(audited).size, 253);
    assert.deepEqual([...audited].sort(), evidence.records.map(row => row.id).sort());
  });
  test('all processing records carry conditions, provenance, complete effects and safe links', () => {
    const catalogIds = new Set(load('catalog.json').ingredients.map(row => row.id));
    for (const record of data.records) {
      assert.ok(record.conditions.trim(), record.id);
      assert.ok(record.source.title, record.id);
      assert.ok(['book', 'research'].includes(record.source.kind));
      assert.ok(record.methods.length && record.ingredientNames.length);
      assert.equal(record.normalizedEffects.length, record.effects.length);
      for (let i = 0; i < record.effects.length; i++) {
        assert.equal(record.normalizedEffects[i].domain, record.effects[i].domain);
        assert.equal(record.normalizedEffects[i].direction, record.effects[i].direction);
        assert.equal(record.normalizedEffects[i].originalLabel, record.effects[i].label);
      }
      for (const link of record.ingredientLinks) {
        assert.ok(catalogIds.has(link.ingredientId));
        assert.equal(link.quantitativeTransferAllowed, false);
        assert.ok(link.reason);
      }
    }
  });
  test('real three-way indexes account for each association without dropping records', () => {
    for (const index of ['method', 'effect', 'ingredient']) {
      const groups = live.groups(index);
      const expectedRecordIds = data.records.filter(r => index !== 'effect' || r.effects.length).map(r => r.id).sort();
      assert.deepEqual([...new Set(groups.flatMap(g => g.recordIds))].sort(), expectedRecordIds);
      for (const group of groups) {
        assert.equal(group.records.length, new Set(group.recordIds).size);
        assert.deepEqual(group.recordIds, group.records.map(r => r.id));
      }
      const exported = data.exports.find(entry => entry.index === index);
      assert.equal(exported.associationRows, groups.reduce((n, group) => n + group.records.length, 0));
      assert.ok(fs.existsSync(path.join(dataDir, path.basename(exported.path))));
    }
  });
  test('research null-effect results and temperatures remain searchable without fabrication', () => {
    const nullEffects = data.records.filter(r => r.source.kind === 'research' && r.effects.some(e => e.direction === 'no_significant_change'));
    assert.ok(nullEffects.length, 'Include the controlled drip-coffee null result');
    for (const record of nullEffects) assert.ok(live.filter({ query: record.title, source: 'research' }).some(r => r.id === record.id));
    for (const original of allOriginal) {
      const merged = data.records.find(r => r.id === original.id);
      assert.deepEqual(merged.reportedValues, original.reportedValues);
    }
  });
  test('the complete original attribute and dot objects still match their source files', () => {
    const root = path.join(__dirname, '../..');
    // The portable repository keeps exact UTF-8 source snapshots inside SQLite.
    // Verify their stored hashes before using them as the source comparison.
    const script = `import hashlib,json,sqlite3,sys
from pathlib import Path
db=sqlite3.connect(Path(sys.argv[1]).resolve().as_uri()+"?mode=ro",uri=True)
out={}
try:
 for key in ("attribute-source","dot-source"):
  text,expected=db.execute("SELECT content_json,sha256 FROM source_snapshots WHERE id=?",(key,)).fetchone()
  assert hashlib.sha256(text.encode("utf-8")).hexdigest()==expected
  value=json.loads(text)
  semantic=hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest()
  out[key]={"value":value,"sha256":expected,"semantic_sha256":semantic}
finally:
 db.close()
print(json.dumps(out,ensure_ascii=False))`;
    const snapshots = JSON.parse(require('node:child_process').execFileSync(process.env.PYTHON || 'python3', ['-c', script, path.join(root, 'flavor-database/flavor.sqlite')], {encoding: 'utf8', maxBuffer: 16 * 1024 * 1024}));
    const original = snapshots['attribute-source'].value;
    const dots = snapshots['dot-source'].value;
    assert.deepEqual(evidence.source, original);
    assert.deepEqual(evidence.dotSource, dots);
    assert.equal(data.inputIntegrity.originalEvidenceSha256, snapshots['attribute-source'].semantic_sha256);
    assert.equal(data.inputIntegrity.originalDotSha256, snapshots['dot-source'].semantic_sha256);
  });
  test('coverage metrics are source counts and not association sums', () => {
    assert.equal(data.metrics.records, data.records.length);
    assert.equal(data.metrics.bookRecords + data.metrics.researchRecords, data.records.length);
    assert.equal(data.metrics.originalAuditCount, 253);
    assert.equal(data.metrics.methodGroups, live.groups('method').length);
    assert.equal(data.metrics.effectGroups, live.groups('effect').length);
    assert.equal(data.metrics.ingredientGroups, live.groups('ingredient').length);
  });
  const qa = path.join(__dirname, '../qa/processing-integrity.json');
  fs.writeFileSync(qa, JSON.stringify({ status: 'passed', tests: tests.length, testNames: tests, metrics: data.metrics, sourceRecordsPreserved: true, audit253Complete: true, allIngredientLinksForbidQuantitativeTransfer: true, originalAttributeSourceUnchanged: true, originalAttributeSourceSha256: data.inputIntegrity.originalEvidenceSha256, originalDotSourceUnchanged: true, originalDotSourceSha256: data.inputIntegrity.originalDotSha256 }, null, 2) + '\n');
} else {
  console.log('INFO Source-curation files not built yet; ran synthetic index semantics only.');
}
console.log(`${tests.length} processing checks passed.`);
