-- “挥发物减少”和“未发现显著变化”分行保留；不把无显著变化当成 0。
SELECT e.group_key,e.domain,e.label,e.direction,e.detail,p.id,p.title,
       p.conditions,p.limitations,p.source_kind,p.source_id,p.source_json
FROM processing_effects AS e JOIN processing_records AS p ON p.id=e.processing_id
WHERE e.domain='chemical' AND e.label='挥发物'
  AND e.direction IN ('decrease','no_significant_change')
ORDER BY e.direction,p.id,e.ordinal;
