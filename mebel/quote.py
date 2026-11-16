"""Оферта за клиент: цена по мебел + PDF с 3D картина и описание.

Цената на всяка мебел = (материали + кант + обков + услуги по рязане и
кантиране) × (1 + надценка %) + труд на модул. Плочите се разпределят между
мебелите пропорционално на площта на детайлите им.
"""
import datetime

from .catalog import find, HANDLES
from .project import compute

DEFAULT_QUOTE = {
    "company": "", "company_phone": "", "company_email": "", "company_address": "",
    "customer": "", "customer_phone": "", "customer_address": "",
    "number": 1, "validity_days": 14, "lead_days": 21,
    "markup_pct": 20.0, "labor_per_item": 40.0,
    "transport": 0.0, "montage": 0.0, "discount_pct": 0.0,
    "vat": True, "vat_pct": 20.0, "advance_pct": 50.0,
    "notes": "Цената включва материали, обков, изработка. Цветът и декорът се потвърждават по мостра.",
}


def quote_settings(project):
    q = dict(DEFAULT_QUOTE)
    q.update(project.get("quote", {}))
    return q


def item_costs(comp, project):
    """Себестойност по мебел: [{name, materials, hardware, services, total}] в реда на проекта."""
    cat = project["catalog"]
    st = project["settings"]
    M = {m["key"]: m for m in cat["materials"]}
    # площ по материал за всяка мебел и общо
    area_tot = {}
    per = []
    for it, r in comp.builds:
        a = {}
        for p in r.parts:
            a[p.material] = a.get(p.material, 0) + p.length * p.width * p.qty
        for k, v in a.items():
            area_tot[k] = area_tot.get(k, 0) + v
        per.append((it, r, a))
    reserve = 1 + st.get("band_reserve", 10) / 100
    out = []
    for it, r, a in per:
        mat = 0.0
        serv = 0.0
        for k, v in a.items():
            share = v / area_tot[k] if area_tot.get(k) else 0
            cr = comp.cuts.get(k)
            sheets = cr.n_sheets if cr else 0
            mat += sheets * M[k]["price"] * share
            if cr:
                serv += cr.cut_length_m() * st["cut_price_m"] * share
        for p in r.parts:
            for bk, m in p.band_meters().items():
                mat += m * p.qty * reserve * find(cat["bands"], bk)["price"]
                serv += m * p.qty * st["band_service_m"]
        hw = sum(h.qty * h.price for h in r.hardware)
        out.append({"name": it["name"], "materials": mat, "hardware": hw, "services": serv, "total": mat + hw + serv})
    return out


def item_price(cost, q):
    return round(cost["total"] * (1 + q["markup_pct"] / 100) + q["labor_per_item"], 2)


def describe(it, r, cat):
    """Кратко описание на мебелта за клиента (списък редове)."""
    M = {m["key"]: m for m in cat["materials"]}
    kinds = [s[0] for s in r.shapes]
    doors = kinds.count("door") + kinds.count("lift")
    drawers = kinds.count("drawer")
    shelves = kinds.count("shelf")
    rails = kinds.count("rail")
    lines = [f"Размери: {it['W']:g} × {it['H']:g} × {it['D']:g} мм (Ш × В × Д)",
             f"Корпус: {M[it['carcass_mat']]['name']}",
             f"Фронтове: {M[it['front_mat']]['name']}"]
    eq = []
    if doors:
        eq.append(f"{doors} врат{'а' if doors == 1 else 'и'}")
    if drawers:
        eq.append(f"{drawers} чекмедже{'' if drawers == 1 else 'та'}")
    if shelves:
        eq.append(f"{shelves} рафт{'' if shelves == 1 else 'а'}")
    if rails:
        eq.append(f"{rails} закачалк{'а' if rails == 1 else 'и'}")
    if eq:
        lines.append("Оборудване: " + ", ".join(eq))
    hw = []
    if doors:
        hw.append(find(cat["hinges"], it.get("hinge", "std110"))["name"].split("(")[0].strip())
    if drawers:
        hw.append(find(cat["slides"], it.get("slide", "ball"))["name"].split("(")[0].strip())
    hw.append(HANDLES.get(it.get("handle"), ""))
    lines.append("Обков: " + "; ".join(h for h in hw if h))
    return lines


def export_quote_pdf(project, path, comp=None):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas as rcanvas
    from .export import _font, _wrap
    from .view3d import boxes_from, render_polys

    F, FB = _font()
    q = quote_settings(project)
    cat = project["catalog"]
    comp = comp or compute(project)
    costs = item_costs(comp, project)
    PW, PH = A4
    mg = 40
    c = rcanvas.Canvas(path, pagesize=A4)
    c.setTitle(f"Оферта №{q['number']}")
    today = datetime.date.today()

    def page_header():
        c.setFillColor(colors.HexColor("#2f2a24"))
        c.rect(0, PH - 70, PW, 70, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont(FB, 16)
        c.drawString(mg, PH - 38, q["company"] or "Мебели по поръчка")
        c.setFont(F, 8.5)
        contact = "   ".join(x for x in (q["company_phone"], q["company_email"], q["company_address"]) if x)
        c.drawString(mg, PH - 55, contact)
        c.setFont(FB, 13)
        c.drawRightString(PW - mg, PH - 38, f"ОФЕРТА № {q['number']}")
        c.setFont(F, 8.5)
        c.drawRightString(PW - mg, PH - 55, f"Дата: {today:%d.%m.%Y}   Валидна до: {(today + datetime.timedelta(days=int(q['validity_days']))):%d.%m.%Y}")
        c.setFillColor(colors.black)

    page_header()
    y = PH - 95
    c.setFont(FB, 10)
    c.drawString(mg, y, "Клиент:")
    c.setFont(F, 10)
    c.drawString(mg + 50, y, q["customer"] or "—")
    extra = "   ".join(x for x in (q["customer_phone"], q["customer_address"]) if x)
    if extra:
        c.setFont(F, 8.5)
        c.drawString(mg + 50, y - 12, extra)
    y -= 34

    img = 165
    subtotal = 0.0
    for (it, r), cost in zip(comp.builds, costs):
        block = img + 20
        if y - block < 60:
            c.showPage()
            page_header()
            y = PH - 95
        price = item_price(cost, q)
        subtotal += price
        c.setStrokeColor(colors.HexColor("#d8d2c8"))
        c.setFillColor(colors.HexColor("#faf8f4"))
        c.roundRect(mg, y - block, PW - 2 * mg, block, 6, stroke=1, fill=1)
        # 3D картина (векторна)
        boxes = boxes_from(it, r, cat)
        size = (float(it["W"]), float(it["H"]), float(it["D"]))
        x0, y0 = mg + 8, y - block + 10
        c.setLineWidth(0.3)
        c.setStrokeColor(colors.HexColor("#6d6252"))
        for pts, col in render_polys(boxes, size, 30, 15, img, img, zoom=1.05):
            pth = c.beginPath()
            pth.moveTo(x0 + pts[0], y0 + img - pts[1])
            for i in range(2, len(pts), 2):
                pth.lineTo(x0 + pts[i], y0 + img - pts[i + 1])
            pth.close()
            c.setFillColor(colors.HexColor(col))
            c.drawPath(pth, stroke=1, fill=1)
        # текст
        tx = mg + img + 24
        c.setFillColor(colors.black)
        c.setFont(FB, 12)
        c.drawString(tx, y - 22, it["name"])
        c.setFont(F, 9)
        ty = y - 40
        for ln in _wrap(describe(it, r, cat), 62):
            c.drawString(tx, ty, ln)
            ty -= 12.5
        c.setFont(FB, 13)
        c.drawRightString(PW - mg - 12, y - block + 14, f"{price:,.2f} €".replace(",", " "))
        y -= block + 10

    # --- суми
    if y < 230:
        c.showPage()
        page_header()
        y = PH - 95
    disc = round(subtotal * q["discount_pct"] / 100, 2)
    rows = [("Мебели", subtotal)]
    if disc:
        rows.append((f"Отстъпка {q['discount_pct']:g}%", -disc))
    if q["transport"]:
        rows.append(("Транспорт", q["transport"]))
    if q["montage"]:
        rows.append(("Монтаж", q["montage"]))
    net = round(sum(v for _, v in rows), 2)
    if q["vat"]:
        vat = round(net * q["vat_pct"] / 100, 2)
        rows += [("Сума без ДДС", None), (f"ДДС {q['vat_pct']:g}%", vat)]
        total = net + vat
    else:
        total = net
    c.setFont(F, 10)
    xl, xr = PW - mg - 260, PW - mg
    for lbl, v in rows:
        c.drawString(xl, y, lbl)
        c.drawRightString(xr, y, f"{(net if v is None else v):,.2f} €".replace(",", " "))
        y -= 15
    c.setStrokeColor(colors.black)
    c.line(xl, y + 8, xr, y + 8)
    c.setFont(FB, 13)
    c.drawString(xl, y - 8, "ОБЩО" + (" с ДДС" if q["vat"] else ""))
    c.drawRightString(xr, y - 8, f"{total:,.2f} €".replace(",", " "))
    y -= 26
    if q["advance_pct"]:
        c.setFont(F, 9.5)
        adv = round(total * q["advance_pct"] / 100, 2)
        c.drawString(xl, y, f"Аванс {q['advance_pct']:g}% при поръчка: {adv:,.2f} €".replace(",", " "))
        y -= 22
    c.setFont(FB, 10)
    c.drawString(mg, y, "Условия")
    c.setFont(F, 9)
    y -= 14
    terms = [f"Срок за изработка: {int(q['lead_days'])} работни дни след потвърждение и аванс.",
             f"Офертата е валидна {int(q['validity_days'])} дни."] + [ln for ln in q["notes"].splitlines() if ln.strip()]
    for ln in _wrap(terms, 110):
        c.drawString(mg, y, ln)
        y -= 12
    y -= 30
    if y > 50:
        c.setFont(F, 9)
        c.drawString(mg, y, "Изготвил: ............................")
        c.drawString(PW / 2 + 20, y, "Приел (клиент): ............................")
    c.save()
    return total
