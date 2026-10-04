-- 参数 {"a":"ing-c76f6a79f6db","b":"ing-6354a61df090","include_excluded":0}。
-- 查双方向，但保留原表主食材方向。每条配对行独立，不选“最强”一条。
SELECT p.id,p.table_id,p.main_record_id,p.paired_record_id,
       p.main_ingredient_id,p.paired_ingredient_id,p.is_example,
       p.recommendation_eligible,p.provenance_kind,
       r.pdf_page,r.book_page,
       (SELECT json_group_array(shared_with_main) FROM
          (SELECT shared_with_main FROM dot_values
           WHERE record_id=p.paired_record_id ORDER BY category_index)) AS shared_14_json,
       p.raw_json
FROM pairings AS p JOIN dot_records AS r ON r.id=p.paired_record_id
WHERE ((p.main_ingredient_id=:a AND p.paired_ingredient_id=:b)
    OR (p.main_ingredient_id=:b AND p.paired_ingredient_id=:a))
  AND (:include_excluded=1 OR (p.recommendation_eligible=1 AND p.is_example=0))
ORDER BY r.pdf_page,p.table_id,p.id;
