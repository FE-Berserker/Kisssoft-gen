"""ClampConnection（KISSsoft M1C）金样收割器。

幂等重跑：官方算例 06/07 + 文件变体（UTF-16 ``key=value¶`` 行尾、锚定行首
正则替换、绝对路径 LoadFile）→ ``CalculateRetVal`` 唯一判据 → ``GetVar``
全变量收割；全部案通过健全性过滤后一次性写
``tests/golden/clamp_connection/kisssoft_m1c.json``（失败不覆盖旧档）。

COM 形态照 ``gen_conical_fit_kisssoft.py``：SetSilentMode → GetModule("M01C",
True)（返回值丢弃、方法全在根对象）→ LoadFile 绝对路径 → CalculateRetVal →
GetVar → finally ReleaseModule。公式链口径见
``docs/specs/clamp-connection-m1c.md``「背景口径」。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

KS_EXAMPLE = Path(r"C:\KISSsoft 2026\example")
CASES_DIR = ROOT / "tmp" / "m1c_harvest_cases"
GOLDEN = ROOT / "tests" / "golden" / "clamp_connection" / "kisssoft_m1c.json"

#: 官方算例基座
_BASES = {
    "ex06": "06 Clamped connections (Split hub).M1C",
    "ex07": "07 Clamped connections (Split hub lever).M1C",
}

#: 案集（name, base, changes）——覆盖矩阵：K 三档 / ceil(i/2) 链（i=1..5）/
#: 载荷与摩擦 / 几何单因子与多因子 / 许用系数 / own-input 韧性（0.8·Rm 钳位
#: 三点）/ KMAT 库材料（C45 韧性、GJL-150/250 铸铁）/ 惰性字段与 SHmin 证伪
#: 见证 / 开口杠杆链。
CASES: list[tuple[str, str, list[tuple[str, object]]]] = [
    ("split_06", "ex06", []),
    ("split_k0", "ex06", [("m01c.Kindex", 0)]),
    ("split_k2", "ex06", [("m01c.Kindex", 2)]),
    ("split_i1", "ex06", [("m01c.i", 1)]),
    ("split_i3", "ex06", [("m01c.i", 3)]),
    ("split_i4", "ex06", [("m01c.i", 4)]),
    ("split_i5", "ex06", [("m01c.i", 5)]),
    ("split_mu018", "ex06", [("m01c.mu", 0.18)]),
    ("split_T150", "ex06", [("m01c.nomTorque", 150)]),
    ("split_KA15", "ex06", [("m01c.KA", 1.5)]),
    ("split_l50", "ex06", [("m01c.l", 50)]),
    ("split_ls42", "ex06", [("m01c.ls", 42)]),
    ("split_D60", "ex06", [("m01c.D", 60)]),
    ("split_a30", "ex06", [("m01c.a", 30)]),
    ("split_h90", "ex06", [("m01c.h", 90)]),
    ("split_pf05", "ex06", [("m01c.PFfactor", 0.5)]),
    ("split_steel_own", "ex06", [("m01c.matn.DBID", 19999),
                                 ("m01c.matn.bez", "Own"),
                                 ("m01c.matn.Rp", 800), ("m01c.matn.Rm", 1000)]),
    ("split_Rp900", "ex06", [("m01c.matn.DBID", 19999),
                             ("m01c.matn.bez", "Own"),
                             ("m01c.matn.Rp", 900), ("m01c.matn.Rm", 1000)]),
    ("split_Rp700", "ex06", [("m01c.matn.DBID", 19999),
                             ("m01c.matn.bez", "Own"),
                             ("m01c.matn.Rp", 700), ("m01c.matn.Rm", 1000)]),
    ("split_Rp760", "ex06", [("m01c.matn.DBID", 19999),
                             ("m01c.matn.bez", "Own"),
                             ("m01c.matn.Rp", 760), ("m01c.matn.Rm", 1000)]),
    ("split_c45", "ex06", [("m01c.matn.DBID", 10010)]),
    ("split_gjl150", "ex06", [("m01c.matn.DBID", 10400)]),
    ("split_gjl250", "ex06", [("m01c.matn.DBID", 10420)]),
    ("split_shmin99", "ex06", [("m01c.SHmin", 99)]),
    ("split_shaftRp", "ex06", [("m01c.matw.Rp", 1600)]),
    ("split_geo_mix", "ex06", [("m01c.l", 50), ("m01c.ls", 42),
                               ("m01c.D", 60), ("m01c.a", 30)]),
    ("slotted_07", "ex07", []),
    ("slotted_l1_35", "ex07", [("m01c.l1", 35)]),
    ("slotted_l2_65", "ex07", [("m01c.l2", 65)]),
    ("slotted_l60", "ex07", [("m01c.l", 60)]),
    ("slotted_i3", "ex07", [("m01c.i", 3)]),
    ("slotted_T90", "ex07", [("m01c.nomTorque", 90)]),
    ("slotted_h90", "ex07", [("m01c.h", 90)]),
    ("slotted_ls40", "ex07", [("m01c.ls", 40)]),
    ("slotted_k2", "ex07", [("m01c.Kindex", 2)]),
    ("slotted_steel_own", "ex07", [("m01c.matn.DBID", 19999),
                                   ("m01c.matn.bez", "Own"),
                                   ("m01c.matn.Rp", 800),
                                   ("m01c.matn.Rm", 1000)]),
]

#: 收割变量名录（RPT M01CLe0.RPT 花括号集 + 输入回显）
VARS = [
    "m01c.configuration", "m01c.Kindex", "m01c.h", "m01c.l", "m01c.D", "m01c.a",
    "m01c.l1", "m01c.l2", "m01c.ls", "m01c.nomTorque", "m01c.KA", "m01c.Fkl",
    "m01c.mu", "m01c.i", "m01c.SHmin", "m01c.PFfactor",
    "m01c.matn.DBID", "m01c.matn.bez", "m01c.matn.Rp", "m01c.matn.Rm",
    "m01c.K", "m01c.Wb", "m01c.pF", "m01c.sigmaB",
    "m01c.SF", "m01c.SH", "m01c.SB", "m01c.pFmax", "m01c.sigmaBmax",
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
    s = str(raw).rstrip("\u00b6").strip()
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
        ksoft.GetModule("M01C", True)
        for idx, (name, base, changes) in enumerate(CASES, start=1):
            t = texts[base]
            for key, val in changes:
                t = _setkey(t, key, val)
            case = CASES_DIR / f"m1c_{idx:03d}_{name}.M1C"
            case.write_text(t, "utf-16")
            ksoft.LoadFile(str(case))
            ok = ksoft.CalculateRetVal()
            if not ok:
                raise SystemExit(f"[{name}] CalculateRetVal=False（金样案须全部可算）")
            expect = {v: _getvar(ksoft, v) for v in VARS}
            # 健全性：结果变量缺一即废（None 不允许进金样）
            for key in ("m01c.pF", "m01c.sigmaB", "m01c.SH", "m01c.SF",
                        "m01c.SB", "m01c.Wb", "m01c.pFmax", "m01c.sigmaBmax"):
                if expect[key] is None:
                    raise SystemExit(f"[{name}] 结果变量 {key} 为空")
            if expect["m01c.pF"] <= 0:
                raise SystemExit(f"[{name}] pF={expect['m01c.pF']} 非正")
            cases[name] = {"file": _BASES[base], "changes":
                           [[k, v] for k, v in changes], "expect": expect}
            print(f"[{idx:02d}/{len(CASES)}] {name}: pF={expect['m01c.pF']:.6g} "
                  f"SH={expect['m01c.SH']:.6g} SB={expect['m01c.SB']:.6g}")
    finally:
        try:
            ksoft.ReleaseModule()
        except Exception:
            pass  # noqa: S110 —— 释放失败不带走收割结果
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(json.dumps({
        "source": "KISSsoft 2026 M01C official examples 06/07 + file variants "
                  "(COM GetVar, CalculateRetVal-gated), 2026-10-02",
        "note": "单位：几何 mm、力 N、扭矩 N·m（组件内 Tn 为 N·mm，测试映射 ×1000）。"
                "Kindex∈{0,1,2}→K∈{1,π²/8,π/2}（3 为内核越界怪癖 K=0→SH=inf，组件 Literal 拒）；"
                "split σB 的 i/2 实为 ceil(i/2)（每半毂螺栓数上取整）；"
                "split pF 分母为 l（RPT 备注公式 ls 为笔误）；"
                "SH 的 T 实以 N·mm 入式（备注 N·m 系单位标注笔误）；"
                "许用：GJL（KMAT 铸铁类 DBID 10400/10410/10420）pFmax=PFfactor·Rm、"
                "sigmaBmax=0.5·Rm；韧性（含 own-input DBID=19999）pFmax=PFfactor·min(Rp,0.8·Rm)、"
                "sigmaBmax=0.7·Rp；惰性见证案：split_h90 / split_shaftRp / split_shmin99 / "
                "slotted_ls40 / slotted_k2；slotted 判废面 h≥D+2a、l2>l1 不入金样（calc=False），"
                "组件 check 复刻。",
        "harvest": "python tools/gen_clamp_connection_kisssoft.py",
        "cases": cases,
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"金样落盘：{GOLDEN}（{len(cases)} 案）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
