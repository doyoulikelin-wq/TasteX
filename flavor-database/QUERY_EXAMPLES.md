# Agent 查询示例

以下命令在本目录运行；数据库默认由接口自身位置定位。所有示例使用本次库内真实 ID，正式任务仍应先搜索确认。先读 [`AGENTS.md`](AGENTS.md)，字段见 [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md)。

## 1. 先确认范围，再取稳定 ID

```sh
python3 flavor_db.py stats
python3 flavor_db.py search '大蒜' --kind ingredient --limit 50 --offset 0
python3 flavor_db.py ingredient ing-2053d8521c93
```

`search` 支持 kind=all、ingredient、evidence、processing、page。按字面子串检索，`%` 和 `_` 不作为用户通配符；检索命中不是属性存在证明。原文字、别名和简繁体支持依库内已有检索文本，未声明任意同义词理解。

`ingredient` 返回完整原目录对象、全部正式来源轮廓、文字/加工关联及资产元信息。其中历史 `canonical` 为保留资料，不能覆盖 `profile` 的全部来源结果。

同一显示名可能对应不同 ID，检查时只展示，不合并：

```sh
python3 flavor_db.py sql --file queries/04_same_display_name.sql --limit 1000
```

```sql
SELECT display_name,COUNT(*) AS stable_identity_count,json_group_array(id) AS ids
FROM ingredients GROUP BY display_name HAVING COUNT(*)>1;
```

## 2. 全部来源轮廓、变体、未知与冲突

```sh
python3 flavor_db.py profile ing-18f21fe85570
python3 flavor_db.py profile ing-18f21fe85570 --include-examples
python3 flavor_db.py sql --file queries/02_all_source_variants.sql --params '{"ingredient_id":"ing-27422575ad23","include_examples":0}' --limit 1000
```

示例分别为黑橄榄、黑蒜泥。`profile` 返回 14 类及每类 marked/unmarked/unknown 计数和对应来源行 ID，同时返回所有不同向量 `variants`；相同向量也保留全部来源 ID、页码和行数。默认排除教学行，使用 `--include-examples` 才纳入。

`status=conflict` 时仍要读取 `has_unknown`。只出现于教学资料的身份会有 14 个 unknown 状态、record_count=0、unknown_count=0：无正式来源与“有来源但未知格”不同。

```sql
SELECT ingredient_id,category_index,category_name,status,has_unknown,
       marked_count,unmarked_count,unknown_count,record_count
FROM v_ingredient_aroma_profile
WHERE ingredient_id='ing-18f21fe85570'
ORDER BY category_index;
```

不得把 marked_count/record_count 当成浓度、感官强度或出现概率；这是不同原表的标记统计。

## 3. 原始证据与书页上下文

```sh
python3 flavor_db.py evidence E0054
python3 flavor_db.py processing-record PB-E0054
python3 flavor_db.py page 115
python3 flavor_db.py search '蒜素' --kind page
```

E0054 与 PB-E0054 为黑蒜相关资料。原来源区分温热熟成与微生物发酵；保存约 60°C、4–6 周等书中条件，不延伸成任意时间/温度的风味函数。`page 115` 是 PDF 第 115 页，不能自动称为书中第 115 页。

页查询返回已有抽取文本与页原对象；它不重做 OCR、不查看原图，也不能代替圆点位置和图表视觉核验。原属性的 `original`、加工记录的 `original` / `source` / `conditions` / `limitations` 均应随结论引用。

## 4. 三个加工索引与交叉筛选

```sh
python3 flavor_db.py indexes --by method --limit 1000
python3 flavor_db.py indexes --by effect --limit 1000
python3 flavor_db.py indexes --by ingredient --limit 1000
```

每组返回 key、label、original_labels、record_ids、record_count 和 association_count。整个返回另含 population_record_count / population_record_ids / group_membership_count：分别是筛选后的唯一记录、记录清单与跨组成员计数，不能混成一个分母。

先按方式找到记录，再观察同一批记录涉及哪些效果/食材：

```sh
python3 flavor_db.py processing --method '温热熟成' --limit 1000
python3 flavor_db.py processing --method '冷藏' --limit 1000
python3 flavor_db.py indexes --by effect --method '冷藏' --limit 1000
python3 flavor_db.py indexes --by ingredient --method '冷藏' --limit 1000
```

按来源名称索引选择：

```sh
python3 flavor_db.py processing --ingredient-name '大蒜' --limit 1000
python3 flavor_db.py sql --file queries/11_processing_ingredient_index.sql --params '{"ingredient_name":"大蒜"}' --limit 1000
```

`--ingredient-name` 精确匹配来源名称组，和 `--ingredient-id` 的稳定身份关联不是同一口径。154 是名称组数量，不能据此声称只覆盖或合并为 154 个食材身份。

SQL 统计每组唯一加工记录：

```sql
SELECT method_key,label,COUNT(DISTINCT processing_id) AS record_count
FROM processing_methods GROUP BY method_key,label;
SELECT group_key,domain,direction,label,COUNT(DISTINCT processing_id) AS record_count
FROM processing_effects GROUP BY group_key,domain,direction,label;
SELECT name_key,label,COUNT(DISTINCT processing_id) AS record_count
FROM processing_ingredient_names GROUP BY name_key,label;
```

CLI `sql` 每次只接受一条语句；可用文件中的 UNION ALL 一次返回三索引：

```sh
python3 flavor_db.py sql --file queries/10_three_indexes.sql --limit 1000
```

索引筛选先选加工记录总体，然后展示该总体的全部索引条目。例如筛“挥发物下降”的记录后，效果索引仍会列出这些记录包含的其他效果；不能把同记录其他效果也解释为下降。

## 5. 减少与未显著变化分开

```sh
python3 flavor_db.py processing --effect '挥发物' --domain chemical --direction decrease --source research --limit 1000
python3 flavor_db.py processing --effect '挥发物' --domain chemical --direction no_significant_change --source research --limit 1000
python3 flavor_db.py sql --file queries/07_volatile_effect_directions.sql --limit 1000
```

`--effect` 精确匹配规范标签或完整 group_key；`--domain`、`--direction` 必须在同一个效果条目联合满足。味觉、香气、相对峰面积、挥发物释放量和感官喜好不可互换；“未显著变化”不是“完全没变”或数值零。

```sql
SELECT p.id,e.group_key,e.domain,e.direction,e.detail,
       p.conditions,p.limitations,p.source_json
FROM processing_effects e JOIN processing_records p ON p.id=e.processing_id
WHERE e.domain='chemical' AND e.label='挥发物'
  AND e.direction IN ('decrease','no_significant_change');
```

## 6. 直接名称关联与相关上下文单列

**默认 `--ingredient-id` 包括所有关联种类**。用原料身份回答加工问题时，建议先显式查 exact_name + alias_name，再单独读取相关语境：

```sh
python3 flavor_db.py processing --ingredient-id ing-2053d8521c93 --link-kind exact_name --link-kind alias_name --limit 1000
python3 flavor_db.py processing --ingredient-id ing-2053d8521c93 --link-kind related_context --limit 1000
```

`--link-kind` 可重复，多个值按 OR；其他不同筛选维度按 AND。`matched_ingredient_links` 只列此次身份筛选实际命中的链接，原记录仍保留所有 `ingredientLinks`。读取两处时不要把其他关联误当成本次命中依据。

直接名称关联仍须检查 contextScope、源状态与数值迁移限制。related_context 仅供进一步查阅，不能直接当作大蒜在同条件下的实测。

```sh
python3 flavor_db.py sql --file queries/08_ingredient_processing_links.sql --params '{"ingredient_id":"ing-2053d8521c93"}' --limit 1000
```

## 7. 查原始配对而非推导传递关系

```sh
python3 flavor_db.py pairs ing-c76f6a79f6db --with-id ing-6354a61df090 --limit 1000
python3 flavor_db.py pairs ing-c76f6a79f6db --with-id ing-6354a61df090 --include-excluded --limit 1000
```

示例为草莓与奶油乳酪。接口查两个方向，输出仍保留 main_ingredient_id、paired_ingredient_id、table_id、行 ID 与来源方向。默认排除教学或不符合候选资格的记录，`--include-excluded` 才返回全部直接来源。没有直接来源记录不等于不适配；更不能以 A–B 与 B–C 推出 A–C。

```sh
python3 flavor_db.py sql --file queries/09_pairings.sql --params '{"a":"ing-c76f6a79f6db","b":"ing-6354a61df090","include_excluded":0}' --limit 1000
```

## 8. 资产、完整快照与输出文件

先读资产元信息，再明确导出：

```sh
python3 flavor_db.py asset ing-27422575ad23
mkdir -p exported
python3 flavor_db.py asset ing-27422575ad23 --out exported/black-garlic.svg
python3 flavor_db.py asset hero-strawberry --out exported/strawberry-editorial.png
```

仅 `--out` 会写图片。已有目标默认拒绝覆盖；确需覆盖时显式加 `--force`。资产来源和 SHA-256 一并返回，SVG 是示意插画，AI 主视觉不是实物照片。

```sh
python3 flavor_db.py source-snapshot
python3 flavor_db.py source-snapshot processing > processing-source.json
python3 flavor_db.py evidence E0054 > E0054-evidence.json
python3 flavor_db.py processing --method '冷藏' --limit 1000 > cold-storage-records.json
```

`source-snapshot ID` 返回带 id、relative_path、sha256、content 的 JSON 包装；`content` 是解析后的完整对象，输出文件本身不是原文件字节。要逐字节校验/还原，应直接读取 source_snapshots.content_json 并按 UTF-8 编码，不能把上述 JSON 包装文件与源摘要比较：

```python
from pathlib import Path
import hashlib
import sqlite3

path = Path('flavor.sqlite').resolve()
with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as con:
    text, expected = con.execute(
        'SELECT content_json,sha256 FROM source_snapshots WHERE id=?',
        ('processing',),
    ).fetchone()
    original_bytes = text.encode('utf-8')
    assert hashlib.sha256(original_bytes).hexdigest() == expected
    # 若需要原字节文件，明确选择一个新目标：
    # Path('processing.original.json').write_bytes(original_bytes)
```

## 9. Python Agent 直接调用

仅使用标准库并保留直接/相关证据区分的完整例子：

```sh
python3 examples/query_database.py
```

也可在本目录导入与 CLI 共用的只读 API：

```python
from flavor_db import FlavorDB

with FlavorDB() as db:
    found = db.search('大蒜', kind='ingredient', limit=50)
    profile = db.profile('ing-2053d8521c93')
    direct = db.processing(
        ingredient_id='ing-2053d8521c93',
        link_kind=['exact_name', 'alias_name'],
        limit=1000,
    )
    print(found['total'], profile['variant_count'], direct['total'])
```

从其他目录导入时，把本目录加入 Python 模块搜索路径，或直接使用本目录脚本的绝对路径。数据库默认仍为 flavor_db.py 同级 flavor.sqlite，也可 `FlavorDB('/path/to/flavor.sqlite')`。

## 返回值、分页和失败处理

- 成功结果写 stdout，JSON 的 null 和 boolean 保留类型。错误写 stderr，形如 `{"error":{"type":"…","message":"…"}}`，进程非零退出；不要将错误当成空结果。
- search、pairs、processing、indexes 默认 limit=50，最大 1,000，offset 从 0 开始。返回 total、returned、limit、offset、has_more、truncated 与 items。
- 下一页使用 offset + returned，直到 has_more=false。total 是当前筛选口径；不要只拿第一页称“全部”。truncated 在非首页也可能为 true，表示这次响应未含整个总体。
- sql 默认最多 100 行，最大 10,000，返回 total=null（未额外计数）及 has_more。需要确切总数时单独运行 COUNT；需要完整大量结果时自己设计明确的分页条件或使用只读标准库连接。
- sql 仅接受受限的只读 SELECT/CTE，支持 `--params` JSON 数组绑定 ? 或对象绑定 :name，拒绝写入、ATTACH 和扩展加载。默认超时 5 秒，可在子命令前指定 `--sql-timeout 30`，范围大于 0 至 60 秒。
- SQL 重复列名时返回 columns + 数组行以防字段覆盖，其他情况返回对象行。BLOB 通过通用 SQL 读取会按 base64 表达，图片导出优先使用 asset。
- `--compact` 是全局参数，应放在子命令之前；压缩的是 JSON 排版，不是删除证据字段。

```sh
python3 flavor_db.py --compact search '大蒜' --kind ingredient
python3 flavor_db.py --sql-timeout 30 sql --file queries/10_three_indexes.sql --limit 1000
```

## 用于三类创新的输出边界

按目标找原料应区分圆点标记、文字提及与加工效果；替换食材应比较多版本、具体状态与功能条件；新配方应保留直接配对依据和加工条件。可以输出候选与试验建议，但没有实测依据时不得写“预测提升 30%”、确定最佳配比或生成虚构感官曲线。每个建议同时给出来源记录、适用条件、未知/冲突及待验证事项。
