# CPMCM 2026 D 无人机运输与通信协同优化

赛题、原始 Excel、DEM 是输入事实来源；`src/core/` 统一距离、地形、时间、载荷、能耗、充电和资源检查。仓库保持私有。

本轮依据用户提供的 WJ数模截图，冻结 Q1，新增架次列生成、时间索引整数模型和区间资源着色，重新组批 Q2/Q3；三点分时中继同时计入返航、周转与再出航。结果、方法异同及证明边界见 [对标审计](docs/external_benchmark_algorithm_audit.md)。所有正式数据从官方输入重算，有限目录/网格下界不称为原题全局证书。

## 安装与数据

支持 Python 3.11 / 3.12，建议建立虚拟环境：

```bash
python -m venv .venv
# Linux / Codespaces: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

将官方 D 题 ZIP **完整解压到 `data/raw/`**，保留其子目录和原文件名。程序递归定位文件，也兼容 `#Uxxxx` 中文文件名；遇到重名输入会报错，避免随机选择不同版本。

必需输入为五个官方参数工作簿及 `30米DEM.tif`；赛题、DEM MAT、地理文件与官方模板请保留。原始文件默认不提交 Git。每个问题生成的 `input_manifest.json` 记录六个计算输入的 SHA-256，校验时检查输入版本。

```bash
python run_q1.py
python run_q2.py
python run_q3.py
python run_q4.py
python run_all.py
python -m pytest -q
```

也可以显式指定原始附件解压目录：

```bash
python run_all.py /path/to/D_problem_unpacked --out /path/to/output
python scripts/validate_results.py /path/to/D_problem_unpacked --results /path/to/output
```

`scripts/run_q1.py` 等旧入口仍保留，调用相同 CLI。`run_all` 在临时目录完成 Q1–Q4 和全量校验，全部成功后发布本次输出，失败时保留上一次完整结果。单独运行某一问题后，应重新运行受其影响的下游问题和总校验。

## 计算流程

| 问题 | 模型与输入 | 主要输出 |
|---|---|---|
| Q1 | 官方参数、DEM；单点往返能力与词典序集合划分 DP | 最大安全载荷、18 个批次、余量敏感性 |
| Q2 | 共享物理引擎；基准合并链 + 分组/路线/资源邻域搜索 | 选定方案、前沿 CSV、每个前沿方案的可重放 JSON、资源表 |
| Q3 | 官方通信与中继参数、外层离散搜索 + 内层 HiGHS LP | 联合时刻、逐箱交付、通信窗口、中继能耗与资源表 |
| Q4 | 固定 Q3 任务和通信关系、官方库存 | K=2 / K=3 分区与独立资源缺口 |

Q1 使用题目给定的计划速度，未引入风场。风速、顺逆风、侧风不是官方输入，也未用于调整正式结果。内部单位为 m、s、kg、m³、kWh、kW；只有输出小时、SOC 百分数及无线链路距离 km 时进行单位转换。

Q1 默认读取每个机型的官方返航余量；`python run_q1.py --rho 0.25` 才会统一覆盖所有机型。`Q1_metrics.json` 中 `reserve_fraction: null` 表示未覆盖，实际余量见 `reserve_by_type`。默认官方 A/B/C 均为 20%，所以本轮正式数值不变。

Q2 在全部按期子问题中归并可交换货箱，枚举单点/双点可行架次，建立同时约束无人机飞行和电池充电区间的时间索引模型。列生成定价遍历有限目录所有网格开始时刻，整数主问题生成方案，再用区间图着色恢复实体编号并压缩连续时序。默认20架次切片按延误、完工、能耗比较；`--target-trips 22` 可改选切片。合并链与变邻域保留为补充。`Q2_column_audit.json` 分开记录有限目录LP修正下界、受限MIP间隙、热启动重算与最终选择，不把这些下界扩展到未枚举路线。

Q3 保留旧离散初始构造及通信修复，并加入 `config/q3_column_seed.json` 的三点两机热启动和分时窗口列模型。粗空间筛选为5 s；每个完整候选必须通过1 s与0.5 s网格并集、硬截止、SOC、完整充电和中继周转校验，随后用条件LP优化连续时刻。一架中继负责长窗口，另一架返航O01、周转后前往后续点。运输架次内绑定一个悬停点是当前搜索限制，不能当成原题禁止单跳切换。19运输/3中继为可配置偏好，非最优性定理。

`config/search.json` 保存搜索预算与目标；种子20260924，Q2执行100000次基础邻域与10000次资源重排，Q3执行5000次邻域，列生成最多32轮、每个整数主问题最多75 s。`config/q2_column_seed.json` 与 `config/q3_column_seed.json` 是本次从官方数据求出的离散热启动，只含货箱、路线、资源顺序及中继位置，必须每次重算，不能读取历史时间/能耗作为答案。时间预算可能使新MIP候选随机器变化；受保护热启动保证保留可复核方案。Q4冻结最终Q3后重新穷举，输出分法计数、资源峰值和缺口分解。

通信保留逐阶段1 s与0.5 s两组非嵌套采样的并集，中继窗口前后各留 5 s。DEM 净空与视线共用像元闭边界遍历：边界两侧、角点相接的像元均纳入，采用较高地形的保守约定，不再对坐标取整缓存。**离散采样仍不构成连续时间通信的解析证明。** 建链时无人机已在空中，因此其悬停及通信能耗计入中继能耗。

## 项目结构

```text
config/q3_plan.json              可解释的离散初始解；须修复并重算，不含时刻/能耗结果
config/search.json               固定种子、迭代预算和邻域参数
src/config.py                   赛题规则、单位常数、算法参数
src/core/                       官方输入、模型、地形、物理、路线、约束、I/O、溯源
src/q1/physics_engine.py         单点能力与精确组批
src/q2/heuristic.py              初始可行构造
src/q2/tradeoff.py               原合并链种子、结果导出
src/q2/search.py                 分组/路线/资源邻域及 Pareto 档案
src/core/discrete.py             共享运输邻域与固定资源顺序的精确时刻
src/core/communication.py        双向链路预算、中继物理与通信状态采样
src/q3/communication.py          旧导入路径的兼容导出
src/q3/solver.py                 给定离散方案的 HiGHS 联合时序 LP
src/q3/preparation.py            真实物理与双网格通信预检、精确坐标缓存
src/q3/search.py                 运输/中继离散搜索与可行解保护
src/q4/partition.py              固定任务的分区枚举
src/validation.py               从官方数据重算结果
src/cli.py                      统一入口
run_q1.py … run_q4.py            单题入口
run_all.py                      全流程入口
scripts/                        兼容入口、校验、可选绘图
results/q1 … results/q4         当前生成结果
results/validation.json         最近一次成功的全量校验
archive/baseline-e668347/        原始 baseline 证据
config/ docs/ tests/            离散方案、说明、测试
```

## 测试与输出校验

```bash
python -m pytest -q
python -m ruff check --select F,E9 src scripts tests run_all.py run_q1.py run_q2.py run_q3.py run_q4.py
python scripts/validate_results.py
```

单元测试使用小型合成 DEM，覆盖物理边界、NoData、非法输入、路线卸货、资源占用、通信门限、CSV 篡改、CLI 导入和失败恢复。有官方数据时还执行跨问题物理一致性和参数读取测试；也可通过 `UAV_DATA_ROOT` 指定数据。CI 不含私人赛题附件，官方数据集成测试会明确 skip；全量真实数据运行已在本轮审计环境中完成。

校验器重算 Q1 航段、载荷和敏感性，Q2 所有保存的前沿计划及所选方案一致性，Q3 运输/中继能耗、SOC、资源、交付、最小硬截止余量与通信状态，以及 Q4 分区和库存统计。资源表不会在校验过程中被静默修复。校验失败会撤销旧 `validation.json`，避免留下误导性的成功记录。Q4 独立入口先核对 Q3 的官方输入指纹；完整物理和通信复核仍需运行总校验器。

论文、科研图与结果工作簿：

```bash
python -m pip install -r requirements-paper.txt
python scripts/analyze_paper.py
python scripts/setup_paper_fonts.py
python scripts/build_paper.py
```

新论文在 [paper/](paper/README.md)：同步最新算法结果的匿名论文（含自动目录和附录）、12 张主图、16 张表。主图均输出 PDF/SVG/300 dpi PNG，数字由结果文件生成。构建另需 XeLaTeX、ctex、xeCJK、Fandol，完整命令和 Excel 导出见论文 README。

原 `scripts/make_figures.py` 的六幅图已由统一图形流水线替代并删除。`docs/paper/` 中旧稿仅作历史资料。当前证据及适用边界见 [论文终审](paper/reports/FINAL_AUDIT.md)，AI 记录见 `docs/AI_USAGE.md`。

当前对标方案的通信回放：1 s/0.5 s/0.25 s分别检查38978/77643/154962条状态，均零未覆盖；最低余量分别0.132435/0.132073/0.125590 dB。有限采样仍非连续时间证明。Q2固定路线工作量下界诊断运行 `python scripts/diagnose_transport_load.py`。

历史通信修复（PR #10）：原0.5 s回放的1个未覆盖状态（−0.154251 dB）保存在 `archive/baseline-2a98f09/`。候选搜索和独立验证均采用1 s与0.5 s网格并集，先修复失效中继再继续5000次搜索。该次方案在1 s、0.5 s及未参与搜索的0.25 s回放中均为0未覆盖，最低余量0.02877762 dB；这仍不是连续时间证明。该次Q1/Q2正式决策保持一致；本轮对标优化已继续修改Q2/Q3，并重算Q4及图文，请以当前结果与对标审计为准。对比见 [通信修复对比](results/communication_repair_comparison.csv)，审计见 [修复审计](docs/audit/communication-repair/REPORT.md)。

额外独立回放与修复前后对比：

```bash
python scripts/replay_communication.py --out results/communication_replay.json
python scripts/compare_algorithms.py --baseline archive/baseline-2a98f09/results --baseline-label before-communication-repair --baseline-replay archive/baseline-2a98f09/communication_replay.json --results-replay results/communication_replay.json --out results/communication_repair_comparison.csv
```

通信比较区分检查网格：历史1 s通过不能自动填写为0.5 s通过。正式结果中的 `checked_states` 是双网格精确并集去重后的数量；论文独立回放按单独网格计数，包含相位端点重复，二者不可直接相加比较。
