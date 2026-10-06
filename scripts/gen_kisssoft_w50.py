"""KISSsoft W50/W51 滚动轴承寿命——金样 dump 与校准扫描（COM 单会话）。

用法（在仓库根，用 venv python）::

    python tools/gen_kisssoft_w50.py --all

- ``--golden``：官方算例 01/02（W050）与 03/04/05（W051）全变量 dump
  → ``tests/golden/bearing_life/kisssoft_w50.json``（金样对账数据）。
- ``--scan``：球 Pref 定律 + 逐切片 aISO 逆向扫描 →
  ``tmp/harvest_w50_scan8.json``（数据收割中间产物，tmp 不入 git；
  历史扫描函数已随数据定稿退役，重收割时按需重接）。

COM 形态（Z91 先例 + 本任务探针 tmp/w51_probe*.py 结论）：
``GetModule(name, True)`` 后 ``LoadFile/Calculate/SetVar/GetVar`` 全在根对象；
``SetVar`` 驱动重算在 W050/W051 均可用（与 Z92 相反）；``Calculate`` 无返回值，
成功判据 = GetVar 值联动。COM 会话占用一个 license 席位。
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import win32com.client

ROOT = Path(__file__).resolve().parents[1]
EX = Path(r"C:\KISSsoft 2026\example")
GOLDEN_OUT = ROOT / "tests" / "golden" / "bearing_life" / "kisssoft_w50.json"
SCAN3_OUT = ROOT / "tmp" / "harvest_w50_scan8.json"

#: W050 金样变量（Lag[0]/Lag[1] 深沟球与圆锥两算例通用；报告模板 W050Le0.RPT 口径）
W050_VARS = (
    "Allg.Drehzahl", "Allg.AxialKraft", "Allg.VorspannFlag",
    "Allg.Vorspannkraft", "Allg.SchragLag", "Allg.AusfallW", "Allg.a1",
    "Allg.ErwLebensd", "Allg.SollLeben", "Allg.Oil.theOil", "Allg.Oil.nu40",
    "Allg.Oil.nu100", "Allg.Oil.contaminationId", "Allg.Oil.s_fac",
    "Lag[0].TypeID", "Lag[0].BFormID", "Lag[0].InnenD", "Lag[0].AussenD",
    "Lag[0].Breite", "Lag[0].Fr", "Lag[0].Fa", "Lag[0].P", "Lag[0].P0",
    "Lag[0].C", "Lag[0].C0", "Lag[0].Cu_considered", "Lag[0].fs",
    "Lag[0].e", "Lag[0].X", "Lag[0].Y", "Lag[0].nu", "Lag[0].nu1",
    "Lag[0].a23", "Lag[0].Lh_basic", "Lag[0].Lh",
    "Lag[0].bearingLubrication.ec", "Lag[0].WinkelBL",
    "Lag[1].TypeID", "Lag[1].Fr", "Lag[1].Fa", "Lag[1].P", "Lag[1].P0",
    "Lag[1].C", "Lag[1].C0", "Lag[1].Cu_considered", "Lag[1].fs",
    "Lag[1].e", "Lag[1].X", "Lag[1].Y", "Lag[1].nu", "Lag[1].nu1",
    "Lag[1].a23", "Lag[1].Lh_basic", "Lag[1].Lh",
    "Lag[1].bearingLubrication.ec",
)

#: W051 金样变量（KVAR W051 字典 + W051Le0.RPT 口径）
W051_VARS = (
    "geometry.Z", "geometry.Dw", "geometry.Dpw", "geometry.Lwe",
    "geometry.Pd", "geometry.Pa", "geometry.ri", "geometry.ro",
    "geometry.cr", "geometry.c0r", "geometry.cu", "geometry.HV",
    "loading.F", "loading.nInnerRing", "loading.failureProbability",
    "loading.aISOmax", "loading.useModifiedLife", "oil.theOil",
    "oil.nu40", "oil.nu100", "oil.contaminationId", "oil.ec",
    "loading.derived.kappa", "loading.derived.nu", "loading.derived.nu1",
    "loading.derived.eC", "loading.derived.Pref", "loading.derived.P0ref",
    "loading.derived.S0ref", "loading.derived.L10r", "loading.derived.L10rh",
    "loading.derived.L10rm", "loading.derived.Lnmrh",
    "loading.derived.pmax_i", "loading.derived.pmax_o", "results[0].aISO",
    "results[0].Pks",
)


def _gv(ks, var):
    try:
        return ks.GetVar(var)
    except Exception as exc:  # noqa: BLE001
        return f"<ERR {exc}>"


def _sv(ks, var, val):
    try:
        ks.SetVar(var, val)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  SetVar {var}={val} ERR {exc}")
        return False


def _calc(ks):
    try:
        ks.Calculate()
    except Exception as exc:  # noqa: BLE001
        print(f"  Calculate ERR {exc}")


def _switch(ks, module):
    """模块切换前 ReleaseModule（tmp/w51_diag.py 结论：跨模块不 Release 则 GetVar 全空）。"""
    try:
        ks.ReleaseModule()
    except Exception as exc:  # noqa: BLE001
        print(f"ReleaseModule ERR（license 席位可能仍占用）: {exc}")
    ks.GetModule(module, True)


def dump_module(ks, module, fname, vars_):
    _switch(ks, module)
    ks.LoadFile(str(fname))
    _calc(ks)
    return {v: _gv(ks, v) for v in vars_}


def run_golden(ks):
    cases = {
        "w50_01_deep_groove": ("W050", EX / "01 Deep Groove.W50"),
        "w50_02_tapered": ("W050", EX / "02 Tapered Roller.W50"),
        "w51_03_ball": ("W051", EX / "03 Deep Groove (Inner Geometry).W51"),
        "w51_04_ball_fs": ("W051", EX / "04 Deep Groove (Fine Sizing).W51"),
        "w51_05_roller": ("W051", EX / "05 Cylindrical Roller (Inner Geometry).W51"),
    }
    out = {}
    for name, (module, fname) in cases.items():
        t0 = time.time()
        vars_ = W050_VARS if module == "W050" else W051_VARS
        out[name] = dump_module(ks, module, fname, vars_)
        print(f"[golden] {name}: {len(out[name])} vars ({time.time()-t0:.1f}s)")
    GOLDEN_OUT.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_OUT.write_text(
        json.dumps({"source": "KISSsoft 2026 COM (PowerShell-free, pywin32)",
                    "harvested": time.strftime("%Y-%m-%d"), "cases": out},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[golden] -> {GOLDEN_OUT}")


def scan_aiso_ball(ks):
    """A. aISO 修正因子曲面（球，03 算例基底，cu_input 手填控 σ、nu40 控 κ）。"""
    rows = []
    _switch(ks, "W051")
    ks.LoadFile(str(EX / "03 Deep Groove (Inner Geometry).W51"))
    _sv(ks, "geometry.cu_input", "true")
    for nu40 in (20, 50, 100, 200, 400):
        nu100 = round(nu40 / 12.571, 3)
        _sv(ks, "oil.nu40", str(nu40))
        _sv(ks, "oil.nu100", str(nu100))
        for cu in (30, 60, 120, 250, 500, 1000, 2000, 4000, 8000):
            _sv(ks, "geometry.cu", str(cu))
            _calc(ks)
            rows.append({
                "nu40": nu40, "cu": cu,
                "kappa": _gv(ks, "loading.derived.kappa"),
                "eC": _gv(ks, "loading.derived.eC"),
                "Pref": _gv(ks, "loading.derived.Pref"),
                "L10r": _gv(ks, "loading.derived.L10r"),
                "L10rm": _gv(ks, "loading.derived.L10rm"),
                "aISO": _gv(ks, "results[0].aISO"),
            })
        print(f"[scan A] nu40={nu40} done ({len(rows)} rows)")
    return rows


def scan_aiso_roller(ks):
    """B. 滚子（05 算例基底）：切力输入 + 修正寿命开，记录全链变量。"""
    rows = []
    _switch(ks, "W051")
    ks.LoadFile(str(EX / "05 Cylindrical Roller (Inner Geometry).W51"))
    _sv(ks, "loading.isForce", "true")
    _sv(ks, "loading.F", "0,7162.055242,18.22356303")
    _sv(ks, "loading.useModifiedLife", "true")
    _sv(ks, "geometry.cu_input", "true")
    for nu40 in (20, 50, 100, 200, 400):
        nu100 = round(nu40 / 12.571, 3)
        _sv(ks, "oil.nu40", str(nu40))
        _sv(ks, "oil.nu100", str(nu100))
        for cu in (60, 125, 250, 500, 1000, 2000, 4000, 8000, 16000):
            _sv(ks, "geometry.cu", str(cu))
            _calc(ks)
            rows.append({
                "nu40": nu40, "cu": cu,
                "kappa": _gv(ks, "loading.derived.kappa"),
                "eC": _gv(ks, "loading.derived.eC"),
                "Pref": _gv(ks, "loading.derived.Pref"),
                "L10r": _gv(ks, "loading.derived.L10r"),
                "L10rm": _gv(ks, "loading.derived.L10rm"),
                "aISO_slices": _gv(ks, "results[0].aISO"),
                "Pks_slices": _gv(ks, "results[0].Pks"),
            })
        print(f"[scan B] nu40={nu40} done ({len(rows)} rows)")
    return rows


def scan_ec_map(ks):
    """C. W050 污染档 0-14 → ec 表值映射（算例 01 基底，Dpw≈60）。"""
    rows = []
    _switch(ks, "W050")
    ks.LoadFile(str(EX / "01 Deep Groove.W50"))
    for cid in range(15):
        _sv(ks, "Allg.Oil.contaminationId", str(cid))
        _calc(ks)
        rows.append({"contaminationId": cid,
                     "ec": _gv(ks, "Lag[0].bearingLubrication.ec"),
                     "nu": _gv(ks, "Lag[0].nu")})
    print("[scan C] done")
    return rows


def scan_viscosity(ks):
    """D. 粘温式 ν(T)：油品 (ν40,ν100) × 温度档，W050 与 W051 各读一次。"""
    rows = []
    oils = ((220, 17.5), (100, 11), (460, 30))
    temps = (40, 50, 60, 70, 80, 100)
    _switch(ks, "W050")
    ks.LoadFile(str(EX / "01 Deep Groove.W50"))
    for nu40, nu100 in oils:
        _sv(ks, "Allg.Oil.nu40", str(nu40))
        _sv(ks, "Allg.Oil.nu100", str(nu100))
        for t in temps:
            _sv(ks, "Allg.Oil.theOil", str(t))
            _calc(ks)
            rows.append({"module": "W050", "nu40": nu40, "nu100": nu100,
                         "T": t, "nu": _gv(ks, "Lag[0].nu")})
    _switch(ks, "W051")
    ks.LoadFile(str(EX / "03 Deep Groove (Inner Geometry).W51"))
    for nu40, nu100 in oils:
        _sv(ks, "oil.nu40", str(nu40))
        _sv(ks, "oil.nu100", str(nu100))
        for t in temps:
            _sv(ks, "oil.theOil", str(t))
            _calc(ks)
            rows.append({"module": "W051", "nu40": nu40, "nu100": nu100,
                         "T": t, "nu": _gv(ks, "loading.derived.nu")})
    print("[scan D] done")
    return rows


def scan_nu1(ks):
    """E. 参考粘度 ν1(n, Dpw)：转速档 × 两模块（Dpw 60 / 46 两个基底）。"""
    rows = []
    for module, fname, var in (
            ("W050", "01 Deep Groove.W50", "Lag[0].nu1"),
            ("W051", "03 Deep Groove (Inner Geometry).W51",
             "loading.derived.nu1")):
        _switch(ks, module)
        ks.LoadFile(str(EX / fname))
        for n in (100, 300, 600, 980, 1500, 3000, 6000):
            if module == "W050":
                _sv(ks, "Allg.Drehzahl", str(n))
            else:
                _sv(ks, "loading.nInnerRing", str(n))
            _calc(ks)
            rows.append({"module": module, "n": n, "nu1": _gv(ks, var)})
    print("[scan E] done")
    return rows




SIGMA_CU = (15, 25, 40, 60, 100, 160, 250, 400, 650, 1000, 1600, 2500,
            4000, 6500, 10000, 16000, 25000, 40000)
KAPPA_NU40 = (10, 20, 40, 80, 130, 200, 320, 500, 800)


def scan_aiso_dense(ks):
    """F. aISO 曲面加密（W051 球 03 / 滚子 05，14 σ 档 × 9 κ 档）。"""
    rows = []
    for tag, fname, force in (
            ("ball", "03 Deep Groove (Inner Geometry).W51", None),
            ("roller", "05 Cylindrical Roller (Inner Geometry).W51",
             ("0,7162.055242,18.22356303", "true"))):
        _switch(ks, "W051")
        ks.LoadFile(str(EX / fname))
        if force:
            _sv(ks, "loading.isForce", "true")
            _sv(ks, "loading.F", force[0])
            _sv(ks, "loading.useModifiedLife", "true")
        _sv(ks, "geometry.cu_input", "true")
        for nu40 in KAPPA_NU40:
            _sv(ks, "oil.nu40", str(nu40))
            _sv(ks, "oil.nu100", str(round(nu40 / 12.571, 3)))
            for cu in SIGMA_CU:
                _sv(ks, "geometry.cu", str(cu))
                _calc(ks)
                rows.append({
                    "type": tag, "nu40": nu40, "cu": cu,
                    "kappa": _gv(ks, "loading.derived.kappa"),
                    "eC": _gv(ks, "loading.derived.eC"),
                    "Pref": _gv(ks, "loading.derived.Pref"),
                    "L10r": _gv(ks, "loading.derived.L10r"),
                    "L10rm": _gv(ks, "loading.derived.L10rm"),
                })
            print(f"[scan F] {tag} nu40={nu40} done ({len(rows)} rows)")
    return rows


def scan_ec_dp(ks):
    """G. eC 污染档 × Dpw 断点表（W051 03 基底；Dpw 变更后 cr 等会重算，
    只取 eC 与 Dpw 读数）。"""
    rows = []
    _switch(ks, "W051")
    ks.LoadFile(str(EX / "03 Deep Groove (Inner Geometry).W51"))
    for cid in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14):
        _sv(ks, "oil.contaminationId", str(cid))
        for dpw in (30, 46, 60, 80, 95, 120, 160, 220):
            _sv(ks, "geometry.Dpw", str(dpw))
            _calc(ks)
            rows.append({"contaminationId": cid, "Dpw": dpw,
                         "eC": _gv(ks, "loading.derived.eC"),
                         "Dpw_read": _gv(ks, "geometry.Dpw")})
        print(f"[scan G] id={cid} done")
    _sv(ks, "geometry.Dpw", "46")
    return rows


def scan_viscosity2(ks):
    """H. ν(T) 拟合数据（W051 03 基底，(ν40,ν100) × T → derived.nu 实测）。"""
    rows = []
    _switch(ks, "W051")
    ks.LoadFile(str(EX / "03 Deep Groove (Inner Geometry).W51"))
    for nu40, nu100 in ((50, 4), (100, 8), (220, 17.5), (460, 36.6),
                        (680, 54)):
        _sv(ks, "oil.nu40", str(nu40))
        _sv(ks, "oil.nu100", str(nu100))
        for t in (30, 40, 50, 60, 70, 80, 90, 100, 120):
            _sv(ks, "oil.theOil", str(t))
            _calc(ks)
            rows.append({"nu40": nu40, "nu100": nu100, "T": t,
                         "nu": _gv(ks, "loading.derived.nu")})
        print(f"[scan H] nu40={nu40} done")
    return rows


def scan_w50_a23(ks):
    """I. W050 目录法 a23 曲面（01 基底：Fr × nu40 → a23/Lh/Lh_basic/P/ec）。"""
    rows = []
    _switch(ks, "W050")
    ks.LoadFile(str(EX / "01 Deep Groove.W50"))
    for nu40 in (20, 60, 130, 300):
        _sv(ks, "Allg.Oil.nu40", str(nu40))
        _sv(ks, "Allg.Oil.nu100", str(round(nu40 / 12.571, 3)))
        for fr in (500, 1000, 2000, 3127.5, 5000, 8000):
            _sv(ks, "Lag[0].Fr", str(fr))
            _calc(ks)
            rows.append({
                "nu40": nu40, "Fr": fr,
                "kappa": _gv(ks, "Lag[0].nu") and None,
                "nu": _gv(ks, "Lag[0].nu"), "nu1": _gv(ks, "Lag[0].nu1"),
                "P": _gv(ks, "Lag[0].P"), "ec": _gv(ks,
                                                    "Lag[0].bearingLubrication.ec"),
                "a23": _gv(ks, "Lag[0].a23"),
                "Lh_basic": _gv(ks, "Lag[0].Lh_basic"),
                "Lh": _gv(ks, "Lag[0].Lh"),
            })
        print(f"[scan I] nu40={nu40} done")
    return rows




_KAPPA_TARGETS = (4.0, 3.0, 2.2, 1.6, 1.2, 0.9, 0.65, 0.5)
_NU_T = ((30, 425.09175880), (40, 220.0), (50, 124.31183460),
         (60, 75.59145523), (70, 48.88395324), (80, 33.29464970),
         (90, 23.69309248), (100, 17.5), (120, 10.45389136))


def _T_for_nu(nu_target: float):
    """由 ν(T) 实测曲线（nu40=220 库油）log-log 反解温度 [℃]。"""
    import math
    ts = [t for t, _ in _NU_T]
    vs = [v for _, v in _NU_T]
    for k in range(len(vs) - 1):
        if vs[k + 1] <= nu_target <= vs[k]:
            f = ((math.log(nu_target) - math.log(vs[k + 1]))
                 / (math.log(vs[k]) - math.log(vs[k + 1])))
            return round(ts[k + 1] + f * (ts[k] - ts[k + 1]), 1)
    return None


def scan_aiso_temp(ks):
    """J. aISO 曲面（theOil 控 κ——nu40 SetVar 无效、温度有效，第四轮）。

    球 03（n=1500，ν1≈17.13）/ 滚子 05（n=1000，ν1≈14.60），
    κ 档 {4…0.5} × σ 档（cu 14 档）。
    """
    rows = []
    for tag, fname, nu1, force in (
            ("ball", "03 Deep Groove (Inner Geometry).W51", 17.1312, None),
            ("roller", "05 Cylindrical Roller (Inner Geometry).W51",
             14.6010, ("0,7162.055242,18.22356303", "true"))):
        for kp in _KAPPA_TARGETS:
            t = _T_for_nu(kp * nu1)
            if t is None:
                print(f"[scan J] {tag} kappa={kp} 超温度域，跳过")
                continue
            _switch(ks, "W051")
            ks.LoadFile(str(EX / fname))
            if force:
                _sv(ks, "loading.isForce", "true")
                _sv(ks, "loading.F", force[0])
                _sv(ks, "loading.useModifiedLife", "true")
            _sv(ks, "geometry.cu_input", "true")
            _sv(ks, "oil.theOil", str(t))
            for cu in SIGMA_CU:
                _sv(ks, "geometry.cu", str(cu))
                _calc(ks)
                rows.append({
                    "type": tag, "T": t, "cu": cu,
                    "kappa": _gv(ks, "loading.derived.kappa"),
                    "eC": _gv(ks, "loading.derived.eC"),
                    "Pref": _gv(ks, "loading.derived.Pref"),
                    "L10r": _gv(ks, "loading.derived.L10r"),
                    "L10rm": _gv(ks, "loading.derived.L10rm"),
                })
            kp_read = rows[-1]["kappa"] if rows else "?"
            print(f"[scan J] {tag} kappa~{kp} (T={t}) done -> {kp_read}")
    return rows




def scan_ec_dp_roller(ks):
    """K. eC 污染档 × Dpw（滚子表，05 基底——eC 闭式分球/滚子，J 轮教训）。"""
    rows = []
    _switch(ks, "W051")
    ks.LoadFile(str(EX / "05 Cylindrical Roller (Inner Geometry).W51"))
    for cid in range(15):
        _sv(ks, "oil.contaminationId", str(cid))
        for dpw in (30, 46, 60, 80, 95, 120, 160, 220):
            _sv(ks, "geometry.Dpw", str(dpw))
            _calc(ks)
            rows.append({"contaminationId": cid, "Dpw": dpw,
                         "eC": _gv(ks, "loading.derived.eC")})
        print(f"[scan K] roller id={cid} done")
    return rows




def scan_pref_law(ks):
    """L. Pref 反推：Fr 幂律 × 游隙影响 × 逐滚子变量探测（05 滚子基底）。"""
    rows = []
    _switch(ks, "W051")
    ks.LoadFile(str(EX / "05 Cylindrical Roller (Inner Geometry).W51"))
    _sv(ks, "loading.isForce", "true")
    _sv(ks, "loading.useModifiedLife", "true")
    # 逐滚子变量名探测
    for probe in ("results[0].elementResults[0].p_max",
                  "results[0].elementResults[0].F",
                  "results[0].elementResults[0].Fy",
                  "results[0].elementResults[19].p_max",
                  "results[0].elementResults[19].Fy"):
        print(f"[probe] {probe} = {_gv(ks, probe)!r}"[:100])
    for pd in ("-0.02", "0", "0.02", "0.05"):
        _sv(ks, "geometry.Pd", pd)
        for fr in (2000.0, 4000.0, 7162.055242, 10000.0, 15000.0):
            _sv(ks, "loading.F", f"0,-{fr},0")
            _calc(ks)
            rows.append({
                "Pd_mm": float(pd), "Fr": fr,
                "Pref": _gv(ks, "loading.derived.Pref"),
                "P0ref": _gv(ks, "loading.derived.P0ref"),
                "L10r": _gv(ks, "loading.derived.L10r"),
                "pmax_i": _gv(ks, "loading.derived.pmax_i"),
                "pmax_o": _gv(ks, "loading.derived.pmax_o"),
            })
        print(f"[scan L] Pd={pd} done")
    return rows




def scan_ball_pref(ks):
    """M. 球 Pref 定律（03 基底：Pd × Fr 网格 → Pref/P0ref/L10r）。"""
    rows = []
    _switch(ks, "W051")
    ks.LoadFile(str(EX / "03 Deep Groove (Inner Geometry).W51"))
    _sv(ks, "loading.isForce", "true")
    _sv(ks, "loading.useModifiedLife", "true")
    for pd in ("-0.02", "0", "0.013", "0.025", "0.05"):
        _sv(ks, "geometry.Pd", pd)
        for fr in (200.0, 400.0, 992.0, 2000.0, 4000.0):
            _sv(ks, "loading.F", f"0,-{fr},0")
            _calc(ks)
            rows.append({"Pd_mm": float(pd), "Fr": fr,
                         "Pref": _gv(ks, "loading.derived.Pref"),
                         "P0ref": _gv(ks, "loading.derived.P0ref"),
                         "L10r": _gv(ks, "loading.derived.L10r")})
        print(f"[scan M] ball Pd={pd} done")
    return rows


def scan_slice_aiso(ks):
    """N. 逐切片 aISO 逆向（05 基底：cu 档 → aISO/Pks 41 元数组）。"""
    rows = []
    _switch(ks, "W051")
    ks.LoadFile(str(EX / "05 Cylindrical Roller (Inner Geometry).W51"))
    _sv(ks, "loading.isForce", "true")
    _sv(ks, "loading.F", "0,-7162.055242,18.22356303")
    _sv(ks, "geometry.cu_input", "true")
    for cu in (5000, 10000, 25417, 50000):
        _sv(ks, "geometry.cu", str(cu))
        _calc(ks)
        rows.append({"cu": cu, "kappa": _gv(ks, "loading.derived.kappa"),
                     "eC": _gv(ks, "loading.derived.eC"),
                     "Pref": _gv(ks, "loading.derived.Pref"),
                     "L10r": _gv(ks, "loading.derived.L10r"),
                     "L10rm": _gv(ks, "loading.derived.L10rm"),
                     "aISO": _gv(ks, "results[0].aISO"),
                     "Pks": _gv(ks, "results[0].Pks")})
        print(f"[scan N] cu={cu} done")
    return rows


def run_scan(ks):
    out = {
        "ball_pref": scan_ball_pref(ks),
        "slice_aiso": scan_slice_aiso(ks),
    }
    SCAN3_OUT.parent.mkdir(parents=True, exist_ok=True)
    SCAN3_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    print(f"[scan] -> {SCAN3_OUT}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", action="store_true")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    if not (args.all or args.golden or args.scan):
        ap.error("需 --golden / --scan / --all 之一")
    ks = win32com.client.Dispatch("KISSsoftCOM.KISSsoft")
    try:
        ks.SetSilentMode(True)
        if args.all or args.golden:
            run_golden(ks)
        if args.all or args.scan:
            run_scan(ks)
    finally:
        try:
            ks.ReleaseModule()
        except Exception as exc:  # noqa: BLE001
            print("ReleaseModule ERR:", exc)


if __name__ == "__main__":
    main()
