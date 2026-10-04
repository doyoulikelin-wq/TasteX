# 风味证据数据库 · Agent 本地版

将现有风味工作台的食材、原始圆点记录、文字证据、加工变化、三个加工索引及图片整理为一个可搬移的 SQLite 数据库。**建议使用 Python 3.10 或更新版本，仅需标准库，无需联网或安装依赖。** 当前目录：`/Users/linlin/Desktop/IACDTT/flavor-database`。

## 三步开始

1. Agent 先读 [`AGENTS.md`](AGENTS.md)，了解稳定 ID、来源、未知与冲突的使用约束。
2. 在本目录查看范围并搜索食材，取得真实 ID：

```sh
python3 flavor_db.py stats
python3 flavor_db.py search '大蒜' --kind ingredient
```

3. 用搜索到的 ID 查全部来源版本与加工记录：

```sh
python3 flavor_db.py profile ing-2053d8521c93
python3 flavor_db.py processing --ingredient-id ing-2053d8521c93 --link-kind exact_name --link-kind alias_name
python3 flavor_db.py indexes --by method --limit 1000
```

上例只查直接名称/别名关联；相关语境须单列。接口返回 JSON，保留来源 ID、条件、限制与完整原始对象；计数不是风味强度。

## 文件入口

| 文件 | 用途 |
|---|---|
| [`flavor.sqlite`](flavor.sqlite) | 完整本地数据库，约 155 MB；包含源 JSON 快照、392 页已抽取文字及图片字节 |
| [`flavor_db.py`](flavor_db.py) | 只读 JSON 命令行与可导入 Python API |
| [`AGENTS.md`](AGENTS.md) | Agent 首读合约：如何检索、引用、保留条件和生成试配假设 |
| [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md) | 全部业务表/视图、字段类型、主外键、NULL 与 JSON 语义 |
| [`QUERY_EXAMPLES.md`](QUERY_EXAMPLES.md) | 可复制的 CLI、SQL、Python 示例及返回值说明 |
| [`schema.sql`](schema.sql) | 数据库结构 |
| [`VALIDATION.md`](VALIDATION.md) | 中文验收结论与测试/报告入口 |
| [`manifest.json`](manifest.json) | 版本、计数、数据库/输入摘要、构建范围 |
| [`queries/`](queries/) | 参数化 SQL 示例：全部版本、原证据、三索引、配对与出处 |
| [`examples/query_database.py`](examples/query_database.py) | 只用 Python 标准库的只读查询示例 |
| [`build_database.py`](build_database.py) | 从原工作区重新构建数据库；日常查询无需运行 |

## 当前收录范围

| 数据 | 数量 |
|---|---:|
| 稳定食材身份 | 1,474（默认推荐可用 1,464） |
| 来源圆点表 / 来源行 | 949 / 10,439 |
| 圆点类别单元 | 146,146 = 10,439 × 14 |
| 配对记录 | 9,490 = 9,480 目录配对 + 10 恢复教学配对 |
| 原属性证据 / 描述词 / 报告数值 | 253 / 70 / 24 |
| 加工记录 | 176 = 163 书中记录 + 13 研究记录，涉及 7 篇论文 |
| 加工方式 / 效果 / 来源名称索引组 | 55 / 293 / 154 |
| 加工适用性审核 / 加工报告数值 | 253 / 65 |
| 源 JSON 文件快照 / 已抽取书页文字 | 19 / 392 页 |
| 嵌入图片资产 | 1,475 = 1,474 个 SVG + 1 张 AI 主视觉 PNG |

数量口径分别是来源行、记录、关联或组，不是实验样本量。多个来源版本、冲突、未知、教学资料和无法直接关联的证据均保留。三个加工索引组重叠，不能把组内计数相加当成总记录数。

## 搬移与只读调用

复制整个 `flavor-database` 文件夹到另一台电脑后，可直接运行上述命令。最小查询运行集是 `flavor.sqlite` 与 `flavor_db.py`，但供 Agent 使用时请同时携带本目录 Markdown。接口默认在自身目录找库，不依赖当前工作目录或原 JSON 路径：

```sh
python3 /path/to/flavor-database/flavor_db.py stats
python3 flavor_db.py --db /path/to/flavor.sqlite stats
```

日常使用只读；需要导出图片时显式传入 `asset --out`。普通查询不会改库。重建依赖原数据工作区，在工作区根目录运行：

```sh
python3 flavor-database/build_database.py --workspace /Users/linlin/Desktop/IACDTT
```

其他位置重建时修改 `--workspace` 为包含来源文件的根目录，可用 `--output /path/to/flavor.sqlite` 指定目标。修改应先发生在有出处和审核记录的来源文件，再重建与核验；不要直接改 SQLite 中的证据。

## 可以支持什么

Agent 可据此按目标筛原料、比较替换候选、组合有出处的配对与加工路径，生成待实做的试配方案。每条结论需携带 ID、原出处、条件、限制及“来源陈述/研究摘要/Agent 假设”的区分。

原表圆点不是浓度或感官强度；未标记不是无分子，未知不是零。研究条目保存已整理结论与报告值，尚非论文完整原始实验矩阵。此库也不表示全书已穷尽提取、每格已人工复核或结果已独立实验验证。

原书 PDF **不嵌入**，仅保留外部路径与摘要；392 页抽取文字不替代原图表。原 JSON 中的复核裁图路径原样保留，但裁图本身未嵌入或搬移；在新机器进行视觉复核仍需原 PDF 或原工作区。图片是程序 SVG 插画与 AI 主视觉，不是真实食材照片。数据库不含浏览器中用户保存的试配配方或 localStorage。

## 校验与重跑

另有 63 项文档命令、SQL 与 Python 示例核验通过，记录见 [`validation-doc-examples.json`](validation-doc-examples.json)。

27 项核心检查已通过：13 项来源一致性、8 项查询语义/可搬移性、6 项 API 只读与边界检查。详细范围见 [`VALIDATION.md`](VALIDATION.md)，机器可读记录为 [`validation-source.json`](validation-source.json)、[`validation-query-semantics.json`](validation-query-semantics.json)、[`validation-api.json`](validation-api.json)。

在本目录可重跑：

```sh
python3 tests/test_database.py
python3 tests/test_query_semantics.py
python3 tests/test_api.py
```

来源一致性检查需要原工作区文件；携带数据库后可继续运行查询与只读接口检查。构建和校验不会把证据升级成科学测量或配方验证。
