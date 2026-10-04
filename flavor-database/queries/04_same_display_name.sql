-- 同一个显示名可能对应多个稳定身份；只用于发现，不合并。
SELECT display_name,COUNT(*) AS stable_identity_count,
       json_group_array(id) AS ingredient_ids_json,
       json_group_array(original_name) AS original_names_json
FROM ingredients GROUP BY display_name HAVING COUNT(*)>1
ORDER BY stable_identity_count DESC,display_name;
