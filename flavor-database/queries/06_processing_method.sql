-- 参数 {"method":"温热熟成"}；可替换为“冷藏”。返回完整条件与来源。
-- 方法是多对多关系，用 EXISTS 避免同一加工记录被重复返回。
SELECT p.id,p.title,p.record_kind,p.before_state,p.after_state,p.conditions,
       p.summary,p.limitations,p.evidence_level,p.source_kind,p.source_id,
       p.source_json,p.original_json,p.raw_json
FROM processing_records AS p
WHERE EXISTS(SELECT 1 FROM processing_methods AS m
             WHERE m.processing_id=p.id AND (m.method_key=:method OR m.label=:method))
ORDER BY p.id;
