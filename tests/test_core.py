import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mebel.catalog import default_catalog, FURNITURE_TYPES
from mebel.furniture import default_item, build, new_section
from mebel.ideas import ideas
from mebel.optimizer import optimize, Piece
from mebel.project import new_project, compute, save, load
from mebel.export import export_pdf, export_parts_csv, export_hardware_csv

CAT = default_catalog()


def test_all_types_and_ideas_build():
    for ft in FURNITURE_TYPES:
        it = default_item(ft)
        assert build(it, CAT).parts
        vs, _ = ideas(ft, it["W"], it["H"], it["D"])
        assert vs
        for _, _, ov in vs:
            it2 = dict(it); it2.update(ov)
            assert build(it2, CAT).parts


def test_base_cabinet_dimensions():
    it = default_item("base")  # 600x820x560, крачета 100, траверси
    r = build(it, CAT)
    P = {p.name: p for p in r.parts}
    assert P["Страница"].length == 720 and P["Страница"].width == 557   # 560 - ХДФ 3
    assert P["Дъно"].length == 564                                       # 600 - 2*18
    assert P["Врата"].length == 717 and P["Врата"].width == 597          # фуга 3
    assert any("Панта" in h.name and h.qty == 2 for h in r.hardware)


def test_drawer_box_ball_slides():
    it = default_item("chest")
    it["sections"] = [new_section(doors=0, shelves=0, drawers=3, drawer_h=0)]
    r = build(it, CAT)
    P = {p.name: p for p in r.parts}
    iw = it["W"] - 36
    assert P["Чекмедже – чело/гръб"].length == iw - 26 - 32
    assert P["Чекмедже – страница"].qty == 6
    assert P["Фронт чекмедже"].qty == 3


def test_optimizer_respects_sheet_and_grain():
    pcs = [Piece(i, str(i), 2000, 500, True) for i in range(5)]
    res = optimize("x", 2800, 2070, pcs, kerf=4, trim=10, iterations=50)
    assert not res.unplaced
    assert res.n_sheets == 2   # 4 на плоча по ширина 2050 (4*500+3*4=2012)
    for sh in res.sheets:
        for p in sh.placed:
            assert not p.rotated
            assert p.x >= 10 and p.y >= 10
            assert p.x + p.dx <= 2790 + 1e-6 and p.y + p.dy <= 2060 + 1e-6
        # без застъпване
        pl = sh.placed
        for a in range(len(pl)):
            for b in range(a + 1, len(pl)):
                A, B = pl[a], pl[b]
                assert A.x + A.dx <= B.x or B.x + B.dx <= A.x or A.y + A.dy <= B.y or B.y + B.dy <= A.y


def test_optimizer_rotation_without_grain():
    pcs = [Piece(i, str(i), 1000, 2000, False) for i in range(2)]
    res = optimize("x", 2800, 2070, pcs, iterations=10)
    assert res.n_sheets == 1 and not res.unplaced


def test_project_compute_and_export():
    pr = new_project()
    pr["items"].append(default_item("base"))
    pr["settings"]["iterations"] = 30
    comp = compute(pr)
    assert comp.cuts and comp.costs["ОБЩО"] > 0
    d = tempfile.mkdtemp()
    export_pdf(comp, pr, os.path.join(d, "a.pdf"))
    export_parts_csv(comp, pr, os.path.join(d, "a.csv"))
    export_hardware_csv(comp, os.path.join(d, "h.csv"))
    save(pr, os.path.join(d, "p.mebel.json"))
    assert load(os.path.join(d, "p.mebel.json"))["items"][1]["type"] == "base"
    assert os.path.getsize(os.path.join(d, "a.pdf")) > 5000


FAKE = {
    "is_furniture": True, "furniture_type": "wardrobe", "name": "Гардероб дъб", "description": "Три врати.",
    "width_mm": 1500, "height_mm": 2300, "depth_mm": 600, "base": "plinth", "base_height_mm": 80, "top": "between",
    "fronts_material": "ПДЧ", "fronts_finish": "дъб", "carcass_finish": "дъб", "wood_grain_decor": True,
    "handles": "profile", "lift_up_door": False,
    "sections": [
        {"width_ratio": 0.66, "doors": 2, "shelves": 1, "drawers": 0, "drawers_fill_section": False, "drawer_front_h": 0,
         "drawers_on_top": False, "hanging_rails": 1, "door_height": 0, "open_shelves_above": 0},
        {"width_ratio": 0.34, "doors": 1, "shelves": 4, "drawers": 2, "drawers_fill_section": False, "drawer_front_h": 200,
         "drawers_on_top": False, "hanging_rails": 0, "door_height": 0, "open_shelves_above": 0},
    ],
    "advice": ["Съвет"],
}


def test_photo_result_to_item():
    from mebel.photo import result_to_item
    it = result_to_item(FAKE, CAT, {"W": 1600})
    assert it["W"] == 1600 and it["H"] == 2300 and it["type"] == "wardrobe"
    assert it["front_mat"] == "pdch18_dab" and it["handle"] == "profile"
    assert len(it["sections"]) == 2 and it["sections"][0]["rail"] == 1 and it["sections"][1]["drawers"] == 2
    r = build(it, CAT)
    assert r.parts and any(p.name == "Фронт чекмедже" for p in r.parts)


def test_photo_analyze_with_fake_client(tmp_path):
    import json, types
    from mebel import photo
    img = tmp_path / "a.png"
    img.write_bytes(bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                                  "1f15c4890000000d49444154789c6300010000050001"
                                  "0d0a2db40000000049454e44ae426082"))
    seen = {}

    class Msgs:
        def create(self, **kw):
            seen.update(kw)
            return types.SimpleNamespace(stop_reason="end_turn",
                                         content=[types.SimpleNamespace(type="text", text=json.dumps(FAKE))])
    client = types.SimpleNamespace(beta=types.SimpleNamespace(messages=Msgs()))
    res = photo.analyze_photo(str(img), "k", {"H": 2300}, client=client)
    assert res["furniture_type"] == "wardrobe"
    assert seen["model"] == "claude-opus-5-5" and seen["fallbacks"] == "default"
    assert seen["messages"][0]["content"][0]["type"] == "image"
    assert "височина = 2300" in seen["messages"][0]["content"][1]["text"]


def test_3d_boxes():
    from mebel.view3d import boxes_from
    it = default_item("wardrobe")
    bx = boxes_from(it, build(it, CAT), CAT)
    kinds = {b["kind"] for b in bx}
    assert {"side", "door", "back", "shelf"} <= kinds
    assert all(b["x1"] > b["x0"] and b["y1"] > b["y0"] and b["z1"] > b["z0"] for b in bx)


def test_quote_pdf(tmp_path):
    from mebel.quote import export_quote_pdf, item_costs, item_price, quote_settings
    pr = new_project()
    pr["items"].append(default_item("base"))
    pr["settings"]["iterations"] = 20
    pr["quote"] = {"customer": "Иван Петров", "transport": 30, "montage": 80, "discount_pct": 5}
    comp = compute(pr)
    costs = item_costs(comp, pr)
    assert len(costs) == 2 and all(c["total"] > 0 for c in costs)
    # сборът на себестойностите ≈ общите разходи от проекта
    tot_proj = sum(v for k, v in comp.costs.items() if not k.startswith("_") and k != "ОБЩО")
    assert abs(sum(c["total"] for c in costs) - tot_proj) < 0.5
    q = quote_settings(pr)
    total = export_quote_pdf(pr, str(tmp_path / "q.pdf"), comp)
    expect_net = sum(item_price(c, q) for c in costs) * 0.95 + 110
    assert abs(total - round(expect_net * 1.2, 2)) < 0.1
    assert (tmp_path / "q.pdf").stat().st_size > 5000


def test_photo_grok_with_fake_http(tmp_path, monkeypatch):
    import io, json
    from mebel import photo
    img = tmp_path / "a.png"
    img.write_bytes(bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                                  "1f15c4890000000d49444154789c6300010000050001"
                                  "0d0a2db40000000049454e44ae426082"))
    seen = {}

    class R(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): pass

    def opener(req, timeout=0):
        seen["url"] = req.full_url
        seen["auth"] = req.headers.get("Authorization")
        seen["body"] = json.loads(req.data)
        txt = "```json\n" + json.dumps(FAKE, ensure_ascii=False) + "\n```"
        return R(json.dumps({"choices": [{"message": {"content": txt}}]}).encode())
    res = photo._analyze_grok(str(img), "xai-k", {"W": 1500}, "grok-4", opener=opener)
    assert res["furniture_type"] == "wardrobe"
    assert seen["url"].startswith("https://api.x.ai/") and seen["auth"] == "Bearer xai-k"
    assert seen["body"]["model"] == "grok-4"
    assert seen["body"]["messages"][0]["content"][0]["image_url"]["url"].startswith("data:image/png;base64,")


def test_photo_config_providers(tmp_path, monkeypatch):
    from mebel import photo
    monkeypatch.setenv("APPDATA", str(tmp_path))
    photo.save_config(provider="grok", grok_model="grok-4")
    photo.save_api_key("xai-1", "grok")
    photo.save_api_key("sk-ant-1", "claude")
    assert photo.provider() == "grok" and photo.load_api_key() == "xai-1" and photo.load_api_key("claude") == "sk-ant-1"


def test_updater_check():
    import io, json
    from mebel import updater

    class R(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): pass

    def mk(tag):
        return lambda req, timeout=0: R(json.dumps({"tag_name": tag, "body": "x", "html_url": "u",
            "assets": [{"name": "MebelDesigner.exe", "browser_download_url": "https://dl/x.exe"}]}).encode())
    assert updater.check(opener=mk("v99.0.0"))["url"] == "https://dl/x.exe"
    assert updater.check(opener=mk("v0.0.1")) is None
