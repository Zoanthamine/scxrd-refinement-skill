---
name: scxrd-refinement
description: 单晶 X 射线结构诊断与精修。按输入选择直接 SHELXL/Olex2 精修，或用 DIALS 处理原始帧、选点、索引、积分和标度；辅助 CIF/FCF 与 checkCIF 核验和可追溯交付。
---

# 单晶诊断与精修

目标是得到有证据支持、可复现的结构模型与配套数据；警报和 R 值用于发现问题，不作为自动删数据或决定空间群的目标函数。

## 先选择入口

| 当前输入/问题 | 使用流程 | 按需读取 |
|---|---|---|
| 已有配套 INS/RES/HKL，处理化学、H、ADP、无序或构型 | 原样复现，直接进入 SHELXL/Olex2；无需 DIALS | [模型精修](references/refinement-decisions.md)、[操作命令](references/workflow-recipes.md) |
| 有原始帧，需重还原或解释高 Rint、索引/积分异常 | 检查格式与仪器几何后启用 DIALS | [还原决策](references/dials-decisions.md)、[操作顺序](references/dials-to-olex2.md)、[脚本](references/dials-tools.md) |
| 只有积分数据 .expt/.refl | 从基底核查/标度进入，不重复选点积分 | [还原决策](references/dials-decisions.md)、[脚本](references/dials-tools.md) |
| CIF/FCF 或报告不配套、实验字段缺失 | 先确认当前模型/数据版本，再验证和交付 | [元数据](references/cif-metadata.md)、[操作命令](references/workflow-recipes.md) |
| 历史模型不复现、结论冲突或拟借鉴旧方案 | 查当前文件与失败分支，不沿用旧最小 R 模型 | [实践经验](references/practice-lessons.md)、[排错](references/pitfalls.md) |

DIALS 是可选分支，不是所有精修的前置步骤。没有原始帧时明确不能验证的积分、晶胞和空间群问题；CIF 标签修改不能代替重新还原。

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
- 指定当前唯一候选、用途、采用理由、缺项和未解决问题。公开发布只包含通用方法/代码，当前研究数据与身份字段另行授权。

## 工具选择

脚本在 `scripts/`，先用 `--help` 核对参数。

| 工具 | 用途/边界 |
|---|---|
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
