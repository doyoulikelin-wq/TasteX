-- 参数 {"query":"大蒜"}。名称检索先取得 stable ID；不要合并同名 ID。
SELECT i.id, i.original_name, i.display_name, i.recommendation_eligible,
       i.name_needs_review, i.example_only
FROM ingredients AS i
WHERE instr(i.search_text, :query) > 0
ORDER BY i.display_name, i.id;
