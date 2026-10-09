#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
01_diagnose.py — SCXRD 数据与模型诊断（动手精修之前必跑）

检查内容：
  1. 目录清点：ins / res / hkl / lst / cif 是否齐全，res/lst 是否 0 字节
  2. 修复隐患：EXTI+SWAT 冲突、TITL 与 LATT 空间群不一致、UNIT 与原子表不匹配
  3. 数据质量：Rint / Rsigma / I>2σ 比例 / 分辨率壳层 / 负强度比例
  4. 数据裁决：目录内多份 hkl 是否为同一数据（整体缩放 or 真差异）
  5. 模型合理性：连通分量、配位数、Uij 正定性、异常 Ueq、H 计数
  6. 输出可执行建议

用法:
  python 01_diagnose.py <数据目录>
  python 01_diagnose.py <job.ins> [<job.hkl>]
"""
import os, re, sys, math, glob
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xtal_core import (read_lines, read_res, read_hkl, hkl_rint, shell_stats,
                       bonds, contacts, COV, VDW, MASS, is_atom_line)

W = 100
def h(t):
    print("\n" + "=" * W)
    print(t)
    print("=" * W)

def rule(t=""):
    print("-" * W + ((" " + t) if t else ""))


def pick_files(target):
    """定位 ins/res/hkl/lst。"""
    if os.path.isfile(target):
        base = target
        d = os.path.dirname(os.path.abspath(target)) or '.'
    else:
        d = os.path.abspath(target)
        # 优先 ins，其次 res，再退到「有 hkl 的目录」
        base = None
        for pat in ('*.ins', '*.res'):
            cands = [p for p in glob.glob(os.path.join(d, pat))
                     if os.path.getsize(p) > 0]
            if cands:
                base = max(cands, key=os.path.getmtime)
                break
        if base is None:
            hkls = glob.glob(os.path.join(d, '*.hkl'))
            if hkls:
                print(f"!! 目录中只有 hkl、没有 ins/res —— 只能做数据质量检查")
                base = os.path.splitext(max(hkls, key=os.path.getsize))[0] + '.res'
            else:
                print(f"!! 目录中既没有 ins/res 也没有 hkl: {d}")
                sys.exit(1)
    stem = os.path.splitext(base)[0]
    out = {'dir': d, 'ins': None}
    for ext in ('ins', 'res', 'hkl', 'lst', 'cif', 'fcf'):
        p = stem + '.' + ext
        out[ext] = p if os.path.exists(p) else None
    # hkl 名字常与 res 不同（_a.hkl / 0ma.hkl 等），按体积兜底
    if not out['hkl']:
        g = sorted(glob.glob(os.path.join(d, '*.hkl')),
                   key=lambda p: -os.path.getsize(p))
        if g:
            out['hkl'] = g[0]
    # res 也可用 ins 兜底
    if not out['res'] and out['ins']:
        out['res'] = out['ins']
    return out


def check_ins_health(ins_path):
    """结构性检查：0 字节、EXTI/SWAT 冲突、TITL/LATT 矛盾、UNIT 失配。"""
    issues = []
    if not ins_path or not os.path.exists(ins_path):
        return ["找不到 ins 文件"], {}
    if os.path.getsize(ins_path) == 0:
        return ["ins 为 0 字节 —— 上次 SHELXL 未正常写出（常见于指令冲突）"], {}

    txt = read_lines(ins_path)
    info = {}
    has = defaultdict(list)
    for ln in txt:
        u = ln.strip().split()[0].upper() if ln.strip() else ''
        has[u].append(ln.strip())

    if has.get('EXTI') and has.get('SWAT'):
        issues.append("同时存在 EXTI 与 SWAT（互斥）→ 删掉两者或只留一个，否则 res 为 0 字节")
    if has.get('LATT'):
        latt = has['LATT'][0].split()[1]
        titl = has.get('TITL', [''])[0]
        m = re.search(r'\bin\s+(\S+)', titl)
        sg = m.group(1) if m else '?'
        if latt == '-1' and re.search(r'\bP\s*1\b|P1$', sg):
            issues.append(f"TITL 写 P1 但 LATT -1（中心对称）→ 空间群不自洽")
        if latt == '1' and 'P-1' in sg:
            issues.append(f"TITL 写 P-1 但 LATT 1 → 空间群不自洽")
    if has.get('FVAR'):
        v = has['FVAR'][0].split()
        if len(v) > 1:
            try:
                fv = float(v[1])
                info['fvar'] = fv
                if abs(fv) > 0.9 and abs(fv - 1.0) > 0.15:
                    issues.append(f"FVAR = {fv:.4f} 远离 1.0 —— 若模型无消光/孪晶需求，"
                                  f"检查是否误用为占位；注意 FVAR 不改变分子内几何")
            except ValueError:
                pass
    return issues, info


def check_unit_vs_atoms(cr):
    """UNIT 与原子表是否一致（SHELXL 会报 'Cell contents ... do not agree'）。"""
    if not (cr.unit and cr.sfac):
        return None
    cnt = Counter()
    for a in cr.atoms:
        cnt[a.el] += 1
    # 对称操作数
    nsym = max(1, len(cr.symm))
    rows = []
    ok = True
    for el, u in zip(cr.sfac, cr.unit):
        got = cnt.get(el, 0) * nsym
        rows.append((el, u, got))
        if u != got:
            ok = False
    return dict(ok=ok, rows=rows, nsym=nsym)


def check_model(cr):
    """配位数、Uij 正定性、异常 Ueq、分子连通分量。"""
    bl = bonds(cr, exclude_h=True)
    deg = defaultdict(int)
    for x, y, d, ff in bl:
        deg[x.label] += 1
        deg[y.label] += 1
    bad_deg = []
    for a in cr.atoms:
        if a.is_h():
            continue
        d = deg[a.label]
        if a.el == 'C' and d not in (1, 2, 3, 4):
            bad_deg.append((a.label, a.el, d))
        elif a.el == 'O' and d not in (1, 2):
            bad_deg.append((a.label, a.el, d))
        elif a.el in ('N',) and d not in (1, 2, 3, 4):
            bad_deg.append((a.label, a.el, d))
        elif a.el in ('Si', 'S') and d not in (2, 3, 4):
            bad_deg.append((a.label, a.el, d))

    npd, high = [], []
    for a in cr.atoms:
        if a.is_h() or not a.uij:
            continue
        u = a.uij
        if any(u[i][i] <= 0 for i in range(3)):
            npd.append(a.label)
        for (p, q, r) in ((0, 1, 2), (0, 1, 1), (0, 2, 2), (1, 2, 2)):
            pass
        # 正定条件 |Uij| < sqrt(Uii*Ujj)
        for i, j in ((0, 1), (0, 2), (1, 2)):
            if abs(u[i][j]) >= math.sqrt(max(u[i][i]*u[j][j], 1e-12)):
                npd.append(a.label)
                break
        if a.ueq() > 0.10:
            high.append((a.label, a.ueq()))

    heavy = [a for a in cr.atoms if not a.is_h()]
    comps = defaultdict(list)
    if heavy:
        parent = {a.label: a.label for a in heavy}
        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for x, y, d, ff in bl:
            parent[find(x.label)] = find(y.label)
        for a in heavy:
            comps[find(a.label)].append(a.label)

    return dict(nbond=len(bl), bad_deg=bad_deg, npd=sorted(set(npd)),
                high=sorted(high, key=lambda t: -t[1]),
                comps=sorted([sorted(v) for v in comps.values()],
                             key=len, reverse=True))


def hkl_compare(paths):
    """多份 hkl 是否同一数据（整体缩放）。"""
    if len(paths) < 2:
        return None
    sets = {}
    for p in paths:
        d = {}
        for ln in read_lines(p):
            q = ln.split()
            if len(q) != 5:
                continue
            try:
                d[(int(q[0]), int(q[1]), int(q[2]))] = (float(q[3]), float(q[4]))
            except ValueError:
                continue
        sets[p] = d
    res = []
    keys = list(sets)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            A, B = sets[keys[i]], sets[keys[j]]
            common = set(A) & set(B)
            if not common:
                res.append((keys[i], keys[j], None, "无共同反射"))
                continue
            ratios = []
            for k in common:
                fa, fb = A[k][0], B[k][0]
                if abs(fb) > 1e-9:
                    ratios.append(fa/fb)
            ratios.sort()
            med = ratios[len(ratios)//2]
            dev = [abs(A[k][0]/med - B[k][0])/max(abs(B[k][0]), 1e-6) for k in common]
            dev.sort()
            same = dev[int(len(dev)*0.9)] < 0.01
            res.append((keys[i], keys[j], med,
                        f"一致(整体×{med:.4f})" if same else
                        f"不同数据 (90%分位偏差 {dev[int(len(dev)*0.9)]:.3f})"))
    return res


# ================================================================ 主流程
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    target = sys.argv[1]
    f = pick_files(target)

    h(f"1. 目录清点 — {f['dir']}")
    for k in ('ins', 'res', 'hkl', 'lst', 'cif', 'fcf'):
        p = f.get(k)
        if p:
            print(f"  {k:4}: {os.path.basename(p):40} {os.path.getsize(p):>12,} 字节")
        else:
            print(f"  {k:4}: (缺失)")
    if f['res'] and os.path.getsize(f['res']) == 0:
        print("  !! res 为 0 字节 —— 上次 SHELXL 未正常结束，不要在其基础上继续")
    if f['lst'] and os.path.getsize(f['lst']) == 0:
        print("  !! lst 为 0 字节 —— 同上")

    h("2. ins 健康检查")
    issues, info = check_ins_health(f['ins'])
    if issues:
        for x in issues:
            print("  !! " + x)
    else:
        print("  未发现指令冲突")

    # 解析结构
    src = f['res'] if (f['res'] and os.path.getsize(f['res']) > 0) else f['ins']
    if not src:
        print("\n没有可解析的 ins/res，终止。")
        return
    print(f"\n  (以 {os.path.basename(src)} 为模型来源)")
    cr = read_res(src)

    h("3. 晶胞 / 空间群 / 组成")
    if cr.cell:
        print(f"  CELL  = {cr.cell[0]:.4f} {cr.cell[1]:.4f} {cr.cell[2]:.4f} "
              f"{cr.cell[3]:.2f} {cr.cell[4]:.2f} {cr.cell[5]:.2f}")
        print(f"  V     = {cr.volume():.2f} A^3")
    print(f"  SYMM  = {len(cr.symm)} 个操作(含恒等) "
          f"-> 若 LATT=-1 且 TITL 给出中心对称群属正常")
    print(f"  SFAC  = {cr.sfac}")
    print(f"  UNIT  = {cr.unit}")
    nheavy = sum(1 for a in cr.atoms if not a.is_h())
    nh = sum(1 for a in cr.atoms if a.is_h())
    print(f"  原子  = 重原子 {nheavy} + H {nh} = {len(cr.atoms)}")
    uv = check_unit_vs_atoms(cr)
    if uv:
        print("\n  UNIT vs 原子表×对称操作:")
        for el, want, got in uv['rows']:
            flag = "" if want == got else "   <-- 不一致！"
            print(f"    {el:3} UNIT={want:>6}  实际={got:>6}{flag}")
        if not uv['ok']:
            print("  → SHELXL 会报 'Cell contents from UNIT instruction and atom list "
                  "do not agree'；请核对占有率、特殊位置、Z 和组成；不要按标签数直接改 UNIT")

    h("4. 模型合理性")
    m = check_model(cr)
    print(f"  共价键数(不含 H): {m['nbond']}")
    print(f"  分子连通分量(原子数): {[len(x) for x in m['comps']]}")
    if len(m['comps']) > 1:
        print("    → Z'>1 或多个独立分子/溶剂；确认是否为共晶或未建模的溶剂")
    if m['bad_deg']:
        print("  配位数异常原子:")
        for lab, el, d in m['bad_deg']:
            print(f"    {lab:6} ({el}) deg={d}   <-- 检查原子类型或缺失原子")
    else:
        print("  配位数全部正常")
    print(f"  Uij 非正定原子: {m['npd'] if m['npd'] else '无'}")
    if m['high']:
        print("  Ueq > 0.10 的原子（提示无序/过大热运动）:")
        for lab, u in m['high'][:15]:
            print(f"    {lab:6} Ueq = {u:.4f}")
        print("    → 优先尝试 RIGU/SIMU 约束；若残峰明显再考虑无序拆分")
    else:
        print("  无 Ueq > 0.10 的原子")

    # H 处理
    h("4b. 氢原子")
    hh = [a for a in cr.atoms if a.is_h()]
    oh = [a for a in hh if not a.uiso is None]
    print(f"  H 总数: {len(hh)}")
    print(f"  自由精修(有 Uiso 值而非负 AFIX 代码): {len(oh)}"
          f"  {[a.label for a in oh]}")
    ohx = [a for a in hh if a.label.startswith('H') and a.uiso is None]
    print(f"  骑式(AFIX 负值): {len(ohx)}")
    # O-H 距离检查
    for a in cr.atoms:
        if a.el in ('O', 'N'):
            for b in hh:
                d = math.dist(a.cart, b.cart)
                if 0.6 < d < 1.3:
                    w = ""
                    if a.el == 'O' and not (0.75 <= d <= 1.00):
                        w = "   <-- O-H 键长异常（典型 0.82-0.98），可用 DFIX/AFIX 147 规范化"
                    print(f"    {a.label}-{b.label} = {d:.3f} A{w}")

    h("5. 衍射数据质量")
    if not f['hkl']:
        print("  未找到 hkl 文件，跳过")
    else:
        rows = read_hkl(f['hkl'])
        print(f"  文件: {os.path.basename(f['hkl'])}   记录数: {len(rows)}")
        if rows and cr.cell:
            allhkl = [(h, k, l) for h, k, l, _, _ in rows]
            hmax = max(abs(h) for h, k, l in allhkl)
            kmax = max(abs(k) for h, k, l in allhkl)
            lmax = max(abs(l) for h, k, l in allhkl)
            print(f"  |h|max={hmax}  |k|max={kmax}  |l|max={lmax}")
            rt = hkl_rint(rows, cr.cell)
            print(f"  Rint(本工具按点群+Friedel) = {rt['rint']:.2f}%   "
                  f"Rsigma = {rt['rsigma']:.2f}%")
            print(f"  参与统计的反射 {rt['nref']}，等价类 {rt['ngroups']}")
            gt2 = sum(1 for h, k, l, fo, s in rows if s > 0 and fo > 2*s)
            print(f"  I>2sigma 比例 = {gt2/len(rows)*100:.1f}%")
            neg = sum(1 for h, k, l, fo, s in rows if fo < 0)
            print(f"  负 Fo^2 比例 = {neg/len(rows)*100:.1f}%")
            print("\n  分辨率壳层统计:")
            print(f"    {'d range':>13} {'N':>7} {'I>2s%':>7} {'I>3s%':>7} "
                  f"{'medI/s':>8} {'meanFo2':>10}")
            for s in shell_stats(rows, cr.cell):
                print(f"    {s['lo']:6.2f}-{s['hi']:6.2f} {s['n']:7d} "
                      f"{s['gt2']:7.1f} {s['gt3']:7.1f} {s['med_isig']:8.2f} "
                      f"{s['mean_fo2']:10.1f}")
            # 判读
            print("\n  判读:")
            rt_pct = rt['rint']
            if rt_pct > 12:
                print(f"    !! Rint = {rt_pct:.1f}% 偏高（本工具合并口径，需核对积分报告）"
                      f" —— 需区分数据问题、对称性和模型问题，不能据此预测 Flack 精度")
            elif rt_pct > 7:
                print(f"    !  Rint = {rt_pct:.1f}% 中等偏高")
            else:
                print(f"    OK Rint = {rt_pct:.1f}%")
            hi = [s for s in shell_stats(rows, cr.cell) if s['lo'] < 0.95]
            if hi and sum(s['gt2'] for s in hi)/len(hi) < 40:
                print("    !! 0.80-0.95 A 壳层 I>2sigma 很低 —— 高角较弱："
                      "\n       → 不要仅凭强反射比例决定截断；必要时独立进行正确分辨率范围的对照"
                      "\n       → 保留全数据，如实报告数据局限")

    h("6. 多份 hkl 裁决")
    allhkl = sorted(glob.glob(os.path.join(f['dir'], '*.hkl')))
    if len(allhkl) > 1:
        for p in allhkl:
            print(f"  {os.path.basename(p):45} {os.path.getsize(p):>12,} 字节")
        cmp = hkl_compare(allhkl)
        for a, b, med, txt in cmp or []:
            print(f"  {os.path.basename(a)} vs {os.path.basename(b)}: {txt}")
        if cmp and all('一致' in c[3] for c in cmp):
            print("  → 全部为同一数据（仅整体缩放）：还需核对 sigma 缩放、Friedel 对、重复记录和处理来源")
        else:
            print("  → 存在真实差异，需追溯来源并做同口径对照，不能只按 wR2 选数据")
    else:
        print(f"  只有 {len(allhkl)} 份 hkl")

    h("7. 结论与建议")
    print("""
  动手前请确认：
    [ ] UNIT 与原子表一致（结合占有率和特殊位置核对）
    [ ] 无 EXTI/SWAT 冲突
    [ ] 空间群自洽（TITL vs LATT vs SYMM）
    [ ] 已记录基线 R1/wR2/GooF（用于对比后续每一轮）
  推荐下一步：
    1) 复制原始文件到 work/rNN_xxx/ 归档（绝不原地改原始数据）
    2) python 03_run.py --base <res> --hkl <hkl> --stage r01_baseline --dir work
    3) 核对归档的 INS、LST 和基线指标，再建立单议题分支
  若 Rint 偏高：检查数据和模型；是否加限制或截断须有独立证据。
""")


if __name__ == '__main__':
    main()
