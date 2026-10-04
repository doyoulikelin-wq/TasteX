# 猕猴桃微辣瘦牛肉干 · KJ-001 R2

运行 ID：`run-22754ce0a9c10df438c890a4`。工作流版本：0.1.0。

**这是来源驱动的候选筛选与实验计划。尚未制作、试吃或验证风味效果。**

## 需求与交付范围

猕猴桃风味但是没有那么甜的肉干，带一点辣味，不希望苦或者腻。用户已确认采用瘦牛肉。

基质：ready_to_eat_lean_beef_jerky；当前阶段：screening_plan_not_made_or_tasted；目标场景：食用前调味、当餐小试；未验证保存性。

| 目标 | 意图 | 参照物 | 验收条件 |
|---|---|---|---|
| flavor_identity | 先自由描述，再评价猕猴桃辨识度 | 待校准 | 待校准 |
| sweetness | 没有那么甜；参照产品与可接受范围待用户实际比较 | 待校准 | 待校准 |
| pungency | 一点辣，保留水果辨识度 | 待校准 | 待校准 |
| bitterness | 不希望有苦味 | 待校准 | 待校准 |
| greasiness | 不希望油腻或挂口 | 待校准 | 待校准 |

## 候选路线比较

| 路线 | 状态 | 采用/暂缓理由 | 局限 |
|---|---|---|---|
| 路线 A：即食猕猴桃果肉粉食前附着 | selected_for_screening | 优先把水果加量与辣椒加量独立控制，使用现有原味肉干做小试；不让鲜果长时间腌制与赋香同时变化。选择依据是可检验性，并无更好吃的实测证明。 | 果粉不是鲜果，可能只有酸感而缺乏猕猴桃辨识度。；果粉增量同时改变天然糖、酸与固形物，不能视为只加香气。；附粉、掉粉、结团、挂口及10分钟后的变化未知；不能沿用基底货架期。 |
| 路线 B：受控果汁接触后再制成肉干 | deferred | 作为风味进入肉内部的候选路线，需另行研究肉干加工、酶作用和香气保持，不纳入此次食前附粉的同一因子试验。 | 果汁接触时间、温度和酶活与肉质耦合，过度嫩化风险不能从本库换算出通用操作量。；后续热加工会改变风味；不能把鲜果轮廓当成肉干成品。；需单独验证加工、含水终点与保存，不提供未验证的生肉制备参数。 |
| 路线 C：规格明确的猕猴桃风味配料后加 | alternative | 若实际果粉只有酸甜或粉感，另行筛查供应商风味配料；本路线目前没有确定产品和匹配实测数据。 | 尚未选品，载体中的糖、油、溶剂及实际果香未知，不能假定无甜感或无油腻。；是否接受这种配料、名称标示、价格和采购可行性待确认。；数据库鲜果/配对证据不验证该商业材料，不能沿用果粉3/5 g剂量。 |

所有参数原始来由保存在 brief.json：user/source/hypothesis 分列。路线理由是显式输入，本工具不把书中类别标记换成最优克数。

## 检索记录与证据边界

完整输入、所有命中和零结果、全部来源版本及页文本保存在 evidence.json；报告不以摘要替代原始证据。

| 材料 | 请求状态 | 参照身份 | 状态关系 |
|---|---|---|---|
| 可即食原味瘦牛肉干 | 可即食原味瘦牛肉干 | ing-70099ea01925 | different_state |
| 可即食猕猴桃果肉冻干粉 | 可即食猕猴桃果肉冻干粉 | ing-f9bfb14ffe98 | different_state |
| 可即食低辣非烟熏红辣椒粉 | 低辣非烟熏红辣椒粉，实际即食处理规格待核实 | ing-e4fa8473e829 | unresolved |
| 饮用水 | 饮用水 | 未映射 | unresolved |

实际检索覆盖（命中数不代表独立研究数或证据强度）：

| 材料键 | 来源圆点行 / 版本 | 属性记录 | 结构化加工记录 | 全文命中页 |
|---|---|---|---|---|
| base | 11 / 1 | 1 | 2 | 118 |
| kiwi | 24 / 2 | 4 | 0 | 29 |
| chili | 7 / 3 | 6 | 4 | 168 |
| water | 0 / 0 | 0 | 1 | 0 |

当前材料参照 ID 之间的直接配对查询：

- base × kiwi：0 条；未命中仍是未知，不等于不相容。所有命中保留原始方向。
- base × chili：0 条；未命中仍是未知，不等于不相容。所有命中保留原始方向。
- kiwi × chili：0 条；未命中仍是未知，不等于不相容。所有命中保留原始方向。

路线引用核对：

- `rte-powder-postcoat` → `E0001`：retained_reference。
- `rte-powder-postcoat` → `E0002`：retained_reference。
- `rte-powder-postcoat` → `E0003`：retained_reference。
- `rte-powder-postcoat` → `E0004`：retained_reference。
- `rte-powder-postcoat` → `book_pages:43`：retained_reference。
- `rte-powder-postcoat` → `E0105`：retained_reference。
- `rte-powder-postcoat` → `E0106`：unresolved_reference。
- `rte-powder-postcoat` → `p044_t01_r04`：retained_reference。
- `rte-powder-postcoat` → `legacy-r1/evidence/external_references.json:EXT-03`：retained_reference。
- `controlled-juice-before-drying` → `book_pages:43`：retained_reference。
- `controlled-juice-before-drying` → `legacy-r1/evidence/external_references.json:EXT-02`：retained_reference。
- `controlled-juice-before-drying` → `legacy-r1/evidence/external_references.json:EXT-03`：retained_reference。

页面命中只表示文字出现，不证明该页的每个图表都以此食材为主体。跨加工状态、相关语境和间接配对不升级成成品实测。

检索发现的缺口：

- {"ingredient_key": "base", "kind": "state_or_identity_transfer_unvalidated", "reference_id": "ing-70099ea01925", "requested_state": "可即食原味瘦牛肉干", "identity_relation": "different_state", "detail": "Source reference does not validate the actual ingredient batch, requested processing state, flavor intensity or dosage."}
- {"ingredient_key": "kiwi", "kind": "no_structured_processing", "page_hit_count": 29, "detail": "Structured processing retrieval has zero hits. Page text was still searched in full; absence in the processing layer cannot rule out source discussion."}
- {"ingredient_key": "kiwi", "kind": "state_or_identity_transfer_unvalidated", "reference_id": "ing-f9bfb14ffe98", "requested_state": "可即食猕猴桃果肉冻干粉", "identity_relation": "different_state", "detail": "Source reference does not validate the actual ingredient batch, requested processing state, flavor intensity or dosage."}
- {"ingredient_key": "kiwi", "kind": "profile_uncertainty", "categories": [{"category_index": 6, "display_name": "焦糖", "status": "conflict", "unknown_count": 0, "has_unknown": false}, {"category_index": 9, "display_name": "木质", "status": "conflict", "unknown_count": 0, "has_unknown": false}], "detail": "Conflicts and unknowns are retained together; do not average or fill them."}
- {"ingredient_key": "chili", "kind": "state_or_identity_transfer_unvalidated", "reference_id": "ing-e4fa8473e829", "requested_state": "低辣非烟熏红辣椒粉，实际即食处理规格待核实", "identity_relation": "unresolved", "detail": "Source reference does not validate the actual ingredient batch, requested processing state, flavor intensity or dosage."}
- {"ingredient_key": "chili", "kind": "profile_uncertainty", "categories": [{"category_index": 2, "display_name": "花卉", "status": "conflict", "unknown_count": 0, "has_unknown": false}, {"category_index": 4, "display_name": "草本", "status": "conflict", "unknown_count": 0, "has_unknown": false}, {"category_index": 6, "display_name": "焦糖", "status": "conflict", "unknown_count": 0, "has_unknown": false}, {"category_index": 7, "display_name": "烘烤", "status": "conflict", "unknown_count": 0, "has_unknown": false}, {"category_index": 9, "display_name": "木质", "status": "conflict", "unknown_count": 0, "has_unknown": false}], "detail": "Conflicts and unknowns are retained together; do not average or fill them."}
- {"ingredient_key": "water", "kind": "no_ingredient_search_hits", "detail": "No identity matches in this search; absence of evidence is not evidence of absence."}
- {"ingredient_key": "water", "kind": "unresolved_reference", "detail": "No source ID selected; candidates are not silently treated as the requested material."}
- {"ingredient_key": "water", "kind": "state_or_identity_transfer_unvalidated", "reference_id": null, "requested_state": "饮用水", "identity_relation": "unresolved", "detail": "Source reference does not validate the actual ingredient batch, requested processing state, flavor intensity or dosage."}
- {"ingredient_keys": ["base", "kiwi"], "kind": "no_direct_pair_evidence", "reference_ids": ["ing-70099ea01925", "ing-f9bfb14ffe98"], "detail": "No direct source row found for these exact IDs. Other varieties, states or indirect paths do not establish this pair."}
- {"ingredient_keys": ["base", "chili"], "kind": "no_direct_pair_evidence", "reference_ids": ["ing-70099ea01925", "ing-e4fa8473e829"], "detail": "No direct source row found for these exact IDs. Other varieties, states or indirect paths do not establish this pair."}
- {"ingredient_keys": ["kiwi", "chili"], "kind": "no_direct_pair_evidence", "reference_ids": ["ing-f9bfb14ffe98", "ing-e4fa8473e829"], "detail": "No direct source row found for these exact IDs. Other varieties, states or indirect paths do not establish this pair."}
- {"kind": "unresolved_route_reference", "route_id": "rte-powder-postcoat", "reference": "E0106", "meaning": "Not retained in this evidence bundle; cannot count as checked support."}

## 因子试验与对照

所有设计量以 100 g 制好的基底为分母；每单元使用 50 g 基底。

计划 7 个单元、2 个独立制备批次；实际制作记录尚为空。

| 单元 | 类型 | 计划称量 g |
|---|---|---|
| cell-09f61f10fded | factorial | {"base": 50.0, "chili": 0.0, "kiwi": 0.0, "water": 0.5} |
| cell-a83702147ad1 | factorial | {"base": 50.0, "chili": 0.05, "kiwi": 0.0, "water": 0.5} |
| cell-9f7defee81e7 | factorial | {"base": 50.0, "chili": 0.0, "kiwi": 1.5, "water": 0.5} |
| cell-e783d28796d6 | factorial | {"base": 50.0, "chili": 0.05, "kiwi": 1.5, "water": 0.5} |
| cell-ff2ea3e57334 | factorial | {"base": 50.0, "chili": 0.0, "kiwi": 2.5, "water": 0.5} |
| cell-e4062d7b651b | factorial | {"base": 50.0, "chili": 0.05, "kiwi": 2.5, "water": 0.5} |
| cell-94f7655ea828 | native_control | {"base": 50.0, "chili": 0.0, "kiwi": 0.0, "water": 0.0} |

随机盲码与呈样顺序由指定 seed 生成。设计者保留 design.json 的解码表；试吃者使用 tasting-sheet.md，避免提前看配方。

预设比较：

- {"id": "contrast-001", "kind": "simple_factor_effect", "question": "在其他配料水平相同时，kiwi 从 0 g 增至 3 g / 基准份，对各评分的差异是什么？", "factor": "kiwi", "from_g_per_basis": 0, "to_g_per_basis": 3, "held_factors_g_per_basis": {"chili": 0}, "terms": [{"cell_id": "cell-9f7defee81e7", "weight": 1}, {"cell_id": "cell-09f61f10fded", "weight": -1}], "estimated_value": null}
- {"id": "contrast-002", "kind": "simple_factor_effect", "question": "在其他配料水平相同时，kiwi 从 0 g 增至 5 g / 基准份，对各评分的差异是什么？", "factor": "kiwi", "from_g_per_basis": 0, "to_g_per_basis": 5, "held_factors_g_per_basis": {"chili": 0}, "terms": [{"cell_id": "cell-ff2ea3e57334", "weight": 1}, {"cell_id": "cell-09f61f10fded", "weight": -1}], "estimated_value": null}
- {"id": "contrast-003", "kind": "simple_factor_effect", "question": "在其他配料水平相同时，kiwi 从 0 g 增至 3 g / 基准份，对各评分的差异是什么？", "factor": "kiwi", "from_g_per_basis": 0, "to_g_per_basis": 3, "held_factors_g_per_basis": {"chili": 0.1}, "terms": [{"cell_id": "cell-e783d28796d6", "weight": 1}, {"cell_id": "cell-a83702147ad1", "weight": -1}], "estimated_value": null}
- {"id": "contrast-004", "kind": "simple_factor_effect", "question": "在其他配料水平相同时，kiwi 从 0 g 增至 5 g / 基准份，对各评分的差异是什么？", "factor": "kiwi", "from_g_per_basis": 0, "to_g_per_basis": 5, "held_factors_g_per_basis": {"chili": 0.1}, "terms": [{"cell_id": "cell-e4062d7b651b", "weight": 1}, {"cell_id": "cell-a83702147ad1", "weight": -1}], "estimated_value": null}
- {"id": "contrast-005", "kind": "simple_factor_effect", "question": "在其他配料水平相同时，chili 从 0 g 增至 0.1 g / 基准份，对各评分的差异是什么？", "factor": "chili", "from_g_per_basis": 0, "to_g_per_basis": 0.1, "held_factors_g_per_basis": {"kiwi": 0}, "terms": [{"cell_id": "cell-a83702147ad1", "weight": 1}, {"cell_id": "cell-09f61f10fded", "weight": -1}], "estimated_value": null}
- {"id": "contrast-006", "kind": "simple_factor_effect", "question": "在其他配料水平相同时，chili 从 0 g 增至 0.1 g / 基准份，对各评分的差异是什么？", "factor": "chili", "from_g_per_basis": 0, "to_g_per_basis": 0.1, "held_factors_g_per_basis": {"kiwi": 3}, "terms": [{"cell_id": "cell-e783d28796d6", "weight": 1}, {"cell_id": "cell-9f7defee81e7", "weight": -1}], "estimated_value": null}
- {"id": "contrast-007", "kind": "simple_factor_effect", "question": "在其他配料水平相同时，chili 从 0 g 增至 0.1 g / 基准份，对各评分的差异是什么？", "factor": "chili", "from_g_per_basis": 0, "to_g_per_basis": 0.1, "held_factors_g_per_basis": {"kiwi": 5}, "terms": [{"cell_id": "cell-e4062d7b651b", "weight": 1}, {"cell_id": "cell-ff2ea3e57334", "weight": -1}], "estimated_value": null}
- {"id": "contrast-008", "kind": "factorial_difference_in_differences", "question": "kiwi 的高低水平差异是否随 chili 的水平改变？", "factors": ["kiwi", "chili"], "terms": [{"cell_id": "cell-e783d28796d6", "weight": 1}, {"cell_id": "cell-a83702147ad1", "weight": -1}, {"cell_id": "cell-9f7defee81e7", "weight": -1}, {"cell_id": "cell-09f61f10fded", "weight": 1}], "held_factors_g_per_basis": {}, "interpretation": "同一评分尺度的差中之差；待有配对观察才估计，不是已证实的协同/掩盖机制。", "estimated_value": null}
- {"id": "contrast-009", "kind": "factorial_difference_in_differences", "question": "kiwi 的高低水平差异是否随 chili 的水平改变？", "factors": ["kiwi", "chili"], "terms": [{"cell_id": "cell-e4062d7b651b", "weight": 1}, {"cell_id": "cell-a83702147ad1", "weight": -1}, {"cell_id": "cell-ff2ea3e57334", "weight": -1}, {"cell_id": "cell-09f61f10fded", "weight": 1}], "held_factors_g_per_basis": {}, "interpretation": "同一评分尺度的差中之差；待有配对观察才估计，不是已证实的协同/掩盖机制。", "estimated_value": null}
- {"id": "contrast-010", "kind": "native_vs_constants_control", "question": "仅添加固定配料并执行相应处理，相比原样基底有何差异？", "changed_constant_masses_g_per_basis": {"water": 1}, "terms": [{"cell_id": "cell-09f61f10fded", "weight": 1}, {"cell_id": "cell-94f7655ea828", "weight": -1}], "interpretation": "若固定配料只有水，可估计此润湿处理的整体差异；不推广为独立水活度、保存期或分子机制。", "estimated_value": null}

解释范围：

- 仅在同一批次、同一试吃者、相同维度且所需样品评分齐全时计算对比；未评分保持 null。
- 将每个制备批次的对比单独报告，再查看重复方向；不把多人评分或多口试吃当成独立制备批次。
- 原料批次或状态改变时需记录适用范围；剂量改变会同时改变糖、酸、固形物等，不能归因为纯香气效应。
- 两批小试不足以确认人群偏好、统计显著性、分子机制、货架期或商品化稳定性。
- 未指定目标参照或接受线时只能报告观察和用户选择，不能自动宣布符合全部用户目标。
- 每样50 g基底：沿用R1规模，降低相对称量误差并留出多人分样；不表示每人必须吃完50 g。每批7样350 g基底，两批共700 g。
- 使用相同肉干及粉料批次完成第一轮两次独立制备；每份按计划称量并记录实际读数、原料lot、操作者和时间，不能从计划自动填实际。
- 辣椒最小计划0.05 g/样，需核实秤在该量级的可用性。显示0.01 g分度不等于准确；若称量不可靠则整样等比例放大并记录，不能用猕猴桃预混粉制作无果粉的独立辣椒组。
- 原样对照不加水或粉；六个因子样均加0.50 g水；容器、肉干块尺寸和试吃温度尽量一致并记录。
- 只使用明确适合即食的材料，先检查基底与单料状态；后加不加热。现拌当餐试吃，不能沿用原肉干常温保存期。
- 统一拌后10分钟观察并记录实际经过时间、附粉损耗、结团和掉粉；本轮不改变这些条件作为新的因子。
- 制样者保管design中的盲码映射，试吃者仅看盲评表；按每批随机顺序呈样，先自由描述再告知风味目标。
- 样间饮水清口并等待前一样辣感消退；可分两次会话，记录参与者/会话与实际顺序。两批随机顺序并不等于完全顺序平衡。
- 0–10为记录尺度：强度项0无10极强；flavor_identity为0不能辨认10非常清楚；chew_hardness为0很软10很硬；overall_fit为0完全不合目标10完全符合。无数据留null，不设置虚构及格线。
- 甜感参照、实际原料标签与保存目标未定时，继续小试设计但不宣布产品达标或可商品化。

## 未解决条件

- `product.storage_requirement`：No storage or shelf-life claim can be made.
- `targets[0].reference`：Preference needs user calibration; do not invent a pass threshold.
- `targets[0].acceptance`：Preference needs user calibration; do not invent a pass threshold.
- `targets[1].reference`：Preference needs user calibration; do not invent a pass threshold.
- `targets[1].acceptance`：Preference needs user calibration; do not invent a pass threshold.
- `targets[2].reference`：Preference needs user calibration; do not invent a pass threshold.
- `targets[2].acceptance`：Preference needs user calibration; do not invent a pass threshold.
- `targets[3].reference`：Preference needs user calibration; do not invent a pass threshold.
- `targets[3].acceptance`：Preference needs user calibration; do not invent a pass threshold.
- `targets[4].reference`：Preference needs user calibration; do not invent a pass threshold.
- `targets[4].acceptance`：Preference needs user calibration; do not invent a pass threshold.
- `ingredients[0]`：Requested material is not asserted to equal the source ingredient state.
- `ingredients[1]`：Requested material is not asserted to equal the source ingredient state.
- `ingredients[2]`：Requested material is not asserted to equal the source ingredient state.
- `ingredients[3]`：Requested material is not asserted to equal the source ingredient state.
- `constraints[3]`：本轮不额外添加糖、甜味剂或油，保留基底和果粉天然糖/脂肪未知；不作低糖声称
- `constraints[4]`：本后加路线要求肉干和粉料均明确适合直接食用
- `constraints[5]`：是否需要常温保存、保存时长及包装未指定；本轮仅当餐小试
- `assumptions[0]`：保留实际评分与用户选择，不宣称甜度降低百分比或达标。
- `assumptions[1]`：记录咀嚼硬度、粉感与自由描述，不能自动优化质地。
- `assumptions[2]`：制样前记录并试吃基底；基底存在苦或腻时不能把缺陷归因给果粉。
- `assumptions[3]`：鲜果证据不能等同果粉；所有结论只限实际批次与该处理。
- `assumptions[4]`：0.10 g/100 g 不保证微辣；记录实际称量，不从书中辣椒范围换算成品SHU。
- `assumptions[5]`：试吃前按参与者实际情况确认原料适用；不由数据库推断适合所有人。
- `assumptions[6]`：只是筛选观察窗口，不是酶作用、保香或保存的最佳时间。
- `assumptions[7]`：可初查制备重复性；换原料批次的迁移性尚未检验。
- 所有配料克数是筛选设计，不是实称值、最佳比例或感官预测。
- 随机呈样降低固定顺序偏差，但没有实现完整顺序平衡，也不能消除前样味觉残留和提示效应。
- 盲码映射含配方身份，应由制样者保管；自行制样者不能视为完全盲评。
- 不同批次应独立称量制备；同一锅分装或同一样重复评分不构成独立制备批次。
- 静置 10 分钟是统一待观察条件，未证明为最优处理时间。
- 包含小于 0.1 g 的配料：显示分度不等于称量准确度；记录校验和实际读数，设备不能可靠称量时等比例放大整样。

## 经验回填与复验

1. 保留原料批次、实际称量、制备批次、匿名试吃者、自由描述和每项评分。未知仍填 null。
2. 复制 observation-template.json，填写真实结果后用 experience record 追加到独立经验库；不要把模板当结果导入。
3. 成功、失败和意见分歧都保留；纠错用 supersedes 追加，旧记录不覆盖。
4. 默认只查询完全匹配的基质/材料状态/工艺/食用情境。相近情境仅作参考，不能自动迁移剂量或结论。
5. 重复制备、不同批次和不同试吃者分别计数；单次评价不升级为普遍规则。

manifest.json 和 events.jsonl 记录输入摘要及确定性步骤；用 replay 重放并比较文件摘要。哈希一致说明输入与记录一致，不证明真实发生了试吃。
