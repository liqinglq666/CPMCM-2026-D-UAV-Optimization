# 图17—27终稿级重构验收

实际逐图查看11幅PDF的彩色与灰度渲染，共22幅。最终宽均16.3 cm；PDF必要文字≥8 pt；画布外文字0；字体已嵌入，SVG含可编辑文字，PNG为600 dpi。
生成时逐项检查217项；对成品数据、真实源记录、来源哈希及PDF文件又检查146项，均通过。58个冻结结果文件哈希保持不变。

本记录只认证单图成品，未认证最终Word/A4整页分页。图20灰度中交接/服务与返航明度较接近；彩色阶段和灰度下ID、纹理、释放时刻可读，此点未隐藏。

## 图17

- 修订：修复三维北向轴裁切、地形遮蔽实体标签、R2与005近邻；三剖面统一0—500 m并将链长/余量置于空白区。
- 实看：同状态三链路、真实闭像元阶梯与三维×2声明可读；灰度仍由线型与节点形状区分。
- 最终PDF SHA256：`191147eb9eb6a4a8b56a729b50b25b22430b2625189e489e8a38e696f84fc10d`
- 彩色：`C:\Users\11346\Documents\Codex\2026-09-26\d-uav-paper-updated-pdf-pdf\work\fig_v2\fig_17_pdf_color.png`
- 灰度：`C:\Users\11346\Documents\Codex\2026-09-26\d-uav-paper-updated-pdf-pdf\work\fig_v2\fig_17_pdf_gray.png`

## 图18

- 修订：增加顶部共享图例与标题间距；将包络与不足点上下错开，保留真实时刻。
- 实看：24行分组与灰度可读；密集采样刻度在印刷尺度局部视觉汇聚，精确逐点记录由CSV提供，未绘连续状态带。
- 最终PDF SHA256：`631aef3fe5cf82a38d770522f00d2f66a8bb8d871556a8d650145a68cd0face7`
- 彩色：`C:\Users\11346\Documents\Codex\2026-09-26\d-uav-paper-updated-pdf-pdf\work\fig_v2\fig_18_pdf_color.png`
- 灰度：`C:\Users\11346\Documents\Codex\2026-09-26\d-uav-paper-updated-pdf-pdf\work\fig_v2\fig_18_pdf_gray.png`

## 图19

- 修订：复核图例明确前段合并为准备、出航与建链；实体占用另加300 s。
- 实看：两层同轴、实体编号和任务编号可区分；384.830 s空闲及最后返航线清楚。
- 最终PDF SHA256：`337a9832d8252ead33706f1640d5b9a3003bee806ccd430b92c08c4719765121`
- 彩色：`C:\Users\11346\Documents\Codex\2026-09-26\d-uav-paper-updated-pdf-pdf\work\fig_v2\fig_19_pdf_color.png`
- 灰度：`C:\Users\11346\Documents\Codex\2026-09-26\d-uav-paper-updated-pdf-pdf\work\fig_v2\fig_19_pdf_gray.png`

## 图20

- 修订：移开行前机型符号避免压住资源编号；中继按原模型拆分180 s准备、出航、30 s建链、服务、返航，完整显示充电/周转。
- 实看：彩色阶段与四层释放可读；灰度下交接/服务与返航明度较近，但资源ID、任务ID、充电/周转纹理和返航线明确，此限制单独保留。
- 最终PDF SHA256：`e531b4d68b58dd1a3b9f99694f44a8e18bebfda44bef2c9e06589c258b65705c`
- 彩色：`C:\Users\11346\Documents\Codex\2026-09-26\d-uav-paper-updated-pdf-pdf\work\fig_v2\fig_20_pdf_color.png`
- 灰度：`C:\Users\11346\Documents\Codex\2026-09-26\d-uav-paper-updated-pdf-pdf\work\fig_v2\fig_20_pdf_gray.png`

## 图21

- 修订：实际PDF发现对数指数只有5.95 pt，已改0.01/0.1/1等十进制刻度，保持对数轴。
- 实看：必要文字均8.5 pt，最紧采样与24项保守下界明确分层，彩色和灰度可读。
- 最终PDF SHA256：`9ffea8bdfe2c6303356fcc42c68b2c7945c1ab8e0b5eb4a343f552ee70e8c5a6`
- 彩色：`C:\Users\11346\Documents\Codex\2026-09-26\d-uav-paper-updated-pdf-pdf\work\fig_v2\fig_21_pdf_color.png`
- 灰度：`C:\Users\11346\Documents\Codex\2026-09-26\d-uav-paper-updated-pdf-pdf\work\fig_v2\fig_21_pdf_gray.png`

## 图22

- 修订：采用实际相邻访问边及真实column后缀，完整列九分量而不补成完全图。
- 实看：15区完整ID、六条真实关系和九分量，在彩色与灰度均可直接读出。
- 最终PDF SHA256：`39864ee422ccd002631df271594161f5c1436b3015f673508605a6be28b9f4c8`
- 彩色：`C:\Users\11346\Documents\Codex\2026-09-26\d-uav-paper-updated-pdf-pdf\work\fig_v2\fig_22_pdf_color.png`
- 灰度：`C:\Users\11346\Documents\Codex\2026-09-26\d-uav-paper-updated-pdf-pdf\work\fig_v2\fig_22_pdf_gray.png`

## 图23

- 修订：增高两地图与底部统计区，避免7.3 cm地图缩字；统一两侧纯运输工作量口径。
- 实看：同范围地图、成员形状、组标签、工作量与缺口可读，无虚构连续分界。
- 最终PDF SHA256：`f063b7bbd96b3a7f5c80a99727aaa4e749c8bb109885a9ecc8b7506d77d12655`
- 彩色：`C:\Users\11346\Documents\Codex\2026-09-26\d-uav-paper-updated-pdf-pdf\work\fig_v2\fig_23_pdf_color.png`
- 灰度：`C:\Users\11346\Documents\Codex\2026-09-26\d-uav-paper-updated-pdf-pdf\work\fig_v2\fig_23_pdf_gray.png`

## 图24

- 修订：与图23同尺寸、地图范围、工作量尺度；三组由形状和标签共同编码。
- 实看：资源优先小组与均衡偏好可比较，灰度仍保留圆/方/三角成员编码。
- 最终PDF SHA256：`28685354976218c930ea6d2a509e0cb1f0efe0cfad4f6d7e61c5a1c62e55f513`
- 彩色：`C:\Users\11346\Documents\Codex\2026-09-26\d-uav-paper-updated-pdf-pdf\work\fig_v2\fig_24_pdf_color.png`
- 灰度：`C:\Users\11346\Documents\Codex\2026-09-26\d-uav-paper-updated-pdf-pdf\work\fig_v2\fig_24_pdf_gray.png`

## 图25

- 修订：删除与右图图例争位的轴标题，缺口数量并入面板标题。
- 实看：整数矩阵、单格缺口色阶和分类纹理条均清楚，零缺口仍有数量记录。
- 最终PDF SHA256：`09290905cae32566031162c8b36690be216673bc3717e0990efc4797a5726205`
- 彩色：`C:\Users\11346\Documents\Codex\2026-09-26\d-uav-paper-updated-pdf-pdf\work\fig_v2\fig_25_pdf_color.png`
- 灰度：`C:\Users\11346\Documents\Codex\2026-09-26\d-uav-paper-updated-pdf-pdf\work\fig_v2\fig_25_pdf_gray.png`

## 图26

- 修订：按0—100%统一热图并保留不可达斜纹；真实窄23架次段不拉宽，另列精确显示区间。
- 实看：灰度顺序色阶、空实端点、原五场景核验和不可行区可辨；完整浮点边界随图保存。
- 最终PDF SHA256：`1aeea9652112128fee2cee4fb93964b4edf0f3eed24b7e5313e1f061aea6f04a`
- 彩色：`C:\Users\11346\Documents\Codex\2026-09-26\d-uav-paper-updated-pdf-pdf\work\fig_v2\fig_26_pdf_color.png`
- 灰度：`C:\Users\11346\Documents\Codex\2026-09-26\d-uav-paper-updated-pdf-pdf\work\fig_v2\fig_26_pdf_gray.png`

## 图27

- 修订：扩宽SOC最小窗与标签区；增加底排左边距消除纵轴裁切；三个箱号改折线引线避免穿字。
- 实看：独立样本ECDF、三个最低SOC、31箱排序和仅最低箱的窄窗在两种模式均可读。
- 最终PDF SHA256：`ff103e1bbaa977583fb6070a37ecbb02b404976bfd68a153bf652592019a45d5`
- 彩色：`C:\Users\11346\Documents\Codex\2026-09-26\d-uav-paper-updated-pdf-pdf\work\fig_v2\fig_27_pdf_color.png`
- 灰度：`C:\Users\11346\Documents\Codex\2026-09-26\d-uav-paper-updated-pdf-pdf\work\fig_v2\fig_27_pdf_gray.png`
