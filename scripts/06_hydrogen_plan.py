#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
06_hydrogen_plan.py — 依据连接性自动规划氢原子（HFIX 分组）

来自多次模型精修与交付实践：
  * 按共价阈值建连接表
  * 每个碳按 价键数 + 是否不饱和（C=O/C=C 等）推断应有的 H 数
  * 生成 HFIX 分组：13(叔 CH) / 23(仲 CH2) / 43(芳或烯 CH) / 137(甲基，最优取向)
  * 交叉核对 UNIT 中的 H 总数，报告不一致

同时也报告：
  * 分子连通分量（判断 Z'、是否有多余溶剂分子）
  * O/N 上的可解离氢（建议用差峰或 AFIX 147）
  * 疑似原子类型错误（如把甲基碳建成 O）

用法:
  python 06_hydrogen_plan.py <res|ins> [--expect-h N] [--print-ins]
"""
import os, re, sys, argparse, math
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xtal_core import read_res, COV, VDW

# 共价判键阈值（元素对 -> 距离上限 Å）
BOND_LIMIT = {
    ('C', 'C'): 1.80, ('C', 'O'): 1.72, ('C', 'N'): 1.68, ('C', 'Si'): 2.15,
    ('C', 'S'): 1.90, ('C', 'Cl'): 1.85, ('C', 'Br'): 2.00, ('C', 'I'): 2.18,
    ('C', 'F'): 1.60, ('O', 'Si'): 2.00, ('O', 'O'): 1.60, ('N', 'Si'): 2.00,
    ('Si', 'Si'): 2.60, ('S', 'O'): 1.75, ('C', 'H'): 1.25, ('O', 'H'): 1.15,
    ('N', 'H'): 1.15, ('Si', 'H'): 1.65,
}
# 不饱和判据
UNSAT = {('C', 'O'): 1.34, ('C', 'N'): 1.34, ('C', 'C'): 1.44}


def build_adj(cr, exclude_h=False):
    ats = [a for a in cr.atoms if not (exclude_h and a.is_h())]
    adj = defaultdict(list)
    for i, x in enumerate(ats):
        for y in ats[i + 1:]:
            key = tuple(sorted((x.el, y.el)))
            lim = BOND_LIMIT.get(key)
            if lim is None:
                lim = (COV.get(x.el, 0.8) + COV.get(y.el, 0.8)) * 1.35 + 0.1
            d, ff = cr.nearest(x.frac, y.frac)
            if 0.05 < d < lim:
                adj[x.label].append((y.label, y.el, d))
                adj[y.label].append((x.label, x.el, d))
    return adj, ats


def plan_hydrogens(cr, verbose=True):
    adj, ats = build_adj(cr, exclude_h=True)
    heavy = [a for a in ats if not a.is_h()]
    plans = {13: [], 23: [], 43: [], 137: [], 'OH': []}
    total_h = 0
    detail = []
    for a in heavy:
        if a.el != 'C':
            continue
        nb = adj[a.label]
        deg = len(nb)
        unsat = any(e == 'O' and d < UNSAT[('C', 'O')] for _, e, d in nb) or \
                any(e == 'C' and d < UNSAT[('C', 'C')] for _, e, d in nb)
        if deg == 1:
            h, afix = 3, 137                 # 甲基
        elif unsat and deg <= 3:
            h, afix = max(0, 3 - deg), 43    # 羰基/烯碳：sp2
        else:
            h = max(0, 4 - deg)
            afix = {1: 13, 2: 23, 3: 137}.get(h)   # 叔 CH / 仲 CH2 / 异常
        if afix == 137 and deg > 1:
            afix = None                      # 已是不饱和端基时不再当甲基
        total_h += h
        detail.append((a.label, a.el, deg, unsat, h, afix,
                       sorted(nb, key=lambda t: t[2])))
        if afix:
            plans[afix].append(a.label)
    # O/N 上的氢：只有"端基"O/N 才带 H
    #   羟基氧：恰好 1 个重原子邻居（碳）
    #   醚/酯/硅醚氧：2 个重原子邻居（如 OMe 的 O，无 H）
    oh_atoms = []
    for a in heavy:
        if a.el not in ('O', 'N'):
            continue
        heavy_nb = [(n, e, d) for n, e, d in adj[a.label]]
        if len(heavy_nb) == 1 and heavy_nb[0][1] in ('C', 'N', 'S'):
            oh_atoms.append(a.label)
            total_h += 1
        elif len(heavy_nb) == 0:
            oh_atoms.append(a.label)      # 水/游离氧，仍按每个 2H 提示
            total_h += 2
    plans['OH'] = oh_atoms

    if verbose:
        print(f"{'atom':8}{'el':>3}{'deg':>5}{'unsat':>7}{'H':>4}  neighbours (d/A)")
        for lab, el, deg, unsat, h, afix, nb in detail:
            nbs = " ".join(f"{n}:{d:.2f}" for n, e, d in nb)
            flag = ""
            if el == 'C' and deg == 0:
                flag = "  <-- 孤立碳：检查是否漏原子或标签错"
            if el == 'C' and deg > 4:
                flag = "  <-- 配位数 >4：检查原子类型"
            print(f"{lab:8}{el:>3}{deg:>5}{str(unsat):>7}{h:>4}  {nbs}{flag}")
        print(f"\n总 H（按连接性推断）= {total_h}")
        if cr.unit:
            want = None
            for el, n in zip(cr.sfac, cr.unit):
                if el == 'H':
                    want = n
            if want:
                nsym = max(1, len(cr.symm))
                print(f"UNIT 中 H = {want}  -> 每个不对称单位应为 {want/nsym:.1f}"
                      f"（本模型推断 {total_h}）")
                if abs(want / nsym - total_h) > 0.6:
                    print("  !! 不一致：可能缺 H、多 H，或原子类型/占位有问题")
        print("\n--- HFIX 分组（可直接粘进 ins）---")
        for k in (13, 23, 43, 137):
            if plans[k]:
                print(f"HFIX {k:<4} {' '.join(plans[k])}")
        if plans['OH']:
            print(f"# O/N 上的氢（建议用差峰定位，或用 AFIX 147 刚性旋转群）:")
            print(f"#   {' '.join(plans['OH'])}")
    return plans, total_h, adj, heavy


def report_components(cr, adj, heavy):
    seen, comps = set(), []
    for a in heavy:
        if a.label in seen:
            continue
        stack, comp = [a.label], []
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            comp.append(cur)
            stack += [n for n, e, d in adj[cur] if n not in seen]
        comps.append(sorted(comp))
    comps.sort(key=len, reverse=True)
    print(f"\n分子连通分量: {[len(c) for c in comps]}")
    if len(comps) > 1:
        for i, c in enumerate(comps[1:], 1):
            els = defaultdict(int)
            for lab in c:
                m = re.match(r'^([A-Za-z]{1,2})', lab)
                els[m.group(1) if m else '?'] += 1
            kind = "疑似溶剂/未建模片段" if len(c) < 25 else "独立分子 (Z'>1)"
            print(f"  组 {i}: {len(c)} 原子 {dict(els)}  -> {kind}")
            print(f"    {' '.join(c[:24])}{' ...' if len(c) > 24 else ''}")
    return comps


def report_type_suspects(cr):
    """找可能的原子类型错误：如 C 位点被 O 包围过近、O 位点无重原子邻居。"""
    adj, ats = build_adj(cr, exclude_h=False)
    heavy = [a for a in ats if not a.is_h()]
    sus = []
    for a in heavy:
        nb = [(n, e, d) for n, e, d in adj[a.label] if not n.startswith('H')]
        if a.el == 'O' and len(nb) == 0:
            sus.append((a.label, 'O 无重原子邻居 —— 可能是水/游离氧，或标签错'))
        if a.el == 'C' and len(nb) == 0:
            sus.append((a.label, 'C 孤立 —— 可能是未连上的原子或标签错'))
        if a.el == 'C' and any(e == 'O' for _, e, _ in nb) and \
           sum(1 for _, e, _ in nb if e == 'O') >= 2 and len(nb) <= 2:
            sus.append((a.label, 'C 连 ≥2 个 O 且配位低 —— 确认是 COO/碳酸酯而非醇'))
    if sus:
        print("\n原子类型/连接存疑：")
        for lab, msg in sus:
            print(f"  {lab:8} {msg}")
    else:
        print("\n未发现明显的原子类型/连接异常")
    return sus


def main():
    print('注意：以下仅为连接几何产生的候选 H 方案；须核对键级、价态、PART 和已有 H，不直接写入模型。')
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('model', help='res 或 ins')
    ap.add_argument('--expect-h', type=int, help='期望的 H 总数（人工核对用）')
    ap.add_argument('--print-ins', action='store_true', help='打印可粘贴的指令块')
    a = ap.parse_args()

    cr = read_res(a.model)
    print(f"=== {os.path.basename(a.model)} ===")
    print(f"原子 {len(cr.atoms)}（重原子 "
          f"{sum(1 for x in cr.atoms if not x.is_h())}, "
          f"H {sum(1 for x in cr.atoms if x.is_h())}）")
    plans, total_h, adj, heavy = plan_hydrogens(cr)
    comps = report_components(cr, adj, heavy)
    report_type_suspects(cr)
    if a.expect_h is not None:
        print(f"\n人工给定期望 H = {a.expect_h}；本模型（含已存在 H）="
              f"{sum(1 for x in cr.atoms if x.is_h())}；"
              f"按连接性推断应加 = {total_h}")
    if a.print_ins:
        print("\n--- 指令块 ---")
        for k in (13, 23, 43, 137):
            if plans[k]:
                print(f"HFIX {k:<4} {' '.join(plans[k])}")


if __name__ == '__main__':
    main()
