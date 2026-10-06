"""KISSsoft F020 拉伸弹簧收割器：--golden（金样）/ --scan-wire（线材表收割）。

COM 配方（M2A/M2E/M1B 先例固化）：
- Dispatch("KISSsoftCOM.KISSsoft") → SetSilentMode(True) → GetModule("F020")（返回值丢弃，
  全部方法在根对象调用）→ LoadFile(绝对路径，UTF-16 key=value¶ 文件变体) →
  CalculateRetVal()（唯一可信判据）→ GetVarAsJson("f2") 全变量 dump → ReleaseModule。
- F020 机制坑（探针 9 轮钉死，详见 docs/specs/extension-spring-f20.md）：
  判废案部分变量（Rm/tauzul/w/k）仍在 dump；域外 mat.DBID 回落默认行；
  d>7.5 家族须共变（nt+1)·d ≤ LK 保有效；松弛角点曲线≠dat 节点三次（实测 LSQ 入库）。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
KS_EXAMPLE = Path(r"C:\KISSsoft 2026\example\03 Tension Spring.F20")
KS_DAT = Path(r"C:\KISSsoft 2026\dat")
GOLDEN = REPO / "tests/golden/extension_spring/kisssoft_f20.json"
WIRE_OUT = REPO / "tools/data/spring_wire/wire_harvest.json"

# KMAT 弹簧线材真实行（10936–10955；10941 已删除不入库，EN 10089 热成形 10930–10935 内核判废不入库）
WIRE_DBIDS = {
    10936: ("A", "F01-010.dat"), 10937: ("B", "F01-011.dat"),
    10938: ("C", "F01-012.dat"), 10939: ("D", "F01-013.dat"),
    10940: ("X10CrNi 18-8", "F01-014.dat"),
    10942: ("VDC", "F01-019.dat"), 10943: ("VDCrV", "F01-020.dat"),
    10944: ("VDSiCr", "F01-021.dat"), 10945: ("FDC", "F01-016.dat"),
    10946: ("FDCrV", "F01-017.dat"), 10947: ("FDSiCr", "F01-018.dat"),
    10948: ("TDC", "F01-022.dat"), 10949: ("TDCrV", "F01-023.dat"),
    10950: ("TDSiCr", "F01-024.dat"),
    10951: ("SL", "F01-010.dat"), 10952: ("SM", "F01-011.dat"),
    10953: ("SH", "F01-012.dat"), 10954: ("DM", "F01-011.dat"),
    10955: ("DH", "F01-013.dat"),
}
# 松弛角点扫描的 (dat → T 节点)；relData 全零的 dat 不扫
RELAX_DATS = {
    "F01-012.dat": (20.0, 80.0), "F01-013.dat": (20.0, 80.0),
    "F01-014.dat": (80.0, 160.0),
    "F01-016.dat": (20.0, 80.0), "F01-018.dat": (80.0, 160.0),
    "F01-019.dat": (20.0, 80.0), "F01-021.dat": (80.0, 160.0),
    "F01-022.dat": (20.0, 80.0), "F01-023.dat": (80.0, 160.0),
}

MAT_KEYS = ("DBID", "bez", "G", "E", "alphaG", "dmin", "dmax", "rho", "ny",
            "alpha", "typ", "verwendung")

G0, D0, d0, n0, L20 = 81500.0, 32.5, 7.5, 40.3333333, 390.0
W0 = D0 / d0
BODY0 = n0 * d0


def setkey(text: str, key: str, val) -> str:
    sval = "true" if val is True else "false" if val is False else str(val)
    new, cnt = re.subn(rf"^{re.escape(key)}=[^¶\n]*¶", lambda _m: f"{key}={sval}¶",
                       text, flags=re.MULTILINE)
    if cnt != 1:
        raise RuntimeError(f"setkey {key} 命中 {cnt} 次（期望 1）")
    return new


def geom(d: float, s2: float) -> dict:
    """保 w=4.3333 保 R 的 d 扫描几何（n∝d、L2 放长、LH 共变）+ 行程。"""
    D = W0 * d
    n = n0 * (d / d0)
    L2 = L20 + BODY0 * ((d / d0) ** 2 - 1.0) + max(0.0, s2 - 40.0)
    LH = 20.0 * d / d0
    return {"f2.d": d, "f2.D": D, "f2.n": n, "f2.L2": L2, "f2.LH": LH,
            "f2.s2": s2, "f2.F1": 0.0}


def parse_dat(path: Path) -> dict:
    raw = path.read_text("cp1252")
    lines = [ln.strip() for ln in raw.splitlines()
             if ln.strip() and not ln.strip().startswith(("--", "//"))]
    tables, i = {}, 0
    while i < len(lines):
        m = re.match(r":TABLE\s+(FUNCTION|LIST)\s+(\w+)", lines[i])
        if not m:
            i += 1
            continue
        kind, name = m.groups()
        j = i + 1
        meta = []
        while j < len(lines) and not lines[j].upper().startswith("DATA"):
            meta.append(lines[j])
            j += 1
        j += 1
        rows = []
        while j < len(lines) and not lines[j].upper().startswith("END"):
            rows.append([float(x) for x in lines[j].split()])
            j += 1
        tables[name] = {"kind": kind, "meta": meta, "rows": rows}
        i = j
    return tables


def fit_cubic(pts) -> list[float] | None:
    """LSQ rel = aτ + bτ² + cτ³（过原点三次，与引擎一致）。

    自变量按 τ_ref 归一化解病态（τ³ 达 1e7 量级，法方程直接解会丢
    1e-5 精度）；残差超 1e-4 判失败返回 None。
    """
    import numpy as np

    t_ref = max(abs(t) for t, _ in pts)
    x = np.array([t / t_ref for t, _ in pts])
    y = np.array([r for _, r in pts])
    A = np.column_stack([x, x * x, x**3])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    resid = float(np.max(np.abs(A @ coef - y)))
    rel_resid = resid / max(float(np.max(np.abs(y))), 1e-9)
    if rel_resid > 1e-4:
        return None
    a, b, c = coef
    return [a / t_ref, b / t_ref**2, c / t_ref**3]


def _corner_of(corners: dict, key: str, tau: float) -> float:
    co = (corners.get(key) or {}).get("coeffs")
    if not co:
        return 0.0
    return co[0] * tau + co[1] * tau * tau + co[2] * tau**3


def scan_wire(ks, cases_dir: Path) -> dict:
    """KMAT 行 + 松弛角点扫描。"""
    base_text = KS_EXAMPLE.read_text("utf-16")
    out = {"materials": [], "relax": {}}
    # --- KMAT 行 ---
    for dbid in sorted(WIRE_DBIDS):
        text = setkey(base_text, "f2.mat.DBID", dbid)
        path = cases_dir / f"mat_{dbid}.F20"
        path.write_text(text, "utf-16")
        ks.LoadFile(str(path.resolve()))
        retv = ks.CalculateRetVal()
        v = json.loads(ks.GetVarAsJson("f2")).get("return_value") or {}
        m = json.loads(ks.GetVarAsJson("f2.mat")).get("return_value") or {}
        if not m:  # f2.mat 命名空间偶发空——逐键 GetVar 兜底（probe 先例）
            for k in MAT_KEYS:
                try:
                    raw = ks.GetVar(f"f2.mat.{k}")
                except Exception:
                    raw = None
                if raw is not None:
                    txt = str(raw).rstrip("¶").strip()
                    try:
                        m[k] = float(txt)
                    except ValueError:
                        m[k] = txt
        out["materials"].append({
            "dbid": dbid, "grade": WIRE_DBIDS[dbid][0],
            "dat": WIRE_DBIDS[dbid][1], "retv": bool(retv),
            "name": m.get("bez"), "G": m.get("G"), "E": m.get("E"),
            "alphaG": m.get("alphaG"), "dmin": m.get("dmin"), "dmax": m.get("dmax"),
            "rho": m.get("rho"), "datafile": v.get("datafile"),
            "tauzul": v.get("tauzul"), "Rm": v.get("Rm"), "richt": v.get("richt"),
        })
        print(f"[KMAT] {dbid} {WIRE_DBIDS[dbid][0]:10s} {m.get('bez')} "
              f"G={m.get('G')} dat={v.get('datafile')} retv={retv}")
    # --- 松弛角点（每 dat × d∈{1,6} × T∈两节点 × s2 网格）---
    dat2dbid = {dat: dbid for dbid, (_, dat) in WIRE_DBIDS.items()}
    for dat, (t_lo, t_hi) in RELAX_DATS.items():
        dbid = dat2dbid[dat]
        corners = {}
        for d in (1.0, 6.0):
            for tag, T in (("lo", t_lo), ("hi", t_hi)):
                pts = []
                for s2 in (2.0, 5.0, 10.0, 20.0, 40.0):
                    changes = geom(d, s2) | {"f2.temp": T, "f2.mat.DBID": dbid}
                    text = base_text
                    for k, val in changes.items():
                        text = setkey(text, k, val)
                    path = cases_dir / f"rx_{dat}_{d}_{tag}_{s2}.F20"
                    path.write_text(text, "utf-16")
                    ks.LoadFile(str(path.resolve()))
                    retv = ks.CalculateRetVal()
                    v = json.loads(ks.GetVarAsJson("f2")).get("return_value") or {}
                    if not retv or v.get("Rx") is None or not v.get("tau2"):
                        print(f"[RELAX] {dat} d={d} T={T} s2={s2} 判废！")
                        continue
                    pts.append((v["tau2"], v["Rx"]))
                if len(pts) >= 4:
                    co = fit_cubic(pts)
                    corners[f"d{int(d)}_{tag}"] = {
                        "coeffs": co, "pts": [[round(t, 6), round(r, 8)] for t, r in pts]}
                    ok = "OK" if co else "拟合残差超限"
                    print(f"[RELAX] {dat} d={int(d)} T={tag}({T}) n={len(pts)} {ok}")
                else:
                    corners[f"d{int(d)}_{tag}"] = {"coeffs": None, "pts": pts}
        # T 映射（d=7.5、s2=40）：x>0 两点定线 + {80,160} 族 x<0 三点样条
        # （三族映射互不相同：f013 带截距 / 18-8 纯线性 / FDSiCr 下段钳零）
        dbid_mid = dbid
        fpts = []
        for x in ((0.25, 0.5) if t_lo == 20.0 else (-0.75, -0.5, -0.25, 0.25, 0.5)):
            T = t_lo + x * (t_hi - t_lo)
            changes = geom(7.5, 40.0) | {"f2.temp": T, "f2.mat.DBID": dbid_mid}
            text = base_text
            for k, val in changes.items():
                text = setkey(text, k, val)
            path = cases_dir / f"ft_{dat}_x{x}.F20"
            path.write_text(text, "utf-16")
            ks.LoadFile(str(path.resolve()))
            retv = ks.CalculateRetVal()
            v = json.loads(ks.GetVarAsJson("f2")).get("return_value") or {}
            if not retv or v.get("Rx") is None or not v.get("tau2"):
                print(f"[FMAP] {dat} x={x} 判废！")
                continue
            tau = v["tau2"]
            wd = (7.5 - 1.0) / 5.0
            lo = (_corner_of(corners, "d1_lo", tau)
                  + wd * (_corner_of(corners, "d6_lo", tau)
                          - _corner_of(corners, "d1_lo", tau)))
            hi = (_corner_of(corners, "d1_hi", tau)
                  + wd * (_corner_of(corners, "d6_hi", tau)
                          - _corner_of(corners, "d1_hi", tau)))
            fpts.append({"x": x, "F": (v["Rx"] - lo) / (hi - lo)})
            print(f"[FMAP] {dat} x={x:+.2f} T={T:g} Rx={v['Rx']:.6f} F={fpts[-1]['F']:+.6f}")
        out["relax"][dat] = {"t_lo": t_lo, "t_hi": t_hi, "corners": corners,
                             "f_map": fpts}
    return out


def golden_cases() -> dict[str, dict]:
    """金样矩阵：官方算例 + 变体。"""
    cases: dict[str, dict] = {"base": {}}
    for dbid, tag in ((10951, "SL"), (10952, "SM"), (10953, "SH"), (10955, "DH"),
                      (10942, "VDC"), (10947, "FDSiCr"), (10940, "sso18_8"),
                      (10945, "FDC")):
        cases[f"mat_{tag}"] = {"f2.mat.DBID": dbid}
    cases["mode_s1"] = {"f2.belastung0": False, "f2.belastung1": True, "f2.s1": 15}
    cases["mode_F2"] = {"f2.belastung2": False, "f2.belastung3": True, "f2.F2": 800}
    cases["laen0_L0"] = {"f2.LaengeAuswahl": 0, "f2.L0": 360}
    cases["laen1_L1"] = {"f2.LaengeAuswahl": 1, "f2.L1": 380}
    cases["durch0_Di"] = {"f2.DurchmesserAuswahl": 0, "f2.Di": 27}
    cases["f0_200"] = {"f2.F0": 200}
    cases["t_80"] = {"f2.temp": 80}
    cases["static"] = {"f2.belastungsart": 0}
    cases["bench_D40"] = {"f2.D": 40, "f2.F1": 10.0 * G0 * d0**4 / (8 * 40**3 * n0),
                          "f2.herstellungsart": 0}
    cases["d45_f10"] = geom(4.5, 40)
    cases["d45_f1400"] = geom(4.5, 40) | {"f2.F1": 400}
    cases["d65_f1400"] = geom(6.5, 40) | {"f2.F1": 400}
    cases["d25_s10"] = geom(2.5, 10)
    cases["rx_d6_T20"] = geom(6.0, 40)
    cases["rx_d6_T80"] = geom(6.0, 40) | {"f2.temp": 80}
    cases["rx_d1_T20"] = geom(1.0, 2)
    cases["rx_d1_T80"] = geom(1.0, 2) | {"f2.temp": 80}
    cases["rx_d6_T50"] = geom(6.0, 40) | {"f2.temp": 50}
    cases["approx_VDC_f10"] = {"f2.mat.DBID": 10942}
    cases["approx_VDC_f1400"] = {"f2.mat.DBID": 10942, "f2.F1": 400}
    return cases


HARVEST_VARS = [
    "R", "w", "k", "Di", "De", "nt", "LK", "L1", "L2", "s1", "s2", "W1", "W2",
    "Rm", "tauzul", "tau0", "tau1", "tau2", "tauk1", "tauk2", "taukh",
    "taukh_zul", "Fn", "sn", "Ln", "richt", "Rx", "F2Rx", "Gmodul", "F0",
    "F1", "F2", "dynamisch", "gewickelt", "kaltgeformt", "datafile",
]


def harvest(ks, cases_dir: Path) -> dict:
    base_text = KS_EXAMPLE.read_text("utf-16")
    out = {"source": "KISSsoft 2026 F020 官方算例 03 Tension Spring.F20 + 文件变体",
           "harvest": ("GetVarAsJson('f2')（CalculateRetVal 判据）；公式链与容差分档见 "
                       "docs/specs/extension-spring-f20.md"),
           "cases": {}}
    for name, changes in golden_cases().items():
        text = base_text
        for key, val in changes.items():
            text = setkey(text, key, val)
        path = cases_dir / f"golden_{name}.F20"
        path.write_text(text, "utf-16")
        ks.LoadFile(str(path.resolve()))
        retv = ks.CalculateRetVal()
        v = json.loads(ks.GetVarAsJson("f2")).get("return_value") or {}
        if not retv:
            raise SystemExit(f"金样案 {name} 判废（变体 {changes}）——收割中止")
        expect = {k: v[k] for k in HARVEST_VARS if k in v}
        out["cases"][name] = {"changes": changes, "expect": expect}
        print(f"[GOLDEN] {name:18s} R={v['R']:.6f} taukh_zul={v['taukh_zul']} "
              f"Rx={v['Rx']}")
    return out


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else "--golden"
    import pythoncom
    import win32com.client as client

    cases_dir = REPO / "tmp/f20_harvest"
    cases_dir.mkdir(parents=True, exist_ok=True)
    pythoncom.CoInitialize()
    ks = client.Dispatch("KISSsoftCOM.KISSsoft")
    try:
        ks.SetSilentMode(True)
        try:
            ks.GetModule("F020", True)
        except Exception:
            ks.GetModule("F020")
        if mode == "--scan-wire":
            data = scan_wire(ks, cases_dir)
            # 完整性门槛：任一牌号 retv=False / 角点拟合失败 / f_map 不足即中止
            # 不落盘（防止降级快照静默覆盖——VDSiCr/TDC/TDCrV 有松弛数据，降级
            # 会使组件 Rx≡0 无红灯）
            for mat in data["materials"]:
                if not mat.get("retv") or mat.get("G") is None:
                    raise SystemExit(f"KMAT 行 {mat['dbid']} 收割失败：{mat}")
            for dat, rel in data["relax"].items():
                for key, corner in rel["corners"].items():
                    if corner.get("coeffs") is None:
                        raise SystemExit(f"{dat} 角点 {key} 拟合失败（快照不落盘）")
                hi = [p for p in (rel.get("f_map") or []) if p["x"] > 0]
                if len(hi) < 2:
                    raise SystemExit(f"{dat} f_map 正向点不足 2（快照不落盘）")
            WIRE_OUT.parent.mkdir(parents=True, exist_ok=True)
            WIRE_OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False), "utf-8")
            print(f"written {WIRE_OUT}")
        else:
            data = harvest(ks, cases_dir)
            GOLDEN.parent.mkdir(parents=True, exist_ok=True)
            old = json.loads(GOLDEN.read_text("utf-8")) if GOLDEN.exists() else {}
            for k in ("source", "harvest"):
                data[k] = old.get(k, data[k])
            GOLDEN.write_text(json.dumps(data, indent=1, ensure_ascii=False), "utf-8")
            print(f"written {GOLDEN}")
    finally:
        try:
            ks.ReleaseModule()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
