/* Processing indexes are views of complete source records, never flavor simulators. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.FlavorProcessingEngine = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const unique = values => [...new Set(values)];
  const text = value => String(value == null ? '' : value).normalize('NFKC').toLocaleLowerCase();
  const compare = (a, b) => b.records.length - a.records.length || a.label.localeCompare(b.label, 'zh-Hans-CN') || a.key.localeCompare(b.key);
  function effectEntries(record) {
    return (record.normalizedEffects || record.effects || []).map(effect => ({
      ...effect,
      key: effect.groupKey || `${effect.domain}|${effect.normalizedLabel || effect.label}|${effect.direction}`,
      label: effect.normalizedLabel || effect.label,
    }));
  }
  function methodEntries(record) {
    return record.methodIndexEntries || (record.methods || []).map(label => ({ key: label, label, originalLabel: label }));
  }
  function ingredientEntries(record) {
    return record.ingredientIndexEntries || (record.ingredientNames || []).map(label => ({ key: label, label, originalLabel: label }));
  }
  function create(data) {
    if (!data || !Array.isArray(data.records)) throw new TypeError('Processing data must contain a records array');
    const all = data.records;
    const ids = new Set();
    for (const record of all) {
      if (!record.id || ids.has(record.id)) throw new Error(`Missing or duplicate processing record ID: ${record.id}`);
      ids.add(record.id);
    }
    function filter({ query = '', source = '', kind = '', domain = '' } = {}) {
      const words = text(query).split(/\s+/).filter(Boolean);
      return all.filter(record => {
        if (source && source !== 'all' && record.source?.kind !== source) return false;
        if (kind && kind !== 'all' && record.recordKind !== kind) return false;
        if (domain && domain !== 'all' && !effectEntries(record).some(effect => effect.domain === domain)) return false;
        const haystack = text(record.searchText || JSON.stringify(record));
        return words.every(word => haystack.includes(word));
      });
    }
    function groups(index, records = all) {
      if (!['method', 'effect', 'ingredient'].includes(index)) throw new RangeError(`Unknown processing index: ${index}`);
      const grouped = new Map();
      for (const record of records) {
        const entries = index === 'method' ? methodEntries(record) : index === 'ingredient' ? ingredientEntries(record) : effectEntries(record);
        for (const entry of entries) {
          const key = entry.key;
          if (!grouped.has(key)) grouped.set(key, {
            key, label: entry.label,
            ...(index === 'effect' ? { domain: entry.domain, direction: entry.direction } : {}),
            records: [], recordIds: [], ingredientNames: [], methods: [], effects: [], originalLabels: [],
          });
          const group = grouped.get(key);
          if (!group.recordIds.includes(record.id)) {
            group.records.push(record); group.recordIds.push(record.id);
            group.ingredientNames.push(...(record.ingredientNames || []));
            group.methods.push(...(record.methods || []));
            group.effects.push(...effectEntries(record));
          }
          group.originalLabels.push(entry.originalLabel || entry.label);
        }
      }
      return [...grouped.values()].map(group => ({
        ...group,
        ingredientNames: unique(group.ingredientNames), methods: unique(group.methods), originalLabels: unique(group.originalLabels),
        effects: [...new Map(group.effects.map(effect => [effect.key, effect])).values()],
      })).sort(compare);
    }
    function selection({ index = 'method', groupKey = '', ...criteria } = {}) {
      const population = filter(criteria);
      const indexGroups = groups(index, population);
      const selectedGroup = groupKey ? indexGroups.find(group => group.key === groupKey) || null : null;
      // An obsolete group key yields an empty selection, never an unrelated full export.
      const records = groupKey ? (selectedGroup?.records || []) : population;
      return { records, groups: indexGroups, selectedGroup, population, populationCount: population.length };
    }
    function forIngredient(catalogId) {
      return all.flatMap(record => {
        const links = (record.ingredientLinks || []).filter(link => link.ingredientId === catalogId);
        return links.length ? [{ ...record, matchingLinks: links, linkKinds: unique(links.map(link => link.kind)) }] : [];
      });
    }
    return { filter, groups, selection, forIngredient };
  }
  return { create };
});
