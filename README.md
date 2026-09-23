# CPMCM 2026 D 无人机运输与通信协同优化

赛题、原始 Excel、DEM 是输入事实来源；`src/core/` 统一距离、地形、时间、载荷、能耗、充电和资源检查。仓库保持私有。

最新独立审计以已合并的 `4a00465` 为起点，重新扫描并运行 baseline，未沿用上轮 PASS 结论。新增问题、修复与回归证据见 [独立审计报告](docs/audit/independent-pass-2/REPORT.md)。更早一轮从 `e668347` 修复 Q3 入口故障的记录保留在 [历史审计报告](docs/audit/REFACTOR_REPORT.md) 和 `archive/baseline-e668347/`。

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
| Q2 | 共享物理引擎；时限优先构造、可行合并、无人机和电池调度 | 选定方案、前沿 CSV、每个前沿方案的可重放 JSON、资源表 |
| Q3 | 官方通信与中继参数、共享物理引擎、显式离散方案 | 联合时刻、逐箱交付、通信窗口、中继能耗与资源表 |
| Q4 | 固定 Q3 任务和通信关系、官方库存 | K=2 / K=3 分区与独立资源缺口 |

Q1 使用题目给定的计划速度，未引入风场。风速、顺逆风、侧风不是官方输入，也未用于调整正式结果。内部单位为 m、s、kg、m³、kWh、kW；只有输出小时、SOC 百分数及无线链路距离 km 时进行单位转换。

Q1 默认读取每个机型的官方返航余量；`python run_q1.py --rho 0.25` 才会统一覆盖所有机型。`Q1_metrics.json` 中 `reserve_fraction: null` 表示未覆盖，实际余量见 `reserve_by_type`。默认官方 A/B/C 均为 20%，所以本轮正式数值不变。

Q2 默认导出从初始 24 架次到 17 架次的可行合并前沿，选择 22 架次。`--target-trips` 改变选择，`--frontier-min` 改变搜索下界；无法达到指定架次数会明确报错。

Q3 的 `config/q3_plan.json` 保存继承自历史可行方案的**货箱分组、路线、中继点、资源分配及顺序**，不保存最终时刻、能耗、SOC 或链路计算结果。程序根据 DEM 重新确定悬停海拔，通过线性规划依次优化加权延误、联合完成时间和中继服务时长。它是固定离散方案条件下的调度求解器，**不能声称自动搜索了全部路线/中继点或得到全局最优**。Q3 不再按易变的 Q2 行号继承任务，修改 Q2 参数不会自动改变这份离散方案；如需改变任务分组，编辑 JSON 后重新校验。

通信逐阶段采样间隔不超过 1 s，中继窗口前后各留 5 s。DEM 净空与视线共用像元闭边界遍历：边界两侧、角点相接的像元均纳入，采用较高地形的保守约定，不再对坐标取整缓存。**离散采样仍不构成连续时间通信的解析证明。** 建链时无人机已在空中，因此其悬停及通信能耗计入中继能耗。

## 项目结构

```text
config/q3_plan.json              已选离散方案，不含硬编码结果
src/config.py                   赛题规则、单位常数、算法参数
src/core/                       官方输入、模型、地形、物理、路线、约束、I/O、溯源
src/q1/physics_engine.py         单点能力与精确组批
src/q2/heuristic.py              初始可行构造
src/q2/tradeoff.py               缓存路线评价、合并前沿与资源调度
src/core/communication.py        双向链路预算、中继物理与通信状态采样
src/q3/communication.py          旧导入路径的兼容导出
src/q3/solver.py                 通信采样与固定离散方案的联合时刻求解
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

可选绘图：

```bash
python -m pip install -r requirements-figures.txt
python scripts/make_figures.py
```

本轮不重写论文、不声称已生成官方结果工作簿。`docs/paper/` 中的旧稿保留为历史工作资料，引用数值前应依据当前 `results/` 更新。AI 辅助记录见 `docs/AI_USAGE.md`。
