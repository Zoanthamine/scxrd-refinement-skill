# 方法整合来源与核查范围

2026-10-28：参考本地安装的 [solve-single-crystal-skill](https://github.com/owenxyzhang-seseTJ/solve-single-crystal-skill)，重点学习输入证据分级、配体参考、孪晶调查和交付重现思路。新增脚本独立实现，没有直接复制其未明确许可的代码、原文、图片或案例数据；本包的科学参数仍由当前样品决定。

整合到本包：
- [初始结构与配体](solution-and-ligand.md)：只读目录/ZIP 盘点、SFRM 校准/未知分类、SHELXT 候选比较和 RDKit 参考几何。
- [孪晶调查](twin-investigation.md)：数据可支持范围、候选律、PLATON/FCF 版本差异与日志记录。
- [交付核查](package-audit.md)：沿用当前布局，核对基本文件、显式依赖、哈希、ZIP 和重跑证据。
- [可选本机入口](local-runtime.md)：只引用外部环境配置，不把个人路径写入公开包。

按[官方 SHELXL 指令](https://shelx.uni-goettingen.de/shelxl_html.php)修正来源材料中关于 TWIN 负号/退孪晶、SWAT、BASF 边界的过度简化；来源中的固定金属框架建模顺序、必须全部候选群、必须退孪晶、A 警报归零门槛也未推广为所有晶体的固定规则。

测试范围记录在仓库 VALIDATION.md。本轮新增方法检查不等于重新验收全部仪器格式、PLATON 构建、实际样品精修或在线投稿，也不依赖用户另装 solve-single-crystal 才能阅读和运行本包新增工具。
