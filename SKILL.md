---
name: scxrd-refinement
description: 单晶 X 射线数据诊断、SHELXT 解结构与 SHELXL/Olex2 精修；按需从原始帧启用 DIALS。提供输入分级、配体拓扑、孪晶调查及 CIF/FCF、依赖和交付核查。
---

# 单晶诊断与精修

目标是得到有证据支持、可复现的结构模型与配套数据；警报和 R 值用于发现问题，不作为自动删数据或决定空间群的目标函数。

## 本机运行入口

本机已配置统一科研环境时，先读[本机运行与工具分工](references/local-runtime.md)：普通辅助脚本走 science，依赖 DIALS/cctbx/dxtbx 的脚本走 dials；有效程序路径只从统一环境配置读取。其他机器使用已验证的独立环境。

## 先选择入口

| 当前输入/问题 | 使用流程 | 按需读取 |
|---|---|---|
| 只有 CIF/RES，没有配套强度 | 做模型/文件诊断，先找回强度来源；取得强度后再实验精修 | [输入盘点](references/solution-and-ligand.md) |
| 待解结构或配体拓扑不清 | 盘点输入，按消光/化学建立 SHELXT 候选；配体单独核对 | [解结构与配体](references/solution-and-ligand.md) |
| 需调查孪晶律、HKLF 协议或 PLATON/FCF 兼容 | 先确认数据支持范围，再建立有依据的候选和独立对照 | [孪晶调查](references/twin-investigation.md) |
| 已有配套 INS/RES/HKL，处理化学、H、ADP、无序或构型 | 原样复现，直接进入 SHELXL/Olex2；无需 DIALS | [模型精修](references/refinement-decisions.md)、[操作命令](references/workflow-recipes.md) |
| 分裂、互斥构象、多组分或穿过对称元素的无序 | 核对差密度、占有率/多重性与组分连接，再设计最简单模型 | [无序与占有率](references/disorder-and-occupancy.md) |
| 活泼H/质子转移、孪晶线索或弥散溶剂 | 分别核查化学/氢键、孪晶类型/输入协议及空腔贡献 | [H、孪晶与溶剂案例](references/hydrogen-twin-solvent-cases.md) |
| 有原始帧，需重还原或解释高 Rint、索引/积分异常 | 检查格式与仪器几何后启用 DIALS | [还原决策](references/dials-decisions.md)、[操作顺序](references/dials-to-olex2.md)、[脚本](references/dials-tools.md) |
| 只有积分数据 .expt/.refl | 从基底核查/标度进入，不重复选点积分 | [还原决策](references/dials-decisions.md)、[脚本](references/dials-tools.md) |
| CIF/FCF 或报告不配套、实验字段缺失、需调查警报或写回复 | 先确认当前模型/数据版本，再按警报对象核查和交付 | [警报调查与回复](references/checkcif-case-triage.md)、[元数据](references/cif-metadata.md)、[操作命令](references/workflow-recipes.md) |
| 历史模型不复现、结论冲突或拟借鉴旧方案 | 查当前文件与失败分支，不沿用旧最小 R 模型 | [实践经验](references/practice-lessons.md)、[排错](references/pitfalls.md) |

DIALS 是可选分支，不是所有精修的前置步骤。没有原始帧时明确不能验证的积分、晶胞和空间群问题；CIF 标签修改不能代替重新还原。

借鉴外部教程时，按[教程来源与适用边界](references/tutorial-sources.md)区分文字、图像/视频索引及已核实方法；历史案例的原子名、比例和参数不能自动输入当前晶体。

整合来源及已修正的经验见[方法整合说明](references/integration-provenance.md)。

## 建立基线

1. 确认当前候选与最新记录，列出配套 INS/RES/HKL/LST/CIF/FCF，记录来源、版本与哈希。不能按 final 文件名、文件大小或最低 R 自动选输入。
2. 原始实验文件保持原样，在新目录做对照。程序成功、空警报、打包成功与科学验证通过是不同状态。
3. 原样复现，保留 WGHT/HKLF/MERG/SHEL/OMIT/PART/AFIX 及其他科学指令。失败先核对数据源、版本、外部依赖和运行协议。
4. 记录 R1(gt/all)、强反射数、wR2、GooF、Rint/Rsigma、参数/限制数、末轮 shift/s.u.、残峰、ADP、组成连接和适用的绝对结构指标。
5. 明确证据支持的问题；读取对应参考，只试与该问题有关的分支。

## 每个对照闭环

记录“证据—假设—父版本—唯一改动—实际输入/命令—结果—采用理由—遗留问题”。独立对照从同一父版本启动；有效单项的组合还须实际测试。

还原对照同时记录分辨率、完整度、重复度、I/σ、CC½、DIALS Rmerge/Rmeas、SHELXL Rint、Rsigma、误差模型及强反射集合。反射集或 σ 改变后的 R1(gt)不能直接排名。保留弱及负强度；排除必须有当前图像、位置、仪器或独立等价测量证据。

结构性修改写成完整 INS，核对空间群/晶胞/hkl/坐标同步变换。overlay 不用于拼接原子、PART/FVAR/AFIX 或空间群；脚本的占有率、连接、ADP和对称结果仅供初筛。

退出码、RES/LST和统计齐全只是运行门槛。是否采用还看几何、ADP、占有率和参数稳定性。当前 WGHT 与下一轮建议值分开记录；最后 shift/s.u.从末循环读取。无新证据时停止盲试，报告限制及再采集所需信息。

## 验证与交付

- 从选定一轮生成配套文件；坐标、反射筛选或权重改变后重出 CIF/FCF。
- 元数据按当前记录/明确用户确认补充，矛盾留痕；不推断软件、组成、透射率或合成绝对构型。实测晶胞与理想化假设分开标注。
- 本地检查语法、晶胞/波长/对称、组成/占有率、权重、嵌入记录与结构因子。轻量脚本未覆盖的检查另做。
- 外传当前样品 CIF/FCF 前确认授权，沿用本会话对相同样品/目的地的有效授权；其他本地工作先完成。完整 CIF+FCF 验证，CIF-only 明确未做结构因子核验。
- 报告绑定实际提交文件哈希、日期和模式；请求成功不等于验证成功，修改后的 CIF 不继承旧报告。
- 警报答复只写核实事实及局限；自动 VRF 是待填写骨架。A=0 不证明空间群、绝对构型或发表适用性。
- 指定当前唯一候选、用途、采用理由、缺项和未解决问题；按[交付核查](references/package-audit.md)检查 FAB/include、哈希、ZIP 与包内重现。公开发布只包含通用方法/代码，当前研究数据与身份字段另行授权。

## 工具选择

脚本在 `scripts/`，先用 `--help` 核对参数。

| 工具 | 用途/边界 |
|---|---|
| inventory_crystal_input.py | 目录/ZIP 只读盘点，区分 SFRM 校准、候选和未知；不据此宣布可重积分 |
| prepare_ligand.py | RDKit 拓扑核对及显式参考构象；不替代衍射坐标 |
| validate_crystal_package.py | 基本文件、显式依赖、哈希及 ZIP 完整性；不等于科学验证 |
| dials_stage.py | 单阶段运行、输入哈希/命令/日志/状态；不自动决定参数或串行盲试 |
| dials_audit.py | identifier/dataset/模板映射、几何及等价强度诊断；不自动删轮 |
| dials_screen.py | 双重证据候选；默认仅报告，显式选择才输出未缩放筛选副本；须重标度 |
| dials_absorption.py | physical 模型吸收分量及乘积核查；相对范围不是绝对透射，不自动填 CIF |
| 01_diagnose.py / xtal_core.py | 文件与几何初筛；复杂无序、特殊位置等需独立复核 |
| 03_run.py / 04_summarize.py | 保留指令、独立归档、失败停止；历程汇总须核对迭代子目录 |
| 06_hydrogen_plan.py / 07_symmetry_check.py | H/对称建议，不自动决定化学或空间群 |
| 08_cif.py | Gemmi 元数据编辑与有限一致性检查，不猜缺失字段 |
| 09_checkcif.py | 授权后在线提交、模式/哈希留痕及 VRF 草稿 |
| 10_delivery.py | 归集、哈希和打包，科学结论另写 |

选择安装有依赖的 Python；DIALS 工具用 DIALS 自带解释器，不能混用不同 Python 的二进制包。SHELXL 通过 `--shelxl`、`SHELXL_EXE` 或 PATH 指定。正式结构图由 Olex2/PLATON 导出。
