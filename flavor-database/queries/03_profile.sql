-- 参数 {"ingredient_id":"ing-18f21fe85570"}。视图默认排除教学行。
-- conflict 与 has_unknown 可同时为真；计数不是强度。
SELECT ingredient_id,category_index,category_name,marked_count,unmarked_count,
       unknown_count,record_count,status,has_unknown
FROM v_ingredient_aroma_profile
WHERE ingredient_id=:ingredient_id ORDER BY category_index;
