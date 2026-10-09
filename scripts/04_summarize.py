#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
04_summarize.py — 汇总所有精修轮次，生成可读的"精修历程表"

读取归档目录下的 history.csv（由 03_run.py 写）或直接扫描各轮 lst，
输出：
  * 控制台表格
  * refinement_history.md（含结论段模板）
  * refinement_history.csv（可直接进 SI）

用法:
  python 04_summarize.py --dir <归档根目录> [--job model] [--expect "C29H46O4Si"]
"""
import os, re, sys, csv, glob, argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xtal_core import read_lines

FIELDS = ['stage', 'R1_gt', 'R1_all', 'wR2', 'GooF', 'npar', 'peak', 'hole',
          'Flack', 'Parsons', 'WGHT_used', 'WGHT_next', 'Rint', 'nrefl', 'marks']


def parse_lst(path):
    try:
        t = open(path, encoding='latin-1', errors='replace').read()
    except OSError:
        return None
    d = {}
    m = re.search(r"R1\s*=\s*([\d\.]+)\s+for\s+(\d+)\s+Fo\s*>\s*4sig\(Fo\)\s+and\s+"
                  r"([\d\.]+)\s+for all\s+(\d+)\s+data", t)
    if m:
        d['R1_gt'], d['n_gt'] = float(m.group(1)), int(m.group(2))
        d['R1_all'], d['nrefl'] = float(m.group(3)), int(m.group(4))
    m = re.search(r"wR2\s*=\s*([\d\.]+),\s*GooF\s*=\s*S\s*=\s*([\d\.]+)", t)
    if m:
        d['wR2'], d['GooF'] = float(m.group(1)), float(m.group(2))
    m = re.search(r"Flack x\s*=\s*(-?[\d\.]+)\((\d+)\)", t)
    if m:
        d['Flack'] = f"{m.group(1)}({m.group(2)})"
    m = re.search(r"(-?[\d\.]+)\((\d+)\)\s+from\s+(\d+)\s+selected quotients", t)
    if m:
        d['Parsons'] = f"{m.group(1)}({m.group(2)})"
    m = re.search(r"Recommended weighting scheme:\s*WGHT\s+([\d\.\-]+)\s+([\d\.\-]+)", t)
    if m:
        d['WGHT_next'] = f"{m.group(1)} {m.group(2)}"
    m = re.search(r"Weight\s*=\s*1\s*/\s*\[\s*sigma\^2\(Fo\^2\)\s*\+\s*\(\s*([\d\.]+)\s*\*\s*P"
                  r"\s*\)\^2\s*\+\s*([\d\.]+)\s*\*\s*P\s*\]", t)
    if m:
        d['WGHT_used'] = f"{m.group(1)} {m.group(2)}"
    m = re.search(r"Highest peak\s+([\d\.\-]+)", t)
    if m:
        d['peak'] = float(m.group(1))
    m = re.search(r"Deepest hole\s+([\d\.\-]+)", t)
    if m:
        d['hole'] = float(m.group(1))
    m = re.search(r"Total number of l\.s\. parameters\s*=\s*(\d+)", t)
    if m:
        d['npar'] = int(m.group(1))
    m = re.search(r"R\(int\)\s*=\s*([\d\.]+)", t)
    if m:
        d['Rint'] = float(m.group(1))
    marks = [l.strip() for l in t.splitlines() if '**' in l and
             any(k in l for k in ('ERROR', 'WARNING', 'BAD', 'NO ATOMS', 'MISSING',
                                  'CONFLICT', 'WRONG', 'NPD', 'Absolute structure',
                                  'split'))]
    d['marks'] = ' | '.join(m[:70] for m in marks[:3])
    return d


def collect(root, job):
    rows = []
    csv_p = os.path.join(root, 'history.csv')
    hist = {}
    if os.path.exists(csv_p):
        with open(csv_p, encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                hist[r.get('stage', '')] = r
    for d in sorted(os.listdir(root)):
        p = os.path.join(root, d)
        if not os.path.isdir(p):
            continue
        lst = os.path.join(p, job + '.lst')
        if not os.path.exists(lst) or os.path.getsize(lst) < 800:
            continue
        rec = parse_lst(lst) or {}
        h = hist.get(d, {})
        rows.append(dict(
            stage=d,
            R1_gt=rec.get('R1_gt', h.get('R1_gt', '')),
            R1_all=rec.get('R1_all', h.get('R1_all', '')),
            wR2=rec.get('wR2', h.get('wR2', '')),
            GooF=rec.get('GooF', h.get('GooF', '')),
            npar=rec.get('npar', h.get('npar', '')),
            peak=rec.get('peak', h.get('peak', '')),
            hole=rec.get('hole', h.get('hole', '')),
            Flack=rec.get('Flack', h.get('Flack', '')),
            Parsons=rec.get('Parsons', h.get('Flack_parsons', '')),
            WGHT_used=rec.get('WGHT_used', h.get('WGHT_used', '')),
            WGHT_next=rec.get('WGHT_next', h.get('WGHT_next', '')),
            Rint=rec.get('Rint', h.get('Rint', '')),
            nrefl=rec.get('nrefl', h.get('nrefl', '')),
            marks=rec.get('marks', h.get('notes', '')),
        ))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dir', required=True, help='归档根目录')
    ap.add_argument('--job', default='model')
    ap.add_argument('--expect', default='', help='目标化学式（写进报告）')
    ap.add_argument('--md', help='输出 Markdown 路径（默认 <dir>/refinement_history.md）')
    ap.add_argument('--csv', help='输出 CSV 路径（默认 <dir>/refinement_history.csv）')
    a = ap.parse_args()

    rows = collect(a.dir, a.job)
    if not rows:
        print(f"在 {a.dir} 下没找到任何 {a.job}.lst")
        return

    def num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    # 控制台表
    def fmt(v, spec, dash='-'):
        try:
            return format(float(v), spec)
        except (TypeError, ValueError):
            return dash

    print(f"{'stage':32}{'R1(gt)':>9}{'R1(all)':>9}{'wR2':>8}{'GooF':>7}"
          f"{'npar':>6}{'peak':>7}{'hole':>7}  Flack / Parsons")
    print("-" * 112)
    for r in rows:
        print(f"{r['stage'][:31]:32}"
              f"{fmt(r['R1_gt'], '.4f'):>9}"
              f"{fmt(r['R1_all'], '.4f'):>9}"
              f"{fmt(r['wR2'], '.4f'):>8}"
              f"{fmt(r['GooF'], '.3f'):>7}"
              f"{str(r['npar'] or '-'):>6}"
              f"{fmt(r['peak'], '+.2f'):>7}"
              f"{fmt(r['hole'], '+.2f'):>7}"
              f"  {r['Flack'] or '-'} / {r['Parsons'] or '-'}")

    # 找最优（wR2 最小且 res 非空）
    valid = [r for r in rows if num(r['wR2']) is not None]
    best = min(valid, key=lambda r: num(r['wR2'])) if valid else None

    md = a.md or os.path.join(a.dir, 'refinement_history.md')
    lines = [f"# 单晶精修历程表",
             "",
             f"- 生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}",
             f"- 归档目录：`{a.dir}`",
             f"- 作业名：`{a.job}`"]
    if a.expect:
        lines.append(f"- 目标化学式：{a.expect}")
    lines += ["", f"共 {len(rows)} 轮精修。", "",
              "| 轮次 | R1(I>2σ) | R1(all) | wR2 | GooF | 参数 | 残峰+ | 残峰− | Flack | Parsons |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        f = lambda k: (f"{num(r[k]):.4f}" if num(r[k]) is not None else "—")
        f3 = lambda k: (f"{num(r[k]):.3f}" if num(r[k]) is not None else "—")
        f2 = lambda k: (f"{num(r[k]):+.2f}" if num(r[k]) is not None else "—")
        lines.append(f"| `{r['stage']}` | {f('R1_gt')} | {f('R1_all')} | "
                     f"{f('wR2')} | {f3('GooF')} | {r['npar'] or '—'} | "
                     f"{f2('peak')} | {f2('hole')} | {r['Flack'] or '—'} | "
                     f"{r['Parsons'] or '—'} |")
    if best:
        lines += ["", "## 最优轮次", "",
                  f"按 wR2 最小选：**`{best['stage']}`** "
                  f"(R1 = {best['R1_gt']}, wR2 = {best['wR2']}, GooF = {best['GooF']})",
                  "",
                  "> 注意：最终版本不一定等于 wR2 最小者。定稿应同时满足：",
                  "> 化学合理、无 NPD/split 告警、无残留 TWIN/BASF、",
                  "> 权重已收敛、绝对构型可解释。"]
    lines += ["", "## 每轮标记（** 信息）", ""]
    for r in rows:
        if r['marks']:
            lines.append(f"- `{r['stage']}`: {r['marks']}")
    open(md, 'w', encoding='utf-8').write("\n".join(lines) + "\n")

    csvp = a.csv or os.path.join(a.dir, 'refinement_history.csv')
    with open(csvp, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    print(f"\n已写出:\n  {md}\n  {csvp}")


if __name__ == '__main__':
    main()
