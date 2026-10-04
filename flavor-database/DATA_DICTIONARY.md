# 数据字典

数据库 `flavor.sqlite` 的结构以 [`schema.sql`](schema.sql) 为准。以下表与字段清单据该文件生成，说明保留证据语义。

## 范围与关系

| 资料 | 入库范围 |
|---|---:|
| 稳定食材身份 / 香气大类 / 描述词 | 1,474 / 14 / 70 |
| 来源圆点表 / 来源行 / 类别单元 | 949 / 10,439 / 146,146（10,439 × 14） |
| 有来源方向的配对 | 9,490（9,480 目录 + 10 恢复教学） |
| 原属性证据 / 原属性数值 / 加工适用性审核 | 253 / 24 / 253 |
| 加工记录 | 176（书中 163 + 研究 13），7 篇研究 |
| 加工方式 / 效果 / 来源名称组 | 55 / 293 / 154 |
| 已抽取书页文字 | 392 页 |
| 嵌入图片 | 1,475（1,474 SVG + 1 AI 主视觉 PNG） |

加工索引均是多对多；组内记录数用 `COUNT(DISTINCT processing_id)`。154 个来源名称组不是稳定身份数。条目、索引组、报告数值均不是独立实验样本数。

```text
ingredients → aliases / dot_records → dot_values → aroma_categories
source_tables → dot_records → pairings
attribute_evidence → evidence_links → ingredients
                   → descriptor_mentions → descriptors
                   → reported_numbers / evidence_domains
processing_records → methods / effects / ingredient_names
                   → processing_links → ingredients
                   → processing_evidence → attribute_evidence
                   → processing_numbers / sources
assets → ingredients（主视觉可无食材 ID）
book_pages + source_snapshots + metadata → 已抽取书页、输入快照与构建说明
```

图中 methods、effects、ingredient_names 是 processing_ 前缀表名的简称，aliases 是 ingredient_aliases。

## 类型、NULL 与 JSON

- `TEXT` 为 UTF-8；布尔值是 `INTEGER` 0/1；`ordinal` 是来源数组顺序。主外键和类型在每张字段表中列明。
- SQL `NULL` 表示未提供、无法可靠判读或不适用，依字段和原始 JSON 区分。来源已有“未报告”等文字则原样保留。空字符串、空数组、SQL NULL、JSON null 不擅自互换。
- 圆点 0 表示来源未标记，不是化学不存在、零浓度或零感官强度；NULL 不填成 0。主行共享标记可不适用。
- `value_json` / `minimum_json` / `maximum_json` 保留已提供非空值的原类型，可能是数字、范围、数组或文字。来源字段缺失与来源显式 null 均映射为 SQL NULL；仅靠展开列不能区分，须查 raw_json / source_snapshots 还原。必须同时读单位、指标、分母及操作符。
- `raw_json` 是完整来源或派生对象，`original_json` 是原证据依据，`raw_source_json` 是原始圆点提取资料；普通列仅为检索展开层，不截断未展开内容。
- `source_snapshots.content_json` 是输入文件完整 UTF-8 文本，`sha256` 对原字节计算。普通 raw_json 是对象再序列化，保证可深比较还原，不承诺原空格/键顺序。
- 资产 content 的 sha256 对嵌入字节计算。PDF 的摘要只用于验证外部原文件：数据库没有 PDF 二进制全文，但包含 392 页已有抽取文字。

## 证据范围与方向

`exact_name` 为来源名称匹配，`alias_name` 为别名匹配，`related_context` 为相关语境。前两者也须核对品种、部位和加工状态；JSON 中的 contextScope、quantitativeTransferAllowed 继续有效。提及和主题标签不能升级成属性存在事实。

| record_kind | 解释 | 限制 |
|---|---|---|
| change | 来源描述变化/比较 | 只用于报告条件，不外推任意增量 |
| condition_dependency | 随条件或过程组合变化 | 不压成固定普适方向 |
| state_profile | 某加工后/特定状态轮廓 | 未必有加工前对照，不构造变化率 |

效果方向当前为 increase、decrease、emerge、change、conditional、no_significant_change。未发现显著变化不是证明绝对无变化，也不是可填入计算的零。香气、味觉、质地、刺激感、化学测定和感官喜好必须分开。

## 表与字段

下列“否（主键）”指 schema 主键意图及本次有效数据；SQLite 普通 TEXT PRIMARY KEY 的历史 NULL 行为不应用于写入。本库通过只读接口使用。复合主键数字为列顺序。

### `ingredients`

粒度：一个稳定食材身份；原名生成的 ing-… ID 为键。显示名允许重复，raw_json 保留完整目录对象与历史 canonical，后者不是唯一可信风味向量。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `id` | `TEXT` | PK 1 | 否（主键） | 稳定身份或来源内唯一标识。 |
| `original_name` | `TEXT` | — | 否 | 原始身份名称。 |
| `display_name` | `TEXT` | — | 否 | 显示名称；不保证唯一。 |
| `visual_family` | `TEXT` | — | 是 | 图片/导航类别推断；不是风味测量。 |
| `recommendation_eligible` | `INTEGER` | — | 否 | 0/1：是否允许进入默认候选。 |
| `name_needs_review` | `INTEGER` | — | 否 | 0/1：是否仍有名称待审标志。 |
| `example_only` | `INTEGER` | — | 否 | 0/1：是否只来自教学身份。 |
| `search_text` | `TEXT` | — | 否 | 派生检索文本，不是新测量。 |
| `raw_json` | `TEXT` | — | 否 | 完整来源/派生对象 JSON；普通列未展开的字段仍保留。 |

### `ingredient_aliases`

粒度：一个食材身份的一条别名。alias_key 只用于规范化检索，不授权合并稳定身份。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `ingredient_id` | `TEXT` | PK 1；→ `ingredients.id` | 否（主键） | 稳定食材身份。 |
| `alias` | `TEXT` | PK 2 | 否（主键） | 别名原字符串。 |
| `alias_key` | `TEXT` | — | 否 | 检索规范键，不用于合并 ID。 |

### `aroma_categories`

粒度：一个原书圆点类别，共 14 类；category_index=0–13，来源名与显示名分开。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `category_index` | `INTEGER` | PK 1 | 否（主键） | 原表类别顺序，0–13。 |
| `source_name` | `TEXT` | — | 否 | 来源类别名称。 |
| `display_name` | `TEXT` | — | 否 | 显示名称；不保证唯一。 |

### `descriptors`

粒度：一个原书描述词条，共 70 条。raw_json 保留原 taxonomy；描述词不是数值量表。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `id` | `TEXT` | PK 1 | 否（主键） | 稳定身份或来源内唯一标识。 |
| `category_index` | `INTEGER` | → `aroma_categories.category_index` | 是 | 原表类别顺序，0–13。 |
| `source_label` | `TEXT` | — | 否 | 来源描述词。 |
| `display_label` | `TEXT` | — | 否 | 显示描述词。 |
| `raw_json` | `TEXT` | — | 否 | 完整来源/派生对象 JSON；普通列未展开的字段仍保留。 |

### `source_tables`

粒度：一张圆点来源表，共 949 张。raw_json 为目录表对象，raw_source_json 为原始圆点表对象；主行外键延迟至事务结束检查。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `id` | `TEXT` | PK 1 | 否（主键） | 稳定身份或来源内唯一标识。 |
| `main_ingredient_id` | `TEXT` | → `ingredients.id` | 否 | 当前原表主食材身份。 |
| `main_record_id` | `TEXT` | → `dot_records.id` | 是 | 当前原表主行 ID。 |
| `pdf_page` | `INTEGER` | — | 是 | PDF 文件页序，1 起。 |
| `book_page` | `INTEGER` | — | 是 | 书的印刷页码；不推算固定偏移。 |
| `is_example` | `INTEGER` | — | 否 | 0/1：是否教学；默认候选排除。 |
| `review_status` | `TEXT` | — | 是 | 已有提取/复核状态，不等于科学重复验证。 |
| `raw_json` | `TEXT` | — | 否 | 完整来源/派生对象 JSON；普通列未展开的字段仍保留。 |
| `raw_source_json` | `TEXT` | — | 否 | 原始圆点对象 JSON，包括可用坐标和修订资料。 |

### `dot_records`

粒度：一个食材身份在一张原表的一行，共 10,439 行。raw_json 为目录行；raw_source_json 保存原提取对象、坐标、复核与手工修改资料。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `id` | `TEXT` | PK 1 | 否（主键） | 稳定身份或来源内唯一标识。 |
| `ingredient_id` | `TEXT` | → `ingredients.id` | 否 | 稳定食材身份。 |
| `table_id` | `TEXT` | → `source_tables.id` | 否 | 原表 ID。 |
| `role` | `TEXT` | — | 否 | 原表行角色。 |
| `main_ingredient_id` | `TEXT` | → `ingredients.id` | 是 | 当前原表主食材身份。 |
| `pdf_page` | `INTEGER` | — | 是 | PDF 文件页序，1 起。 |
| `book_page` | `INTEGER` | — | 是 | 书的印刷页码；不推算固定偏移。 |
| `is_example` | `INTEGER` | — | 否 | 0/1：是否教学；默认候选排除。 |
| `identity_eligible` | `INTEGER` | — | 否 | 0/1：来源行身份是否可用。 |
| `review_status` | `TEXT` | — | 是 | 已有提取/复核状态，不等于科学重复验证。 |
| `name_review_status` | `TEXT` | — | 是 | 来源行名称审核状态。 |
| `raw_json` | `TEXT` | — | 否 | 完整来源/派生对象 JSON；普通列未展开的字段仍保留。 |
| `raw_source_json` | `TEXT` | — | 否 | 原始圆点对象 JSON，包括可用坐标和修订资料。 |

### `dot_values`

粒度：一个来源行 × 一个类别，共 146,146 行。presence=1/0/NULL 为标记/未标记/未知；shared_with_main 只描述当前表共享标记，主行可不适用。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `record_id` | `TEXT` | PK 1；→ `dot_records.id` | 否（主键） | 圆点来源行 ID。 |
| `category_index` | `INTEGER` | PK 2；→ `aroma_categories.category_index` | 否（主键） | 原表类别顺序，0–13。 |
| `presence` | `INTEGER` | — | 是 | 1 标记、0 未标记、NULL 未知。 |
| `shared_with_main` | `INTEGER` | — | 是 | 1 本表共享标记、0 未标记、NULL 未知或不适用。 |

### `pairings`

粒度：一个原表的主食材 → 配对行。9,480 条目录配对与 10 条恢复教学配对，共 9,490 条；不是不重复的无向食材对。共享类别经 paired_record_id 关联 dot_values。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `id` | `TEXT` | PK 1 | 否（主键） | 稳定身份或来源内唯一标识。 |
| `table_id` | `TEXT` | → `source_tables.id` | 否 | 原表 ID。 |
| `main_record_id` | `TEXT` | → `dot_records.id` | 是 | 当前原表主行 ID。 |
| `paired_record_id` | `TEXT` | → `dot_records.id` | 否 | 配对来源行 ID。 |
| `main_ingredient_id` | `TEXT` | → `ingredients.id` | 否 | 当前原表主食材身份。 |
| `paired_ingredient_id` | `TEXT` | → `ingredients.id` | 否 | 配对行食材身份。 |
| `is_example` | `INTEGER` | — | 否 | 0/1：是否教学；默认候选排除。 |
| `recommendation_eligible` | `INTEGER` | — | 否 | 0/1：是否允许进入默认候选。 |
| `provenance_kind` | `TEXT` | — | 否 | 目录或恢复教学配对等来源类型。 |
| `raw_json` | `TEXT` | — | 否 | 完整来源/派生对象 JSON；普通列未展开的字段仍保留。 |

### `attribute_evidence`

粒度：一条原属性文字/图表证据，共 253 条 E… ID。original_json 是原依据行，raw_json 是含关联、标签与检索文本的完整对象。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `id` | `TEXT` | PK 1 | 否（主键） | 稳定身份或来源内唯一标识。 |
| `ingredient_name` | `TEXT` | — | 是 | 原文食材名。 |
| `display_ingredient` | `TEXT` | — | 是 | 显示食材名，不是唯一身份。 |
| `state` | `TEXT` | — | 是 | 原文原料状态与上下文。 |
| `attribute_type` | `TEXT` | — | 是 | 来源属性类型。 |
| `evidence_mode` | `TEXT` | — | 是 | 文字、图表等证据载体。 |
| `pdf_page` | `INTEGER` | — | 是 | PDF 文件页序，1 起。 |
| `book_page` | `INTEGER` | — | 是 | 书的印刷页码；不推算固定偏移。 |
| `note` | `TEXT` | — | 是 | 来源附注和限制。 |
| `search_text` | `TEXT` | — | 否 | 派生检索文本，不是新测量。 |
| `raw_json` | `TEXT` | — | 否 | 完整来源/派生对象 JSON；普通列未展开的字段仍保留。 |
| `original_json` | `TEXT` | — | 否 | 原始依据对象 JSON。 |

### `evidence_links`

粒度：一条属性证据的一条稳定身份关联；ordinal 保留来源数组顺序。raw_json 保留 contextScope、匹配依据和 quantitativeTransferAllowed。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `evidence_id` | `TEXT` | PK 1；→ `attribute_evidence.id` | 否（主键） | E… 原属性证据 ID。 |
| `ordinal` | `INTEGER` | PK 2 | 否（主键） | 原数组顺序；不是质量排名。 |
| `ingredient_id` | `TEXT` | → `ingredients.id` | 否 | 稳定食材身份。 |
| `link_kind` | `TEXT` | — | 否 | exact_name / alias_name / related_context。 |
| `reason` | `TEXT` | — | 是 | 关联或审核理由。 |
| `raw_json` | `TEXT` | — | 否 | 完整来源/派生对象 JSON；普通列未展开的字段仍保留。 |

### `evidence_domains`

粒度：一条属性证据 × 一个检索主题标签；标签不是属性存在断言。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `evidence_id` | `TEXT` | PK 1；→ `attribute_evidence.id` | 否（主键） | E… 原属性证据 ID。 |
| `domain` | `TEXT` | PK 2 | 否（主键） | 维度/检索主题。 |

### `descriptor_mentions`

粒度：一条证据中的一个描述词提及。interpretation=text_mention_only；否定、比较和例子也可能命中。raw_json 保留字段路径。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `evidence_id` | `TEXT` | PK 1；→ `attribute_evidence.id` | 否（主键） | E… 原属性证据 ID。 |
| `ordinal` | `INTEGER` | PK 2 | 否（主键） | 原数组顺序；不是质量排名。 |
| `descriptor_id` | `TEXT` | → `descriptors.id` | 否 | 原描述词 ID。 |
| `interpretation` | `TEXT` | — | 否 | 提及语义边界；不是属性存在断言。 |
| `raw_json` | `TEXT` | — | 否 | 完整来源/派生对象 JSON；普通列未展开的字段仍保留。 |

### `reported_numbers`

粒度：一条原属性报告数值，共 24 条。值和范围保留 JSON 原类型；单位、分母、比较操作符不可丢弃。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `id` | `TEXT` | PK 1 | 否（主键） | 稳定身份或来源内唯一标识。 |
| `evidence_id` | `TEXT` | → `attribute_evidence.id` | 是 | E… 原属性证据 ID。 |
| `metric` | `TEXT` | — | 是 | 报告指标名。 |
| `unit` | `TEXT` | — | 是 | 报告单位；缺失不可补默认值。 |
| `value_json` | `TEXT` | — | 是 | 非空值的原类型 JSON；缺失与显式 null 均为 SQL NULL，细节查 raw_json。 |
| `minimum_json` | `TEXT` | — | 是 | 下限原类型 JSON；缺失与显式 null 均为 SQL NULL。 |
| `maximum_json` | `TEXT` | — | 是 | 上限原类型 JSON；缺失与显式 null 均为 SQL NULL。 |
| `operator` | `TEXT` | — | 是 | 原报告比较/约束操作符。 |
| `denominator` | `TEXT` | — | 是 | 指标分母或归一化基准。 |
| `pdf_page` | `INTEGER` | — | 是 | PDF 文件页序，1 起。 |
| `book_page` | `INTEGER` | — | 是 | 书的印刷页码；不推算固定偏移。 |
| `raw_json` | `TEXT` | — | 否 | 完整来源/派生对象 JSON；普通列未展开的字段仍保留。 |

### `sources`

粒度：一个书目或研究来源条目；条目数量不等于独立论文数。主书 ID 为 B-FOODPAIRING-2021，外部 PDF 路径与摘要只用于定位校验。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `id` | `TEXT` | PK 1 | 否（主键） | 稳定身份或来源内唯一标识。 |
| `kind` | `TEXT` | — | 否 | 所属实体或来源种类。 |
| `title` | `TEXT` | — | 是 | 可读标题。 |
| `journal` | `TEXT` | — | 是 | 期刊名称。 |
| `year` | `INTEGER` | — | 是 | 发表年份。 |
| `doi` | `TEXT` | — | 是 | 来源 DOI。 |
| `url` | `TEXT` | — | 是 | 来源网页 URL。 |
| `relative_path` | `TEXT` | — | 是 | 构建来源或原资产相对路径；运行不要求外部资产存在。 |
| `sha256` | `TEXT` | — | 是 | 原文件字节 SHA-256，证明一致性而非科学正确性。 |
| `raw_json` | `TEXT` | — | 否 | 完整来源/派生对象 JSON；普通列未展开的字段仍保留。 |

### `processing_records`

粒度：一条加工变化、条件依赖或处理状态记录，共 176 条（书中 163、研究 13，涉及 7 篇论文）。source_json 是逐条出处，original_json 是依据，raw_json 是完整加工对象。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `id` | `TEXT` | PK 1 | 否（主键） | 稳定身份或来源内唯一标识。 |
| `title` | `TEXT` | — | 否 | 可读标题。 |
| `record_kind` | `TEXT` | — | 否 | change / condition_dependency / state_profile。 |
| `before_state` | `TEXT` | — | 是 | 来源前状态；缺失不补基线。 |
| `after_state` | `TEXT` | — | 是 | 来源后状态；不保证有对照实验。 |
| `conditions` | `TEXT` | — | 是 | 温时、设备、品种、基质、测定与缺失条件说明。 |
| `mechanism` | `TEXT` | — | 是 | 来源机制解释，不等于独立验证。 |
| `summary` | `TEXT` | — | 是 | 基于原证据的摘要。 |
| `limitations` | `TEXT` | — | 是 | 外推、测量和资料限制。 |
| `evidence_level` | `TEXT` | — | 是 | 证据类型/级别说明。 |
| `source_kind` | `TEXT` | — | 否 | book 或 research。 |
| `source_id` | `TEXT` | → `sources.id` | 否 | sources 中的书目 ID。 |
| `search_text` | `TEXT` | — | 否 | 派生检索文本，不是新测量。 |
| `raw_json` | `TEXT` | — | 否 | 完整来源/派生对象 JSON；普通列未展开的字段仍保留。 |
| `source_json` | `TEXT` | — | 否 | 逐记录出处 JSON，含可用页码、DOI/URL。 |
| `original_json` | `TEXT` | — | 否 | 原始依据对象 JSON。 |

### `processing_methods`

粒度：一条加工记录的一个方式索引项；55 个规范方式组，原标签保留。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `processing_id` | `TEXT` | PK 1；→ `processing_records.id` | 否（主键） | 加工记录 ID。 |
| `ordinal` | `INTEGER` | PK 2 | 否（主键） | 原数组顺序；不是质量排名。 |
| `method_key` | `TEXT` | — | 否 | 加工方式导航组键。 |
| `label` | `TEXT` | — | 否 | 规范显示标签。 |
| `original_label` | `TEXT` | — | 是 | 归并前来源标签。 |

### `processing_effects`

粒度：一条加工记录的一个效果索引项；293 个维度 + 规范标签 + 方向组合组。raw_json 保留规范化依据和原标签，detail 保留上下文。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `processing_id` | `TEXT` | PK 1；→ `processing_records.id` | 否（主键） | 加工记录 ID。 |
| `ordinal` | `INTEGER` | PK 2 | 否（主键） | 原数组顺序；不是质量排名。 |
| `domain` | `TEXT` | — | 否 | 维度/检索主题。 |
| `label` | `TEXT` | — | 否 | 规范显示标签。 |
| `original_label` | `TEXT` | — | 是 | 归并前来源标签。 |
| `direction` | `TEXT` | — | 否 | 增加/减少/形成/变化/条件依赖/未显著变化代码。 |
| `group_key` | `TEXT` | — | 否 | 维度 + 规范标签 + 方向的效果组键。 |
| `detail` | `TEXT` | — | 是 | 具体效果描述与上下文。 |
| `raw_json` | `TEXT` | — | 否 | 完整来源/派生对象 JSON；普通列未展开的字段仍保留。 |

### `processing_ingredient_names`

粒度：一条加工记录的一个来源名称索引项；154 个名称组，不是 154 个 stable ID 身份。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `processing_id` | `TEXT` | PK 1；→ `processing_records.id` | 否（主键） | 加工记录 ID。 |
| `ordinal` | `INTEGER` | PK 2 | 否（主键） | 原数组顺序；不是质量排名。 |
| `name_key` | `TEXT` | — | 否 | 来源名称导航键，不是 stable ingredient ID。 |
| `label` | `TEXT` | — | 否 | 规范显示标签。 |
| `original_label` | `TEXT` | — | 是 | 归并前来源标签。 |

### `processing_links`

粒度：一条加工记录的一条稳定食材身份关联。直接名称匹配仍需核对状态；相关语境单列解释。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `processing_id` | `TEXT` | PK 1；→ `processing_records.id` | 否（主键） | 加工记录 ID。 |
| `ordinal` | `INTEGER` | PK 2 | 否（主键） | 原数组顺序；不是质量排名。 |
| `ingredient_id` | `TEXT` | → `ingredients.id` | 否 | 稳定食材身份。 |
| `link_kind` | `TEXT` | — | 否 | exact_name / alias_name / related_context。 |
| `reason` | `TEXT` | — | 是 | 关联或审核理由。 |
| `raw_json` | `TEXT` | — | 否 | 完整来源/派生对象 JSON；普通列未展开的字段仍保留。 |

### `processing_evidence`

粒度：一条加工记录 × 一条既有 E… 属性证据。补充书页和研究可能无 E… 关联，仍可通过 source_json 追溯出处。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `processing_id` | `TEXT` | PK 1；→ `processing_records.id` | 否（主键） | 加工记录 ID。 |
| `evidence_id` | `TEXT` | PK 2；→ `attribute_evidence.id` | 否（主键） | E… 原属性证据 ID。 |

### `processing_numbers`

粒度：一条加工记录中的一个报告数值。保留 reportedValues 的原类型、范围、单位与测定语境；这不是完整原始实验矩阵。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `processing_id` | `TEXT` | PK 1；→ `processing_records.id` | 否（主键） | 加工记录 ID。 |
| `ordinal` | `INTEGER` | PK 2 | 否（主键） | 原数组顺序；不是质量排名。 |
| `metric` | `TEXT` | — | 是 | 报告指标名。 |
| `value_json` | `TEXT` | — | 是 | 非空值的原类型 JSON；缺失与显式 null 均为 SQL NULL，细节查 raw_json。 |
| `unit` | `TEXT` | — | 是 | 报告单位；缺失不可补默认值。 |
| `context` | `TEXT` | — | 是 | 数值的测量或条件语境。 |
| `minimum_json` | `TEXT` | — | 是 | 下限原类型 JSON；缺失与显式 null 均为 SQL NULL。 |
| `maximum_json` | `TEXT` | — | 是 | 上限原类型 JSON；缺失与显式 null 均为 SQL NULL。 |
| `operator` | `TEXT` | — | 是 | 原报告比较/约束操作符。 |
| `denominator` | `TEXT` | — | 是 | 指标分母或归一化基准。 |
| `raw_json` | `TEXT` | — | 否 | 完整来源/派生对象 JSON；普通列未展开的字段仍保留。 |

### `processing_audit`

粒度：一条既有属性证据的加工适用性审核，共 253 条；保留决定、理由及对应加工 ID 数组。未纳入不意味着原属性证据无效。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `evidence_id` | `TEXT` | PK 1；→ `attribute_evidence.id` | 否（主键） | E… 原属性证据 ID。 |
| `decision` | `TEXT` | — | 否 | 加工适用性审核决定。 |
| `reason` | `TEXT` | — | 是 | 关联或审核理由。 |
| `record_ids_json` | `TEXT` | — | 否 | 对应加工 ID 数组，空数组表示未纳入。 |
| `raw_json` | `TEXT` | — | 否 | 完整来源/派生对象 JSON；普通列未展开的字段仍保留。 |

### `source_snapshots`

粒度：一个构建输入 JSON 文件的完整文本快照。content_json 为原 UTF-8 文本，sha256 对原文件字节计算，可无原工作区还原。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `id` | `TEXT` | PK 1 | 否（主键） | 稳定身份或来源内唯一标识。 |
| `relative_path` | `TEXT` | — | 否 | 构建来源或原资产相对路径；运行不要求外部资产存在。 |
| `sha256` | `TEXT` | — | 否 | 原文件字节 SHA-256，证明一致性而非科学正确性。 |
| `content_json` | `TEXT` | — | 否 | 原输入 JSON 完整 UTF-8 文本。 |

### `book_pages`

粒度：一页 PDF 的已抽取文字，共 392 页。pdf_page 是 PDF 页序；文字抽取不保留全部图表视觉关系，不能替代原图或推算印刷页码。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `pdf_page` | `INTEGER` | PK 1 | 否（主键） | PDF 文件页序，1 起。 |
| `text` | `TEXT` | — | 否 | 抽取或合成检索文本；回源解释。 |
| `width` | `REAL` | — | 是 | 已有抽取页尺寸；本次来源缺少该字段时 NULL，不从文字估计。 |
| `height` | `REAL` | — | 是 | 已有抽取页尺寸；本次来源缺少该字段时 NULL，不从文字估计。 |
| `raw_json` | `TEXT` | — | 否 | 完整来源/派生对象 JSON；普通列未展开的字段仍保留。 |

### `metadata`

粒度：一个构建/范围/政策元信息键值项；value_json 保存完整 JSON 值。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `key` | `TEXT` | PK 1 | 否（主键） | 元信息唯一键。 |
| `value_json` | `TEXT` | — | 否 | 该键完整 JSON 值，不限定为数值。 |

### `assets`

粒度：一个嵌入资产，共 1,475 个：1,474 个食材 SVG 与 1 张 AI 主视觉 PNG。content 保留原字节，hero 可无 ingredient_id；不是实物照片或形态测量证据。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `id` | `TEXT` | PK 1 | 否（主键） | 稳定身份或来源内唯一标识。 |
| `ingredient_id` | `TEXT` | → `ingredients.id` | 是 | 稳定食材身份。 |
| `relative_path` | `TEXT` | — | 否 | 构建来源或原资产相对路径；运行不要求外部资产存在。 |
| `status` | `TEXT` | — | 否 | 资产来源/审核状态。 |
| `sha256` | `TEXT` | — | 否 | 原文件字节 SHA-256，证明一致性而非科学正确性。 |
| `mime_type` | `TEXT` | — | 否 | 原资产 MIME 类型。 |
| `byte_size` | `INTEGER` | — | 否 | 原图片字节数。 |
| `width` | `INTEGER` | — | 是 | 页面或图片宽度；单位须按 raw_json 解释。 |
| `height` | `INTEGER` | — | 是 | 页面或图片高度；单位须按 raw_json 解释。 |
| `content` | `BLOB` | — | 否 | 完整图片二进制字节。 |
| `raw_json` | `TEXT` | — | 否 | 完整来源/派生对象 JSON；普通列未展开的字段仍保留。 |

### `search_documents`

粒度：一种实体的一份可检索文本。kind+id 定位原实体；检索命中后应回源读取完整条件和出处。

| 字段 | SQLite 类型 | 主键 / 外键 | 可为 NULL | 含义 |
|---|---|---|---|---|
| `kind` | `TEXT` | PK 1 | 否（主键） | 所属实体或来源种类。 |
| `id` | `TEXT` | PK 2 | 否（主键） | 稳定身份或来源内唯一标识。 |
| `title` | `TEXT` | — | 否 | 可读标题。 |
| `text` | `TEXT` | — | 否 | 抽取或合成检索文本；回源解释。 |

## 视图

| 视图 | 粒度 / 字段 | 默认口径 |
|---|---|---|
| `v_ingredient_aroma_profile` | 一食材 × 一类别。ingredient_id、category_name、status 为 TEXT；category_index、marked_count、unmarked_count、unknown_count、record_count、has_unknown 为 INTEGER | 每 ID 14 行，排除教学来源。计数之和等于 record_count。有 1 与 0 则 conflict；否则有未知格或无正式行则 unknown；再判 marked/unmarked。conflict 仍可能 has_unknown=1。仅教学身份 record_count=0、unknown_count=0、status=unknown；没有正式来源不等于存在一个未知格。 |
| `v_processing_by_method` | 每个方式关联行；method_key、method_label、method_original_label 为 TEXT，method_ordinal 为 INTEGER，再加 processing_records 全字段 | 同记录可入多组，COUNT(DISTINCT id) 才是组内证据数。 |
| `v_processing_by_effect` | 每个效果关联行；group_key、domain、direction、effect_label、effect_original_label、effect_detail 为 TEXT，effect_ordinal 为 INTEGER，再加工记录全字段 | 在同一效果行联合过滤维度与方向，避免跨效果伪命中。 |
| `v_processing_by_ingredient` | 每个来源名称关联行；name_key、ingredient_label、ingredient_original_label 为 TEXT，ingredient_ordinal 为 INTEGER，再加工记录全字段 | 名称导航与 stable ID 关联不同。 |
| `v_recommendable_pairings` | 字段与 pairings 相同 | recommendation_eligible=1 且 is_example=0；无合并、无分数化。 |

视图没有独立主键/外键约束，引用继承底表。原始字段的 NULL 保留；计数值为派生数量，不是强度。

## 可选检索加速结构

构建器在环境支持时额外创建 `search_fts`（FTS5 trigram，external content=search_documents，rowid 对齐），字段为 kind、id、title、text；kind/id 不建词项索引。FTS 自带的 search_fts_data、search_fts_idx、search_fts_docsize、search_fts_config 等影子表是 SQLite 内部结构，不是新增业务证据，Agent 不应直接修改。短中文词或缺少 FTS 支持时仍可使用普通只读文本查询；以 manifest 的 runtime.search 记录实际可用状态。27 张业务表与上列 5 个视图不依赖这个加速层解释。

## 追溯与校验

1. 由 ingredient ID 读所有 dot_records，再以 record_id/table_id 回到源行与源表；PDF 页序和印刷页码分别引用。
2. E… ID 读取 original_json；加工 ID 读取 source_json、original_json、conditions、limitations，再经 source_id 查书目/研究。
3. `source_snapshots` 中主要 ID 为 catalog、evidence-full、processing、processing-book、processing-research、asset-manifest、attribute-source、dot-source、book-pages；其他快照使用 file:相对路径。以实际查询清单为准。
4. 对 content_json 的 UTF-8 字节计算 SHA-256，应等于该行 sha256。`manifest.json` 另记录数据库文件及输入摘要，具体运行结果见校验报告。
5. 查询、还原源快照和导出嵌入图片不依赖外部原 JSON。重建需来源工作区；打开 PDF 图表需外部原书。原 JSON 中 crop_path、sourceCropPath 等复核裁图路径原样保留，裁图本身不在 1,475 个 assets 之中，也未复制进本目录；搬移后这些路径不保证有效。book_pages 是文字抽取，不完整保留视觉表格、图形和阅读顺序，不推算固定页码偏移。

当前库是现有抽取成果的无损整理，不代表全书/论文原始实验矩阵全部提取、每格圆点人工复核或独立实验重现。校验说明入库一致性，不把资料升级为新测量。
