"""KISSsoft W7C 推力滑动轴承官方算例金样收割（COM GetVar 逐变量）。

对 2 个官方算例（13 固定面瓦 DIN 31653 / 14 可倾瓦 ISO 12130·DIN 31654）
经 KISSsoftCOM 计算并收割激活轴承全量变量，写
``tests/golden/plain_bearing/kisssoft_w7c.json``。

``--scan`` 模式：推力瓦无量纲特性 COM 扫描（Roller_Chain_Power 口径）。
基算例 13（固定瓦）/ 14（可倾瓦），变 ``Fn``（对数网格，扫 h_min/C_wed
区间）× 变 ``L``/``B``（L/B 节点，L=瓦块周向长度、B=(Do−Di)/2，Do/Di
联动改写、lwed=0.75·L 跟随标准几何），逐点收割维度化输出（hmin/Pf/Q/
TB/fspez 族），快照 ``tools/data/plain_bearing/thrust_chars_scan.json.gz``
供 ``Plain_Thrust_`` 表 seed。

用法::

    python scripts/gen_plain_thrust_kisssoft.py            # 金样收割
    python scripts/gen_plain_thrust_kisssoft.py --scan     # 特性扫描
"""

from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

import pyffalo_root

REPO = pyffalo_root.repo_root()
GOLDEN = REPO / "tests/golden/plain_bearing/kisssoft_w7c.json"
SCAN_OUT = REPO / "tools/data/plain_bearing/thrust_chars_scan.json.gz"
KISS_EXAMPLE = Path("C:/KISSsoft 2026/example")
SCAN_CASES = REPO / "tmp/w7c_scan_cases"

#: 官方算例 → 金样名（W7C 单轴承 Lag[0]）
CASES = [
    ("13 Plain Thrust Bearing (DIN 31653).W7C", "din31653_fixed_13", 0),
    ("14 Plain Thrust Bearing (ISO 12130, DIN 31654).W7C", "iso12130_tilt_14", 0),
]

#: 扫描网格：L/B 节点（L=30 基准，B 由 Do/Di 调出）× Fn 对数网格 [N]
SCAN_LB = (0.5, 0.75, 1.0, 1.5, 2.0)
SCAN_FNS = tuple(round(100.0 * (1.55 ** k)) for k in range(25))

#: 逐点收割变量（KVAR W07C 名录 + 报告模板 PlainThrustBearinge.RPT）
_VARS = (
    "hmin", "Pf", "TB", "Teff", "deltaT", "Q", "Re", "pspez", "pmax",
    "FBst", "fBspez", "fs", "U", "Dm", "e", "cp", "k", "rhoB",
)


def _getvar(ksoft, name: str):
    try:
        raw = ksoft.GetVar(name)
    except Exception:  # noqa: BLE001
        return None
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return str(raw)


def harvest() -> int:
    import win32com.client as client

    cases: dict[str, dict] = {}
    ksoft = client.Dispatch("KISSsoftCOM.KISSsoft")
    try:
        ksoft.SetSilentMode(True)
        ksoft.GetModule("W07C", True)
        for fname, cname, lag in CASES:
            path = KISS_EXAMPLE / fname
            if not path.exists():
                raise SystemExit(f"未找到算例：{path}")
            ksoft.LoadFile(str(path))
            ok = ksoft.CalculateRetVal()
            if not ok:
                raise SystemExit(
                    f"[{cname}] 计算失败（CalculateRetV=False）——"
                    f"{GOLDEN.name} 保持原样，修复后重跑"
                )
            pfx = f"Lag[{lag}]."
            cases[cname] = {
                "file": fname, "bearing": lag,
                "input": {v: _getvar(ksoft, pfx + v) for v in
                          ("Do", "Di", "L", "lwed", "Cwed", "aFst", "Flaeche",
                           "AnzSegmente", "hlim", "M", "kA", "Fn", "Fs")},
                "expect": {**{v: _getvar(ksoft, pfx + v) for v in _VARS},
                           **{g: _getvar(ksoft, g) for g in
                              ("Allg.Drehzahl", "Allg.Tamb", "Allg.Ten",
                               "Allg.Tex", "Allg.Oil.nu40", "Allg.Oil.nu100",
                               "Allg.Oil.roOil", "Allg.WarmeAbfuhr")}},
            }
            e = cases[cname]["expect"]
            print(f"[{cname}] hmin={e.get('hmin')} TB={e.get('TB')} "
                  f"Pf={e.get('Pf')} Q={e.get('Q')} fspez={e.get('fs')} "
                  f"FBst={e.get('FBst')}", flush=True)
    finally:
        try:
            ksoft.ReleaseModule()
        except Exception:  # noqa: BLE001, S110
            pass

    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(
        json.dumps({
            "source": ("KISSsoft 2026 W07C COM GetVar 逐变量收割"
                       "（2026-10-01；官方算例 13/14 原文件）"),
            "note": ("几何 mm、温度 ℃、Pf 为 W（GetVar 原值，非报告 kW）、"
                     "pspez Pa、Q l/min（对流模式 0）；W7C 单轴承 Lag[0]"),
            "cases": cases,
        }, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"{len(cases)} 案 → {GOLDEN}")
    return 0


def scan() -> int:
    """推力瓦特性扫描：两瓦型 × L/B 节点 × Fn 网格 → 快照 JSON.gz。"""
    import win32com.client as client

    base_files = {"fixed": KISS_EXAMPLE / CASES[0][0],
                  "tilt": KISS_EXAMPLE / CASES[1][0]}
    base_texts = {k: p.read_text("utf-16") for k, p in base_files.items()}
    SCAN_CASES.mkdir(parents=True, exist_ok=True)
    curves: dict[str, dict] = {}
    ksoft = client.Dispatch("KISSsoftCOM.KISSsoft")
    try:
        ksoft.SetSilentMode(True)
        ksoft.GetModule("W07C", True)
        for kind, text in base_texts.items():
            for lb in SCAN_LB:
                b = round(30.0 / lb, 4)  # B = L/(L/B)（L=30 基准）
                di = 560.0  # 基准内径，Do = Di + 2B
                do = round(di + 2.0 * b, 4)
                pts: list[dict] = []
                for fn in SCAN_FNS:
                    t = re.sub(r"^Lag\[0\]\.Fn=[^¶]*¶", f"Lag[0].Fn={fn}¶",
                               text, flags=re.MULTILINE)
                    t = re.sub(r"^Lag\[0\]\.Do=[^¶]*¶", f"Lag[0].Do={do}¶",
                               t, flags=re.MULTILINE)
                    t = re.sub(r"^Lag\[0\]\.Di=[^¶]*¶", f"Lag[0].Di={di}¶",
                               t, flags=re.MULTILINE)
                    # 散热面积放大防内核 TB 超限判废——扫描油为恒粘度
                    # （η 与温度无关），gF/gf 特性不受热态影响
                    t = re.sub(r"^Lag\[0\]\.Flaeche=[^¶]*¶",
                               "Lag[0].Flaeche=50¶", t, flags=re.MULTILINE)
                    case = SCAN_CASES / f"scan_{kind}_lb{lb:g}_fn{fn:g}.W7C"
                    case.write_text(t, "utf-16")
                    ksoft.LoadFile(str(case))
                    if not ksoft.CalculateRetVal():
                        continue
                    g = lambda v: _getvar(ksoft, f"Lag[0].{v}")  # noqa: E731
                    hmin = g("hmin")
                    if hmin is None or not (1e-4 < hmin < 10.0):
                        continue
                    rec = {"Fn": fn, "hmin": hmin}
                    for v in _VARS:
                        if v == "hmin":
                            continue
                        val = g(v)
                        if val is not None:
                            rec[v] = val
                    # seed 的 _thrust_rows 依赖 Pf——缺必需量即丢点（其余
                    # 变量如 fs/FBst 为瓦型专属，缺失属正常不强制）
                    if rec.get("Pf") is not None:
                        pts.append(rec)
                pts.sort(key=lambda p: p["hmin"])
                dedup: list[dict] = []
                for p in pts:
                    if dedup and p["hmin"] <= dedup[-1]["hmin"] * 1.000001:
                        continue
                    dedup.append(p)
                if len(dedup) < 6:
                    print(f"{kind} L/B={lb:g}: 点数不足（{len(dedup)}）——跳过",
                          flush=True)
                    continue
                curves[f"{kind}:{lb:g}"] = {"kind": kind, "L_over_B": lb,
                                            "points": dedup}
                hs = [p["hmin"] for p in dedup]
                print(f"{kind} L/B={lb:g}: {len(dedup)} 点，hmin ∈ "
                      f"[{hs[0]:.4g}, {hs[-1]:.4g}] mm", flush=True)
    finally:
        try:
            ksoft.ReleaseModule()
        except Exception:  # noqa: BLE001, S110
            pass

    SCAN_OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(SCAN_OUT, "wt", encoding="utf-8") as fh:
        json.dump({
            "source": ("KISSsoft 2026 W07C COM 扫描（基算例 13 固定瓦 / "
                       "14 可倾瓦，变 Fn × 变 Do/Di（L/B 节点，B=L/(L/B))）"),
            "params": {"L": 30.0, "Z": 24.0, "Di": 560.0, "n": 600.0,
                       "eta": {"fixed": 0.9 * 19.2 / 1000.0,
                               "tilt": 0.9 * 16.9 / 1000.0},
                       "Cwed": {"fixed": 0.05,
                                "tilt": 0.028649538378826978902}},
            "curves": curves,
        }, fh, ensure_ascii=False)
    print(f"扫描完成 → {SCAN_OUT}")
    return 0


if __name__ == "__main__":
    if "--scan" in sys.argv:
        sys.exit(scan())
    sys.exit(harvest())
