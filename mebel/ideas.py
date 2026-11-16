"""Генератор на дизайнерски идеи по габаритни размери.

Връща списък варианти: (заглавие, описание, промени_по_item). Правилата
следват ергономията на корпусните мебели:
  * врата 350-600 мм широчина; над 600 мм – две врати;
  * рафт от ПДЧ 18 мм – светъл отвор до ~800 мм (иначе провисва);
  * закачалка: ризи/сака ≥ 950 мм под тръбата, палта/рокли ≥ 1500 мм;
  * чекмеджета: фронт 140-250 мм, горните по-ниски за прибори;
  * разстояние между рафтове за книги 280-350 мм, за папки 330-350 мм.
"""
import math
from .furniture import new_section


def _split(total, max_w, min_n=1):
    n = max(min_n, math.ceil(total / max_w))
    return n


def ideas(ftype, W, H, D):
    W, H, D = float(W), float(H), float(D)
    f = {
        "wardrobe": _wardrobe, "base": _base, "wall": _wall, "tall": _tall,
        "chest": _chest, "night": _chest, "tv": _tv, "shelf": _shelf, "custom": _custom,
    }.get(ftype, _custom)
    res = f(W, H, D)
    tips = general_tips(ftype, W, H, D)
    return res, tips


def _wardrobe(W, H, D):
    out = []
    ndoors = max(1, round(W / 500))
    # групи врати: по 2 на секция, остатъкът – единична врата
    groups = [2] * (ndoors // 2) + ([1] if ndoors % 2 else [])
    if len(groups) == 1 and ndoors == 2:
        groups = [1, 1]
    secs_desc = f"{ndoors} врати по ~{W / ndoors:.0f} мм"

    def layout(kind):
        secs = []
        for k, nd in enumerate(groups):
            if k == 0:
                secs.append(new_section(doors=nd, shelves=1, rail=2 if kind == "double" else 1))
            elif k == 1 and kind == "drawers":
                secs.append(new_section(doors=1, shelves=3, drawers=3, drawer_h=200))
                if nd == 2:
                    secs.append(new_section(doors=1, shelves=5))
            elif k % 2 == 0 and len(groups) > 2:
                secs.append(new_section(doors=nd, shelves=1, rail=1))
            else:
                # секциите с рафтове – по 1 врата, за да не провисват рафтовете
                for _ in range(nd):
                    secs.append(new_section(doors=1, shelves=5))
        return secs

    out.append(("Класически", f"{secs_desc}. Секция със закачалка и рафт над нея + секция с рафтове.",
                {"sections": layout("classic")}))
    if W >= 900:
        out.append(("С чекмеджета", f"{secs_desc}. Закачалка + секция с 3 външни чекмеджета долу и рафтове над тях.",
                    {"sections": layout("drawers")}))
    if H >= 2200:
        out.append(("Двойна закачалка", "Две тръби една над друга за ризи и панталони – печели място при къси дрехи.",
                    {"sections": layout("double")}))
    if W >= 1200:
        secs = layout("classic")
        secs.append(new_section(width=300, doors=0, shelves=6))
        out.append(("С отворен край", "Добавена тясна отворена етажерка (300 мм) в края за декорация/аксесоари.",
                    {"sections": secs}))
    return out


def _base(W, H, D):
    out = []
    if W <= 450:
        out.append(("Врата + рафт", "Тесен шкаф с една врата и един рафт.", {"sections": [new_section(doors=1, shelves=1)]}))
        out.append(("Бутилиера/отворен", "Отворени рафтове за бутилки/кърпи (без врата).", {"sections": [new_section(doors=0, shelves=2)]}))
        out.append(("3 чекмеджета", "Три чекмеджета – прибори, кутии, тигани.", {"sections": [new_section(doors=0, shelves=0, drawers=3, drawer_h=0)]}))
    elif W <= 650:
        out.append(("1 врата + рафт", "Класически долен шкаф.", {"sections": [new_section(doors=1, shelves=1)]}))
        out.append(("Чекмедже + врата", "Горно чекмедже за прибори, врата отдолу.", {"sections": [new_section(doors=1, shelves=1, drawers=1, drawer_h=150, drawer_top=True)]}))
        out.append(("4 чекмеджета", "Най-удобно за ежедневна употреба – всичко се вижда отгоре.", {"sections": [new_section(doors=0, shelves=0, drawers=4, drawer_h=0)]}))
        out.append(("Мивка", "Шкаф за мивка – 2 врати или 1 врата, без рафт, задната траверса по-ниско/изрязан гръб.",
                    {"sections": [new_section(doors=1, shelves=0)], "back": "none"}))
    else:
        out.append(("2 врати + рафт", "Широк шкаф с две врати.", {"sections": [new_section(doors=2, shelves=1)]}))
        out.append(("3 широки чекмеджета", "Широки чекмеджета за тенджери – препоръчват се скрити водачи.",
                    {"sections": [new_section(doors=0, shelves=0, drawers=3, drawer_h=0)], "slide": "hidden"}))
        if W >= 900:
            half = (W - 3 * 18) / 2
            out.append(("Чекмеджета + врата", "Ляво колона чекмеджета, дясно врата с рафт.",
                        {"sections": [new_section(width=half, doors=0, shelves=0, drawers=4, drawer_h=0), new_section(doors=1, shelves=1)]}))
    return out


def _wall(W, H, D):
    out = []
    nd = 1 if W <= 600 else 2
    sh = max(1, int((H - 36) // 300) - 1)
    out.append((f"{nd} врат{'а' if nd == 1 else 'и'} + {sh} рафт{'а' if sh > 1 else ''}", "Стандартен горен шкаф.",
                {"sections": [new_section(doors=nd, shelves=sh)]}))
    if H <= 600 and W >= 600:
        out.append(("Подемна клапа", "Една хоризонтална врата с подемен механизъм – удобна над абсорбатор или високо.",
                    {"sections": [new_section(doors=1, shelves=1)], "hinge": "lift"}))
    out.append(("Отворени рафтове", "Без врати – за подправки и чаши. Внимание: събира прах.",
                {"sections": [new_section(doors=0, shelves=sh)]}))
    if W >= 800:
        out.append(("Врати + отворена ниша", "Затворена част + отворена секция 300 мм.",
                    {"sections": [new_section(doors=nd, shelves=sh), new_section(width=300, doors=0, shelves=sh)]}))
    return out


def _tall(W, H, D):
    out = [("Килер", "Две врати и 4-5 рафта – за провизии/чистачки.", {"sections": [new_section(doors=2 if W > 600 else 1, shelves=5)]}),
           ("Чекмеджета + врата", "Две чекмеджета долу, врата отгоре.", {"sections": [new_section(doors=2 if W > 600 else 1, shelves=4, drawers=2, drawer_h=250)]}),
           ("Врата долу + ниша", "Ниска врата долу (вграден уред/ниша над нея).",
            {"sections": [new_section(doors=2 if W > 600 else 1, shelves=1, door_h=800, open_shelves=1)]})]
    return out


def _chest(W, H, D):
    out = []
    usable = H - 100
    n = max(2, min(6, int(usable // 200)))
    if W > 1000:
        out.append(("Две колони чекмеджета", f"2 × {n} чекмеджета – по-къси, по-стабилни кутии.",
                    {"sections": [new_section(doors=0, shelves=0, drawers=n, drawer_h=0), new_section(doors=0, shelves=0, drawers=n, drawer_h=0)]}))
    out.append((f"{n} еднакви чекмеджета", "Класически скрин.", {"sections": [new_section(doors=0, shelves=0, drawers=n, drawer_h=0)]}))
    if n > 2:
        out.append((f"{n-1} високи чекмеджета", "По-дълбоки чекмеджета за пуловери и спално бельо.",
                    {"sections": [new_section(doors=0, shelves=0, drawers=n - 1, drawer_h=0)]}))
    out.append(("Чекмедже + врата", "Горно чекмедже, отдолу врата с рафт.",
                {"sections": [new_section(doors=1 if W <= 600 else 2, shelves=1, drawers=1, drawer_h=160, drawer_top=True)]}))
    return out


def _tv(W, H, D):
    out = []
    if W >= 1200:
        side = (W - 2 * 18 - 2 * 18) / 4
        out.append(("Врата–чекмеджета–врата", "Симетрично: врати отстрани, чекмеджета в средата.",
                    {"sections": [new_section(width=side, doors=1, shelves=1), new_section(doors=0, shelves=0, drawers=2, drawer_h=0), new_section(width=side, doors=1, shelves=1)]}))
        out.append(("Отворен център", "Отворена ниша за приемник/конзола в средата, затворено отстрани.",
                    {"sections": [new_section(width=side, doors=1, shelves=1), new_section(doors=0, shelves=1), new_section(width=side, doors=1, shelves=1)]}))
    n = max(1, math.ceil(W / 600))
    out.append((f"{n} клапи/врати", "Изцяло затворен шкаф с врати.", {"sections": [new_section(doors=1, shelves=1) for _ in range(n)]}))
    out.append(("Само чекмеджета", "Широки чекмеджета – най-практично за дребни неща.",
                {"sections": [new_section(doors=0, shelves=0, drawers=2, drawer_h=0) for _ in range(max(1, math.ceil(W / 800)))]}))
    return out


def _shelf(W, H, D):
    out = []
    ncol = max(1, math.ceil((W - 36) / 800))
    nsh = max(1, int((H - 120) // 330) - 1)
    out.append((f"{ncol} колони × {nsh} рафта", "Отворена библиотека, отвор ≤ 800 мм против провисване.",
                {"sections": [new_section(doors=0, shelves=nsh) for _ in range(ncol)]}))
    if H >= 1200:
        out.append(("Шкаф отдолу, отворено отгоре", "Врати до 800 мм височина, отворени рафтове над тях.",
                    {"sections": [new_section(doors=1 if (W / ncol) <= 600 else 2, shelves=1, door_h=780, open_shelves=max(1, nsh - 2)) for _ in range(ncol)]}))
        out.append(("Чекмеджета отдолу", "Две чекмеджета долу, рафтове над тях.",
                    {"sections": [new_section(doors=0, shelves=max(1, nsh - 1), drawers=2, drawer_h=200) for _ in range(ncol)]}))
    return out


def _custom(W, H, D):
    return [("Врати + рафтове", "Универсален модул.", {"sections": [new_section(doors=1 if W <= 600 else 2, shelves=max(1, int(H // 350) - 1))]}),
            ("Отворен", "Отворени рафтове.", {"sections": [new_section(doors=0, shelves=max(1, int(H // 350) - 1))]})]


def general_tips(ftype, W, H, D):
    tips = []
    if ftype == "wardrobe":
        if D < 550:
            tips.append("Дълбочина под 550 мм е малка за закачалка напречно – закачалките (450 мм) ще опират във вратите. Помислете за изтегляща се напречна закачалка.")
        if H > 2600:
            tips.append("Над 2600 мм е добре гардеробът да е на две нива (основен корпус + антресола) – по-лесно се внася и монтира.")
        if W > 2000:
            tips.append("Гардероб над 2 м – правете го от отделни корпуси (по 2 врати), снадени с винтове – по-лесен транспорт и по-точен монтаж.")
    if ftype == "base":
        if abs(D - 560) > 40:
            tips.append("Стандартна дълбочина на кухненски корпус е 560 мм (плот 600 мм).")
        tips.append("Височина на работния плот: ръст/2 + 50…100 мм (обикновено 880-920 мм с плота).")
    if ftype == "wall":
        tips.append("Долният ръб на горните шкафове – 500-600 мм над плота. Дълбочина 300-350 мм.")
    if ftype in ("chest", "night"):
        tips.append("При деца/наклонен под – обезопасете скрина с ъгъл към стената против преобръщане.")
    if ftype == "shelf" and H > 1500:
        tips.append("Висока етажерка задължително се прикрепва към стената.")
    return tips
