-- Flavor evidence database v1.0. All source JSON is retained unchanged semantically.
PRAGMA foreign_keys = ON;
PRAGMA user_version = 1;

CREATE TABLE ingredients (
 id TEXT PRIMARY KEY, original_name TEXT NOT NULL, display_name TEXT NOT NULL,
 visual_family TEXT, recommendation_eligible INTEGER NOT NULL CHECK(recommendation_eligible IN(0,1)),
 name_needs_review INTEGER NOT NULL CHECK(name_needs_review IN(0,1)),
 example_only INTEGER NOT NULL CHECK(example_only IN(0,1)), search_text TEXT NOT NULL, raw_json TEXT NOT NULL
);
CREATE TABLE ingredient_aliases (
 ingredient_id TEXT NOT NULL REFERENCES ingredients(id), alias TEXT NOT NULL, alias_key TEXT NOT NULL,
 PRIMARY KEY(ingredient_id,alias)
);
CREATE INDEX idx_alias_key ON ingredient_aliases(alias_key);
CREATE INDEX idx_ingredients_display ON ingredients(display_name);
CREATE TABLE aroma_categories(category_index INTEGER PRIMARY KEY CHECK(category_index BETWEEN 0 AND 13),source_name TEXT NOT NULL,display_name TEXT NOT NULL);
CREATE TABLE descriptors(id TEXT PRIMARY KEY,category_index INTEGER REFERENCES aroma_categories(category_index),source_label TEXT NOT NULL,display_label TEXT NOT NULL,raw_json TEXT NOT NULL);
CREATE TABLE source_tables(
 id TEXT PRIMARY KEY,main_ingredient_id TEXT NOT NULL REFERENCES ingredients(id),
 main_record_id TEXT REFERENCES dot_records(id) DEFERRABLE INITIALLY DEFERRED,
 pdf_page INTEGER,book_page INTEGER,is_example INTEGER NOT NULL CHECK(is_example IN(0,1)),review_status TEXT,
 raw_json TEXT NOT NULL,raw_source_json TEXT NOT NULL
);
CREATE TABLE dot_records(
 id TEXT PRIMARY KEY,ingredient_id TEXT NOT NULL REFERENCES ingredients(id),table_id TEXT NOT NULL REFERENCES source_tables(id),
 role TEXT NOT NULL,main_ingredient_id TEXT REFERENCES ingredients(id),pdf_page INTEGER,book_page INTEGER,
 is_example INTEGER NOT NULL CHECK(is_example IN(0,1)),identity_eligible INTEGER NOT NULL CHECK(identity_eligible IN(0,1)),
 review_status TEXT,name_review_status TEXT,raw_json TEXT NOT NULL,raw_source_json TEXT NOT NULL
);
CREATE INDEX idx_records_ingredient ON dot_records(ingredient_id,is_example);
CREATE INDEX idx_records_table ON dot_records(table_id);
CREATE TABLE dot_values(
 record_id TEXT NOT NULL REFERENCES dot_records(id),category_index INTEGER NOT NULL REFERENCES aroma_categories(category_index),
 presence INTEGER CHECK(presence IN(0,1)),shared_with_main INTEGER CHECK(shared_with_main IN(0,1)),
 PRIMARY KEY(record_id,category_index)
);
CREATE INDEX idx_dot_values_category ON dot_values(category_index,presence);
CREATE TABLE pairings(
 id TEXT PRIMARY KEY,table_id TEXT NOT NULL REFERENCES source_tables(id),main_record_id TEXT REFERENCES dot_records(id),
 paired_record_id TEXT NOT NULL REFERENCES dot_records(id),main_ingredient_id TEXT NOT NULL REFERENCES ingredients(id),
 paired_ingredient_id TEXT NOT NULL REFERENCES ingredients(id),is_example INTEGER NOT NULL CHECK(is_example IN(0,1)),
 recommendation_eligible INTEGER NOT NULL CHECK(recommendation_eligible IN(0,1)),provenance_kind TEXT NOT NULL,raw_json TEXT NOT NULL
);
CREATE INDEX idx_pairings_main ON pairings(main_ingredient_id,recommendation_eligible);
CREATE INDEX idx_pairings_paired ON pairings(paired_ingredient_id,recommendation_eligible);
CREATE TABLE attribute_evidence(
 id TEXT PRIMARY KEY,ingredient_name TEXT,display_ingredient TEXT,state TEXT,attribute_type TEXT,evidence_mode TEXT,
 pdf_page INTEGER,book_page INTEGER,note TEXT,search_text TEXT NOT NULL,raw_json TEXT NOT NULL,original_json TEXT NOT NULL
);
CREATE TABLE evidence_links(
 evidence_id TEXT NOT NULL REFERENCES attribute_evidence(id),ordinal INTEGER NOT NULL,ingredient_id TEXT NOT NULL REFERENCES ingredients(id),
 link_kind TEXT NOT NULL,reason TEXT,raw_json TEXT NOT NULL,PRIMARY KEY(evidence_id,ordinal)
);
CREATE INDEX idx_evidence_links_ingredient ON evidence_links(ingredient_id,link_kind);
CREATE TABLE evidence_domains(evidence_id TEXT NOT NULL REFERENCES attribute_evidence(id),domain TEXT NOT NULL,PRIMARY KEY(evidence_id,domain));
CREATE TABLE descriptor_mentions(
 evidence_id TEXT NOT NULL REFERENCES attribute_evidence(id),ordinal INTEGER NOT NULL,descriptor_id TEXT NOT NULL REFERENCES descriptors(id),
 interpretation TEXT NOT NULL,raw_json TEXT NOT NULL,PRIMARY KEY(evidence_id,ordinal)
);
CREATE INDEX idx_mentions_descriptor ON descriptor_mentions(descriptor_id);
CREATE TABLE reported_numbers(
 id TEXT PRIMARY KEY,evidence_id TEXT REFERENCES attribute_evidence(id),metric TEXT,unit TEXT,value_json TEXT,
 minimum_json TEXT,maximum_json TEXT,operator TEXT,denominator TEXT,pdf_page INTEGER,book_page INTEGER,raw_json TEXT NOT NULL
);
CREATE TABLE sources(
 id TEXT PRIMARY KEY,kind TEXT NOT NULL,title TEXT,journal TEXT,year INTEGER,doi TEXT,url TEXT,relative_path TEXT,sha256 TEXT,raw_json TEXT NOT NULL
);
CREATE TABLE processing_records(
 id TEXT PRIMARY KEY,title TEXT NOT NULL,record_kind TEXT NOT NULL,before_state TEXT,after_state TEXT,conditions TEXT,mechanism TEXT,summary TEXT,limitations TEXT,
 evidence_level TEXT,source_kind TEXT NOT NULL,source_id TEXT NOT NULL REFERENCES sources(id),search_text TEXT NOT NULL,
 raw_json TEXT NOT NULL,source_json TEXT NOT NULL,original_json TEXT NOT NULL
);
CREATE INDEX idx_processing_source_kind ON processing_records(source_kind,record_kind);
CREATE TABLE processing_methods(
 processing_id TEXT NOT NULL REFERENCES processing_records(id),ordinal INTEGER NOT NULL,method_key TEXT NOT NULL,label TEXT NOT NULL,original_label TEXT,
 PRIMARY KEY(processing_id,ordinal)
);
CREATE INDEX idx_processing_methods_key ON processing_methods(method_key);
CREATE TABLE processing_effects(
 processing_id TEXT NOT NULL REFERENCES processing_records(id),ordinal INTEGER NOT NULL,domain TEXT NOT NULL,label TEXT NOT NULL,original_label TEXT,
 direction TEXT NOT NULL,group_key TEXT NOT NULL,detail TEXT,raw_json TEXT NOT NULL,PRIMARY KEY(processing_id,ordinal)
);
CREATE INDEX idx_processing_effects_group ON processing_effects(group_key);
CREATE INDEX idx_processing_effects_dimension ON processing_effects(domain,direction);
CREATE TABLE processing_ingredient_names(
 processing_id TEXT NOT NULL REFERENCES processing_records(id),ordinal INTEGER NOT NULL,name_key TEXT NOT NULL,label TEXT NOT NULL,original_label TEXT,
 PRIMARY KEY(processing_id,ordinal)
);
CREATE INDEX idx_processing_names_key ON processing_ingredient_names(name_key);
CREATE TABLE processing_links(
 processing_id TEXT NOT NULL REFERENCES processing_records(id),ordinal INTEGER NOT NULL,ingredient_id TEXT NOT NULL REFERENCES ingredients(id),
 link_kind TEXT NOT NULL,reason TEXT,raw_json TEXT NOT NULL,PRIMARY KEY(processing_id,ordinal)
);
CREATE INDEX idx_processing_links_ingredient ON processing_links(ingredient_id,link_kind);
CREATE TABLE processing_evidence(processing_id TEXT NOT NULL REFERENCES processing_records(id),evidence_id TEXT NOT NULL REFERENCES attribute_evidence(id),PRIMARY KEY(processing_id,evidence_id));
CREATE TABLE processing_numbers(
 processing_id TEXT NOT NULL REFERENCES processing_records(id),ordinal INTEGER NOT NULL,metric TEXT,value_json TEXT,unit TEXT,context TEXT,
 minimum_json TEXT,maximum_json TEXT,operator TEXT,denominator TEXT,raw_json TEXT NOT NULL,PRIMARY KEY(processing_id,ordinal)
);
CREATE TABLE processing_audit(
 evidence_id TEXT PRIMARY KEY REFERENCES attribute_evidence(id),decision TEXT NOT NULL,reason TEXT,record_ids_json TEXT NOT NULL,raw_json TEXT NOT NULL
);
CREATE TABLE source_snapshots(id TEXT PRIMARY KEY,relative_path TEXT NOT NULL,sha256 TEXT NOT NULL,content_json TEXT NOT NULL);
CREATE TABLE book_pages(pdf_page INTEGER PRIMARY KEY,text TEXT NOT NULL,width REAL,height REAL,raw_json TEXT NOT NULL);
CREATE TABLE metadata(key TEXT PRIMARY KEY,value_json TEXT NOT NULL);
CREATE TABLE assets(
 id TEXT PRIMARY KEY,ingredient_id TEXT REFERENCES ingredients(id),relative_path TEXT NOT NULL,status TEXT NOT NULL,
 sha256 TEXT NOT NULL,mime_type TEXT NOT NULL,byte_size INTEGER NOT NULL,width INTEGER,height INTEGER,content BLOB NOT NULL,raw_json TEXT NOT NULL
);
CREATE INDEX idx_assets_ingredient ON assets(ingredient_id);
CREATE TABLE search_documents(kind TEXT NOT NULL,id TEXT NOT NULL,title TEXT NOT NULL,text TEXT NOT NULL,PRIMARY KEY(kind,id));

-- 0 means unmarked in a source row; NULL is unknown, never chemical absence.
CREATE VIEW v_ingredient_aroma_profile AS
WITH counts AS (
 SELECT i.id AS ingredient_id,c.category_index,c.display_name AS category_name,
 SUM(CASE WHEN v.presence=1 THEN 1 ELSE 0 END) AS marked_count,
 SUM(CASE WHEN v.presence=0 THEN 1 ELSE 0 END) AS unmarked_count,
 SUM(CASE WHEN v.record_id IS NOT NULL AND v.presence IS NULL THEN 1 ELSE 0 END) AS unknown_count,COUNT(v.record_id) AS record_count
 FROM ingredients i CROSS JOIN aroma_categories c
 LEFT JOIN dot_records r ON r.ingredient_id=i.id AND r.is_example=0
 LEFT JOIN dot_values v ON v.record_id=r.id AND v.category_index=c.category_index
 GROUP BY i.id,c.category_index
)
SELECT *,CASE WHEN marked_count>0 AND unmarked_count>0 THEN 'conflict'
 WHEN unknown_count>0 OR record_count=0 THEN 'unknown' WHEN marked_count>0 THEN 'marked' ELSE 'unmarked' END AS status,
 (unknown_count>0) AS has_unknown FROM counts;
CREATE VIEW v_processing_by_method AS SELECT m.method_key,m.label AS method_label,m.original_label AS method_original_label,m.ordinal AS method_ordinal,p.* FROM processing_methods m JOIN processing_records p ON p.id=m.processing_id;
CREATE VIEW v_processing_by_effect AS SELECT e.group_key,e.domain,e.direction,e.label AS effect_label,e.original_label AS effect_original_label,e.detail AS effect_detail,e.ordinal AS effect_ordinal,p.* FROM processing_effects e JOIN processing_records p ON p.id=e.processing_id;
CREATE VIEW v_processing_by_ingredient AS SELECT n.name_key,n.label AS ingredient_label,n.original_label AS ingredient_original_label,n.ordinal AS ingredient_ordinal,p.* FROM processing_ingredient_names n JOIN processing_records p ON p.id=n.processing_id;
CREATE VIEW v_recommendable_pairings AS SELECT * FROM pairings WHERE recommendation_eligible=1 AND is_example=0;
