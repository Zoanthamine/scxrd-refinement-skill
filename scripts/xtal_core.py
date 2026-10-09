#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xtal_core.py — SCXRD 精修工具箱的通用核心库

设计原则：不硬编码任何化合物相关常量（晶胞、元素、原子名），
全部从 ins / res / cif / hkl 文件读取。

主要能力：
  * 解析 SHELXL 的 ins/res 原子记录（正确处理 '=' 续行）
  * 从 ins 的 SFAC/UNIT/LATT/SYMM 读取元素、计数、空间群
  * 通用对称操作（从 SYMM 行自动解析，支持任意空间群）
  * 分数坐标 -> 笛卡尔坐标；SHELXL Uij 还原为真实 U(Å^2)
  * 共价半径判键、连通分量、分子内/分子间接触
  * hkl 数据质量分壳层统计

用法：
  from xtal_core import Cryst, read_res, parse_symm
"""
from __future__ import annotations
import math, os, re, sys
from collections import defaultdict

# ---------------------------------------------------------------- 元素数据
# 共价半径 (Å)，用于判键
COV = {
    'H': 0.31, 'B': 0.84, 'C': 0.76, 'N': 0.71, 'O': 0.66, 'F': 0.57,
    'Si': 1.11, 'P': 1.07, 'S': 1.05, 'Cl': 1.02, 'Br': 1.20, 'I': 1.39,
    'Se': 1.20, 'Na': 1.66, 'K': 2.03, 'Ca': 1.76, 'Mg': 1.41,
    'Fe': 1.32, 'Zn': 1.22, 'Cu': 1.32, 'Ni': 1.24, 'Co': 1.26,
    'Pd': 1.39, 'Pt': 1.36, 'Au': 1.36, 'Ag': 1.45, 'Sn': 1.39, 'Ge': 1.20,
}
# 范德华半径 (Å)
VDW = {
    'H': 1.20, 'B': 1.92, 'C': 1.70, 'N': 1.55, 'O': 1.52, 'F': 1.47,
    'Si': 2.10, 'P': 1.80, 'S': 1.80, 'Cl': 1.75, 'Br': 1.85, 'I': 1.98,
    'Se': 1.90, 'Na': 2.27, 'K': 2.75, 'Ca': 2.31, 'Mg': 1.73, 'Fe': 2.00,
}
# 原子量
MASS = {
    'H': 1.008, 'B': 10.81, 'C': 12.011, 'N': 14.007, 'O': 15.999, 'F': 18.998,
    'Si': 28.085, 'P': 30.974, 'S': 32.06, 'Cl': 35.45, 'Br': 79.904, 'I': 126.90,
    'Se': 78.97, 'Na': 22.99, 'K': 39.098, 'Ca': 40.078, 'Mg': 24.305,
    'Fe': 55.845, 'Zn': 65.38, 'Cu': 63.546, 'Ni': 58.693, 'Co': 58.933,
}
# 元素符号 -> 常用标签前缀（用于从标签猜元素，仅作 fallback）
def guess_element(label: str, sfac_list=None, sfac_index=None) -> str:
    """优先用 SFAC 序号；否则按标签前缀猜（注意 Si 这类双字母需先匹配）。"""
    if sfac_list and sfac_index is not None and 1 <= sfac_index <= len(sfac_list):
        return sfac_list[sfac_index - 1]
    m = re.match(r'^([A-Z][a-z]?)', label)
    if m:
        s = m.group(1)
        if s in COV or s in VDW:
            return s
    m = re.match(r'^([A-Za-z]{1,2})', label)
    return m.group(1).capitalize() if m else 'C'

NUM = re.compile(r'-?\d+\.\d+')
# 严格原子记录：标签 + 散射因子(1..N) + 至少 3 个小数坐标
ATOM_RX = re.compile(
    r"^([A-Za-z][A-Za-z0-9_]{0,7})\s+(\d+)\s+"
    r"(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)")

KEYWORDS = {
    "TITL", "CELL", "ZERR", "LATT", "SYMM", "SFAC", "UNIT", "L.S.", "CGLS",
    "PLAN", "TEMP", "CONF", "HTAB", "BOND", "MORE", "FMAP", "ACTA", "WGHT",
    "FVAR", "REM", "END", "HKLF", "EQIV", "OMIT", "SHEL", "MERG", "TWIN",
    "BASF", "EXTI", "SWAT", "ANIS", "RIGU", "SIMU", "ISOR", "DELU", "FLAT",
    "CHIV", "SUMP", "EADX", "EADP", "EXYZ", "DFIX", "SADI", "DANG", "FREE",
    "HFIX", "AFIX", "RESI", "BLOC", "STIR", "BIND", "BUMP", "SIZE", "LIST",
    "DAMP", "PEAK", "MOLE", "CONN", "PART", "LAUE", "MOVE", "ANIS.",
}


# ---------------------------------------------------------------- 基本工具
def read_lines(path: str):
    for enc in ('latin-1', 'utf-8', 'cp1252'):
        try:
            with open(path, encoding=enc, errors='strict') as f:
                return f.read().splitlines()
        except (UnicodeDecodeError, LookupError):
            continue
    with open(path, encoding='latin-1', errors='replace') as f:
        return f.read().splitlines()


def write_lines(path: str, lines, encoding='latin-1'):
    """SHELXL 只接受 ASCII/latin-1；中文必须挡在这里。"""
    bad = []
    for i, l in enumerate(lines):
        try:
            l.encode(encoding)
        except UnicodeEncodeError:
            bad.append((i + 1, l[:60]))
    if bad:
        raise ValueError(
            "输出含非 latin-1 字符，SHELXL 会读失败。请先清理：\n" +
            "\n".join(f"  行 {i}: {t}" for i, t in bad[:10]))
    with open(path, 'w', encoding=encoding, newline='\n') as f:
        f.write("\n".join(lines) + "\n")


def is_atom_line(s: str):
    """严格判定是否为原子记录首行（排除 ZERR/PLAN 等同形指令）。"""
    u = s.split()[0].upper() if s.split() else ""
    if u.rstrip('.') in {k.rstrip('.') for k in KEYWORDS}:
        return False
    return bool(ATOM_RX.match(s))


# ---------------------------------------------------------------- 结构容器
class Cryst:
    """晶体结构容器：晶胞 + 对称操作 + 原子。"""

    def __init__(self, cell=None, symm=None, sfac=None, atoms=None,
                 unit=None, title=None):
        self.cell = cell                  # (a,b,c,alpha,beta,gamma)
        self.symm = symm or []            # [(x,y,z), ...] 不含恒等操作也可
        self.sfac = sfac or []            # ['C','H','O','Si']
        self.unit = unit                  # [116,184,16,4]
        self.title = title
        self.atoms = atoms or []          # list[Atom]

    # ---- 晶胞 ----
    def orth_matrix(self):
        a, b, c, al, be, ga = self.cell
        al, be, ga = map(math.radians, (al, be, ga))
        v = math.sqrt(max(1e-12, 1 - math.cos(al)**2 - math.cos(be)**2
                          - math.cos(ga)**2
                          + 2*math.cos(al)*math.cos(be)*math.cos(ga)))
        return [[a, b*math.cos(ga), c*math.cos(be)],
                [0, b*math.sin(ga),
                 c*(math.cos(al)-math.cos(be)*math.cos(ga))/math.sin(ga)],
                [0, 0, c*v/math.sin(ga)]]

    def volume(self):
        M = self.orth_matrix()
        return abs(M[0][0]*(M[1][1]*M[2][2]-M[1][2]*M[2][1])
                   - M[0][1]*(M[1][0]*M[2][2]-M[1][2]*M[2][0])
                   + M[0][2]*(M[1][0]*M[2][1]-M[1][1]*M[2][0]))

    def cart(self, frac):
        M = self.orth_matrix()
        return tuple(M[i][0]*frac[0] + M[i][1]*frac[1] + M[i][2]*frac[2]
                     for i in range(3))

    def frac(self, cart):
        """笛卡尔 -> 分数（用矩阵求逆）"""
        M = self.orth_matrix()
        # 3x3 求逆
        d = (M[0][0]*(M[1][1]*M[2][2]-M[1][2]*M[2][1])
             - M[0][1]*(M[1][0]*M[2][2]-M[1][2]*M[2][0])
             + M[0][2]*(M[1][0]*M[2][1]-M[1][1]*M[2][0]))
        if abs(d) < 1e-12:
            raise ValueError("晶胞矩阵奇异")
        inv = [
            [(M[1][1]*M[2][2]-M[1][2]*M[2][1])/d,
             (M[0][2]*M[2][1]-M[0][1]*M[2][2])/d,
             (M[0][1]*M[1][2]-M[0][2]*M[1][1])/d],
            [(M[1][2]*M[2][0]-M[1][0]*M[2][2])/d,
             (M[0][0]*M[2][2]-M[0][2]*M[2][0])/d,
             (M[0][2]*M[1][0]-M[0][0]*M[1][2])/d],
            [(M[1][0]*M[2][1]-M[1][1]*M[2][0])/d,
             (M[0][1]*M[2][0]-M[0][0]*M[2][1])/d,
             (M[0][0]*M[1][1]-M[0][1]*M[1][0])/d],
        ]
        return tuple(sum(inv[i][j]*cart[j] for j in range(3)) for i in range(3))

    def real_u(self, uout):
        """SHELXL 的 Uij 输出为 U*a_i*a_j；还原为真实 U(Å^2)。
        uout: 3x3 嵌套列表。"""
        L = self.cell[:3]
        return [[uout[i][j] / (L[i]*L[j]) for j in range(3)] for i in range(3)]

    # ---- 对称 ----
    def images(self, frac, span=1):
        """返回 frac 在所有对称操作 + 平移下的全部像。"""
        out = []
        for op in self.symm:
            u = op(*frac)
            for i in range(-span, span + 1):
                for j in range(-span, span + 1):
                    for k in range(-span, span + 1):
                        out.append((u[0] + i, u[1] + j, u[2] + k))
        return out

    def nearest(self, f1, f2, span=1):
        """两分数坐标（考虑对称与平移）之间的最短距离及对应像。"""
        c1 = self.cart(f1)
        best = (float('inf'), None)
        for ff in self.images(f2, span):
            d = math.dist(c1, self.cart(ff))
            if d < best[0]:
                best = (d, ff)
        return best

    def formula_from_unit(self, z):
        """由 UNIT 与 Z 给出每分子式单位的组成。"""
        if not self.unit or not self.sfac or not z:
            return None
        return {el: n / z for el, n in zip(self.sfac, self.unit)}


class Atom:
    __slots__ = ('label', 'el', 'frac', 'occ', 'uiso', 'uij', 'cart', 'U',
                 'sfac', 'riding', 'afix')

    def __init__(self, label, el, frac, occ=1.0, uiso=None, uij=None, sfac=None):
        self.label, self.el, self.frac = label, el, frac
        self.occ, self.uiso, self.uij, self.sfac = occ, uiso, uij, sfac
        self.cart = None
        self.U = None
        self.riding = False    # True = AFIX 骑式（Uiso 字段为负的 AFIX 代码）
        self.afix = None

    def ueq(self):
        if self.uij:
            return sum(self.uij[i][i] for i in range(3)) / 3.0
        return self.uiso

    def is_h(self):
        return self.el == 'H'

    def is_refined(self):
        """坐标是否自由精修（骑式 H 不是）。"""
        return not self.riding



# ---------------------------------------------------------------- 解析器
def parse_symm(lines):
    """从 SYMM 行解析对称操作 -> [callable]（含恒等）。"""
    ops = [lambda x, y, z: (x, y, z)]
    for ln in lines:
        s = ln.strip()
        if not s.upper().startswith('SYMM'):
            continue
        expr = s[4:].strip()
        parts = [p.strip() for p in expr.split(',')]
        if len(parts) != 3:
            continue
        ops.append(_make_op(parts))
    return ops


def _make_op(parts):
    """把 'X+1/2' / '-Y' / '0.5-Z' 这类表达式编译成函数。"""
    compiled = []
    for expr in parts:
        e = expr.upper().replace(' ', '')
        # 提取 X/Y/Z 的系数与常数项
        coeff = 0.0
        const = 0.0
        work = e
        for var, name in (('X', 0), ('Y', 1), ('Z', 2)):
            m = re.search(r'([+-]?\d*\.?\d*)\*?' + var, work)
            if m:
                cs = m.group(1)
                if cs in ('', '+'):
                    c = 1.0
                elif cs == '-':
                    c = -1.0
                elif '/' in cs:
                    num, den = cs.split('/')
                    c = float(num or 1) / float(den)
                else:
                    c = float(cs)
                coeff = c
                work = work[:m.start()] + work[m.end():]
        # 剩余部分作为常数
        work = work.strip()
        if work:
            try:
                if '/' in work and '.' not in work:
                    num, den = work.split('/')
                    const = float(num) / float(den)
                else:
                    const = float(work)
            except ValueError:
                const = 0.0
        compiled.append((coeff, const))
    def op(x, y, z):
        vals = (x, y, z)
        return tuple(compiled[i][0]*vals[i] + compiled[i][1] for i in range(3))
    return op


def read_res(path):
    """解析 SHELXL 的 ins/res 文件 -> Cryst。
    正确处理 '=' 续行；自动跳过 REM / Q 残峰 / ZERR。"""
    raw = read_lines(path)
    cell = symm_lines = sfac = unit = title = None
    atoms = []
    i = 0
    while i < len(raw):
        s = raw[i].strip()
        if not s:
            i += 1
            continue
        u = s.split()[0].upper()
        if u == 'TITL':
            title = s[4:].strip()
        elif u == 'CELL':
            p = s.split()
            cell = tuple(float(x) for x in p[2:8])
        elif u == 'SFAC':
            sfac = [x.capitalize() for x in s.split()[1:]]
        elif u == 'UNIT':
            unit = [int(float(x)) for x in s.split()[1:]]
        elif u == 'SYMM':
            symm_lines = (symm_lines or [])
            symm_lines.append(s)
        elif is_atom_line(s):
            rec = [s]
            i += 1
            while i < len(raw) and rec[-1].rstrip().endswith('='):
                rec.append(raw[i].strip())
                i += 1
            i -= 1
            nums = NUM.findall(' '.join(rec))
            m = ATOM_RX.match(s)
            lab, sf = m.group(1), int(m.group(2))
            if not re.match(r'^Q\d+$', lab) and lab.upper() != 'ZERR':
                frac = (float(nums[0]), float(nums[1]), float(nums[2]))
                occ = float(nums[3]) if len(nums) > 3 else 1.0
                uij = None
                uiso = None
                riding = False
                if len(nums) >= 10:
                    u = [float(v) for v in nums[4:10]]
                    uij = [[u[0], u[5], u[4]], [u[5], u[1], u[3]],
                           [u[4], u[3], u[2]]]
                elif len(nums) == 5:
                    val = float(nums[4])
                    if val < 0:
                        # 负值 = 骑式标记：-1.2 / -1.5 = SHELXL 生成的 AFIX 代码
                        riding = True
                    else:
                        uiso = val
                at = Atom(lab, None, frac, occ, uiso, uij, sfac=sf)
                at.riding = riding
                atoms.append(at)
        i += 1

    c = Cryst(cell=cell, symm=parse_symm(symm_lines or []), sfac=sfac,
              unit=unit, atoms=atoms, title=title)
    # 标注元素与笛卡尔坐标
    for at in c.atoms:
        at.el = guess_element(at.label, c.sfac, at.sfac)
        at.cart = c.cart(at.frac)
        if at.uij:
            at.U = c.real_u(at.uij)
    return c


# ---------------------------------------------------------------- 连接性
def bonds(c, exclude_h=True, tol=1.35):
    """按共价半径判键（含对称操作生成的键）。
    返回 [(Atom, Atom, dist, sym_shift)]。"""
    ats = [a for a in c.atoms if (not exclude_h or not a.is_h())]
    out = []
    for i, x in enumerate(ats):
        for y in ats[i + 1:]:
            rx, ry = COV.get(x.el, 0.8), COV.get(y.el, 0.8)
            cut = (rx + ry) * tol + 0.1
            d, ff = c.nearest(x.frac, y.frac)
            if 0.05 < d < cut:
                out.append((x, y, d, ff))
    return out


def connected_components(atoms, bond_list):
    """按给定键表分连通分量（只用于分子内，忽略纯对称桥连）。"""
    parent = {a.label: a.label for a in atoms}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for x, y, d, ff in bond_list:
        parent[find(x.label)] = find(y.label)
    comp = defaultdict(list)
    for a in atoms:
        comp[find(a.label)].append(a)
    return list(comp.values())


def contacts(c, kind='inter', lo=1.8, hi=3.4):
    """非键接触：kind='all'|'inter'。
    成键判据：d < 1.25*(rcov1+rcov2)。"""
    ats = [a for a in c.atoms if not a.is_h()]
    out = []
    for i, x in enumerate(ats):
        for y in ats[i + 1:]:
            rx, ry = COV.get(x.el, 0.8), COV.get(y.el, 0.8)
            cutb = 1.25 * (rx + ry)
            d, ff = c.nearest(x.frac, y.frac)
            if d < cutb:
                continue
            if lo < d < hi:
                out.append((d, x, y, ff))
    out.sort(key=lambda t: t[0])
    return out


def hbond_candidates(c, hi=3.4):
    """潜在氢键：给体 O/N 与受体 O/N/S/Cl 之间 < hi。"""
    don = [a for a in c.atoms if a.el in ('O', 'N') and not a.is_h()]
    acc = [a for a in c.atoms if a.el in ('O', 'N', 'S', 'Cl', 'F') and not a.is_h()]
    out = []
    for d in don:
        for a in acc:
            if d is a:
                continue
            dist, ff = c.nearest(d.frac, a.frac)
            if dist < hi:
                out.append((dist, d, a, ff))
    out.sort(key=lambda t: t[0])
    return out


# ---------------------------------------------------------------- 数据质量
def read_hkl(path):
    """读 SHELXL HKLF 4 格式：h k l Fo^2 sigma。返回 list，跳过 (0,0,0)。"""
    rows = []
    for ln in read_lines(path):
        p = ln.split()
        if len(p) != 5:
            continue
        try:
            h, k, l = int(p[0]), int(p[1]), int(p[2])
            f2, s = float(p[3]), float(p[4])
        except ValueError:
            continue
        if (h, k, l) == (0, 0, 0):
            continue
        rows.append((h, k, l, f2, s))
    return rows


def d_spacing(cell, h, k, l):
    a, b, cc, al, be, ga = cell
    al, be, ga = map(math.radians, (al, be, ga))
    v = math.sqrt(max(1e-12, 1 - math.cos(al)**2 - math.cos(be)**2
                      - math.cos(ga)**2
                      + 2*math.cos(al)*math.cos(be)*math.cos(ga)))
    return v / math.sqrt(
        (h/a)**2 + (k/b)**2 + (l/cc)**2
        + 2*(k/cc)*(l/b)*0  # 正交项在此近似；三斜请用完整式
    ) if v else None


def shell_stats(rows, cell,edges=None):
    """按 d 壳层统计 I>2σ 比例、中位 I/σ、平均 Fo²。"""
    a, b, c = cell[:3]
    def dsp(h, k, l):
        return 1.0 / math.sqrt((h/a)**2 + (k/b)**2 + (l/c)**2)
    if edges is None:
        edges = [(0.80, 0.85), (0.85, 0.90), (0.90, 0.95), (0.95, 1.00),
                 (1.00, 1.10), (1.10, 1.20), (1.20, 1.40), (1.40, 1.60),
                 (1.60, 2.00), (2.00, 99.0)]
    out = []
    for lo, hi in edges:
        sel = [(f, s) for h, k, l, f, s in rows if lo <= dsp(h, k, l) < hi and s > 0]
        if not sel:
            continue
        n = len(sel)
        g2 = sum(1 for f, s in sel if f > 2*s) / n * 100
        g3 = sum(1 for f, s in sel if f > 3*s) / n * 100
        r = sorted(f/s for f, s in sel)
        out.append(dict(lo=lo, hi=hi, n=n, gt2=g2, gt3=g3,
                        med_isig=r[len(r)//2],
                        mean_fo2=sum(f for f, s in sel)/n))
    return out


def _symm_rotation_matrix(op):
    """由对称操作函数提取 3x3 旋转部分（数值微分法，通用）。"""
    o = op(0.0, 0.0, 0.0)
    e = 1e-6
    cols = []
    for k in range(3):
        v = [0.0, 0.0, 0.0]
        v[k] = e
        p = op(*v)
        cols.append([(p[i] - o[i]) / e for i in range(3)])
    return [[cols[k][i] for k in range(3)] for i in range(3)]


def point_group_from_symm(symm_ops):
    """由实空间 SYMM 导出倒空间 Laue 类操作（含 Friedel）。
    倒空间旋转 = 实空间旋转矩阵的转置。"""
    ops, seen = [], set()
    for op in symm_ops:
        R = _symm_rotation_matrix(op)
        Rt = tuple(tuple(int(round(R[j][i])) for j in range(3)) for i in range(3))
        if Rt not in seen:
            seen.add(Rt); ops.append(Rt)
    for Rt in list(ops):
        neg = tuple(tuple(-x for x in row) for row in Rt)
        if neg not in seen:
            seen.add(neg); ops.append(neg)
    return [ [list(r) for r in op] for op in ops ]


def hkl_laue_class(h, k, l, pg_ops):
    """把 hkl 归到 Laue 类代表。"""
    best = None
    for R in pg_ops:
        t = (int(round(R[0][0]*h + R[0][1]*k + R[0][2]*l)),
             int(round(R[1][0]*h + R[1][1]*k + R[1][2]*l)),
             int(round(R[2][0]*h + R[2][1]*k + R[2][2]*l)))
        if best is None or t < best:
            best = t
    return best


def hkl_rint(rows, cell=None, symm_ops=None, pg_ops=None):
    """按 Laue 类（含 Friedel）计算 Rint / Rsigma。

    pg_ops   直接给出倒空间操作（优先）
    symm_ops 由实空间 SYMM 操作推导
    都没有   退回 ±h,±k,±l 全对称（对三斜 Laue 类 -1 是正确的）
    """
    if pg_ops is None:
        if symm_ops:
            pg_ops = point_group_from_symm(symm_ops)
        else:
            pg_ops = [[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                      [[-1, 0, 0], [0, -1, 0], [0, 0, -1]]]
    groups = defaultdict(list)
    for r in rows:
        h, k, l, f, s = r[0], r[1], r[2], r[3], r[4]
        groups[hkl_laue_class(h, k, l, pg_ops)].append((f, s))
    num = den = 0.0
    sig_num = sig_den = 0.0
    nref = 0
    mult = defaultdict(int)
    for g, vals in groups.items():
        mult[len(vals)] += 1
        if len(vals) < 2:
            continue
        m = sum(v[0] for v in vals) / len(vals)
        for f, s in vals:
            num += abs(f - m)
            den += f
            sig_num += s*s
            sig_den += f*f
            nref += 1
    return dict(
        rint=(num/den*100 if den else 0),
        rsigma=(math.sqrt(sig_num)/math.sqrt(sig_den)*100 if sig_den else 0),
        nref=nref, ngroups=len(groups), multiplicity=dict(sorted(mult.items())))

def mol_volume(c):
    """范德华体积和（用于堆积/空腔粗估）"""
    return sum(4/3*math.pi*VDW.get(a.el, 1.7)**3 for a in c.atoms)

def molecular_mass(c, z=1):
    """由 UNIT/Z 计算分子量（含 H 时用 UNIT 的 H 计数）"""
    if not (c.unit and c.sfac):
        return None
    return sum(MASS.get(el, 12.0)*n/z for el, n in zip(c.sfac, c.unit))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    cr = read_res(sys.argv[1])
    print(f"TITL: {cr.title}")
    print(f"CELL: {cr.cell}")
    print(f"SFAC: {cr.sfac}   UNIT: {cr.unit}")
    print(f"对称操作数(含恒等): {len(cr.symm)}")
    print(f"原子数: {len(cr.atoms)} "
          f"(重原子 {sum(1 for a in cr.atoms if not a.is_h())}, "
          f"H {sum(1 for a in cr.atoms if a.is_h())})")
    print(f"晶胞体积: {cr.volume():.2f} A^3")
    bl = bonds(cr)
    print(f"共价键数(不含 H): {len(bl)}")
    comps = connected_components([a for a in cr.atoms if not a.is_h()], bl)
    print(f"分子连通分量: {[len(x) for x in comps]}")
