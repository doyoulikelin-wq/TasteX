# TasteX harness 使用说明

## 它执行什么

TasteX 是本地、确定性的“证据→试验→观察记录”执行框架。Agent 阅读来源与已有经验，编写有依据的研究 brief；框架检查并运行该 brief。它不调用模型服务，不自动生成供应商配料，不从书中圆点预测成品评分。

三个不同层次：来源数据库描述被提取的证据；运行目录保存某次研究与实验设计；经验数据库保存真实观察。界面的香气类别相似度也不是味觉强度、喜欢程度或配方成功率。

## 新案例

复制 `cases/kiwi-jerky/brief.json`，修改 case_id/revision、基质、目标、食材状态和路线。所有设计量的分母为 `design.basis_g` 克的指定基底；`sample_base_g` 是实际计划使用的基底量，不是样品总质量。完整样品质量会另算。别把原肉质量与干制后质量混用。

`targets.reference` 和 `acceptance` 未校准就保持 null。acceptance 的对象用于保存可阅读的验收约定，本版本不自动计算达标。`constraints.status` 与 `assumptions.status` 明示 confirmed/assumed/unresolved；通过 validate 表示结构一致，未解决的研究问题仍会显示。

每种材料必须且只能作为基底、一个因子或一个常量。因子至少两个水平；超过 512 种组合要拆成多个筛选阶段。一个运行选择一条路线；其余路线写明 alternative/deferred 和理由。加工路线不同，需独立设计，不能随意当同一种材料加量。

```sh
python3 -m tastex validate cases/kiwi-jerky/brief.json
python3 -m tastex run cases/kiwi-jerky/brief.json --out runs/kiwi-r2
```

自定义源库/别名使用全局参数，放在子命令之前：

```sh
python3 -m tastex --db flavor-database/flavor.sqlite --aliases configs/search_aliases.json run cases/kiwi-jerky/brief.json --out runs/custom
```

返回 JSON；错误输出到 stderr 并以非零退出，适合 agent 或脚本调用。不得忽略返回状态。

## 运行产物

| 文件 | 用途 |
|---|---|
| brief.json | 规范化完整输入，包括路线、状态、阈值未知与外部证据快照 |
| aliases.json | 本次实际采用的别名配置 |
| validation.json | 结构检查、警告及未解决研究条件 |
| evidence.json | 每次查询、全部分页/零结果、全部 profile 版本、属性/加工/页全文、直接配对与引用核对 |
| design.json | 全因子与对照、计划称量、盲码映射、预设对比、适用范围与局限 |
| report.md | 可阅读的需求、路线、检索覆盖、实验设计及回填说明 |
| tasting-sheet.md | 不含配方和食材名的盲码表，先自由描述再评分 |
| observation-template.json | 待填写的真实观察模板，实际重量和评分全部 null |
| events.jsonl | 固定阶段事件；没有假装真实制作的事件 |
| manifest.json | 输入与所有输出 SHA-256、代码指纹、运行 ID 与状态 |

数据保留在 JSON/数据库；MD 负责阅读，不用摘要覆盖来源。`retained_reference` 只证明引用内容被收录，不证明它支持剂量或产品结论。外部旧研究记录标记 `previous_research_not_refetched`，本次执行不联网更新文献。

## 完全重放和版本

```sh
python3 -m tastex verify-run runs/kiwi-r2
python3 -m tastex replay runs/kiwi-r2 --out runs/replay-r2
```

run_id 由规范化需求、规范化别名、数据库字节摘要、harness 代码指纹和版本共同决定。换输出目录不改变 run_id。输入/代码相同的所有受控产物须逐文件相同。输出目录存在就拒绝覆盖。

代码变化时旧运行仍能核验，但 replay 需要检出当时 Git 提交；用 `git log -- cases/.../example-run/manifest.json` 找到配套版本。不同 Python 版本的重现性在 CI 验证。没有存 Git 提交到 run_id，是为避免“提交包含自己的摘要”的循环。

校验只证明内容与清单一致；操作者能伪造清单或记录，哈希不是实物发生、来源科学正确性或人类身份认证。SQLite 查询可能随将来的库版本改变，所以数据库和代码都锁定；新的库生成新的运行。

## 经验如何影响下一轮

先从 `design.json` 读取 scope（基质、材料状态、工艺协议、食用情境），用 experience search 查完全匹配记录；如需参考相近条件必须显式 include-near，结果不会混成 exact。阅读失败与分歧、实际重量和批次，再在下一份 brief 的路线与参数 basis 中引用 observation_id/run_id，并解释迁移限制。

这一步是可审计的 agent 判断，本版没有自动训练推荐模型、自动学习阈值或自动把经验写成普遍规律。细节见 [EXPERIENCE.md](EXPERIENCE.md)。真实经验存储和追加记录的内容必须由实际制作与评价提供。

## 检查范围

- `doctor`：原库指纹、SQLite 结构完整性和外键。
- `scripts/verify_database.py`：源库与内嵌 JSON、资产、manifest 的一致性；不需要原 PDF。
- `tests/`：别名召回、零结果、分页、完整语义、因子设计、跨基质、经验纠错、伪造输入拒绝、完全重放。
- 旧 API/界面测试：完整 profile、unknown/conflict、相似度范围和加工索引。

原始 PDF 人工提取审查与成品真实试吃属于不同验证，不能用软件测试替代。源数据范围见 [DATA_SCOPE.md](DATA_SCOPE.md)。
