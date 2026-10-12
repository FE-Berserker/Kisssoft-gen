"""KISSsoft M10 圆柱过盈官方算例金样收割（COM GetVar 逐变量，幂等，失败不覆盖旧档）。

pyffalo 侧消费方：`InterferenceFit`（components/connection/interference_fit.py）。
落点：`tests/golden/interference_fit/kisssoft_m10.json`（新建目录，此前单层件无金样——
仓内只有 `tests/unit/test_interference_fit.py::test_safety_factors_kisssoft_alignment`
以硬编码 4.94/3.40 两个数做弱对齐，本收割器把对齐从「写死的数」升级为「实机金样」）。

变量名录来源 = `rpt/M010*.RPT` 全部模板的花括号集（UTF-16 解码后正则，227 键），
**不用 KVAR**（惯例：KVAR 缺登/错登）。花括号集里结果侧 ~150 键逐个 GetVar 实测。

COM 机制坑（详见 references/com-mechanics.md「过盈接触族专项」节）：
- SetSilentMode 先行；GetModule('M10', True) 返回值丢弃、全部方法在根对象调用；
- **模块名拼写敏感且无效名会毒化整个 COM 会话**：探过 M10/M010 可、M01 抛
  com_error、M02/M020 静默判废——更坑的是判废后即使换回正确名，本会话内
  CalculateRetVal 恒 False、GetVar 全空。故本收割器每案独立 Dispatch。
- CalculateRetVal 唯一判据；GetVar 归一化（异常/None/空串→None，¶ 尾剥除）。
- `m01r.si[0..2]` 是滑动安全系数——**不在 m01n/m01w 压力族下而在 r 族**，
  按直觉猜 `m01n.si` 全空（三族 3×5 候选名实测只有这一组命中）。
- 三档语义 = KISSsoft `[均值, 最小, 最大]`，**最坏档在 [2]**（安全系数越小越
  靠 [2]）。pyffalo 侧统一 `[max,min,mean]` 且安全系数取最坏档——对账时
  别把 KISSsoft [1] 当最坏档，会得出 ~45% 的假偏差。
- 应力符号：KISSsoft 报幅值（正数），pyffalo 报带符号（压为负）——对账取幅值。
- **下标语义是「公差带档序」不是「值的大小序」**，这是本族最大的对账陷阱：
  同一档序贯穿所有三档量，但每个量的**最坏档下标不同**——因为最坏 = 最小值
  还是最大值随量而异。实测（算例 02）：
    压力 p      [121.28, 81.73, 154.42]  → 递增，最坏（最大）= [2]
    滑动 si     = p × 0.0707（同比例）   → 递增，最坏（最小）= [1]
    毂 σViMF    [636.98, 438.67, 793.71]  → 递增，最坏（最大）= [2]
    毂 SiRm     = Rm/σViMF（恒 1200）    → 递减，最坏（最小）= [2]
  故 **SiRm/SiRe 取 [2]、滑动 si 取 [1]**——pyffalo 组件侧两者都取最坏档，
  对账时下标取错会得 si ~1.8 倍、SiRm ~1.8 倍的假偏差。
- 死键 / 派生快照（文件变体四探针钉死：改 l 50→100、df 60→80、Mb 10→40）：
  - `m01r.pr` 恒 0.0（死键）；`m01r.my` 恒 0.16（死键，不随 l/df/Mb 变）。
  - `m01r.temp` / `tempW` / `tempWM` **不是死键**但也非温度输入：随 df 变
    （df 60→80 时 211.30→191.74）、不随 l / Mb 变——是内核算出的最大许用
    温度（过盈耗尽临界温升），别当输入温度回显读。
  - `m01r.Fpress[0..2]` 随 l 线性（50→100 时 69.59→139.19 kN）、随 df 反比，
    是**压入力 [kN]**；`FpressLMont[0]` = `Fpress[0]` × 0.8125（恒 1−3/16，
    三变体精确恒定，具体口径未钉死，record 档）。
  - `m01r.faktLMont` = 1.3（压装系数）、`m01r.faktmy` = 1.6（拆卸系数）——
    即 spec 记录的「压装/拆卸力系数 1.3/1.6」，pyffalo 侧未移植
    （K_adhesion 默认 1.4 是另一套粘着口径，非此二者）。
  - `m01sollSi.*` 是**许用安全系数设定值**（无量纲，RmW=1.5 / ReN=1.0 /
    Ru=1.2 / SpW=SpN=1.0，两案恒同）——是设计输入不是计算结果。注意 KISSsoft
    屈服档用 1.0，pyffalo Baseline 默认 1.5（基线可改，非公式差异）。
- M10 内核对 `m01{w,n}.tol.bez` 公差代号做服务端展开（K010 不展开，M10 展开），
  故任意 (直径, 代号) 的 ISO 真值可经本模块取到（见 com-mechanics K10 节）。
- 官方算例 01 单层无环 → `m01n.pressure[0..2]` 全 0（无外压直给输入）；
  算例 02 带外套环 → pressure 为直给的三档外压。
- `m01w.tolOut` / `m01n.tolOut` 在模板集内但内核不回吐（毂外径公差带单层无环
  时不参与计算）——保留为「空回显见证」。毂外径 da 在单层算例里从
  `m01n.da` 读（毂 = 内件 n）。

用法：``python scripts/gen_interference_fit_kisssoft.py``（本机 KISSsoft 2026 + 空闲席位）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pyffalo_root

REPO = pyffalo_root.repo_root()
GOLDEN = REPO / "tests/golden/interference_fit/kisssoft_m10.json"
KS_EX = Path("C:/KISSsoft 2026/example")
KS_RPT = Path("C:/KISSsoft 2026/rpt")

CASES = {
    "cyl_01": "01 Cylindrical Interference Fit.M10",
    "cyl_02_outer_rings": "02 Cylindrical Interference Fit (Outer Rings).M10",
}

#: 锚键：算例确实载入的判据（几何在两案均为 df=60，但值非平凡——空模块会回吐 None）
ANCHOR = "m01allg.df"

#: 输入侧（几何/材料/载荷/温度）与结果侧（压力/应力/安全系数/位移）分开登记，
#: 金样里同存两段，便于 pyffalo 侧区分「喂进去的」与「对账的」。
INPUT_KEYS = [
    "m01allg.df", "m01allg.l", "m01allg.FA", "m01allg.FU",
    "m01allg.Fr", "m01allg.Mb", "m01allg.n", "m01allg.Rm[0]", "m01allg.Rm[1]",
    "m01allg.Rp[0]", "m01allg.Rp[1]", "m01allg.zeta", "m01allg.qpaqa",
    "m01allg.eigenTol", "m01allg.elastplast", "m01allg.VarAussenD",
    "m01allg.uebermass[0]", "m01allg.uebermass[1]", "m01allg.uebermass[2]",
    "m01allg.pF", "m01allg.cb", "m01allg.s",
    "m01w.da", "m01w.di", "m01w.dref", "m01w.deff",
    "m01w.mat.E", "m01w.mat.ny", "m01w.mat.bez", "m01w.mat.DBID",
    "m01w.mat.alpha", "m01w.mat.rho", "m01w.oberfl.rz", "m01w.tol.bez",
    "m01w.tol.max", "m01w.tol.min", "m01w.tol.width", "m01w.tolOut",
    "m01w.tempB", "m01w.tempWFueg", "m01w.K1Streck", "m01w.K1Zug",
    "m01n.da", "m01n.dref", "m01n.deff", "m01n.fitsCount",
    "m01n.mat.E", "m01n.mat.ny", "m01n.mat.bez", "m01n.mat.DBID",
    "m01n.mat.alpha", "m01n.mat.rho", "m01n.oberfl.rz", "m01n.tol.bez",
    "m01n.tol.max", "m01n.tol.min", "m01n.tol.width",
    "m01n.tolDa_max", "m01n.tolDa_min", "m01n.tolOut",
    "m01n.tempB", "m01n.tempMontage", "m01n.pressureFlag",
    "m01n.pressure[0]", "m01n.pressure[1]", "m01n.pressure[2]",
    "m01n.K1Streck", "m01n.K1Zug", "m01n.wallthickness",
    "m01M.nenn", "m01M.grenz[0]", "m01M.grenz[1]", "m01M.grenz[2]", "m01M.cb",
]

RESULT_KEYS = [
    # 接触压力：r 族才是结果侧主压力键（n 族 pressure 是外压直给输入）
    "m01r.p[0]", "m01r.p[1]", "m01r.p[2]", "m01r.pr", "m01r.pb",
    # 毂（内件 n）：等效应力 / 应力分量 / 安全系数 / 位移
    "m01n.sigmaVi[0]", "m01n.sigmaVi[1]", "m01n.sigmaVi[2]",
    "m01n.sigmaViMF[0]", "m01n.sigmaViMF[1]", "m01n.sigmaViMF[2]",
    "m01n.sigmaVa[0]", "m01n.sigmaVa[1]", "m01n.sigmaVa[2]",
    "m01n.sigmaRa[0]", "m01n.sigmaRa[1]", "m01n.sigmaRa[2]",
    "m01n.sigmaRi[0]", "m01n.sigmaRi[1]", "m01n.sigmaRi[2]",
    "m01n.sigmaRai[0]", "m01n.sigmaRai[1]", "m01n.sigmaRai[2]",
    "m01n.SiRm[0]", "m01n.SiRm[1]", "m01n.SiRm[2]",
    "m01n.SiRe[0]", "m01n.SiRe[1]", "m01n.SiRe[2]",
    "m01n.delta[0]", "m01n.delta[1]", "m01n.delta[2]",
    "m01n.delta_i[0]", "m01n.delta_i[1]", "m01n.delta_i[2]",
    "m01n.delta_ix[0]", "m01n.delta_ix[1]", "m01n.delta_ix[2]",
    "m01n.delta20[0]", "m01n.delta20[1]", "m01n.delta20[2]",
    "m01n.deltax[0]", "m01n.deltax[1]", "m01n.deltax[2]",
    "m01n.deltax20[0]", "m01n.deltax20[1]", "m01n.deltax20[2]",
    "m01n.tauTa[0]", "m01n.tauTa[1]", "m01n.tauTa[2]",
    "m01n.tauTi[0]", "m01n.tauTi[1]", "m01n.tauTi[2]",
    "m01n.tauTai[0]", "m01n.tauTai[1]", "m01n.tauTai[2]",
    # 轴（外件 w）
    "m01w.sigmaVi[0]", "m01w.sigmaVi[1]", "m01w.sigmaVi[2]",
    "m01w.sigmaVa[0]", "m01w.sigmaVa[1]", "m01w.sigmaVa[2]",
    "m01w.sigmaVaMF[0]", "m01w.sigmaVaMF[1]", "m01w.sigmaVaMF[2]",
    "m01w.sigmaRa[0]", "m01w.sigmaRa[1]", "m01w.sigmaRa[2]",
    "m01w.sigmaRi[0]", "m01w.sigmaRi[1]", "m01w.sigmaRi[2]",
    "m01w.SiRm[0]", "m01w.SiRm[1]", "m01w.SiRm[2]",
    "m01w.SiRe[0]", "m01w.SiRe[1]", "m01w.SiRe[2]",
    "m01w.delta[0]", "m01w.delta[1]", "m01w.delta[2]",
    "m01w.delta_e[0]", "m01w.delta_e[1]", "m01w.delta_e[2]",
    "m01w.delta_e20[0]", "m01w.delta_e20[1]", "m01w.delta_e20[2]",
    "m01w.delta_ex[0]", "m01w.delta_ex[1]", "m01w.delta_ex[2]",
    "m01w.delta_ex20[0]", "m01w.delta_ex20[1]", "m01w.delta_ex20[2]",
    "m01w.deltax[0]", "m01w.deltax[1]", "m01w.deltax[2]",
    "m01w.tauTa[0]", "m01w.tauTa[1]", "m01w.tauTa[2]",
    "m01w.tauTi[0]", "m01w.tauTi[1]", "m01w.tauTi[2]",
    # 结果（r 族）：滑动安全 / 压入力 / 过盈量 / 温度
    "m01r.si[0]", "m01r.si[1]", "m01r.si[2]",
    "m01r.Fpress[0]", "m01r.Fpress[1]", "m01r.Fpress[2]",
    "m01r.FpressLMont[0]", "m01r.FpressLMont[1]",
    "m01r.faktLMont", "m01r.faktmy", "m01r.my", "m01r.myLMont",
    "m01r.abmass[0]", "m01r.abmass[1]", "m01r.abmass[2]",
    "m01r.abmass20[0]", "m01r.abmass20[1]", "m01r.abmass20[2]",
    "m01r.pUmg[0]", "m01r.pUmg[1]", "m01r.pUmg[2]",
    "m01r.temp", "m01r.tempW", "m01r.tempWM",
    "m01r.coolingShaft", "m01r.heatingHub",
    # 许用应力基准
    "m01sollSi.RmW", "m01sollSi.ReN", "m01sollSi.Ru",
    "m01sollSi.SpW", "m01sollSi.SpN",
]

SOURCE = ("KISSsoft 2026 M10 圆柱过盈官方算例 01/02，COM GetVar 逐变量收割"
          "（{} 收割）。变量名录 = rpt/M010*.RPT 全部模板花括号集（UTF-16 解码后"
          "正则，{} 键），不用 KVAR。".format("2026-10-12", 227))

NOTE = (
    "下标语义 = 公差带档序 [均值, 最小, 最大]，同一档序贯穿所有三档量；但"
    "**每量的最坏档下标不同**（最坏=最小还是最大随量而异）：压力/应力递增 → "
    "最坏在 [2]；滑动 si（∝ 压力）递增 → 最坏（最小）在 [1]；SiRm/SiRe = Rm/σ "
    "递减 → 最坏（最小）在 [2]。对账取错下标会得 ~1.8 倍假偏差。\n"
    "pyffalo 侧 InterferenceFit 统一 [max, min, mean] 且安全系数一律取最坏档，"
    "故 SiRm/SiRe ↔ KISSsoft [2]、Sr ↔ KISSsoft si[1]。\n"
    "符号口径：KISSsoft 应力报幅值（正数），pyffalo 报带符号（压应力为负）——"
    "对轴侧取幅值比对。\n"
    "压力键：结果侧主压力是 m01r.p[0..2]；m01n.pressure[0..2] 是外压直给输入"
    "（算例 01 单层无环 → 全 0，算例 02 带外套环 → 三档非零）。\n"
    "滑动安全系数键 = m01r.si[0..2]（r 族，不在 m01n/m01w 压力族下）。\n"
    "毂 = m01n（内件 Nabe）、轴 = m01w（外件 Welle）、结果 = m01r。\n"
    "恒等式（两案精确）：si[k] = p[k] × 0.0706778839（滑动安全 ∝ 压力）；"
    "SiRm[k] × sigmaViMF[k] = Rm（毂 700/1200 逐位）。\n"
    "死键：m01r.pr ≡ 0.0、m01r.my ≡ 0.16（四探针不变）。m01r.temp* 是内核"
    "算出的最大许用温度（随 df 变、不随 l/Mb 变），非输入温度回显。\n"
    "m01r.Fpress[0..2] = 压入力 [kN]（∝ l）；FpressLMont[0] = Fpress[0]×0.8125"
    "（恒定，口径未钉死，record 档）。faktLMont=1.3 压装 / faktmy=1.6 拆卸"
    "（pyffalo 未移植）。\n"
    "m01sollSi.* = 许用安全系数设定值（RmW=1.5 / ReN=1.0 / Ru=1.2 / SpW=SpN=1.0），"
    "设计输入非计算结果；KISSsoft 屈服档 1.0 vs pyffalo Baseline 默认 1.5。\n"
    "cyl_01 单层无环；cyl_02_outer_rings 含两片外套环（多层结构另见 "
    "tests/golden/interference_fit_multi/，那套的 p0 由 m01r.p 复核可验）。\n"
    "空回显见证：m01allg.da（模板集内无定义）、m01w.tolOut / m01n.tolOut"
    "（单层无环时不参与计算）。"
)


def rpt_keys() -> set[str]:
    """M010 报告模板的花括号变量集（命名空间权威名录）。"""
    import re

    keys: set[str] = set()
    for path in sorted(list(KS_RPT.glob("M010*.RPT")) + list(KS_RPT.glob("M010*.rpt"))):
        text = path.read_bytes().decode("utf-16-le", errors="ignore")
        keys |= set(re.findall(r"\{([A-Za-z0-9_.\[\]]+)\}", text))
    return keys


def _gv(ks, name: str):
    try:
        raw = ks.GetVar(name)
    except Exception:  # noqa: BLE001
        return None
    if raw is None:
        return None
    s = str(raw).rstrip("\u00b6").strip()
    try:
        return float(s)
    except ValueError:
        return s or None


def _one_case(fname: str, keys: list[str]) -> dict:
    """一案一个 COM 会话（规避无效模块名导致全会话中毒）。"""
    import win32com.client as client

    ks = client.Dispatch("KISSsoftCOM.KISSsoft")
    try:
        ks.SetSilentMode(True)
        ks.GetModule("M10", True)
        ks.LoadFile(str(KS_EX / fname))
        if _gv(ks, ANCHOR) is None:
            raise SystemExit(f"[{fname}] 锚键 {ANCHOR} 为空（未载入？）")
        if not ks.CalculateRetVal():
            raise SystemExit(f"[{fname}] CalculateRetVal=False，金样保持原样")
        return {"file": fname, "calc": True,
                "vars": {k: _gv(ks, k) for k in keys}}
    finally:
        try:
            ks.ReleaseModule()
        except Exception:  # noqa: BLE001, S110
            pass
        del ks


def main() -> int:
    rpt = rpt_keys()
    keys = INPUT_KEYS + RESULT_KEYS
    unknown = [k for k in keys if k not in rpt and k != ANCHOR]
    if unknown:
        print(f"警告：{len(unknown)} 个键不在 M010 模板花括号集内（GetVar 仍试）："
              f"{unknown[:8]}")

    cases: dict[str, dict] = {}
    for name, fname in CASES.items():
        row = _one_case(fname, keys)
        row["inputs"] = {k: row["vars"][k] for k in INPUT_KEYS}
        row["results"] = {k: row["vars"][k] for k in RESULT_KEYS}
        # 健全性过滤：结果侧关键量缺一即废
        missing = [k for k in ("m01r.p[0]", "m01r.si[1]", "m01n.sigmaViMF[2]",
                               "m01w.sigmaVi[2]") if row["results"][k] is None]
        if missing:
            raise SystemExit(f"[{name}] 结果变量缺失 {missing}，金样保持原样")
        cases[name] = row
        hit = sum(1 for v in row["vars"].values() if v is not None)
        print(f"  {name}: {fname}  命中 {hit}/{len(keys)} 键")

    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(
        json.dumps({"source": SOURCE, "note": NOTE, "cases": cases},
                   ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"{len(cases)} 案 → {GOLDEN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
