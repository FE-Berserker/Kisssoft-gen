"""KISSsoft M2E 半圆键官方算例金样收割 + dt 行多项式扫描 + DIN 6888 剖面快照。

三件事（对应 docs/specs/woodruff-key-m2e.md）：

1. ``--golden``（默认）：官方算例 ``18 Woodruff Key.M2E`` + 16 个文件变体
   （Reihe B / 小键 / 双键 / 峰值 / 交变 / fL / a0 / D2 语义 / K_A / fS 覆盖）
   经 KISSsoftCOM 全变量收割 → ``tests/golden/woodruff_key/kisssoft_m2e.json``
   （``tests/unit/test_kisssoft_m2e_golden.py`` 对账）。同时为每案计算 Kλ
   锚点（比值三元组 = pyffalo 闭式同表达式，键 = ``m02En.D`` 内核等效直径）
   → ``tools/data/woodruff_key/klambda_anchors.json``，
   ``tools/gen_key_joint_seeds.py`` 并入 ``Key_Joint_KLambda``（Kind=anchor；
   ``klambda()`` 锚点优先精确命中——M2E 与 M2A 内核 Kλ 同曲面，18 坐标
   对照逐位，见 docs/KISSSOFT.md M2E 专项段）。
2. ``--scan-dt``：载荷作用直径 dtW/dtN 的内核式不可解析反推（归一化结构
   ``dtX/dWa = f(htX/dWa, b/dWa)`` 已证、闭式未解）→ 每（Reihe, 剖面行）
   沿 dWa 一元多项式扫描快照 → ``tools/data/woodruff_key/dt_scan.json.gz``
   （网格点进拟合、偏移点进 holdout；seed 期断言 holdout ≤1e-9 与几何
   闭式逐位）。
3. ``--profile``：随包 ``dat/M02E-001.DAT``（Reihe A）/ ``M02E-002.DAT``
   （Reihe B）→ ``tools/data/woodruff_key/din6888_profile.csv``（18 行）。

COM 形态（M2A 配方）：``SetSilentMode(True)`` + ``GetModule("M02E", True)``
+ 文件变体（UTF-16 ``key=value¶`` 行替换，改键必须保留行尾 ¶）+
``CalculateRetVal()`` 唯一可信判据 + ``GetVar`` + ``ReleaseModule``。
**M2E 输入面比 M2A 窄**：几何字段（bKeil/hKeil/DKeil/t1MaxKeil…）与材料
快照（mat.Rp/typ/behandlung）改档无效——内核按 DinIdK+dWa 从 DAT 表重读、
材料 own-input 字段不落盘（三轮探针钉死，勿再走弯路）。

用法::

    python tools/gen_woodruff_key_kisssoft.py               # 金样收割
    python tools/gen_woodruff_key_kisssoft.py --scan-dt
    python tools/gen_woodruff_key_kisssoft.py --profile
"""

from __future__ import annotations

import csv
import gzip
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GOLDEN = REPO / "tests/golden/woodruff_key/kisssoft_m2e.json"
DATA_DIR = REPO / "tools/data/woodruff_key"
ANCHORS = DATA_DIR / "klambda_anchors.json"
DT_SCAN = DATA_DIR / "dt_scan.json.gz"
PROFILE_CSV = DATA_DIR / "din6888_profile.csv"
KISS_DAT_A = Path("C:/KISSsoft 2026/dat/M02E-001.DAT")
KISS_DAT_B = Path("C:/KISSsoft 2026/dat/M02E-002.DAT")
CASES_DIR = REPO / "tmp/m2e_harvest_cases"
KISS_EXAMPLE = Path("C:/KISSsoft 2026/example/18 Woodruff Key.M2E")

#: 金样案（官方算例 + 文件变体；changes = M2E 存档真输入面）
CASES: list[tuple[str, list[tuple[str, object]]]] = [
    ("ex18", []),
    ("reiheb_ex18", [("m02Ek.DinIdK", 10020)]),
    ("dwa_6", [("m02Ew.dWa", 6)]),
    ("dwa_10", [("m02Ew.dWa", 10)]),
    ("dwa_17", [("m02Ew.dWa", 17)]),
    ("dwa_22", [("m02Ew.dWa", 22)]),
    ("dwa_38", [("m02Ew.dWa", 38)]),
    ("reiheb_12", [("m02Ek.DinIdK", 10020), ("m02Ew.dWa", 12)]),
    ("ianz2", [("m02Ea.iANZ", 2)]),
    ("ianz2_dwa38", [("m02Ea.iANZ", 2), ("m02Ew.dWa", 38)]),
    ("mmax", [("m02Ea.Mmax", 600)]),
    ("momart_nw", [("m02Ea.MomArt", 1), ("m02Ea.NW", 1e6)]),
    ("mmax_nl", [("m02Ea.Mmax", 600), ("m02Ea.NL", 1e5)]),
    ("a0_8", [("m02En.a0", 8)]),
    # D 消费语义 = D2（D1=60/D2=50 双非饱和档判别，探针 dnocf 系钉死）
    ("d2_50_38", [("m02Ew.dWa", 38), ("m02En.D2", 50)]),
    ("stoss", [("m02Ea.Mnenn", 200), ("m02Ea.StossFak", 1.5)]),
    ("fs_input", [("m02Ew.isFsInput", "true"), ("m02Ew.fs", 2.0)]),
]

HARVEST_VARS = [
    # 全局载荷与系数
    "m02Ea.L", "m02Ea.Mnenn", "m02Ea.Mmax", "m02Ea.Meq", "m02Ea.MomArt",
    "m02Ea.NL", "m02Ea.NW", "m02Ea.iANZ", "m02Ea.StossFak", "m02Ea.fw",
    "m02Ea.Klamda", "m02Ea.Kphibeq", "m02Ea.Kphibmax",
    # 轴侧
    "m02Ew.dWa", "m02Ew.di", "m02Ew.lW", "m02Ew.htW", "m02Ew.FlacheW",
    "m02Ew.dtW", "m02Ew.alphaW", "m02Ew.Feq", "m02Ew.Fmax", "m02Ew.peq",
    "m02Ew.pmax", "m02Ew.fs", "m02Ew.isFsInput", "m02Ew.fL", "m02Ew.fH",
    "m02Ew.pzul", "m02Ew.Resulteq", "m02Ew.Resultmax", "m02Ew.ResultW",
    "m02Ew.SollS", "m02Ew.mat.Rp", "m02Ew.mat.Rm", "m02Ew.mat.typ",
    "m02Ew.mat.behandlung",
    # 毂侧
    "m02En.lN", "m02En.htN", "m02En.FlacheN", "m02En.dtN", "m02En.alphaN",
    "m02En.Feq", "m02En.Fmax", "m02En.peq", "m02En.pmax", "m02En.fs",
    "m02En.fL", "m02En.fH", "m02En.pzul", "m02En.Resulteq",
    "m02En.Resultmax", "m02En.ResultN", "m02En.D", "m02En.D1", "m02En.D2",
    "m02En.c", "m02En.cFlag", "m02En.a0", "m02En.mat.Rp", "m02En.mat.Rm",
    "m02En.mat.typ", "m02En.mat.behandlung",
    # 键
    "m02Ek.DinIdK", "m02Ek.bKeil", "m02Ek.hKeil", "m02Ek.DKeil",
    "m02Ek.t1MaxKeil", "m02Ek.t2MaxKeil", "m02Ek.PressP", "m02Ek.pzul",
    "m02Ek.fs", "m02Ek.fL", "m02Ek.fH", "m02Ek.Resulteq", "m02Ek.Resultmax",
    "m02Ek.ResultP", "m02Ek.mat.Rp", "m02Ek.mat.Rm", "m02Ek.mat.typ",
    "m02Ek.mat.behandlung",
    # 剖面缓存
    "tm02Et.d", "tm02Et.b", "tm02Et.h", "tm02Et.L", "tm02Et.gd", "tm02Et.t1",
    "tm02Et.t2",
]

#: dt 扫描网格（每剖面行：拟合网格 + holdout 偏移点；行 dWa 覆盖 (lo, hi]）
#: Reihe A/B 各 9 行；行下界取上一行 d + 0.05（行 3 下界 2.05）。
SCAN_ROWS: list[tuple[float, float]] = [
    (2.05, 3.0), (3.05, 4.0), (4.05, 6.0), (6.05, 8.0), (8.05, 10.0),
    (10.05, 12.0), (12.05, 17.0), (17.05, 22.0), (22.05, 38.0),
]

_PROFILE_ROW = re.compile(
    r"^\s*(\d+(?:\.\d*)?)\s+(\d+(?:\.\d*)?)\s+(\d+(?:\.\d*)?)\s+"
    r"(\d+(?:\.\d*)?)\s+(\d+(?:\.\d*)?)\s+(\d+(?:\.\d*)?)\s+"
    r"(\d+(?:\.\d*)?)\s*$")


def _setkey(text: str, key: str, val) -> str:
    """文件变体单键改写（锚定行首；¶ 为 KISSsoft 存档行分隔符 U+00B6）。"""
    out, n = re.subn(rf"^{re.escape(key)}=[^¶]*¶",
                     lambda _m, key=key, val=val: f"{key}={val}¶",
                     text, flags=re.MULTILINE)
    if n != 1:
        raise SystemExit(f"M2E 变体键改写失败 {key}={val}（命中 {n} 处）")
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


def _reihe_of(changes: list[tuple[str, object]]) -> int:
    return 2 if any(k == "m02Ek.DinIdK" and v == 10020 for k, v in changes) else 1


def _klambda_ratios(changes: list[tuple[str, object]], expect: dict) -> dict:
    """Kλ 锚点比值三元组——与组件运行时同表达式（pyffalo 闭式单源）。

    D 取内核等效直径 ``m02En.D``（cFlag=false 下 = D2，判别案钉死）；
    a0 钳位语义与 ``klambda()`` 一致（min(a0/L, 1)）。
    """
    from pyffalo.data.woodruff_key import geometry

    ch = dict(changes)
    d = float(expect.get("m02Ew.dWa") or ch.get("m02Ew.dWa", 30))
    reihe = _reihe_of(changes)
    g = geometry(d, reihe)
    d_eff = expect["m02En.D"]
    a0 = float(expect["m02En.a0"])
    return {"LOverD": g["L"] / d, "DOverD": d_eff / d,
            "A0OverL": min(a0 / g["L"], 1.0)}


def harvest() -> int:
    """金样收割 → tests/golden/woodruff_key/kisssoft_m2e.json + Kλ 锚点。"""
    import win32com.client as client

    from pyffalo.data.woodruff_key import geometry

    CASES_DIR.mkdir(parents=True, exist_ok=True)
    base_text = KISS_EXAMPLE.read_text("utf-16")
    cases: dict[str, dict] = {}
    anchors: dict[str, dict] = {}
    ksoft = client.Dispatch("KISSsoftCOM.KISSsoft")
    try:
        ksoft.SetSilentMode(True)
        ksoft.GetModule("M02E", True)
        for i, (name, changes) in enumerate(CASES):
            text = base_text
            for key, val in changes:
                text = _setkey(text, key, val)
            local = CASES_DIR / f"golden_{i:02d}.M2E"
            local.write_text(text, "utf-16")
            ksoft.LoadFile(str(local))
            if not ksoft.CalculateRetVal():
                raise SystemExit(f"{name}: CalculateRetVal=False")
            expect = {v: _getvar(ksoft, v) for v in HARVEST_VARS}
            missing = [v for v, x in expect.items() if x is None]
            if missing:
                raise SystemExit(f"{name}: 变量缺失 {missing}")
            cases[name] = {"file": "18 Woodruff Key.M2E", "changes": changes,
                           "expect": expect}
            # 几何闭式对账（收割期即断言，防闭式与内核漂移）
            reihe = _reihe_of(changes)
            g = geometry(float(expect["m02Ew.dWa"]), reihe)
            for ours, theirs in (("L", "m02Ea.L"), ("ht_w", "m02Ew.htW"),
                                 ("ht_n", "m02En.htN"),
                                 ("area_w", "m02Ew.FlacheW"),
                                 ("area_n", "m02En.FlacheN")):
                got = expect[theirs]
                if abs(g[ours] - got) > 1e-9 * max(1.0, abs(got)):
                    raise SystemExit(
                        f"{name}: 几何闭式 {ours} 漂移 {g[ours]!r} vs {got!r}")
            ratios = _klambda_ratios(changes, expect)
            anchors[name] = {**ratios, "KLamda": expect["m02Ea.Klamda"]}
            print(f"{name:14s} Kλ={expect['m02Ea.Klamda']!r} "
                  f"dtW={expect['m02Ew.dtW']:.6f} peqW={expect['m02Ew.peq']:.4f}",
                  flush=True)
    finally:
        try:
            ksoft.ReleaseModule()
        except Exception:  # noqa: BLE001, S110
            pass
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(json.dumps({
        "source": "KISSsoft 2026 M02E official example 18 Woodruff Key + "
                  "file variants (DIN 6888 Reihe A/B), COM GetVar",
        "note": "torque Nm; lengths mm; pressure/strength N/mm²; safeties "
                "dimensionless. t1/t2 = profile max values (t1MaxKeil/"
                "t2MaxKeil); Kλ = shared M2A surface (anchor rows); "
                "dtW/dtN = per-row polynomial (holdout ≤1e-9); "
                "k_share(eq/max) = 1 | 13/15 / 1 | 11/15 for 1|2 keys.",
        "harvest": "python tools/gen_woodruff_key_kisssoft.py",
        "cases": cases,
    }, ensure_ascii=False, indent=1), "utf-8")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ANCHORS.write_text(json.dumps({
        "source": "KISSsoft 2026 M2E COM; ratios via pyffalo.data."
                  "woodruff_key closed forms (bit-exact anchor hits)",
        "anchors": anchors,
    }, indent=1), "utf-8")
    print(f"→ {GOLDEN}（{len(cases)} 案）")
    print(f"→ {ANCHORS}（{len(anchors)} 锚点）")
    return 0


def scan_dt() -> int:
    """dtW/dtN 每剖面行稠密扫描 → dt_scan.json.gz（网格 + holdout 偏移点）。

    每行网格 16 点 + holdout 4 点（半步长错位），Reihe A/B 各 9 行
    共 360 案；同点收割 htW/htN/FlächeW/FlächeN 供 seed 期几何闭式逐位断言。
    """
    import win32com.client as client

    from pyffalo.data.woodruff_key import geometry

    CASES_DIR.mkdir(parents=True, exist_ok=True)
    base_text = KISS_EXAMPLE.read_text("utf-16")
    points: list[dict] = []
    failed: list[str] = []
    ksoft = client.Dispatch("KISSsoftCOM.KISSsoft")
    try:
        ksoft.SetSilentMode(True)
        ksoft.GetModule("M02E", True)
        n = 0
        for reihe, dinid in (("A", 10010), ("B", 10020)):
            for row_d, (lo, hi) in zip(
                    (3.0, 4.0, 6.0, 8.0, 10.0, 12.0, 17.0, 22.0, 38.0),
                    SCAN_ROWS, strict=True):
                grid = [lo + (hi - lo) * i / 15 for i in range(16)]
                hold = [lo + (hi - lo) * (i + 0.5) / 16 for i in (1, 5, 9, 13)]
                for kind, d in ([( "grid", g) for g in grid]
                                + [("hold", h) for h in hold]):
                    n += 1
                    tag = f"dt{reihe}_{row_d:g}_{d:.6g}"
                    text = _setkey(base_text, "m02Ew.dWa", repr(round(d, 6)))
                    text = _setkey(text, "m02Ek.DinIdK", dinid)
                    local = CASES_DIR / f"{tag}.M2E"
                    local.write_text(text, "utf-16")
                    ksoft.LoadFile(str(local))
                    if not ksoft.CalculateRetVal():
                        failed.append(tag)
                        continue
                    g = geometry(round(d, 6), 1 if reihe == "A" else 2)
                    points.append({
                        "reihe": 1 if reihe == "A" else 2, "row": row_d,
                        "kind": kind, "dWa": round(d, 6),
                        "DTW": _getvar(ksoft, "m02Ew.dtW"),
                        "DTN": _getvar(ksoft, "m02En.dtN"),
                        "htW": _getvar(ksoft, "m02Ew.htW"),
                        "htN": _getvar(ksoft, "m02En.htN"),
                        "FlW": _getvar(ksoft, "m02Ew.FlacheW"),
                        "FlN": _getvar(ksoft, "m02En.FlacheN"),
                        "Klamda": _getvar(ksoft, "m02Ea.Klamda"),
                        "closure": {"L": g["L"], "ht_w": g["ht_w"],
                                    "ht_n": g["ht_n"], "area_w": g["area_w"],
                                    "area_n": g["area_n"]},
                    })
                    if n % 45 == 0:
                        print(f"  {n}/360 …", flush=True)
    finally:
        try:
            ksoft.ReleaseModule()
        except Exception:  # noqa: BLE001, S110
            pass
    if failed:
        raise SystemExit(f"dt 扫描判废 {len(failed)}: {failed[:8]}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with gzip.open(DT_SCAN, "wt", encoding="utf-8") as fh:
        json.dump({
            "source": "KISSsoft 2026 M2E COM scan (tools/"
                      "gen_woodruff_key_kisssoft.py --scan-dt)",
            "points": points,
        }, fh, ensure_ascii=False)
    print(f"→ {DT_SCAN}（{len(points)} 点）")
    return 0


def extract_profile() -> int:
    """dat/M02E-001/002.DAT（DIN 6888 Reihe A/B）→ din6888_profile.csv。

    列序 d, b, h, L, gd, t1, t2（9 数据行；表头 0/2 行为哑行不入库）。
    """
    rows = []
    for reihe, dat in (("A", KISS_DAT_A), ("B", KISS_DAT_B)):
        for line in dat.read_text(encoding="cp1252",
                                  errors="replace").splitlines():
            m = _PROFILE_ROW.match(line)
            if not m:
                continue
            d, b, h, L, gd, t1, t2 = (float(x) for x in m.groups())
            rows.append([reihe, d, b, h, L, gd, t1, t2])
    if len(rows) != 18:
        raise SystemExit(f"DIN 6888 剖面行数异常：{len(rows)}（应 18 = A9+B9）")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with PROFILE_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Reihe", "DMax", "B", "H", "L", "GD", "T1", "T2"])
        w.writerows(rows)
    print(f"→ {PROFILE_CSV}（{len(rows)} 行）")
    return 0


def main(argv: list[str]) -> int:
    if "--scan-dt" in argv:
        return scan_dt()
    if "--profile" in argv:
        return extract_profile()
    return harvest()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
