-- 参数 {"ingredient_id":"ing-27422575ad23","include_examples":0}。
-- 每行保留一条来源记录。presence 中 0=未标记，NULL=未知；不做多数投票。
SELECT r.id AS record_id, r.ingredient_id, r.table_id, r.role,
       r.pdf_page, r.book_page, r.is_example, r.identity_eligible,
       r.review_status, r.name_review_status,
       (SELECT json_group_array(presence) FROM
          (SELECT presence FROM dot_values WHERE record_id=r.id ORDER BY category_index))
         AS presence_14_json,
       (SELECT json_group_array(shared_with_main) FROM
          (SELECT shared_with_main FROM dot_values WHERE record_id=r.id ORDER BY category_index))
         AS shared_with_main_14_json,
       r.raw_json, r.raw_source_json
FROM dot_records AS r
WHERE r.ingredient_id=:ingredient_id AND (:include_examples=1 OR r.is_example=0)
ORDER BY r.pdf_page,r.table_id,r.id;
