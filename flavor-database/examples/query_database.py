#!/usr/bin/env python3
"""Python 标准库只读查询示例；可从任意工作目录运行。"""
from pathlib import Path
import json
import sqlite3

PACKAGE_DIR = Path(__file__).resolve().parents[1]
DATABASE = PACKAGE_DIR / "flavor.sqlite"


def rows(connection, statement, parameters=()):
    return [dict(row) for row in connection.execute(statement, parameters)]


def main():
    # mode=ro 禁止创建/修改数据库；query_only 增加连接级只读约束。
    connection = sqlite3.connect(DATABASE.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    try:
        candidates = rows(connection, """
            SELECT id,original_name,display_name,recommendation_eligible
            FROM ingredients WHERE instr(search_text, ?) > 0
            ORDER BY display_name,id
        """, ("大蒜",))
        # 依据检索结果选择精确显示名；若出现多 ID，全部保留，不随意取第一条。
        exact = [candidate for candidate in candidates if candidate["display_name"] == "大蒜"]
        profiles = []
        for ingredient in exact:
            identity = ingredient["id"]
            profiles.append({
                "ingredient": ingredient,
                "profile": rows(connection, """
                    SELECT * FROM v_ingredient_aroma_profile
                    WHERE ingredient_id=? ORDER BY category_index
                """, (identity,)),
                "direct_name_processing": rows(connection, """
                    SELECT p.id,p.title,p.conditions,p.summary,p.limitations,
                           p.source_id,p.source_json,l.link_kind,l.raw_json AS link_json
                    FROM processing_links l JOIN processing_records p ON p.id=l.processing_id
                    WHERE l.ingredient_id=? AND l.link_kind IN ('exact_name','alias_name')
                    ORDER BY p.id,l.ordinal
                """, (identity,)),
                "related_processing_contexts": rows(connection, """
                    SELECT p.id,p.title,p.conditions,p.summary,p.limitations,
                           p.source_id,p.source_json,l.link_kind,l.raw_json AS link_json
                    FROM processing_links l JOIN processing_records p ON p.id=l.processing_id
                    WHERE l.ingredient_id=? AND l.link_kind='related_context'
                    ORDER BY p.id,l.ordinal
                """, (identity,)),
            })
        print(json.dumps({
            "query": "大蒜", "candidates": candidates, "profiles": profiles,
            "limits": ["标记计数不是强度", "直接名称匹配仍需核对状态和条件", "相关上下文不是同食材实测"],
        }, ensure_ascii=False, indent=2))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
