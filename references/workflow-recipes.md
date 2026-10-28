# 按问题选操作

路径变量指向当前任务真实文件；无晶体默认参数。本机统一环境的调用见[运行入口](local-runtime.md)，使用其 science/dials 后端；以下 `$py` 为其他环境中已核实的解释器示例。

## 运行

```powershell
$py = "<已验证的 Python>"
$S = "<本 skill 目录>\scripts"
$W = "<新的工作归档目录>"
$base = "<当前配套 RES 或 INS>"
$hkl = "<已核实的 HKL>"
& $py "$S\01_diagnose.py" "<数据目录>"
& $py "$S\03_run.py" --base $base --hkl $hkl --stage baseline --dir $W --plain
& $py "$S\03_run.py" --base "<完整试验 INS>" --hkl $hkl --stage trial_01 --dir $W
```

用 --shelxl 或 SHELXL_EXE 指定程序。外部 include/ABIN 依赖需另准备专用运行环境，当前运行器不搬运这些依赖。
基线通过后酌情用 --converge N；权重迭代分别存放 weight_NN 子目录，以 run_result.json 指向的最后一轮为准。下一轮建议权重不是本轮已使用权重。
批量第一行须明确父文件，后续留空只使用本批上一成功轮；独立对照须显式写同一父文件。

## 弱数据与反射

保留全数据基线，检查积分/吸收日志、壳层、消光、模型遗漏及异常反射。
异常点记录 hkl、I、σ、Fo/Fc 和来源，负强度本身不是删除理由。
只有具体问题支持时另建截断或排除对照；记录反射数、完整度、分辨率范围，不只比 R。

SHEL 两个数字都是 Å 分辨率界限。`SHEL 999 0.85` 仅是高分辨率截止写法示例，0.85 不是推荐值。
旧项目 `SHEL 0.85 0.02` 选取了相反侧范围，不能据此证明一般“截断有害”。

## 化学、H 与无序

先映射目标图与模型，核对键级/价态、CH/CH2、保护基和相对构型。
H 规划仅作候选；羟基/水/胺 H 结合差图和几何判断，长 O–H 或短 H···H 不自动解释为真实氢键。
无序试验写完整 INS，明确 FVAR（首项为尺度）、PART、互补占有率及特殊位置。不能 overlay 粘贴占位坐标。
检查互斥组分、ADP/占有率相关性，按证据选择限制。RIGU/SIMU 是 restraints；EADP/EXYZ 等是 constraints。
不设通用 ΔwR2 阈值，不从某项目拷贝原子名、限制强度和占有率。

## 空间群与晶胞

07_symmetry_check.py 仅初筛。根据消光、度量、候选操作和化学建立模型。
记录变换矩阵、原点移动，坐标/hkl/晶胞/对称同步变换，核对 Z/Z′、特殊位置和独立原子。
LATT 正号含反演、负号不含反演；同一晶胞换空间群不意味着 UNIT 必须减半。
未经原始数据确认的理想化晶胞应标为候选假设，不能赋予虚构误差。

## 构型与溶剂

核对绝对结构统计量、不确定度、Friedel 覆盖与处理方式；独立化学依据确实存在时才引用合成构型，否则保留未知。
Dcalc 来自输入组成/Z/V，不是独立的溶剂排除证据。掩膜或显式溶剂需有空腔、密度和实验记录支持，报告处理范围、电子数和局限。

## 验证和交付

明确生成 CIF/FCF 时使用 --acta；先核对 LIST/MERG/FMAP 兼容性，不悄改协议。

```powershell
& $py "$S\03_run.py" --base "<选定 RES>" --hkl $hkl --stage export --dir $W --acta
& $py "$S\08_cif.py" prepare --cif "<本轮 CIF>" --metacif "<配套 metacif>" --out "<候选 CIF>"
& $py "$S\08_cif.py" validate --cif "<候选 CIF>" --res "<本轮 RES>" --lst "<本轮 LST>" --fcf "<本轮 FCF>" --json "<检查结果.json>"
& $py "$S\09_checkcif.py" --cif "<候选 CIF>" --fcf "<本轮 FCF>" --outdir "<新的验证目录>" --vrf
& $py "$S\10_delivery.py" --outdir "<新的交付目录>" --name "<样品代号>" --cif "<候选 CIF>" --fcf "<本轮 FCF>" --res "<本轮 RES>" --ins "<本轮 INS>" --lst "<本轮 LST>" --hkl $hkl --checkcif "<对应报告>" --notes "<结论与局限.md>" --zip
```

--meta 仅用于当前有来源字段；不默认裁剪 CIF，不将 VRF TODO 写入定稿。
保存 validation_manifest.json 与报告，阅读报告确认结构因子实际完成核验。

