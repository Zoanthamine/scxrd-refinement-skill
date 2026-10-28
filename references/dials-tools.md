# DIALS 辅助脚本与迁移

所有DIALS数据工具在DIALS自带Python下运行，避免跨解释器二进制包混用。无研究样品默认路径、空间群、轮次或截止。先 `--help`；参数由 [还原决策](dials-decisions.md) 支持。工具输出仍含当前任务的路径/identifier，作为本地记录保存，不自动公开。

## 1. 单阶段留痕运行

`dials_stage.py`使用标准库，可由普通Python运行，实际DIALS程序需可执行。激活DIALS环境，或通过`--dials-bin`/`DIALS_BIN`指定启动器目录；优先级为显式参数、环境变量、PATH，失效的显式配置会停止。本机统一入口见[运行说明](local-runtime.md)。输入使用绝对路径，输出参数使用新阶段中的相对文件名；PHIL中包含的文件路径由调用者明确写绝对路径。

```powershell
$py = '<DIALS环境中的python>'
$S = '<skill目录>\scripts'
$W = '<新的项目工作目录>'
$E = '<绝对路径>\imported.expt'
& $py "$S\dials_stage.py" --program find_spots --out "$W\02_spots" `
  --input $E --expect strong.refl -- $E nproc=4
```

程序支持import/find_spots/index/refine/integrate/combine_experiments/symmetry/scale/two_theta_refine/export等单阶段。命令参数原样透传，不猜空间群或删除设置；shell通配符输入匹配为文件，没有匹配即停止。

- `--input`重复指定需要计算哈希的来源文件；原始帧很多时按项目审计清单另存，不能将部分哈希声称成全部来源。
- `--expect`重复指定非空输出；只验证产物存在，不替代科学核查。
- `--timeout`可选；失败/超时保留console和failed状态，停止依赖步骤。
- `--dry-run`仅保存计划，状态为dry_run，不声称已运行。
- 输出目录必须新建；`command.json`保存命令与声明来源，`status.json`保存执行状态。
- 若所选参数会写入源文件目录，先改到阶段目录；运行器不沙箱化DIALS，也不验证每个PHIL参数。

## 2. dataset映射、几何和强度一致性

```powershell
& $py "$S\dials_audit.py" --expt '<scaled.expt>' --refl '<scaled.refl>' `
  --out "$W\audit" --d-min <当前截止> --partiality <当前阈值> --friedel <merge或separate>
```

输入必须配套、identifier唯一，且指标基底已确认一致。输出`dataset_audit.json`，列dataset id/identifier/图像模板/扫描范围/晶胞及XY残差。scaled表另给全局非加权等价均值的每dataset偏差诊断，**不是官方分轮Rint**，不作为自动删轮依据。支持仅有位置列的indexed/integrated表做映射与几何检查，但不会生成不存在的scaled指标。

`--friedel separate`用于保留Bijvoet差异；merge只有在当前目的允许时使用。脚本不能独立证明共同基底、晶体身份或正确空间群。

## 3. 双重证据异常观测诊断

```powershell
& $py "$S\dials_screen.py" --expt '<scaled.expt>' --refl '<scaled.refl>' `
  --out "$W\screen_report" --d-min <截止> --partiality <阈值> `
  --friedel <merge或separate> --xy-min <像素偏差> --z-min <稳健Z阈值> `
  --min-references <参考观测数量> --min-datasets <独立参考dataset数量>
```

默认只写CSV候选和审计。条件：可用于当前范围的strong观测，同时有位置偏差与稳健强度偏差；整dataset不进入自身参考，参考散布防止低估σ导致过多误判。dataset通常对应独立扫描，须先核实；不能把同一物理扫描分片当作多个独立参考。

查看原图/shoebox后，如决定建立筛选对照，再加：

```powershell
--write-filtered --source-expt '<未缩放integrated.expt>' --source-refl '<未缩放integrated.refl>'
```

源表不得已有scale强度/因子。候选按identifier、**原始**HKL、预测质心匹配，一条候选恰好对应一条源观测才写`filtered.expt/refl`。不同基底/重新预测/部分合并可能导致匹配失败；先调查，不能放宽匹配到静默多删。空候选会输出原样副本，不声称有改善。

新副本须重新`dials.scale`并同协议导出/精修，核对覆盖、σ和指标后决定采用。工具不自动采纳，不删除整个唯一HKL，不按弱度或负强度筛除。

## 4. 吸收分量核查

```powershell
& $py "$S\dials_absorption.py" --expt '<scaled.expt>' --refl '<scaled.refl>' `
  --out "$W\absorption" --partiality <当前阈值>
```

当前实现针对DIALS 3.30的physical模型内部API：使用同一晶体坐标和轴对齐，配置组件，验证完整分量乘积复现存储`inverse_scale_factor`，然后仅取吸收分量。不同版本必须重新检查实现；乘积不符、无吸收分量或非physical模型立即失败，不猜替代范围。

结果为共同最大值归一化的**相对经验**范围，绝对物理透射未知。排除总体尺度和衰减，记录观测集合和版本；脚本不编辑CIF。当前所用数据/报告要求是否支持该表述，由实际方法与元数据审核决定。

## 5. 验证与可移植性

- 标准精修脚本依赖Python 3.10+；数值初筛需NumPy，CIF编辑需Gemmi，格式验证需PyYAML。
- DIALS/cctbx/dxtbx使用独立DIALS环境，依其官方平台说明安装；公开包不内置DIALS、SHELXL、Olex2或Bruker程序。
- Windows从已配置环境运行；Linux/macOS同样使用参数化路径。PowerShell示例的续行/变量写法需按shell调整，Python工具不依赖盘符。
- `03_run.py --shelxl <可执行文件>`或`SHELXL_EXE`/PATH定位；没有默认Olex2安装位置。
- 测试用合成数据：`python scripts/test_regressions.py`与`python scripts/test_dials_helpers.py`。第一套需要Gemmi，第二套需要NumPy；测试不联网、不选择科学模型。
- 离线真实数据冒烟验证与合成行为测试互补，不能证明新仪器格式/API全部兼容。
