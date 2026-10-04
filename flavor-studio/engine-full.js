/* Full-source flavour evidence engine. No DOM and no canonical-vector fallback.
 * Browser: FlavorFullEngine.create(catalog, evidence)
 * Node:    require('./engine-full.js').create(catalog, evidence)
 * All returned scores/counts describe source markings, never taste or intensity.
 */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.FlavorFullEngine = api;
})(typeof window !== 'undefined' ? window : typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const CATEGORY_COUNT = 14;
  const DEFAULT_CATEGORIES = ['水果', '柑橘', '花卉', '青綠', '草本', '蔬菜', '焦糖', '烘烤', '堅果', '木質', '辛辣', '乳酪', '動物', '化學'];
  const unique = values => [...new Set(values)];
  const idOf = value => typeof value === 'string' ? value : value && (value.ingredientId || value.id);
  const validCell = value => value === 0 || value === 1 ? value : null;
  const vectorKey = vector => vector.map(value => value === null ? '?' : value).join('');
  const pairKey = (a, b) => [a, b].sort().join('\u0000');

  function create(data, evidence) {
    if (!data || !Array.isArray(data.ingredients)) throw new TypeError('A catalogue with an ingredients array is required.');
    const categories = Array.isArray(data.categories) ? data.categories.slice() : DEFAULT_CATEGORIES.slice();
    if (categories.length !== CATEGORY_COUNT) throw new RangeError('The source model requires exactly 14 aroma categories.');
    const labels = Array.isArray(data.categoryDisplayNames) ? data.categoryDisplayNames.slice() : categories.slice();
    const ingredients = new Map();
    for (const ingredient of data.ingredients) {
      if (!ingredient || typeof ingredient.id !== 'string') throw new TypeError('Every ingredient requires its stable source ID.');
      if (ingredients.has(ingredient.id)) throw new Error(`Duplicate ingredient ID: ${ingredient.id}`);
      ingredients.set(ingredient.id, ingredient);
    }
    const tables = new Map((data.tables || []).map(table => [table.id || table.tableId, table]));
    const recordsByIngredient = new Map();
    const allRecords = new Map();
    const profileCache = new Map();

    for (const [ingredientId, ingredient] of ingredients) {
      const records = (Array.isArray(ingredient.records) ? ingredient.records : []).map((record, position) => {
        const sourceRef = record.sourceRef || {};
        const id = record.id || record.recordId || sourceRef.rowId || `${ingredientId}::unidentified-record-${position}`;
        const tableId = record.tableId || sourceRef.tableId || null;
        const table = tables.get(tableId);
        const suppliedVector = Array.isArray(record.presence) ? record.presence : [];
        const presence = Array.from({ length: CATEGORY_COUNT }, (_, index) => validCell(suppliedVector[index]));
        const invalidCellIndices = presence.flatMap((value, index) => {
          const original = suppliedVector[index];
          return original === 0 || original === 1 || original === null ? [] : [index];
        });
        const result = {
          ...record, id, ingredientId, tableId, presence,
          rawPresence: record.presence,
          isExample: Boolean(record.isExample || table && table.isExample),
          identityEligible: record.identityEligible !== false && record.nameNeedsReview !== true,
          invalidCellIndices,
          sourceRef: {
            ...sourceRef, tableId,
            rowId: sourceRef.rowId || id,
            pdfPage: sourceRef.pdfPage ?? record.pdfPage ?? table?.pdfPage ?? null,
            bookPage: sourceRef.bookPage ?? record.bookPage ?? table?.bookPage ?? null,
          },
          original: record,
        };
        const existing = allRecords.get(id);
        if (existing && existing.ingredientId !== ingredientId) {
          throw new Error(`Source record ${id} is assigned to more than one stable ingredient ID.`);
        }
        allRecords.set(id, result);
        return result;
      });
      recordsByIngredient.set(ingredientId, records);
    }

    function categoryBase(index) {
      return { index, name: categories[index], label: labels[index] || categories[index] };
    }

    function sourceProfile(id, options = {}) {
      const ingredientId = idOf(id);
      const includeExamples = options.includeExamples === true;
      const requestedRecordId = options.recordId ?? null;
      const cacheKey = JSON.stringify([ingredientId, includeExamples, requestedRecordId]);
      if (profileCache.has(cacheKey)) return profileCache.get(cacheKey);
      const ingredient = ingredients.get(ingredientId);
      const originalRecords = recordsByIngredient.get(ingredientId) || [];
      if (requestedRecordId !== null && !originalRecords.some(record => record.id === requestedRecordId)) {
        throw new RangeError(`Record ${requestedRecordId} does not belong to ingredient ${ingredientId}.`);
      }
      const chosenRecords = requestedRecordId === null ? originalRecords : originalRecords.filter(record => record.id === requestedRecordId);
      const records = chosenRecords.filter(record => includeExamples || !record.isExample);
      const excludedExamples = chosenRecords.filter(record => !includeExamples && record.isExample);
      const variantMap = new Map();
      for (const record of records) {
        const key = vectorKey(record.presence);
        if (!variantMap.has(key)) variantMap.set(key, {
          id: `${ingredientId}::${key}`, key, presence: record.presence.slice(), sourceIds: [], sourceRefs: [], records: [], recordCount: 0,
        });
        const variant = variantMap.get(key);
        variant.sourceIds.push(record.id);
        variant.sourceRefs.push(record.sourceRef);
        variant.records.push(record);
        variant.recordCount += 1;
      }
      const variants = [...variantMap.values()];
      const categoryResults = categories.map((_, index) => {
        const markedRecords = records.filter(record => record.presence[index] === 1);
        const unmarkedRecords = records.filter(record => record.presence[index] === 0);
        const unknownRecords = records.filter(record => record.presence[index] === null);
        const marked = markedRecords.length, unmarked = unmarkedRecords.length, unknown = unknownRecords.length;
        // Conflicts remain conflicts even when additional unknown rows exist.
        const status = marked && unmarked ? 'conflict' : unknown || !records.length ? 'unknown' : marked ? 'marked' : 'unmarked';
        return {
          ...categoryBase(index), marked, unmarked, unknown, recordCount: records.length, status,
          sourceIds: records.map(record => record.id),
          markedSourceIds: markedRecords.map(record => record.id),
          unmarkedSourceIds: unmarkedRecords.map(record => record.id),
          unknownSourceIds: unknownRecords.map(record => record.id),
          variantCount: variants.length,
          valueVariantCount: new Set(records.map(record => record.presence[index])).size,
          hasAnyMarked: marked > 0,
          allSourcesMarked: records.length > 0 && marked === records.length,
          allSourcesUnmarked: records.length > 0 && unmarked === records.length,
        };
      });
      const profile = {
        ingredientId, found: Boolean(ingredient), name: ingredient?.name ?? null,
        displayName: ingredient?.displayName || ingredient?.name || null,
        selection: { includeExamples, recordId: requestedRecordId },
        sourceRecordCount: originalRecords.length,
        recordCount: records.length, records, sourceIds: records.map(record => record.id),
        variantCount: variants.length, variants,
        categories: categoryResults,
        excludedExamples, excludedExampleCount: excludedExamples.length,
        selectedRecordFiltered: requestedRecordId !== null && excludedExamples.length > 0,
        identityIssueRecordIds: records.filter(record => !record.identityEligible).map(record => record.id),
        invalidCellRecordIds: records.filter(record => record.invalidCellIndices.length).map(record => record.id),
        certainIndices: categoryResults.filter(category => category.status === 'marked').map(category => category.index),
        markedSomeIndices: categoryResults.filter(category => category.marked > 0).map(category => category.index),
        conflictingIndices: categoryResults.filter(category => category.status === 'conflict').map(category => category.index),
        unknownIndices: categoryResults.filter(category => category.unknown > 0 || !category.recordCount).map(category => category.index),
        basis: 'all_source_records_without_canonical_fallback',
        categorySemantics: 'A source marking is not chemical absence, intensity, concentration, or preference.',
      };
      profileCache.set(cacheKey, profile);
      return profile;
    }

    function selectionOptions(value, defaults = {}) {
      return {
        includeExamples: value && typeof value === 'object' && value.includeExamples !== undefined ? value.includeExamples === true : defaults.includeExamples === true,
        ...(value && typeof value === 'object' && value.recordId != null ? { recordId: value.recordId } : {}),
      };
    }

    function vectorComparison(a, b) {
      const knownIndices = [], unknownIndices = [], common = [], union = [];
      let forcedIntersection = 0, knownMismatch = 0, oneWithUnknown = 0, zeroWithUnknown = 0, bothUnknown = 0;
      for (let index = 0; index < CATEGORY_COUNT; index += 1) {
        const av = a.presence[index], bv = b.presence[index];
        if (av !== null && bv !== null) {
          knownIndices.push(index);
          if (av === 1 || bv === 1) union.push(index);
          if (av === 1 && bv === 1) { common.push(index); forcedIntersection += 1; }
          else if (av === 1 || bv === 1) knownMismatch += 1;
        } else {
          unknownIndices.push(index);
          if (av === null && bv === null) bothUnknown += 1;
          else if (av === 1 || bv === 1) oneWithUnknown += 1;
          else zeroWithUnknown += 1;
        }
      }
      // Scores only use jointly known cells. Empty marked unions have no score;
      // they are not treated as proof of perfect aroma similarity.
      const score = union.length ? common.length / union.length : null;
      const minimumDenominator = forcedIntersection + knownMismatch + oneWithUnknown + zeroWithUnknown + bothUnknown;
      const maximumNumerator = forcedIntersection + oneWithUnknown + bothUnknown;
      const maximumDenominator = maximumNumerator + knownMismatch;
      const completionMin = minimumDenominator ? forcedIntersection / minimumDenominator : null;
      const completionMax = maximumDenominator ? maximumNumerator / maximumDenominator : zeroWithUnknown ? 0 : null;
      return {
        aVariantId: a.id, bVariantId: b.id,
        aPresence: a.presence.slice(), bPresence: b.presence.slice(),
        aSourceIds: a.sourceIds.slice(), bSourceIds: b.sourceIds.slice(),
        aSourceRefs: a.sourceRefs.slice(), bSourceRefs: b.sourceRefs.slice(),
        aRecordCount: a.recordCount, bRecordCount: b.recordCount,
        sourcePairCount: a.recordCount * b.recordCount,
        score, knownJaccard: score,
        intersection: common.length, union: union.length,
        knownIndices, knownDimensions: knownIndices.length,
        unknownIndices, unknownDimensions: unknownIndices.length,
        commonCategories: common, unionCategories: union,
        containsUnknown: unknownIndices.length > 0,
        scoringBasis: 'jaccard_on_jointly_known_source_markings_only',
        emptyKnownUnion: union.length === 0,
        unknownBounds: {
          min: completionMin, max: completionMax,
          basis: 'mathematical_bounds_over_all_possible_unknown_completions_not_imputed_values',
          hasUnknown: unknownIndices.length > 0,
        },
      };
    }

    function compare(a, b, options = {}) {
      const aid = idOf(a), bid = idOf(b);
      const aProfile = sourceProfile(aid, { ...selectionOptions(a, options), ...(options.aRecordId != null ? { recordId: options.aRecordId } : {}) });
      const bProfile = sourceProfile(bid, { ...selectionOptions(b, options), ...(options.bRecordId != null ? { recordId: options.bRecordId } : {}) });
      const details = [];
      for (const av of aProfile.variants) for (const bv of bProfile.variants) details.push(vectorComparison(av, bv));
      const definedScores = details.map(detail => detail.score).filter(value => value !== null);
      const completionMins = details.map(detail => detail.unknownBounds.min).filter(value => value !== null);
      const completionMaxes = details.map(detail => detail.unknownBounds.max).filter(value => value !== null);
      const commonCertain = categories.flatMap((_, index) => aProfile.categories[index].status === 'marked' && bProfile.categories[index].status === 'marked' ? [index] : []);
      const sharedPossible = categories.flatMap((_, index) => aProfile.categories[index].marked > 0 && bProfile.categories[index].marked > 0 ? [index] : []);
      const unknownPossible = categories.flatMap((_, index) => {
        const ac = aProfile.categories[index], bc = bProfile.categories[index];
        return (ac.marked || ac.unknown) && (bc.marked || bc.unknown) && (ac.unknown || bc.unknown) ? [index] : [];
      });
      return {
        a: aid, b: bid, aProfile, bProfile,
        min: definedScores.length ? Math.min(...definedScores) : null,
        max: definedScores.length ? Math.max(...definedScores) : null,
        variantComparisons: details.length,
        comparableComparisons: definedScores.length,
        unknownComparisons: details.filter(detail => detail.containsUnknown).length,
        emptyKnownUnionComparisons: details.filter(detail => detail.emptyKnownUnion).length,
        sourcePairCount: aProfile.recordCount * bProfile.recordCount,
        commonCertain, sharedPossible, sharedVariable: sharedPossible.filter(index => !commonCertain.includes(index)), unknownPossible,
        details,
        unknownBounds: {
          min: completionMins.length ? Math.min(...completionMins) : null,
          max: completionMaxes.length ? Math.max(...completionMaxes) : null,
          basis: 'outer_mathematical_bounds_not_a_prediction_or_confidence_interval',
        },
        scoringBasis: 'range_of_jaccard_values_across_distinct_source_vectors_on_jointly_known_categories',
        sharedPossibleMeaning: 'category_co_marking_in_some_source_rows_not_evidence_of_shared_molecules',
        isPreferencePrediction: false,
      };
    }

    function targetMatch(id, indices, options = {}) {
      if (!Array.isArray(indices)) throw new TypeError('Target categories must be an array of integer indices.');
      const targetIndices = unique(indices);
      for (const index of targetIndices) if (!Number.isInteger(index) || index < 0 || index >= CATEGORY_COUNT) throw new RangeError(`Unknown aroma category index: ${index}`);
      const profile = sourceProfile(id, options);
      const selectedCategories = targetIndices.map(index => profile.categories[index]);
      const result = {
        ingredientId: profile.ingredientId, targetIndices, profile,
        matchedAllSource: [], markedSomeSource: [], conflicting: [], unknown: [], unmarked: [],
        categories: selectedCategories,
        details: selectedCategories.map(category => ({
          ...category,
          sources: profile.records.map(record => ({
            sourceId: record.id, value: record.presence[category.index], sourceRef: record.sourceRef,
            identityEligible: record.identityEligible, reviewStatus: record.reviewStatus,
          })),
        })),
        recordCount: profile.recordCount,
        hasSourceRecords: profile.recordCount > 0,
        bucketSemantics: 'markedSomeSource overlaps conflicting and unknown; unknown means at least one unknown source cell or no usable source row',
      };
      for (const category of selectedCategories) {
        if (category.allSourcesMarked) result.matchedAllSource.push(category.index);
        else if (category.marked > 0) result.markedSomeSource.push(category.index);
        if (category.marked && category.unmarked) result.conflicting.push(category.index);
        if (category.unknown || !category.recordCount) result.unknown.push(category.index);
        if (category.allSourcesUnmarked) result.unmarked.push(category.index);
      }
      return result;
    }

    function mixture(selection, options = {}) {
      if (!Array.isArray(selection)) throw new TypeError('A mixture selection must be an array.');
      // Amount values are preserved exactly as entered. No conversion or implicit
      // normalisation can feed back into source aroma counts.
      const preservedSelection = selection.map(item => typeof item === 'string' ? { id: item, amount: null } : { ...item });
      const uniqueIds = unique(preservedSelection.map(idOf));
      const grouped = new Map(uniqueIds.map(id => [id, preservedSelection.filter(item => idOf(item) === id)]));
      const chosenProfiles = new Map();
      const selectionWarnings = [];
      for (const [ingredientId, items] of grouped) {
        if (!ingredients.has(ingredientId)) selectionWarnings.push({ ingredientId, type: 'unknown_ingredient_id' });
        const explicitRecordIds = unique(items.filter(item => item.recordId != null).map(item => item.recordId));
        // Multiple selections of the same source ID count as one ingredient.
        // If they request conflicting record views, retain the full record set.
        const recordId = explicitRecordIds.length === 1 && items.every(item => item.recordId === explicitRecordIds[0]) ? explicitRecordIds[0] : undefined;
        if (explicitRecordIds.length > 1) selectionWarnings.push({ ingredientId, type: 'multiple_record_selections_use_all_sources', recordIds: explicitRecordIds });
        chosenProfiles.set(ingredientId, sourceProfile(ingredientId, { includeExamples: options.includeExamples === true, ...(recordId !== undefined ? { recordId } : {}) }));
      }
      const categoryResults = categories.map((_, index) => {
        const certainIngredientIds = [], variableIngredientIds = [], unknownIngredientIds = [], unmarkedIngredientIds = [], unknownPresentIngredientIds = [];
        for (const ingredientId of uniqueIds) {
          const category = chosenProfiles.get(ingredientId).categories[index];
          if (category.unknown || !category.recordCount) unknownPresentIngredientIds.push(ingredientId);
          if (category.status === 'marked') certainIngredientIds.push(ingredientId);
          else if (category.status === 'conflict') variableIngredientIds.push(ingredientId);
          else if (category.status === 'unmarked') unmarkedIngredientIds.push(ingredientId);
          else unknownIngredientIds.push(ingredientId);
        }
        const observedSomeIngredientIds = uniqueIds.filter(id => chosenProfiles.get(id).categories[index].marked > 0);
        return {
          ...categoryBase(index), certainIngredientIds, variableIngredientIds, unknownIngredientIds, unmarkedIngredientIds,
          unknownPresentIngredientIds, observedSomeIngredientIds,
          min: certainIngredientIds.length,
          max: certainIngredientIds.length + variableIngredientIds.length + unknownIngredientIds.length,
          certainCount: certainIngredientIds.length, variableCount: variableIngredientIds.length,
          unknownCount: unknownIngredientIds.length, unmarkedCount: unmarkedIngredientIds.length,
          ingredientCount: uniqueIds.length,
          sourceDetails: uniqueIds.map(id => ({ ingredientId: id, ...chosenProfiles.get(id).categories[index] })),
        };
      });
      return {
        selection: preservedSelection,
        amounts: preservedSelection.map((item, index) => ({ selectionIndex: index, ingredientId: idOf(item), amount: Object.prototype.hasOwnProperty.call(item, 'amount') ? item.amount : null, ...(Object.prototype.hasOwnProperty.call(item, 'grams') ? { grams: item.grams } : {}), unit: item.unit ?? (Object.prototype.hasOwnProperty.call(item, 'grams') ? 'g' : null) })),
        ingredientIds: uniqueIds, ingredientCount: uniqueIds.length,
        profiles: uniqueIds.map(id => chosenProfiles.get(id)), categories: categoryResults,
        duplicateIngredientIds: [...grouped].filter(([, items]) => items.length > 1).map(([id]) => id), selectionWarnings,
        amountPolicy: 'amounts_preserved_only_not_used_as_aroma_weights',
        rangeMeaning: 'bounds_on_count_of_selected_ingredient_ids_with_a_source_category_mark_not_intensity',
        jointlyAttainableBoundsAssessed: false,
        jointRangeNote: 'Per-category bounds need not occur together in one source variant combination.',
        isSensoryPrediction: false,
      };
    }

    const edgeMap = new Map();
    function addEdge(edge, fallback = false) {
      const id = edge.id || edge.sourceRef?.rowId;
      if (!id) return;
      if (edgeMap.has(id)) return;
      edgeMap.set(id, { edge, fallback });
    }
    for (const edge of data.edges || []) addEdge(edge);
    // Catalogue recommendation edges omit the teaching table. Its original
    // pairing rows remain accessible here as explicitly labelled excluded edges.
    for (const [ingredientId, records] of recordsByIngredient) for (const record of records) {
      if (record.role !== 'pairing' || !record.mainIngredientId) continue;
      const table = tables.get(record.tableId);
      const shared = Array.isArray(record.sharedWithMain) ? record.sharedWithMain : record.shared;
      if (!Array.isArray(shared)) continue;
      addEdge({
        id: record.id, tableId: record.tableId, mainId: record.mainIngredientId, pairedId: ingredientId,
        shared: shared.slice(), presence: record.presence.slice(), sourceRef: record.sourceRef,
        reviewStatus: record.reviewStatus, mainRecordId: table?.mainRecordId || null,
        isExample: record.isExample,
        sourceNamesEligible: record.identityEligible && table?.mainNameIdentityEligible !== false,
        recommendationEligible: !record.isExample && record.identityEligible && table?.recommendationEligible !== false,
        originalPairingRecord: record.original,
      }, true);
    }
    const edgesByPair = new Map();
    for (const { edge, fallback } of edgeMap.values()) {
      const key = pairKey(edge.mainId, edge.pairedId);
      if (!edgesByPair.has(key)) edgesByPair.set(key, []);
      edgesByPair.get(key).push({ edge, fallback });
    }

    function pairEvidence(a, b, options = {}) {
      const aid = idOf(a), bid = idOf(b);
      const includeExamples = options.includeExamples === true;
      const all = (edgesByPair.get(pairKey(aid, bid)) || []).map(({ edge, fallback }) => {
        const table = tables.get(edge.tableId || edge.sourceRef?.tableId);
        const record = allRecords.get(edge.id);
        const isExample = Boolean(edge.isExample || table?.isExample || record?.isExample);
        const exclusionReasons = [];
        if (isExample && !includeExamples) exclusionReasons.push('teaching_example_excluded_by_default');
        if (edge.sourceNamesEligible === false || record?.identityEligible === false || table?.mainNameIdentityEligible === false) exclusionReasons.push('source_identity_requires_review');
        if (ingredients.get(edge.mainId)?.nameNeedsReview || ingredients.get(edge.pairedId)?.nameNeedsReview) exclusionReasons.push('ingredient_identity_requires_review');
        if (!isExample && edge.recommendationEligible === false) exclusionReasons.push('source_edge_excluded_from_recommendation');
        const included = exclusionReasons.length === 0;
        return {
          ...edge,
          shared: Array.from({ length: CATEGORY_COUNT }, (_, index) => validCell(edge.shared?.[index])),
          original: edge,
          recoveredFromSourceRow: fallback,
          isExample, included,
          status: isExample ? 'example' : included ? 'included' : 'excluded',
          exclusionReasons: unique(exclusionReasons),
          queryDirection: edge.mainId === aid ? 'a_is_source_main' : 'b_is_source_main',
          sourceRelationScope: 'only_this_table_main_and_paired_row',
        };
      });
      const included = all.filter(edge => edge.included), excluded = all.filter(edge => !edge.included), examples = all.filter(edge => edge.isExample);
      return {
        a: aid, b: bid, all, included, excluded, examples,
        counts: { all: all.length, included: included.length, excluded: excluded.length, examples: examples.length },
        noDirectEvidence: all.length === 0,
        relationScope: 'direct_table_rows_only', isTransitive: false,
        interpretation: 'All direct source rows are returned without selecting the largest shared count; absence of a row is not incompatibility.',
      };
    }

    const evidenceRecords = Array.isArray(evidence) ? evidence : Array.isArray(evidence?.records) ? evidence.records : [];
    const evidenceIndex = new Map();
    for (const record of evidenceRecords) {
      const links = Array.isArray(record.links) ? record.links : [];
      for (const ingredientId of unique(links.map(link => link.ingredientId).filter(Boolean))) {
        if (!evidenceIndex.has(ingredientId)) evidenceIndex.set(ingredientId, []);
        const matchingLinks = links.filter(link => link.ingredientId === ingredientId);
        evidenceIndex.get(ingredientId).push({ ...record, matchingLinks, matchKinds: unique(matchingLinks.map(link => link.kind)) });
      }
    }
    function evidenceFor(id) {
      const ingredientId = idOf(id), linked = evidenceIndex.get(ingredientId) || [];
      const uniqueRecords = entries => [...new Map(entries.map((entry, index) => [entry.id || `position-${index}`, entry])).values()];
      const allLinked = uniqueRecords(linked);
      const exact = allLinked.filter(record => record.matchKinds.includes('exact_name'));
      const aliases = allLinked.filter(record => record.matchKinds.includes('alias_name'));
      const related = allLinked.filter(record => record.matchKinds.includes('related_context'));
      const direct = uniqueRecords([...exact, ...aliases]);
      const other = allLinked.filter(record => !record.matchKinds.some(kind => ['exact_name', 'alias_name', 'related_context'].includes(kind)));
      return {
        ingredientId, exact, aliases, related, direct, allLinked, other,
        counts: { exact: exact.length, aliases: aliases.length, related: related.length, direct: direct.length, allLinked: allLinked.length, other: other.length },
        sourceAvailable: evidenceRecords.length > 0,
        relatedContextPolicy: 'Related context remains context, never promoted to a measured property of this ingredient.',
      };
    }

    return {
      sourceProfile, compare, targetMatch, mixture, pairEvidence, evidenceFor,
      categories: categories.slice(), categoryDisplayNames: labels.slice(),
      summary: {
        ingredients: ingredients.size,
        sourceRecords: [...recordsByIngredient.values()].reduce((sum, records) => sum + records.length, 0),
        sourceEdges: edgeMap.size, evidenceRecords: evidenceRecords.length,
        canonicalVectorsUsed: false,
      },
    };
  }

  return Object.freeze({ create, version: '2.0.0-full-source' });
});
