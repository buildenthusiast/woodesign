"""Параметрично генериране на детайли, обков и чертеж за корпусна мебел.

Модел: корпус (две страници, дъно, таван/траверси, гръб, основа), разделен
вертикално на секции. Всяка секция отдолу нагоре съдържа:
  [зона чекмеджета] [зона врати (или отворена)] [отворена зона над вратите]
Всички размери са в мм. Координати за чертежа: (0,0) долу вляво, изглед отпред.
"""
from dataclasses import dataclass, field
import math

from .catalog import find, FURNITURE_TYPES

SHELF_SPAN_LIMIT = {16: 700, 18: 800, 19: 800, 22: 900, 25: 1000, 28: 1100}


@dataclass
class Part:
    module: str
    name: str
    length: float          # размер по фладера (готов размер, с канта)
    width: float
    qty: int
    material: str          # ключ на материал
    edges: dict = field(default_factory=lambda: {"L1": "none", "L2": "none", "W1": "none", "W2": "none"})
    note: str = ""

    def cut_size(self, bands, reduce=True):
        """Размер за рязане: готов размер минус дебелината на кантовете >= 1 мм."""
        def bt(k):
            b = find(bands, self.edges.get(k, "none"))
            return b["t"] if (reduce and b["t"] >= 1.0) else 0.0
        l = self.length - bt("W1") - bt("W2")
        w = self.width - bt("L1") - bt("L2")
        return round(l, 1), round(w, 1)

    def band_meters(self):
        """Връща {ключ_кант: метри} за един брой."""
        res = {}
        for k, v in self.edges.items():
            if v == "none":
                continue
            size = self.length if k.startswith("L") else self.width
            res[v] = res.get(v, 0) + size / 1000.0
        return res


@dataclass
class Hw:
    name: str
    qty: float
    unit: str = "бр."
    price_key: str = ""
    price: float = 0.0


@dataclass
class BuildResult:
    parts: list
    hardware: list
    warnings: list
    shapes: list   # (kind, x, y, w, h, label)
    info: list


def default_item(ftype="wardrobe", catalog=None):
    base = {
        "name": FURNITURE_TYPES.get(ftype, "Модул"), "type": ftype,
        "W": 1000, "H": 2000, "D": 560,
        "carcass_mat": "pdch18_bial", "front_mat": "pdch18_bial", "back_mat": "hdf3_bial",
        "drawer_mat": "pdch16_bial", "drawer_bottom_mat": "hdf3_bial",
        "carcass_band": "0.8", "front_band": "2.0", "drawer_band": "0.4",
        "base": "legs", "base_h": 100, "top": "between", "back": "nailed",
        "hinge": "soft110", "slide": "ball", "handle": "handle", "gap": 3,
        "sections": [new_section()],
    }
    presets = {
        "base": dict(W=600, H=820, D=560, base="legs", base_h=100, top="rails", sections=[new_section(doors=1, shelves=1)]),
        "wall": dict(W=600, H=720, D=320, base="wall", base_h=0, top="between", sections=[new_section(doors=1, shelves=2)]),
        "tall": dict(W=600, H=2100, D=560, base="legs", base_h=100, top="between", sections=[new_section(doors=2, shelves=4)]),
        "wardrobe": dict(W=1500, H=2400, D=600, base="plinth", base_h=80, top="between"),
        "chest": dict(W=900, H=850, D=450, base="plinth", base_h=60, top="over", sections=[new_section(doors=0, shelves=0, drawers=4, drawer_h=0)]),
        "night": dict(W=450, H=500, D=400, base="legs", base_h=60, top="over", sections=[new_section(doors=0, shelves=0, drawers=2, drawer_h=0)]),
        "tv": dict(W=1600, H=500, D=400, base="legs", base_h=60, top="over", D_=0),
        "shelf": dict(W=900, H=2000, D=300, base="plinth", base_h=60, top="over", sections=[new_section(doors=0, shelves=5)]),
        "custom": dict(),
    }
    p = presets.get(ftype, {})
    p.pop("D_", None)
    base.update(p)
    if ftype == "wardrobe":
        base["sections"] = [new_section(doors=2, shelves=1, rail=1), new_section(doors=1, shelves=5)]
    if ftype == "tv":
        base["sections"] = [new_section(doors=1, shelves=1), new_section(doors=0, shelves=0, drawers=2, drawer_h=0), new_section(doors=1, shelves=1)]
    return base


def new_section(width=0, doors=1, shelves=2, drawers=0, drawer_h=180, rail=0, door_h=0, open_shelves=0, shelf_fixed=False, drawer_top=False):
    return {"width": width, "doors": doors, "shelves": shelves, "drawers": drawers, "drawer_h": drawer_h,
            "rail": rail, "door_h": door_h, "open_shelves": open_shelves, "shelf_fixed": shelf_fixed,
            "drawer_top": drawer_top}


def hinges_per_door(h, w):
    n = 2 if h <= 900 else 3 if h <= 1600 else 4 if h <= 2000 else 5
    if w > 600 and n < 5:
        n += 1
    return n


def _joint_screws(depth):
    return 2 + int(depth // 300)


def build(item, catalog):
    M = {m["key"]: m for m in catalog["materials"]}
    mod = item.get("name", "Модул")
    W, H, D = float(item["W"]), float(item["H"]), float(item["D"])
    cm = M[item["carcass_mat"]]
    t = float(cm["t"])
    fm = M[item["front_mat"]]
    bm = M.get(item.get("back_mat"))
    dm = M.get(item.get("drawer_mat"), cm)
    dbm = M.get(item.get("drawer_bottom_mat"), bm or cm)
    cband = item.get("carcass_band", "0.8")
    fband = item.get("front_band", "2.0")
    if fm["kind"] == "МДФ" and fband != "none":
        fband_eff = "none"
    else:
        fband_eff = fband
    dband = item.get("drawer_band", "0.4")
    gap = float(item.get("gap", 3))
    base, bh = item.get("base", "legs"), float(item.get("base_h", 0))
    if base in ("wall", "none"):
        bh = 0.0
    top = item.get("top", "between")
    back = item.get("back", "nailed")
    back_t = float(bm["t"]) if (bm and back != "none") else 0.0
    hinge = find(catalog["hinges"], item.get("hinge", "std110"))
    slide = find(catalog["slides"], item.get("slide", "ball"))
    handle = item.get("handle", "handle")

    parts, hw, warn, shapes, info = [], [], [], [], []

    def P(name, l, w, qty, mat, L1="none", L2="none", W1="none", W2="none", note=""):
        if qty <= 0 or l <= 0 or w <= 0:
            return
        parts.append(Part(mod, name, round(l, 1), round(w, 1), int(qty), mat,
                          {"L1": L1, "L2": L2, "W1": W1, "W2": W2}, note))

    def HW(name, qty, unit="бр.", price_key=None, price=None):
        if qty <= 0:
            return
        if price is None:
            price = catalog.get("hardware_prices", {}).get(price_key or name, 0.0)
        for h in hw:
            if h.name == name:
                h.qty += qty
                return
        hw.append(Hw(name, qty, unit, price_key or name, price))

    # --- дълбочина на корпусните детайли
    dp = D - back_t if back == "nailed" else D
    inner_depth = dp - (12 + back_t if back == "groove" else 0)   # светла дълбочина пред гърба
    shelf_d = inner_depth - 20

    # --- вертикални нива
    y_bottom = bh                     # долна страна на дъното
    carc_h = H - bh                   # височина на корпуса
    if base == "plinth":
        side_len = H
    else:
        side_len = carc_h
    if top == "over":
        side_len -= t
    ih = carc_h - 2 * t               # светла височина
    iw = W - 2 * t
    y_in0 = y_bottom + t              # горна страна на дъното
    y_in1 = y_in0 + ih                # долна страна на тавана

    if ih <= 0 or iw <= 0:
        return BuildResult([], [], ["Размерите са твърде малки за избраната дебелина."], [], [])

    # --- корпус
    P("Страница", side_len, dp, 2, cm["key"], L1=cband, note="фладер вертикално")
    if top == "over":
        P("Таван (върху страниците)", W, dp, 1, cm["key"], L1=cband, W1=cband, W2=cband)
    elif top == "rails":
        P("Траверса предна", iw, 100, 1, cm["key"], L1=cband)
        P("Траверса задна", iw, 100, 1, cm["key"])
    else:
        P("Таван", iw, dp, 1, cm["key"], L1=cband)
    P("Дъно", iw, dp, 1, cm["key"], L1=cband)
    joints = 2 * (2 * _joint_screws(dp)) if top != "rails" else 2 * _joint_screws(dp) + 8

    shapes.append(("side", 0, 0 if base == "plinth" else y_bottom, t, side_len, ""))
    shapes.append(("side", W - t, 0 if base == "plinth" else y_bottom, t, side_len, ""))
    shapes.append(("panel", t if top != "over" else 0, H - t, iw if top != "over" else W, t, ""))
    shapes.append(("panel", t, y_bottom, iw, t, ""))

    if base == "plinth":
        P("Цокъл преден", iw, bh, 1, cm["key"], L1="none", note="отстъпен 30-50 мм назад")
        shapes.append(("plinth", t, 0, iw, bh, ""))
        joints += 4
    elif base == "legs":
        nlegs = 2 * (1 + math.ceil(W / 800))
        HW("Краче регулируемо 100-150 мм", nlegs)
        shapes.append(("legs", 0, 0, W, bh, ""))
    elif base == "wall":
        HW("Окачвач за горен шкаф", 2)

    # --- гръб
    if back != "none" and bm:
        if back == "nailed":
            bl, bw = carc_h - 4, W - 4
            HW("Гвоздеи/скоби за гръб", math.ceil(2 * (bl + bw) / 120))
        else:
            bl, bw = ih + 2 * 8 - 2, iw + 2 * 8 - 2
            info.append("Гръб в канал: канал 8 мм дълбок, на 12 мм от задния ръб.")
        sl, sw = bm["sheet_l"], bm["sheet_w"]
        fits = (bl <= sl and bw <= sw) or (bl <= sw and bw <= sl)
        if fits:
            P("Гръб", bl, bw, 1, bm["key"])
        else:
            n = math.ceil(bw / (min(sl, sw) - 20))
            P("Гръб (разделен)", bl, (bw + (n - 1) * 20) / n, n, bm["key"], note="съединява се върху преграда/летва")
            warn.append(f"Гърбът е по-голям от плочата – разделен на {n} части, които се снаждат върху вертикална преграда.")

    # --- секции
    secs = item.get("sections") or [new_section()]
    n = len(secs)
    avail = iw - (n - 1) * t
    fixed = sum(float(s.get("width") or 0) for s in secs)
    # автоматичните секции делят остатъка пропорционално на броя врати
    wts = [max(1, int(s.get("doors") or 0)) for s in secs]
    nauto = sum(wt for s, wt in zip(secs, wts) if not s.get("width"))
    autow = (avail - fixed) / nauto if nauto else 0
    if nauto == 0 and abs(fixed - avail) > 0.5:
        warn.append(f"Сборът от широчините на секциите ({fixed:.0f}) не съвпада със светлата широчина ({avail:.0f}). Последната секция е коригирана.")
    widths = [float(s.get("width") or autow * wt) for s, wt in zip(secs, wts)]
    if nauto and fixed == 0 and n > 1:
        # всички секции авто: фронтовете (вратите) да станат еднакво широки
        tw = sum(wts)
        widths = [W * wt / tw - t * (1.5 if k in (0, n - 1) else 1.0) for k, wt in enumerate(wts)]
    if nauto == 0:
        widths[-1] += avail - sum(widths)
    if any(w < 100 for w in widths):
        warn.append("Секция е по-тясна от 100 мм – проверете широчините.")

    # вертикални прегради
    if n > 1:
        P("Вертикална преграда", ih, dp - (0 if back != "groove" else 0), n - 1, cm["key"], L1=cband)
        joints += (n - 1) * 2 * _joint_screws(dp)

    span_limit = SHELF_SPAN_LIMIT.get(int(t), 800)
    if cm["kind"] == "МДФ":
        span_limit -= 50

    x = t
    front_bottom = y_bottom if base != "plinth" else bh
    if base == "wall":
        front_bottom = 0
    front_top = H
    FH = front_top - front_bottom - gap
    door_count = drawer_count = 0
    loose_shelves = 0

    for i, (s, sw) in enumerate(zip(secs, widths)):
        x0, x1 = x, x + sw
        # габарит на фронта по хоризонтала (до средата на преградите)
        fx0 = 0 if i == 0 else x0 - t / 2
        fx1 = W if i == n - 1 else x1 + t / 2
        span = fx1 - fx0
        if i < n - 1:
            shapes.append(("divider", x1, y_in0, t, ih, ""))

        sh_start = len(shapes)
        nd = int(s.get("drawers") or 0)
        ndoors = int(s.get("doors") or 0)
        dh = float(s.get("drawer_h") or 0)
        cur_front_y = front_bottom + gap / 2
        cur_in_y = y_in0

        # чекмеджета
        if nd > 0:
            fill_all = dh <= 0
            if fill_all:
                fh = (FH - (nd - 1) * gap) / nd
            else:
                fh = dh
            box_h = max(slide["min_box_h"], min(250, math.floor((fh - 40) / 10) * 10))
            lens = [L for L in slide["lengths"] if L <= inner_depth - 10]
            if not lens:
                warn.append(f"{mod}: дълбочината ({inner_depth:.0f}) е малка за водачите – най-къс водач {min(slide['lengths'])} мм.")
                L = min(slide["lengths"])
            else:
                L = max(lens)
            outer = sw - slide["clear"]
            dt = float(dm["t"])
            fw = span - gap
            P("Фронт чекмедже", fh, fw, nd, fm["key"], fband_eff, fband_eff, fband_eff, fband_eff)
            P("Чекмедже – страница", L, box_h, 2 * nd, dm["key"], L1=dband)
            P("Чекмедже – чело/гръб", outer - 2 * dt, box_h, 2 * nd, dm["key"], L1=dband)
            P("Чекмедже – дъно", L - 2, outer - 2, nd, dbm["key"])
            HW(f"Водачи: {slide['name']} L={L} мм", nd, "чифт", price=slide["price"])
            HW("Конфирмат 7x50", 8 * nd)
            HW("Гвоздеи/скоби за гръб", 20 * nd)
            if handle == "handle":
                HW("Дръжка", nd)
            elif handle == "push" and "hidden" not in slide["key"]:
                HW("Push-to-open тласкач", nd)
            drawer_count += nd
            info.append(f"Секция {i+1}: чекмеджета {nd} бр., кутия {outer:.0f}×{L}×{box_h} мм (Ш×Д×В), фронт {fw:.0f}×{fh:.0f}.")
            for k in range(nd):
                shapes.append(("drawer", fx0 + gap / 2, cur_front_y, fw, fh, f"Ч{k+1}"))
                cur_front_y += fh + gap
            used_h = nd * (fh + gap)
            if fill_all:
                cur_in_y = y_in1
            else:
                # фиксирана хоризонтала над чекмеджетата
                cur_in_y = front_bottom + used_h
                if cur_in_y < y_in1 - 50:
                    P("Хоризонтала над чекмеджета", sw, dp, 1, cm["key"], L1=cband)
                    joints += 2 * _joint_screws(dp)
                    shapes.append(("panel", x0, cur_in_y, sw, t, ""))
                    cur_in_y += t
        # зона врати
        zone_h = y_in1 - cur_in_y
        door_h_param = float(s.get("door_h") or 0)
        if zone_h > 50:
            if ndoors > 0:
                if door_h_param > 0 and door_h_param < (front_top - cur_front_y - gap):
                    dz_front = door_h_param
                    dz_top_in = cur_front_y + door_h_param   # приблизително ниво на хоризонталата
                else:
                    dz_front = front_top - cur_front_y - gap / 2
                    dz_top_in = y_in1
                door_w = (span - ndoors * gap) / ndoors
                door_hgt = dz_front
                if hinge["kind"] == "lift":
                    P("Клапа (подемна врата)", span - gap, door_hgt, 1, fm["key"], fband_eff, fband_eff, fband_eff, fband_eff, note="фладер хоризонтално")
                    HW(f"Подемен механизъм: {hinge['name']}", 1, "к-т", price=hinge["price"])
                    shapes.append(("lift", fx0 + gap / 2, cur_front_y, span - gap, door_hgt, "клапа"))
                    door_count += 1
                    if handle == "handle":
                        HW("Дръжка", 1)
                else:
                    P("Врата", door_hgt, door_w, ndoors, fm["key"], fband_eff, fband_eff, fband_eff, fband_eff)
                    nh = hinges_per_door(door_hgt, door_w)
                    HW(f"Панта: {hinge['name']}", nh * ndoors, price=hinge["price"])
                    if hinge["key"] == "push110":
                        HW("Push-to-open тласкач", ndoors)
                    elif handle == "handle":
                        HW("Дръжка", ndoors)
                    elif handle == "push":
                        HW("Push-to-open тласкач", ndoors)
                    door_count += ndoors
                    if door_w > 600:
                        warn.append(f"{mod}, секция {i+1}: врата {door_w:.0f} мм е по-широка от препоръчителните 600 мм – помислете за 2 врати.")
                    if door_hgt > 2400:
                        warn.append(f"{mod}: врата {door_hgt:.0f} мм – висока врата може да се изкриви; използвайте токоизправител или МДФ 22.")
                    for k in range(ndoors):
                        side_hinge = "L" if (ndoors == 1 and i == 0) or (ndoors == 2 and k == 0) else "R"
                        if ndoors == 1 and i > 0:
                            side_hinge = "R" if i == n - 1 else "L"
                        shapes.append(("door", fx0 + gap / 2 + k * (door_w + gap), cur_front_y, door_w, door_hgt, side_hinge))
                if dz_top_in < y_in1 - 50:
                    P("Хоризонтала над вратите", sw, dp, 1, cm["key"], L1=cband)
                    joints += 2 * _joint_screws(dp)
                    shapes.append(("panel", x0, dz_top_in, sw, t, ""))
                    # отворена зона над вратите
                    _place_shelves(P, shapes, s.get("open_shelves", 0), x0, sw, dz_top_in + t, y_in1, shelf_d, cm, cband, False)
                    loose_shelves += int(s.get("open_shelves", 0))
                    top_zone = dz_top_in
                else:
                    top_zone = y_in1
            else:
                top_zone = y_in1
            # рафтове + закачалка в зоната
            rails = int(s.get("rail") or 0)
            nsh = int(s.get("shelves") or 0)
            if rails > 0:
                ys = []
                y = top_zone
                for k in range(nsh):
                    y -= 330
                    if y > cur_in_y + 400:
                        ys.append(y)
                for y in ys:
                    P("Рафт", sw - (0 if s.get("shelf_fixed") else 1), shelf_d, 1, cm["key"], L1=cband)
                    shapes.append(("shelf", x0, y, sw, t, ""))
                rail_y = (min(ys) if ys else top_zone) - 60
                shapes.append(("rail", x0 + 10, rail_y, sw - 20, 0, ""))
                HW("Тръба за закачалка (м)", round((sw - 2) / 1000, 2), "м")
                HW("Държач за тръба", 2)
                if rails > 1:
                    r2 = cur_in_y + (rail_y - cur_in_y) / 2
                    shapes.append(("rail", x0 + 10, r2, sw - 20, 0, ""))
                    HW("Тръба за закачалка (м)", round((sw - 2) / 1000, 2), "м")
                    HW("Държач за тръба", 2)
                free = rail_y - cur_in_y
                if free < 900 and rails == 1:
                    warn.append(f"{mod}, секция {i+1}: под закачалката има само {free:.0f} мм (за ризи ≥ 950, за рокли/палта ≥ 1500).")
                if sw > 1000:
                    warn.append(f"{mod}, секция {i+1}: тръба > 1000 мм – добавете среден държач.")
                loose_shelves += 0 if s.get("shelf_fixed") else len(ys)
                if s.get("shelf_fixed"):
                    joints += len(ys) * 2 * _joint_screws(dp)
            else:
                _place_shelves(P, shapes, nsh, x0, sw, cur_in_y, top_zone, shelf_d, cm, cband, s.get("shelf_fixed"))
                if s.get("shelf_fixed"):
                    joints += nsh * 2 * _joint_screws(dp)
                else:
                    loose_shelves += nsh
            if nsh > 0 and sw > span_limit and not rails:
                warn.append(f"{mod}, секция {i+1}: рафт {sw:.0f} мм ще провисне (макс. ~{span_limit} мм за {cm['name']}). Добавете преграда или ползвайте 25 мм.")
        if s.get("drawer_top") and nd > 0:
            # огледално: чекмеджетата горе, вратите долу (детайлите са същите)
            for k in range(sh_start, len(shapes)):
                kind, sx, sy, sw_, sh_, lab = shapes[k]
                if kind in ("drawer", "door", "lift"):
                    sy = front_bottom + front_top - sy - sh_
                elif kind in ("panel", "shelf", "rail"):
                    sy = y_in0 + y_in1 - sy - sh_
                shapes[k] = (kind, sx, sy, sw_, sh_, lab)
        x = x1 + t

    HW("Конфирмат 7x50", joints)
    HW("Рафтоносач", loose_shelves * 4)
    for h in hw:
        if isinstance(h.qty, float):
            h.qty = round(h.qty, 2)

    if fm["kind"] == "МДФ" and fband != "none":
        info.append("Фронтовете са от МДФ – кант не се слага, ръбовете се фрезоват и боядисват/фолират.")
    info.append(f"Светли размери: {iw:.0f} × {ih:.0f} мм, дълбочина рафт {shelf_d:.0f} мм.")
    if door_count:
        info.append(f"Врати: {door_count} бр. Чашка Ø35 мм на 22.5 мм от ръба на вратата (ос), първата панта на ~100 мм от края.")
    for p in parts:
        mat = M[p.material]
        dims = sorted([p.length, p.width], reverse=True)
        sdims = sorted([mat["sheet_l"], mat["sheet_w"]], reverse=True)
        if dims[0] > sdims[0] - 20 or dims[1] > sdims[1] - 20:
            warn.append(f"{p.name} {p.length:.0f}×{p.width:.0f} не се побира в плоча {mat['sheet_l']}×{mat['sheet_w']} ({mat['name']}).")
    warn = list(dict.fromkeys(warn))
    return BuildResult(parts, hw, warn, shapes, info)


def _place_shelves(P, shapes, nsh, x0, sw, y_lo, y_hi, shelf_d, cm, cband, fixed):
    nsh = int(nsh or 0)
    if nsh <= 0:
        return
    t = cm["t"]
    step = (y_hi - y_lo - nsh * t) / (nsh + 1)
    P("Рафт" + (" (фиксиран)" if fixed else ""), sw - (0 if fixed else 1), shelf_d, nsh, cm["key"], L1=cband)
    for k in range(nsh):
        y = y_lo + step * (k + 1) + t * k
        shapes.append(("shelf", x0, y, sw, t, ""))


def aggregate_parts(parts):
    """Обединява еднакви детайли (материал, размер, кантове)."""
    out = {}
    for p in parts:
        key = (p.material, p.length, p.width, tuple(sorted(p.edges.items())), p.name, p.module)
        if key in out:
            out[key].qty += p.qty
        else:
            out[key] = Part(p.module, p.name, p.length, p.width, p.qty, p.material, dict(p.edges), p.note)
    return list(out.values())
