# TasteX

从风味证据到可复验小试的本地 agent harness。完整保存来源、食材状态、冲突、未知和加工条件，把候选方案、试验计划与真实观察分开。

**当前版本完成的是可运行的研究与试验工作流，尚无真实试吃结果，也没有经过验证的感官预测模型。** 猕猴桃微辣瘦牛肉干是第一个研究案例；草莓酸奶是跨基质的软件回归用例。

## 快速开始

需要 Python 3.10+、Git 和 Git LFS。核心 harness 只使用 Python 标准库，不需要 API key、云端服务或模型订阅。

```sh
git clone https://github.com/doyoulikelin-wq/TasteX.git
cd TasteX
git lfs install
git lfs pull
python3 -m tastex doctor
python3 -m tastex run cases/kiwi-jerky/brief.json --out runs/kiwi-r2
python3 -m tastex replay runs/kiwi-r2 --out runs/kiwi-r2-replay
```

先阅读生成的 `runs/kiwi-r2/report.md`。完整证据在 `evidence.json`，全因子配方、盲码和比较式在 `design.json`，试吃者仅使用 `tasting-sheet.md`。不要提前让试吃者看解码表。

数据库约 148 MiB、离线单文件 HTML 约 60 MiB，通过 Git LFS 管理。GitHub 的普通 ZIP 下载或跳过 LFS 的 clone 可能只有指针文件；`doctor` 会识别这种情况。正常运行从仓库根目录启动，不需要安装。可选 `pip install -e .` 添加 `tastex` 命令；这不是包含完整数据库的独立 wheel。

## 工作流

```mermaid
flowchart LR
    A[需求与显式未知] --> B[别名、身份与加工状态]
    B --> C[结构化记录 + 全文 + 直接配对]
    C --> D[比较路线并标记参数依据]
    D --> E[全因子、对照、独立批次与盲码]
    E --> F[保存证据与可重放运行]
    F --> G[真实制作与试吃]
    G --> H[独立经验库追加观察和纠错]
    H --> I[按适用范围检索与复验]
    I --> A
```

Agent 负责阅读证据、写需求文件和解释候选路线；harness 执行结构检查、完整检索、确定性设计、记录核验及复放。路线理由来自显式输入，**程序不会根据香气圆点自动推算最佳克数，也不会自动把候选配方宣布为成功**。先读 [AGENTS.md](AGENTS.md) 与 [工作流说明](docs/HARNESS.md)。

已落实的改进：

- 需求拆成目标、硬约束、偏好、假设；甜感参照、保存要求等未知不擅自补成答案。
- 检索展开审查过的简繁体/中英文别名，同时查询结构化加工与完整书页，保存分页和零结果。
- 鲜果、果汁、果粉、品种与加工状态不自动合并；保留全部来源版本、冲突和 `null`。
- 直接配对保留方向，相关语境单列；没有直接记录不等于不相容，间接关系不升级为证据。
- 先比较供香路线，所有用量标记来自用户、来源或假设；引用保留可核对快照。
- 猕猴桃 R2：3 个果粉水平 × 2 个辣椒水平，加不润湿原样对照；7 单元 × 2 独立计划批次。
- 每次运行固定需求、数据库、配置和代码摘要；拒绝覆盖旧运行，支持逐文件完全复放。
- 经验独立存储，真实观察才可正常写入；失败、缺失和分歧保留，纠错追加，按条件与剂量分组。

详细对照和尚未完成的实证环节见 [改进审计](docs/IMPROVEMENTS.md)。

## 数据与界面

| 内容 | 数量 / 说明 |
|---|---|
| 食材身份 | 1,474 |
| 圆点来源行 / 单元格 | 10,439 / 146,146 |
| 配对来源行 | 9,490；包含教学行，不能全部作为推荐依据 |
| 属性证据 | 253 |
| 加工记录 | 176：书籍 163 + 文献 13 |
| 加工索引 | 方式、效果、食材三种索引 |
| 书页文本 | 392 页；全文保留在只读数据库 |
| 可核对的原始 JSON 快照 | 19 |
| 本地图像资产 | 1,475：1,474 个食材 SVG + 1 张生成的主视觉；SVG 为程序绘制示意图 |

源数据库保持原字节，SHA-256：`1db2c4700ce4e2fc4a05a51885f6efd0c5089be2a3655df9cdb685db296e9a6a`。

```sh
python3 scripts/verify_database.py
python3 -m http.server 4178 --bind 127.0.0.1
```

浏览器打开 [本地创作室](http://127.0.0.1:4178/flavor-studio/index.html)。也可直接打开 `flavor-studio/风味创作室.html` 离线使用。界面包含“按目标找原料、替换食材、组合新配方”和加工层三个索引；本次 harness 通过命令行调用，**没有把试验与经验录入接入旧界面**。

原 PDF 与原截图不在仓库；提取数据、来源审查说明、研究记录和图像资产均在本地内容中。[数据库接口](flavor-database/QUERY_EXAMPLES.md)、[数据范围与源快照](docs/DATA_SCOPE.md)、[来源与权利说明](NOTICE.md)。

## 经验与验证

```sh
# 只填写真实制作/试吃后得到的记录，模板中的 null 不是结果
python3 -m tastex experience --store local/experience.sqlite record observation.json --run runs/kiwi-r2
python3 -m tastex experience --store local/experience.sqlite verify
python3 -m tastex experience --store local/experience.sqlite analyze runs/kiwi-r2

# 软件与数据回归；测试中的合成评分只写到隔离临时目录
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s flavor-database/tests -p test_api.py -v
node flavor-studio/scripts/test_engine_full.cjs
node flavor-studio/scripts/test_processing.cjs
```

[经验库字段、查询与纠错](docs/EXPERIENCE.md) · [猕猴桃 R2 案例及历程](cases/kiwi-jerky/README.md) · [可复放示例报告](cases/kiwi-jerky/example-run/report.md) · [历史 R1](cases/kiwi-jerky/legacy-r1/猕猴桃微辣瘦牛肉干_配方与工作记录.md)。

GitHub Actions 验证 Python 3.10/3.13、数据库快照、检索与试验回归、经验规则、已发布案例复放及界面计算语义。软件检查通过证明实现满足这些检查，不能证明提取完全正确、真实风味达标或成品可长期保存。
