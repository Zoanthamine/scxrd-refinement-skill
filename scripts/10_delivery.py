#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
10_delivery.py — 交付打包：文件归集 + SHA256 + 交付说明 + zip

来自多次模型精修与交付实践：
  * 把定稿文件按固定命名归集到 01_upload / 02_validation / 03_refinement_records
  * 计算 SHA256 并写入 DELIVERY_SHA256.csv
  * 生成 DELIVERY_README.md（含结论、模型处理、数据局限、仍需补充的元数据）
  * 可选打 zip

用法:
  python 10_delivery.py --outdir <交付目录> --name <化合物代码> \
      --cif <定稿.cif> --fcf <x.fcf> --res <x.res> --ins <x.ins> --lst <x.lst> --hkl <x.hkl> \
      [--checkcif <报告.html>] [--figures <图1> <图2>] [--history <历程.md>] \
      [--formula "C29H46O4Si"] [--r1 0.0983] [--wr2 0.2310] [--goof 1.074] \
      [--zip]
"""
import os, re, sys, shutil, hashlib, argparse, zipfile, json
from datetime import datetime
from pathlib import Path

SUB = {'upload': '01_upload', 'validation': '02_validation',
       'records': '03_refinement_records', 'figures': '04_figures',
       'docs': '05_documents'}


def _safe_copy(src, dst, tries=6):
    """带重试的拷贝（云同步可能短暂锁住目标）。"""
    for k in range(tries):
        try:
            if os.path.exists(dst):
                try:
                    os.chmod(dst, 0o666)
                except OSError:
                    pass
                os.remove(dst)
            shutil.copy2(src, dst)
            return True
        except OSError:
            import time as _t
            _t.sleep(0.3 * (k + 1))
    try:
        shutil.copyfile(src, dst)
        return True
    except OSError as e:
        print(f"  !! 无法归档 {os.path.basename(dst)}: {e}")
        return False


def sha256(path, buf=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(buf)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def parse_lst_metrics(lst):
    d = {}
    if not lst or not os.path.exists(lst):
        return d
    t = open(lst, encoding='latin-1', errors='replace').read()
    for key, pat in (
            ('R1_gt', r"R1\s*=\s*([\d\.]+)\s+for\s+\d+\s+Fo\s*>\s*4sig"),
            ('R1_all', r"R1\s*=\s*[\d\.]+\s+for\s+\d+\s+Fo\s*>\s*4sig\(Fo\)\s+and\s+([\d\.]+)"),
            ('wR2', r"wR2\s*=\s*([\d\.]+),\s*GooF"),
            ('GooF', r"wR2\s*=\s*[\d\.]+,\s*GooF\s*=\s*S\s*=\s*([\d\.]+)"),
            ('peak', r"Highest peak\s+([\d\.\-]+)"),
            ('hole', r"Deepest hole\s+([\d\.\-]+)"),
            ('Rint', r"R\(int\)\s*=\s*([\d\.]+)"),
            ('Flack', r"Flack x\s*=\s*(-?[\d\.]+\(\d+\))"),
            ('Parsons', r"(-?[\d\.]+\(\d+\))\s+from\s+\d+\s+selected quotients"),
            ('npar', r"Total number of l\.s\. parameters\s*=\s*(\d+)"),
            ('shift', r"Mean shift/esd\s*=\s*[\d\.\-]+\s+Maximum\s*=\s*([\d\.\-]+)"),
    ):
        m = re.search(pat, t)
        if m:
            d[key] = m.group(1)
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--name', required=True, help='化合物代码，如 sample-01')
    for k in ('cif', 'fcf', 'res', 'ins', 'lst', 'hkl'):
        ap.add_argument('--' + k)
    ap.add_argument('--checkcif', help='checkCIF 报告（html）')
    ap.add_argument('--figures', nargs='*', default=[])
    ap.add_argument('--support', nargs='*', default=[], help='Actual FAB/include/method dependency files')
    ap.add_argument('--history', help='精修历程 md')
    ap.add_argument('--formula', default='')
    ap.add_argument('--notes', help='额外说明文本文件')
    ap.add_argument('--zip', action='store_true')
    a = ap.parse_args()

    if os.path.exists(a.outdir) or (a.zip and os.path.exists(a.outdir + '.zip')):
        raise SystemExit('Delivery destination already exists; choose a new version directory')
    if os.path.basename(a.name) != a.name or a.name in ('.','..'):
        raise SystemExit('name must be a simple basename')
    for key in ('cif','fcf','res','ins','lst','hkl','checkcif','history','notes'):
        path = getattr(a,key)
        if path and not os.path.isfile(path):
            raise SystemExit(f'Missing supplied {key}: {path}')
    for path in a.figures + a.support:
        if not os.path.isfile(path):
            raise SystemExit(f'Missing figure: {path}')
    for s in SUB.values():
        os.makedirs(os.path.join(a.outdir, s), exist_ok=True)

    def put(src, sub, dstname):
        if not src or not os.path.exists(src):
            return None
        subdir = SUB.get(sub, sub)
        os.makedirs(os.path.join(a.outdir, subdir), exist_ok=True)
        dst = os.path.join(a.outdir, subdir, dstname)
        if not _safe_copy(src, dst):
            raise SystemExit(f'Copy failed: {src}')
        if sha256(src) != sha256(dst):
            raise SystemExit(f'Hash mismatch: {src}')
        return dst

    files = []
    N = a.name
    files.append(put(a.cif, 'upload', f'{N}.cif'))
    files.append(put(a.fcf, 'upload', f'{N}.fcf'))
    files.append(put(a.checkcif, 'validation', 'checkcif_report.html'))
    if a.checkcif:
        manifest = os.path.join(os.path.dirname(a.checkcif), 'validation_manifest.json')
        if os.path.isfile(manifest):
            files.append(put(manifest, 'validation', 'validation_manifest.json'))
    for ext, key in (('res', 'res'), ('ins', 'ins'), ('lst', 'lst'), ('hkl', 'hkl')):
        files.append(put(getattr(a, key), 'records', f'{N}.{ext}'))
    for i, f in enumerate(a.figures or [], 1):
        if f and os.path.exists(f):
            files.append(put(f, 'figures', os.path.basename(f)))
    for path in a.support:
        support_name = f'{N}.fab' if Path(path).suffix.lower() == '.fab' else os.path.basename(path)
        if os.path.exists(os.path.join(a.outdir, SUB['records'], support_name)):
            raise SystemExit(f'Support basename collision: {support_name}')
        files.append(put(path, 'records', support_name))
    files.append(put(a.history, 'docs', 'refinement_history.md'))
    files.append(put(a.notes, 'docs', 'notes.md'))
    files = [f for f in files if f]

    # SHA256
    rows = []
    for f in sorted(files):
        rel = os.path.relpath(f, a.outdir)
        rows.append((rel, sha256(f), os.path.getsize(f)))
    sha_csv = os.path.join(a.outdir, 'DELIVERY_SHA256.csv')
    with open(sha_csv, 'w', encoding='utf-8-sig') as fh:
        fh.write('relpath,sha256,bytes\n')
        for rel, h, n in rows:
            fh.write(f'{rel},{h},{n}\n')

    # 指标
    m = parse_lst_metrics(a.lst)
    md = os.path.join(a.outdir, 'DELIVERY_README.md')
    L = [f'# {N} 单晶精修交付说明', '',
         f'- 生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}',
         f'- 化合物：{a.formula or "（未填写）"}', '']
    if m:
        L += ['## 最终精修结果', '',
              '| 指标 | 值 |', '|---|---|',
              f"| R1 [I>2σ] | {m.get('R1_gt','—')} |",
              f"| R1 (all) | {m.get('R1_all','—')} |",
              f"| wR2 | {m.get('wR2','—')} |",
              f"| GooF | {m.get('GooF','—')} |",
              f"| 参数数 | {m.get('npar','—')} |",
              f"| 残峰 max/min | {m.get('peak','—')} / {m.get('hole','—')} e Å⁻³ |",
              f"| Rint | {m.get('Rint','—')} |",
              f"| Flack（经典） | {m.get('Flack','—')} |",
              f"| Flack（Parsons） | {m.get('Parsons','—')} |",
              f"| Max shift/esd | {m.get('shift','—')} |", '']
    L += ['## 文件用途', '',
          '- `01_upload/`：本轮选定的 CIF 与 FCF；是否满足投稿要求需另行审查。',
          '- `02_validation/`：checkCIF/PLATON 报告。',
          '- `03_refinement_records/`：SHELXL 的 `.ins/.res/.lst/.hkl`，可完全复现。',
          '- `04_figures/`：结构图。',
          '- `05_documents/`：精修历程与说明。',
          '- `DELIVERY_SHA256.csv`：全部文件的校验和。', '',
          '## 投稿前请核对/补充', '',
          '- [ ] 晶体描述（颜色、形状、尺寸）',
          '- [ ] 仪器型号、光源、检测器、扫描方式',
          '- [ ] 吸收校正方法与 Tmin/Tmax',
          '- [ ] 晶胞测定所用反射数与 θ 范围',
          '- [ ] 采集/还原/精修软件名称与版本',
          '- [ ] 绝对构型的证据来源（未确定时如实保留；不得假定合成已知）',
          '- [ ] 各条 ALERT 的解释（见 `validation_response_form` 类文档）', '']
    L += ['## 文件清单（SHA256 见 CSV）', '']
    for rel, h, n in rows:
        L.append(f'- `{rel}`  ({n:,} B)')
    open(md, 'w', encoding='utf-8').write("\n".join(L) + "\n")
    print(f"已写出 {md}")
    print(f"已写出 {sha_csv}（{len(rows)} 个文件）")

    if a.zip:
        zp = os.path.join(a.outdir + '.zip')
        with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
            for f in files + [sha_csv, md]:
                z.write(f, os.path.relpath(f, os.path.dirname(a.outdir)))
        print(f"已打包 {zp}（{os.path.getsize(zp):,} 字节）")


if __name__ == '__main__':
    main()
