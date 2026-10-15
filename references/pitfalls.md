# 排错与近期经验

## 运行

| 症状 | 处理 |
|---|---|
| ILLEGAL REFERENCE TO RESIDUE | 查孤立标题/时间戳，确认无科学意义后在副本删除；不白名单静默删除未知指令 |
| MISPLACED SYMM | 检查头部顺序；AFIX/PART/RESI 有上下文，不全文件重排 |
| BAD CONTINUATION / 行过长 | 保留前导空格，只在非末行保留 =；整条编辑原子/限制记录 |
| NO ATOMS / AFIX CONFLICT | 查丢失原子、插进 Uij 续行的 H、分组数量与闭合 |
| 数值参数报错 | 查当前手册；SIMU 支持第三个 dmax，不能和其他指令一概而论 |
| 同步锁/归档失败 | 临时目录运行；失败保留唯一结果，不删临时数据 |
| 超时/空 RES/无统计 | 停止该分支，不读旧输出冒充成功，不继续批处理 |
| 多份 HKL | 明确来源，不按大小或最低 R 自动选择 |
| 包导入失败 | 核对 Python ABI，不混用 Olex2 和其他解释器的二进制包 |
| PLATON GUI 挂起 | 是当前构建/调用方式限制，不推广为 PLATON 普遍不能命令行运行 |
| Olex2屏幕报错，根目录LST找不到 | 按本次任务的时间戳/调用日志找实际运行LST；旧版本可能在olex2/temp。读错误前后上下文和完整指令/续行，不认定上一行必是根因 |

指令以 [SHELXL 官方手册](https://shelx.uni-goettingen.de/shelxl_html.php) 为准，尤其 LATT、SHEL、SIMU、ACTA、AFIX 和占有率。

## 实践经验

按问题读取 [跨项目经验](practice-lessons.md)。历史候选和旧报告不是当前数据的默认结论。

外部案例的核实与修正见[教程来源](tutorial-sources.md)：带σ的DFIX/SUMP是限制而非硬边界/严格等式；负PART、SOF与特殊位置须区别；警报/空腔/Flack不是自动诊断。原案例只有图片/视频时，先取得实际模型和输入再复现。

## 工具限制

原始帧、解码、索引基底、dataset映射与误差回退见 [DIALS决策说明](dials-decisions.md)。特定样品的读取插件不随此通用skill分发；新格式必须重新独立验证。

01/06/07 与 xtal_core 是简化解析和几何初筛。特殊位置、FVAR 占有率、残基重复标签、PART 连接、非正交 ADP、合并口径需独立复核，必要时用 SHELXL/Olex2、Gemmi 或专用程序。

正式椭球图用 Olex2/PLATON 从选定模型导出，核对元素、标签、组分、对称和概率。旧的简化绘图器已从公开包移除，避免输出不能核验的正式图。
