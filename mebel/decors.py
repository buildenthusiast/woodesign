"""Библиотека с декори (цвят/шарка на облицовката) за корпус и фронтове.

Кодовете и имената са от каталога на Kronospan (дистрибутор Съливер, Пловдив).
Цветовете са ориентировъчни (за визуализация) – точният тон се проверява по
мостра. Потребителят може да добави собствени декори: с избор на цвят, от
снимка на мостра или от линк към снимката в каталога (цветът се изчислява).
"""
import os

SUP = "Kronospan"

# (код, име, вид, цвят)
_KRONO = [
    ("8685 BS", "Снежно бяло шагрен", "uni", "#f4f4f1"),
    ("8681 SU", "Брилянтно бяло", "uni", "#f7f7f5"),
    ("8100 SM", "Перлено бяло", "uni", "#eeeae0"),
    ("564 PE", "Бадем", "uni", "#e3d6bf"),
    ("112 PE", "Сиво", "uni", "#a7a9a8"),
    ("171 PE", "Сиво слейт", "uni", "#6e7275"),
    ("162 PE", "Сиво графит шагрен", "uni", "#4a4c4e"),
    ("164 PE", "Графит", "uni", "#3d3f41"),
    ("134 BS", "Жълто", "uni", "#e8c33a"),
    ("7190 BS", "Зелена мамба", "uni", "#7aa53a"),
    ("3025 SN", "Светъл дъб Сонома", "wood", "#d1b48a"),
    ("8431 SN", "Дъб Нагано", "wood", "#b3936e"),
    ("8921 PR", "Дъб Ферара", "wood", "#b88e5f"),
    ("5501 SN", "Дъб Славония", "wood", "#b48f62"),
    ("5527 SN", "Каменен дъб", "wood", "#9c917f"),
    ("5194 SN", "Дъб винтидж сив", "wood", "#9a948a"),
    ("K001 PW", "Дъб крафт бял", "wood", "#e2d8c8"),
    ("K002 PW", "Дъб крафт сив", "wood", "#a39d93"),
    ("K004 PW", "Дъб крафт табак", "wood", "#8a6440"),
    ("K005 PW", "Дъб ърбън ойстър", "wood", "#a8a091"),
    ("K006 PW", "Дъб ърбън амбър", "wood", "#a57a4c"),
    ("K007 PW", "Дъб ърбън кафе", "wood", "#5f4532"),
    ("K076 PW", "Пясъчен дъб експресив", "wood", "#c4a57d"),
    ("K090 PW", "Дъб експресив бронз", "wood", "#7b5a3c"),
    ("K081 PW", "Дъб сатен Коустланд", "wood", "#c7ad8c"),
    ("K079 PW", "Сив дъб Клубхаус", "wood", "#8d877d"),
    ("K105 PW", "Дъб ендгрейн суров", "wood", "#c2a27a"),
    ("K107 PW", "Дъб ендгрейн елеганс", "wood", "#b28d63"),
    ("729 PR", "Орех", "wood", "#7a5236"),
    ("9614 BS", "Орех Лион", "wood", "#6b4a33"),
    ("8953 SU", "Орех Тиеполо", "wood", "#5e4130"),
    ("K008 PW", "Орех селект лайт", "wood", "#9c7653"),
    ("K009 PW", "Орех селект дарк", "wood", "#4e3628"),
    ("K020 PW", "Орех селект огнен", "wood", "#8a5634"),
    ("5500 SU", "Благороден бряст светъл", "wood", "#b9a084"),
    ("K017 PW", "Златен бряст", "wood", "#b08752"),
    ("K018 PW", "Опушен бряст", "wood", "#6f5a4a"),
    ("K019 PW", "Сребърен бряст", "wood", "#a8a59e"),
    ("K085 PW", "Хикори Рокфорд светъл", "wood", "#d3b78e"),
    ("K086 PW", "Хикори Рокфорд натурал", "wood", "#b98e60"),
    ("K087 PW", "Хикори Рокфорд тъмен", "wood", "#6d4c35"),
    ("K012 SU", "Перлен арт бук", "wood", "#d9c7ae"),
    ("K013 SU", "Пясъчен арт бук", "wood", "#cdb08a"),
    ("381 PR", "Бук баварски", "wood", "#d9a878"),
    ("1715 BS", "Бреза", "wood", "#e0c9a3"),
    ("1912 BS", "Елша светла", "wood", "#c99a6a"),
    ("K078 PW", "Череша Ривърсайд тъмна", "wood", "#6e3a26"),
    ("5529 SN", "Орегон", "wood", "#a77a4f"),
    ("K083 SN", "Светъл артууд", "wood", "#c6b49b"),
    ("K084 SN", "Тъмен артууд", "wood", "#574638"),
    ("4298 SU", "Ателие лайт", "wood", "#b8b0a4"),
    ("4299 SU", "Ателие дарк", "wood", "#4f4a45"),
    ("8548 SN", "Файнлайн мока", "wood", "#5a4637"),
    ("8995 SN", "Коко Боло", "wood", "#6a4430"),
    ("K015 PW", "Пиратско дърво винтидж", "wood", "#7d6a58"),
    ("K021 SN", "Африканско дърво", "wood", "#5c3e2c"),
    ("K022 SN", "Блекууд сатен", "wood", "#2f2a26"),
    ("854 BS", "Венге", "wood", "#3e2c22"),
    ("9763 BS", "Венге Луизиана", "wood", "#3b2a20"),
    ("7648 SN", "Етно венге кафяво", "wood", "#4b3426"),
]

# МДФ фронтове – боя/фолио/гланц (RAL)
_MDF = [
    ("RAL 9016 мат", "МДФ боя бял мат", "paint", "#f1f1ee"),
    ("RAL 9016 гланц", "МДФ гланц бял", "gloss", "#fbfbfb"),
    ("RAL 9001", "МДФ боя крем", "paint", "#e9e0d2"),
    ("RAL 7035", "МДФ боя светлосиво", "paint", "#c5c7c4"),
    ("RAL 7016", "МДФ боя антрацит", "paint", "#383e42"),
    ("RAL 9005 мат", "МДФ боя черно мат", "paint", "#1f1f1f"),
    ("RAL 5014", "МДФ боя гълъбово синьо", "paint", "#637d96"),
    ("RAL 6021", "МДФ боя бледо зелено", "paint", "#89ac76"),
    ("NCS S 2005-Y30R", "МДФ боя кашмир (беж)", "paint", "#c9bfae"),
]

KIND_NAMES = {"uni": "едноцветен", "wood": "дървесен", "paint": "боя", "gloss": "гланц", "stone": "камък/бетон"}


def default_decors():
    out = [{"key": c, "name": n, "kind": k, "color": col, "supplier": SUP, "image": ""} for c, n, k, col in _KRONO]
    out += [{"key": c, "name": n, "kind": k, "color": col, "supplier": "МДФ", "image": ""} for c, n, k, col in _MDF]
    return out


def label(d):
    return f"{d['key']} – {d['name']}"


def get(decors, key, default="8685 BS"):
    for d in decors:
        if d["key"] == key:
            return d
    for d in decors:
        if d["key"] == default:
            return d
    return {"key": key or "?", "name": "Неизвестен декор", "kind": "uni", "color": "#eeeeea", "supplier": "", "image": ""}


def default_for_material(mat):
    """Декор по подразбиране за материал (когато в мебелта няма избран)."""
    if not mat:
        return "8685 BS"
    if mat.get("kind") == "МДФ":
        return "RAL 9016 мат"
    if mat.get("grain"):
        return "3025 SN"
    return "8685 BS"


def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def nearest(decors, hex_color, wood=None, kinds=None):
    """Най-близкият декор по цвят (по желание само дървесни/едноцветни)."""
    try:
        r, g, b = _rgb(hex_color)
    except (ValueError, TypeError, IndexError):
        return None
    best, bd = None, 1e18
    for d in decors:
        if wood is True and d["kind"] != "wood":
            continue
        if wood is False and d["kind"] == "wood":
            continue
        if kinds and d["kind"] not in kinds:
            continue
        r2, g2, b2 = _rgb(d["color"])
        dist = 2 * (r - r2) ** 2 + 4 * (g - g2) ** 2 + 3 * (b - b2) ** 2
        if dist < bd:
            best, bd = d, dist
    return best


# ------------------------------------------------------------ собствени декори
def decor_dir():
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    d = os.path.join(base, "MebelDesigner", "decors")
    os.makedirs(d, exist_ok=True)
    return d


def analyze_image_bytes(raw):
    """Средeн цвят и дали има изразена шарка (дърво) от снимка на мостра."""
    from PIL import Image, ImageStat
    import io
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = im.size
    # централната част – без рамки и надписи
    im = im.crop((w // 6, h // 6, w - w // 6, h - h // 6)).resize((64, 64))
    st = ImageStat.Stat(im)
    r, g, b = (int(x) for x in st.mean)
    contrast = sum(st.stddev) / 3
    warm = r > b + 12
    kind = "wood" if (contrast > 9 and warm) else "uni"
    return "#%02x%02x%02x" % (r, g, b), kind


def save_image(raw, code):
    safe = "".join(ch if ch.isalnum() else "_" for ch in code)
    p = os.path.join(decor_dir(), safe + ".jpg")
    from PIL import Image
    import io
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    im.thumbnail((400, 400))
    im.save(p, "JPEG", quality=88)
    return p


def download(url, timeout=20):
    import urllib.request
    from .updater import _ssl_context
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 MebelDesigner"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as r:
        return r.read()
