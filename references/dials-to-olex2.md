# 从原始帧到 DIALS 还原、Olex2 精修的操作流程

适用：已有原始衍射帧，需要重新还原、排查高 Rint，或需要一份可照着操作的流程。以下列出软件操作、输出和进入下一阶段前的检查条件。命令在 DIALS 环境中执行；Olex2 命令在 Olex2 自己的命令栏执行。

命令参数随版本变化；先在当前 DIALS 环境查看帮助并记录版本。批量 SHELXL 和 Olex2 GUI 采用同一模型时仍须核对引擎和版本。

## 1. 先建数据和软件清单

**操作**：确认原始帧盘可读，核对样品、扫描轮次、帧数、缺帧、曝光时间、旋转宽度、波长、温度、探测器几何。保留已有 `.ins/.res/.hkl/.lst/.cif/.fcf` 和原还原日志。

原始数据只读使用；处理文件放进新的项目工作目录。每次试验用新子目录，防止默认输出覆盖前一轮。最少记录实际命令、版本、输入路径、退出码、日志和采用理由。


## 2. 验证帧读取，再做选点

**操作**：先检查几张低背景、高背景、不同曝光和不同探测器角度的帧，确认像素、方向、尺寸和头信息合理。新格式或解码异常时，与独立读取器逐像素比较，查看压缩/underflow/overflow规则。

```powershell
# 在DIALS环境中运行，路径换成当前真实目录
dials.import "<原始目录>\<已核实扫描>_*.sfrm"
dials.image_viewer imported.expt
```

**输出**：`imported.expt`，含各序列的仪器几何和帧位置。

**检查**：导入序列数、各序列帧范围、曝光/角度是否对应原记录。失败先查路径与帧解码，不继续拿空结果选点。


## 3. 选点（find_spots）

```powershell
dials.find_spots "<导入目录>\imported.expt" nproc=4
dials.image_viewer "<导入目录>\imported.expt" strong.refl
```

**输出**：`strong.refl`，它是探测到的斑点及其位置，不是最后完整反射集。

**检查**：斑点是否落在真实峰上；背景条纹、坏像素、散射扇形是否被误识别；每轮点数和分布。阈值、掩膜、增益等变更需有图像或标定依据。降低选点阈值不等于获得更多可靠反射。


## 4. 索引（index）

同一晶体、不同扫描的倒易格子能对齐时，可先尝试联合索引：

```powershell
dials.index "<导入目录>\imported.expt" "<选点目录>\strong.refl" joint_indexing=True
```

联合失败或序列间格子不能对齐时，另建目录逐序列索引：

```powershell
dials.index "<导入目录>\imported.expt" "<选点目录>\strong.refl" joint_indexing=False nproc=4
```

**输出**：`indexed.expt`、`indexed.refl`。

**检查**：实际成功的序列、索引点数、晶胞、取向矩阵、残差和基底是否一致。“程序成功”可能只有部分序列成功。

已有可靠晶胞时，失败扫描可另做已知晶胞实空间搜索对照：

```powershell
dials.index "<失败序列导入.expt>" "<对应strong.refl>" `
  known_symmetry.unit_cell=<a,b,c,alpha,beta,gamma> `
  known_symmetry.space_group=<已论证空间群> `
  joint_indexing=False indexing.method=real_space_grid_search indexing.nproc=1
```

尖括号为待替换参数，不可原样运行。使用晶胞/空间群先验需保留来源；索引成功不构成对该空间群的独立证明。遇到基底变换，坐标、HKL和晶胞须保持一致。


## 5. 几何精化（refine）：这里还不是原子模型精修

```powershell
dials.refine "<索引目录>\indexed.expt" "<索引目录>\indexed.refl"
```

**输出**：`refined.expt`、`refined.refl`。

**检查**：各轮XY质心和旋转角残差、保留/排除斑点数、晶胞变化及随扫描的取向变化。参数过多或弱斑点污染时，可按证据比较固定仪器参数等更简化模型；比较时也记录反射集合变化。

只有预测位置与真实斑点合理对应，才继续积分。残差持续偏大的扫描保留为独立诊断对象。


## 6. 积分（integrate）

```powershell
dials.integrate "<几何目录>\refined.expt" "<几何目录>\refined.refl" nproc=4
```

**输出**：`integrated.expt`、`integrated.refl`。

**检查**：背景拟合、前景像素、过载、求和/剖面拟合失败率、partiality、剖面相关性及I/σ壳层。选点提供索引/几何/峰形参考；积分会预测并测量反射，所以最终反射不只是strong.refl里的强点。

要比较分辨率或预测范围时，记录`prediction.d_min`；积分预测范围与最终标度/精修范围是两个设置，前者应支持后者。

可见空间背景梯度支持另试平面背景时，单独建目录：

```powershell
dials.integrate "<同一refined.expt>" "<同一refined.refl>" nproc=4 `
  integration.background.algorithm=simple `
  integration.background.simple.model.algorithm=linear2d `
  integration.background.simple.outlier.algorithm=plane
```


## 7. 合并已独立处理的序列，核对对称性

若序列分成多个索引/积分分支，合并各配套文件：

```powershell
dials.combine_experiments "<分支A>\integrated.expt" "<分支B>\integrated.expt" `
  "<分支A>\integrated.refl" "<分支B>\integrated.refl"
```

**输出**：`combined.expt`、`combined.refl`。

记录experiment identifier、dataset id和原扫描编号的映射。**dataset id不等于扫描轮次**，合并/重新标度后顺序可能变化。

未知对称性应结合度量、操作评分、消光与后续结构核验；可使用`dials.symmetry`提供数据层的对称性证据。当前官方小分子教程说明其空间群建议有Sohncke范围的限制，不能将一次建议当作中心对称/滑移面的完整判断。[DIALS小分子教程](https://dials.github.io/documentation/tutorials/small_molecule_tutorial.html)

## 8. 标度和吸收校正（scale）

```powershell
dials.scale "<积分或合并.expt>" "<积分或合并.refl>" d_min=<选择的分辨率>
```

**输出**：`scaled.expt`、`scaled.refl`、`dials.scale.html`及日志。

**检查**：整体与壳层Rmerge、Rmeas、CC½、I/σ、完整度、重复度、自动离群点、标度曲线及误差模型是否正常完成。SHELXL后续的Rint另列，不能拿DIALS Rmerge冒充。

吸收模型阶数、约束及尺度/衰减参数按样品和数据支持程度选择；多变量组合先有单因素或配对对照。当前版本的默认值和实际生效参数从日志/源码/官方文档核实。[DIALS标度指南](https://dials.github.io/dials_scale_user_guide.html)


```powershell
dials.scale "<combined.expt>" "<combined.refl>" `
  d_min=<当前截止> physical.lmax=<当前阶数> physical.surface_weight=<当前约束> `
  dataset_selection.exclude_datasets=<从当前identifier映射核实的dataset列表>
```


## 9. 异常观测筛选与分辨率对照（按需）

保留未筛选基线，先区分坏像素、坏帧、单次反射观测和某个唯一HKL；它们不是同一种排除。

异常观测须同时有位置/图像异常及独立等价测量不一致的证据。参考比较应排除被测试整轮，记录参考观测与独立扫描数量。

筛选阈值按像素尺度、正常定位误差和σ可信程度重新选。实际执行时保存每条观测的identifier、扫描、HKL、帧/位置和理由，映射回**未缩放积分数据**的副本，重新标度；保留其他等价测量。负强度、弱点或高角点本身不是剔除证据。

选择截止同时看壳层信息、完整度、稳定性和目标提交要求。0.25不是全场通用的Rint接收线，0.80 Å不是所有晶体的固定分辨率。

## 10. 独立测定供精修使用的晶胞和误差

```powershell
dials.two_theta_refine "<选定scaled.expt>" "<选定scaled.refl>" `
  output.cif=refined_cell.cif output.p4p=refined_cell.p4p
```

**输出**：新晶胞、标准不确定度、参与测定的反射数/θ范围及对应模型。

导出INS可能仍采用多序列的中位晶胞；要核对并将选定实测晶胞写入CELL、其误差写入ZERR后重新精修，CIF/FCF与模型统一。测量误差依赖当前仪器几何，不能把固定几何下的小误差当作已完成独立仪器标定。

## 11. 导出SHELX数据，准备进入Olex2

```powershell
dials.export "<选定scaled.expt>" "<选定scaled.refl>" `
  format=shelx intensity=scale shelx.composition=<当前正确分子式> `
  mtz.min_isigi=-999
```


建立新Olex2目录，将文件改成同一个基本名，例如`sample.ins`、`sample.hkl`。已有模型时用已论证的`.res/.ins`原子模型，配上**这次新HKL**，同步晶胞、ZERR、波长、对称及截止。确认不会误读旧HKL。


## 12. Olex2打开与解析

1. 打开配套`sample.ins`；已有完整模型则打开`sample.res`。
2. `Work → Solve`核对化学组成、晶胞、波长及空间群设定；从零解析时选择已配置的SHELXT，点击`Solve`。
3. 已有可靠模型的还原对照直接沿用该模型做精修；为了对比Rint不必反复重解结构。
4. 核对C/H/杂原子、分子连接、CH/CH2、保护基及目标图；Q峰不能只按高度或位置硬填成目标原子。
5. 出现两套分子时检查真实Z′、漏对称和基底变换，不能通过直接删掉一套来得到“一个分子”。


## 13. Olex2逐步精修

在`Work → Refine`明确选择SHELXL（需要复现时使用相同版本）。下面是Olex2命令栏操作，不是在PowerShell执行：

```text
refine 20
edit ins
edit lst
```

按模型成熟度进行：

1. 初步位置/元素确认，必要时先各向同性精修，查看连接、差图、占有率与尺度。
2. 非氢原子可靠后，在Toolbox中对适用原子设为anisotropic，再精修。`anis`作用于选中/指定原子；先确认选择范围。
3. 用Toolbox的`Add H`（或`hadd`）生成候选氢，逐个核对价态、CH/CH2/CH3和AFIX。羟基、水、胺H结合差图和化学环境处理。
4. 查看差图、椭球、非正定ADP、短接触和占有率。溶剂/无序/孪晶只在有证据时建立独立模型。
5. 逐轮比较完整R指标、强反射数、GooF、残峰、限制数和最后shift/su，而非只看屏幕上的R1。

Olex2命令和选择行为见[官方命令说明](https://www.olexsys.org/olex2/docs/reference/commands-manual/all-commands/)。精修参数和LST检查见[官方精修说明](https://www.olexsys.org/olex2/docs/tasks/tasks/structure-refinement/)。


## 14. 核查数据范围和权重，确认最后一轮收敛

在INS/RES核对SHEL、HKLF、MERG、WGHT。例如，高分辨率截止写作（数值仅为语法示例）：

```text
SHEL 999 0.80
```

它使用Å单位，示例中的数值须按当前数据另选；不是固定应加入每个项目的指令。数据还原已经截止时，仍须核对精修截止是否一致。

先记录当前实际WGHT；采用SHELXL下一轮建议值时重新精修。最后从LST最后循环读取shift/su、从RES/CIF核对实际权重；建议值不是已用值。有些摘要解析器取到首轮shift，应回读最后循环。


## 15. 生成配套CIF与FCF，补实验信息

SHELXL作为引擎时，Olex2的`Work → Refine → Refinement Settings Extra`选择ACTA，最后再精修以生成`.cif/.fcf`；具体布局可能随版本不同。核对LIST/MERG/FMAP与ACTA兼容。

在`Work → Report`核对仪器、波长、温度、晶体尺寸/颜色、组成、数据收集/还原软件、晶胞测定、吸收过程与范围。原采集软件可以保留，新还原不能继续写成旧SAINT/SADABS。

从实际校正提取Tmin/Tmax。相对经验因子须说明归一化及绝对透射未知；总体标度/衰减不能当吸收因子，晶体尺寸理论估算不能冒充实验范围。无法可靠提取则保留未知并报告缺项。新CIF的原子、内嵌INS/RES/HKL、FCF必须来自同一最终轮。

生成与报告入口见[Olex2最终整理说明](https://www.olexsys.org/olex2/docs/tasks/finalising-a-structure/)；实验范围应按[IUCr透射因子要求](https://iucrdata.iucr.org/x/services/authorchecklist.html)报告。

## 16. 配套验证与归档

1. 本地核对CIF语法、晶胞/波长/对称、原子与组成、实际权重、内嵌记录，以及FCF反射数。
2. 有当前样品外传授权时，向IUCr checkCIF提交完整CIF＋FCF（Olex2界面选择Send FCF）；缺授权时先完成本地核验和包，再确认上传。
3. 阅读结构因子报告：确认已收到FCF，重算R1、wR2、S和反射数与CIF一致。HTTP成功或CIF-only报告不代表FCF已验证。
4. 对A/B/C逐项判断：元数据遗漏据实补齐，结构问题回到模型，积分/一致性问题回到DIALS。每个修改后的文件都用新的配套报告。
5. 保存CIF/FCF/INS/RES/HKL/LST、完整报告、版本、哈希、排除清单与采用理由。CIF＋FCF单独打包便于手动提交，完整归档另存。


## 快速判断：该回到哪一层处理

| 现象 | 回到的步骤 |
|---|---|
| 帧打不开、基线/计数不合理 | 1–2：盘、格式和解码 |
| 背景被识别为斑点、索引失败 | 3–4：选点、掩膜、索引/基底 |
| 预测位置偏离、不同轮几何不一致 | 5：几何模型/原始帧核查 |
| 背景或前景失败、剖面拟合异常 | 6：积分/背景/峰形 |
| Rint高、等价反射不一致 | 7–9：对称、标度、吸收和异常观测 |
| 连接、H、ADP、无序或溶剂问题 | 12–14：原子模型精修 |
| CIF字段缺失、FCF和CIF不一致 | 15–16：配套输出和验证 |

继续试验应由具体异常支持；已无新证据时交付局限和重新采集所需信息，停止无目标“压R”。

按需选择数据、斑点、积分和标度参数见 [DIALS 决策说明](dials-decisions.md)；脚本见 [工具用法](dials-tools.md)。
