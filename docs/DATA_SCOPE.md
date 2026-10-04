# 数据范围、迁移与恢复

TasteX 的运行数据源是 `flavor-database/flavor.sqlite`。日常查询、harness 运行、已有证据追溯和下面的自包含校验都不需要原作者电脑上的工作区。需要 Python 3.10 以上版本，使用标准库即可。

## 当前保存了什么

数据库包含 1,474 个食材身份、949 个来源表、10,439 条圆点记录、146,146 个类别单元、9,490 条有来源方向的配对、253 条属性证据、176 条加工记录、392 页抽取文字，以及 1,475 个本地图片资产。配对中包括显式标记的教学记录；不要把总条数当成可推荐的不同无向配对数量。

数据库还保存 **19 份来源 JSON 的精确 UTF-8 文本快照**，涵盖目录、属性、圆点原始整理、加工、别名和审查记录、图片清单以及全书抽取文字。`raw_json` 保存每条原始对象的完整语义；`source_snapshots.content_json` 还保留原文件格式与字节摘要。查询中的未知值、冲突、来源版本、状态和条件都应保留。

图片由 1,474 份程序绘制的食材 SVG 示意图和 1 张 AI 生成草莓主视觉构成，不是全部食材的真实照片，也不是品种鉴定或感官测量证据。

## 自包含校验

在仓库根目录执行：

```sh
python3 scripts/verify_database.py
```

可指定迁移后的数据库与清单：

```sh
python3 scripts/verify_database.py --db /path/to/flavor.sqlite --manifest /path/to/manifest.json
```

可将 JSON 结果写到一个尚不存在的文件：

```sh
python3 scripts/verify_database.py --report /tmp/tastex-database-check.json
```

校验复用随库保留的原始映射测试，并将输入改为数据库中的快照。16 组检查覆盖 SQLite 完整性和外键、数据库/构建器/结构文件与清单的 SHA-256、全部表行数与关键统计、19 份快照的 UTF-8 精确摘要，以及全部食材身份、圆点单元、配对、属性关联、加工关联、数值与单位、全来源轮廓、页文本、检索文本和资产字节。验证前后数据库摘要必须相同。

**这些检查证明数据库与随附来源副本一致，不能证明原始人工提取或 OCR 正确。** 它们也不证明原书科学结论已被独立验证、论文原始实验矩阵已完整提取，或某个配方已被实际试吃。数据库与快照共同继承的错误，需要回看原书或原研究后修订。SHA-256 是完整性检查，不是第三方签名或可信来源认证。

原有完整工作区测试仍保留在 `flavor-database/tests/test_database.py`。该原测试需要外部 JSON、原图片和 PDF；普通迁移验证应使用新脚本。新脚本的 `original_pdf_rechecked` 明确为 `false`，只比对数据库与清单里保存的 PDF 引用摘要。

## 恢复来源文件

恢复 19 份 JSON 到显式目录：

```sh
python3 scripts/restore_sources.py /tmp/tastex-restored-sources
```

同时恢复图片：

```sh
python3 scripts/restore_sources.py /tmp/tastex-restored-with-assets --assets
```

仅检查恢复计划而不写文件：

```sh
python3 scripts/restore_sources.py /tmp/tastex-preview --assets --dry-run
```

脚本按原工作区相对路径结构恢复，包括 `flavor-studio/`、`output/flavor/`、`outputs/…/` 与 `tmp/pdfs/flavor_source/pages.json`。它先核对所有内容摘要和目标路径，再创建文件；已有目标文件、越界相对路径、绝对路径及符号链接目标会被拒绝。脚本没有覆盖模式，也不会写源数据库。可以选择一个新的空目录重新恢复。

## 原书、截图与完整重建

仓库**不提供原始 PDF，也不提供原页裁图和复核截图**。数据库中的 PDF、裁图及旧工作区路径是保留下来的出处引用，搬移后不应假定这些路径可直接打开。392 页抽取文字不能替代图表的视觉核验，PDF 页序不能统一减去固定数值当作印刷页码。

若需运行原构建器完整重建，先恢复 JSON 和资产，另行提供自己有权使用的原 PDF，并与 `manifest.json` 中的 `original_pdf.sha256` 对照。原构建器要求原 PDF 以记录真实摘要；本项目没有用空白 PDF 或伪造摘要绕过该要求。原页截图的重新生成和人工复核也需要合法取得的源文件。

```sh
python3 flavor-database/build_database.py --workspace /path/to/restored-workspace --output /path/to/new/flavor.sqlite
```

新建输出应放入单独目录，保留当前数据库与审计记录。源构建器默认输出会替换目标，因此上例使用明确的新输出路径。

## 内容权利与经验边界

原书文字、图表对应的整理内容、论文信息及引用资料的权利属于各自权利人。仓库存储、哈希校验或提供导出工具 **不产生、也不扩大这些来源内容的使用授权**；代码许可不自动覆盖来源文本、图像和数据库中的第三方内容。阅读、再分发与商业使用应按对应内容的实际授权处理。项目没有声称对这些来源拥有重新许可的权利。

用户的配方、试验计划和真实感官结果应保存在独立案例或经验库中。它们不能反写成书中事实；一次观察也不能自动升级为可跨品种、加工状态、原料批次或使用场景复用的规律。
