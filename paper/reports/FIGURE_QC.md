# 12 图与页面终检 — 2026-09-24

全部图由真实 CSV/JSON/DEM 自动绘制；统一用户指定语义色板。黄色仅作星号强调；浅色填充配深色文字/边框。主图按正文首次论证顺序插入，全部 PDF/SVG 为矢量，PNG 为 300 dpi。

| 图 | 主张 | 数据 |
|---|---|---|
| 1 / fig01_framework | 统一物理底座逐层扩展到运输执行、通信保障和独立资源配置；继承规则与继承固定方案严格区分 | paper/data/analysis.json；results/q4/Q4_resource_summary.csv |
| 2 / fig02_task_map | 原始地形与任务节点建立空间背景，参考连线不冒充运输路线 | paper/data/analysis.json；paper/data/terrain_map.json |
| 3 / fig03_physics | 地形抬高巡航高度，去程载荷与返程空载产生不同能耗 | paper/data/terrain_profile.csv；paper/data/energy_components.csv；paper/data/analysis.json；src/config.py |
| 4 / fig04_payload_boundary | 额定载荷与能量上限共同限制安全运载能力 | results/q1/Q1_max_safe_payload.csv；paper/data/analysis.json |
| 5 / fig05_batching | 不可拆分货箱通过精确集合划分形成最低架次数组批 | results/q1/Q1_batch_solution.csv；paper/data/constraint_slacks.csv；paper/data/analysis.json |
| 6 / fig06_tradeoff | 压缩架次付出及时性代价；所选点是有限候选的显式折中 | results/q2/Q2_tradeoff_frontier.csv；results/q2/Q2_transport_trips_balanced.csv |
| 7 / fig07_resources | 飞机返航释放与电池充满释放分别约束实体资源时序 | results/q2/Q2_resource_check.csv |
| 8 / fig08_communication_map | 直连不足发生在航段内部；固定离散计划与LP连续时序分开 | paper/data/analysis.json；paper/data/terrain_map.json；paper/data/communication_states_05s.csv；results/q3/Q3_relay_sorties.csv |
| 9 / fig09_communication_time | 中继窗口保障已检查状态；最紧采样余量仍不能证明连续安全 | paper/data/analysis.json；paper/data/communication_states_05s.csv；results/q3/Q3_relay_sorties.csv |
| 10 / fig10_partition | 不可拆连通分量限制分组，库存总量不能抵消按类型资源缺口 | results/q4/Q4_resource_summary.csv；results/q4/Q4_partition_config.csv；results/q3/Q3_transport_trips.csv |
| 11 / fig11_sensitivity | 连续能力收缩与离散组批跳变须分开；固定方案阈值不是全局分界 | paper/data/payload_reserve.csv；results/q1/Q1_sensitivity_summary.csv；paper/data/analysis.json |
| 12 / fig12_validation | 可行不等于稳健；SOC、硬时限、加密通信证据共同界定边界 | paper/data/constraint_slacks.csv；paper/data/hard_deadline_slacks.csv；paper/data/analysis.json |

图 9 的时间窗最小值使用真实 argmin 时刻，不把窗首当事件时刻，不连接跨任务/模式跳变。全局最紧原始记录单独放大。图 11 不把不可达填为零，不为五个离散重算点虚构阶梯阈值。

32 页逐页审查范围：1 摘要；2–3 目录；4–7 总体/数据/地图；8–9 公共物理；10–12 Q1；13–16 Q2 及资源；17–20 Q3；21–23 Q4及敏感性起点；24–27 敏感性/验证/结论；28 文献；29–32 跨页完整结果与辅助说明。部分页底留白用于维持主图与解释的阅读顺序，未通过缩小正文或裁图强行压页。

12 图重画 PNG SHA 均一致；原生/转曲 PDF 已检查字形、分页、公式断行、坐标单位、阈值、图例及匿名信息。机器结果见 `consistency.json`；兼容逐页渲染见 `final-visual-run/browser-check.json` 与 `compatibility.json`。旧 `icarus-critique.txt` 属前一轮九图历史检查，不充当本轮验收。
