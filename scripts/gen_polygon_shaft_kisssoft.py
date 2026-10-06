"""KISSsoft M2D 多边形轴连接金样收割 + 62 行截面量扫描 + 剖面快照。

三件事（docs/specs/polygon-shaft-m2d.md）：

1. ``--golden``（默认）：官方算例 ``17 Polygon.M2D`` + 文件变体（双方法 ×
   双剖面 × 覆盖/变体/峰值/交变/fs/ltr/Mb/D1 解禁）经 KISSsoftCOM 全变量
   收割 → ``tests/golden/polygon_shaft/kisssoft_m2d.json``
   （``tests/unit/test_kisssoft_m2d_golden.py`` 对账）。收割期即对每案跑
   pyffalo 闭式断言（压强/pzul/安全/截面量 ≤1e-9，Wp 多项式档同容差），
   防闭式与内核漂移。
2. ``--sections``：62 表行（P3G 五键 / P4C 四键全行值改写，模拟 GUI 真实
   选行）+ Wp 一维扫描网格（Dm=45 × e 0.1..5.5）→
   ``tools/data/polygon_shaft/wp_scan.json.gz``（seed 期 holdout 断言源）。
3. ``--profile``：随包 ``dat/M02D-001/002.DAT`` →
   ``tools/data/polygon_shaft/polygon_profile.csv``（62 行）。

COM 形态（M2A/M2E 配方）：``SetSilentMode(True)`` + ``GetModule("M02D", True)``
+ 文件变体（UTF-16 ``key=value¶`` 行替换，**LoadFile 必须绝对路径**——M1B
相对路径静默失败坑）+ ``CalculateRetVal()`` 唯一可信判据 + ``GetVar`` +
``ReleaseModule``。M2D 输入面宽（几何五字段/载荷/方法键改档全部生效），
远好于 M2E（几何快照死值）；材料快照（Rp/Rm/typ）改档无效（DBID 库锁定）。

用法::

    python scripts/gen_polygon_shaft_kisssoft.py               # 金样收割
    python scripts/gen_polygon_shaft_kisssoft.py --sections
    python scripts/gen_polygon_shaft_kisssoft.py --profile
"""

from __future__ import annotations

import csv
import gzip
import json
import math
import re
import sys
from pathlib import Path

import pyffalo_root

REPO = pyffalo_root.repo_root()
sys.path.insert(0, str(REPO / "src"))

GOLDEN = REPO / "tests/golden/polygon_shaft/kisssoft_m2d.json"
DATA_DIR = REPO / "tools/data/polygon_shaft"
WP_SCAN = DATA_DIR / "wp_scan.json.gz"
PROFILE_CSV = DATA_DIR / "polygon_profile.csv"
CASES_DIR = REPO / "tmp/m2d_harvest_cases"
KISS_EXAMPLE = Path("C:/KISSsoft 2026/example/17 Polygon.M2D")

#: 金样案（官方算例 + 文件变体；changes = M2D 存档真输入面）
CASES: list[tuple[str, list[tuple[str, object]]]] = [
    ("ex17", []),
    ("dm46", [("m02Dk.Dm", 46)]),                       # DM 覆盖（连续值）
    ("e20", [("m02Dk.e", 2.0)]),                        # E 覆盖
    ("y07_p3g", [("m02Dk.y", 0.7)]),                    # Y 覆盖（s 消费）
    ("row14", [("m02Dk.Dm", 14), ("m02Dk.da", 14.88),
               ("m02Dk.di", 13.12), ("m02Dk.e", 0.44), ("m02Dk.y", 1.44)]),
    ("row40", [("m02Dk.Dm", 40), ("m02Dk.da", 42.8),
               ("m02Dk.di", 37.2), ("m02Dk.e", 1.4), ("m02Dk.y", 1.2)]),
    ("row70", [("m02Dk.Dm", 70), ("m02Dk.da", 75.6),
               ("m02Dk.di", 64.4), ("m02Dk.e", 2.8), ("m02Dk.y", 1.2)]),
    ("din_p3g", [("m02Da.RechenMeth", 1)]),
    ("din_mmax", [("m02Da.RechenMeth", 1), ("m02Da.Mmax", 600)]),
    ("din_row40", [("m02Da.RechenMeth", 1), ("m02Dk.Dm", 40),
                   ("m02Dk.da", 42.8), ("m02Dk.di", 37.2),
                   ("m02Dk.e", 1.4), ("m02Dk.y", 1.2)]),
    ("din_mb200", [("m02Da.RechenMeth", 1), ("m02Da.Mb", 200)]),
    ("p4c_row14", [("m02Dk.DinIdK", 10020), ("m02Dk.da", 14),
                   ("m02Dk.di", 11), ("m02Dk.e", 1.6), ("m02Dk.y", 0.7)]),
    ("p4c_row45", [("m02Dk.DinIdK", 10020), ("m02Dk.da", 45),
                   ("m02Dk.di", 40), ("m02Dk.e", 6), ("m02Dk.y", 0.7)]),
    ("p4c_row75", [("m02Dk.DinIdK", 10020), ("m02Dk.da", 75),
                   ("m02Dk.di", 65), ("m02Dk.e", 6), ("m02Dk.y", 0.7)]),
    ("din_p4c_row45", [("m02Da.RechenMeth", 1), ("m02Dk.DinIdK", 10020),
                       ("m02Dk.da", 45), ("m02Dk.di", 40), ("m02Dk.e", 6),
                       ("m02Dk.y", 0.7)]),
    ("din_p4c_row75", [("m02Da.RechenMeth", 1), ("m02Dk.DinIdK", 10020),
                       ("m02Dk.da", 75), ("m02Dk.di", 65), ("m02Dk.e", 6),
                       ("m02Dk.y", 0.7)]),
    ("mmax_nl", [("m02Da.Mmax", 600), ("m02Da.NL", 1e5)]),
    ("momart_nw", [("m02Da.MomArt", 1), ("m02Da.NW", 1e6)]),
    ("stoss", [("m02Da.Mnenn", 200), ("m02Da.StossFak", 1.5)]),
    ("fs_input", [("m02Dw.isFsInput", "true"), ("m02Dw.fs", 2.0)]),
    ("ltr60", [("m02Da.ltr", 60)]),
]

HARVEST_VARS = [
    # a 段（载荷/方法）
    "m02Da.Mnenn", "m02Da.Meq", "m02Da.Mmax", "m02Da.StossFak", "m02Da.NW",
    "m02Da.NL", "m02Da.MomArt", "m02Da.ltr", "m02Da.RechenMeth",
    "m02Da.Mb", "m02Da.Ft", "m02Da.fw",
    # k 段（型面几何）
    "m02Dk.DinIdK", "m02Dk.Dm", "m02Dk.da", "m02Dk.di", "m02Dk.e",
    "m02Dk.y", "m02Dk.dr", "m02Dk.er",
    # w 段（轴）
    "m02Dw.FlacheW", "m02Dw.peq", "m02Dw.pmax", "m02Dw.pzul", "m02Dw.fs",
    "m02Dw.fL", "m02Dw.fH", "m02Dw.Resulteq", "m02Dw.Resultmax",
    "m02Dw.ResultW", "m02Dw.SollS", "m02Dw.Ap", "m02Dw.Ip", "m02Dw.Wp",
    "m02Dw.Tau", "m02Dw.Wx", "m02Dw.sigmaB", "m02Dw.mat.Rp", "m02Dw.mat.Rm",
    # n 段（毂）
    "m02Dn.FlacheN", "m02Dn.peq", "m02Dn.pmax", "m02Dn.pzul", "m02Dn.fs",
    "m02Dn.fL", "m02Dn.fH", "m02Dn.Resulteq", "m02Dn.Resultmax",
    "m02Dn.ResultN", "m02Dn.D1", "m02Dn.s",
]

#: Wp 一维扫描网格（Dm=45；拟合 0.1..5.5 步 0.1 + holdout 偏移点；
#: xmax = 5.5/45 与 data/polygon_shaft.WP_X_MAX 单源）
_WP_FIT_ES = [round(0.1 * i, 4) for i in range(1, 56)]
_WP_HOLD_ES = [0.17, 0.73, 1.37, 2.63, 3.43, 4.37, 5.23]
WP_X_MAX = 5.5 / 45.0

#: 官方算例 17 材料存档快照（C45：Rp=370/Rm=630）——s 与 pzul 链消费值；
#: GetVar 的 mat.Rp/mat.Rm 按几何直径重算（显示值，非链输入）
_MAT_RP0, _MAT_RM0 = 370.0, 630.0


def _setkey(text: str, key: str, val) -> str:
    """文件变体单键改写（锚定行首；¶ 为 KISSsoft 存档行分隔符）。"""
    out, n = re.subn(rf"^{re.escape(key)}=[^¶]*¶",
                     lambda _m, key=key, val=val: f"{key}={val}¶",
                     text, flags=re.MULTILINE)
    if n != 1:
        raise SystemExit(f"M2D 变体键改写失败 {key}={val}（命中 {n} 处）")
    return out


def _getvar(ksoft, var: str):
    try:
        val = ksoft.GetVar(var)
    except Exception:  # noqa: BLE001 — 变量在构型下不存在属正常
        return None
    if isinstance(val, str):
        try:
            return float(val)
        except ValueError:
            return val or None
    return val


def _read_dat(path: Path) -> list[list[float]]:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            rows.append([float(x) for x in line.split("|")])
    return rows


def _assert_close(case: str, label: str, got: float, want: float,
                  tol: float = 1e-9) -> None:
    if got is None or want is None:
        return
    if abs(got - want) > tol * max(abs(want), 1.0):
        raise SystemExit(
            f"{case}: 闭式 {label} 漂移 {got!r} vs 内核 {want!r}")


def _closure_checks(name: str, changes: list[tuple[str, object]],
                    e: dict) -> None:
    """收割期即对账（pyffalo 单源闭式 vs 内核，防漂移入库）。"""
    from pyffalo.data import polygon_shaft as ps

    ch = dict(changes)
    profile = "P4C" if ch.get("m02Dk.DinIdK") == 10020 else "P3G"
    method = int(e["m02Da.RechenMeth"])
    dm, da, di, ecc = (e["m02Dk.Dm"], e["m02Dk.da"], e["m02Dk.di"],
                       e["m02Dk.e"])
    y, l_tr = e["m02Dk.y"], e["m02Da.ltr"]
    g = ps.geometry(profile, dm, da, di, ecc, y)
    if g["dm"] != dm and profile == "P4C":
        dm = g["dm"]  # P4C 内核写回派生 Dm
    t_eq = e["m02Da.Meq"] * 1000.0
    t_peak = e["m02Da.Mmax"] * 1000.0
    if method == 0 and e["m02Dw.peq"]:
        _assert_close(name, "peq", ps.p_contact(0, profile, g, t_eq, l_tr),
                      e["m02Dw.peq"])
    if method == 0 and e["m02Dw.pmax"]:
        _assert_close(name, "pmax",
                      ps.p_contact(0, profile, g, t_peak, l_tr),
                      e["m02Dw.pmax"])
    elif method == 1 and e["m02Dw.pmax"]:
        # DIN 静载轨 pmax 消费 Meq（din_mmax 案钉死，Mmax 不进 DIN）
        _assert_close(name, "pmax",
                      ps.p_contact(1, profile, g, t_eq, l_tr),
                      e["m02Dw.pmax"])
    # Fläche/Ft 仅 Niemann 断言——DIN 路径不刷新（GetVar 回吐基线档陈旧
    # 缓存：din_row14 Fläche=384、din_dm14 Ft=22222 vs 真值 71428 均陈旧）
    if method == 0:
        _assert_close(name, "Fläche", ps.area_proj(profile, g, l_tr),
                      e["m02Dw.FlacheW"])
        if e["m02Da.Ft"]:
            _assert_close(name, "Ft", 2.0 * t_peak / dm, e["m02Da.Ft"])
    # s 断言：Niemann 恒用存档 Rm（row14/40/70/ex17 四案钉死——GetVar
    # 的 mat.Rm 显示值按直径重算但 s 链不消费）；DIN 的 s 与 pzul 在
    # 跨材料档时消费不同 Rp 列（din_row14：pzul 用重算 490、s 用存档
    # 370；din_d1_120 两链均 345）——库材料分档双轨黑盒，不建模
    # （own-input 材料卡天然等价，M2A K1 先例），金样矩阵避开跨档案，
    # DIN 的 s 仅在 333 档（pzul=0.9·370）断言。
    if method == 0 and e["m02Dn.s"]:
        _assert_close(name, "s(Rm)",
                      ps.wall_thickness(t_peak, _MAT_RM0, l_tr, y),
                      e["m02Dn.s"])
    # isclose 门禁（ocr 分支复审）：精确相等在内核值带浮点噪声时
    # 会静默跳过 DIN 的 s 断言，破坏 fail-fast 设计
    if (method == 1 and e["m02Dn.s"]
            and math.isclose(e["m02Dw.pzul"], 0.9 * _MAT_RP0,
                            rel_tol=1e-9)):
        # DIN 的 s 消费 Meq（din_mmax 案钉死，与 pmax/tau 同侧）
        _assert_close(name, "s(Rp)",
                      ps.wall_thickness(t_eq, _MAT_RP0, l_tr, y),
                      e["m02Dn.s"])
    if method == 1 and e["m02Dw.Wp"]:
        props = ps.section_props(profile, dm, g["e_eq"], di)
        _assert_close(name, "Ap", props["ap"], e["m02Dw.Ap"])
        _assert_close(name, "Ip", props["ip"], e["m02Dw.Ip"])
        _assert_close(name, "Wp", props["wp"], e["m02Dw.Wp"])
        _assert_close(name, "Wx", props["w_x"], e["m02Dw.Wx"])
        _assert_close(name, "Tau", t_eq / props["wp"], e["m02Dw.Tau"])


def harvest() -> int:
    """金样收割 → tests/golden/polygon_shaft/kisssoft_m2d.json。"""
    import win32com.client as client

    CASES_DIR.mkdir(parents=True, exist_ok=True)
    base_text = KISS_EXAMPLE.read_text("utf-16")
    cases: dict[str, dict] = {}
    ksoft = client.Dispatch("KISSsoftCOM.KISSsoft")
    try:
        ksoft.SetSilentMode(True)
        ksoft.GetModule("M02D", True)
        for name, changes in CASES:
            text = base_text
            for key, val in changes:
                text = _setkey(text, key, val)
            local = (CASES_DIR / f"golden_{name}.M2D").resolve()
            local.write_text(text, "utf-16")
            ksoft.LoadFile(str(local))          # 绝对路径（M1B 坑）
            if not ksoft.CalculateRetVal():
                raise SystemExit(f"{name}: CalculateRetVal=False")
            expect = {v: _getvar(ksoft, v) for v in HARVEST_VARS}
            missing = [v for v, x in expect.items() if x is None]
            if missing:
                raise SystemExit(f"{name}: 变量缺失 {missing}")
            _closure_checks(name, changes, expect)
            cases[name] = {"file": "17 Polygon.M2D", "changes": changes,
                           "expect": expect}
            print(f"{name:16s} peq={expect['m02Dw.peq']!r} "
                  f"pmax={expect['m02Dw.pmax']!r} "
                  f"Wp={expect['m02Dw.Wp']!r}", flush=True)
    finally:
        try:
            ksoft.ReleaseModule()
        except Exception:  # noqa: BLE001, S110
            pass
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(json.dumps({
        "source": "KISSsoft 2026 M02D official example 17 Polygon + file "
                  "variants (P3G/P4C × Niemann/DIN), COM GetVar",
        "note": "torque Nm (组件 N·mm ×1e-3 对账); lengths mm; pressure "
                "N/mm²; safeties dimensionless. P4C 的 dr/er 派生 "
                "(dr=di+2e, er=(da−di)/4, Dm=(da+di)/2); DIN 轨 peq/fw "
                "恒 0（不消费）; σB = Mb[Nm 数值]/Wx 内核量纲 quirk 照抄;"
                " s 用毂侧强度（Niemann Rm / DIN Rp）; 判废 Dm≥D1。",
        "harvest": "python tools/gen_polygon_shaft_kisssoft.py",
        "cases": cases,
    }, ensure_ascii=False, indent=1), "utf-8")
    print(f"→ {GOLDEN}（{len(cases)} 案）")
    return 0


def scan_sections() -> int:
    """62 行截面量 + Wp 扫描网格 → tools/data/polygon_shaft/wp_scan.json.gz。"""
    import win32com.client as client

    from pyffalo.data import polygon_shaft as ps

    p3g = _read_dat(Path("C:/KISSsoft 2026/dat/M02D-001.DAT"))
    p4c = _read_dat(Path("C:/KISSsoft 2026/dat/M02D-002.DAT"))
    vlist = ["m02Dk.Dm", "m02Dk.da", "m02Dk.di", "m02Dk.e", "m02Dk.dr",
             "m02Dk.er", "m02Dw.Ap", "m02Dw.Ip", "m02Dw.Wp", "m02Dw.Wx",
             "m02Dw.pmax"]
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    base_text = KISS_EXAMPLE.read_text("utf-16")
    rows: list[dict] = []
    fit_pts: list[dict] = []
    hold_pts: list[dict] = []
    ksoft = client.Dispatch("KISSsoftCOM.KISSsoft")
    try:
        ksoft.SetSilentMode(True)
        ksoft.GetModule("M02D", True)

        def run(name: str, changes: list[tuple[str, object]]) -> dict:
            text = base_text
            for key, val in changes:
                text = _setkey(text, key, val)
            local = (CASES_DIR / f"scan_{name}.M2D").resolve()
            local.write_text(text, "utf-16")
            ksoft.LoadFile(str(local))
            if not ksoft.CalculateRetVal():
                raise SystemExit(f"scan {name}: CalculateRetVal=False")
            expect = {v: _getvar(ksoft, v) for v in vlist}
            # 与 harvest 同款 fail-fast：缺失变量若流入 rows，对账循环内
            # 以 TypeError/ZeroDivision 远离案源爆出（ocr 交叉审查建议）
            miss = [v for v in vlist if expect[v] is None]
            if miss:
                raise SystemExit(f"scan {name}: 变量缺失 {miss}")
            return {"expect": expect}

        # ① 62 表行（判废行截面量仍有值——pmax 归零不动截面量）
        for i, (d1, d2, d3, ecc, y) in enumerate(p3g):
            r = run(f"p3g_{i:02d}", [("m02Da.RechenMeth", 1),
                                     ("m02Dk.DinIdK", 10010),
                                     ("m02Dk.Dm", repr(d1)),
                                     ("m02Dk.da", repr(d2)),
                                     ("m02Dk.di", repr(d3)),
                                     ("m02Dk.e", repr(ecc)),
                                     ("m02Dk.y", repr(y))])
            e = r["expect"]
            rows.append({"dm": d1, "e": ecc, "di": d3, "da": d2,
                         "wp": e["m02Dw.Wp"], "ap": e["m02Dw.Ap"],
                         "ip": e["m02Dw.Ip"], "w_x": e["m02Dw.Wx"]})
        for i, (da, di, ecc, y) in enumerate(p4c):
            r = run(f"p4c_{i:02d}", [("m02Da.RechenMeth", 1),
                                     ("m02Dk.DinIdK", 10020),
                                     ("m02Dk.da", repr(da)),
                                     ("m02Dk.di", repr(di)),
                                     ("m02Dk.e", repr(ecc)),
                                     ("m02Dk.y", repr(y))])
            e = r["expect"]
            rows.append({"profile": "P4C", "da": da, "di": di, "dm": da / 2 + di / 2,
                         "e": ecc, "wp": e["m02Dw.Wp"], "w_x": e["m02Dw.Wx"],
                         "ap": e["m02Dw.Ap"], "ip": e["m02Dw.Ip"]})
        # ② Wp 一维网格（Dm=45）+ 齐次档
        for ecc in _WP_FIT_ES:
            e = run(f"w3_{ecc:g}", [("m02Da.RechenMeth", 1),
                                     ("m02Dk.Dm", 45),
                                     ("m02Dk.e", repr(ecc))])["expect"]
            fit_pts.append({"dm": e["m02Dk.Dm"], "e": e["m02Dk.e"],
                            "wp": e["m02Dw.Wp"]})
        for ecc in _WP_HOLD_ES:
            e = run(f"w3h_{ecc:g}", [("m02Da.RechenMeth", 1),
                                     ("m02Dk.Dm", 45),
                                     ("m02Dk.e", repr(ecc))])["expect"]
            hold_pts.append({"dm": e["m02Dk.Dm"], "e": e["m02Dk.e"],
                             "wp": e["m02Dw.Wp"]})
        for dm, ecc in ((22.5, 0.8), (90.0, 3.2), (30.0, 32.0 / 30.0),
                        (60.0, 64.0 / 60.0), (36.0, 0.72)):
            e = run(f"w3z_{dm:g}", [("m02Da.RechenMeth", 1),
                                    ("m02Dk.Dm", repr(dm)),
                                    ("m02Dk.e", repr(ecc))])["expect"]
            hold_pts.append({"dm": e["m02Dk.Dm"], "e": e["m02Dk.e"],
                             "wp": e["m02Dw.Wp"]})
    finally:
        try:
            ksoft.ReleaseModule()
        except Exception:  # noqa: BLE001, S110
            pass
    # 收割期对账（62 行全部 + 网格抽点）
    worst = 0.0
    for r in rows:
        if r.get("profile") == "P4C":
            props = ps.section_props("P4C", r["dm"], r["e"], r["di"])
            worst = max(worst, abs(props["wp"] - r["wp"]) / abs(r["wp"]),
                        abs(props["w_x"] - r["w_x"]) / abs(r["w_x"]))
        else:
            props = ps.section_props("P3G", r["dm"], r["e"], r["di"])
            worst = max(worst, abs(props["wp"] - r["wp"]) / abs(r["wp"]),
                        abs(props["ap"] - r["ap"]) / abs(r["ap"]),
                        abs(props["ip"] - r["ip"]) / abs(r["ip"]),
                        abs(props["w_x"] - r["w_x"]) / abs(r["w_x"]))
    for p in fit_pts + hold_pts:
        props = ps.section_props("P3G", p["dm"], p["e"], 1.0)
        worst = max(worst, abs(props["wp"] - p["wp"]) / abs(p["wp"]))
    if worst > 1e-9:
        raise SystemExit(f"截面量对账最坏 {worst:.3e} > 1e-9")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with gzip.open(WP_SCAN, "wt", encoding="utf-8") as fh:
        json.dump({"source": "KISSsoft 2026 M2D COM scan", "xmax": WP_X_MAX,
                   "fit": fit_pts, "holdout": hold_pts, "rows": rows}, fh)
    print(f"→ {WP_SCAN}（fit {len(fit_pts)} + holdout {len(hold_pts)} + "
          f"rows {len(rows)}；对账最坏 {worst:.2e}）")
    return 0


def snapshot_profile() -> int:
    """dat/M02D-001/002.DAT → tools/data/polygon_shaft/polygon_profile.csv。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for (d1, d2, d3, ecc, y) in _read_dat(Path("C:/KISSsoft 2026/dat/M02D-001.DAT")):
        rows.append({"Profile": "P3G", "DM": d1, "DA": d2, "DI": d3,
                     "E": ecc, "Y": y})
    for (da, di, ecc, y) in _read_dat(Path("C:/KISSsoft 2026/dat/M02D-002.DAT")):
        rows.append({"Profile": "P4C", "DM": round((da + di) / 2, 10),
                     "DA": da, "DI": di, "E": ecc, "Y": y})
    with PROFILE_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["Profile", "DM", "DA", "DI", "E", "Y"])
        w.writeheader()
        w.writerows(rows)
    print(f"→ {PROFILE_CSV}（{len(rows)} 行）")
    return 0


def main() -> int:
    if "--sections" in sys.argv:
        return scan_sections()
    if "--profile" in sys.argv:
        return snapshot_profile()
    return harvest()


if __name__ == "__main__":
    sys.exit(main())
