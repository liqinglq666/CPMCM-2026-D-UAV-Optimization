# Consistency Report

机器证据见 `consistency.json` 与 `consistency-run.txt`。

| 对照层 | 实际检查 | 结果 |
|---|---|---|
| 正式计算 → 论文诊断 | 24 个源文件 SHA256，与本轮独立重算逐字节对照 | PASS |
| 逐架次 → 汇总数字 | 独立累加能耗、时间、架次数、最小 SOC，检查每箱恰好一次 | PASS |
| 数字宏 → 摘要/正文/附录 PDF | 36 个生成宏中使用的 34 个均匹配 PDF；未定义引用为零 | PASS |
| CSV/JSON → Excel | 8 张表、1723 个数据单元格逐格对比，数值类型与完整精度检查 | PASS |
| 官方模板 → Excel | 六张表及表头保留；新增两张 Q3 必要明细 | PASS |
| 图形 → 数据 | 9 份契约的全部来源存在，manifest 为每份来源记录 SHA256 | PASS |
| 相同数据 → 重绘 | 九张图全部重新执行，PNG SHA256 完全相同 | PASS |
| 三格式导出 | 9 PDF + 9 SVG + 9 PNG；PNG 300 dpi；SVG 无栅格截图 | PASS |
| PDF | 19 页连续页码；无 overfull、缺字或未定义引用错误 | PASS |

PDF SHA256：`75574aeb80723a04db6f5de895f5844b477dae4bf8ecc3ea24febda50126ffbb`。

Excel SHA256：`27812796a9fdfd8d9ee01e218e33d2ce60e772380613990235fd5a4578e5303e`。

Python 验证器仅读取 Excel。工作簿是静态结果视图，不声称在 Excel 内重新求解路线和调度。比较浮点值采用相对 1e-12 / 绝对 1e-10 容差，仅展示值四舍五入。储备场景中的不可达空值和无硬截止货箱的空白属于已定义状态，不计为计算失败。
