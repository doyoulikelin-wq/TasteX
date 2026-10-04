-- 参数 {"ingredient_name":"大蒜"}。
-- 这是来源名称索引；不是 stable ID 关联，也不自动包含所有加工状态。
SELECT DISTINCT id,title,record_kind,conditions,summary,limitations,
       source_kind,source_id,source_json
FROM v_processing_by_ingredient
WHERE name_key=:ingredient_name OR ingredient_label=:ingredient_name
ORDER BY id;
