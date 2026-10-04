-- 参数 {"ingredient_id":"ing-2053d8521c93"}。
-- direct_name 仍需核对原料状态；related_context 必须与直接名称证据分开解释。
SELECT l.link_kind,
       CASE WHEN l.link_kind IN ('exact_name','alias_name') THEN 'direct_name'
            ELSE 'related_context' END AS link_scope,
       l.ingredient_id,p.id,p.title,p.record_kind,p.conditions,p.summary,p.limitations,
       p.source_kind,p.source_id,p.source_json,l.reason,l.raw_json AS link_json
FROM processing_links AS l JOIN processing_records AS p ON p.id=l.processing_id
WHERE l.ingredient_id=:ingredient_id
ORDER BY link_scope,l.link_kind,p.id,l.ordinal;
