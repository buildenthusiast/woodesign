"""Оптимизация на разкроя (гилотинен разкрой – както реже форматен циркуляр).

Всяка плоча се реже с прави резове от край до край. Отчитат се:
  * дебелина на диска (kerf);
  * обрез по краищата на плочата (повредени ръбове);
  * посока на фладера – детайл с фладер не се завърта;
  * материали без фладер – детайлите могат да се завъртат на 90°.
Алгоритъм: многократно подреждане с различни евристики + случайни
пермутации, избира се резултатът с най-малко плочи и най-голям остатък.
"""
import random
from dataclasses import dataclass, field


@dataclass
class Piece:
    pid: int
    label: str
    l: float      # по фладера (X на плочата)
    w: float
    grain: bool   # True = не може да се върти


@dataclass
class Placed:
    piece: Piece
    x: float
    y: float
    dx: float
    dy: float
    rotated: bool


@dataclass
class Sheet:
    L: float
    W: float
    placed: list = field(default_factory=list)
    free: list = field(default_factory=list)

    def used_area(self):
        return sum(p.dx * p.dy for p in self.placed)


@dataclass
class CutResult:
    material_key: str
    sheet_l: float
    sheet_w: float
    sheets: list
    unplaced: list
    kerf: float
    trim: float

    @property
    def n_sheets(self):
        return len(self.sheets)

    def utilization(self):
        if not self.sheets:
            return 0.0
        total = self.sheet_l * self.sheet_w * len(self.sheets)
        return sum(s.used_area() for s in self.sheets) / total

    def cut_length_m(self):
        """Ориентировъчна дължина на резовете (м) – за цена на услугата."""
        tot = 0.0
        for s in self.sheets:
            for p in s.placed:
                tot += p.dx + p.dy
        return tot / 1000.0


def _fits(fr, dx, dy):
    return dx <= fr[2] + 1e-6 and dy <= fr[3] + 1e-6


def _pack(pieces, L, W, kerf, trim, split_rule, fit_rule):
    sheets = []
    unplaced = []
    UL, UW = L - 2 * trim, W - 2 * trim
    for pc in pieces:
        orients = [(pc.l, pc.w, False)]
        if not pc.grain and abs(pc.l - pc.w) > 0.01:
            orients.append((pc.w, pc.l, True))
        if not any(dx <= UL and dy <= UW for dx, dy, _ in orients):
            unplaced.append(pc)
            continue
        best = None
        for si, sh in enumerate(sheets):
            for fi, fr in enumerate(sh.free):
                for dx, dy, rot in orients:
                    if _fits(fr, dx, dy):
                        lw, lh = fr[2] - dx, fr[3] - dy
                        if fit_rule == "bssf":
                            score = (min(lw, lh), max(lw, lh))
                        elif fit_rule == "baf":
                            score = (fr[2] * fr[3] - dx * dy, min(lw, lh))
                        else:  # blsf
                            score = (max(lw, lh), min(lw, lh))
                        score = (si,) + score  # предпочита по-ранни плочи
                        if best is None or score < best[0]:
                            best = (score, si, fi, dx, dy, rot)
        if best is None:
            sh = Sheet(L, W, [], [(trim, trim, UL, UW)])
            sheets.append(sh)
            fr = sh.free[0]
            for dx, dy, rot in orients:
                if _fits(fr, dx, dy):
                    best = (None, len(sheets) - 1, 0, dx, dy, rot)
                    break
        _, si, fi, dx, dy, rot = best
        sh = sheets[si]
        fx, fy, fw, fh = sh.free.pop(fi)
        sh.placed.append(Placed(pc, fx, fy, dx, dy, rot))
        rw = fw - dx - kerf     # остатък вдясно
        rh = fh - dy - kerf     # остатък отгоре
        if split_rule == "auto":
            horiz = rw * fh < fw * rh   # запазва по-големия остатък цял
        else:
            horiz = split_rule == "h"
        if horiz:
            # хоризонтален рез през цялата ширина
            right = (fx + dx + kerf, fy, rw, dy)
            topr = (fx, fy + dy + kerf, fw, rh)
        else:
            right = (fx + dx + kerf, fy, rw, fh)
            topr = (fx, fy + dy + kerf, dx, rh)
        for r in (right, topr):
            if r[2] > 1 and r[3] > 1:
                sh.free.append(r)
    return sheets, unplaced


def _score(sheets):
    if not sheets:
        return (0, 0)
    last = sheets[-1]
    return (len(sheets), last.used_area())


def optimize(material_key, sheet_l, sheet_w, pieces, kerf=4.0, trim=10.0, iterations=300, seed=1):
    rng = random.Random(seed)
    orders = [
        lambda p: -(p.l * p.w),
        lambda p: -max(p.l, p.w),
        lambda p: -p.l,
        lambda p: -p.w,
        lambda p: -(p.l + p.w),
    ]
    best = None
    rules = [(s, f) for s in ("auto", "h", "v") for f in ("bssf", "baf", "blsf")]

    def consider(seq, s, f):
        nonlocal best
        sh, un = _pack(seq, sheet_l, sheet_w, kerf, trim, s, f)
        sc = (len(un),) + _score(sh)
        if best is None or sc < best[0]:
            best = (sc, sh, un)

    for key in orders:
        seq = sorted(pieces, key=key)
        for s, f in rules:
            consider(seq, s, f)
    base = sorted(pieces, key=orders[0])
    for _ in range(iterations):
        seq = base[:]
        # леко разбъркване: размяна на съседни групи
        for _k in range(max(1, len(seq) // 4)):
            i = rng.randrange(len(seq)) if seq else 0
            j = min(len(seq) - 1, i + rng.randint(1, 3))
            if seq:
                seq[i], seq[j] = seq[j], seq[i]
        s, f = rng.choice(rules)
        consider(seq, s, f)
    _, sheets, unplaced = best
    return CutResult(material_key, sheet_l, sheet_w, sheets, unplaced, kerf, trim)


def optimize_project(parts, catalog, kerf=4.0, trim=10.0, reduce_band=True, iterations=300):
    """parts: списък Part (агрегирани). Връща {material_key: CutResult} и номерацията."""
    M = {m["key"]: m for m in catalog["materials"]}
    by_mat = {}
    pid = 0
    numbering = []
    for idx, p in enumerate(parts):
        numbering.append(idx + 1)
        l, w = p.cut_size(catalog["bands"], reduce_band)
        mat = M[p.material]
        for _ in range(p.qty):
            pid += 1
            by_mat.setdefault(p.material, []).append(Piece(pid, str(idx + 1), l, w, bool(mat["grain"])))
    results = {}
    for mk, pcs in by_mat.items():
        m = M[mk]
        results[mk] = optimize(mk, m["sheet_l"], m["sheet_w"], pcs, kerf, trim, iterations)
    return results
