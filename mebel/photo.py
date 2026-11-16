"""Разпознаване на мебел от снимка чрез Claude (Anthropic) или Grok (xAI) и превръщане
в параметричен дизайн за програмата.

Нужен е API ключ от https://platform.claude.com (раздел API Keys). Ключът се
пази локално в %APPDATA%\\MebelDesigner\\config.json или се чете от
променливата ANTHROPIC_API_KEY.
"""
import base64
import json
import os

from .furniture import default_item, new_section
from .catalog import FURNITURE_TYPES

MODEL = "claude-opus-5-5"
MAX_SIDE = 1568          # препоръчителна максимална страна на изображението
MAX_BYTES = 4_500_000    # под лимита от 5 MB за изображение

SECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "width_ratio": {"type": "number", "description": "Относителна широчина на секцията (сборът на всички = 1)."},
        "doors": {"type": "integer", "description": "Брой врати в секцията: 0, 1 или 2."},
        "shelves": {"type": "integer", "description": "Рафтове зад вратите (или в отворената секция)."},
        "drawers": {"type": "integer", "description": "Брой външни чекмеджета в секцията."},
        "drawers_fill_section": {"type": "boolean", "description": "true ако чекмеджетата заемат цялата височина на секцията."},
        "drawer_front_h": {"type": "number", "description": "Височина на един фронт на чекмедже в мм (ако не заемат цялата секция)."},
        "drawers_on_top": {"type": "boolean", "description": "true ако чекмеджетата са над вратите."},
        "hanging_rails": {"type": "integer", "description": "Брой тръби за закачалки (0, 1 или 2)."},
        "door_height": {"type": "number", "description": "Височина на вратите в мм, ако покриват само долната част и отгоре има отворени рафтове; иначе 0."},
        "open_shelves_above": {"type": "integer", "description": "Отворени рафтове над ниските врати."},
    },
    "required": ["width_ratio", "doors", "shelves", "drawers", "drawers_fill_section", "drawer_front_h",
                 "drawers_on_top", "hanging_rails", "door_height", "open_shelves_above"],
    "additionalProperties": False,
}

RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "is_furniture": {"type": "boolean", "description": "false ако на снимката няма корпусна мебел."},
        "furniture_type": {"type": "string", "enum": list(FURNITURE_TYPES.keys())},
        "name": {"type": "string", "description": "Кратко име на български."},
        "description": {"type": "string", "description": "Описание на дизайна на български (2-4 изречения)."},
        "width_mm": {"type": "number"},
        "height_mm": {"type": "number"},
        "depth_mm": {"type": "number"},
        "base": {"type": "string", "enum": ["legs", "plinth", "wall", "none"]},
        "base_height_mm": {"type": "number"},
        "top": {"type": "string", "enum": ["between", "over", "rails"]},
        "fronts_material": {"type": "string", "enum": ["ПДЧ", "МДФ"], "description": "МДФ за боядисани/фрезовани/гланц фронтове, ПДЧ за ламинирани."},
        "fronts_finish": {"type": "string", "description": "Цвят/декор на фронтовете на български."},
        "carcass_finish": {"type": "string", "description": "Цвят/декор на корпуса на български."},
        "wood_grain_decor": {"type": "boolean", "description": "true ако декорът е дървесен (има фладер)."},
        "handles": {"type": "string", "enum": ["handle", "push", "profile"]},
        "lift_up_door": {"type": "boolean", "description": "true ако има хоризонтална подемна клапа."},
        "sections": {"type": "array", "items": SECTION_SCHEMA, "description": "Вертикалните секции отляво надясно."},
        "advice": {"type": "array", "items": {"type": "string"}, "description": "2-5 практически съвета на български за изработката."},
    },
    "required": ["is_furniture", "furniture_type", "name", "description", "width_mm", "height_mm", "depth_mm", "base",
                 "base_height_mm", "top", "fronts_material", "fronts_finish", "carcass_finish", "wood_grain_decor",
                 "handles", "lift_up_door", "sections", "advice"],
    "additionalProperties": False,
}

PROMPT = """Ти си опитен мебелист-конструктор на корпусни мебели от ПДЧ и МДФ.
Разгледай снимката и опиши мебелта като параметричен модел, за да може да се направи подобна.

Модел на програмата: корпус (2 страници, дъно, таван), разделен вертикално на секции отляво надясно.
Всяка секция отдолу нагоре: [чекмеджета] [врати с рафтове/закачалка зад тях] [отворени рафтове над ниски врати].
- Вратите винаги са наслагващи; 1 или 2 врати на секция (широчина на врата ≤ 600 мм).
- Ако чекмеджетата са горе, а вратата долу (кухня), drawers_on_top = true.
- Видимите отворени ниши броим като секции с doors = 0.
- Броят на рафтовете зад затворени врати не се вижда – предложи разумен брой (един на ~350 мм височина).

Размери в мм. {dims}
Ако не можеш да определиш размер, ползвай типичен: кухненски долен 600×820×560, горен 600×720×320,
гардероб 600 мм дълбочина, скрин 450 мм, етажерка 300 мм.
Ако на снимката няма корпусна мебел, върни is_furniture = false и попълни останалото с най-близката разумна мебел.
Всички текстове – на български."""


# ------------------------------------------------------------------ конфигурация
def config_path():
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "MebelDesigner", "config.json")


PROVIDERS = {"claude": "Claude (Anthropic)", "grok": "Grok (xAI)"}
GROK_DEFAULT_MODEL = "grok-4"
GROK_URL = "https://api.x.ai/v1/chat/completions"


def load_config():
    try:
        with open(config_path(), encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(**kw):
    p = config_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    data = load_config()
    data.update({k: (v.strip() if isinstance(v, str) else v) for k, v in kw.items()})
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)


def provider():
    return load_config().get("provider", "claude")


def load_api_key(prov=None):
    prov = prov or provider()
    cfg = load_config()
    if prov == "grok":
        return cfg.get("grok_key", "") or os.environ.get("XAI_API_KEY", "")
    return cfg.get("api_key", "") or os.environ.get("ANTHROPIC_API_KEY", "")


def save_api_key(key, prov="claude"):
    save_config(**({"grok_key": key} if prov == "grok" else {"api_key": key}))


# ------------------------------------------------------------------ изображение
def _media_type(path):
    ext = os.path.splitext(path)[1].lower()
    return {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}.get(ext, "image/jpeg")


def load_image(path):
    """Връща (media_type, base64). Намалява голяма снимка, ако има Pillow."""
    with open(path, "rb") as f:
        raw = f.read()
    mt = _media_type(path)
    try:
        from PIL import Image
        import io
        im = Image.open(io.BytesIO(raw))
        if max(im.size) > MAX_SIDE or len(raw) > MAX_BYTES:
            im = im.convert("RGB")
            im.thumbnail((MAX_SIDE, MAX_SIDE))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=88)
            raw, mt = buf.getvalue(), "image/jpeg"
    except ImportError:
        pass
    if len(raw) > 5_000_000:
        raise ValueError("Снимката е по-голяма от 5 MB. Намалете я или инсталирайте Pillow (pip install pillow).")
    return mt, base64.standard_b64encode(raw).decode("ascii")


# ------------------------------------------------------------------ API
class PhotoError(Exception):
    pass


def _prompt(known):
    parts = []
    for k, lbl in (("W", "широчина"), ("H", "височина"), ("D", "дълбочина")):
        if known.get(k):
            parts.append(f"{lbl} = {known[k]:g} мм")
    dims = ("Потребителят знае: " + ", ".join(parts) + " – използвай ги точно.") if parts else "Потребителят не е дал размери – прецени ги по пропорциите."
    return PROMPT.replace("{dims}", dims)


def analyze_photo(path, api_key, known=None, client=None, prov=None, model=None):
    """Анализира снимката с избрания доставчик и връща речник по RESULT_SCHEMA."""
    prov = prov or provider()
    if prov == "grok":
        return _analyze_grok(path, api_key, known or {}, model or load_config().get("grok_model") or GROK_DEFAULT_MODEL)
    return _analyze_claude(path, api_key, known or {}, client)


def _parse_json(text):
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{"):]
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b < 0:
        raise PhotoError("Неочакван отговор от модела – опитайте отново.")
    try:
        return json.loads(t[a:b + 1])
    except ValueError:
        raise PhotoError("Неочакван отговор от модела – опитайте отново.")


def _analyze_grok(path, api_key, known, model, opener=None):
    """Grok (xAI) – OpenAI-съвместим REST интерфейс, без допълнителни библиотеки."""
    import urllib.request
    import urllib.error
    if not api_key:
        raise PhotoError("Няма API ключ за Grok. Въведете го в „Снимка → API ключ“.")
    mt, data = load_image(path)
    prompt = _prompt(known) + "\nВърни САМО JSON обект по тази схема, без друг текст:\n" + json.dumps(RESULT_SCHEMA, ensure_ascii=False)
    body = {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:{mt};base64,{data}", "detail": "high"}},
            {"type": "text", "text": prompt},
        ]}],
        "response_format": {"type": "json_schema", "json_schema": {"name": "furniture", "schema": RESULT_SCHEMA, "strict": True}},
    }
    opener = opener or urllib.request.urlopen

    def call(b):
        req = urllib.request.Request(GROK_URL, data=json.dumps(b).encode("utf-8"), method="POST",
                                     headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
        with opener(req, timeout=180) as r:
            return json.loads(r.read().decode("utf-8"))
    try:
        try:
            resp = call(body)
        except urllib.error.HTTPError as e:
            if e.code == 400:   # моделът може да не поддържа json_schema – опит без него
                body.pop("response_format")
                resp = call(body)
            else:
                raise
    except urllib.error.HTTPError as e:
        msg = ""
        try:
            msg = e.read().decode("utf-8", "replace")[:300]
        except Exception:  # noqa
            pass
        if e.code in (401, 403):
            raise PhotoError("Невалиден API ключ за Grok или няма достъп до модела „%s“." % model)
        if e.code == 404:
            raise PhotoError(f"Моделът „{model}“ не е намерен. Сменете името на модела в „Снимка → API ключ“.")
        if e.code == 429:
            raise PhotoError("Твърде много заявки или изчерпан кредит в xAI.")
        raise PhotoError(f"Грешка от xAI ({e.code}): {msg}")
    except urllib.error.URLError:
        raise PhotoError("Няма връзка с интернет / api.x.ai.")
    try:
        text = resp["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise PhotoError("Неочакван отговор от xAI.")
    if isinstance(text, list):
        text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
    return _parse_json(text or "")


def _analyze_claude(path, api_key, known, client=None):
    import anthropic
    mt, data = load_image(path)
    client = client or anthropic.Anthropic(api_key=api_key or None)
    try:
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": RESULT_SCHEMA}},
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mt, "data": data}},
                {"type": "text", "text": _prompt(known)},
            ]}],
        )
    except anthropic.AuthenticationError:
        raise PhotoError("Невалиден API ключ. Проверете го в „Снимка → API ключ“.")
    except anthropic.PermissionDeniedError:
        raise PhotoError("Ключът няма достъп до модела. Проверете акаунта си в platform.claude.com.")
    except anthropic.RateLimitError:
        raise PhotoError("Твърде много заявки или изчерпан кредит. Опитайте след малко / проверете баланса.")
    except anthropic.BadRequestError as e:
        raise PhotoError(f"Заявката е отхвърлена: {getattr(e, 'message', e)}")
    except anthropic.APIStatusError as e:
        raise PhotoError(f"Грешка от сървъра ({e.status_code}). Опитайте отново.")
    except anthropic.APIConnectionError:
        raise PhotoError("Няма връзка с интернет / сървъра.")
    if resp.stop_reason == "refusal":
        raise PhotoError("Моделът отказа да анализира тази снимка.")
    if resp.stop_reason == "max_tokens":
        raise PhotoError("Отговорът е прекъснат – опитайте отново.")
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    try:
        return json.loads(text)
    except ValueError:
        raise PhotoError("Неочакван отговор от модела – опитайте отново.")


# ------------------------------------------------------------------ към проект
def _clamp(v, lo, hi, default):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return default
    return default if v != v else max(lo, min(hi, v))


def result_to_item(res, catalog, known=None):
    """Превръща резултата от анализа в item за furniture.build()."""
    known = known or {}
    ftype = res.get("furniture_type") if res.get("furniture_type") in FURNITURE_TYPES else "custom"
    it = default_item(ftype)
    it["name"] = (res.get("name") or it["name"])[:40]
    it["W"] = round(known.get("W") or _clamp(res.get("width_mm"), 200, 6000, it["W"]))
    it["H"] = round(known.get("H") or _clamp(res.get("height_mm"), 200, 3000, it["H"]))
    it["D"] = round(known.get("D") or _clamp(res.get("depth_mm"), 150, 1000, it["D"]))
    if res.get("base") in ("legs", "plinth", "wall", "none"):
        it["base"] = res["base"]
    it["base_h"] = 0 if it["base"] in ("wall", "none") else round(_clamp(res.get("base_height_mm"), 30, 200, 100))
    if res.get("top") in ("between", "over", "rails"):
        it["top"] = res["top"]
    if res.get("handles") in ("handle", "push", "profile"):
        it["handle"] = res["handles"]

    mats = catalog["materials"]
    t_c = next((m["t"] for m in mats if m["key"] == it["carcass_mat"]), 18)
    want_kind = res.get("fronts_material", "ПДЧ")
    grain = bool(res.get("wood_grain_decor"))
    cands = [m for m in mats if m["kind"] == want_kind and m["t"] >= 16]
    if want_kind == "ПДЧ":
        cands.sort(key=lambda m: (m["grain"] != grain, abs(m["t"] - 18)))
    else:
        cands.sort(key=lambda m: (abs(m["t"] - 18), -m["sheet_l"]))
    if cands:
        it["front_mat"] = cands[0]["key"]
    if grain:
        g = [m for m in mats if m["kind"] == "ПДЧ" and m["grain"] and m["t"] == t_c]
        if g and ftype not in ("base", "wall", "tall"):
            it["carcass_mat"] = g[0]["key"]
    if res.get("lift_up_door"):
        it["hinge"] = "lift"

    secs_in = res.get("sections") or []
    secs = []
    for s in secs_in[:8]:
        doors = int(_clamp(s.get("doors"), 0, 2, 1))
        drawers = int(_clamp(s.get("drawers"), 0, 8, 0))
        fill = bool(s.get("drawers_fill_section")) and doors == 0
        sec = new_section(
            doors=doors,
            shelves=int(_clamp(s.get("shelves"), 0, 10, 2)),
            drawers=drawers,
            drawer_h=0 if fill else round(_clamp(s.get("drawer_front_h"), 100, 400, 180)),
            rail=int(_clamp(s.get("hanging_rails"), 0, 2, 0)),
            door_h=round(_clamp(s.get("door_height"), 0, 3000, 0)),
            open_shelves=int(_clamp(s.get("open_shelves_above"), 0, 10, 0)),
            drawer_top=bool(s.get("drawers_on_top")) and drawers > 0 and doors > 0,
        )
        if fill:
            sec["shelves"] = 0
        sec["_ratio"] = _clamp(s.get("width_ratio"), 0.01, 1, 0)
        secs.append(sec)
    if secs:
        # широчини по пропорциите от снимката; последната секция – авто (поема остатъка)
        ratios = [s.pop("_ratio") for s in secs]
        tot = sum(ratios)
        if len(secs) > 1 and tot > 0:
            avail = it["W"] - 2 * t_c - (len(secs) - 1) * t_c
            equal_by_doors = [max(1, s["doors"]) for s in secs]
            eq_tot = sum(equal_by_doors)
            # ако пропорциите са близо до „равни врати“ – остави авто, вратите ще са еднакви
            if any(abs(r / tot - e / eq_tot) > 0.08 for r, e in zip(ratios, equal_by_doors)):
                for s, r in zip(secs[:-1], ratios[:-1]):
                    s["width"] = round(avail * r / tot)
        it["sections"] = secs
    return it
