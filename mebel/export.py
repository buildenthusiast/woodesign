"""Експорт: CSV (за цех/услуга по разкрой) и PDF (пълна документация)."""
import csv
import os

from .catalog import find

EDGE_TXT = {"none": "", "0.4": "0.4", "0.8": "0.8", "1.0": "1", "2.0": "2"}


def edges_str(p):
    e = p.edges
    s = []
    for k, lbl in (("L1", "Д1"), ("L2", "Д2"), ("W1", "Ш1"), ("W2", "Ш2")):
        if e.get(k, "none") != "none":
            s.append(f"{lbl}:{EDGE_TXT.get(e[k], e[k])}")
    return " ".join(s)


def export_parts_csv(comp, project, path):
    cat = project["catalog"]
    M = {m["key"]: m for m in cat["materials"]}
    red = project["settings"]["reduce_band"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["№", "Модул", "Детайл", "Материал", "Дебелина", "Дължина (фладер)", "Ширина", "Брой",
                    "Фладер", "Кант Д1", "Кант Д2", "Кант Ш1", "Кант Ш2", "Рязане Д", "Рязане Ш", "Бележка"])
        for i, p in enumerate(comp.parts, 1):
            m = M[p.material]
            cl, cw = p.cut_size(cat["bands"], red)
            w.writerow([i, p.module, p.name, m["name"], m["t"], f"{p.length:g}", f"{p.width:g}", p.qty,
                        "да" if m["grain"] else "не",
                        *[EDGE_TXT.get(p.edges[k], "") for k in ("L1", "L2", "W1", "W2")],
                        f"{cl:g}", f"{cw:g}", p.note])


def export_hardware_csv(comp, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Обков", "Количество", "Мярка", "Ед. цена", "Сума"])
        for h in comp.hardware:
            w.writerow([h.name, f"{h.qty:g}", h.unit, f"{h.price:.2f}", f"{h.qty * h.price:.2f}"])


# ---------------------------------------------------------------- PDF
def _font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    cands = [
        (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ]
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    cands.insert(0, (os.path.join(base, "DejaVuSans.ttf"), os.path.join(base, "DejaVuSans-Bold.ttf")))
    for r, b in cands:
        if os.path.exists(r):
            pdfmetrics.registerFont(TTFont("UF", r))
            pdfmetrics.registerFont(TTFont("UFB", b if os.path.exists(b) else r))
            return "UF", "UFB"
    return "Helvetica", "Helvetica-Bold"


COLORS = {"door": "#d9b38c", "drawer": "#c9a27a", "lift": "#d9b38c", "side": "#eeeeee", "panel": "#eeeeee",
          "divider": "#eeeeee", "shelf": "#bbbbbb", "plinth": "#888888"}


def draw_front(c, shapes, W, H, x0, y0, maxw, maxh, fronts=True):
    """Рисува изглед отпред в reportlab canvas c."""
    from reportlab.lib import colors
    s = min(maxw / W, maxh / H)
    def R(x, y, w, h, fill, stroke=colors.black, lw=0.5, dash=None):
        c.setLineWidth(lw)
        c.setStrokeColor(stroke)
        c.setFillColor(colors.HexColor(fill) if fill else colors.white)
        if dash:
            c.setDash(*dash)
        c.rect(x0 + x * s, y0 + y * s, max(w * s, 0.1), max(h * s, 0.1), stroke=1, fill=1 if fill else 0)
        c.setDash()
    R(0, 0, W, H, None, lw=0.3)
    for k, x, y, w, h, lab in shapes:
        if k in ("side", "panel", "divider", "plinth"):
            R(x, y, w, h, COLORS[k])
        elif k == "shelf":
            R(x, y, w, h, COLORS[k], lw=0.3)
        elif k == "rail":
            c.setStrokeColor(colors.HexColor("#555555")); c.setLineWidth(1.5)
            c.line(x0 + x * s, y0 + y * s, x0 + (x + w) * s, y0 + y * s)
        elif k == "legs":
            c.setFillColor(colors.HexColor("#666666"))
            for lx in (30, W - 60):
                c.rect(x0 + lx * s, y0, 30 * s, h * s, stroke=0, fill=1)
    if fronts:
        for k, x, y, w, h, lab in shapes:
            if k in ("door", "drawer", "lift"):
                R(x, y, w, h, COLORS[k], lw=0.6)
                c.setStrokeColor(colors.HexColor("#555555")); c.setLineWidth(0.3)
                if k == "door":
                    # линии на отваряне (върхът сочи към страната на пантите)
                    hx = x if lab == "L" else x + w
                    ox = x + w if lab == "L" else x
                    c.setDash(2, 2)
                    c.line(x0 + ox * s, y0 + y * s, x0 + hx * s, y0 + (y + h / 2) * s)
                    c.line(x0 + ox * s, y0 + (y + h) * s, x0 + hx * s, y0 + (y + h / 2) * s)
                    c.setDash()
                elif k == "drawer":
                    c.line(x0 + (x + w / 2 - 40) * s, y0 + (y + h - 30) * s, x0 + (x + w / 2 + 40) * s, y0 + (y + h - 30) * s)


def export_pdf(comp, project, path):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas as rcanvas
    F, FB = _font()
    cat = project["catalog"]
    M = {m["key"]: m for m in cat["materials"]}
    st = project["settings"]
    PW, PH = landscape(A4)
    c = rcanvas.Canvas(path, pagesize=landscape(A4))
    c.setTitle(project.get("name", "Проект"))
    margin = 30

    def header(title):
        c.setFont(FB, 14)
        c.setFillColor(colors.black)
        c.drawString(margin, PH - margin, title)
        c.setFont(F, 8)
        c.drawRightString(PW - margin, PH - margin, project.get("name", ""))
        return PH - margin - 22

    # --- обобщение
    y = header("Обобщение и ориентировъчна цена")
    c.setFont(F, 10)
    for it, r in comp.builds:
        c.drawString(margin, y, f"• {it['name']}: {it['W']:g} × {it['H']:g} × {it['D']:g} мм (Ш×В×Д)")
        y -= 14
    y -= 8
    c.setFont(FB, 11); c.drawString(margin, y, "Материали"); y -= 14; c.setFont(F, 10)
    for name, q, cost in comp.costs["_lines"]:
        c.drawString(margin, y, f"{name}: {q}"); c.drawRightString(margin + 420, y, f"{cost:.2f} €"); y -= 13
    y -= 6
    for k, v in comp.costs.items():
        if k.startswith("_"):
            continue
        c.setFont(FB if k == "ОБЩО" else F, 10)
        c.drawString(margin, y, k); c.drawRightString(margin + 420, y, f"{v:.2f} €"); y -= 13
    c.setFont(F, 8)
    c.drawString(margin, y - 6, "Цените са ориентировъчни – редактирайте ги в раздел „Материали и цени“.")
    y -= 26
    if comp.warnings:
        c.setFont(FB, 11); c.drawString(margin, y, "Предупреждения"); y -= 14; c.setFont(F, 8.5)
        for w in comp.warnings:
            if y < 40:
                c.showPage(); y = header("Предупреждения (продълж.)"); c.setFont(F, 8.5)
            c.drawString(margin, y, "! " + w[:170]); y -= 11
    c.showPage()

    # --- всяка мебел: чертеж + инфо
    for it, r in comp.builds:
        y = header(f"{it['name']} – {it['W']:g} × {it['H']:g} × {it['D']:g} мм")
        draw_front(c, r.shapes, it["W"], it["H"], margin, 60, 330, y - 80, fronts=True)
        draw_front(c, r.shapes, it["W"], it["H"], margin + 360, 60, 200, y - 80, fronts=False)
        c.setFont(F, 7); c.drawString(margin, 45, "Изглед отпред (с фронтове)"); c.drawString(margin + 360, 45, "Без фронтове")
        tx = margin + 580
        c.setFont(F, 8)
        c.setFillColor(colors.black)
        yy = y
        for line in _wrap(r.info + ["", "Обков:"] + [f"  {h.name}: {h.qty:g} {h.unit}" for h in r.hardware], 52):
            c.drawString(tx, yy, line); yy -= 10
            if yy < 30:
                break
        c.showPage()

    # --- списък детайли
    cols = [("№", 22), ("Модул", 110), ("Детайл", 140), ("Материал", 140), ("Д", 45), ("Ш", 45), ("Бр", 25),
            ("Кант", 120), ("Рязане Д×Ш", 80)]
    def table_header(y):
        c.setFont(FB, 8)
        x = margin
        for t, w in cols:
            c.drawString(x, y, t); x += w
        c.line(margin, y - 3, PW - margin, y - 3)
        return y - 13
    y = table_header(header("Списък на детайлите (кроялен лист)"))
    c.setFont(F, 8)
    for i, p in enumerate(comp.parts, 1):
        if y < 35:
            c.showPage(); y = table_header(header("Списък на детайлите (продълж.)")); c.setFont(F, 8)
        cl, cw = p.cut_size(cat["bands"], st["reduce_band"])
        vals = [str(i), p.module[:22], p.name[:28], M[p.material]["name"][:28], f"{p.length:g}", f"{p.width:g}", str(p.qty), edges_str(p), f"{cl:g}×{cw:g}"]
        x = margin
        for (t, w), v in zip(cols, vals):
            c.drawString(x, y, v); x += w
        y -= 11
    c.setFont(F, 7)
    c.drawString(margin, max(y - 8, 20), "Д = размер по фладера. Д1/Д2 – кант по дългите ръбове, Ш1/Ш2 – по късите. Размер за рязане = готов размер − кант ≥ 1 мм.")
    c.showPage()

    # --- обков
    y = header("Обков и консумативи")
    c.setFont(F, 9)
    tot = 0
    for h in comp.hardware:
        c.drawString(margin, y, h.name[:90]); c.drawRightString(margin + 560, y, f"{h.qty:g} {h.unit}")
        c.drawRightString(margin + 650, y, f"{h.qty * h.price:.2f} €"); tot += h.qty * h.price; y -= 12
        if y < 40:
            c.showPage(); y = header("Обков (продълж.)"); c.setFont(F, 9)
    c.setFont(FB, 9); c.drawRightString(margin + 650, y - 4, f"Общо: {tot:.2f} €")
    y -= 24
    c.setFont(FB, 10); c.drawString(margin, y, "Кантове"); y -= 13; c.setFont(F, 9)
    for bk, m in comp.bands.items():
        c.drawString(margin, y, f"{find(cat['bands'], bk)['name']}: {m:.1f} м (+{st.get('band_reserve', 10)}% резерв = {m * (1 + st.get('band_reserve', 10) / 100):.1f} м)"); y -= 12
    c.showPage()

    # --- разкрой
    for mk, cr in comp.cuts.items():
        m = M[mk]
        for si, sh in enumerate(cr.sheets, 1):
            y = header(f"Разкрой: {m['name']} – плоча {si}/{cr.n_sheets} ({cr.sheet_l:g}×{cr.sheet_w:g})")
            c.setFont(F, 8)
            used = sh.used_area() / (cr.sheet_l * cr.sheet_w) * 100
            c.drawString(margin, y, f"Използване: {used:.1f}%   Рез: {cr.kerf:g} мм   Обрез: {cr.trim:g} мм   Фладер: {'по дължината (→)' if m['grain'] else 'няма – детайлите могат да се въртят'}")
            draw_sheet(c, sh, cr, margin, 40, PW - 2 * margin, y - 60, F)
            c.showPage()
        if cr.unplaced:
            y = header(f"НЕ СЕ ПОБИРАТ в {m['name']}")
            c.setFont(F, 9)
            for pc in cr.unplaced:
                c.drawString(margin, y, f"№{pc.label}: {pc.l:g}×{pc.w:g}"); y -= 12
            c.showPage()
    c.save()


def draw_sheet(c, sh, cr, x0, y0, maxw, maxh, F):
    from reportlab.lib import colors
    s = min(maxw / cr.sheet_l, maxh / cr.sheet_w)
    c.setFillColor(colors.HexColor("#f3f3f3")); c.setStrokeColor(colors.black); c.setLineWidth(0.8)
    c.rect(x0, y0, cr.sheet_l * s, cr.sheet_w * s, stroke=1, fill=1)
    for p in sh.placed:
        c.setFillColor(colors.HexColor("#e8c9a0")); c.setLineWidth(0.4)
        c.rect(x0 + p.x * s, y0 + p.y * s, p.dx * s, p.dy * s, stroke=1, fill=1)
        c.setFillColor(colors.black)
        fs = max(5, min(9, p.dy * s / 3, p.dx * s / 6))
        c.setFont(F, fs)
        cx, cy = x0 + (p.x + p.dx / 2) * s, y0 + (p.y + p.dy / 2) * s
        c.drawCentredString(cx, cy + fs * 0.2, f"№{p.piece.label}")
        if p.dy * s > 2.5 * fs:
            c.drawCentredString(cx, cy - fs, f"{p.dx:g}×{p.dy:g}{' ↻' if p.rotated else ''}")
    c.setFont(F, 7)
    c.drawString(x0, y0 - 10, f"{cr.sheet_l:g} мм →")


def _wrap(lines, n):
    out = []
    for ln in lines:
        while len(ln) > n:
            cut = ln.rfind(" ", 0, n)
            cut = n if cut <= 0 else cut
            out.append(ln[:cut]); ln = "   " + ln[cut:].lstrip()
        out.append(ln)
    return out
