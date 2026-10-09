#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CIF tools: validate (limited consistency checks), prepare (Gemmi metadata merge),
upload (explicit diagnostic copy only). Missing metadata stays unknown.
prepare --res/--lst are retained for CLI compatibility; no formula or stereochemistry is inferred.
"""
import os, re, sys, json, argparse, math, glob
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xtal_core import read_lines, write_lines


# ---------------------------------------------------------------- 轻量 CIF 读取
def cif_blocks(path):
    """把 CIF 拆成 data block：{name: text}"""
    try:
        import gemmi
    except ImportError:
        pass
    else:
        return {block.name: block.as_string() for block in gemmi.cif.read_file(path)}
    txt = open(path, encoding='latin-1', errors='replace').read()
    blocks, cur, name = {}, [], None
    in_text = False
    for ln in txt.splitlines():
        if ln.startswith(';'):
            in_text = not in_text
        if not in_text and ln.strip().lower().startswith('data_'):
            if name is not None:
                blocks[name] = "\n".join(cur)
            name = ln.strip()[5:]
            cur = []
        elif name is not None:
            cur.append(ln)
    if name is not None:
        blocks[name] = "\n".join(cur)
    return blocks


def cif_val(text, tag, default=None):
    """取数据项的值（单行）。"""
    m = re.search(r"^" + re.escape(tag) + r"\s+(.+)$", text, re.M)
    if not m:
        return default
    v = m.group(1).strip()
    if v.startswith(';'):
        # 多行文本块
        m2 = re.search(r"^" + re.escape(tag) + r"\s*\n;\n(.*?)\n;", text, re.M | re.S)
        return m2.group(1) if m2 else default
    return v.strip("'\"")


def cif_num(text, tag, default=None):
    v = cif_val(text, tag)
    if v in (None, '?', '.'):
        return default
    try:
        return float(re.split(r'[\(\s]', v)[0])
    except (ValueError, AttributeError):
        return default


def cif_loop(text, prefix):
    """取一个 loop_ 表，返回 (列名列表, 行列表)。"""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ln.strip().lower() != 'loop_':
            continue
        j = i + 1
        tags = []
        while j < len(lines) and lines[j].strip().startswith('_'):
            tags.append(lines[j].strip()); j += 1
        if not tags or not all(t.startswith(prefix) for t in tags):
            continue
        rows = []
        while j < len(lines):
            s = lines[j].strip()
            if (not s) or s.startswith('_') or s.lower() == 'loop_' or \
               s.startswith('data_') or s.startswith('#'):
                break
            rows.append(s.split())
            j += 1
        return tags, rows
    return [], []


# ---------------------------------------------------------------- validate
def do_validate(a):
    print("=" * 92)
    print(f"CIF 本地校验：{os.path.basename(a.cif)}")
    print("=" * 92)
    problems, notes = [], []
    try:
        import gemmi
        gemmi.cif.read_file(a.cif)
    except ImportError:
        notes.append('Gemmi unavailable: syntax not validated; heuristic checks only')
    except Exception as exc:
        raise SystemExit(f'CIF syntax error: {exc}')
    for key in ('res', 'fcf', 'lst'):
        path = getattr(a, key)
        if path and not os.path.isfile(path):
            raise SystemExit(f'Missing supplied {key}: {path}')
        if not path:
            notes.append(f'{key} not supplied; corresponding checks skipped')

    blocks = cif_blocks(a.cif)
    print(f"data block: {list(blocks)}")
    if len(blocks) != 1:
        raise SystemExit('Select one structure data block before using this limited validator.')
    T = list(blocks.values())[0] if blocks else ''
    if not T:
        print("!! CIF 无法解析出 data block")
        raise SystemExit(2)

    # --- 基础项 ---
    formula = cif_val(T, '_chemical_formula_sum') or cif_val(T, '_chemical_formula_moiety')
    sg = cif_val(T, '_space_group_name_H-M_alt') or cif_val(T, '_symmetry_space_group_name_H-M')
    Z = cif_num(T, '_cell_formula_units_Z')
    cell = [cif_num(T, k) for k in
            ('_cell_length_a', '_cell_length_b', '_cell_length_c',
             '_cell_angle_alpha', '_cell_angle_beta', '_cell_angle_gamma')]
    print(f"化学式   : {formula}")
    print(f"空间群   : {sg}   Z = {Z}")
    print(f"晶胞     : {['%.4f' % x if x else '?' for x in cell]}")
    print(f"R1(gt)={cif_num(T,'_refine_ls_R_factor_gt')}  "
          f"wR2={cif_num(T,'_refine_ls_wR_factor_ref')}  "
          f"GooF={cif_num(T,'_refine_ls_goodness_of_fit_ref')}  "
          f"Npar={cif_num(T,'_refine_ls_number_parameters')}")
    print(f"残峰     : {cif_num(T,'_refine_diff_density_max')} / "
          f"{cif_num(T,'_refine_diff_density_min')} e/A^3")
    fl = cif_val(T, '_refine_ls_abs_structure_Flack')
    ac = cif_val(T, '_chemical_absolute_configuration')
    print(f"绝对构型 : Flack={fl}  _chemical_absolute_configuration={ac}")

    # --- 与 RES 比对 ---
    if a.res and os.path.exists(a.res):
        from xtal_core import read_res
        cr = read_res(a.res)
        print(f"\n-- 与 {os.path.basename(a.res)} 比对 --")
        if cr.cell:
            dmax = max((abs(x-y) for x,y in zip(cell, cr.cell) if x is not None and y is not None), default=float('inf'))
            print(f"  晶胞最大偏差 = {dmax:.5f}")
            if dmax > 1e-3:
                problems.append(f"CIF 与 RES 晶胞不一致（最大 {dmax:.4f}）")
        # 残留 TWIN/BASF/LIST 6/OMIT
        res_txt = "\n".join(read_lines(a.res))
        for pat, msg in ((r'^(TWIN|BASF)\b', '含 TWIN/BASF：核对孪晶依据，不自动删除'),
                         (r'^LIST\s+6\b', '最终模型含 LIST 6（诊断指令）'),
                         (r'^OMIT\b', '最终模型含 OMIT（排除反射，需说明）')):
            if re.search(pat, res_txt, re.M):
                notes.append(msg)
        n_atoms = len(cr.atoms)
        print(f"  RES 原子数 = {n_atoms}")
        # H 计数
        h_res = sum(1 for x in cr.atoms if x.is_h())
        print(f"  RES 中 H 数 = {h_res}")

    # --- 与 FCF 比对 ---
    if a.fcf and os.path.exists(a.fcf):
        print(f"\n-- 与 {os.path.basename(a.fcf)} 比对 --")
        F = open(a.fcf, encoding='latin-1', errors='replace').read()
        fb = cif_blocks(a.fcf)
        FT = list(fb.values())[0] if fb else F
        code = cif_val(FT, '_shelx_refln_list_code')
        print(f"  FCF list code = {code}  (应为 4)")
        if code and str(code).strip() != '4':
            problems.append(f"FCF 的 _shelx_refln_list_code = {code}，应为 4")
        tags, rows = cif_loop(FT, '_refln_')
        print(f"  FCF 反射数 = {len(rows)}")
        nref_cif = cif_num(T, '_refine_ls_number_reflns')
        if nref_cif and rows and abs(len(rows) - nref_cif) > max(5, nref_cif * 0.01):
            problems.append(f"FCF 反射数 {len(rows)} 与 CIF 报告值 {int(nref_cif)} 不符")
        fcell = [cif_num(FT, k) for k in
                 ('_cell_length_a', '_cell_length_b', '_cell_length_c',
                  '_cell_angle_alpha', '_cell_angle_beta', '_cell_angle_gamma')]
        if all(fcell) and all(cell):
            dmax = max(abs(x - y) for x, y in zip(cell, fcell))
            print(f"  CIF/FCF 晶胞最大偏差 = {dmax:.5f}")
            if dmax > 1e-3:
                problems.append("CIF 与 FCF 晶胞不一致")

    # --- 与 LST 比对 ---
    if a.lst and os.path.exists(a.lst):
        L = open(a.lst, encoding='latin-1', errors='replace').read()
        print(f"\n-- 与 {os.path.basename(a.lst)} 比对 --")
        m = re.search(r"(\d+)\s+atoms may be split and\s+(\d+)\s+atoms NPD", L)
        if m:
            print(f"  split={m.group(1)}  NPD={m.group(2)}")
            if m.group(1) != '0' or m.group(2) != '0':
                notes.append(f"lst 报 split={m.group(1)} NPD={m.group(2)}（需检查；split 提示不等于已证实无序）")
        else:
            notes.append("lst 未找到 'NPD / may be split' 行（可能未跑到最后）")
        m = re.search(r"R\(int\)\s*=\s*([\d\.]+)\s+R\(sigma\)\s*=\s*([\d\.]+)", L)
        if m:
            print(f"  Rint={m.group(1)}  Rsigma={m.group(2)}")
        m = re.search(r"Recommended weighting scheme:\s*WGHT\s+([\d\.\-]+)\s+([\d\.\-]+)", L)
        w_used = re.search(r"weighting scheme.*?WGHT\s+([\d\.\-]+)\s+([\d\.\-]+)", T, re.S) or \
                 re.search(r"w=1/\[\S+\^2\+\(([\d\.]+)P\)\^2\+([\d\.]+)P\]", T)
        if m:
            print(f"  SHELXL 建议 WGHT = {m.group(1)} {m.group(2)}")
            if w_used:
                try:
                    used = [float(w_used.group(1)), float(w_used.group(2))]
                    nxt = [float(m.group(1)), float(m.group(2))]
                    gap = max(abs(used[0]-nxt[0]), abs(used[1]-nxt[1]))
                    print(f"  CIF 中 WGHT ≈ {used}  差 = {gap:.4f}")
                    if gap > 0.05:
                        notes.append("CIF 的 WGHT 与 SHELXL 建议值差 >0.05"
                                     "—— 权重稳定性提示；PLAT964 需另核对 CIF 与内嵌 RES 的实际权重")
                except (ValueError, IndexError):
                    pass

    # --- 仍为 ? 的元数据项 ---
    qs = re.findall(r"^(\S+)\s+\?\s*$", T, re.M)
    qs = [q for q in qs if not q.startswith('_refine_ls_abs')]
    if qs:
        print(f"\n仍为 '?' 的元数据项（共 {len(qs)}）:")
        for q in qs:
            print(f"  {q}")
        notes.append(f"{len(qs)} 个元数据项为 '?'（投稿前尽量补全）")

    print("\n" + "-" * 92)
    if problems:
        print("!! 需要修正的问题：")
        for x in problems:
            print("   - " + x)
    else:
        print("已执行的有限检查未发现硬性问题；不代表全面自洽或投稿通过")
    if notes:
        print("提示（非致命）：")
        for x in notes:
            print("   - " + x)
    if a.json:
        json.dump(dict(problems=problems, notes=notes, formula=formula,
                       space_group=sg, Z=Z, cell=cell),
                  open(a.json, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
        print(f"\n已写出 {a.json}")
    if problems:
        raise SystemExit(2)


# ---------------------------------------------------------------- prepare
# No invented experiment metadata defaults.
DEFAULTS = {}
CRITICAL = dict.fromkeys((
    '_exptl_crystal_size_max', '_exptl_crystal_size_mid', '_exptl_crystal_size_min',
    '_exptl_absorpt_correction_T_min', '_exptl_absorpt_correction_T_max',
    '_cell_measurement_reflns_used', '_cell_measurement_theta_min',
    '_cell_measurement_theta_max'), '?')

def do_prepare(a):
    """Use a real CIF parser; merge explicit metadata without inventing values."""
    try:
        import gemmi
    except ImportError:
        raise SystemExit('prepare requires Gemmi in this Python environment; no file was written.')
    doc = gemmi.cif.read_file(a.cif)
    if len(doc) != 1:
        raise SystemExit('prepare requires one explicit structure data block.')
    block = doc.sole_block()
    provenance = {}
    missing = []
    def value(v):
        if v is None or str(v) in ('?', '.'):
            return '?' if v is None else str(v)
        s = str(v)
        if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
            s = s[1:-1]
        return gemmi.cif.quote(s)
    if a.metacif:
        source = gemmi.cif.read_file(a.metacif).sole_block()
        for item in source:
            if not item.pair:
                continue
            tag, raw = item.pair
            if not tag.startswith(('_exptl_', '_diffrn_', '_cell_measurement_', '_computing_')):
                continue
            if raw in ('?', '.'):
                continue
            current = block.find_value(tag)
            if current in (None, '?', '.'):
                block.set_pair(tag, raw)
                provenance[tag] = str(a.metacif)
            elif current != raw:
                print(f'CONFLICT retained CIF: {tag}: {current} vs {raw}')
    if a.meta:
        with open(a.meta, encoding='utf-8') as handle:
            meta = json.load(handle)
        for tag, val in meta.items():
            if not tag.startswith('_'):
                continue
            if tag.startswith('_shelx_'):
                raise ValueError('Embedded records/checksums must come from the final refinement.')
            block.set_pair(tag, value(val))
            provenance[tag] = str(a.meta)
    for tag in CRITICAL:
        if block.find_value(tag) in (None, '?', '.'):
            block.set_pair(tag, '?')
            missing.append(tag)
    # RES/LST are not grounds to infer synthesis, solvent composition or experiment metadata.
    doc.write_file(a.out)
    gemmi.cif.read_file(a.out)
    with open(a.out + '.metadata.json', 'w', encoding='utf-8') as f:
        json.dump(dict(sources=provenance, missing=missing,
                       status='candidate; metadata sources require review'),
                  f, indent=2, ensure_ascii=False)
    print(f'Written {a.out}; missing experimental fields: {len(missing)}')
    for tag in missing:
        print('  ? ' + tag)


# ---------------------------------------------------------------- upload
def do_upload(a):
    T = open(a.cif, encoding='latin-1', errors='replace').read()
    before = len(T)
    for key in ('_shelx_hkl_file', '_shelx_res_file', '_shelx_fcf_file'):
        T, n = re.subn(r"^" + re.escape(key) + r"\s*\n;\n.*?\n;\s*\n", "",
                       T, count=0, flags=re.M | re.S)
        if n:
            print(f"  移除 {key} 内嵌文本块 ×{n}")
    T = re.sub(r"^(_shelx_hkl_checksum|_shelx_res_checksum|_shelx_fcf_checksum)\s+.*$",
               lambda m: f"{m.group(1)}              ?", T, flags=re.M)
    T = re.sub(r"\n{3,}", "\n\n", T)
    open(a.out, 'w', encoding='latin-1').write(T)
    print(f"{a.out}: {before:,} -> {len(T):,} 字节 "
          f"({len(T)/before*100:.1f}%)   [诊断裁剪副本；不得替代完整存档]")
    if len(T) > 150_000:
        print("  !! 文件较大；若上传失败先检查服务响应和语法，不盲删结构信息")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    v = sub.add_parser('validate')
    v.add_argument('--cif', required=True)
    v.add_argument('--res')
    v.add_argument('--fcf')
    v.add_argument('--lst')
    v.add_argument('--json', help='把结果写成 JSON')

    p = sub.add_parser('prepare')
    p.add_argument('--cif', required=True)
    p.add_argument('--res', help='旧命令兼容参数；不自动推导化学式')
    p.add_argument('--lst', help='旧命令兼容参数；不自动改写绝对结构')
    p.add_argument('--metacif', help='Olex2 的 .metacif（读回晶体尺寸/透射比等）')
    p.add_argument('--out', required=True)
    p.add_argument('--meta', help='JSON 文件，键为 CIF 数据项名')

    u = sub.add_parser('upload')
    u.add_argument('--cif', required=True)
    u.add_argument('--out', required=True)

    a = ap.parse_args()
    if a.cmd == 'validate':
        do_validate(a)
    elif a.cmd == 'prepare':
        do_prepare(a)
    else:
        do_upload(a)


if __name__ == '__main__':
    main()
