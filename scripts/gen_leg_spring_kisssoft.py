"""LegSpring（KISSsoft F30）金样收割器。

幂等重跑：官方算例 04 Leg Spring + 文件变体（UTF-16 ``key=value¶`` 行尾、
锚定行首替换、绝对路径 LoadFile）→ ``CalculateRetVal`` 唯一判据 →
``GetVar`` 全变量收割；全部案通过健全性过滤后一次性写
``tests/golden/leg_spring/kisssoft_f30.json``（失败不覆盖旧档）。

COM 形态照 ``gen_woodruff_key_kisssoft.py``：SetSilentMode → GetModule(
"F030", True)（返回值丢弃、方法全在根对象）→ LoadFile 绝对路径 →
CalculateRetVal → GetVar → finally ReleaseModule。公式链口径见
``docs/specs/leg-spring-f30.md``「背景口径」。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pyffalo_root

ROOT = pyffalo_root.repo_root()
sys.path.insert(0, str(ROOT / "src"))

KS_EXAMPLE = Path(r"C:\KISSsoft 2026\example")
CASES_DIR = ROOT / "tmp" / "f30_harvest_cases"
GOLDEN = ROOT / "tests" / "golden" / "leg_spring" / "kisssoft_f30.json"

_BASES = {"ex04": "04 Leg Spring.F30"}

#: 案集（name, base, changes）——覆盖矩阵：三模态 / 几何单因子（d/D/n/a/
#: R1/R2/r）/ 载荷扫 / 温度 / 牌号（own + B/D/不锈钢/VDC）/ 公差等级与
#: 线径公差标准 / 引导三态 / 方向 / 动载见证 / ALK0·Dd 快照格点 / 惰性
#: 字段见证（alpha0 / abgebogen / windungssinn——注意 belastungsrichtung
#: 与 windungssinn 联动翻号）。
CASES: list[tuple[str, str, list[tuple[str, object]]]] = [
    ("official", "ex04", []),
    ("own_E210", "ex04", [("f3.mat.DBID", 19999), ("f3.mat.bez", "Own"),
                          ("f3.mat.E", 210000), ("f3.mat.Rm", 1740),
                          ("f3.mat.dmin", 1), ("f3.mat.dmax", 20)]),
    # 载荷模态（belastung[1]/[2]：0=F / 1=α / 2=T）
    ("m1_T", "ex04", [("f3.belastung[1]", 2), ("f3.T1", 2500)]),
    ("m2_a", "ex04", [("f3.belastung[2]", 1), ("f3.alpha2", 100)]),
    ("m2_T", "ex04", [("f3.belastung[2]", 2), ("f3.T2", 5000)]),
    ("m1a_m2T", "ex04", [("f3.belastung[1]", 1), ("f3.alpha1", 40),
                         ("f3.belastung[2]", 2), ("f3.T2", 5500)]),
    # d / D / n / a 扫
    ("d2", "ex04", [("f3.d", 2), ("f3.De", 31), ("f3.Di", 27)]),
    ("d3", "ex04", [("f3.d", 3), ("f3.De", 32), ("f3.Di", 26)]),
    ("d5", "ex04", [("f3.d", 5), ("f3.De", 34), ("f3.Di", 24)]),
    ("d8", "ex04", [("f3.d", 8), ("f3.De", 37), ("f3.Di", 21)]),
    ("D16", "ex04", [("f3.D", 16), ("f3.De", 20), ("f3.Di", 12)]),
    ("D20", "ex04", [("f3.D", 20), ("f3.De", 24), ("f3.Di", 16)]),
    ("D25", "ex04", [("f3.D", 25), ("f3.De", 29), ("f3.Di", 21)]),
    ("D35", "ex04", [("f3.D", 35), ("f3.De", 39), ("f3.Di", 31)]),
    ("D45", "ex04", [("f3.D", 45), ("f3.De", 49), ("f3.Di", 41)]),
    ("n4", "ex04", [("f3.n", 4)]),
    ("n8", "ex04", [("f3.n", 8)]),
    ("n15", "ex04", [("f3.n", 15)]),
    ("n20", "ex04", [("f3.n", 20)]),
    ("a005", "ex04", [("f3.a", 0.05)]),
    ("a05", "ex04", [("f3.a", 0.5)]),
    ("a10", "ex04", [("f3.a", 1.0)]),
    ("a_zero", "ex04", [("f3.a", 0)]),
    # 簧腿
    ("R1_35", "ex04", [("f3.R1", 35), ("f3.F1", 2975.424 / 35)]),
    ("R1_45", "ex04", [("f3.R1", 45)]),
    ("R1_80", "ex04", [("f3.R1", 80)]),
    ("R1_100", "ex04", [("f3.R1", 100)]),
    ("R2_25", "ex04", [("f3.R2", 25)]),
    ("R2_35", "ex04", [("f3.R2", 35)]),
    ("R2_70", "ex04", [("f3.R2", 70)]),
    ("r1_2", "ex04", [("f3.r1", 2)]),
    ("r1_8", "ex04", [("f3.r1", 8)]),
    ("r2_5", "ex04", [("f3.r2", 5)]),
    # 载荷扫（角度链 / 绕紧几何）
    ("F2_60", "ex04", [("f3.F2", 60)]),
    ("F2_150", "ex04", [("f3.F2", 150)]),
    ("F2_200", "ex04", [("f3.F2", 200)]),
    ("F1_20", "ex04", [("f3.F1", 20)]),
    # 温度（E(T) 链）
    ("T100", "ex04", [("f3.temp", 100)]),
    ("T200", "ex04", [("f3.temp", 200)]),
    # 牌号（σzul 按 dat 表分档；own 只改 E/Rm 显示——σzul 仍走 dat，见证）
    ("grade_B", "ex04", [("f3.mat.DBID", 10937)]),
    ("grade_D", "ex04", [("f3.mat.DBID", 10939)]),
    ("grade_st", "ex04", [("f3.mat.DBID", 10940)]),
    ("grade_vdc", "ex04", [("f3.mat.DBID", 10942)]),
    # 公差块
    ("gq0", "ex04", [("f3.Tol_Q", 0)]),
    ("gq2", "ex04", [("f3.Tol_Q", 2)]),
    ("gq2_d8", "ex04", [("f3.Tol_Q", 2), ("f3.d", 8), ("f3.De", 37),
                        ("f3.Di", 21)]),
    ("td2", "ex04", [("f3.Tol_dID", 2)]),
    ("td4", "ex04", [("f3.Tol_dID", 4)]),
    ("td5", "ex04", [("f3.Tol_dID", 5)]),
    ("td_own", "ex04", [("f3.Tol_dID", 7), ("f3.Tol_d", 0.02)]),
    # 引导三态（Dd / Dh）
    ("fue0", "ex04", [("f3.fuehrung", 0), ("f3.dorn", 0)]),
    ("sleeve", "ex04", [("f3.fuehrung", 2), ("f3.huelse", 1), ("f3.dorn", 0)]),
    ("sleeve_d8", "ex04", [("f3.fuehrung", 2), ("f3.huelse", 1),
                          ("f3.dorn", 0), ("f3.d", 8), ("f3.De", 37),
                          ("f3.Di", 21)]),
    ("sleeve_D35", "ex04", [("f3.fuehrung", 2), ("f3.huelse", 1),
                            ("f3.dorn", 0), ("f3.D", 35), ("f3.De", 39),
                            ("f3.Di", 31)]),
    # 方向（aresult 符号；belastungsrichtung 联动 windungssinn）
    ("dir_rev", "ex04", [("f3.belastungsrichtung", 1)]),
    # 动载见证（σq 族 COM 恒 0——口径记录）
    ("dyn_witness", "ex04", [("f3.dynamisch", 1)]),
    # ALK0 / Dd 快照格点（表上逐位验证）
    ("grid_d25_D16", "ex04", [("f3.d", 2.5), ("f3.D", 16), ("f3.De", 18.5),
                              ("f3.Di", 13.5)]),
    ("grid_d6_D40", "ex04", [("f3.d", 6), ("f3.D", 40), ("f3.De", 46),
                             ("f3.Di", 34)]),
    ("grid_d10_D80", "ex04", [("f3.d", 10), ("f3.D", 80), ("f3.De", 90),
                              ("f3.Di", 70), ("f3.R1", 120), ("f3.R2", 100)]),
    ("grid_d18_D90", "ex04", [("f3.d", 18), ("f3.D", 90), ("f3.De", 108),
                              ("f3.Di", 72), ("f3.R1", 150), ("f3.R2", 120)]),
    ("grid_n4_D45", "ex04", [("f3.D", 45), ("f3.De", 49), ("f3.Di", 41),
                             ("f3.n", 4)]),
    # 惰性字段见证（alpha0 / abgebogen：输出应与 official 全同）
    ("inert_a0_10", "ex04", [("f3.alpha0", 10)]),
    ("inert_tang", "ex04", [("f3.abgebogen", 0)]),
]

#: 收割变量名录（输入回显 + 结果 + 公差；l1/l2 死字段与 AM 恒 0 不收）
VARS = [
    "f3.D", "f3.De", "f3.Di", "f3.d", "f3.n", "f3.a", "f3.R1", "f3.R2",
    "f3.r1", "f3.r2", "f3.alpha0", "f3.F1", "f3.F2", "f3.T1", "f3.T2",
    "f3.temp", "f3.belastung[1]", "f3.belastung[2]", "f3.windungssinn",
    "f3.belastungsrichtung", "f3.dynamisch", "f3.Tol_dID", "f3.Tol_d",
    "f3.Tol_Q", "f3.guete", "f3.fuehrung", "f3.mat.DBID", "f3.mat.E",
    "f3.mat.Rm", "f3.Emodul", "f3.w",
    "f3.RMR", "f3.Fn", "f3.Tn", "f3.alphan", "f3.amax", "f3.LK0",
    "f3.alpha1", "f3.alpha2", "f3.alphas1", "f3.alphas2", "f3.aresult",
    "f3.beta1", "f3.beta2", "f3.beta10", "f3.beta20",
    "f3.W1", "f3.W2", "f3.q",
    "f3.sigma1", "f3.sigma2", "f3.sigmaq1", "f3.sigmaq2", "f3.sigmaqh",
    "f3.sigmazul", "f3.Dea", "f3.Dia", "f3.Dd", "f3.Dh",
    "f3.AD", "f3.AM", "f3.Aalpha", "f3.ALK0", "f3.Ar1", "f3.Ar2",
    "f3.Aphi1", "f3.Aphi2",
]


def _setkey(text: str, key: str, val) -> str:
    """锚定行首替换（[^¶\\r\\n]* 不跨行，K14 轮教训；替换串走 lambda——
    值不按 re 替换模板转义，未来变体值含 \\1/\\g 也不被解释）。"""
    text, n = re.subn(rf"^{re.escape(key)}=[^¶\r\n]*¶",
                      lambda _m: f"{key}={val}¶", text, flags=re.MULTILINE)
    if n != 1:
        raise SystemExit(f"变体键 {key} 替换 {n} 处（应为 1）")
    return text


def _getvar(ksoft, name: str):
    """COM 变量归一化：异常 / None / 空串 → None；数值串 → float。"""
    try:
        raw = ksoft.GetVar(name)
    except Exception:
        return None
    if raw is None or raw == "":
        return None
    s = str(raw).rstrip("¶").strip()
    try:
        return float(s)
    except ValueError:
        return s


def main() -> int:
    import win32com.client as client

    texts = {n: (KS_EXAMPLE / f).read_text("utf-16")
             for n, f in _BASES.items()}
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    ksoft = client.Dispatch("KISSsoftCOM.KISSsoft")
    cases: dict[str, dict] = {}
    try:
        ksoft.SetSilentMode(True)
        ksoft.GetModule("F030", True)
        for idx, (name, base, changes) in enumerate(CASES, start=1):
            t = texts[base]
            for key, val in changes:
                t = _setkey(t, key, val)
            case = CASES_DIR / f"f30_{idx:03d}_{name}.F30"
            case.write_text(t, "utf-16")
            ksoft.LoadFile(str(case))
            ok = ksoft.CalculateRetVal()
            if not ok:
                raise SystemExit(f"[{name}] CalculateRetVal=False（金样案须全部可算）")
            expect = {v: _getvar(ksoft, v) for v in VARS}
            # 健全性：核心结果变量缺一即废
            for key in ("f3.RMR", "f3.sigma2", "f3.alphas2", "f3.W2",
                        "f3.Dea", "f3.AD", "f3.Aalpha"):
                if expect[key] is None:
                    raise SystemExit(f"[{name}] 结果变量 {key} 为空")
            if expect["f3.RMR"] <= 0:
                raise SystemExit(f"[{name}] RMR={expect['f3.RMR']} 非正")
            cases[name] = {"file": _BASES[base],
                           "changes": [[k, v] for k, v in changes],
                           "expect": expect}
            print(f"[{idx:02d}/{len(CASES)}] {name}: RMR={expect['f3.RMR']:.6g} "
                  f"σ2={expect['f3.sigma2']:.6g} αs2={expect['f3.alphas2']:.6g}")
    finally:
        try:
            ksoft.ReleaseModule()
        except Exception:
            pass  # noqa: S110 —— 释放失败不带走收割结果
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(json.dumps({
        "source": "KISSsoft 2026 F030 official example 04 Leg Spring + file "
                  "variants (COM GetVar, CalculateRetVal-gated), 2026-10-02",
        "note": "单位：几何 mm、力 N、扭矩/功 N·mm、角 °。内核常数 K_RMR="
                "0.9999808805119359、K_LEG=38.19391268601792（COM 反推，勿"
                "解析化）；q=(w+0.07)/(w-0.75)；β 存度、alphas=alpha+β动+β定、"
                "W=T·π·alphas/360；绕紧几何 x=alphas2/360n、e=D·x/(1-x²)、"
                "δ=D·x²/(1-x²)、Dea=D+δ+d+e、Dia=D+δ-d-e；公差 AD=D/(40·"
                "d^0.17)·guete、Aα=2.4·√w·n^0.76·guete、Ar=(0.2r+0.6)·guete、"
                "Aφ=4√(r1/d)·guete、ALK0=α表·(n+1.992528-0.415110/n)·guete、"
                "Dd/Dh=快照表族；σzul=0.7·Rm_dat(d)（回显整数圆整，复现差"
                "≤1.2MPa→σzul/Tn/Fn/αn 挂 2e-3 档）；l1/l2 死字段与 AM 恒 0 "
                "不收；σq 族 COM 恒 0（dyn_witness 见证，组件按帮助 7815 口径"
                "σq=q·σ 自实现无金样）；own 案 σzul 为内核陈旧值（沿袭前一案"
                "例牌号表——own 紧排 official 且 Rm=1740 与 SH@4 断点巧合对"
                "齐）；E(T) 线性式内核残差 ~1.5e-5（T100/T200 的 αG 不自洽疑"
                "查表）→温度案 RMR/α/σ 派生族挂 5e-5 档；belastung[1]/[2] 为"
                "双载荷点模态"
                "0=F/1=α/2=T（[0] 未用）；dir_rev 的 aresult=-(alphas2-alpha0)"
                "且 windungssinn 联动翻 0；inert_* 案输出应与 official 全同"
                "（alpha0/abgebogen 计算惰性）。",
        "harvest": "python tools/gen_leg_spring_kisssoft.py",
        "cases": cases,
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"金样落盘：{GOLDEN}（{len(cases)} 案）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
