"""TorsionBarSpring（KISSsoft F50）金样收割器。

幂等重跑：官方算例 06 + 文件变体（UTF-16 ``key=value¶`` 行尾、锚定行首
正则替换、绝对路径 LoadFile）→ ``CalculateRetVal`` 唯一判据 → ``GetVar``
全变量收割；全部案通过健全性过滤后一次性写
``tests/golden/torsion_bar_spring/kisssoft_f50.json``（失败不覆盖旧档）。

COM 形态照 ``gen_clamp_connection_kisssoft.py``。公式链口径见
``docs/specs/torsion-bar-f50.md``「背景口径」（六轮探针钉死）。
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
CASES_DIR = ROOT / "tmp" / "f50_harvest_cases"
GOLDEN = ROOT / "tests" / "golden" / "torsion_bar_spring" / "kisssoft_f50.json"

#: 官方算例基座
_BASES = {"ex06": "06 Torsion Bar Spring.F50"}

#: 案集（name, base, changes）——覆盖矩阵：三端部构型 / 两预置档 / GFlag
#: 自定义材料 / 载荷四输入模式 / 温度链 / ny 表 df·d 与 Rh 档 / s 表
#: da·df 网格 / 长度链 ls·L / z 反比 / 载荷点等值与零 / 倒挂外的判废邻域
#: 案全部取整数几何坐标（s 表节点逐位；ny 插值同式任意比值逐位）。
CASES: list[tuple[str, str, list[tuple[str, object]]]] = [
    ("base_06", "ex06", []),
    ("kopf0", "ex06", [("f5.kopfausfuehr", 0)]),
    ("kopf1", "ex06", [("f5.kopfausfuehr", 1)]),
    ("nopreset", "ex06", [("f5.vorgesetzt", "false")]),
    ("flag_TT", "ex06", [("f5.theta1Flag", "false"),
                         ("f5.theta2Flag", "false")]),
    ("flag_thT", "ex06", [("f5.theta2Flag", "false")]),
    ("flag_Tth", "ex06", [("f5.theta1Flag", "false")]),
    ("temp0", "ex06", [("f5.temp", 0)]),
    ("temp20", "ex06", [("f5.temp", 20)]),
    ("temp100", "ex06", [("f5.temp", 100)]),
    ("temp150", "ex06", [("f5.temp", 150)]),
    ("ownG70", "ex06", [("f5.GFlag", "true"), ("f5.G", 70000)]),
    ("d10", "ex06", [("f5.d", 10)]),
    ("d16", "ex06", [("f5.d", 16)]),
    ("d20", "ex06", [("f5.d", 20)]),
    ("d65_all_ok", "ex06", [("f5.d", 65), ("f5.df", 90), ("f5.da", 100)]),
    ("df18", "ex06", [("f5.df", 18)]),
    ("df22", "ex06", [("f5.df", 22)]),
    ("df24", "ex06", [("f5.df", 24)]),
    ("da22", "ex06", [("f5.da", 22)]),
    ("da28", "ex06", [("f5.da", 28)]),
    ("da32", "ex06", [("f5.da", 32)]),
    ("rh10", "ex06", [("f5.Rh", 10)]),
    ("rh45", "ex06", [("f5.Rh", 45)]),
    ("rh05", "ex06", [("f5.Rh", 0.5)]),
    ("ls80", "ex06", [("f5.ls", 80)]),
    ("L200", "ex06", [("f5.L", 200)]),
    ("geo_mix", "ex06", [("f5.d", 16), ("f5.da", 30), ("f5.df", 22),
                         ("f5.Rh", 25), ("f5.ls", 120), ("f5.L", 180)]),
    ("z10", "ex06", [("f5.z", 10)]),
    ("z36", "ex06", [("f5.z", 36)]),
    ("theta_equal", "ex06", [("f5.theta1", 10)]),
    ("th1_3", "ex06", [("f5.theta1", 3)]),
    ("T2_300", "ex06", [("f5.theta2Flag", "false"), ("f5.T2", 300)]),
    ("t1_zero_direct", "ex06", [("f5.theta1Flag", "false"), ("f5.T1", 0)]),
]

#: 收割变量名录（F050 归档变量全量 + GFlag 回显；新增变量一律追加）
VARS = [
    "f5.kopfausfuehr", "f5.vorgesetzt", "f5.GFlag", "f5.Rh", "f5.T", "f5.T1",
    "f5.T2", "f5.Tmax", "f5.theta", "f5.theta1", "f5.theta2", "f5.thetamax",
    "f5.theta1Flag", "f5.theta2Flag", "f5.d", "f5.da", "f5.df", "f5.z",
    "f5.L", "f5.ls", "f5.temp", "f5.G", "f5.rho", "f5.alphaG",
    "f5.Ip", "f5.Wp", "f5.lh", "f5.le", "f5.lf", "f5.lk", "f5.Rt",
    "f5.Wt1", "f5.Wt2", "f5.gamma1", "f5.gamma2", "f5.tau1", "f5.tau2",
    "f5.tauh", "f5.taum", "f5.tauzul", "f5.p1", "f5.p2", "f5.Rm", "f5.Gmodul",
]


def _setkey(text: str, key: str, val) -> str:
    """锚定行首替换（[^¶\\r\\n]* 不跨行，K14 轮教训）。"""
    text, n = re.subn(rf"^{re.escape(key)}=[^¶\r\n]*¶", f"{key}={val}¶",
                      text, flags=re.MULTILINE)
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
        ksoft.GetModule("F050", True)
        for name, base, changes in CASES:
            t = texts[base]
            for key, val in changes:
                t = _setkey(t, key, val)
            case = CASES_DIR / f"f50_{name}.F50"
            case.write_text(t, "utf-16")
            ksoft.LoadFile(str(case))
            ok = ksoft.CalculateRetVal()
            if not ok:
                raise SystemExit(f"[{name}] CalculateRetVal=False（金样案须全部可算）")
            expect = {v: _getvar(ksoft, v) for v in VARS}
            # 金样对账实际消费的量（test_kisssoft_f50_golden._PAIRS）缺一即
            # 废：None 进档会被对账测试静默 skip，等于悄悄削掉回归覆盖
            required = ("f5.Ip", "f5.Wp", "f5.Gmodul", "f5.lh", "f5.le",
                        "f5.lf", "f5.lk", "f5.Rt", "f5.T1", "f5.T2",
                        "f5.theta1", "f5.theta2", "f5.thetamax", "f5.tau1",
                        "f5.tau2", "f5.taum", "f5.tauh", "f5.gamma1",
                        "f5.gamma2", "f5.Wt1", "f5.Wt2", "f5.tauzul",
                        "f5.Tmax", "f5.p1", "f5.p2")
            missing = [k for k in required if expect[k] is None]
            if missing:
                raise SystemExit(f"[{name}] 结果变量为空：{missing}")
            cases[name] = {"file": _BASES[base],
                           "changes": [[k, str(v)] for k, v in changes],
                           "expect": expect}
            print(f"[{name}] ok")
    finally:
        try:
            ksoft.ReleaseModule()
        except Exception:
            pass
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(json.dumps({
        "source": "KISSsoft 2026 F050 official example 06 + file variants "
                  "(COM GetVar, PyWin32, 2026-10-02)",
        "note": "单位口径：KISSsoft 存档 T/T1/T2/Tmax 为 N·m、Rt 为 N·m/°；"
                "pyffalo 组件内 N·mm（对账 ×1000，见 test_kisssoft_f50_golden"
                " 的 _PAIRS scale）。公式链全闭式（spec torsion-bar-f50 背景"
                "口径）：Ip/Wp 圆截面；tauzul=1020(预置)/700 硬编码；Gmodul="
                "round(G·(1+alphaG·(temp−20))) 取整 quirk（alphaG 存档死键恒"
                " −0.00028，金样全默认档）；lh=√(Rh²−(Rh−h1)²) h1=(da−d)/2 "
                "根号内≤0 取 0；ny=le/lh 查 DIN 2091 比值表（Rh/d 五档界 "
                "1.10/1.35/1.75/2.5 × df/d 0.1 节点线性插值 >2.0 钳位）；"
                "le=ny·lh、lf=ls−2(lh−le)、lk=(L−ls)/2；Rt=Gmodul·Ip·(π/180)"
                "/(1000·lf) N·m/°；tauh=τ2−τ1（应力幅回显与材料无关）；"
                "gamma_i=τ_i/Gmodul；Wt_i=0.5·T_i·θ_i(rad) [N·m]；利用率(角)"
                "≡利用率(剪)≡τ2/τzul·100；p：四方 3T·1000/(df²·lk)、六方 ×2"
                "（z 均不进）、齿形 T·1000/(z·lk·s(da,df)) s 为整数网格快照"
                "表（本金样案全整数坐标 → 逐位档；d65_all_ok 案 (da,df)="
                "(100,90) 域外，p1/p2 不对账 record 档——组件表外钳位非逐位）。"
                "KISSsoft quirks 不复刻"
                "处：theta1Flag=false 时内核 θ1/Wt1 置 0（组件回算补全，"
                "对账时该两量按条件跳过）；d=0 内核产出 inf（组件判废）。"
                "判废面另见组件 check（df<d / df>da / ls>L / 倒挂 / 高载点"
                "零 / 齿形 z<1）。",
        "harvest": "python tools/gen_torsion_bar_kisssoft.py",
        "cases": cases}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"written {GOLDEN} ({len(cases)} cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
