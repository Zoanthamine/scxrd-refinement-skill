# scxrd-refinement

中文为主的单晶X射线诊断与精修Codex skill。根据当前输入选择直接SHELXL/Olex2精修，或启用DIALS原始帧还原分支；提供CIF/FCF核验、checkCIF留痕和归档工具。

## 使用

将此仓库克隆/复制到你的Codex技能目录，目录名保留`scxrd-refinement`；入口为[SKILL.md](SKILL.md)。默认支持按任务自动选择，也可以明确调用`$scxrd-refinement`。

```text
<CODEX_HOME>/skills/scxrd-refinement/SKILL.md
```

不自动安装或修改DIALS/SHELXL/Olex2，也不内置这些程序。路径与所有科学设置来自当前样品，详细依赖及跨平台用法见[工具说明](references/dials-tools.md)。

## 按需参考

| 内容 | 入口 |
|---|---|
| 完整16步：原始帧→选点→索引→几何→积分→标度→Olex2→验证归档 | [操作流程](references/dials-to-olex2.md) |
| 数据/帧/斑点选择、积分背景、标度、截止和异常观测 | [DIALS决策](references/dials-decisions.md) |
| DIALS运行、映射/诊断、候选筛选和吸收分量脚本 | [工具说明](references/dials-tools.md) |
| 化学、H、ADP、对称、无序、孪晶、构型和收敛 | [精修决策](references/refinement-decisions.md) |
| 分裂、多组分、特殊位置与几何/ADP限制 | [无序与占有率](references/disorder-and-occupancy.md) |
| 活泼H、孪晶输入、弥散溶剂及SQUEEZE依赖 | [案例分支](references/hydrogen-twin-solvent-cases.md) |
| 具体checkCIF警报调查与证据回复 | [警报处理](references/checkcif-case-triage.md) |
| 外部教程的来源、吸收范围和修正 | [教程说明](references/tutorial-sources.md) |
| SHELXL运行、元数据、checkCIF和归档命令 | [命令模板](references/workflow-recipes.md) |
| 多次实践的可迁移经验 | [实践经验](references/practice-lessons.md) |

研究数据和未公开样品不随包发布。历史样品的空间群、截断、删点与吸收参数不作为通用默认值；高Rint和checkCIF警报须回到当前证据处理。

## 检查

```text
python scripts/test_regressions.py
python scripts/test_dials_helpers.py
```

合成行为测试不联网，不产生科学结论。DIALS工具使用DIALS自带Python；吸收分量工具涉及内部API，须检查版本和分量乘积。正式结构图从Olex2/PLATON导出，未包含旧的简化绘图器。

发布前核验范围见[VALIDATION.md](VALIDATION.md)。本仓库的方法说明与脚本按MIT许可；外部程序、教程原文及媒体遵循各自许可。仅整理可迁移方法并引用来源，不分发教程原文或图片。
