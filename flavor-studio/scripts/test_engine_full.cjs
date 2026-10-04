'use strict';
// Run: node flavor-studio/scripts/test_engine_full.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { create } = require('../engine-full.js');

const categories = Array.from({ length: 14 }, (_, index) => `category-${index}`);
const vector = (...values) => [...values, ...Array(Math.max(0, 14 - values.length)).fill(0)];
function record(id, presence, extra = {}) {
  return { id, tableId: `table-${id}`, role: 'main', presence, sourceRef: { rowId: id, tableId: `table-${id}`, pdfPage: 43, bookPage: 40 }, ...extra };
}
function ingredient(id, records, extra = {}) {
  // The canonical vector intentionally disagrees with real rows. The engine must
  // never silently fall back to it, even when the real record set is empty.
  return { id, name: id, displayName: id, presence: Array(14).fill(1), canonical: { presence: Array(14).fill(1), recordId: 'canonical-not-a-source-row' }, records, ...extra };
}
const recordsA = [record('a1', vector(1, 1, null, 0)), record('a2', vector(0, 1, 1, 0)), record('a3', vector(1, 1, null, 0)), record('a-example', vector(1, 0, 0, 1), { isExample: true })];
const recordsB = [record('b1', vector(1, 1, 1, 0)), record('b2', vector(1, 0, 1, 0))];
const dataset = {
  categories,
  ingredients: [
    ingredient('A', recordsA), ingredient('B', recordsB),
    ingredient('C', [record('c1', vector(0, 0, 0))]),
    ingredient('all-unknown', [record('unknown1', Array(14).fill(null))]),
    ingredient('empty', []),
    ingredient('same-name-one', [record('same1', vector(1, 0))], { name: 'source-name-one', displayName: 'same visible name' }),
    ingredient('same-name-two', [record('same2', vector(0, 1))], { name: 'source-name-two', displayName: 'same visible name' }),
    ingredient('only-example', [record('example-only', vector(1, 1), { isExample: true })]),
    ingredient('main-teaching', [record('teacher-main', vector(1), { tableId: 'teaching-table' })]),
    ingredient('paired-teaching', [record('teacher-pair', vector(1), { tableId: 'teaching-table', role: 'pairing', mainIngredientId: 'main-teaching', sharedWithMain: vector(1) })]),
  ],
  tables: [{ id: 'teaching-table', isExample: true, mainRecordId: 'teacher-main', recommendationEligible: false }],
  edges: [
    { id: 'ab-small', tableId: 't-ab-one', mainId: 'A', pairedId: 'B', shared: vector(1, 0, null), recommendationEligible: true },
    { id: 'ab-large', tableId: 't-ab-two', mainId: 'B', pairedId: 'A', shared: vector(1, 1, 1), recommendationEligible: true },
    { id: 'ab-excluded', tableId: 't-ab-three', mainId: 'A', pairedId: 'B', shared: vector(0, 1), sourceNamesEligible: false, recommendationEligible: false },
    { id: 'bc', tableId: 't-bc', mainId: 'B', pairedId: 'C', shared: vector(1), recommendationEligible: true },
  ],
};
const evidence = { records: [
  { id: 'e1', original: { quote: 'An exact source statement', table: { cells: [1, null, 3] } }, links: [{ ingredientId: 'A', kind: 'exact_name', reason: 'exact raw name' }], domains: ['aroma'] },
  { id: 'e2', original: { note: 'Alias mention' }, links: [{ ingredientId: 'A', kind: 'alias_name', reason: 'script variant' }], domains: ['process'] },
  { id: 'e3', original: { note: 'Context about a different ingredient' }, links: [{ ingredientId: 'A', kind: 'related_context', reason: 'comparison only' }], domains: ['taste'] },
  { id: 'e4', original: { note: 'One record with two kinds' }, links: [{ ingredientId: 'A', kind: 'exact_name', reason: 'named' }, { ingredientId: 'A', kind: 'related_context', reason: 'context' }, { ingredientId: 'B', kind: 'exact_name', reason: 'also named' }], domains: ['texture'] },
] };
const before = JSON.stringify({ dataset, evidence });
const engine = create(dataset, evidence);
const tests = [];
function test(name, work) { work(); tests.push(name); console.log(`PASS ${name}`); }

test('all real source rows, conflicts and nulls are preserved; examples excluded', () => {
  const p = engine.sourceProfile('A');
  assert.equal(p.recordCount, 3); assert.equal(p.sourceRecordCount, 4); assert.equal(p.variantCount, 2);
  assert.equal(p.categories[0].status, 'conflict'); assert.equal(p.categories[0].marked, 2); assert.equal(p.categories[0].unmarked, 1);
  assert.equal(p.categories[1].status, 'marked'); assert.equal(p.categories[2].status, 'unknown'); assert.equal(p.categories[2].unknown, 2); assert.equal(p.categories[2].marked, 1);
  assert.equal(p.categories[3].status, 'unmarked'); assert.equal(p.excludedExampleCount, 1);
  assert.deepEqual(p.variants.map(v => v.recordCount).sort(), [1, 2]);
  assert.deepEqual(p.categories[2].unknownSourceIds, ['a1', 'a3']);
});

test('single-source selection is explicit and cannot borrow another ingredient record', () => {
  const p = engine.sourceProfile('A', { recordId: 'a2' }); assert.equal(p.recordCount, 1); assert.equal(p.categories[0].status, 'unmarked');
  assert.throws(() => engine.sourceProfile('A', { recordId: 'b1' }), /does not belong/);
  assert.equal(engine.sourceProfile('A', { recordId: 'a-example' }).recordCount, 0);
  assert.equal(engine.sourceProfile('A', { recordId: 'a-example', includeExamples: true }).recordCount, 1);
});

test('no canonical fallback exists for empty/example-only record sets', () => {
  for (const id of ['empty', 'only-example']) {
    const p = engine.sourceProfile(id); assert.equal(p.recordCount, 0); assert.equal(p.variantCount, 0);
    assert.ok(p.categories.every(c => c.status === 'unknown' && c.marked === 0 && c.unmarked === 0));
  }
  assert.equal(engine.compare('empty', 'A').min, null);
  assert.equal(engine.compare('empty', 'A').variantComparisons, 0);
});

test('same display name never merges stable source ingredient IDs', () => {
  assert.deepEqual(engine.sourceProfile('same-name-one').sourceIds, ['same1']);
  assert.deepEqual(engine.sourceProfile('same-name-two').sourceIds, ['same2']);
  assert.equal(engine.compare('same-name-one', 'same-name-two').min, 0);
});

test('Jaccard enumerates distinct vectors, retains source multiplicity and reports ranges', () => {
  const c = engine.compare('A', 'B');
  assert.equal(c.variantComparisons, 4); assert.equal(c.sourcePairCount, 6); assert.equal(c.unknownComparisons, 2);
  assert.equal(c.min, 1 / 3); assert.equal(c.max, 1);
  assert.equal(c.details.reduce((sum, d) => sum + d.sourcePairCount, 0), 6);
  assert.ok(c.details.every(d => d.aSourceIds.length === d.aRecordCount && d.bSourceIds.length === d.bRecordCount));
  assert.deepEqual(c.commonCertain, []);
  assert.deepEqual(c.sharedPossible, [0, 1, 2]);
  assert.equal(c.isPreferencePrediction, false);
});

test('unknown-only comparisons have no known score and bounded possibility is not confidence', () => {
  const c = engine.compare('all-unknown', 'A');
  assert.equal(c.min, null); assert.equal(c.max, null); assert.equal(c.comparableComparisons, 0);
  assert.equal(c.unknownComparisons, 2); assert.equal(c.unknownBounds.min, 0); assert.equal(c.unknownBounds.max, 1);
  assert.ok(c.details.every(d => d.score === null && d.knownDimensions === 0));
  assert.equal(engine.compare('C', 'C').min, null); // empty positive union is not a perfect match
});

test('mathematical unknown bounds agree with exhaustive binary completions', () => {
  const sampleValues = [0, 1, null];
  const vectors = [];
  for (const a of sampleValues) for (const b of sampleValues) for (const c of sampleValues) vectors.push([a, b, c]);
  function completions(v) {
    const unknown = v.flatMap((x, i) => x === null ? [i] : []), out = [];
    for (let mask = 0; mask < 2 ** unknown.length; mask += 1) {
      const next = v.slice(); unknown.forEach((index, bit) => { next[index] = (mask >> bit) & 1; }); out.push(next);
    }
    return out;
  }
  for (const av of vectors) for (const bv of vectors) {
    const local = create({ categories, ingredients: [ingredient('x', [record('x1', vector(...av))]), ingredient('y', [record('y1', vector(...bv))])] });
    const actual = local.compare('x', 'y').details[0].unknownBounds;
    const scores = [];
    for (const aa of completions(av)) for (const bb of completions(bv)) {
      const union = aa.filter((x, i) => x === 1 || bb[i] === 1).length;
      if (union) scores.push(aa.filter((x, i) => x === 1 && bb[i] === 1).length / union);
    }
    assert.equal(actual.min, scores.length ? Math.min(...scores) : null, `min ${av}/${bv}`);
    assert.equal(actual.max, scores.length ? Math.max(...scores) : null, `max ${av}/${bv}`);
  }
});

test('target matching exposes all/partial/conflict/unknown buckets with source evidence', () => {
  const m = engine.targetMatch('A', [0, 1, 2, 3]);
  assert.deepEqual(m.matchedAllSource, [1]); assert.deepEqual(m.markedSomeSource, [0, 2]);
  assert.deepEqual(m.conflicting, [0]); assert.deepEqual(m.unknown, [2]); assert.deepEqual(m.unmarked, [3]);
  assert.equal(m.details[2].sources.length, 3); assert.equal(m.details[2].sources[0].value, null);
  assert.ok(!Object.hasOwn(m, 'score')); assert.throws(() => engine.targetMatch('A', [14]), /Unknown aroma/);
});

test('mixture uses source states; grams never become intensity weights', () => {
  const first = engine.mixture([{ id: 'A', amount: 5, unit: 'g' }, { id: 'B', amount: null, unit: 'g' }]);
  const second = engine.mixture([{ id: 'A', amount: 50000, unit: 'g' }, { id: 'B', amount: 0.001, unit: 'g' }]);
  assert.deepEqual(first.categories, second.categories);
  assert.deepEqual(first.selection, [{ id: 'A', amount: 5, unit: 'g' }, { id: 'B', amount: null, unit: 'g' }]);
  assert.deepEqual(first.categories[0].certainIngredientIds, ['B']); assert.deepEqual(first.categories[0].variableIngredientIds, ['A']);
  assert.equal(first.categories[0].min, 1); assert.equal(first.categories[0].max, 2);
  assert.deepEqual(first.categories[2].unknownIngredientIds, ['A']);
  const duplicate = engine.mixture([{ id: 'A', grams: null }, { id: 'A', grams: 10 }]);
  assert.equal(duplicate.ingredientCount, 1); assert.equal(duplicate.selection.length, 2); assert.deepEqual(duplicate.duplicateIngredientIds, ['A']);
  assert.equal(duplicate.amounts[0].grams, null);
  const byRecord = engine.mixture([{ id: 'A', recordId: 'a2', amount: null }]); assert.equal(byRecord.categories[0].max, 0);
});

test('direct pair evidence preserves all rows and exclusions; never takes a strongest edge', () => {
  const p = engine.pairEvidence('A', 'B');
  assert.deepEqual(p.all.map(edge => edge.id), ['ab-small', 'ab-large', 'ab-excluded']);
  assert.equal(p.included.length, 2); assert.equal(p.excluded.length, 1); assert.equal(p.all[0].shared[2], null);
  assert.ok(p.excluded[0].exclusionReasons.includes('source_identity_requires_review'));
  assert.deepEqual(engine.pairEvidence('B', 'A').all.map(edge => edge.id), p.all.map(edge => edge.id));
  assert.ok(p.all.every(edge => edge.sourceRelationScope === 'only_this_table_main_and_paired_row'));
});

test('shared molecule claims do not propagate across A-B and B-C or across source rows', () => {
  assert.equal(engine.pairEvidence('A', 'B').all.length, 3);
  assert.equal(engine.pairEvidence('B', 'C').all.length, 1);
  assert.equal(engine.pairEvidence('A', 'C').all.length, 0);
  assert.equal(engine.pairEvidence('A', 'C').noDirectEvidence, true);
  assert.equal(engine.pairEvidence('A', 'C').isTransitive, false);
  assert.match(engine.compare('A', 'B').sharedPossibleMeaning, /not_evidence_of_shared_molecules/);
});

test('teaching edges are recovered only as labelled source evidence and excluded by default', () => {
  const p = engine.pairEvidence('main-teaching', 'paired-teaching');
  assert.equal(p.all.length, 1); assert.equal(p.examples.length, 1); assert.equal(p.included.length, 0);
  assert.equal(p.all[0].status, 'example'); assert.equal(p.all[0].recoveredFromSourceRow, true);
  assert.equal(engine.pairEvidence('main-teaching', 'paired-teaching', { includeExamples: true }).included.length, 1);
  assert.equal(engine.sourceProfile('paired-teaching').recordCount, 0);
});

test('exact, alias and related evidence remain distinct with complete original objects', () => {
  const e = engine.evidenceFor('A');
  assert.deepEqual(e.exact.map(r => r.id), ['e1', 'e4']); assert.deepEqual(e.aliases.map(r => r.id), ['e2']);
  assert.deepEqual(e.related.map(r => r.id), ['e3', 'e4']); assert.equal(e.direct.length, 3); assert.equal(e.allLinked.length, 4);
  assert.deepEqual(e.exact[0].original, { quote: 'An exact source statement', table: { cells: [1, null, 3] } });
  assert.equal(e.allLinked.find(r => r.id === 'e4').matchingLinks.length, 2);
  assert.deepEqual(engine.evidenceFor('B').exact.map(r => r.id), ['e4']);
  assert.equal(engine.evidenceFor('same-name-one').allLinked.length, 0);
});

test('source input objects are not modified', () => {
  assert.equal(JSON.stringify({ dataset, evidence }), before);
});

const cataloguePath = path.join(__dirname, '..', 'data', 'catalog.json');
if (fs.existsSync(cataloguePath)) {
  test('real catalogue integration: every full source row survives, example rows remain labelled', () => {
    const catalog = JSON.parse(fs.readFileSync(cataloguePath, 'utf8')), real = create(catalog);
    let chapterRows = 0, teachingRows = 0;
    for (const entry of catalog.ingredients) {
      const p = real.sourceProfile(entry.id), all = real.sourceProfile(entry.id, { includeExamples: true });
      chapterRows += p.recordCount; teachingRows += all.recordCount - p.recordCount;
      assert.equal(all.recordCount, entry.records.length);
      assert.ok(p.categories.every(c => c.marked + c.unmarked + c.unknown === p.recordCount));
      assert.equal(p.variants.reduce((sum, v) => sum + v.recordCount, 0), p.recordCount);
      assert.ok(p.records.every(r => !r.isExample));
    }
    assert.equal(chapterRows + teachingRows, catalog.ingredients.reduce((sum, i) => sum + i.records.length, 0));
    assert.equal(teachingRows, 11);
    assert.equal(real.summary.canonicalVectorsUsed, false);
    assert.equal(real.summary.sourceEdges, 9490);
  });
}
console.log(JSON.stringify({ passed: tests.length, failed: 0, tests }, null, 2));
