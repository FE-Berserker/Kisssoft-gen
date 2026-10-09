"""K17 Plastics Manager 金样收割器（官方算例 + 合成统计案 + 几何/传热变体）。

产物：pyffalo ``tests/golden/plastic_gear/kisssoft_k17.json``。

反直觉发现（docstring 留档，回灌 KISSSOFT.md 专项节）：

1. m0（VDI 2736-4）的换算是**幂律** ``lgN_P = lgN_50·(1 − z_P·κ)``，κ =
   全表各合并级 ``s(lgN)/lgN_50`` 均值——**不是**教科书「均值 − z·s」；
2. z 表为 4 位半格值表（5%: 1.6450 ≠ 95%: 1.6445，表源非对称），
   节点间按精确 z 比例内插后收 4 位小数（dp7.3 → 1.4540 钉死）；
3. 齿根应力用**失效轮齿宽**（b1 变体零影响），齿面用共同齿宽
   ``min(b1,b2)``（扫描钉死）；
4. K17 变体每温度族须 ≥ 2 个扭矩级，单级表 retval=True 但 root 全空；
5. 表行 ambientT > 某行 rootTfailed 时整体判废（温差为负）；
6. m2（Weibull RLS）实测分位曲线无法被任何标准 2P Weibull 复现
   （中段 ±1.4e-3、尾段 −14%），金样容差放宽档记录；
7. 传热系数 R* 在 μ≠0.32 有折点行为（K 可为负），主结构仅在
   μ=0.32 家族内逐位。

用法（本 skill 根目录）::

    python scripts/gen_plastics_manager_kisssoft.py [pyffalo_root]

COM 每次调用占一个 license 席位；断点重跑安全（案全过才写盘）。
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pyffalo_root import repo_root  # noqa: E402

import win32com.client  # noqa: E402

PYFFALO = repo_root()
GOLDEN = PYFFALO / "tests" / "golden" / "plastic_gear" / "kisssoft_k17.json"
HARVEST = "python scripts/gen_plastics_manager_kisssoft.py"

EX = Path(r"C:\KISSsoft 2026\example")
BASE_K17 = EX / "09 Plastics Manager.K17"
BASE_Z12 = EX / "test_gears.Z12"
_SEP = "\u00b6"  # ¶


# ---------------------------------------------------------------- 文件变体

def _read_u16(p: Path) -> str:
    return p.read_bytes().decode("utf-16-le")


def rep_key(text: str, key: str, val: str) -> str:
    pat = re.compile(rf"(?<![^{_SEP}\r\n]){re.escape(key)}=[^{_SEP}\r\n]*")
    hits = pat.findall(text)
    if len(hits) != 1:
        raise SystemExit(f"判废：{key} 命中 {len(hits)} 次")
    return pat.sub(key + "=" + val, text)


def replace_table(text: str, rows: list[dict]) -> str:
    lines = re.split(_SEP + "\r\n", text)
    out = [ln for ln in lines if not re.match(r"^table\[\d+\]\.", ln)]
    new_rows = []
    for i, r in enumerate(rows):
        for k, v in [("isActive", "true"), ("FileName", ""), ("T", r["T"]),
                     ("n", r["n"]), ("nL", r["nL"]), ("ambientT", r["ambientT"]),
                     ("rootTfailed", r["rootTfailed"]),
                     ("flankTfailed", r["flankTfailed"]), ("failedGear", "0"),
                     ("failureMethod", "1"), ("counterGear", "0"),
                     ("Wear", "0"), ("flankTcounter", "0"), ("oilT", "0")]:
            new_rows.append(f"table[{i}].{k}={v}")
    idx = next(i for i, ln in enumerate(out) if ln.startswith("testFile="))
    return (_SEP + "\r\n").join(out[:idx] + new_rows + out[idx:])


# ---------------------------------------------------------------- COM

def _gv(k, name):  # noqa: ANN001
    try:
        v = k.GetVar(name)
        return None if v in (None, "") else v
    except Exception:
        return None


def run_k17(k, case: Path, root_n: int = 14) -> dict:  # noqa: ANN001
    k.GetModule("K017", True)
    k.LoadFile(str(case))
    if not k.CalculateRetVal():
        raise SystemExit(f"判废：{case.name} CalculateRetVal=False")
    rows = []
    for i in range(root_n):
        row = {}
        for f in ["sigF0", "T", "n", "nLmod", "rootTfailed", "rootK"]:
            v = _gv(k, f"root[{i}].{f}")
            if v is not None:
                row[f] = float(v)
        v = _gv(k, f"root[{i}].list")
        if v is not None:
            row["list"] = v
        if not row:
            break
        rows.append(row)
    groups = []
    for i in range(8):
        t_, l_ = _gv(k, f"listRoot[{i}].temp"), _gv(k, f"listRoot[{i}].list")
        if t_ is None:
            break
        groups.append([float(t_), l_])
    return {"root": rows, "listRoot": groups}


# ---------------------------------------------------------------- 覆盖矩阵

def synthetic_rows_2level(vals1: list[float], vals2: list[float]) -> list[dict]:
    """两组同温水平（保证 ≥2 应力级）——合成统计案表体。"""
    rows = []
    for v in vals1:
        rows.append({"T": "1.0", "n": "1000", "nL": repr(v), "ambientT": "20",
                     "rootTfailed": "100", "flankTfailed": "100"})
    for v in vals2:
        rows.append({"T": "1.2", "n": "1000", "nL": repr(v), "ambientT": "20",
                     "rootTfailed": "100", "flankTfailed": "100"})
    return rows


def main() -> None:
    k17_text = _read_u16(BASE_K17)
    z12_text = _read_u16(BASE_Z12)
    cases: dict[str, dict] = {}
    meta: dict[str, dict] = {}

    k = win32com.client.Dispatch("KISSsoftCOM.KISSsoft")
    try:
        k.SetSilentMode(True)

        # ---- 1. 官方算例（统计/结构/传热主基准，dp=10/m0）----
        res = run_k17(k, BASE_K17)
        cases["base"] = res
        meta["base"] = {"desc": "官方算例 09 Plastics Manager（24 行/12 合并对/3 温度组）"}

        # ---- 2. 统计矩阵（官方表 × dp × method）----
        for dp in ["1", "5", "10", "50", "90", "99"]:
            for m in ["0", "1", "2"]:
                t = rep_key(rep_key(k17_text, "damageProbability", dp),
                            "statisticalMethod", m)
                f = EX / "_hv_stat.K17"
                f.write_bytes(t.encode("utf-16-le"))
                cases[f"stat_m{m}_dp{dp}"] = run_k17(k, f, root_n=3)
                f.unlink(missing_ok=True)
        meta["stat"] = {"desc": "官方表 × 统计方法 m0/m1/m2 × 损伤概率（root 前 3 行）"}

        # ---- 3. 合成统计案（A/P/Q/R：估计器消歧证据链）----
        synth = {
            "synA": synthetic_rows_2level([1.0, 2.0, 4.0], [0.5, 1.0, 2.0]),
            "synP": synthetic_rows_2level([1.0, 2.0, 4.0], [0.5, 0.55, 0.6]),
            "synQ": synthetic_rows_2level([1.0, 1.05, 1.1], [0.5, 1.0, 2.0]),
            "synR": (synthetic_rows_2level([1.0, 2.0, 4.0], [0.5, 1.0, 2.0])
                     + synthetic_rows_2level([1.2, 1.44], [0.6, 0.72])),
        }
        # synR 重构为三水平（1.0/1.15/1.3）：直接替换
        synR_rows = []
        for v in [1.0, 2.0, 4.0]:
            synR_rows.append({"T": "1.0", "n": "1000", "nL": repr(v),
                              "ambientT": "20", "rootTfailed": "100",
                              "flankTfailed": "100"})
        for v in [1.0, 1.2, 1.44]:
            synR_rows.append({"T": "1.15", "n": "1000", "nL": repr(v),
                              "ambientT": "20", "rootTfailed": "100",
                              "flankTfailed": "100"})
        for v in [1.0, 1.05, 1.1]:
            synR_rows.append({"T": "1.3", "n": "1000", "nL": repr(v),
                              "ambientT": "20", "rootTfailed": "100",
                              "flankTfailed": "100"})
        synth["synR"] = synR_rows
        for name, rows in synth.items():
            for m in ["0", "1", "2"]:
                t = rep_key(replace_table(k17_text, rows), "statisticalMethod", m)
                f = EX / "_hv_synth.K17"
                f.write_bytes(t.encode("utf-16-le"))
                cases[f"{name}_m{m}"] = run_k17(k, f, root_n=3)
                f.unlink(missing_ok=True)
        meta["synth"] = {"desc": "合成两/三水平表（κ 估计器与三方法消歧）"}

        # ---- 4. 几何变体（应力链方向性：b2/b1/x2/x1/a）----
        geo = {
            "geo_b2p7": {"ZR[1].b": "7"},
            "geo_b1p10": {"ZR[0].b": "10"},
            "geo_x2z0": {"ZR[1].x.nul": "0"},
            "geo_x1z0": {"ZR[0].x.nul": "0"},
            "geo_a28": {"ZP[0].a": "28"},
        }
        for name, ch in geo.items():
            z = EX / "_hv_gear.Z12"
            z.write_bytes(rep_key_multi(z12_text, ch).encode("utf-16-le"))
            t = rep_key(k17_text, "testFile", z.name)
            f = EX / "_hv_geo.K17"
            f.write_bytes(t.encode("utf-16-le"))
            cases[name] = run_k17(k, f, root_n=3)
            f.unlink(missing_ok=True)
            z.unlink(missing_ok=True)
        meta["geo"] = {"desc": "试验齿轮几何变体（σF0/T 系数：b2 反比 / b1 无关 / x 敏感）"}

        # ---- 5. 传热矩阵（μ/n/POT/Rth）----
        thermal: dict[str, dict[str, str]] = {
            "th_mu016": {"COFdry": "0.16"}, "th_mu064": {"COFdry": "0.64"},
            "th_POT50": {"PowerOnTime": "50"}, "th_POT25": {"PowerOnTime": "25"},
            "th_Rth0025": {"HeatTransferResistance": "0.025"},
            "th_Rth010": {"HeatTransferResistance": "0.1"},
        }
        for name, ch in thermal.items():
            t = k17_text
            for kk, vv in ch.items():
                t = rep_key(t, kk, vv)
            f = EX / "_hv_th.K17"
            f.write_bytes(t.encode("utf-16-le"))
            r = run_k17(k, f, root_n=1)
            cases[name] = {"root": r["root"][:1]}
            f.unlink(missing_ok=True)
        # n 变体（24 行逐个替换）
        for nn in ["500", "2000"]:
            t = k17_text
            for i in range(24):
                t = rep_key(t, f"table[{i}].n", nn)
            f = EX / "_hv_thn.K17"
            f.write_bytes(t.encode("utf-16-le"))
            r = run_k17(k, f, root_n=1)
            cases[f"th_n{nn}"] = {"root": r["root"][:1]}
            f.unlink(missing_ok=True)
        meta["thermal"] = {"desc": "传热系数矩阵（μ=0.32 家族内主结构；μ 家族外已知折点）"}
    finally:
        k.ReleaseModule()

    # ---- 健全性过滤：全案 root 非空（thermal 单行案）----
    for name, c in cases.items():
        if not c.get("root"):
            raise SystemExit(f"判废：{name} 无合并行")
        for r in c["root"]:
            for fld in ["nLmod", "rootK"]:
                if r.get(fld) is None:
                    raise SystemExit(f"判废：{name}.{fld} 为 None")

    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(json.dumps({
        "source": "KISSsoft 2026 K17 Plastics Manager COM（官方算例 + 文件变体，"
                  "2026-10-09 收割）",
        "note": "统计 m0/m1 与传热 μ=0.32 家族逐位；σ 链基准几何 0.2%、几何变体"
                "放宽档（YF 齿条式 vs KISSsoft VDI 2736C）；m2 中段 ±5e-3 尾段"
                "放宽（KISSsoft 曲线非标准 2P Weibull，见 spec）；μ≠0.32 传热"
                "R* 折点记已知偏差",
        "harvest": HARVEST,
        "base_gear": {"Mn": 1.0, "Alphan": 20.0, "Z1": 17, "Z2": 39,
                      "x1": 0.2045, "x2": -0.313835, "a": 27.99,
                      "b1": 8.0, "b2": 6.0, "E1": 206000.0, "E2": 2077.9,
                      "FailureGear": 2},
        "meta": meta,
        "cases": cases,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK: {len(cases)} 案 -> {GOLDEN}")


def rep_key_multi(text: str, changes: dict[str, str]) -> str:
    for kk, vv in changes.items():
        text = rep_key(text, kk, vv)
    return text


if __name__ == "__main__":
    main()
