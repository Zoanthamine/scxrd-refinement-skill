# 交付包：依赖、完整性与重现

沿用 10_delivery 的 01_upload / 02_validation / 03_refinement_records / 04_figures / 05_documents 布局，不为整合另一技能强制更换目录。未加工原始数据可留在项目的只读来源包，以清单/哈希关联；用户要求完整原始包时再归集，外发另按已授权范围。

1. 指定当前候选及其配套 CIF/FCF/INS/RES/HKL/LST。读取末轮指标和实际协议；坐标、权重、数据筛选变化后重出相关文件。
2. 将必需 FAB、include 文件和方法/警报说明一并列出。原文件保持原样；重现目录中匹配基本名、相对 include 路径和真实来源。
3. 按已具备依赖的引擎重跑包内副本，核对统计和收敛，外部依赖运行不能用不支持 ABIN/include 的普通 03_run 代替。未重跑需明确标记。
4. 科学一致性由 CIF/FCF 核查、模型检查和适用验证报告支持；文件齐全和 A=0 均不等于可发表。
5. 打包新版本，验证 ZIP CRC，计算/核对 SHA-256；报告未解决问题。

```text
python scripts/10_delivery.py --outdir delivery_v2 --name sample --cif selected.cif --fcf selected.fcf --res selected.res --ins selected.ins --hkl selected.hkl --lst selected.lst --support selected.fab restraints.inc --notes refinement_notes.md --zip
python scripts/validate_crystal_package.py delivery_v2 --basename sample --zip delivery_v2.zip
```

support 仅提供当前实际需要的文件；FAB 按选定基本名归集，其余依赖保留文件名。INS/include 的相对目录必须与实际包内结构匹配，复杂嵌套依赖另准备专用重现目录再归档。无 FAB 的普通模型不要虚构 FAB。

validate_crystal_package 支持递归盘点当前或其他布局，检查六类基本文件、指定基本名、INS 中显式 ABIN/include 依赖、已有 DELIVERY_SHA256.csv，以及可选 ZIP 完整性。它不解析实际强度、不证明模型正确，也不声称全部嵌套依赖或实验来源已追溯；科学验证与包内重跑另做。

警报说明逐条记录：问题、文件/原子/反射证据、已做修正或未采用原因、剩余限制及需要的新实验；英文回复只从这些已核实事实生成，不套用他人的实验经历。
