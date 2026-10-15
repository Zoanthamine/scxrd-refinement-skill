# 教程来源、吸收范围与修正

本轮以Tokyo公众号的本地Markdown整理件作为问题线索：目录121篇，选择下表32篇的可读文字或资源索引；没有读取远端图片/视频，也没有下载并重跑原案例衍射数据。索引/链接不等于完整教程内容。以下参考是独立整理的通用方法，不附转载原文和图片。

## 如何使用

- 需要分裂/特殊位置/多组分时读[无序与占有率](disorder-and-occupancy.md)。
- 遇到质子转移、孪晶或弥散溶剂时读[案例分支](hydrogen-twin-solvent-cases.md)。
- 处理具体警报与回复时读[checkCIF调查](checkcif-case-triage.md)。
- 视频目录仅用来定位后续学习材料；截图中的未读数值/坐标/按钮操作不写成已验证步骤。

## 原文中的内容如何处理

| 线索 | 吸收或修正 |
|---|---|
| 020/030：限制与约束 | 统一用英文辨别：restraint有权重，constraint是严格参数关系；RIGU并非所有异常ADP的默认解法 |
| 113–116：对称元素上的分裂 | 吸收先Grow检查完整组分、再核对ASU的思路；负PART、占有率、多重性按当前群核算，不复制0.5或1/12 |
| 115：12个相关位置 | 不解释成12重旋转轴，按实际群操作、位点稳定子和轨道核查 |
| 119：两组分及共享H | 吸收FVAR/互补SOF与H随构象检查；原文0.7358的补数应为0.2642，旧例数字不作为默认比例 |
| 120：三组分 | SUMP是带σ的限制，不是精确总和；不用不断缩小σ来强行让化学式显示整数 |
| 121：DFIX/DANG与角度 | 吸收余弦定理推导思路；文中2.426写成4.426为笔误，部分TRIA示例两边长度也需复核；理想109.5°不是实际THF通用目标 |
| 026：指标 | 保留指标与文件互查；残峰超过1、绿色指示或GooF接近1均不单独裁决模型好坏 |
| 018：Z/Z′ | Z按每晶胞所报化学式单元定义，不能称作独立分子数；GUI改Z′不能代替组成核对 |
| 032/039/042：加H | 吸收差图/几何/价态联合判断；不把旧辅助选原子命令或固定C–O阈值用于所有样品 |
| 062/117：孪晶 | 区分反演、可支持的TWIN协议与部分重叠HKLF5；警报和低R不能替代数据格式/物理适用性核验 |
| 118：SQUEEZE | 空腔不是溶剂存在的独立证据，mask不是从样品中去掉溶剂；按实际版本检查.fab/ABIN或其他输出依赖 |
| 001–003/106：回复和投稿 | 提炼证据记录方法，不搬用他人的重测经历、默认解释、旧版本或统一投稿要求；003是2021年目录 |
| 060：运行失败 | 吸收找实际运行LST的思路；temp路径随版本变，报错上一行不是所有错误的通用根因 |
| 090：手建p4p | 仅作输入格式便利，不是重新测定晶胞，更不能产生实测误差和反射统计 |

## 官方核对入口

- [SHELXL指令](https://shelx.uni-goettingen.de/shelxl_html.php)：PART、FVAR/SOF、DFIX/DANG/SUMP、HKLF/TWIN/BASF、TEMP与ABIN等。
- [Olex2无序建模](https://www.olexsys.org/olex2/docs/concepts/refinement/disorder/modelling_disorder/)与[PART/占有率](https://www.olexsys.org/olex2/docs/concepts/refinement/disorder/parts_and_occupancies/)。
- [Olex2孪晶](https://www.olexsys.org/olex2/docs/tasks/tasks/twinned-structures/)与[溶剂掩膜](https://www.olexsys.org/olex2/docs/tasks/solvent-masking/)。
- [IUCr检查目录](https://iucrdata.iucr.org/x/services/cif/datavalidation.html)与[Z字典定义](https://www.iucr.org/__data/iucr/cifdic_html/1/cif_core.dic/Icell_formula_units_Z.html)。
- [Spek 2015 SQUEEZE方法论文](https://journals.iucr.org/c/issues/2015/01/00/ln3172/)。

核对日期：2026-10-15。软件具体操作按当前版本复核；本轮未改执行脚本或重新验证历史结构。

## 原始教程索引

编号沿用本地整理件，仅供定位；账户Tokyo。链接来自文章元数据，原文与媒体版权归原作者。远端链接可用性本轮未逐条测试。

| 编号 | 文章 | 原刊日期 |
|---|---|---|
| 001 | [DIFMN02和PLAT098回应No.1](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247484994&idx=1&sn=96f725ff457b9e9439d2c605e25ca48a) | 2020-04-16 |
| 002 | [部分CheckCif警告解释示例No.1](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247484998&idx=1&sn=ad939494d825e1c69bdb7aee4ee7bc04) | 2020-04-18 |
| 003 | [(IUCr) checkCIF所有检查内容汇总及解决策略和解释案例](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247488407&idx=1&sn=33619913f2731b207c1061cb5cc69c46) | 2021-05-06 |
| 017 | [Olex2中在CIF中嵌入hkl和res数据](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247483990&idx=1&sn=c6edd3396eab5cd39cfbe24660fb4d63) | 2019-01-15 |
| 018 | [Olex2中的Z'与Z](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247484012&idx=1&sn=79d52cac060659aa325c2c98eb889a82) | 2019-01-21 |
| 020 | [Olex2中如何添加和编辑约束与限制](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247484078&idx=1&sn=849f99d89b607627493e1a3e45b4ddf2) | 2019-02-05 |
| 026 | [Olex2中GUI面板上显示的各项指标](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247484268&idx=1&sn=751558cd4ca107d7c714abf272ac84d6) | 2019-03-01 |
| 030 | [Olex2无序处理示例2](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247484326&idx=1&sn=e5bace4170ce29a8743c34b404be9fa8) | 2019-03-08 |
| 032 | [羧基氢原子位置的确定](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247484321&idx=1&sn=6737a2afca92c471ca1147e4d0a76b40) | 2019-03-06 |
| 038 | [电子密度图及一个孪晶处理示例](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247484397&idx=2&sn=f9c5e115f88fefd4d430d2ffcbc37bff) | 2019-03-19 |
| 039 | [Olex2中铵根离子加氢技巧](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247484405&idx=1&sn=d0512af431761b4adce2d91b3245791c) | 2019-03-20 |
| 042 | [Olex2中如何加氢](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247484447&idx=1&sn=88dd9ec76462a435a8e4c830f8caf3a5) | 2019-03-25 |
| 043 | [Olex2官网无序示例数据](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247484485&idx=1&sn=b56f4e702fd00348faf3d7e6e54361d8) | 2019-04-04 |
| 060 | [Olex2精修时如何查找问题所在](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247485518&idx=3&sn=84167dfa557a92ef0135ef54ac1ba38d) | 2021-02-28 |
| 061 | [Olex2中强制ShelXT在指定空间群下解析结构](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247487511&idx=1&sn=9b1cbd87258a6e90fb6777212d608851) | 2021-04-17 |
| 062 | [Olex2和Platon-一个简单的孪晶处理示例](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247487904&idx=1&sn=86b7477ef718170a4d49e452ffef82b2) | 2021-04-24 |
| 080 | [使用自由变量和限制(目录+链接)](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247485542&idx=1&sn=6897c8ec9cf433e4c2e86a079801867c) | 2021-03-03 |
| 084 | [晶体解析与精修—结构验证](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247484177&idx=1&sn=e0189ff86637a446575e00edbf36cb8b) | 2019-02-22 |
| 086 | [checkCIF-警告条目组成](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247484245&idx=1&sn=c0244da02491eb4304cbc38ba92268f0) | 2019-02-26 |
| 087 | [晶体学中的R因子](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247484308&idx=1&sn=59705c3ab148e5cca21fe10f75022f26) | 2019-03-04 |
| 090 | [手动创建p4p文件进行单晶解析](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247484571&idx=1&sn=ba6bf3e67b7e30ad44730c60110dfa74) | 2019-04-16 |
| 105 | [文章行文-单晶解析精修描述](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247484353&idx=1&sn=faa38d76f61bc3989c0c54fca56df379) | 2019-03-11 |
| 106 | [一些完全可以避免的审稿意见](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247484535&idx=1&sn=80069a4f25ce161b35a604ff2f3229f4) | 2019-04-14 |
| 113 | [特殊无序处理](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247483848&idx=1&sn=ca4ac161f85e624f919b6d15eb6a40ea) | 2018-12-27 |
| 114 | [特殊无序处理-实战示例1](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247483876&idx=1&sn=3e9edb06a0760e6aad1115e6628a8379) | 2018-12-28 |
| 115 | [特殊无序处理-实战示例2](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247483919&idx=1&sn=c657998a6ae2f26202b41af56aba7e73) | 2019-01-01 |
| 116 | [萘环-穿过对称元素的无序处理实例1](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247484056&idx=1&sn=c61059a6957761265e39a2c7ed82075f) | 2019-01-28 |
| 117 | [简单孪晶处理](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247484205&idx=1&sn=4fb0666596216c75b23ea2b56df932ec) | 2019-02-23 |
| 118 | [简单无序及SQUEEZE操作步骤](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247484237&idx=1&sn=1ad4329795bc4d5fe0d4d2ccf3fff2f8) | 2019-02-25 |
| 119 | [位置无序处理及其简单理解](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247484671&idx=1&sn=efd92395b385171ffaf7eb0ed14c8cce) | 2019-04-26 |
| 120 | [一个三组分无序示例](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247484776&idx=1&sn=03267e23e006feeed446366b208428d6) | 2019-04-29 |
| 121 | [以THF为例详细讲解各个键长键角限制参数的由来](https://mp.weixin.qq.com/s?__biz=MzU0NjkzMTM1MQ%3D%3D&mid=2247487194&idx=1&sn=a003a5f82be458b25b7db47ac5613b02) | 2021-04-11 |
