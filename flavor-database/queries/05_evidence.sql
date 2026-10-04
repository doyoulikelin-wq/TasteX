-- 参数 {"evidence_id":"E0054"}。
SELECT e.id,e.ingredient_name,e.display_ingredient,e.state,e.attribute_type,
       e.pdf_page,e.book_page,e.note,e.original_json,e.raw_json
FROM attribute_evidence AS e WHERE e.id=:evidence_id;
