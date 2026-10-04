# 经验库：真实观察、纠错与配对分析

TasteX 的来源数据库回答“已有文献和书中记录了什么”，经验库回答“我们在指定条件下实际观察到了什么”。两者使用不同的 SQLite 文件：

- `flavor-database/flavor.sqlite`：来源证据，只读。
- `local/experience.sqlite`：本地观察事件账本；首次使用时创建，默认不提交到 Git。

本仓库尚没有用户实际试吃结果。案例、配方比例、盲码表和全为 `null` 的评分模板都不是经验。单元测试的数据仅存在于系统临时目录，不会导入真实经验库。

## 从一轮小试到一条观察

1. 运行一个 brief，保留完整的 run 目录。
2. 制样者按 `design.json` 备料并保管盲码映射；试吃者使用 `tasting-sheet.md`，不要提前看到配方表。
3. 复制该 run 的 `observation-template.json`，填写**实际**批次、样品、匿名参与者 ID、时间、原料批号、实称重量与评分。每个参与者对每个批次的每个样品生成一个唯一 `observation_id`。
4. 导入观察。只有通过来源、范围、原料和数值校验的数据才能进入经验库。
5. 查看原始观察、分组摘要及已计划的配对差异；记录失败和分歧，再决定下一轮 brief 如何修订。

例如先生成 run：

```bash
python3 -m tastex run cases/kiwi-jerky/brief.json --out runs/kiwi-r2
```

把填写完成的观察保存为 `local/tasting-001.json` 后：

```bash
python3 -m tastex experience record local/tasting-001.json --run runs/kiwi-r2
python3 -m tastex experience verify
python3 -m tastex experience summarize --scope '{}'
python3 -m tastex experience analyze runs/kiwi-r2
```

这些命令不会替你产生试吃结果。尚未填写的模板应被拒绝。已存在的 run 不覆盖；修改需求、配方、操作或来源后，生成另一版本的 run。

## 必填内容及其含义

字段格式见 [`schemas/observation.schema.json`](../schemas/observation.schema.json)，动态业务校验由 `ExperienceStore.record()` 执行。

| 字段 | 记录要求 |
|---|---|
| `case_id / revision / run_id` | 与该 run 的 manifest、brief 和模板完全一致；不要自己推测或改写。 |
| `observation_id` | 此次记录的稳定、唯一 ID。相同 ID 的相同内容可重复提交；内容变化必须使用新 ID 纠错。 |
| `batch_id / cell_id` | 必须存在于该 run 的设计里，且该批次包含此样品。批次是独立制样批次，不是“第几位试吃者”。 |
| `participant_id` | 使用稳定匿名 ID；同一人跨样品沿用该 ID，便于配对。没有必要保存姓名、联系方式或健康资料。 |
| `observed_at` | 实际试吃时间，ISO 8601 且带时区，例如 `2026-10-05T15:30:00+08:00`。 |
| `scope` | 四个字符串：`matrix`、`ingredient_state`、`process`、`serving_context`，完整复制对应模板。`process` 可能本身是一段规范化 JSON 字符串，不应手动缩成一个菜名。 |
| `actual_masses_g` | 对应样品所有配料键都要填写，包括 `0`；必须是有限、非负实数，基底大于 `0`。它与计划称量分开，不自动抄计划值。 |
| `material_lots` | 每种实际用量大于 `0` 的原料必须填写真实批号或可追溯的自建批次 ID。未使用的配料可以不写批号或保留 `null`，不能用“待填”冒充已知。 |
| `ratings` | 设计中每个维度都要出现。评分为 `0..10` 的有限数值；未评写 `null`。`0` 是实际评分，不是缺失值。 |
| `free_description` | 自由描述，最好先于提示水果名称的辨识评分记录；没有描述可用空字符串。 |
| `disposition` | `acceptable / reject / mixed / not_evaluated`。它是此人的结论声明，不代表已满足所有需求。 |
| `notes` | 记录偏离、设备限制、实际时间与温度、操作者、会话条件及解释；没有内容可用空字符串。 |
| `origin` | 正常使用必须为 `human_observed`；这是一项来源声明，并不构成独立核验。 |
| `supersedes` | 正常新记录为 `null`；更正时填写被更正的当前观察 ID。 |

同一个已制样样品分给多人品评时，各记录应引用同一制样批次及其原料批号、配方实称量；不要把每人的入口份量误填成整样配方称量。若各人收到的是不同制样或不同配方，应分别记录。

暂未结构化的条件包括**实际**预处理温度、静置时间、制样操作者、试吃会话、清口间隔、设备校准和基底批次脂肪/盐/水分测量。目前它们需写进 `notes`。计划工艺会进入 scope，但计划值不等于实际执行值。因此，`exact` 只表示已记录字段精确匹配，不证明所有未记录条件相同。

## 导入校验

`record()` 在 Python 和 CLI 中共用 `workflow.verify_run()`，检查必需文件、全部 manifest artifact SHA-256、输入摘要、brief 合法性和 run 的内容派生 ID。随后额外检查：

- 观察关联的 run、版本和四维 scope 与模板一致。
- 样品与批次存在；配料键与设计一致；实称重量、原料批号和所有评分维度完整。
- 数字有限、评分在 `0..10`；`true` 不被当成 `1`；常见占位内容会被拒绝。
- 无绝对路径、路径穿越或符号链接的 artifact；未知字段不会悄悄被丢弃。
- 正常经验库不接受 `synthetic_test`；合成示范 run 也不能改个标签伪装成真实观察。
- 已有其他类型的数据库不能作为经验库打开，避免误写来源库。

计划用量与实称量不一致**可以如实记录**，返回 `mass_deviations_g`。保留偏离有利于追溯，不能因此自动认为该记录仍满足计划对比条件。

记录保存 run manifest 摘要、源数据库 SHA-256 引用和 artifact 摘要。此处不重新读取源数据库实物；用 `python3 -m tastex doctor` 检查仓库中的来源库。需要重放旧 run 时，还必须保有对应版本的原始来源库、别名配置及工作流实现。

## 追加、幂等与纠错

经验库中的事件禁止 `UPDATE` 与 `DELETE`。提交相同 ID、内容和来源摘要返回 `already_recorded`，不会增加样本数；相同 ID 内容不同则拒绝。

若发现录入错误，复制当前记录，设置新 `observation_id`，填写 `supersedes`，修正字段并在 `notes` 说明原因。纠错必须指向同一 run、版本、批次、样品、参与者和 scope 的当前记录；不能把甲的试吃改为乙的试吃，也不能把旧 run 的结果搬到新配方。已经被更正的旧版本不能再分叉更正。

搜索和摘要默认仅返回未被更正的当前记录，但旧记录及其摘要始终保留。每个 run × batch × cell × participant × origin 只允许一条当前观察；再试吃应使用新的计划批次/run，不能用多个 ID 人为增加重复数。

每个事件的 SHA-256 覆盖序号、观察全文、来源、前一事件摘要。`verify()` 检查链条与索引字段一致性。**哈希链证明记录的内部一致性，不证明真实进行了试吃，也不能在没有外部可信链头的情况下防止拥有文件控制权的人重写整条链或截短末尾。** 可定期把 `verify()` 的 `head_sha256` 另存于经过审阅的实验报告，作为外部对照。

## 搜索：精确范围与邻近案例

```python
import json
from pathlib import Path
from tastex.experience import ExperienceStore

run = Path("runs/kiwi-r2")
scope = json.loads((run / "observation-template.json").read_text())["scope"]

with ExperienceStore("local/experience.sqlite") as store:
    exact = store.search(scope)
    neighbors = store.search(scope, include_near=True)
    summary = store.summarize(scope)
    contrasts = store.analyze(run)
```

搜索按提供的每个字段精确比较，默认没有别名替换、状态推广、剂量合并或模糊匹配。可用四维 scope，也可用 `case_id`、`revision`、`run_id`、`batch_id`、`cell_id`、`participant_id` 缩小范围。`{}` 列出所有当前真人来源声明记录，并返回 `scope_is_complete: false`。

仅显式指定 `include_near=True` 才返回**至少有一个查询字段相同、又至少有一个字段不同**的邻近条目。它们位于单独的 `near` 数组，附上 `mismatched_fields`；不进入精确摘要。邻近案例可提示新问题，不能自动作为当前配方效果的支持。

## 摘要：不把不同配方混成一条经验

`summarize()` 按完整 scope、run、cell、计划配方和**实际称量**分组。即使“牛肉干＋猕猴桃”的文字相同，不同剂量、run、样品或称量偏差都不会被池化成一个平均“猕猴桃效果”。

每组返回：

- 观察数、参与者数、`run_id + batch_id` 的批次数；同批多人仍只算一批。
- 每个评分的原始值、缺失数、最小值、最大值和范围。
- 接受/拒绝分歧、自由描述、原料批号组合及称量偏差。
- `no_numeric_ratings`：有记录但没有数值评分。
- `observed_one_batch`：只有一批出现数值评分。
- `repeated_not_generalized`：至少两批出现评分，**不等于两批都成功或证明普适规律**。

空库返回 `no_observations`，不会根据设计自动填分。摘要保留原料批号组合，但**没有按批号拆分所有条件组**；批号变化、非结构化的时间/操作者/会话差异仍需检查。标签“多批”也依赖使用者诚实、正确地定义批次，不构成独立制备的外部证明。

## 计划对比：有完整配对才计算

`analyze(run_dir)` 读取该 run 的 `design.contrasts[].terms`，按权重计算预先声明的差异。例如两个样品之差或四样品的差中之差。它只使用：

1. 此 run、此 manifest 版本的当前 `human_observed` 记录。
2. **同一批次、同一参与者**对所有必需样品的评分。
3. 各配料实称相对计划为同一倍数，且整个对比各样品采用相同倍数；计划为零的原料实际也为零。
4. 各样品共同使用的原料批号一致。
5. 此评分维度全部有值；其他维度缺失不会被补零。

不满足条件时该差异是 `null`，并给出缺失样品、缺失评分、配方比例偏离、批号改变等原因。程序既不自动挑选重复评分，也不把不同参与者的两个样品拼成一对。数值允许的 `1e-9` 相对/`1e-12` 绝对误差只处理浮点运算，**不是秤的精度容差**。

输出按批次、参与者、对比分开，附原观察 ID 和时间。实际时间、操作者、会话条件目前仍不自动匹配；必须审阅 notes。全配方等倍放大保持配料比例，但不保证混合几何或香气释放相同。

得到一个非零差中之差，只说明这组配对评分呈现相应数值差异，不是已证实的分子协同、显著性、人群偏好、保存性或产品成功。尚未确认的“微辣”“不太甜”接受线也不会被程序自动发明。

## 如何积累、复用而不制造规律

新一轮先查相同 scope 与配方；同时读失败、分歧和缺失项，再决定是否扩大查看邻近案例。把因此改变的设计和理由写入新 brief/run，而不是覆盖原案例。先用配对结果选择下一轮候选，再通过独立批次、实际原料和目标用户的重复观察扩大适用范围。

v1 已实现可检索的观察积累、纠错、分组摘要和受条件约束的配对计算；**没有实现自动学习一套普适感官预测模型**。批次组数不等于效应可靠度，测试覆盖率也不等于配方成功率。

## 测试模式

`ExperienceStore(path, allow_synthetic=True)` 只允许系统临时目录下的独立数据库或 `:memory:`。即使在该模式下写入 `synthetic_test`，`search()`、`summarize()`、`analyze()` 也默认排除它，不会混入真人经验。普通 CLI 不提供打开合成写入模式的开关。

```bash
python3 -m unittest discover -s tests -p test_experience.py -v
```

测试覆盖空库、来源篡改、路径越界、源库误写防护、未知值、量纲范围、材料批号、纠错分支、跨 run 误配、合成隔离、多参与者/多批次区分，以及配对差异计算与拒算条件。单元测试中的虚构真人标签只用于验证默认分支，明确标记为临时测试 fixture，不写入交付经验库。
