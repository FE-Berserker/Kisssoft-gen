"""KISSsoft W10 轴强度 COM 收割器（shaft-strength-w10）。

经 ``KISSsoftCOM.KISSsoft`` 收割 W10（轴强度 DIN 743 / FKM）的系数与金样：

- ``probe``：license / 官方算例核心量自检；
- ``section``：官方算例（或其变体）逐校核截面全变量金样 JSON（B2 金样主源）；
- ``scan-shoulder``：轴肩缺口系数 βk(D/d, r/d, Rm) 网格 → CSV；
- ``scan-const``：固定值缺口（键槽 Form 4 / 过盈 Form 3 子型 × Rm）→ CSV；
- ``scan-size``：尺寸系数 K1/K2 随截面直径 d（× CrNiMo 钢型）→ CSV；
- ``scan-surface``：表面系数 KFσ(Rm)（默认加工 Rz=16 档）→ CSV（Rz 维度
  走 DIN 743 标准公式 + 本切片对账，见下「Rz 通道」）。

COM 机制坑（实测 2026-10-01，固化勿绕）：

1. **根对象直调**：``GetModule('W010', True)`` 的返回值在类型库标注为
   VT_VOID 且实际 VARIANT 亦为空（makepy/raw Invoke 均拿不到模块对象）；
   ``LoadFile`` / ``Calculate`` / ``GetVar`` / ``SetVar`` / ``ReleaseModule``
   全部在**根对象**上调用即可，模块对象不需要。
2. **SetVar 陈旧值陷阱**（Z92 教训的 W10 翻版）：``SetVar`` 后 ``Calculate``
   返回 True 但结果不刷新（读回是新值、系数是旧值）——一律走**文件变体
   路线**：改 UTF-16 文本键（紧凑 ``key=value¶`` 格式，**等号两侧无空格**，
   值尾 ``¶``）→ ``LoadFile`` 全新状态 → ``Calculate``。
2b. **材料变体双坑**：``shafts[0].material.DBID`` 在文件里出现**两次**，
   只换第一处时 LoadFile 按第二处的库 ID 从材料库重读、覆盖全部快照
   数值（症状：任何材料改写都无效、Kf/KF 跨 Rm 逐位不变）——须两处全
   换为 19999（Eigene Eingabe 自定义档），此时快照数值（Rm/Rp/dinsigb/
   dinsigs/dinsigzdw/dinsigbw/dintautw）才是权威；收割器以 dinsigb 读回
   作材料锚键。
3. **静默回退**：COM 服务进程跨客户端持久，``LoadFile`` 解析失败时保留上
   一文件状态——每次 ``LoadFile`` 后先读回锚键确认变体生效再 ``Calculate``；
   ``CalculateRetVal`` 为唯一可信判据（False 的点记 ``ok=False`` 丢弃）。
4. **Rz 通道**：截面粗糙度输入是「加工方式」枚举（``Qu[i].OberName`` 派生
   显示，文件里只有内部 DB ID），``Qu[i].Rz`` 为派生值（SetVar/SaveFile 均
   不持久化）——Rz 维度不可 COM 扫描，KFσ 的 Rz 依赖按 DIN 743 标准公式
   实现、Rm 维度用本工具 ``scan-surface`` 对账。
5. ``SetSilentMode(True)`` 灭模态框；语言环境无关（变量名稳定，输出值
   ``OberName`` 等本地化字符串勿依赖）。

用法（本机 KISSsoft 2026 + license 席位空闲时）::

    python tools/harvest_kisssoft_w10.py probe
    python tools/harvest_kisssoft_w10.py section --out tools/data/din743/w10_01_section.json
    python tools/harvest_kisssoft_w10.py scan-shoulder --out tools/data/din743/shoulder.csv
    python tools/harvest_kisssoft_w10.py scan-const --out tools/data/din743/const_notch.csv
    python tools/harvest_kisssoft_w10.py scan-size --out tools/data/din743/size_factor.csv
    python tools/harvest_kisssoft_w10.py scan-surface --out tools/data/din743/surface_rz16.csv

产物入 ``tools/data/din743/``（seed 源快照），由 ``tools/gen_din743_seeds.py``
消费建 ``DIN743_Notch`` / ``DIN743_Curve`` 表。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

EXAMPLE = r"C:\KISSsoft 2026\example\01 Shafts.W10"
TMP = ROOT / "tmp"

#: 截面级金样收割的逐截面变量集（B2 金样；Geo/载荷/系数/安全系数全覆盖）
SECTION_VARS = [
    "Name", "Bezeichnung", "Komm", "x", "Aktiviert", "Rz",
    "Geo.da", "Geo.Da", "Geo.di", "Geo.Di", "Geo.r", "Geo.t", "Geo.b",
    "Kerb.Form", "Kerb.Kfb", "Kerb.Kfs", "Kerb.Kft", "Kerb.Kfz",
    "Wb", "Wt", "dWerkstK1Rech", "dWerkstRech",
    "Max.Fres", "Max.Mbres", "Max.Mtres", "Max.Qres",
    "Mitt.Fres", "Mitt.Mbres", "Mitt.Mtres", "Mitt.Qres",
    "Ampl.Fres", "Ampl.Mbres", "Ampl.Mtres", "Ampl.Qres",
    "Sigm.ZugDr", "Sigm.Bieg", "Sigm.Tors",
    "Siga.ZugDr", "Siga.Bieg", "Siga.Tors",
    "Sigmax.ZugDr", "Sigmax.Bieg", "Sigmax.Tors",
    "Din.K1dZug", "Din.K1dStreck",
    "Din.K2d.ZugDr", "Din.K2d.Bieg", "Din.K2d.Tors",
    "Din.KFsig.ZugDr", "Din.KFsig.Bieg", "Din.KFsig.Tors",
    "Din.PsisigK.ZugDr", "Din.PsisigK.Bieg", "Din.PsisigK.Tors",
    "Din.vSig.ZugDr", "Din.vSig.Bieg", "Din.vSig.Tors",
    "Din.K.ZugDr", "Din.K.Bieg", "Din.K.Tors",
    "Din.sigADK.ZugDr", "Din.sigADK.Bieg", "Din.sigADK.Tors",
    "Din.sigANK.ZugDr", "Din.sigANK.Bieg", "Din.sigANK.Tors",
    "Din.sigWK.ZugDr", "Din.sigWK.Bieg", "Din.sigWK.Tors",
    "Din.sigFK.ZugDr", "Din.sigFK.Bieg", "Din.sigFK.Tors",
    "Din.K2F.ZugDr", "Din.K2F.Bieg", "Din.K2F.Tors",
    "Din.gamF.ZugDr", "Din.gamF.Bieg", "Din.gamF.Tors",
    "Din.sigmV", "Din.taumV", "Din.K1dZug", "Din.K1dStreck",
    "sigva", "sigvab", "sigvat",
    "sErmuedung", "sStatisch", "sAnriss", "sResErmuedung", "sResStatisch",
]

_GLOBAL_VARS = [
    "W060Allg.RechMeth", "W060Allg.NurStat", "W060Allg.limitedLife",
    "W060Allg.Din.BeanspFall", "W060Allg.Din.sSollErmuedung",
    "W060Allg.Din.sSollStreck", "WelG.Woehler", "WelG.aktivLK",
    "shafts[0].material.bez", "shafts[0].material.Rm", "shafts[0].material.Rp",
    "shafts[0].material.dindb", "shafts[0].material.dinsigb",
    "shafts[0].material.dinsigs", "shafts[0].material.dinsigzdw",
    "shafts[0].material.dinsigbw", "shafts[0].material.dintautw",
    "shafts[0].length", "shafts[0].speed",
]

_NOTCH_SCAN_VARS = ["Qu[0].Kerb.Kfb", "Qu[0].Kerb.Kft", "Qu[0].Kerb.Kfz",
                    "Qu[0].Kerb.Kfs", "Qu[0].Din.KFsig.Bieg",
                    "Qu[0].Din.KFsig.Tors", "Qu[0].Din.KFsig.ZugDr",
                    "Qu[0].Din.K2d.ZugDr",
                    "Qu[0].Din.K2d.Bieg", "Qu[0].Din.K2d.Tors",
                    "Qu[0].Din.K1dZug", "Qu[0].Din.K1dStreck",
                    "Qu[0].Din.sigWK.Bieg", "Qu[0].Din.sigWK.Tors",
                    "Qu[0].Din.sigWK.ZugDr",
                    "Qu[0].sErmuedung", "Qu[0].sStatisch"]


def _as_float(v):
    """GetVar 值归一：文件存档的整型回传为字符串（如 ``'50'``）→ float。"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).rstrip("\u00b6"))
    except ValueError:
        return None


class W10Com:
    """W10 COM 会话（机制坑见模块 docstring 第 1-3 条）。"""

    def __init__(self) -> None:
        import win32com.client  # pywin32（aedt extra 已含）
        self.k = win32com.client.gencache.EnsureDispatch("KISSsoftCOM.KISSsoft")
        self.k.SetSilentMode(True)
        self.k.GetModule("W010", True)

    def close(self) -> None:
        try:
            self.k.ReleaseModule()
        except Exception:
            pass

    def load(self, path: str) -> None:
        """LoadFile + 锚键读回（防静默回退：calc 用本会话首个 GetVar 探活）。"""
        self.k.LoadFile(str(path))

    def calc(self) -> bool:
        self.k.Calculate()
        try:
            return bool(self.k.CalculateRetVal())
        except Exception:
            return False

    def get(self, var: str):
        try:
            return self.k.GetVar(var)
        except Exception:
            return None


def _read_base_text() -> str:
    return open(EXAMPLE, encoding="utf-16").read()


def setkey(text: str, key: str, val) -> str:
    """紧凑 ``key=value¶`` 替换（等号两侧无空格——带空格会让解析失败回退）。

    替换**全部**出现（``shafts[0].material.DBID`` 在文件里出现两次，
    只换第一处时 LoadFile 会按第二处的库 ID 重读材料、覆盖快照数值——
    2026-10-01 实测踩坑；其余键均唯一，行为不变）。
    """
    pat = re.compile(rf"^({re.escape(key)})=.*$", re.MULTILINE)
    if not pat.search(text):
        raise KeyError(key)
    replacement = f"{key}={val}\u00b6"
    return pat.sub(lambda _: replacement, text)


def variant(text: str, overrides: dict, path: Path) -> Path:
    """写变体文件并返回路径（Qu[0] 几何覆盖需配套 daFlag/DataFromGeometry）。"""
    t = text
    for key, val in overrides.items():
        t = setkey(t, key, val)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(t, encoding="utf-16", newline="")
    return path


def _section_overrides(form: int, d: float, D: float, r: float,
                       extra: dict | None = None) -> dict:
    ov = {
        "Qu[0].Kerb.Form": form,
        "Qu[0].Geo.DataFromGeometry": "false",
        "Qu[0].Geo.daFlag": "true",
        "Qu[0].Geo.da": d,
        "Qu[0].Geo.Da": D,
        "Qu[0].Geo.r": r,
    }
    if extra:
        ov.update(extra)
    return ov


def _material_overrides(rm: float) -> dict:
    """材料强度档变体（DBID=19999 自定义档 + 快照全量一致改写）。

    DBID 必须两处全换（见 :func:`setkey`），否则 LoadFile 从材料库重读
    42CrMo4 覆盖一切；19999（Eigene Eingabe）下快照数值才是权威。疲劳
    极限按 42CrMo4 比例口径（σzdW/σbW/τtW = 0.4/0.5/0.3·Rm）随档缩放。
    """
    return {
        "shafts[0].material.DBID": 19999,
        "shafts[0].material.Rm": rm,
        "shafts[0].material.Rp": round(rm * 0.82),
        "shafts[0].material.dinsigb": rm,
        "shafts[0].material.dinsigs": round(rm * 0.82),
        "shafts[0].material.dinsigzdw": round(rm * 0.4),
        "shafts[0].material.dinsigbw": round(rm * 0.5),
        "shafts[0].material.dintautw": round(rm * 0.3),
    }


def _run_scan(com: W10Com, text: str, cases: list[dict], csv_vars: list[str],
              out: Path) -> int:
    """跑案例网格：每案独立变体文件（全新状态）+ 锚键读回 + CalcRetVal 门。"""
    rows, bad = [], 0
    tmpdir = TMP / "w10_scan"
    for i, case in enumerate(cases):
        overrides = case.pop("__overrides")
        meta = dict(case)
        vpath = tmpdir / f"case_{i:04d}.W10"
        variant(text, overrides, vpath)
        com.load(vpath)
        # 锚键读回：变体未生效（静默回退）即弃（GetVar 整型回传字符串）
        anchor = overrides.get("Qu[0].Geo.da")
        got = _as_float(com.get("Qu[0].Geo.da"))
        if anchor is not None and (got is None or abs(got - float(anchor)) > 1e-9):
            print(f"[{i}] 静默回退：da 读回 {got!r} != {anchor!r}，跳过")
            bad += 1
            continue
        # 材料档读回：DBID 档变体必须生效（否则 η/表面系数全是同一材料）
        mat_anchor = overrides.get("shafts[0].material.dinsigb")
        if mat_anchor is not None:
            mgot = _as_float(com.get("shafts[0].material.dinsigb"))
            if mgot is None or abs(mgot - float(mat_anchor)) > 1e-9:
                print(f"[{i}] 材料变体未生效：dinsigb 读回 {mgot!r} != "
                      f"{mat_anchor!r}，跳过")
                bad += 1
                continue
        ok = com.calc()
        row = dict(meta, ok=ok)
        for v in csv_vars:
            name = v.split(".", 1)[1] if v.startswith("Qu[0].") else v
            row[name] = com.get(v)
        rows.append(row)
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(cases)} done ({time.strftime('%H:%M:%S')})")
        if not ok:
            bad += 1
    out.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        with open(out, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    print(f"{out}: {len(rows)} rows, {bad} bad")
    return bad


# ------------------------------------------------------------------ 子命令

def cmd_probe(_args) -> None:
    com = W10Com()
    try:
        print("LicenseNumber:", com.k.LicenseNumber())
        com.load(EXAMPLE)
        ok = com.calc()
        print("CalcRetVal:", ok)
        for v in ("Qu[0].sErmuedung", "Qu[0].sStatisch", "Qu[0].Kerb.Kfb",
                  "Qu[0].Geo.da", "W060Allg.RechMeth", "shafts[0].material.bez"):
            print(f"  {v} = {com.get(v)}")
    finally:
        com.close()


def cmd_section(args) -> None:
    """官方算例逐截面全变量金样 JSON（激活截面自动发现）。"""
    com = W10Com()
    try:
        com.load(args.file or EXAMPLE)
        ok = com.calc()
        assert ok, "Calculate 失败"
        sections = []
        for i in range(20):
            if _as_float(com.get(f"Qu[{i}].Aktiviert")) != 1.0:
                continue
            data = {}
            for v in SECTION_VARS:
                val = com.get(f"Qu[{i}].{v}")
                if isinstance(val, str):
                    val = val.rstrip("\u00b6")
                data[v] = val
            sections.append({"index": i, "vars": data})
        doc = {
            "source": str(args.file or EXAMPLE),
            "globals": {v: com.get(v) for v in _GLOBAL_VARS},
            "sections": sections,
        }
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print(f"{out}: {len(sections)} sections")
    finally:
        com.close()


def cmd_scan_shoulder(args) -> None:
    """轴肩缺口系数 βk(D/d, r/d, Rm)：DIN 743-2 曲线族重建/对账主源。"""
    ratios = [1.02, 1.05, 1.1, 1.15, 1.2, 1.3, 1.4, 1.5, 1.75, 2.0, 2.5, 3.0]
    rods = [0.005, 0.0075, 0.01, 0.015, 0.02, 0.03, 0.04, 0.05, 0.075, 0.1, 0.15, 0.2]
    rms = [400.0, 800.0, 1200.0]
    d = 50.0
    text = _read_base_text()
    cases = []
    for dd in ratios:
        for rd in rods:
            for rm in rms:
                ov = _section_overrides(1, d, d * dd, d * rd)
                ov.update(_material_overrides(rm))
                cases.append({"__overrides": ov, "D_over_d": dd,
                              "r_over_d": rd, "Rm": rm})
    com = W10Com()
    try:
        _run_scan(com, text, cases, _NOTCH_SCAN_VARS, Path(args.out))
    finally:
        com.close()


def cmd_scan_const(args) -> None:
    """固定值缺口随 Rm 的 Kf 曲线（键槽 Form 4 × NutArt/n、过盈
    Form 3 × Press.Art、光轴对照）。

    2026-10-01 材料变体机制修复后实证：TÜV 建议值口径的 Kf **随 Rm 变**
    （键槽单键 2.11@400 → 3.07@1200；42CrMo4 的 2.98 只是该材料的值），
    故按 (form, subtype) 存 X=Rm 曲线而非常数；Rm 网格 400..1400 步 100。
    """
    rms = [float(r) for r in range(400, 1401, 100)]
    d = 50.0
    text = _read_base_text()
    cases = []
    for rm in rms:
        # 键槽：t/b 用原截面值（5.6/14，d=50 匹配官方算例）
        for nut in (0, 1):
            for n in (1, 2):
                ov = _section_overrides(4, d, d, 0.0,
                                        {"Qu[0].Passf.NutArt": nut,
                                         "Qu[0].Passf.n": n,
                                         "Qu[0].Geo.t": 5.6, "Qu[0].Geo.b": 14})
                ov.update(_material_overrides(rm))
                cases.append({"__overrides": ov, "form": 4, "subtype": nut,
                              "n_keys": n, "Rm": rm})
        for art in range(4):
            ov = _section_overrides(3, d, d, 0.0, {"Qu[0].Press.Art": art})
            ov.update(_material_overrides(rm))
            cases.append({"__overrides": ov, "form": 3, "subtype": art,
                          "Rm": rm})
        # 光轴（Form 0）对照行：Kf≡1、表面系数正常激活
        ov = _section_overrides(0, d, d, 0.0)
        ov.update(_material_overrides(rm))
        cases.append({"__overrides": ov, "form": 0, "subtype": 0, "Rm": rm})
    com = W10Com()
    try:
        _run_scan(com, text, cases, _NOTCH_SCAN_VARS, Path(args.out))
    finally:
        com.close()


def cmd_scan_size(args) -> None:
    """尺寸系数 K1/K2 随 d（DIN 743-1 §5 公式对账锚点；× CrNiMo 钢型）。

    CrNiMo 钢型必须走 DBID=19999 材料变体（与其它材料键一样会被库重载
    冲掉——2026-10-01 实测 CrNiMo=1 无效后修正）。K2 收割实证：拉压
    K2≡1（无应力梯度无尺寸效应）、弯曲=扭转、K2/K1 均随 log10(d) 线性
    （K2 = 1 − 0.1535·log10(d/7.5)，d≳170 钳位 0.8）——插值走半对数。
    """
    ds = [5.0, 7.5, 10.0, 15.0, 20.0, 30.0, 40.0, 60.0, 80.0, 100.0,
          150.0, 200.0, 300.0, 400.0, 600.0]
    text = _read_base_text()
    cases = []
    for d in ds:
        for crnimo in ("0", "1"):
            ov = _section_overrides(0, d, d, 0.0)
            ov.update(_material_overrides(1100.0))
            ov["shafts[0].material.dincrnimo"] = crnimo
            cases.append({"__overrides": ov, "d": d, "CrNiMo": int(crnimo)})
    com = W10Com()
    try:
        _run_scan(com, text, cases,
                  _NOTCH_SCAN_VARS + ["Qu[0].dWerkstK1Rech"], Path(args.out))
    finally:
        com.close()


def cmd_scan_surface(args) -> None:
    """表面系数 KFσ(Rm)（默认加工档 Rz=16）：Rm 维对账切片（Rz 维走标准公式）。"""
    rms = [400.0, 500.0, 600.0, 700.0, 800.0, 900.0, 1000.0, 1100.0, 1200.0]
    text = _read_base_text()
    cases = []
    for rm in rms:
        for form in (0, 1):  # 光轴 + 轴肩（粗糙度未计入 Kf 的两种形态）
            ov = _section_overrides(form, 50.0, 100.0 if form else 50.0, 2.0)
            ov.update(_material_overrides(rm))
            cases.append({"__overrides": ov, "form": form, "Rm": rm})
    com = W10Com()
    try:
        _run_scan(com, text, cases, _NOTCH_SCAN_VARS, Path(args.out))
    finally:
        com.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("probe").set_defaults(fn=cmd_probe)
    p = sub.add_parser("section")
    p.add_argument("--file", default=None, help="W10 文件（默认官方 01 Shafts）")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_section)
    for name, fn in (("scan-shoulder", cmd_scan_shoulder),
                     ("scan-const", cmd_scan_const),
                     ("scan-size", cmd_scan_size),
                     ("scan-surface", cmd_scan_surface)):
        p = sub.add_parser(name)
        p.add_argument("--out", required=True)
        p.set_defaults(fn=fn)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
