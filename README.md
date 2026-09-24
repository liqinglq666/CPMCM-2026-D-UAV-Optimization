# CPMCM 2026 D 无人机运输与通信协同优化

赛题、原始 Excel、DEM 是输入事实来源；`src/core/` 统一距离、地形、时间、载荷、能耗、充电和资源检查。仓库保持私有。

本轮算法优化以 `bf2e053` 为基准：保留 Q1 精确 DP 和 Q4 分区枚举，增加 Q2 邻域搜索及 Q3 外层离散搜索。修改前审计、算法边界与独立复核见 [算法审计](docs/audit/algorithm-search/AUDIT.md) 和 [验证报告](docs/audit/algorithm-search/REPORT.md)，真实重算对比见 [algorithm_comparison.csv](results/algorithm_comparison.csv)。历史审计保留在 `docs/audit/independent-pass-2/` 和 `docs/audit/REFACTOR_REPORT.md`。

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

Q2 先重建原合并链作为可行种子，再搜索货箱迁移/交换/合并/拆分、destroy-repair、路线顺序、机型、实体无人机、电池和执行顺序。默认在硬截止零违反条件下按加权延误、架次数、makespan、能耗词典序选择；`--target-trips 22` 可显式限制所选架次数。`Q2_tradeoff_frontier.csv` 保留每种架次数的一个代表方案；真正的“已发现非支配解集”为 `Q2_pareto_frontier.csv`，其全部方案可重放并接受独立校验。

Q3 的 `config/q3_plan.json` 是明确的初始可行解，不是最终答案。外层对运输分组、路线、型号、无人机、电池、中继点/高度、运输—中继匹配、中继合并/拆分和资源顺序做固定种子的离散搜索；内层 HiGHS LP 优化连续时序。组件复用时，外层选择官方分段充电函数的分支，LP 精确表达该分支的充电占用。每个可行候选均通过完整 1 s 空间通信预检、时间窗和资源校验；最终再独立重算通信。目标严格按硬截止零违反、通信零违反、加权延误、联合 makespan、联合能耗、中继架次数/服务时长排序。外层是启发式，LP 精确性只对给定离散方案和充电分支成立。

`config/search.json` 只保存种子、迭代预算和候选点生成参数。默认固定种子 20260924，Q2/Q3 分别执行 20000/5000 次邻域尝试；每次尝试、best-so-far、停止原因和运行时间均保存。所有解由官方输入重新计算，不读取历史结果充当求解。`results/q3/Q3_selected_plan.json` 是可重放的输出，不写回初始配置。Q4 继承最终 Q3，并记录任务/通信/资源文件指纹；枚举和库存口径不变。复现命令与环境版本见验证报告。

通信逐阶段采样间隔不超过 1 s，中继窗口前后各留 5 s。DEM 净空与视线共用像元闭边界遍历：边界两侧、角点相接的像元均纳入，采用较高地形的保守约定，不再对坐标取整缓存。**离散采样仍不构成连续时间通信的解析证明。** 建链时无人机已在空中，因此其悬停及通信能耗计入中继能耗。

## 项目结构

```text
config/q3_plan.json              可解释的初始可行解，不含时刻/能耗结果
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
src/q3/preparation.py            真实物理与 1 s 通信预检、精确坐标缓存
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

新论文在 [paper/](paper/README.md)：32 页匿名论文（含两页自动目录和附录）、12 张主图、16 张表。主图均输出 PDF/SVG/300 dpi PNG，数字由结果文件生成。构建另需 XeLaTeX、ctex、xeCJK、Fandol，完整命令和 Excel 导出见论文 README。

原 `scripts/make_figures.py` 的六幅图已由统一图形流水线替代并删除。`docs/paper/` 中旧稿仅作历史资料。当前证据及适用边界见 [论文终审](paper/reports/FINAL_AUDIT.md)，AI 记录见 `docs/AI_USAGE.md`。

2026-09-24 已按“统一物理底座 → Q1–Q4 → 敏感性 → 验证评价 → 结论”重构论文。逻辑审计见 `paper/reports/STRUCTURE_AUDIT.md`，逐节论证目标见 `paper/blueprint.md`。计算内核、Q3 离散计划及 24 个正式结果文件保持不变。
