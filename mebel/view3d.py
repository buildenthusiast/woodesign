"""3D изглед на мебелта (чист Tkinter, без допълнителни библиотеки).

Мебелта се сглобява от кутии (детайлите) по данните от furniture.build().
Управление: ляв бутон + влачене = въртене на 360°, колелце = мащаб,
десен бутон + влачене = преместване, двоен клик = начален изглед.
Плъзгачът „Отваряне“ отваря вратите и изтегля чекмеджетата.
"""
import math
import tkinter as tk
from tkinter import ttk

WOOD = "#c9a274"
WHITE = "#eeeeea"
MDF = "#e6e1d8"
DARK = "#555555"


def _mat_color(m):
    if not m:
        return WHITE
    if m.get("grain"):
        return WOOD
    if m.get("kind") == "МДФ":
        return MDF
    if m.get("kind") == "ХДФ":
        return "#dcdcd6"
    return WHITE


def _shade(hex_color, k):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    k = max(0.0, min(1.25, k))
    return "#%02x%02x%02x" % (min(255, int(r * k)), min(255, int(g * k)), min(255, int(b * k)))


def boxes_from(item, res, catalog):
    """Връща списък кутии: dict(x0,x1,y0,y1,z0,z1,color,kind,pivot).
    Оси: X – надясно, Y – нагоре, Z – назад (0 = лице на корпуса)."""
    M = {m["key"]: m for m in catalog["materials"]}
    cm, fm, bm = M.get(item["carcass_mat"]), M.get(item["front_mat"]), M.get(item.get("back_mat"))
    t = float(cm["t"]) if cm else 18.0
    ft = float(fm["t"]) if fm else 18.0
    D = float(item["D"])
    back = item.get("back", "nailed")
    bt = float(bm["t"]) if (bm and back != "none") else 0.0
    dp = D - bt if back == "nailed" else D
    cc, fc = _mat_color(cm), _mat_color(fm)
    out = []

    def B(x0, x1, y0, y1, z0, z1, color, kind, **kw):
        if x1 - x0 > 0.1 and y1 - y0 > 0.1 and z1 - z0 > 0.1:
            d = dict(x0=x0, x1=x1, y0=y0, y1=y1, z0=z0, z1=z1, color=color, kind=kind)
            d.update(kw)
            out.append(d)

    ymin_carc = None
    for k, x, y, w, h, lab in res.shapes:
        if k in ("side", "panel", "divider"):
            B(x, x + w, y, y + h, 0, dp, cc, k)
            if k == "side":
                ymin_carc = y if ymin_carc is None else min(ymin_carc, y)
        elif k == "shelf":
            B(x + 0.5, x + w - 0.5, y, y + h, 20, dp - (15 if back == "groove" else 2), cc, k)
        elif k == "plinth":
            B(x, x + w, y, y + h, 40, 40 + t, cc, k)
        elif k == "legs":
            for lx in (30, w - 70):
                for lz in (40, dp - 80):
                    B(lx, lx + 40, 0, h, lz, lz + 40, "#666666", "leg")
        elif k == "rail":
            zc = dp / 2
            B(x, x + w, y - 15, y, zc - 7, zc + 8, "#9a9a9a", "rail")
        elif k == "door":
            hinge_x = x if lab == "L" else x + w
            B(x, x + w, y, y + h, -ft, 0, fc, "door", hinge=hinge_x, side=lab)
        elif k == "lift":
            B(x, x + w, y, y + h, -ft, 0, fc, "lift", hinge_y=y + h)
        elif k == "drawer":
            B(x, x + w, y, y + h, -ft, 0, fc, "drawer")
            # кутия на чекмеджето зад фронта
            depth = max(200, dp - 30)
            B(x + 25, x + w - 25, y + 15, y + max(60, h - 40), 0, depth, "#d9d4c8", "drawerbox")
    if back != "none" and bt > 0:
        y0 = ymin_carc if ymin_carc is not None else 0
        y0 = max(y0, float(item.get("base_h", 0)) if item.get("base") == "plinth" else y0)
        if back == "nailed":
            B(0, float(item["W"]), y0, float(item["H"]), dp, dp + bt, _mat_color(bm), "back")
        else:
            B(t - 8, float(item["W"]) - t + 8, y0 + t - 8, float(item["H"]) - t + 8, dp - 15, dp - 15 + bt, _mat_color(bm), "back")
    return out


FACES = ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3))


def corners(b, op, D):
    xs, ys, zs = (b["x0"], b["x1"]), (b["y0"], b["y1"]), (b["z0"], b["z1"])
    pts = [(x, y, z) for x in xs for y in ys for z in zs]
    k = b["kind"]
    if op > 0 and k == "door":
        # въртене около вертикалната ос на пантата (до 100°)
        a = math.radians(100 * op) * (-1 if b["side"] == "L" else 1)   # навън към потребителя (z < 0)
        hx = b["hinge"]
        ca, sa = math.cos(a), math.sin(a)
        zp = b["z0"]   # оста е на предната страна на вратата – вратата излиза навън
        pts = [(hx + (x - hx) * ca - (z - zp) * sa, y, zp + (x - hx) * sa + (z - zp) * ca) for x, y, z in pts]
    elif op > 0 and k == "lift":
        a = math.radians(80 * op)   # клапата се вдига нагоре и навън
        hy = b["hinge_y"]
        ca, sa = math.cos(a), math.sin(a)
        zp = b["z0"]
        pts = [(x, hy + (y - hy) * ca - (z - zp) * sa, zp + (y - hy) * sa + (z - zp) * ca) for x, y, z in pts]
    elif op > 0 and k in ("drawer", "drawerbox"):
        dz = -0.75 * (D - 60) * op
        pts = [(x, y, z + dz) for x, y, z in pts]
    return pts



def render_polys(boxes, size, yaw, pitch, w, h, zoom=1.0, pan=(0.0, 0.0), op=0.0, show_back=True, show_fronts=True):
    """Проектира кутиите в 2D: връща [(точки [x1,y1,x2,y2,...], цвят)] в реда на рисуване.
    Екранните координати са с y надолу (както в Tk)."""
    polys = []
    W, H, D = size
    cx, cy, cz = W / 2, H / 2, D / 2
    ya, pa = math.radians(yaw), math.radians(pitch)
    cyw, syw, cp, sp = math.cos(ya), math.sin(ya), math.cos(pa), math.sin(pa)
    diag = math.sqrt(W * W + H * H + D * D)
    scale = min(w, h) / diag * 0.95 * zoom
    cam = diag * 2.2
    light = (-0.35, 0.55, -0.75)
    ln = math.sqrt(sum(c * c for c in light))
    light = tuple(c / ln for c in light)

    def tr(p):
        x, y, z = p[0] - cx, p[1] - cy, p[2] - cz
        x, z = x * cyw + z * syw, -x * syw + z * cyw          # около Y
        y, z = y * cp + z * sp, -y * sp + z * cp               # около X (наклон отгоре)
        return x, y, z

    # позиция на камерата в координатите на мебелта
    camw = (cx + cam * cp * syw, cy + cam * sp, cz - cam * cp * cyw)
    items = []
    for b in boxes:
        k = b["kind"]
        if k == "back" and not show_back:
            continue
        if k in ("door", "drawer", "lift") and not show_fronts:
            continue
        if k == "drawerbox" and op < 0.05 and show_fronts:
            continue
        Wp = corners(b, op, D)
        lo = [min(p[j] for p in Wp) for j in range(3)]
        hi = [max(p[j] for p in Wp) for j in range(3)]
        items.append((lo, hi, Wp, b))

    def sep(A, B):
        """-1: A е зад B; 1: A е пред B; 0: не са разделени."""
        # кутии, разделени по някоя ос: по-далечната от камерата се рисува първа
        for i in range(3):
            if A[1][i] <= B[0][i] + 0.5:
                if camw[i] >= A[1][i]:
                    return -1
                if camw[i] <= B[0][i]:
                    return 1
            if B[1][i] <= A[0][i] + 0.5:
                if camw[i] >= B[1][i]:
                    return 1
                if camw[i] <= A[0][i]:
                    return -1
        return 0

    # топологична подредба: „зад“ преди „пред“; при равенство – по разстояние
    n = len(items)
    dist = [sum(((it[0][j] + it[1][j]) / 2 - camw[j]) ** 2 for j in range(3)) for it in items]
    after = [[] for _ in range(n)]
    indeg = [0] * n
    for i in range(n):
        for j in range(i + 1, n):
            r = sep(items[i], items[j])
            if r == -1:
                after[i].append(j); indeg[j] += 1
            elif r == 1:
                after[j].append(i); indeg[i] += 1
    import heapq
    heap = [(-dist[i], i) for i in range(n) if indeg[i] == 0]
    heapq.heapify(heap)
    order, done = [], [False] * n
    while len(order) < n:
        if not heap:   # цикъл – взимаме най-далечния оставащ
            i = max((k for k in range(n) if not done[k]), key=lambda k: dist[k])
            indeg[i] = 0
            heapq.heappush(heap, (-dist[i], i))
        _, i = heapq.heappop(heap)
        if done[i]:
            continue
        done[i] = True
        order.append(i)
        for j in after[i]:
            indeg[j] -= 1
            if indeg[j] == 0 and not done[j]:
                heapq.heappush(heap, (-dist[j], j))
    for idx in order:
        lo, hi, Wp, b = items[idx]
        P = [tr(p) for p in Wp]
        bc = [sum(p[j] for p in P) / 8 for j in range(3)]
        for f in FACES:
            ctr = [sum(P[i][j] for i in f) / 4 for j in range(3)]
            out_n = (ctr[0] - bc[0], ctr[1] - bc[1], ctr[2] - bc[2])
            to_cam = (-ctr[0], -ctr[1], -cam - ctr[2])
            if out_n[0] * to_cam[0] + out_n[1] * to_cam[1] + out_n[2] * to_cam[2] <= 0:
                continue   # лицето е обърнато назад
            a, b1, c = P[f[0]], P[f[1]], P[f[2]]
            u = (b1[0] - a[0], b1[1] - a[1], b1[2] - a[2])
            v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
            n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
            nl = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1
            lam = abs((n[0] * light[0] + n[1] * light[1] + n[2] * light[2]) / nl)
            pts2 = []
            for i in f:
                x, y, z = P[i]
                pz = cam / (cam + z)
                pts2 += [w / 2 + pan[0] + x * scale * pz, h / 2 + pan[1] - y * scale * pz]
            polys.append((pts2, _shade(b["color"], 0.62 + 0.45 * lam)))
    return polys


class View3D(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(bar, text="Влачете с мишката за въртене на 360° · колелце = мащаб · десен бутон = преместване · двоен клик = начален изглед").pack(side="left")
        self.open_var = tk.DoubleVar(value=0)
        ttk.Label(bar, text="   Отваряне:").pack(side="left")
        ttk.Scale(bar, from_=0, to=1, variable=self.open_var, command=lambda e: self.redraw(), length=160).pack(side="left")
        self.show_back = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Гръб", variable=self.show_back, command=self.redraw).pack(side="left", padx=6)
        self.show_fronts = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Фронтове", variable=self.show_fronts, command=self.redraw).pack(side="left")
        for txt, yaw, pitch in (("Отпред", 0, 0), ("Отстрани", 90, 0), ("Отгоре", 0, 89), ("3/4", 35, 20)):
            ttk.Button(bar, text=txt, command=lambda a=yaw, b=pitch: self.set_view(a, b)).pack(side="left", padx=1)
        self.cv = tk.Canvas(self, bg="#f7f7f5", highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.boxes = []
        self.size = (1000, 1000, 600)
        self.reset()
        self.cv.bind("<ButtonPress-1>", self._press)
        self.cv.bind("<B1-Motion>", self._rot)
        self.cv.bind("<ButtonPress-3>", self._press)
        self.cv.bind("<B3-Motion>", self._pan)
        self.cv.bind("<MouseWheel>", lambda e: self._zoom(1.1 if e.delta > 0 else 1 / 1.1))
        self.cv.bind("<Button-4>", lambda e: self._zoom(1.1))
        self.cv.bind("<Button-5>", lambda e: self._zoom(1 / 1.1))
        self.cv.bind("<Double-Button-1>", lambda e: (self.reset(), self.redraw()))
        self.cv.bind("<Configure>", lambda e: self.redraw())

    # ---------------------------------------------------------- управление
    def reset(self):
        self.yaw, self.pitch, self.zoom, self.pan = 35.0, 18.0, 1.0, [0.0, 0.0]

    def set_view(self, yaw, pitch):
        self.yaw, self.pitch = float(yaw), float(pitch)
        self.redraw()

    def _press(self, e):
        self._last = (e.x, e.y)

    def _rot(self, e):
        dx, dy = e.x - self._last[0], e.y - self._last[1]
        self._last = (e.x, e.y)
        self.yaw = (self.yaw + dx * 0.5) % 360
        self.pitch = max(-89, min(89, self.pitch + dy * 0.4))
        self.redraw()

    def _pan(self, e):
        self.pan[0] += e.x - self._last[0]
        self.pan[1] += e.y - self._last[1]
        self._last = (e.x, e.y)
        self.redraw()

    def _zoom(self, f):
        self.zoom = max(0.2, min(8, self.zoom * f))
        self.redraw()

    def set_model(self, item, res, catalog):
        self.boxes = boxes_from(item, res, catalog) if res else []
        self.size = (float(item["W"]), float(item["H"]), float(item["D"]))
        self.redraw()

    # ---------------------------------------------------------- геометрия
    def _corners(self, b, op):
        return corners(b, op, self.size[2])

    def redraw(self):
        cv = self.cv
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 20 or not self.boxes:
            return
        W, H, D = self.size
        for pts2, col in render_polys(self.boxes, self.size, self.yaw, self.pitch, w, h, self.zoom, self.pan,
                                      float(self.open_var.get()), self.show_back.get(), self.show_fronts.get()):
            cv.create_polygon(pts2, fill=col, outline="#6d6252", width=0.6)
        cv.create_text(10, h - 10, anchor="sw", fill="#777",
                       text=f"{W:g} × {H:g} × {D:g} мм   ·   завъртане {self.yaw:.0f}°, наклон {self.pitch:.0f}°")
