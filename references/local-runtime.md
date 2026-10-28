# 本机运行与工具分工

## 配置入口

安装在用户 Codex home 且存在 `tools/science/INTEGRATION.md` 时，先读取该文件与 `environments.json`；它们维护有效解释器、程序路径、环境变量及能力边界。本参考只规定调用方式，不复制程序盘符、版本或样品参数。未配置统一入口的机器沿用已验证环境与脚本的显式参数。

示例变量由当前安装位置获得；`$Skill` 为实际 skill 目录，不是样品目录：

```powershell
$Skill = '<当前 scxrd-refinement 目录>'
$CodexRoot = Split-Path (Split-Path $Skill -Parent) -Parent
$Launcher = Join-Path $CodexRoot 'tools/science/science.ps1'
$Scripts = Join-Path $Skill 'scripts'
Get-Content -LiteralPath (Join-Path $CodexRoot 'tools/science/INTEGRATION.md')
& $Launcher status
& $Launcher science (Join-Path $Scripts '01_diagnose.py') '<样品目录>'
& $Launcher science (Join-Path $Scripts '03_run.py') --help
& $Launcher dials -m dials.command_line.version
& $Launcher dials (Join-Path $Scripts 'dials_audit.py') --help
```

- `science` 用于常规诊断、SHELXL 运行/汇总、CIF、在线验证及归档脚本；`dials` 用于实际依赖 DIALS/cctbx/dxtbx 的分析。
- `dials_stage.py` 本身使用标准库，可走 science；子程序定位优先级为显式 `--dials-bin`、环境变量 `DIALS_BIN`、PATH。配置路径失效时报错，先修复当前配置，避免静默切换到另一套程序。
- 通过统一入口得到的 SHELXL_EXE 等变量只选择程序，不替样品设置空间群、化学组成、分辨率或删点规则。
- `--help`、版本查询及合成测试验证程序可调用；实际帧格式、仪器几何和吸收模型兼容性仍需按当前数据检查。
- 工作目录选择当前研究项目的新子目录；独立报告/导出遵循用户指定输出位置。启动器和科研配置的临时目录随环境生效。

## 输入证据决定可做的工作

| 输入 | 支持的下一步 | 先查清的边界 |
|---|---|---|
| 完整原始衍射帧与实验几何 | 解码、索引、积分、标度对照 | 读取与几何核实后才继续；校准用掩膜/背景图不当作样品衍射序列 |
| 配套积分 expt/refl | 基底/identifier 核查、标度及异常诊断 | 积分强度不等于原始像素；无法据此重做缺失帧的积分 |
| 已校正 HKL 与模型/晶胞 | SHELXT 解结构、SHELXL/Olex2 精修 | 无原始帧时，对上游积分/多晶域重叠保留限制 |
| CIF/RES，无配套强度 | 几何、组成、对称线索与文件诊断 | 不据坐标重跑程序就声称完成新的实验精修；先找回强度来源 |

## 整合后的任务入口

scxrd-refinement 统一组织还原、初始解、精修和交付。输入分级、配体拓扑与交付工具已经并入本包，无需另装来源技能；分别读[解结构与配体](solution-and-ligand.md)、[孪晶调查](twin-investigation.md)和[交付核查](package-audit.md)。

PLATON/GUI 能力按实际构建验证，不把另一平台的记录当作本机验收。
