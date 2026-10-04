-- sha256 是原输入文件字节的摘要；JSON 对象可在库内完整还原。
SELECT id,relative_path,sha256,length(content_json) AS utf8_text_character_count
FROM source_snapshots ORDER BY id;
