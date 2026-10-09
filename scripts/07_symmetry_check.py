#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
07_symmetry_check.py — 空间群与伪对称判定（竞争精修的定量判据）

来自多次对称初筛与模型比较实践：
  仅凭 wR2 判断空间群常常被过度参数化误导，需先做几何层面的定量检验：

  1. 反演中心扫描：网格搜索最优平移 tau，使 -r+tau 与另一原子（同元素）
     的匹配率最高。匹配率高（>80% within 0.5 A）-> 强烈提示中心对称。
  2. 分子间伪对称：多个分子连通分量两两匹配，判断是否互为反演/平移像。
  3. 缺失对称操作探测：按候选操作合并 hkl，看 Rmerge 是否显著下降
     （漏掉的对称操作会让"独立反射"里混入等价反射）。
  4. 竞争精修建议：给出应尝试的 LATT/空间群组合。

用法:
  python 07_symmetry_check.py <res|ins> --hkl <hkl> [--tau-step 0.1]
"""
import os, re, sys, math, argparse, itertools
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xtal_core import read_res, read_hkl, COV, point_group_from_symm, hkl_laue_class

INSTR = {"HKLF", "SFAC", "UNIT", "LATT", "SYMM", "FVAR", "WGHT", "TEMP", "CELL",
         "ZERR", "TITL", "LIST", "PLAN", "END", "REM", "CONF", "DISP", "L.S.",
         "ACTA", "MORE", "FMAP", "BOND", "HTAB", "EQIV", "SHEL", "ANIS", "RIGU",
         "SIMU", "ISOR", "DELU", "FLAT", "CHIV", "SADI", "DFIX", "DANG",
         "BUMP", "SUMP", "EADP", "EXYZ", "PART", "RESI", "FREE", "OMIT",
         "TWIN", "BASF", "MERG", "HFIX", "AFIX", "CGLS", "BLOC", "DAMP",
         "STIR", "DEFS", "SIZE", "MOLE", "CONN", "PEAK", "LAUE", "MOVE"}


def frac_min_image(cr, f1, f2):
    d = [f1[i] - f2[i] for i in range(3)]
    d = [x - round(x) for x in d]
    return math.dist(cr.cart(d), (0, 0, 0))


def _sym_rot(op):
    """对称操作函数的 3x3 旋转部分（数值微分）。"""
    o = op(0.0, 0.0, 0.0)
    e = 1e-6
    cols = []
    for k in range(3):
        v = [0.0, 0.0, 0.0]
        v[k] = e
        p = op(*v)
        cols.append([(p[i] - o[i]) / e for i in range(3)])
    return [[cols[k][i] for k in range(3)] for i in range(3)]


def inversion_scan(cr, heavy, step=0.1, cut_hit=0.8):
    """网格搜索反演中心平移 tau。返回 (最佳命中率, tau, 明细)"""
    F = [a.frac for a in heavy]
    els = [a.el for a in heavy]
    n = len(F)

    def hits(tau, cut):
        hit = 0
        pairs = {}
        for i in range(n):
            q = [(-F[i][k] + tau[k]) % 1.0 for k in range(3)]
            best = None
            for j in range(n):
                if i == j or els[j] != els[i]:
                    continue
                d = frac_min_image(cr, q, F[j])
                if best is None or d < best[0]:
                    best = (d, j)
            if best and best[0] < cut:
                hit += 1
                pairs[i] = best
        return hit, pairs

    grid = [i * step for i in range(int(round(1.0 / step)))]
    best = (0, [0, 0, 0])
    for u, v, w in itertools.product(grid, repeat=3):
        h, _ = hits((u, v, w), cut_hit)
        if h > best[0]:
            best = (h, [u, v, w])
    tau = list(best[1])
    # 精修 tau（把每对残差平均）
    for _ in range(30):
        hit, pairs = hits(tau, 1.0)
        if not pairs:
            break
        tot = [0.0, 0.0, 0.0]
        for i, (d, j) in pairs.items():
            q = [(-F[i][k] + tau[k]) % 1.0 for k in range(3)]
            diff = [q[k] - F[j][k] for k in range(3)]
            diff = [x - round(x) for x in diff]
            for k in range(3):
                tot[k] += diff[k]
        tau = [(tau[k] + tot[k] / len(pairs)) % 1.0 for k in range(3)]
    detail = {}
    for cut in (0.3, 0.5, 0.8, 1.2):
        h, _ = hits(tau, cut)
        detail[cut] = h
    return detail, tau, hits


def molecular_pseudo_symmetry(cr, adj, heavy, max_ops=8):
    """两两比较连通分量，判断是否互为平移/反演像。"""
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
        comps.append(comp)
    comps = [c for c in comps if len(c) >= 6]
    if len(comps) < 2:
        return None
    idx = {a.label: a for a in heavy}
    c1, c2 = comps[0], comps[1]
    out = []
    for opname, sign in (('identity', +1), ('inversion', -1)):
        best = None
        for tau_i in itertools.product((-1, 0, 1), repeat=3):
            tau = list(tau_i)
            ds = []
            for lab in c1:
                a = idx[lab]
                q = [(sign * a.frac[k] + tau[k]) % 1.0 for k in range(3)]
                bb = None
                for lab2 in c2:
                    b = idx[lab2]
                    if b.el != a.el:
                        continue
                    d = frac_min_image(cr, q, b.frac)
                    if bb is None or d < bb:
                        bb = d
                if bb is not None:
                    ds.append(bb)
            if ds:
                mean = sum(ds) / len(ds)
                frac5 = sum(1 for d in ds if d < 0.5) / len(ds)
                if best is None or mean < best[0]:
                    best = (mean, tau, frac5, len(ds))
        if best:
            out.append((opname, best))
    return out


def missing_symmetry_from_hkl(rows, cr, ops_list):
    """按候选操作集合合并 hkl，输出 Rmerge；Rmerge 显著下降 = 可能漏对称。"""
    res = []
    base_ops = point_group_from_symm(cr.symm)
    for name, ops in ops_list:
        pg = base_ops + [R for R in ops if R not in base_ops]
        num = den = 0.0
        groups = defaultdict(list)
        for h, k, l, f, s in rows:
            groups[hkl_laue_class(h, k, l, pg)].append(f)
        nref = 0
        for g, vals in groups.items():
            if len(vals) < 2:
                continue
            m = sum(vals) / len(vals)
            num += sum(abs(v - m) for v in vals)
            den += sum(abs(v) for v in vals)
            nref += len(vals)
        res.append((name, (num/den*100 if den else 0), len(groups), nref))
    return res


def main():
    print('注意：以下为启发式候选对称检查，匹配比例和建议不构成空间群判定；须结合消光、晶胞变换和衍射证据。')
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('model')
    ap.add_argument('--hkl')
    ap.add_argument('--tau-step', type=float, default=0.1)
    a = ap.parse_args()

    cr = read_res(a.model)
    print(f"=== {os.path.basename(a.model)} ===")
    nsym = len(cr.symm)
    kind = ("P1（仅恒等操作）" if nsym == 1 else
            f"{nsym} 个实空间操作（含恒等）")
    inv = any(all(abs(abs(_rot[i][i]) - 1) < 1e-6 for i in range(3)) and
              sum(1 for i in range(3) if _rot[i][i] < 0) == 3
              for _rot in [_sym_rot(op) for op in cr.symm])
    print(f"SYMM: {kind}  -> {'含反演操作' if inv else '无纯反演操作'}")
    print(f"CELL = {cr.cell}")

    # 连接表
    from xtal_core import bonds, connected_components
    bl = bonds(cr, exclude_h=True)
    heavy = [x for x in cr.atoms if not x.is_h()]
    adj = defaultdict(list)
    for x, y, d, ff in bl:
        adj[x.label].append((y.label, y.el, d))
        adj[y.label].append((x.label, x.el, d))

    print("\n--- 1) 反演中心扫描 ---")
    detail, tau, _hits = inversion_scan(cr, heavy, step=a.tau_step)
    n = len(heavy)
    for cut in sorted(detail):
        print(f"  within {cut:4.1f} A : {detail[cut]:4d}/{n} "
              f"= {100*detail[cut]/n:5.1f}%")
    print(f"  最佳平移 tau = {[round(x,3) for x in tau]}")
    best082 = detail.get(0.8, 0) / n if n else 0
    if best082 > 0.85:
        print("  => 高度提示存在反演中心：应尝试中心对称空间群（LATT -1）")
    elif best082 > 0.6:
        print("  => 部分匹配：可能是伪对称/无序，或两个分子近似互为反演像")
    else:
        print("  => 无显著反演关系：非中心对称空间群合理")

    print("\n--- 2) 分子间伪对称 ---")
    out = molecular_pseudo_symmetry(cr, adj, heavy)
    if out:
        for opname, (mean, t, f5, m) in out:
            print(f"  操作 {opname:10} 平均偏差 {mean:6.2f} A  "
                  f"<0.5A 比例 {f5*100:5.1f}%  (n={m})  tau={t}")
        bestop = min(out, key=lambda t: t[1][0])
        if bestop[1][0] < 0.5:
            hint = ("可能是同一分子的反演像（考虑 P-1 / Z'=1）"
                    if bestop[0] == 'inversion' else
                    "纯平移伪对称（检查是否可直接减半 Z）")
            print(f"  => 两个分子经 {bestop[0]} 高度重合：{hint}")
    else:
        print("  只有一个连通分量（或多组分过小），无分子间伪对称问题")

    if a.hkl and os.path.exists(a.hkl):
        rows = read_hkl(a.hkl)
        print(f"\n--- 3) 缺失对称操作探测（hkl: {os.path.basename(a.hkl)}, "
              f"{len(rows)} 条）---")
        # 常用候选：反演
        INV = [[-1, 0, 0], [0, -1, 0], [0, 0, -1]]
        # 2_1 螺旋 / 镜面（正交/单斜常见）
        cands = [
            ('+inversion', [INV]),
            ('+2fold a (h,-k,-l)', [[[1, 0, 0], [0, -1, 0], [0, 0, -1]]]),
            ('+2fold b (-h,k,-l)', [[[-1, 0, 0], [0, 1, 0], [0, 0, -1]]]),
            ('+2fold c (-h,-k,l)', [[[-1, 0, 0], [0, -1, 0], [0, 0, 1]]]),
        ]
        base = missing_symmetry_from_hkl(rows, cr, [('current', [])])
        print(f"  当前空间群: Rmerge = {base[0][1]:.2f}%  "
              f"({base[0][2]} 等价类, {base[0][3]} 反射)")
        res = missing_symmetry_from_hkl(rows, cr, cands)
        for name, rm, ng, nr in res:
            delta = base[0][1] - rm
            tag = ""
            if delta > 2:
                tag = "  <-- Rmerge 明显下降，考虑该操作"
            print(f"  {name:24} Rmerge = {rm:6.2f}%  ({ng} 类)  下降 {delta:+.2f}{tag}")

    print("""
--- 4) 竞争精修建议 ---
空间群判定不要只看 wR2（参数翻倍本身会压低 wR2）。建议：
  模型A：非中心对称（当前 LATT），保留观察到的全部独立原子
  模型B：加反演中心（LATT -1），UNIT 减半，Z' 减半
  模型C：中心对称但保留 2 个分子（若确有 Z'=2 的独立分子）
比较同一数据、同一精修协议下的 wR2 / 参数数 / GooF / 残峰，
并优先采用可解释性更好（无 >0.5 A 的伪对称残差、无异常 ADB）的模型。
用 03_run.py 分别跑三个模型即可，例如：
  python 03_run.py --base <res> --stage sg_A_P1  --dir <work> -o "LATT 1"
  python 03_run.py --base <res> --stage sg_B_P-1 --dir <work> -o "LATT -1"
""")


if __name__ == '__main__':
    main()
