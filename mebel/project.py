"""Проект: списък мебели + каталог + настройки; изчисления и запис/зареждане."""
import json
from dataclasses import dataclass

from .catalog import default_catalog, find
from .furniture import build, aggregate_parts, default_item
from .optimizer import optimize_project

DEFAULT_SETTINGS = {
    "kerf": 4.0, "trim": 10.0, "reduce_band": True, "iterations": 300,
    "cut_price_m": 0.60, "band_service_m": 0.50, "band_reserve": 10,
}


def new_project():
    return {"version": 1, "name": "Нов проект", "catalog": default_catalog(),
            "settings": dict(DEFAULT_SETTINGS), "items": [default_item("wardrobe")]}


def save(project, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False, indent=2)


def load(path):
    with open(path, encoding="utf-8") as f:
        pr = json.load(f)
    base = new_project()
    for k in ("catalog", "settings"):
        merged = dict(base[k])
        merged.update(pr.get(k, {}))
        pr[k] = merged
    pr.setdefault("items", [])
    return pr


@dataclass
class Computation:
    builds: list           # [(item, BuildResult)]
    parts: list            # агрегирани детайли (номер = индекс + 1)
    hardware: list         # агрегиран обков
    cuts: dict             # material_key -> CutResult
    bands: dict            # band_key -> метри
    costs: dict
    warnings: list


def compute(project, optimize=True):
    cat = project["catalog"]
    st = project["settings"]
    builds = []
    allparts, warnings = [], []
    hw = {}
    for it in project["items"]:
        r = build(it, cat)
        builds.append((it, r))
        allparts += r.parts
        warnings += r.warnings
        for h in r.hardware:
            if h.name in hw:
                hw[h.name].qty = round(hw[h.name].qty + h.qty, 2)
            else:
                from copy import copy
                hw[h.name] = copy(h)
    parts = aggregate_parts(allparts)
    parts.sort(key=lambda p: (p.material, p.module, -p.length * p.width))
    bands = {}
    for p in parts:
        for k, m in p.band_meters().items():
            bands[k] = bands.get(k, 0) + m * p.qty
    cuts = optimize_project(parts, cat, st["kerf"], st["trim"], st["reduce_band"], int(st.get("iterations", 300))) if optimize else {}

    M = {m["key"]: m for m in cat["materials"]}
    costs = {"Плочи": 0.0, "Кантове": 0.0, "Обков": 0.0, "Рязане (услуга)": 0.0, "Кантиране (услуга)": 0.0}
    lines = []
    for mk, cr in cuts.items():
        c = cr.n_sheets * M[mk]["price"]
        costs["Плочи"] += c
        lines.append((M[mk]["name"], f"{cr.n_sheets} плочи", c))
        costs["Рязане (услуга)"] += cr.cut_length_m() * st["cut_price_m"]
    reserve = 1 + st.get("band_reserve", 10) / 100
    for bk, m in bands.items():
        b = find(cat["bands"], bk)
        c = m * reserve * b["price"]
        costs["Кантове"] += c
        costs["Кантиране (услуга)"] += m * st["band_service_m"]
        lines.append((b["name"], f"{m * reserve:.1f} м", c))
    for h in hw.values():
        costs["Обков"] += h.qty * h.price
    costs = {k: round(v, 2) for k, v in costs.items()}
    costs["ОБЩО"] = round(sum(costs.values()), 2)
    costs["_lines"] = lines
    return Computation(builds, parts, list(hw.values()), cuts, bands, costs, warnings)
