#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
03_run.py — 精修运行器（议题驱动 + 归档留痕）

核心设计（议题驱动的精修流程）：
  * 每轮 = 一个议题（氢修正/空间群/无序/权重/孪晶/ADP 稳定性），不是机械重跑
  * SHELXL 在【本地临时目录】运行，结束后把产物拷回归档目录
    —— 避开 Synology/OneDrive 同步锁造成的 "ReplaceFileW EIO"
  * 保留有序科学指令，仅修改显式请求的运行控制；移除 HKLF 后的建议尾部
  * 自动从 lst 提取 R1/wR2/GooF/Flack(Parsons)/残峰/建议 WGHT，并立刻打印
  * 自动记录到 history.csv

用法：
  # 单轮
  python 03_run.py --base <基底 res> --stage r01_baseline --dir <归档根目录> [-o <overlay 指令文件或字符串>]

  # 批量（每行: stage|base|extra）
  python 03_run.py --batch batch.txt --dir <归档根目录>

选项：
  --job NAME      作业名（默认 model）
  --hkl PATH      覆盖 hkl（默认找与 base 同名的 .hkl）
  --cycles N      L.S. 循环数（默认继承基底，缺失则 20）
  --no-acta       不出 CIF
  --threads N     SHELXL 线程数（默认 4；超线程机器建议核数一半）
  --list N        插入 LIST N（做残峰/无序分析时用）
  --plain         不清洗基底，原样复制（用于复现原始结果）
"""
import os, re, sys, csv, json, glob, shutil, argparse, subprocess, tempfile, time, hashlib
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xtal_core import read_lines, write_lines, read_res, is_atom_line

SHELX = os.environ.get("SHELXL_EXE") or shutil.which("shelxl") or "shelxl"
HIST_FIELDS = ['stage', 'job', 'time', 'R1_gt', 'R1_all', 'wR2', 'GooF', 'Flack',
               'Flack_parsons', 'npar', 'peak', 'hole', 'WGHT_used', 'WGHT_next',
               'shift_esd', 'maxshift_A', 'nrefl', 'notes']


# Preserve input semantics; only explicitly requested run controls are changed.
def clean_ins(text_lines, job='model', cycles=None, acta=None, list_n=None,
              keep_rem=False):
    """Preserve ordered scientific input; trim RES suggestions after HKLF."""
    # Preserve scientific instructions and their order. Normalize only run controls.
    out = []
    have_hkl = False
    continuing = False
    for raw in text_lines:
        s = raw.strip()
        if not s:
            out.append(raw)
            continue
        key = s.split()[0].upper()
        if continuing:
            out.append(raw)
            continuing = s.endswith('=')
            continue
        if key == 'END':
            break
        if have_hkl:
            continue  # RES tail contains suggested WGHT and Q peaks, not active input.
        if s.startswith('+') or key == 'ABIN':
            raise ValueError('External include/ABIN dependencies require an explicit prepared workspace.')
        if key == 'HKLF':
            have_hkl = True
        if key in ('L.S.', 'CGLS') and cycles is not None:
            fields = s.split()
            fields[1] = str(cycles)
            raw = ' '.join(fields)
        if key == 'ACTA' and acta is False:
            continue
        if key == 'LIST' and list_n is not None:
            raw = f'LIST {list_n}'
        out.append(raw)
        continuing = s.endswith('=')
    if not have_hkl:
        raise ValueError('Missing HKLF: refusing to invent a reflection format.')
    idx = next(i for i,l in enumerate(out) if l.strip().upper().startswith('HKLF '))
    keys = {l.strip().split()[0].upper() for l in out if l.strip()}
    controls = []
    if not keys.intersection({'L.S.', 'CGLS'}):
        controls.append(f'L.S. {cycles or 20}')
    if acta and 'ACTA' not in keys:
        controls.append('ACTA')
    if list_n is not None and 'LIST' not in keys:
        controls.append(f'LIST {list_n}')
    out[idx:idx] = controls
    return out + ['END']



def ensure_weights(text, wght=None):
    """写入指定 WGHT（None 则沿用基底）。"""
    if wght is None:
        return list(text)
    out = [l for l in text if not l.strip().upper().startswith('WGHT')]
    if wght:
        idx = next((i for i, l in enumerate(out) if is_atom_line(l)),
                   next(i for i,l in enumerate(out) if l.strip().upper().startswith('HKLF')))
        out.insert(idx, f"WGHT {wght}")
    return out


# ---------------------------------------------------------------- 结果解析
def parse_lst(path):
    """从 lst 提取全部关键指标。"""
    try:
        t = Path(path).read_text(encoding='latin-1', errors='replace')
    except OSError:
        return {}
    d = {}
    m = re.search(r"R1\s*=\s*([\d\.]+)\s+for\s+(\d+)\s+Fo\s*>\s*4sig\(Fo\)\s+and\s+"
                  r"([\d\.]+)\s+for all\s+(\d+)\s+data", t)
    if m:
        d['R1_gt'], d['n_gt'] = float(m.group(1)), int(m.group(2))
        d['R1_all'], d['n_all'] = float(m.group(3)), int(m.group(4))
    m = re.search(r"wR2\s*=\s*([\d\.]+),\s*GooF\s*=\s*S\s*=\s*([\d\.]+)", t)
    if m:
        d['wR2'], d['GooF'] = float(m.group(1)), float(m.group(2))
    m = re.search(r"Flack x\s*=\s*(-?[\d\.]+)\((\d+)\)", t)
    if m:
        d['Flack'] = f"{m.group(1)}({m.group(2)})"
    m = re.search(r"(-?[\d\.]+)\((\d+)\)\s+from\s+(\d+)\s+selected quotients", t)
    if m:
        d['Flack_parsons'] = f"{m.group(1)}({m.group(2)})"
        d['nquotients'] = int(m.group(3))
    m = re.search(r"Recommended weighting scheme:\s*WGHT\s+([\d\.\-]+)\s+([\d\.\-]+)", t)
    if m:
        d['WGHT_next'] = f"{m.group(1)} {m.group(2)}"
    m = re.search(r"Highest peak\s+([\d\.\-]+)", t)
    if m:
        d['peak'] = float(m.group(1))
    m = re.search(r"Deepest hole\s+([\d\.\-]+)", t)
    if m:
        d['hole'] = float(m.group(1))
    m = re.search(r"Total number of l\.s\. parameters\s*=\s*(\d+)", t)
    if m:
        d['npar'] = int(m.group(1))
    m = re.search(r"R\(int\)\s*=\s*([\d\.]+)\s+R\(sigma\)\s*=\s*([\d\.]+)", t)
    if m:
        d['Rint'], d['Rsigma'] = float(m.group(1)), float(m.group(2))
    numeric = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?"
    shifts = re.findall(r"Mean shift/esd\s*=\s*(" + numeric + r")\s+Maximum\s*=\s*(" + numeric + r")", t)
    if shifts:
        d['shift_esd'] = shifts[-1][1]
    shifts_a = re.findall(r"Max\. shift\s*=\s*(" + numeric + r")\s*A", t)
    if shifts_a:
        d['maxshift_A'] = float(shifts_a[-1])
    m = re.search(r"Weight\s*=\s*1\s*/\s*\[\s*sigma\^2\(Fo\^2\)\s*\+\s*\(\s*([\d\.]+)\s*\*\s*P\s*\)"
                  r"\^2\s*\+\s*([\d\.]+)\s*\*\s*P\s*\]", t)
    if m:
        d['WGHT_used'] = f"{m.group(1)} {m.group(2)}"
    # 失败/警告标记
    marks = [l.strip() for l in t.splitlines() if '**' in l and
             any(k in l for k in ('ERROR', 'WARNING', 'BAD', 'NO ATOMS',
                                  'MISSING', 'CONFLICT', 'WRONG', 'NPD',
                                  'Absolute structure'))]
    if marks:
        d['marks'] = '; '.join(m[:80] for m in marks[:4])
    return d


def summarize_one(arch_dir, job):
    lst = os.path.join(arch_dir, job + '.lst')
    d = parse_lst(lst)
    return d


# ---------------------------------------------------------------- 运行
def _safe_copy(src, dst, tries=6):
    """带重试的拷贝 —— 云同步（Synology/OneDrive）会短暂锁住目标文件。"""
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
        except (PermissionError, OSError):
            time.sleep(0.35 * (k + 1))
    # 最后再试一次直接覆盖
    try:
        shutil.copyfile(src, dst)
        return True
    except OSError:
        print(f"  !! 无法归档 {os.path.basename(dst)}（被占用/只读），请手动复制")
        return False


def _run_once(lines, hkl, arch, job, threads, timeout):
    """把 ins 写到本地临时目录跑 SHELXL，产物拷回 arch。返回输出字节。"""
    tmp = tempfile.mkdtemp(prefix=f'xtal_{job}_')
    write_lines(os.path.join(tmp, job + '.ins'), lines, encoding='latin-1')
    shutil.copy(hkl, os.path.join(tmp, job + '.hkl'))
    cmd = [SHELX, job, f'-t{threads}']
    failure = None
    try:
        p = subprocess.run(cmd, cwd=tmp, capture_output=True, timeout=timeout)
        out = (p.stdout or b'') + (p.stderr or b'')
        if p.returncode != 0:
            failure = f'SHELXL exit {p.returncode}'
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b'') + (e.stderr or b'')
        failure = f'SHELXL timeout after {timeout}s'
    for f in glob.glob(os.path.join(tmp, job + '.*')):
        if not _safe_copy(f, os.path.join(arch, os.path.basename(f))):
            failure = 'Archiving failed'
    Path(arch, 'console.txt').write_bytes(out)
    for ext in ('.res', '.lst'):
        pth = os.path.join(tmp, job + ext)
        if not os.path.exists(pth) or os.path.getsize(pth) == 0:
            failure = f'Missing/empty {ext}'
    if failure:
        raise RuntimeError(f'{failure}; temporary files retained: {tmp}')
    if not parse_lst(os.path.join(tmp, job + '.lst')).get('wR2'):
        raise RuntimeError(f'No refinement statistics; retained: {tmp}')
    shutil.rmtree(tmp, ignore_errors=True)
    return out


def _print_summary(stage, job, arch, out, d):
    res_p = os.path.join(arch, job + '.res')
    res_size = os.path.getsize(res_p) if os.path.exists(res_p) else 0
    print(f"\n### {stage}  (job={job})")
    if res_size == 0:
        print("  !! res 为 0 字节 —— 运行失败。检查 console.txt 与下方标记")
    for l in out.decode('latin-1', 'replace').splitlines():
        if '**' in l or 'finished' in l:
            print("  [shelxl] " + l.strip()[:110])
    if d:
        print(f"  R1(I>2s)={d.get('R1_gt')}  R1(all)={d.get('R1_all')}  "
              f"wR2={d.get('wR2')}  GooF={d.get('GooF')}")
        print(f"  残峰={d.get('peak')}/{d.get('hole')}  npar={d.get('npar')}  "
              f"Flack={d.get('Flack')}  Parsons={d.get('Flack_parsons')}")
        if d.get('WGHT_used') and d.get('WGHT_next'):
            print(f"  WGHT used={d['WGHT_used']}  next={d['WGHT_next']}{wght_gap_tag(d)}")


def wght_gap_tag(d, tol=0.05):
    try:
        a = [float(x) for x in d['WGHT_used'].split()]
        b = [float(x) for x in d['WGHT_next'].split()]
        diff = max(abs(a[0]-b[0]), abs(a[1]-b[1]))
        return "  <-- 权重差满足脚本阈值" if diff < tol else f"  (差 {diff:.4f})"
    except (ValueError, IndexError, KeyError):
        return ""


def wght_gap(d):
    try:
        a = [float(x) for x in d['WGHT_used'].split()]
        b = [float(x) for x in d['WGHT_next'].split()]
        return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
    except (ValueError, IndexError, KeyError):
        return None


def _log_history(root, stage, job, d):
    hist = os.path.join(root, 'history.csv')
    new = not os.path.exists(hist)
    with open(hist, 'a', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=HIST_FIELDS, extrasaction='ignore')
        if new:
            w.writeheader()
        row = dict(stage=stage, job=job,
                   time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                   nrefl=d.get('n_all'), notes=d.get('marks', ''))
        for k in ('R1_gt', 'R1_all', 'wR2', 'GooF', 'Flack', 'Flack_parsons',
                  'npar', 'peak', 'hole', 'WGHT_used', 'WGHT_next',
                  'shift_esd', 'maxshift_A'):
            row[k] = d.get(k, '')
        w.writerow(row)


def run_stage(base, stage, root, job='model', hkl=None, extra=None,
              cycles=None, acta=None, threads=4, list_n=None, plain=False,
              wght=None, timeout=300, converge=0):
    """跑一轮（或自动权重迭代多轮）。

    converge=N: 若某轮的 SHELXL 建议 WGHT 与本次使用值差异 > 0.05，
                自动用建议值再修一轮，最多 N 次（仅权重稳定性检查，不代替 CIF/RES 一致性检查）。
    """
    if converge < 0:
        raise ValueError('converge must be nonnegative')
    if os.path.basename(stage) != stage or stage in ('.', '..'):
        raise ValueError('stage must be a single directory name')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', job):
        raise ValueError('job must be a simple ASCII basename')
    arch = os.path.join(root, stage)
    os.makedirs(arch, exist_ok=False)

    # 找 hkl
    if hkl is None:
        cand = os.path.splitext(base)[0] + '.hkl'
        if os.path.exists(cand):
            hkl = cand
        else:
            g = sorted(glob.glob(os.path.join(os.path.dirname(base), '*.hkl')),
                       key=lambda p: -os.path.getsize(p))
            if len(g) > 1:
                raise ValueError('Multiple HKL files: specify --hkl explicitly.')
            hkl = g[0] if g else None
    if not hkl or not os.path.exists(hkl):
        raise FileNotFoundError(f"找不到 hkl 文件（base={base}）")

    cur_base = base
    cur_wght = wght
    d = {}
    for it in range(converge + 1):
        if any(l.strip().startswith('+') or l.strip().upper().startswith('ABIN ') for l in read_lines(cur_base)):
            raise ValueError('External dependencies require a prepared dedicated workspace')
        lines = (read_lines(cur_base) if plain else
                 clean_ins(read_lines(cur_base), job=job, cycles=cycles,
                           acta=acta, list_n=list_n))
        lines = ensure_weights(lines, cur_wght)
        if extra and it == 0:
            add = ([l.strip() for l in read_lines(extra) if l.strip()]
                   if os.path.exists(extra) else
                   [x.strip() for x in re.split(r'[;\n]', extra) if x.strip()])
            for record in add:
                key = record.split()[0].upper()
                if key in {'PART','FVAR','AFIX','RESI','CELL','ZERR','LATT','SYMM','SFAC','UNIT','HKLF','END'} or is_atom_line(record):
                    raise ValueError('Structural overlays are unsupported: prepare a complete INS')
            idx = next((i for i, l in enumerate(lines) if is_atom_line(l)),
                       next(i for i,l in enumerate(lines) if l.strip().upper().startswith('HKLF')))
            lines = lines[:idx] + add + lines[idx:]

        if any(l.strip().upper().startswith('ACTA') for l in lines):
            for l in lines:
                fields = l.strip().upper().split()
                if len(fields)>1 and fields[0] in {'LIST','MERG','FMAP'} and fields[1] != {'LIST':'4','MERG':'2','FMAP':'2'}[fields[0]]:
                    raise ValueError('ACTA conflicts with explicit LIST/MERG/FMAP; review the intended protocol')
        iter_arch = arch if it == 0 else os.path.join(arch, f'weight_{it:02d}')
        if it:
            os.makedirs(iter_arch, exist_ok=False)
        out = _run_once(lines, hkl, iter_arch, job, threads, timeout)
        d = summarize_one(iter_arch, job)
        _print_summary(stage + (f" [weight iter {it+1}]" if it else ""),
                       job, iter_arch, out, d)
        _log_history(root, stage, job, d)

        if it >= converge:
            break
        gap = wght_gap(d)
        if gap is None or gap < 0.05:
            if gap is not None:
                print("  → 权重差满足脚本阈值；仍需检查坐标/ADP 收敛")
            break
        nxt = d.get('WGHT_next')
        if not nxt:
            break
        print(f"  → 权重未收敛（差 {gap:.4f}），用建议值 {nxt} 再修一轮")
        res_p = os.path.join(iter_arch, job + '.res')
        if not os.path.exists(res_p) or os.path.getsize(res_p) == 0:
            break
        cur_base = res_p
        cur_wght = nxt

    with open(os.path.join(arch, 'run_result.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(final_directory=os.path.abspath(iter_arch), base=os.path.abspath(base), hkl=os.path.abspath(hkl),
                        hkl_sha256=hashlib.sha256(Path(hkl).read_bytes()).hexdigest(), metrics=d), f, indent=2)
    return iter_arch, d



def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', help='基底 res/ins')
    ap.add_argument('--stage', help='轮次名（归档子目录名）')
    ap.add_argument('--dir', required=True, help='归档根目录（history.csv 也放这里）')
    ap.add_argument('--batch', help='批量文件：每行 stage|base|extra')
    ap.add_argument('--job', default='model')
    ap.add_argument('--hkl')
    ap.add_argument('-o', '--overlay', help='额外指令：文件路径或分号分隔字符串')
    ap.add_argument('--cycles', type=int)
    ap.add_argument('--wght', help='写入指定 WGHT，如 "0.1011 1.7464"')
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--list', dest='list_n', type=int)
    ap.add_argument('--shelxl', help='SHELXL executable path')
    group = ap.add_mutually_exclusive_group()
    group.add_argument('--acta', dest='acta', action='store_true', default=None)
    group.add_argument('--no-acta', dest='acta', action='store_false')
    ap.add_argument('--plain', action='store_true')
    ap.add_argument('--timeout', type=int, default=300)
    ap.add_argument('--converge', type=int, default=0,
                    help='自动权重迭代轮数：若 SHELXL 建议 WGHT 与使用值差 >0.05，'
                         '则用建议值再修，最多 N 次（仅权重稳定性检查，不代替 CIF/RES 一致性检查）')
    a = ap.parse_args()
    global SHELX
    if a.shelxl:
        SHELX = a.shelxl

    os.makedirs(a.dir, exist_ok=True)

    if a.batch:
        n = 0
        previous_res = a.base
        for ln in read_lines(a.batch):
            s = ln.strip()
            if not s or s.startswith('#'):
                continue
            parts = [p.strip() for p in s.split('|')]
            while len(parts) < 3:
                parts.append('')
            st, bse, ex = parts[0], parts[1], parts[2]
            if not bse:
                bse = previous_res
            if not bse:
                ap.error('First batch row requires base or --base.')
            print(f"\n{'='*88}\n=== {st}  <- {os.path.basename(str(bse))}"
                  f"{('  + ' + ex[:60]) if ex else ''}")
            last_arch, _ = run_stage(bse, st, a.dir, job=a.job, hkl=a.hkl, extra=ex or None,
                      cycles=a.cycles, acta=a.acta, threads=a.threads,
                      list_n=a.list_n, plain=a.plain, wght=a.wght,
                      timeout=a.timeout, converge=a.converge)
            previous_res = os.path.join(last_arch, a.job + '.res')
            n += 1
        print(f"\n完成 {n} 轮，history.csv 已更新：{os.path.join(a.dir,'history.csv')}")
        return

    if not (a.base and a.stage):
        ap.error("单轮模式需要 --base 与 --stage")
    run_stage(a.base, a.stage, a.dir, job=a.job, hkl=a.hkl, extra=a.overlay,
              cycles=a.cycles, acta=a.acta, threads=a.threads,
              list_n=a.list_n, plain=a.plain, wght=a.wght, timeout=a.timeout,
              converge=a.converge)


if __name__ == '__main__':
    main()
