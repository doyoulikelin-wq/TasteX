-- 三种导航口径；每个组内按加工记录 ID 去重。
-- 三种记录数以及各组内计数不可相加当成总证据数。
SELECT 'method' AS index_type,method_key AS group_key,label,
       COUNT(DISTINCT processing_id) AS record_count
FROM processing_methods GROUP BY method_key,label
UNION ALL
SELECT 'effect',group_key,label,COUNT(DISTINCT processing_id)
FROM processing_effects GROUP BY group_key,label
UNION ALL
SELECT 'ingredient',name_key,label,COUNT(DISTINCT processing_id)
FROM processing_ingredient_names GROUP BY name_key,label
ORDER BY index_type,group_key;
