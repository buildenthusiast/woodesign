"""Графичен интерфейс (Tkinter) на Мебел Дизайнер."""
import copy
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from . import __version__
from .catalog import FURNITURE_TYPES, BASE_TYPES, TOP_TYPES, BACK_TYPES, HANDLES, find
from .furniture import build, default_item, new_section
from .ideas import ideas
from .project import new_project, save, load, compute
from .export import export_pdf, export_parts_csv, export_hardware_csv, edges_str
from .tips import TIPS
from . import photo
from .view3d import View3D
from . import quote as quote_mod
from . import updater
from . import decors as decor_mod

FRONT_COL = {"door": "#e2c29b", "drawer": "#d4b089", "lift": "#e2c29b"}
CARC_COL = {"side": "#f0f0f0", "panel": "#f0f0f0", "divider": "#f0f0f0", "plinth": "#9a9a9a", "shelf": "#c8c8c8"}


class ScrollFrame(ttk.Frame):
    def __init__(self, master, width=380):
        super().__init__(master)
        self.canvas = tk.Canvas(self, width=width, highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", self._wheel, add="+")

    def _wheel(self, e):
        w = self.winfo_containing(e.x_root, e.y_root)
        while w is not None:
            if w is self:
                self.canvas.yview_scroll(int(-e.delta / 120), "units")
                return
            w = w.master


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Мебел Дизайнер {__version__} – ПДЧ/МДФ")
        self.geometry("1400x860")
        self.minsize(1100, 700)
        try:
            ttk.Style().theme_use("vista" if os.name == "nt" else "clam")
        except tk.TclError:
            pass
        self.project = new_project()
        self.path = None
        self.cur = 0
        self.comp = None
        self._loading = False
        self._after = None
        self.sheet_idx = 0
        self._build_menu()
        self._build_ui()
        self.refresh_all()
        self.after(2500, lambda: self.check_updates(silent=True))

    # ------------------------------------------------------------ updates
    def check_updates(self, silent=True):
        import threading
        out = {}

        def work():
            try:
                out["info"] = updater.check()
            except Exception as e:  # noqa – без интернет и т.н.
                out["err"] = str(e)
        th = threading.Thread(target=work, daemon=True)
        th.start()
        self.status.set("Проверявам за нова версия…")

        def poll():
            if th.is_alive():
                self.after(300, poll)
                return
            info = out.get("info")
            if "err" in out:
                updater.log(f"грешка: {out['err']}")
                self.status.set(f"Проверката за обновления не успя ({out['err'][:80]}). Помощ → Провери за обновления.")
                if not silent:
                    messagebox.showwarning("Обновления", f"Не мога да проверя за обновления:\n{out['err']}\n\n"
                                           f"Изтеглете ръчно от github.com/{updater.REPO}/releases")
                return
            if not info:
                self.status.set(f"Имате последната версия ({__version__}).")
                if not silent:
                    messagebox.showinfo("Обновления", f"Имате последната версия ({__version__}).")
                return
            updater.log(f"намерена версия {info['version']}")
            self.status.set(f"Има нова версия {info['version']} – Помощ → Провери за обновления.")
            msg = f"Има нова версия {info['version']} (вашата е {__version__}).\n\n{info['notes'][:600]}\n\n"
            if updater.is_frozen() and info.get("url"):
                if messagebox.askyesno("Нова версия", msg + "Да я сваля и инсталирам ли сега? Програмата ще се рестартира (запазете проекта)."):
                    self.config(cursor="watch")
                    self.update()
                    try:
                        if updater.download_and_replace(info["url"]):
                            self.destroy()
                    except Exception as e:  # noqa
                        updater.log(f"сваляне: {e!r}")
                        self.config(cursor="")
                        messagebox.showerror("Обновления", f"Грешка при обновяване:\n{e}\n\nИзтеглете ръчно: {info.get('page')}")
            elif not silent or info.get("url"):
                if messagebox.askyesno("Нова версия", msg + "Да отворя ли страницата за изтегляне?"):
                    import webbrowser
                    webbrowser.open(info.get("page") or f"https://github.com/{updater.REPO}/releases")
        self.after(300, poll)

    # ------------------------------------------------------------ helpers
    @property
    def cat(self):
        return self.project["catalog"]

    @property
    def item(self):
        items = self.project["items"]
        if not items:
            return None
        self.cur = max(0, min(self.cur, len(items) - 1))
        return items[self.cur]

    def mat_names(self, kinds=None):
        return [m["name"] for m in self.cat["materials"] if not kinds or m["kind"] in kinds]

    def key_by_name(self, lst, name):
        for m in lst:
            if m["name"] == name:
                return m["key"]
        return None

    def name_by_key(self, lst, key):
        for m in lst:
            if m["key"] == key:
                return m["name"]
        return ""

    # ------------------------------------------------------------ menu
    def _build_menu(self):
        mb = tk.Menu(self)
        f = tk.Menu(mb, tearoff=0)
        f.add_command(label="Нов проект", command=self.cmd_new, accelerator="Ctrl+N")
        f.add_command(label="Отвори…", command=self.cmd_open, accelerator="Ctrl+O")
        f.add_command(label="Запази", command=self.cmd_save, accelerator="Ctrl+S")
        f.add_command(label="Запази като…", command=lambda: self.cmd_save(True))
        f.add_separator()
        f.add_command(label="Експорт PDF (чертежи, детайли, разкрой)…", command=self.cmd_pdf)
        f.add_command(label="Експорт CSV – кроялен лист…", command=self.cmd_csv)
        f.add_command(label="Експорт CSV – обков…", command=self.cmd_hw_csv)
        f.add_separator()
        f.add_command(label="Оферта за клиент (PDF)…", command=self.cmd_quote)
        f.add_separator()
        f.add_command(label="Изход", command=self.destroy)
        mb.add_cascade(label="Файл", menu=f)
        ph = tk.Menu(mb, tearoff=0)
        ph.add_command(label="Нова мебел от снимка…", command=self.cmd_photo)
        ph.add_command(label="API ключ и доставчик (Claude / Grok)…", command=self.cmd_api_key)
        mb.add_cascade(label="Снимка", menu=ph)
        h = tk.Menu(mb, tearoff=0)
        h.add_command(label="Провери за обновления…", command=lambda: self.check_updates(silent=False))
        h.add_command(label="За програмата", command=lambda: messagebox.showinfo(
            "За програмата", f"Мебел Дизайнер {__version__}\nПараметричен дизайн и разкрой на мебели от ПДЧ и МДФ.\n"
                             "Размерите са в мм. Проверявайте винаги размерите преди рязане!"))
        mb.add_cascade(label="Помощ", menu=h)
        self.config(menu=mb)
        self.bind("<Control-n>", lambda e: self.cmd_new())
        self.bind("<Control-o>", lambda e: self.cmd_open())
        self.bind("<Control-s>", lambda e: self.cmd_save())

    # ------------------------------------------------------------ UI
    def _build_ui(self):
        pw = ttk.PanedWindow(self, orient="horizontal")
        pw.pack(fill="both", expand=True)
        left = ttk.Frame(pw, padding=6)
        pw.add(left, weight=0)
        ttk.Label(left, text="Мебели в проекта", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.lst = tk.Listbox(left, width=28, height=20, exportselection=False)
        self.lst.pack(fill="both", expand=True, pady=4)
        self.lst.bind("<<ListboxSelect>>", self.on_select_item)
        ttk.Label(left, text="Тип за добавяне:").pack(anchor="w")
        self.new_type = tk.StringVar(value=FURNITURE_TYPES["wardrobe"])
        ttk.Combobox(left, textvariable=self.new_type, values=list(FURNITURE_TYPES.values()), state="readonly").pack(fill="x")
        ttk.Button(left, text="+ Добави мебел", command=self.add_item).pack(fill="x", pady=(4, 2))
        ttk.Button(left, text="📷 Мебел от снимка…", command=self.cmd_photo).pack(fill="x", pady=2)
        ttk.Button(left, text="Дублирай", command=self.dup_item).pack(fill="x", pady=2)
        ttk.Button(left, text="Изтрий", command=self.del_item).pack(fill="x", pady=2)

        self.nb = ttk.Notebook(pw)
        pw.add(self.nb, weight=1)
        self._tab_design()
        self.v3d = View3D(self.nb)
        self.nb.add(self.v3d, text="  3D изглед  ")
        self._tab_parts()
        self._tab_cut()
        self._tab_materials()
        self._tab_tips()
        self.nb.bind("<<NotebookTabChanged>>", self.on_tab)

        self.status = tk.StringVar(value="Готово.")
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w").pack(fill="x", side="bottom")

    # ---- Дизайн
    def _tab_design(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="  Дизайн  ")
        sf = ScrollFrame(tab, width=420)
        sf.pack(side="left", fill="y")
        f = sf.inner
        self.v = {}
        r = 0

        def head(txt):
            nonlocal r
            ttk.Label(f, text=txt, font=("Segoe UI", 10, "bold")).grid(row=r, column=0, columnspan=2, sticky="w", pady=(10, 2), padx=4)
            r += 1

        def row(label, key, kind="entry", values=None, width=30):
            nonlocal r
            ttk.Label(f, text=label).grid(row=r, column=0, sticky="w", padx=4, pady=1)
            var = tk.StringVar()
            if kind == "combo":
                w = ttk.Combobox(f, textvariable=var, values=values or [], state="readonly", width=width)
            else:
                w = ttk.Entry(f, textvariable=var, width=width + 2)
            w.grid(row=r, column=1, sticky="we", padx=4, pady=1)
            var.trace_add("write", lambda *a: self.on_field())
            self.v[key] = (var, w)
            r += 1
            return w

        head("Габарити (мм)")
        row("Име", "name")
        ttk.Label(f, text="Тип").grid(row=r, column=0, sticky="w", padx=4)
        self.type_lbl = ttk.Label(f, text="")
        self.type_lbl.grid(row=r, column=1, sticky="w", padx=4)
        r += 1
        row("Широчина Ш", "W")
        row("Височина В", "H")
        row("Дълбочина Д", "D")

        ib = ttk.Frame(f)
        ib.grid(row=r, column=0, columnspan=2, sticky="we", padx=4, pady=6)
        r += 1
        ttk.Button(ib, text="💡 Дай ми идеи по тези размери", command=self.show_ideas).pack(fill="x")
        self.ideas_lb = tk.Listbox(f, height=5, exportselection=False)
        self.ideas_lb.grid(row=r, column=0, columnspan=2, sticky="we", padx=4)
        self.ideas_lb.bind("<<ListboxSelect>>", self.on_idea_sel)
        self.ideas_lb.bind("<Double-Button-1>", lambda e: self.apply_idea())
        r += 1
        self.idea_desc = ttk.Label(f, text="", wraplength=380, foreground="#444")
        self.idea_desc.grid(row=r, column=0, columnspan=2, sticky="w", padx=4)
        r += 1
        ttk.Button(f, text="Приложи избраната идея", command=self.apply_idea).grid(row=r, column=0, columnspan=2, sticky="we", padx=4, pady=2)
        r += 1

        head("Материали")
        row("Корпус", "carcass_mat", "combo")
        row("Фронтове (врати/чекм.)", "front_mat", "combo")
        row("Гръб", "back_mat", "combo")
        row("Чекмеджета – кутия", "drawer_mat", "combo")
        row("Чекмеджета – дъно", "drawer_bottom_mat", "combo")
        head("Цвят / декор")
        row("Декор корпус", "carcass_decor", "combo", width=34)
        self.sw_c = tk.Label(f, text="    ", relief="solid", bd=1)
        self.sw_c.grid(row=r - 1, column=2, padx=2)
        row("Декор фронтове", "front_decor", "combo", width=34)
        self.sw_f = tk.Label(f, text="    ", relief="solid", bd=1)
        self.sw_f.grid(row=r - 1, column=2, padx=2)
        ttk.Button(f, text="🎨 Библиотека с декори…", command=self.cmd_decors).grid(row=r, column=0, columnspan=2, sticky="we", padx=4, pady=2)
        r += 1
        head("Кантове")
        row("Корпус (видими ръбове)", "carcass_band", "combo")
        row("Фронтове (4 страни)", "front_band", "combo")
        row("Кутии чекмеджета", "drawer_band", "combo")
        head("Конструкция")
        row("Основа", "base", "combo", list(BASE_TYPES.values()))
        row("Височина крачета/цокъл", "base_h")
        row("Таван", "top", "combo", list(TOP_TYPES.values()))
        row("Гръб", "back", "combo", list(BACK_TYPES.values()))
        row("Фуга между фронтове", "gap")
        head("Обков")
        row("Панти", "hinge", "combo", width=40)
        row("Водачи", "slide", "combo", width=40)
        row("Дръжки", "handle", "combo", list(HANDLES.values()), width=40)

        head("Секции (отляво надясно)")
        cols = ("w", "doors", "sh", "dr", "drh", "rail")
        self.sec_tv = ttk.Treeview(f, columns=cols, show="headings", height=5)
        for c_, t_, w_ in zip(cols, ("Шир.", "Врати", "Рафт.", "Чекм.", "Вис.ч.", "Закач."), (60, 50, 50, 50, 55, 55)):
            self.sec_tv.heading(c_, text=t_)
            self.sec_tv.column(c_, width=w_, anchor="center")
        self.sec_tv.grid(row=r, column=0, columnspan=2, sticky="we", padx=4)
        self.sec_tv.bind("<<TreeviewSelect>>", self.on_sec_sel)
        r += 1
        bf = ttk.Frame(f)
        bf.grid(row=r, column=0, columnspan=2, sticky="we", padx=4, pady=2)
        r += 1
        ttk.Button(bf, text="+ Секция", command=self.add_sec).pack(side="left", expand=True, fill="x")
        ttk.Button(bf, text="− Секция", command=self.del_sec).pack(side="left", expand=True, fill="x")
        ttk.Button(bf, text="◀", width=3, command=lambda: self.move_sec(-1)).pack(side="left")
        ttk.Button(bf, text="▶", width=3, command=lambda: self.move_sec(1)).pack(side="left")
        self.sv = {}
        sec_fields = [("Светла широчина (0 = авто)", "width"), ("Брой врати (0/1/2)", "doors"), ("Рафтове", "shelves"),
                      ("Чекмеджета", "drawers"), ("Височина фронт чекм. (0 = цялата)", "drawer_h"),
                      ("Закачалки (0/1/2)", "rail"), ("Височина на вратите (0 = цялата)", "door_h"),
                      ("Рафтове над вратите", "open_shelves")]
        for lbl, k in sec_fields:
            ttk.Label(f, text=lbl).grid(row=r, column=0, sticky="w", padx=4)
            var = tk.StringVar()
            ttk.Spinbox(f, from_=0, to=5000, textvariable=var, width=10).grid(row=r, column=1, sticky="w", padx=4, pady=1)
            var.trace_add("write", lambda *a: self.on_sec_field())
            self.sv[k] = var
            r += 1
        for lbl, k in (("Фиксирани рафтове (с конфирмати)", "shelf_fixed"), ("Чекмеджетата горе, вратата долу", "drawer_top")):
            var = tk.BooleanVar()
            ttk.Checkbutton(f, text=lbl, variable=var, command=self.on_sec_field).grid(row=r, column=0, columnspan=2, sticky="w", padx=4)
            self.sv[k] = var
            r += 1
        f.columnconfigure(1, weight=1)

        right = ttk.Frame(tab, padding=6)
        right.pack(side="left", fill="both", expand=True)
        top = ttk.Frame(right)
        top.pack(fill="x")
        self.show_fronts = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Покажи фронтовете", variable=self.show_fronts, command=self.draw_preview).pack(side="left")
        self.dim_lbl = ttk.Label(top, text="")
        self.dim_lbl.pack(side="right")
        self.prev = tk.Canvas(right, bg="white", highlightthickness=1, highlightbackground="#ccc")
        self.prev.pack(fill="both", expand=True, pady=4)
        self.prev.bind("<Configure>", lambda e: self.draw_preview())
        self.msg = tk.Text(right, height=9, wrap="word", font=("Segoe UI", 9))
        self.msg.pack(fill="x")
        self.msg.tag_configure("warn", foreground="#b00000")
        self.msg.tag_configure("info", foreground="#333")
        self.msg.tag_configure("tip", foreground="#005a9e")

    # ---- Детайли
    def _tab_parts(self):
        tab = ttk.Frame(self.nb, padding=6)
        self.nb.add(tab, text="  Детайли и обков  ")
        bar = ttk.Frame(tab)
        bar.pack(fill="x")
        ttk.Button(bar, text="Преизчисли", command=self.recompute).pack(side="left")
        ttk.Button(bar, text="CSV кроялен лист…", command=self.cmd_csv).pack(side="left", padx=4)
        ttk.Button(bar, text="PDF документация…", command=self.cmd_pdf).pack(side="left")
        ttk.Button(bar, text="💶 Оферта за клиент…", command=self.cmd_quote).pack(side="left", padx=4)
        self.cost_lbl = ttk.Label(bar, text="", font=("Segoe UI", 10, "bold"))
        self.cost_lbl.pack(side="right")
        cols = ("n", "mod", "name", "mat", "l", "w", "q", "edges", "cut")
        heads = ("№", "Модул", "Детайл", "Материал", "Дълж. (фладер)", "Шир.", "Бр.", "Кант", "Рязане Д×Ш")
        widths = (40, 150, 190, 200, 90, 70, 40, 160, 110)
        pf = ttk.Frame(tab)
        pf.pack(fill="both", expand=True, pady=4)
        self.parts_tv = ttk.Treeview(pf, columns=cols, show="headings")
        for c_, h_, w_ in zip(cols, heads, widths):
            self.parts_tv.heading(c_, text=h_)
            self.parts_tv.column(c_, width=w_, anchor="w" if c_ in ("mod", "name", "mat", "edges") else "center")
        sb = ttk.Scrollbar(pf, command=self.parts_tv.yview)
        self.parts_tv.configure(yscrollcommand=sb.set)
        self.parts_tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        bot = ttk.Frame(tab)
        bot.pack(fill="both", expand=False)
        ttk.Label(bot, text="Обков", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(bot, text="Цена (ориентировъчно)", font=("Segoe UI", 10, "bold")).grid(row=0, column=1, sticky="w", padx=10)
        self.hw_tv = ttk.Treeview(bot, columns=("name", "q", "u", "sum"), show="headings", height=9)
        for c_, h_, w_ in zip(("name", "q", "u", "sum"), ("Обков", "Кол.", "Мярка", "Сума €"), (420, 60, 50, 70)):
            self.hw_tv.heading(c_, text=h_)
            self.hw_tv.column(c_, width=w_, anchor="w" if c_ == "name" else "center")
        self.hw_tv.grid(row=1, column=0, sticky="nsew")
        self.cost_tv = ttk.Treeview(bot, columns=("name", "q", "sum"), show="headings", height=9)
        for c_, h_, w_ in zip(("name", "q", "sum"), ("Позиция", "Количество", "Сума €"), (230, 90, 80)):
            self.cost_tv.heading(c_, text=h_)
            self.cost_tv.column(c_, width=w_, anchor="w" if c_ == "name" else "e")
        self.cost_tv.tag_configure("tot", font=("Segoe UI", 9, "bold"))
        self.cost_tv.grid(row=1, column=1, sticky="nsew", padx=10)
        bot.columnconfigure(0, weight=1)

    # ---- Разкрой
    def _tab_cut(self):
        tab = ttk.Frame(self.nb, padding=6)
        self.nb.add(tab, text="  Разкрой  ")
        bar = ttk.Frame(tab)
        bar.pack(fill="x")
        self.cut_v = {}
        for lbl, k, w in (("Дебелина на диска (рез), мм", "kerf", 6), ("Обрез по краищата, мм", "trim", 6),
                          ("Итерации", "iterations", 6), ("Цена рязане €/м", "cut_price_m", 6), ("Цена кантиране €/м", "band_service_m", 6)):
            ttk.Label(bar, text=lbl).pack(side="left", padx=(8, 2))
            var = tk.StringVar()
            ttk.Entry(bar, textvariable=var, width=w).pack(side="left")
            self.cut_v[k] = var
        self.reduce_band = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Приспадай канта ≥1 мм", variable=self.reduce_band).pack(side="left", padx=8)
        ttk.Button(bar, text="▶ Оптимизирай разкроя", command=self.run_opt).pack(side="left", padx=8)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=4)
        ttk.Label(bar2, text="Материал:").pack(side="left")
        self.cut_mat = tk.StringVar()
        self.cut_mat_cb = ttk.Combobox(bar2, textvariable=self.cut_mat, state="readonly", width=40)
        self.cut_mat_cb.pack(side="left", padx=4)
        self.cut_mat_cb.bind("<<ComboboxSelected>>", lambda e: (setattr(self, "sheet_idx", 0), self.draw_sheet()))
        ttk.Button(bar2, text="◀ Плоча", command=lambda: self.nav_sheet(-1)).pack(side="left", padx=4)
        ttk.Button(bar2, text="Плоча ▶", command=lambda: self.nav_sheet(1)).pack(side="left")
        self.cut_stat = ttk.Label(bar2, text="Натиснете „Оптимизирай разкроя“.")
        self.cut_stat.pack(side="left", padx=10)
        self.sheet_cv = tk.Canvas(tab, bg="white")
        self.sheet_cv.pack(fill="both", expand=True)
        self.sheet_cv.bind("<Configure>", lambda e: self.draw_sheet())
        self.cut_sum = ttk.Label(tab, text="", justify="left")
        self.cut_sum.pack(fill="x")

    # ---- Материали
    def _tab_materials(self):
        tab = ttk.Frame(self.nb, padding=6)
        self.nb.add(tab, text="  Материали и цени  ")
        ttk.Label(tab, text="Плоскостни материали (двоен клик = редакция). Дължината на плочата е по фладера.",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")
        cols = ("name", "kind", "t", "l", "w", "g", "p")
        self.mat_tv = ttk.Treeview(tab, columns=cols, show="headings", height=11)
        for c_, h_, w_ in zip(cols, ("Име", "Вид", "Дебелина", "Дължина", "Ширина", "Фладер", "Цена/плоча €"), (300, 60, 70, 80, 80, 60, 100)):
            self.mat_tv.heading(c_, text=h_)
            self.mat_tv.column(c_, width=w_, anchor="w" if c_ == "name" else "center")
        self.mat_tv.pack(fill="x")
        self.mat_tv.bind("<Double-Button-1>", lambda e: self.edit_mat())
        bf = ttk.Frame(tab)
        bf.pack(fill="x", pady=3)
        ttk.Button(bf, text="+ Нов материал", command=lambda: self.edit_mat(new=True)).pack(side="left")
        ttk.Button(bf, text="Редактирай", command=self.edit_mat).pack(side="left", padx=4)
        ttk.Button(bf, text="Изтрий", command=self.del_mat).pack(side="left")
        ttk.Label(tab, text="Кантове, панти, водачи и дребен обков – двоен клик за промяна на цената",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 0))
        self.price_tv = ttk.Treeview(tab, columns=("grp", "name", "p"), show="headings", height=16)
        for c_, h_, w_ in zip(("grp", "name", "p"), ("Група", "Име", "Цена €"), (100, 560, 90)):
            self.price_tv.heading(c_, text=h_)
            self.price_tv.column(c_, width=w_, anchor="w" if c_ != "p" else "center")
        self.price_tv.pack(fill="both", expand=True)
        self.price_tv.bind("<Double-Button-1>", lambda e: self.edit_price())

    def _tab_tips(self):
        tab = ttk.Frame(self.nb, padding=6)
        self.nb.add(tab, text="  Съвети  ")
        t = tk.Text(tab, wrap="word", font=("Segoe UI", 10), padx=10, pady=10)
        sb = ttk.Scrollbar(tab, command=t.yview)
        t.configure(yscrollcommand=sb.set)
        t.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        t.tag_configure("h", font=("Segoe UI", 12, "bold"), spacing1=10)
        for title, body in TIPS:
            t.insert("end", title + "\n", "h")
            t.insert("end", body.strip() + "\n")
        t.configure(state="disabled")

    # ------------------------------------------------------------ refresh
    def refresh_all(self):
        self.refresh_list()
        self.refresh_combos()
        self.load_item()
        self.load_settings()
        self.refresh_materials()

    def refresh_list(self):
        self.lst.delete(0, "end")
        for it in self.project["items"]:
            self.lst.insert("end", f"{it['name']}  ({it['W']:g}×{it['H']:g}×{it['D']:g})")
        if self.project["items"]:
            self.lst.selection_clear(0, "end")
            self.lst.selection_set(self.cur)

    def refresh_combos(self):
        c = self.cat
        allm = self.mat_names()
        for k in ("carcass_mat", "front_mat", "drawer_mat"):
            self.v[k][1]["values"] = allm
        thin = [m["name"] for m in c["materials"] if m["t"] <= 8] or allm
        self.v["back_mat"][1]["values"] = thin
        self.v["drawer_bottom_mat"][1]["values"] = allm
        bands = [b["name"] for b in c["bands"]]
        for k in ("carcass_band", "front_band", "drawer_band"):
            self.v[k][1]["values"] = bands
        self.v["hinge"][1]["values"] = [h["name"] for h in c["hinges"]]
        self.v["slide"][1]["values"] = [s["name"] for s in c["slides"]]
        labels = [decor_mod.label(d) for d in c.get("decors", [])]
        self.v["carcass_decor"][1]["values"] = labels
        self.v["front_decor"][1]["values"] = labels

    def load_item(self, keep_ideas=False):
        it = self.item
        self._loading = True
        try:
            if it is None:
                return
            c = self.cat
            self.type_lbl.config(text=FURNITURE_TYPES.get(it["type"], it["type"]))
            for k in ("name", "W", "H", "D", "base_h", "gap"):
                v = it.get(k, "")
                self.v[k][0].set(f"{v:g}" if isinstance(v, (int, float)) else v)
            for k in ("carcass_mat", "front_mat", "back_mat", "drawer_mat", "drawer_bottom_mat"):
                self.v[k][0].set(self.name_by_key(c["materials"], it.get(k)))
            for k in ("carcass_band", "front_band", "drawer_band"):
                self.v[k][0].set(self.name_by_key(c["bands"], it.get(k)))
            self.v["hinge"][0].set(self.name_by_key(c["hinges"], it.get("hinge")))
            self.v["slide"][0].set(self.name_by_key(c["slides"], it.get("slide")))
            M = {m["key"]: m for m in c["materials"]}
            for k, mk in (("carcass_decor", "carcass_mat"), ("front_decor", "front_mat")):
                d = decor_mod.get(c.get("decors", []), it.get(k) or decor_mod.default_for_material(M.get(it.get(mk))))
                self.v[k][0].set(decor_mod.label(d))
            self.update_swatches()
            self.v["base"][0].set(BASE_TYPES.get(it.get("base"), ""))
            self.v["top"][0].set(TOP_TYPES.get(it.get("top"), ""))
            self.v["back"][0].set(BACK_TYPES.get(it.get("back"), ""))
            self.v["handle"][0].set(HANDLES.get(it.get("handle"), ""))
            self.refresh_secs()
        finally:
            self._loading = False
        if not keep_ideas:
            self.ideas_lb.delete(0, "end")
            self.idea_desc.config(text="")
        self.update_design()

    def refresh_secs(self, sel=0):
        self.sec_tv.delete(*self.sec_tv.get_children())
        for i, s in enumerate(self.item["sections"]):
            self.sec_tv.insert("", "end", iid=str(i), values=(
                f"{s.get('width') or 'авто'}", s.get("doors", 0), s.get("shelves", 0), s.get("drawers", 0),
                s.get("drawer_h", 0) or "цяла", s.get("rail", 0)))
        if self.item["sections"]:
            sel = min(sel, len(self.item["sections"]) - 1)
            self.sec_tv.selection_set(str(sel))
            self.load_sec(sel)

    def load_sec(self, i):
        s = self.item["sections"][i]
        prev = self._loading
        self._loading = True
        for k, var in self.sv.items():
            v = s.get(k, 0)
            if isinstance(var, tk.BooleanVar):
                var.set(bool(v))
            else:
                var.set(f"{float(v or 0):g}")
        self._loading = prev

    def cur_sec(self):
        sel = self.sec_tv.selection()
        return int(sel[0]) if sel else 0

    # ------------------------------------------------------------ events
    def on_field(self):
        if self._loading or self.item is None:
            return
        it = self.item
        c = self.cat

        def num(k, default):
            try:
                return float(self.v[k][0].get().replace(",", "."))
            except ValueError:
                return default
        it["name"] = self.v["name"][0].get() or "Модул"
        for k in ("W", "H", "D", "base_h", "gap"):
            it[k] = num(k, it.get(k, 0))
        for k in ("carcass_mat", "front_mat", "back_mat", "drawer_mat", "drawer_bottom_mat"):
            key = self.key_by_name(c["materials"], self.v[k][0].get())
            if key:
                it[k] = key
        for k in ("carcass_band", "front_band", "drawer_band"):
            key = self.key_by_name(c["bands"], self.v[k][0].get())
            if key:
                it[k] = key
        hk = self.key_by_name(c["hinges"], self.v["hinge"][0].get())
        if hk:
            it["hinge"] = hk
        for k in ("carcass_decor", "front_decor"):
            lab = self.v[k][0].get()
            for d in c.get("decors", []):
                if decor_mod.label(d) == lab:
                    it[k] = d["key"]
        self.update_swatches()
        sk = self.key_by_name(c["slides"], self.v["slide"][0].get())
        if sk:
            it["slide"] = sk
        for k, mp in (("base", BASE_TYPES), ("top", TOP_TYPES), ("back", BACK_TYPES), ("handle", HANDLES)):
            for kk, vv in mp.items():
                if vv == self.v[k][0].get():
                    it[k] = kk
        self.schedule_update()

    def on_sec_field(self):
        if self._loading or self.item is None or not self.item["sections"]:
            return
        i = self.cur_sec()
        s = self.item["sections"][i]
        for k, var in self.sv.items():
            if isinstance(var, tk.BooleanVar):
                s[k] = bool(var.get())
            else:
                try:
                    val = float(var.get().replace(",", "."))
                except ValueError:
                    continue
                s[k] = int(val) if k not in ("width", "drawer_h", "door_h") else val
        self.sec_tv.item(str(i), values=(f"{s.get('width') or 'авто'}", s.get("doors", 0), s.get("shelves", 0),
                                         s.get("drawers", 0), s.get("drawer_h", 0) or "цяла", s.get("rail", 0)))
        self.schedule_update()

    def schedule_update(self):
        if self._after:
            self.after_cancel(self._after)
        self._after = self.after(250, self.update_design)

    def update_design(self):
        self._after = None
        it = self.item
        if it is None:
            return
        try:
            self.res = build(it, self.cat)
        except Exception as e:  # noqa
            self.res = None
            self.msg.delete("1.0", "end")
            self.msg.insert("end", f"Грешка: {e}", "warn")
            return
        self.comp = None
        name = f"{it['name']}  ({it['W']:g}×{it['H']:g}×{it['D']:g})"
        if self.lst.size() > self.cur and self.lst.get(self.cur) != name:
            self.lst.delete(self.cur)
            self.lst.insert(self.cur, name)
            self.lst.selection_set(self.cur)
        self.msg.delete("1.0", "end")
        for w in self.res.warnings:
            self.msg.insert("end", "⚠ " + w + "\n", "warn")
        for i in self.res.info:
            self.msg.insert("end", "• " + i + "\n", "info")
        _, tips = ideas(it["type"], it["W"], it["H"], it["D"])
        for t in tips:
            self.msg.insert("end", "💡 " + t + "\n", "tip")
        n = sum(p.qty for p in self.res.parts)
        self.dim_lbl.config(text=f"{n} детайла, {len(self.res.hardware)} вида обков")
        self.draw_preview()
        self.update_3d()

    def update_3d(self):
        if getattr(self, "res", None) is not None and self.item is not None:
            self.v3d.set_model(self.item, self.res, self.cat)

    def decor_colors(self):
        it = self.item
        c = self.cat
        M = {m["key"]: m for m in c["materials"]}
        cd = decor_mod.get(c.get("decors", []), it.get("carcass_decor") or decor_mod.default_for_material(M.get(it.get("carcass_mat"))))
        fd = decor_mod.get(c.get("decors", []), it.get("front_decor") or decor_mod.default_for_material(M.get(it.get("front_mat"))))
        return cd["color"], fd["color"]

    def update_swatches(self):
        if self.item is None:
            return
        cc, fc = self.decor_colors()
        self.sw_c.config(bg=cc)
        self.sw_f.config(bg=fc)

    def cmd_decors(self):
        dlg = DecorDialog(self)
        self.wait_window(dlg)
        self.refresh_combos()
        self.load_item()

    def draw_preview(self):
        cv = self.prev
        cv.delete("all")
        it = self.item
        res = getattr(self, "res", None)
        if not it or not res:
            return
        cw, ch = cv.winfo_width(), cv.winfo_height()
        if cw < 50:
            return
        W, H = float(it["W"]), float(it["H"])
        s = min((cw - 80) / W, (ch - 70) / H)
        ox, oy = (cw - W * s) / 2, ch - 40

        def R(x, y, w, h, **kw):
            return cv.create_rectangle(ox + x * s, oy - (y + h) * s, ox + (x + w) * s, oy - y * s, **kw)
        cv.create_line(10, oy, cw - 10, oy, fill="#999")
        fronts = self.show_fronts.get()
        ccol, fcol = self.decor_colors()
        R(0, 0, W, H, outline="#bbb", dash=(2, 2))
        for k, x, y, w, h, lab in res.shapes:
            if k in CARC_COL:
                R(x, y, w, h, fill=(ccol if k in ("side", "panel", "divider", "plinth") else CARC_COL[k]), outline="#555")
            elif k == "rail":
                cv.create_line(ox + x * s, oy - y * s, ox + (x + w) * s, oy - y * s, width=3, fill="#666")
            elif k == "legs":
                for lx in (30, W - 60):
                    R(lx, 0, 30, h, fill="#666", outline="")
        if fronts:
            for k, x, y, w, h, lab in res.shapes:
                if k in FRONT_COL:
                    R(x, y, w, h, fill=fcol, outline="#6b4f2f", width=1)
                    if k == "door":
                        hx = x if lab == "L" else x + w
                        ox2 = x + w if lab == "L" else x
                        cv.create_line(ox + ox2 * s, oy - y * s, ox + hx * s, oy - (y + h / 2) * s, ox + ox2 * s, oy - (y + h) * s, dash=(4, 3), fill="#7a6040")
                        hx2 = x + w - 40 if lab == "L" else x + 40
                        cv.create_line(ox + hx2 * s, oy - (y + h / 2 - 60) * s, ox + hx2 * s, oy - (y + h / 2 + 60) * s, width=3, fill=("#dddddd" if sum(int(fcol[i:i + 2], 16) for i in (1, 3, 5)) < 300 else "#444"))
                    elif k == "drawer":
                        cv.create_line(ox + (x + w / 2 - 60) * s, oy - (y + h - 35) * s, ox + (x + w / 2 + 60) * s, oy - (y + h - 35) * s, width=3, fill=("#dddddd" if sum(int(fcol[i:i + 2], 16) for i in (1, 3, 5)) < 300 else "#444"))
                    elif k == "lift":
                        cv.create_text(ox + (x + w / 2) * s, oy - (y + h / 2) * s, text="↑ клапа", fill="#555")
        # коти
        cv.create_line(ox, oy + 18, ox + W * s, oy + 18, arrow="both", fill="#0060a0")
        cv.create_text(ox + W * s / 2, oy + 28, text=f"{W:g}", fill="#0060a0")
        cv.create_line(ox - 18, oy, ox - 18, oy - H * s, arrow="both", fill="#0060a0")
        cv.create_text(ox - 30, oy - H * s / 2, text=f"{H:g}", fill="#0060a0", angle=90)
        cv.create_text(cw - 10, 12, text=f"Дълбочина {it['D']:g} мм", anchor="e", fill="#0060a0")

    def on_select_item(self, e=None):
        sel = self.lst.curselection()
        if sel and sel[0] != self.cur:
            self.cur = sel[0]
            self.load_item()

    def on_sec_sel(self, e=None):
        if self.sec_tv.selection():
            self.load_sec(self.cur_sec())

    def on_tab(self, e=None):
        txt = self.nb.tab(self.nb.select(), "text").strip()
        if txt.startswith("Детайли"):
            self.recompute(optimize=self.comp is None or not self.comp.cuts)
        elif txt.startswith("Разкрой"):
            self.load_settings()
        elif txt.startswith("3D"):
            self.update_3d()

    # ------------------------------------------------------------ items
    def add_item(self):
        tkey = next((k for k, v in FURNITURE_TYPES.items() if v == self.new_type.get()), "custom")
        it = default_item(tkey)
        names = {i["name"] for i in self.project["items"]}
        base, k = it["name"], 1
        while it["name"] in names:
            k += 1
            it["name"] = f"{base} {k}"
        self.project["items"].append(it)
        self.cur = len(self.project["items"]) - 1
        self.comp = None
        self.refresh_list()
        self.load_item()

    def dup_item(self):
        if self.item is None:
            return
        it = copy.deepcopy(self.item)
        it["name"] += " (копие)"
        self.project["items"].insert(self.cur + 1, it)
        self.cur += 1
        self.refresh_list()
        self.load_item()

    def del_item(self):
        if self.item is None or not messagebox.askyesno("Изтриване", f"Да изтрия ли „{self.item['name']}“?"):
            return
        del self.project["items"][self.cur]
        if not self.project["items"]:
            self.project["items"].append(default_item("custom"))
        self.cur = max(0, self.cur - 1)
        self.comp = None
        self.refresh_list()
        self.load_item()

    def add_sec(self):
        self.item["sections"].append(new_section())
        self.refresh_secs(len(self.item["sections"]) - 1)
        self.schedule_update()

    def del_sec(self):
        if len(self.item["sections"]) <= 1:
            return
        i = self.cur_sec()
        del self.item["sections"][i]
        self.refresh_secs(max(0, i - 1))
        self.schedule_update()

    def move_sec(self, d):
        i = self.cur_sec()
        j = i + d
        secs = self.item["sections"]
        if 0 <= j < len(secs):
            secs[i], secs[j] = secs[j], secs[i]
            self.refresh_secs(j)
            self.schedule_update()

    # ------------------------------------------------------------ ideas
    def show_ideas(self):
        it = self.item
        self._ideas, tips = ideas(it["type"], it["W"], it["H"], it["D"])
        self.ideas_lb.delete(0, "end")
        for title, desc, _ in self._ideas:
            self.ideas_lb.insert("end", title)
        if self._ideas:
            self.ideas_lb.selection_set(0)
            self.on_idea_sel()

    def on_idea_sel(self, e=None):
        sel = self.ideas_lb.curselection()
        if sel and getattr(self, "_ideas", None):
            self.idea_desc.config(text=self._ideas[sel[0]][1])

    def apply_idea(self):
        sel = self.ideas_lb.curselection()
        if not sel or not getattr(self, "_ideas", None):
            messagebox.showinfo("Идеи", "Първо натиснете „Дай ми идеи“ и изберете вариант.")
            return
        _, _, ov = self._ideas[sel[0]]
        self.item.update(copy.deepcopy(ov))
        self.load_item(keep_ideas=True)
        self.ideas_lb.selection_set(sel[0])
        self.on_idea_sel()
        self.status.set("Приложена идея: " + self._ideas[sel[0]][0])

    # ------------------------------------------------------------ compute
    def read_settings(self):
        st = self.project["settings"]
        for k, var in self.cut_v.items():
            try:
                st[k] = float(var.get().replace(",", "."))
            except ValueError:
                pass
        st["iterations"] = int(st.get("iterations", 300))
        st["reduce_band"] = bool(self.reduce_band.get())

    def load_settings(self):
        st = self.project["settings"]
        for k, var in self.cut_v.items():
            var.set(f"{st.get(k, 0):g}")
        self.reduce_band.set(st.get("reduce_band", True))

    def recompute(self, optimize=True):
        self.read_settings()
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            self.comp = compute(self.project, optimize=optimize)
        finally:
            self.config(cursor="")
        self.fill_parts()
        self.status.set("Изчислено.")

    def fill_parts(self):
        comp = self.comp
        cat = self.cat
        M = {m["key"]: m for m in cat["materials"]}
        self.parts_tv.delete(*self.parts_tv.get_children())
        for i, p in enumerate(comp.parts, 1):
            cl, cw = p.cut_size(cat["bands"], self.project["settings"]["reduce_band"])
            self.parts_tv.insert("", "end", values=(i, p.module, p.name, M[p.material]["name"], f"{p.length:g}", f"{p.width:g}",
                                                    p.qty, edges_str(p), f"{cl:g}×{cw:g}"))
        self.hw_tv.delete(*self.hw_tv.get_children())
        for h in comp.hardware:
            self.hw_tv.insert("", "end", values=(h.name, f"{h.qty:g}", h.unit, f"{h.qty * h.price:.2f}"))
        self.cost_tv.delete(*self.cost_tv.get_children())
        for name, q, c in comp.costs["_lines"]:
            self.cost_tv.insert("", "end", values=(name, q, f"{c:.2f}"))
        for k, v in comp.costs.items():
            if not k.startswith("_"):
                self.cost_tv.insert("", "end", values=(k, "", f"{v:.2f}"), tags=("tot",) if k == "ОБЩО" else ())
        if not comp.cuts:
            self.cost_tv.insert("", "end", values=("(плочите – след оптимизация на разкроя)", "", ""))
        self.cost_lbl.config(text=f"Общо ориентировъчно: {comp.costs['ОБЩО']:.2f} €")

    def run_opt(self):
        self.recompute(optimize=True)
        M = {m["key"]: m for m in self.cat["materials"]}
        names = [M[k]["name"] for k in self.comp.cuts]
        self.cut_mat_cb["values"] = names
        if names:
            self.cut_mat.set(names[0])
        self.sheet_idx = 0
        lines = []
        for mk, cr in self.comp.cuts.items():
            lines.append(f"{M[mk]['name']}: {cr.n_sheets} плочи, използване {cr.utilization() * 100:.1f}%, рез ≈ {cr.cut_length_m():.1f} м"
                         + (f", НЕ СЕ ПОБИРАТ: {len(cr.unplaced)}" if cr.unplaced else ""))
        self.cut_sum.config(text="\n".join(lines))
        self.draw_sheet()

    def nav_sheet(self, d):
        cr = self.cur_cut()
        if cr:
            self.sheet_idx = max(0, min(cr.n_sheets - 1, self.sheet_idx + d))
            self.draw_sheet()

    def cur_cut(self):
        if not self.comp or not self.comp.cuts:
            return None
        key = self.key_by_name(self.cat["materials"], self.cut_mat.get())
        return self.comp.cuts.get(key)

    def draw_sheet(self):
        cv = self.sheet_cv
        cv.delete("all")
        cr = self.cur_cut()
        if not cr or not cr.sheets:
            return
        sh = cr.sheets[min(self.sheet_idx, cr.n_sheets - 1)]
        cw, ch = cv.winfo_width(), cv.winfo_height()
        s = min((cw - 40) / cr.sheet_l, (ch - 40) / cr.sheet_w)
        ox, oy = 20, 20 + cr.sheet_w * s

        def R(x, y, w, h, **kw):
            cv.create_rectangle(ox + x * s, oy - (y + h) * s, ox + (x + w) * s, oy - y * s, **kw)
        R(0, 0, cr.sheet_l, cr.sheet_w, fill="#e9e9e9", outline="#333", width=2)
        R(cr.trim, cr.trim, cr.sheet_l - 2 * cr.trim, cr.sheet_w - 2 * cr.trim, outline="#aaa", dash=(2, 3))
        for p in sh.placed:
            R(p.x, p.y, p.dx, p.dy, fill="#e8c9a0", outline="#6b4f2f")
            cx, cy = ox + (p.x + p.dx / 2) * s, oy - (p.y + p.dy / 2) * s
            fs = int(max(7, min(11, p.dy * s / 3)))
            cv.create_text(cx, cy - fs * 0.6, text=f"№{p.piece.label}", font=("Segoe UI", fs, "bold"))
            if p.dy * s > 2.2 * fs:
                cv.create_text(cx, cy + fs * 0.7, text=f"{p.dx:g}×{p.dy:g}" + (" ↻" if p.rotated else ""), font=("Segoe UI", max(7, fs - 1)))
        used = sh.used_area() / (cr.sheet_l * cr.sheet_w) * 100
        M = {m["key"]: m for m in self.cat["materials"]}
        g = "фладер →" if M[cr.material_key]["grain"] else "без фладер"
        self.cut_stat.config(text=f"Плоча {self.sheet_idx + 1} от {cr.n_sheets} | {len(sh.placed)} детайла | използване {used:.1f}% | {g}")

    # ------------------------------------------------------------ materials
    def refresh_materials(self):
        self.mat_tv.delete(*self.mat_tv.get_children())
        for m in self.cat["materials"]:
            self.mat_tv.insert("", "end", iid=m["key"], values=(m["name"], m["kind"], f"{m['t']:g}", m["sheet_l"], m["sheet_w"],
                                                              "да" if m["grain"] else "не", f"{m['price']:.2f}"))
        self.price_tv.delete(*self.price_tv.get_children())
        for grp, lst in (("Кант €/м", "bands"), ("Панта €/бр", "hinges"), ("Водачи €/чифт", "slides")):
            for x in self.cat[lst]:
                if x["key"] == "none":
                    continue
                self.price_tv.insert("", "end", iid=f"{lst}|{x['key']}", values=(grp, x["name"], f"{x['price']:.2f}"))
        for k, v in self.cat["hardware_prices"].items():
            self.price_tv.insert("", "end", iid=f"hw|{k}", values=("Обков", k, f"{v:.2f}"))

    def edit_mat(self, new=False):
        if new:
            m = {"key": "", "name": "Нов материал", "kind": "ПДЧ", "t": 18, "sheet_l": 2800, "sheet_w": 2070, "grain": False, "price": 50.0}
        else:
            sel = self.mat_tv.selection()
            if not sel:
                return
            m = find(self.cat["materials"], sel[0])
        dlg = MatDialog(self, m)
        self.wait_window(dlg)
        if not dlg.result:
            return
        r = dlg.result
        if new:
            base = f"{r['kind']}{r['t']:g}".lower()
            k, n = base, 1
            keys = {x["key"] for x in self.cat["materials"]}
            while k in keys:
                n += 1
                k = f"{base}_{n}"
            r["key"] = k
            self.cat["materials"].append(r)
        else:
            m.update(r)
        self.refresh_materials()
        self.refresh_combos()
        self.load_item()

    def del_mat(self):
        sel = self.mat_tv.selection()
        if not sel:
            return
        key = sel[0]
        used = [it["name"] for it in self.project["items"] if key in (it.get("carcass_mat"), it.get("front_mat"), it.get("back_mat"), it.get("drawer_mat"), it.get("drawer_bottom_mat"))]
        if used:
            messagebox.showwarning("Материал", "Материалът се използва в: " + ", ".join(used))
            return
        self.cat["materials"] = [m for m in self.cat["materials"] if m["key"] != key]
        self.refresh_materials()
        self.refresh_combos()

    def edit_price(self):
        sel = self.price_tv.selection()
        if not sel:
            return
        grp, key = sel[0].split("|", 1)
        if grp == "hw":
            cur = self.cat["hardware_prices"][key]
        else:
            cur = find(self.cat[grp], key)["price"]
        v = simpledialog.askfloat("Цена", "Нова цена (€):", initialvalue=cur, minvalue=0, parent=self)
        if v is None:
            return
        if grp == "hw":
            self.cat["hardware_prices"][key] = v
        else:
            find(self.cat[grp], key)["price"] = v
        self.refresh_materials()
        self.comp = None
        self.update_design()

    # ------------------------------------------------------------ photo
    def cmd_photo(self):
        PhotoDialog(self)

    def cmd_api_key(self, parent=None):
        dlg = ApiKeyDialog(parent or self)
        self.wait_window(dlg)
        if dlg.saved:
            self.status.set(f"Настройките за разпознаване са запазени ({photo.PROVIDERS[photo.provider()]}).")

    def add_from_photo(self, res, known):
        it = photo.result_to_item(res, self.cat, known)
        self.project["items"].append(it)
        self.cur = len(self.project["items"]) - 1
        self.comp = None
        self.refresh_list()
        self.load_item()
        self.nb.select(0)
        self.msg.insert("1.0", "", "tip")
        lines = ["📷 От снимката: " + res.get("description", "")]
        if res.get("fronts_finish") or res.get("carcass_finish"):
            lines.append(f"🎨 Фронтове: {res.get('fronts_finish', '')}; корпус: {res.get('carcass_finish', '')} – изберете декор в „Материали“.")
        for a in res.get("advice", []):
            lines.append("💡 " + a)
        if not res.get("is_furniture", True):
            lines.insert(0, "⚠ На снимката не беше разпозната корпусна мебел – предложен е най-близкият вариант.")
        self.msg.insert("1.0", "\n".join(lines) + "\n", "tip")
        self.status.set(f"Създадена мебел от снимка: {it['name']} – проверете размерите и секциите.")

    # ------------------------------------------------------------ files
    def cmd_new(self):
        if messagebox.askyesno("Нов проект", "Да започна ли нов проект? Незапазените промени ще се загубят."):
            self.project = new_project()
            self.path = None
            self.cur = 0
            self.comp = None
            self.refresh_all()

    def cmd_open(self):
        p = filedialog.askopenfilename(filetypes=[("Мебел проект", "*.mebel.json *.json"), ("Всички", "*.*")])
        if not p:
            return
        try:
            self.project = load(p)
        except Exception as e:  # noqa
            messagebox.showerror("Грешка", f"Не може да се отвори файлът:\n{e}")
            return
        self.path = p
        self.cur = 0
        self.comp = None
        self.refresh_all()
        self.status.set(f"Отворен: {p}")

    def cmd_save(self, as_=False):
        self.read_settings()
        if as_ or not self.path:
            p = filedialog.asksaveasfilename(defaultextension=".mebel.json", filetypes=[("Мебел проект", "*.mebel.json")])
            if not p:
                return
            self.path = p
        save(self.project, self.path)
        self.status.set(f"Запазен: {self.path}")

    def ensure_comp(self):
        if self.comp is None or not self.comp.cuts:
            self.recompute(optimize=True)
        return self.comp

    def cmd_pdf(self):
        p = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not p:
            return
        try:
            export_pdf(self.ensure_comp(), self.project, p)
        except Exception as e:  # noqa
            messagebox.showerror("Грешка", f"PDF не може да се създаде:\n{e}")
            return
        self.status.set(f"PDF: {p}")
        if os.name == "nt":
            os.startfile(p)  # noqa

    def cmd_csv(self):
        p = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV (Excel)", "*.csv")])
        if p:
            export_parts_csv(self.ensure_comp(), self.project, p)
            self.status.set(f"CSV: {p}")

    def cmd_quote(self):
        QuoteDialog(self)

    def cmd_hw_csv(self):
        p = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV (Excel)", "*.csv")])
        if p:
            export_hardware_csv(self.ensure_comp(), p)
            self.status.set(f"CSV: {p}")


class PhotoDialog(tk.Toplevel):
    """Избор на снимка + известни размери; анализът тече във фонова нишка."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Мебел от снимка")
        self.transient(app)
        self.grab_set()
        self.resizable(False, False)
        self.path = None
        self._img = None
        pad = {"padx": 8, "pady": 3}
        ttk.Label(self, text="1. Изберете снимка на мебел (JPG, PNG, WEBP):", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", **pad)
        ttk.Button(self, text="Избери снимка…", command=self.pick).grid(row=1, column=0, sticky="w", **pad)
        self.file_lbl = ttk.Label(self, text="(няма избрана)", foreground="#555", wraplength=330)
        self.file_lbl.grid(row=1, column=1, columnspan=2, sticky="w", **pad)
        self.thumb = ttk.Label(self)
        self.thumb.grid(row=2, column=0, columnspan=3, **pad)
        ttk.Label(self, text="2. Ако знаете размерите, въведете ги (мм, празно = прецени от снимката):",
                  font=("Segoe UI", 10, "bold")).grid(row=3, column=0, columnspan=3, sticky="w", **pad)
        self.dims = {}
        for i, (k, lbl) in enumerate((("W", "Широчина"), ("H", "Височина"), ("D", "Дълбочина"))):
            ttk.Label(self, text=lbl).grid(row=4 + i, column=0, sticky="w", **pad)
            v = tk.StringVar()
            ttk.Entry(self, textvariable=v, width=12).grid(row=4 + i, column=1, sticky="w", **pad)
            self.dims[k] = v
        self.status = ttk.Label(self, text="", foreground="#005a9e", wraplength=420)
        self.status.grid(row=7, column=0, columnspan=3, sticky="w", **pad)
        self.pb = ttk.Progressbar(self, mode="indeterminate", length=420)
        self.pb.grid(row=8, column=0, columnspan=3, **pad)
        bf = ttk.Frame(self)
        bf.grid(row=9, column=0, columnspan=3, pady=8)
        self.go_btn = ttk.Button(bf, text="3. Анализирай и създай дизайн", command=self.go)
        self.go_btn.pack(side="left", padx=4)
        ttk.Button(bf, text="Затвори", command=self.destroy).pack(side="left", padx=4)

    def pick(self):
        p = filedialog.askopenfilename(parent=self, filetypes=[("Снимки", "*.jpg *.jpeg *.png *.webp *.gif"), ("Всички", "*.*")])
        if not p:
            return
        self.path = p
        self.file_lbl.config(text=os.path.basename(p))
        try:
            from PIL import Image, ImageTk
            im = Image.open(p)
            im.thumbnail((420, 300))
            self._img = ImageTk.PhotoImage(im)
            self.thumb.config(image=self._img)
        except Exception:  # noqa – прегледът не е задължителен
            self.thumb.config(image="", text="(преглед не е наличен)")

    def known(self):
        out = {}
        for k, v in self.dims.items():
            try:
                x = float(v.get().replace(",", "."))
                if x > 0:
                    out[k] = x
            except ValueError:
                pass
        return out

    def go(self):
        if not self.path:
            messagebox.showinfo("Снимка", "Първо изберете снимка.", parent=self)
            return
        key = photo.load_api_key()
        if not key:
            self.app.cmd_api_key(parent=self)
            key = photo.load_api_key()
            if not key:
                return
        known = self.known()
        self.go_btn.config(state="disabled")
        self.status.config(text=f"Анализирам снимката с {photo.PROVIDERS[photo.provider()]}… (обикновено 10-60 секунди)")
        self.pb.start(12)
        import threading
        out = {}

        def work():
            try:
                out["res"] = photo.analyze_photo(self.path, key, known)
            except photo.PhotoError as e:
                out["err"] = str(e)
            except Exception as e:  # noqa
                out["err"] = f"Неочаквана грешка: {e}"

        th = threading.Thread(target=work, daemon=True)
        th.start()

        def poll():
            if th.is_alive():
                self.after(300, poll)
                return
            if not self.winfo_exists():
                return
            self.pb.stop()
            self.go_btn.config(state="normal")
            if "err" in out:
                self.status.config(text="")
                messagebox.showerror("Грешка", out["err"], parent=self)
                return
            self.app.add_from_photo(out["res"], known)
            self.destroy()
        self.after(300, poll)


class DecorDialog(tk.Toplevel):
    """Библиотека с декори: преглед, добавяне (цвят / снимка / линк), изтриване."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Библиотека с декори")
        self.transient(app)
        self.grab_set()
        self.geometry("760x560")
        top = ttk.Frame(self, padding=6)
        top.pack(fill="x")
        ttk.Label(top, text="Цветовете са ориентировъчни – потвърждавайте по мостра. Двоен клик = смяна на цвета.",
                  foreground="#555").pack(side="left")
        cols = ("sw", "code", "name", "kind", "sup")
        self.tv = ttk.Treeview(self, columns=cols, show="headings")
        for c_, h_, w_ in zip(cols, ("Цвят", "Код", "Име", "Вид", "Доставчик"), (60, 120, 300, 100, 110)):
            self.tv.heading(c_, text=h_)
            self.tv.column(c_, width=w_, anchor="w")
        self.tv.pack(fill="both", expand=True, padx=6)
        self.tv.bind("<Double-Button-1>", lambda e: self.recolor())
        bf = ttk.Frame(self, padding=6)
        bf.pack(fill="x")
        ttk.Button(bf, text="+ Нов (избор на цвят)", command=self.add_color).pack(side="left")
        ttk.Button(bf, text="+ От снимка на мостра…", command=self.add_file).pack(side="left", padx=4)
        ttk.Button(bf, text="+ От линк към снимка…", command=self.add_url).pack(side="left")
        ttk.Button(bf, text="Изтрий", command=self.delete).pack(side="left", padx=4)
        ttk.Button(bf, text="Затвори", command=self.destroy).pack(side="right")
        self.fill()

    @property
    def decs(self):
        return self.app.cat.setdefault("decors", decor_mod.default_decors())

    def fill(self):
        self.tv.delete(*self.tv.get_children())
        for d in self.decs:
            tag = "c" + d["color"].lstrip("#")
            self.tv.tag_configure(tag, background=d["color"],
                                  foreground="#ffffff" if sum(int(d["color"][i:i + 2], 16) for i in (1, 3, 5)) < 330 else "#000000")
            self.tv.insert("", "end", iid=d["key"], values=("", d["key"], d["name"], decor_mod.KIND_NAMES.get(d["kind"], d["kind"]),
                                                             d.get("supplier", "")), tags=(tag,))

    def _ask_meta(self, kind_guess="uni"):
        code = simpledialog.askstring("Нов декор", "Код на декора (напр. K006 PW):", parent=self)
        if not code:
            return None
        if any(d["key"] == code.strip() for d in self.decs):
            messagebox.showwarning("Декор", "Вече има декор с този код.", parent=self)
            return None
        name = simpledialog.askstring("Нов декор", "Име (напр. Дъб ърбън амбър):", parent=self) or code
        wood = messagebox.askyesno("Нов декор", "Дървесен декор (с шарка/фладер)?", default="yes" if kind_guess == "wood" else "no", parent=self)
        sup = simpledialog.askstring("Нов декор", "Доставчик/марка (по желание):", parent=self) or ""
        return {"key": code.strip(), "name": name.strip(), "kind": "wood" if wood else "uni", "supplier": sup.strip(), "image": ""}

    def add_color(self):
        from tkinter import colorchooser
        col = colorchooser.askcolor(parent=self, title="Цвят на декора")[1]
        if not col:
            return
        d = self._ask_meta()
        if d:
            d["color"] = col
            self.decs.append(d)
            self.fill()

    def _add_from_bytes(self, raw):
        try:
            col, kind = decor_mod.analyze_image_bytes(raw)
        except Exception as e:  # noqa
            messagebox.showerror("Декор", f"Снимката не може да се прочете:\n{e}", parent=self)
            return
        d = self._ask_meta(kind)
        if not d:
            return
        d["color"] = col
        try:
            d["image"] = decor_mod.save_image(raw, d["key"])
        except Exception:  # noqa
            d["image"] = ""
        self.decs.append(d)
        self.fill()
        self.tv.selection_set(d["key"])
        self.tv.see(d["key"])

    def add_file(self):
        p = filedialog.askopenfilename(parent=self, filetypes=[("Снимки", "*.jpg *.jpeg *.png *.webp"), ("Всички", "*.*")])
        if p:
            with open(p, "rb") as fh:
                self._add_from_bytes(fh.read())

    def add_url(self):
        url = simpledialog.askstring("От линк", "Поставете линк към снимката на декора\n(десен бутон върху снимката в каталога → „Копиране на адреса на изображението“):", parent=self)
        if not url:
            return
        try:
            raw = decor_mod.download(url.strip())
        except Exception as e:  # noqa
            messagebox.showerror("Декор", f"Не мога да изтегля снимката:\n{e}", parent=self)
            return
        self._add_from_bytes(raw)

    def recolor(self):
        from tkinter import colorchooser
        sel = self.tv.selection()
        if not sel:
            return
        d = decor_mod.get(self.decs, sel[0])
        col = colorchooser.askcolor(color=d["color"], parent=self, title=decor_mod.label(d))[1]
        if col:
            d["color"] = col
            self.fill()

    def delete(self):
        sel = self.tv.selection()
        if not sel:
            return
        key = sel[0]
        used = [it["name"] for it in self.app.project["items"] if key in (it.get("carcass_decor"), it.get("front_decor"))]
        if used:
            messagebox.showwarning("Декор", "Декорът се използва в: " + ", ".join(used), parent=self)
            return
        self.app.cat["decors"] = [d for d in self.decs if d["key"] != key]
        self.fill()


class ApiKeyDialog(tk.Toplevel):
    """Избор на доставчик (Claude или Grok) + API ключ + модел за Grok."""

    def __init__(self, master):
        super().__init__(master)
        self.title("Разпознаване на снимки – доставчик и API ключ")
        self.transient(master)
        self.grab_set()
        self.saved = False
        cfg = photo.load_config()
        self.prov = tk.StringVar(value=cfg.get("provider", "claude"))
        pad = {"padx": 8, "pady": 3}
        ttk.Label(self, text="Доставчик на изкуствен интелект:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", **pad)
        r = 1
        for k, name in photo.PROVIDERS.items():
            ttk.Radiobutton(self, text=name, value=k, variable=self.prov, command=self.sync).grid(row=r, column=0, columnspan=2, sticky="w", padx=20)
            r += 1
        self.hint = ttk.Label(self, text="", foreground="#555", wraplength=420, justify="left")
        self.hint.grid(row=r, column=0, columnspan=2, sticky="w", **pad)
        r += 1
        ttk.Label(self, text="API ключ:").grid(row=r, column=0, sticky="w", **pad)
        self.key = tk.StringVar()
        ttk.Entry(self, textvariable=self.key, width=48, show="•").grid(row=r, column=1, sticky="we", **pad)
        r += 1
        self.cur_lbl = ttk.Label(self, text="", foreground="#555")
        self.cur_lbl.grid(row=r, column=1, sticky="w", padx=8)
        r += 1
        self.model_lbl = ttk.Label(self, text="Модел (Grok):")
        self.model_lbl.grid(row=r, column=0, sticky="w", **pad)
        self.model = tk.StringVar(value=cfg.get("grok_model") or photo.GROK_DEFAULT_MODEL)
        self.model_e = ttk.Entry(self, textvariable=self.model, width=48)
        self.model_e.grid(row=r, column=1, sticky="we", **pad)
        r += 1
        bf = ttk.Frame(self)
        bf.grid(row=r, column=0, columnspan=2, pady=8)
        ttk.Button(bf, text="Запази", command=self.ok).pack(side="left", padx=4)
        ttk.Button(bf, text="Отказ", command=self.destroy).pack(side="left", padx=4)
        self.sync()

    def sync(self):
        p = self.prov.get()
        cur = photo.load_api_key(p)
        self.cur_lbl.config(text=f"Запазен: {cur[:8] + '…' if cur else 'няма'} (оставете празно, за да го запазите)")
        if p == "grok":
            self.hint.config(text="Ключ от console.x.ai → API Keys. Моделът трябва да разпознава изображения (напр. grok-4). Ако xAI пусне нов модел, сменете името тук.")
            self.model_e.config(state="normal")
        else:
            self.hint.config(text="Ключ от platform.claude.com → API Keys.")
            self.model_e.config(state="disabled")

    def ok(self):
        p = self.prov.get()
        kw = {"provider": p}
        if p == "grok":
            kw["grok_model"] = self.model.get().strip() or photo.GROK_DEFAULT_MODEL
        photo.save_config(**kw)
        if self.key.get().strip():
            photo.save_api_key(self.key.get(), p)
        if not photo.load_api_key(p):
            messagebox.showwarning("API ключ", "Не е въведен ключ за избрания доставчик.", parent=self)
            return
        self.saved = True
        self.destroy()


class QuoteDialog(tk.Toplevel):
    """Данни за офертата; запазват се в проекта (фирмата и цените – за следващия път)."""
    FIELDS = [
        ("Фирма", [("company", "Име на фирмата"), ("company_phone", "Телефон"), ("company_email", "Имейл"), ("company_address", "Адрес")]),
        ("Клиент", [("customer", "Име"), ("customer_phone", "Телефон"), ("customer_address", "Адрес")]),
        ("Цена", [("markup_pct", "Надценка върху материали и обков, %"), ("labor_per_item", "Труд (изработка) на мебел, €"),
                  ("transport", "Транспорт, €"), ("montage", "Монтаж, €"), ("discount_pct", "Отстъпка, %"),
                  ("vat_pct", "ДДС, %"), ("advance_pct", "Аванс, %")]),
        ("Условия", [("number", "№ на офертата"), ("validity_days", "Валидност, дни"), ("lead_days", "Срок за изработка, раб. дни")]),
    ]
    NUM = {"markup_pct", "labor_per_item", "transport", "montage", "discount_pct", "vat_pct", "advance_pct", "number", "validity_days", "lead_days"}

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Оферта за клиент")
        self.transient(app)
        self.grab_set()
        self.q = quote_mod.quote_settings(app.project)
        self.vars = {}
        r = 0
        for grp, fields in self.FIELDS:
            ttk.Label(self, text=grp, font=("Segoe UI", 10, "bold")).grid(row=r, column=0, sticky="w", padx=8, pady=(8, 2))
            r += 1
            for k, lbl in fields:
                ttk.Label(self, text=lbl).grid(row=r, column=0, sticky="w", padx=8, pady=1)
                v = tk.StringVar(value=f"{self.q[k]:g}" if k in self.NUM else str(self.q[k]))
                ttk.Entry(self, textvariable=v, width=40).grid(row=r, column=1, sticky="we", padx=8, pady=1)
                v.trace_add("write", lambda *a: self.preview())
                self.vars[k] = v
                r += 1
        self.vat = tk.BooleanVar(value=bool(self.q["vat"]))
        ttk.Checkbutton(self, text="Начисли ДДС (фирмата е регистрирана по ДДС)", variable=self.vat, command=self.preview).grid(row=r, column=0, columnspan=2, sticky="w", padx=8)
        r += 1
        ttk.Label(self, text="Бележки / условия (по ред на точка)").grid(row=r, column=0, sticky="nw", padx=8, pady=4)
        self.notes = tk.Text(self, width=40, height=4, wrap="word")
        self.notes.insert("1.0", self.q["notes"])
        self.notes.grid(row=r, column=1, sticky="we", padx=8, pady=4)
        r += 1
        self.prev_lbl = ttk.Label(self, text="", justify="left", foreground="#1d4f7a")
        self.prev_lbl.grid(row=r, column=0, columnspan=2, sticky="w", padx=8, pady=6)
        r += 1
        bf = ttk.Frame(self)
        bf.grid(row=r, column=0, columnspan=2, pady=8)
        ttk.Button(bf, text="Създай PDF оферта…", command=self.make).pack(side="left", padx=4)
        ttk.Button(bf, text="Затвори", command=self.destroy).pack(side="left", padx=4)
        self.comp = self.app.ensure_comp()
        self.costs = quote_mod.item_costs(self.comp, self.app.project)
        self.preview()

    def collect(self):
        q = dict(self.q)
        for k, v in self.vars.items():
            if k in self.NUM:
                try:
                    q[k] = float(v.get().replace(",", ".")) if k not in ("number", "validity_days", "lead_days") else int(float(v.get()))
                except ValueError:
                    pass
            else:
                q[k] = v.get().strip()
        q["vat"] = bool(self.vat.get())
        q["notes"] = self.notes.get("1.0", "end").strip()
        return q

    def preview(self):
        if not hasattr(self, "costs"):
            return
        q = self.collect()
        lines = []
        for cst in self.costs:
            lines.append(f"{cst['name']}: себестойност {cst['total']:.2f} € → цена {quote_mod.item_price(cst, q):.2f} €")
        self.prev_lbl.config(text="\n".join(lines))

    def make(self):
        q = self.collect()
        self.app.project["quote"] = q
        name = f"Оферта_{q['number']}" + (f"_{q['customer'].split()[0]}" if q["customer"] else "") + ".pdf"
        p = filedialog.asksaveasfilename(parent=self, defaultextension=".pdf", initialfile=name, filetypes=[("PDF", "*.pdf")])
        if not p:
            return
        try:
            total = quote_mod.export_quote_pdf(self.app.project, p, self.comp)
        except Exception as e:  # noqa
            messagebox.showerror("Грешка", f"Офертата не може да се създаде:\n{e}", parent=self)
            return
        self.app.project["quote"]["number"] = int(q["number"]) + 1
        self.app.status.set(f"Оферта №{q['number']}: {total:.2f} € → {p}")
        if os.name == "nt":
            os.startfile(p)  # noqa
        self.destroy()


class MatDialog(tk.Toplevel):
    def __init__(self, master, m):
        super().__init__(master)
        self.title("Материал")
        self.transient(master)
        self.grab_set()
        self.result = None
        self.vars = {}
        fields = [("Име", "name"), ("Вид (ПДЧ/МДФ/ХДФ/Шперплат)", "kind"), ("Дебелина мм", "t"),
                  ("Дължина на плочата (по фладера) мм", "sheet_l"), ("Ширина на плочата мм", "sheet_w"), ("Цена за плоча €", "price")]
        for r, (lbl, k) in enumerate(fields):
            ttk.Label(self, text=lbl).grid(row=r, column=0, sticky="w", padx=6, pady=3)
            var = tk.StringVar(value=str(m[k]))
            if k == "kind":
                ttk.Combobox(self, textvariable=var, values=["ПДЧ", "МДФ", "ХДФ", "Шперплат", "Масив"], width=30).grid(row=r, column=1, padx=6)
            else:
                ttk.Entry(self, textvariable=var, width=33).grid(row=r, column=1, padx=6)
            self.vars[k] = var
        self.grain = tk.BooleanVar(value=m["grain"])
        ttk.Checkbutton(self, text="Има фладер (детайлите не се въртят)", variable=self.grain).grid(row=len(fields), column=0, columnspan=2, sticky="w", padx=6)
        ttk.Button(self, text="OK", command=self.ok).grid(row=len(fields) + 1, column=0, pady=8)
        ttk.Button(self, text="Отказ", command=self.destroy).grid(row=len(fields) + 1, column=1, pady=8)

    def ok(self):
        try:
            r = {"name": self.vars["name"].get(), "kind": self.vars["kind"].get(), "t": float(self.vars["t"].get()),
                 "sheet_l": int(float(self.vars["sheet_l"].get())), "sheet_w": int(float(self.vars["sheet_w"].get())),
                 "price": float(self.vars["price"].get()), "grain": bool(self.grain.get())}
        except ValueError:
            messagebox.showerror("Грешка", "Проверете числата.", parent=self)
            return
        self.result = r
        self.destroy()


def main():
    App().mainloop()
