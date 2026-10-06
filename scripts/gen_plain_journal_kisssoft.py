"""KISSsoft W070 径向滑动轴承官方算例金样收割（COM GetVar 逐变量）。

对 5 个官方算例（07/08/11/12/15，覆盖 ISO 7902 / DIN 31652 / DIN 31657
可倾瓦 / 低速 / analytic 分支）经 KISSsoftCOM 计算并收割激活轴承的全量
变量，写 ``tests/golden/plain_bearing/kisssoft_w70.json`` 供
``tests/unit/test_kisssoft_w70_golden.py`` 对账。

``--scan`` 模式：ISO 7902 特性曲线 COM 扫描（Roller_Chain_Power 口径）。
动机（2026-10-01 实测钉死）：ISO 7902 / DIN 31652 内核**不消费**随包
``dat/W070-001..005.dat`` 的 9 断点图表——算例 11 变载荷 10 点扫描对照，
ε 逐点系统性偏差 ~0.005、β 偏 2~8°，任何插值轴（线性/log/样条/Akima）
都闭不上；且 ``Lag[].omega/AnzFlachen`` 对该路径零影响（内核恒按 360°
圆柱瓦解）→ 特性数 = f(B/D, So) 二元函数。故按用户裁决口径直接扫内核：
变 ``Fr``（对数 25 档）× 变 ``B``（B/D 11 节点）收割 (So, ε, β, fstopsi,
ftopsi, Q3s, μ) 曲线入快照 ``tools/data/plain_bearing/iso7902_chars_scan.json.gz``，
``tools/gen_plain_bearing_seeds.py`` 以其为 ``Plain_Bearing_ISO7902`` 表的
运行时数据源（dat 图表快照仅存证不入库）。对照：DIN 31657 路径**逐位**
消费随包图表（算例 12 ε 线性插值 9 位一致），不需要扫描。

COM 形态（Z92 扫描机同款）：``SetSilentMode(True)`` + ``GetModule("W070",
True)`` + 文件变体（UTF-16 明文 key=value 行替换）+ ``LoadFile`` +
``CalculateRetV()`` 唯一可信判据 + ``GetVar`` + ``ReleaseModule``。
算例 07/08/15 的激活轴承是 ``Lag[1]``（``CurrentLag=1``），11/12 是
``Lag[0]``——金样 ``bearing`` 字段记录（非激活槽位存档残留默认值不入）。

变量名取权威报告模板 ``rpt/PlainJournalBearinge.RPT`` 花括号名录。
GetVar 缺失变量记 null（DIN 31657 专属量在 ISO 方法算例下不存在属正常）。

用法::

    python tools/gen_plain_journal_kisssoft.py            # 金样收割
    python tools/gen_plain_journal_kisssoft.py --scan     # ISO 特性曲线扫描
"""

from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GOLDEN = REPO / "tests/golden/plain_bearing/kisssoft_w70.json"
SCAN_OUT = REPO / "tools/data/plain_bearing/iso7902_chars_scan.json.gz"
KISS_EXAMPLE = Path("C:/KISSsoft 2026/example")
SCAN_BASE = KISS_EXAMPLE / "07 Plain Journal Bearing (ISO 7902).W70"
SCAN_CASES = REPO / "tmp/w70_scan_cases"

#: 扫描 B/D 节点（0.25..1.5 步 0.05 共 26 档——线性混合余差压到 ~0.1%）
SCAN_BDS = tuple(round(0.25 + 0.05 * k, 2) for k in range(26))
#: 扫描 Fr 对数网格 [N]（算例 07 Fr=3949 → So≈3.05；So 与 Fr 近似成正比；
#: 高载端超膜厚/比压判废的点由 CalculateRetV=False 自然丢弃）
SCAN_FRS = tuple(round(40.0 * (1.7 ** k)) for k in range(31))
_SCAN_D = 35.0  # 基础算例 Lag[1] 直径 [mm]（B 随 B/D 节点联动改写）

#: 扫描逐点收割变量（So 之外的维度化输出，供组件流量 / 温度 / 功耗 /
#: 比压各链直接从数据建无量纲函数，免逐条反推内核公式）
_SCAN_VARS = (
    "So", "RelExzentr", "VerlWinkel", "fstopsi", "ftopsi", "Q3s", "my",
    "OilFlussEigen", "OilFlussFremd", "ReibLeistung", "ReibLeistungS",
    "LagerTemp", "AusTemp", "KinZahig", "DynZahig", "roOilBetr", "SpezWarm",
    "EffLagSpiel", "EffRelSpiel", "pmax", "FlPressung", "Federkonst",
    "UmfGeschw", "Re", "Rekrit",
)

#: 官方算例 → (金样名, 激活轴承索引)
CASES = [
    ("07 Plain Journal Bearing (ISO 7902).W70", "iso7902_07", 1),
    ("08 Plain Journal Bearing (ISO 7902 Low Speed).W70", "iso7902_lowspeed_08", 1),
    ("11 Plain Journal Bearing (DIN 31652).W70", "din31652_11", 0),
    ("12 Plain Journal Bearing (DIN 31657).W70", "din31657_tilt_12", 0),
    ("15 Plain Journal Bearing (ISO 7902 incl. analytic).W70",
     "iso7902_analytic_15", 1),
]

#: 收割变量（激活轴承 Lag[i] 前缀替换）——输入回显
_INPUT_VARS = (
    "Durchmesser", "Breite", "RadialKft", "RadLagSpiel20", "LagSpiel20",
    "AnzFlachen", "omega", "phi", "RBzuCR", "h0maxs", "Mixture",
    "WarmUberKoef", "ZulSchmFilm", "SchmierLoch", "Oberflache",
    "EffLagSpiel", "EffRelSpiel",
)
#: 收割变量——结果
_RESULT_VARS = (
    "So", "RelExzentr", "VerlWinkel", "MindSchmFilm", "LagerTemp",
    "ReibLeistung", "ReibLeistungS", "ReibVerlust",
    "ftopsi", "fstopsi", "my", "mys",
    "FlPressung", "pmax", "pmaxSos",
    "OilFluss", "OilFlussEigen", "OilFlussFremd",
    "MindOilFluss", "Q3s", "Qps", "Q2s", "hmins",
    "Teff", "AusTemp", "EinTemp", "deltaT1", "deltaT2", "Tmax",
    "KinZahig", "DynZahig", "roOilBetr", "eta0", "SpezWarm",
    "Re", "Rekrit", "UmfGeschw", "Federkonst", "radialOperatingOffset",
    "c11s", "c12s", "c21s", "c22s", "d11s", "d12s", "d21s", "d22s",
    "deltaTmaxs", "Ffs",
)
#: analytic 分支（算例 15）
_ANALYTIC_VARS = (
    "analyticResultsCalculated", "analyticResults.eccentricityRatio",
    "analyticResults.attitudeAngle", "analyticResults.minimumFilmThickness",
    "analyticResults.kxx", "analyticResults.kxy",
    "analyticResults.kyx", "analyticResults.kyy",
    "analyticResults.cxx", "analyticResults.cxy",
    "analyticResults.cyx", "analyticResults.cyy",
)
_GLOBAL_VARS = ("Allg.Drehzahl", "Allg.cM", "Allg.RechenMeth", "Allg.WarmeAbfuhr",
                "Allg.VollHalbUmschl", "Allg.OelDruck", "Allg.EinTemp",
                "Allg.AusTemp", "Allg.UmgebTemp", "Allg.MaxAdmTemp",
                "Allg.Oil.nu40", "Allg.Oil.nu100", "Allg.Oil.roOil")


def _getvar(ksoft, name: str):
    """GetVar → float | str | None（缺失/空记 None；非数值串原样保留）。"""
    try:
        raw = ksoft.GetVar(name)
    except Exception:  # noqa: BLE001 — 变量不存在时 COM 层可能抛错
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
        ksoft.GetModule("W070", True)
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
            record: dict[str, dict] = {
                "file": fname,
                "bearing": lag,
                "input": {**{v: _getvar(ksoft, pfx + v) for v in _INPUT_VARS},
                          **{v: _getvar(ksoft, v) for v in _GLOBAL_VARS}},
                "expect": {**{v: _getvar(ksoft, pfx + v) for v in _RESULT_VARS},
                           **{v: _getvar(ksoft, pfx + v) for v in _ANALYTIC_VARS}},
            }
            cases[cname] = record
            e = record["expect"]
            print(f"[{cname}] So={e.get('So')} ε={e.get('RelExzentr')} "
                  f"hmin={e.get('MindSchmFilm')} TB={e.get('LagerTemp')} "
                  f"Pf={e.get('ReibLeistung')} Pf'={e.get('ReibLeistungS')} "
                  f"Q={e.get('OilFluss')}", flush=True)
    finally:
        try:
            ksoft.ReleaseModule()
        except Exception:  # noqa: BLE001, S110
            pass

    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(
        json.dumps({
            "source": ("KISSsoft 2026 W070 COM GetVar 逐变量收割"
                       "（2026-10-01；官方算例 07/08/11/12/15 原文件）"),
            "note": ("单位口径：几何 mm、温度 ℃、ReibLeistung kW、OilFluss "
                     "l/min、So/RelExzentr/ftopsi 无量纲；07/08/15 激活轴承 "
                     "Lag[1]、11/12 激活 Lag[0]（存档 CurrentLag）；DIN 31657 "
                     "专属量（c11s..d22s 等）在 ISO 方法算例下为 null 属正常"),
            "cases": cases,
        }, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"{len(cases)} 案 → {GOLDEN}")
    return 0


def scan(method: int = 1) -> int:
    """ISO 7902 / DIN 31652 特性曲线 COM 扫描（变 Fr × 变 B）→ 快照
    JSON.gz（method=1 → ``iso7902_chars_scan.json.gz``，method=4 →
    ``iso7902_chars_scan_m4.json.gz``）。

    基础算例 07（激活轴承 Lag[1]）；Fr 与 B 改写经文件变体（SetVar
    派生变量会被静默重算，Z92 三约束同款）。每点收割 So/ε/β/fstopsi/
    ftopsi/Q3s/μ + 全量维度化输出——So 由内核热平衡迭代给出，不做定
    So 反解（插值表允许非均匀 So 节点）。``CalculateRetV`` 为假的点
    （超膜厚 / 超温判废）直接丢弃。两方法必须分别扫描：同几何下 M4
    内核 ε +1.9% / μ +13.5% 系统性偏离 M1（DIN 31652:2015 与
    ISO 7902:2020 表系不同，2026-10-01 e07_m4 探针钉死）。
    """
    import win32com.client as client

    if not SCAN_BASE.exists():
        raise SystemExit(f"未找到 KISSsoft 算例：{SCAN_BASE}")
    text = SCAN_BASE.read_text("utf-16")
    if method != 1:
        text = re.sub(r"^Allg\.RechenMeth=[^¶]*¶",
                      f"Allg.RechenMeth={method}¶", text, flags=re.MULTILINE)
    out_path = SCAN_OUT if method == 1 else \
        SCAN_OUT.with_name(SCAN_OUT.name.replace(".json.gz", f"_m{method}.json.gz"))
    SCAN_CASES.mkdir(parents=True, exist_ok=True)
    curves: dict[str, dict] = {}
    ksoft = client.Dispatch("KISSsoftCOM.KISSsoft")
    try:
        ksoft.SetSilentMode(True)
        ksoft.GetModule("W070", True)
        for bd in SCAN_BDS:
            b = round(_SCAN_D * bd, 4)
            pts: list[dict] = []
            for fr in SCAN_FRS:
                t = re.sub(r"^Lag\[1\]\.RadialKft=[^¶]*¶",
                           f"Lag[1].RadialKft={fr}¶", text, flags=re.MULTILINE)
                t = re.sub(r"^Lag\[1\]\.Breite=[^¶]*¶",
                           f"Lag[1].Breite={b}¶", t, flags=re.MULTILINE)
                case = SCAN_CASES / f"scan_m{method}_bd{bd:g}_fr{fr:g}.W70"
                case.write_text(t, "utf-16")
                ksoft.LoadFile(str(case))
                if not ksoft.CalculateRetVal():
                    continue
                g = lambda v: _getvar(ksoft, f"Lag[1].{v}")  # noqa: E731
                eps = g("RelExzentr")
                if eps is None:
                    continue
                # 非物理点防线：极端 So 端 ε≥0.999 外推 / M4 高载失败
                # 路径返回 ε=0 垃圾（RetV 仍 True）
                if not (1e-4 < eps < 0.999):
                    continue
                # seed 派生链的必需变量（Qstar/Kstar 归一）缺一即丢点——
                # None 透传会在 seed 期炸成不透明 TypeError
                required = ("So", "OilFlussEigen", "Federkonst", "DynZahig",
                            "EffRelSpiel", "UmfGeschw")
                vals = {v: g(v) for v in required}
                if any(v is None for v in vals.values()):
                    continue
                pts.append({"So": vals["So"], "Epsilon": eps,
                            "Beta": g("VerlWinkel"), "fstopsi": g("fstopsi"),
                            "ftopsi": g("ftopsi"), "Q3s": g("Q3s"),
                            **{v: val for v, val in vals.items() if v != "So"},
                            **{v: g(v) for v in _SCAN_VARS
                               if v not in required
                               and v not in ("RelExzentr", "VerlWinkel",
                                            "fstopsi", "ftopsi", "Q3s")}})
            pts.sort(key=lambda p: p["So"])
            # So 重复点（温度迭代饱和时 So ∝ Fr 严格性退化）去重保单调
            dedup: list[dict] = []
            for p in pts:
                if dedup and p["So"] <= dedup[-1]["So"] * 1.000001:
                    continue
                dedup.append(p)
            pts = dedup
            so_list = [p["So"] for p in pts]
            if len(pts) < 8:
                raise SystemExit(f"B/D={bd} 扫描点不足（{len(pts)} 点）")
            curves[f"{bd:g}"] = {"B_over_D": bd, "points": pts}
            print(f"B/D={bd:g}: {len(pts)} 点，So ∈ "
                  f"[{so_list[0]:.4g}, {so_list[-1]:.4g}]", flush=True)
    finally:
        try:
            ksoft.ReleaseModule()
        except Exception:  # noqa: BLE001, S110
            pass

    SCAN_OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out_path, "wt", encoding="utf-8") as fh:
        json.dump({
            "source": ("KISSsoft 2026 W070 COM 扫描（基算例 07，"
                       f"RechenMeth={method}；变 Fr × 变 B；omega 对该内核"
                       "无影响实测钉死）"),
            "params": {"D": _SCAN_D, "n": 980.0},
            "b_over_d": {k: v["B_over_D"] for k, v in curves.items()},
            "curves": {k: v["points"] for k, v in curves.items()},
        }, fh, ensure_ascii=False)
    print(f"扫描完成 → {out_path}")
    return 0


if __name__ == "__main__":
    if "--scan" in sys.argv:
        m = 1
        for i, a in enumerate(sys.argv):
            if a == "--method" and i + 1 < len(sys.argv):
                m = int(sys.argv[i + 1])
        sys.exit(scan(method=m))
    sys.exit(harvest())
