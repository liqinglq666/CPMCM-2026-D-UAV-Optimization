# 引用与方法来源核验

核验日期：2026-09-23。仅引用赛题、作者原文、出版社页面、机构资料或官方标准；正文按首次出现编号。没有根据模型记忆补写 DOI。

| 编号 | 已核验书目信息 | 原始/官方来源 |
|---|---|---|
| 1 | 组委会，2026 D 题《山区洪涝灾害下无人机运输与通信协同优化》及附件，2026 | 用户提供的原始 DOCX、五个工作簿、DEM 与附录 |
| 2 | Charles F. F. Karney. Algorithms for geodesics. Journal of Geodesy, 87(1), 43–55, 2013. DOI 10.1007/s00190-012-0578-z | https://geographiclib.sourceforge.io/geod.html |
| 3 | Kevin Dorling, Jordan Heinrichs, Geoffrey G. Messier, Sebastian Magierowski. Vehicle Routing Problems for Drone Delivery. IEEE TSMC: Systems, 47(1), 70–85, 2017. DOI 10.1109/TSMC.2016.2582745 | https://arxiv.org/abs/1608.02305 ; https://ieeexplore.ieee.org/document/7513397/ （索引可读；出版页交互访问受限） |
| 4 | Juan Zhang, James F. Campbell, Donald C. Sweeney, Andrea C. Hupman. Energy consumption models for delivery drones: A comparison and assessment. Transportation Research Part D, 90, 102668, 2021. DOI 10.1016/j.trd.2020.102668 | https://profiles.umsl.edu/en/publications/energy-consumption-models-for-delivery-drones-a-comparison-and-as/ |
| 5 | Yong Zeng, Rui Zhang, Teng Joon Lim. Wireless communications with unmanned aerial vehicles: Opportunities and challenges. IEEE Communications Magazine, 54(5), 36–42, 2016. DOI 10.1109/MCOM.2016.7470933 | https://arxiv.org/abs/1602.03602 ; https://ieeexplore.ieee.org/document/7470933/ （索引及作者版核验） |
| 6 | ITU-R P.525-5, Calculation of free-space attenuation, 2024；批准日期 2024-11-03 | https://www.itu.int/rec/R-REC-P.525-5-202411-I/en |
| 7 | Q. Huangfu, J. A. J. Hall. Parallelizing the dual revised simplex method. Mathematical Programming Computation, 10(1), 119–142, 2018. DOI 10.1007/s12532-017-0130-5 | https://highs.dev/ |

Dorling 等用于说明载荷能量与多架次耦合的研究背景，Zhang 等用于模型适用范围，不将其模型替换赛题规则。Zeng 等用于中继动机，ITU 用于自由空间传播量纲，Karney 用于 WGS84 距离，HiGHS 论文对应 LP 求解器。未声称复现这些文献的实验或比较其性能。

图形方法学习来源：TAO-QKV/Icarus-Figures，MIT，commit `0bcaa40c07ef0dc6ea1506ab147ce0a4f5a542fd`。已学习 README、CLAUDE、cookbook、framework、caption/critique、复杂面板、TikZ hero 与 paperfig 样式；本仓库图形为原创 Matplotlib，不复制外部图像。机械 critique 不会代替人工科学判断，尤其不能把检查脚本对“confidence interval”文字的识别当作实际不确定性证据。

2026-09-24 结构重构：原有七条书目未增删，按新正文首次引用顺序调整编号；机器检查区分七条参考文献与八次引用。用户参考论文只提供结构启发，不作为本题模型或数值来源，也未复制其内容。
