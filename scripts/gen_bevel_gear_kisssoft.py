"""Z70 锥齿轮 KISSsoft 金样收割机（BevelGearPair 对账；幂等，失败不覆盖旧档）。

- 基座：官方《S01 Bevel (ISO 10300 Sample 1 FM)》与《03 Bevel (DIN 3991 FH)》（DIN3991）
- 变体：文件变体路线（UTF-16 key=value、行尾 ¶、锚定行首、命中数≠1 即废）
- KV/KHα 策略：内核自动机值直接收割（ZP[0].KV.KV / ZP[0].KHa），金样测试回喂组件 Params
- 产出：tests/golden/bevel_gear/kisssoft_z70.json（四键 schema，note 为容差分档唯一权威）
"""

from __future__ import annotations

import json
import math
import os
import re
import time
import traceback
from pathlib import Path

import win32com.client

import pyffalo_root

KS_EXAMPLE = Path(r"C:\KISSsoft 2026\example")
REPO = pyffalo_root.repo_root()
GOLDEN = REPO / "tests" / "golden" / "bevel_gear" / "kisssoft_z70.json"
CASES_DIR = REPO / "tmp" / "z70_golden_cases"

_BASES = {
    "s01": "S01 Bevel (ISO 10300 Sample 1 FM).Z70",  # noqa: E501
    "din03": "03 Bevel (DIN 3991 FH).z70",
}  # noqa: E501

VARS = [
    "RechSt.RechenMethID",
    "ZkegR[0].z", "ZkegR[1].z", "ZR[0].b", "ZS.Geo.mn", "ZS.Geo.alfn",
    "ZS.Geo.betab", "ZP[0].Sigma", "ZkegR[0].WI.betm",
    "ZkegR[0].delta", "ZkegR[1].delta", "ZkegR[0].TK.Re", "ZkegR[0].TK.Rm",
    "ZkegR[0].dm", "ZkegR[1].dm", "ZS.Geo.mt",
    "ZR[0].z", "ZR[0].zn", "ZR[0].d", "ZR[0].dB", "ZR[1].z", "ZR[1].zn", "ZR[1].d",
    "ZR[0].x_YF", "ZR[1].x_YF", "ZkegR[0].XS", "ZkegR[1].XS",
    "ZR[0].BP_f.hfP", "ZR[0].BP_f.rofP", "ZR[1].BP_f.rofP",
    "ZP[0].Eps.a", "ZP[0].Eps.b", "ZP[0].Ft",
    "ZS.KA", "ZP[0].KV.KV", "ZP[0].KHa", "ZP[0].KHb", "ZkegP[0].KHbbe",
    "ZP[0].Fuss.Yeps", "ZP[0].Fuss.Ybet", "ZkegP[0].YK", "ZkegP[0].ZK",
    "ZP[0].Flanke.ZE", "ZP[0].Flanke.Zeps",
    "ZPP[0].Fuss.YF", "ZPP[0].Fuss.YS", "ZPP[0].Fuss.sFn", "ZPP[0].Fuss.hF",
    "ZPP[0].Fuss.roF", "ZPP[0].Fuss.alfen",
    "ZPP[0].Fuss.sigF0", "ZPP[0].Fuss.sigF", "ZPP[0].Fuss.sigFP", "ZPP[0].Fuss.SF",
    "ZPP[1].Fuss.YF", "ZPP[1].Fuss.YS", "ZPP[1].Fuss.sFn", "ZPP[1].Fuss.sigF0",
    "ZPP[1].Fuss.sigFP", "ZPP[1].Fuss.SF",
    "ZP[0].Flanke.sigH0", "ZP[0].Flanke.sigH", "ZPP[0].Flanke.sigHP", "ZPP[0].Flanke.SH",
    "ZPP[0].Fa", "ZPP[0].Fr",
]

_x1 = lambda v: {"ZR[0].x.nul": repr(v), "ZR[0].x.E": repr(v), "ZR[0].x.i": repr(v)}  # noqa: E731
_x2 = lambda v: {"ZR[1].x.nul": repr(v), "ZR[1].x.E": repr(v), "ZR[1].x.i": repr(v)}  # noqa: E731
_d2r = lambda d: repr(__import__("math").radians(d))  # noqa: E731

CASES: list[tuple[str, str, dict[str, object]]] = [
    ("official", "s01", {}),
    ("betm0", "s01", {"ZkegR[0].WI.betm": _d2r(0)}),
    ("betm20", "s01", {"ZkegR[0].WI.betm": _d2r(20)}),
    ("betm25", "s01", {"ZkegR[0].WI.betm": _d2r(25)}),
    ("betm30", "s01", {"ZkegR[0].WI.betm": _d2r(30)}),
    ("betm40", "s01", {"ZkegR[0].WI.betm": _d2r(40)}),
    ("b15", "s01", {"ZR[0].b": "15", "ZR[1].b": "15"}),
    ("b20", "s01", {"ZR[0].b": "20", "ZR[1].b": "20"}),
    ("b30", "s01", {"ZR[0].b": "30", "ZR[1].b": "30"}),
    ("z1_11", "s01", {"ZkegR[0].z": "11"}),
    ("z1_18", "s01", {"ZkegR[0].z": "18"}),
    ("x0.3", "s01", _x1(0.3)),
    ("x0.7", "s01", _x1(0.7)),
    ("xs0", "s01", {"ZkegR[0].XS": "0"}),
    ("xs0.08", "s01", {"ZkegR[0].XS": "0.08"}),
    ("alfn17.5", "s01", {"ZS.Geo.alfn": _d2r(17.5)}),
    ("alfn22.5", "s01", {"ZS.Geo.alfn": _d2r(22.5)}),
    ("KA1.0", "s01", {"ZS.KA": "1.0"}),
    ("KA1.5", "s01", {"ZS.KA": "1.5"}),
    ("KHbbe1.0", "s01", {"ZkegP[0].KHbbe": "1.0"}),
    ("KHbbe1.3", "s01", {"ZkegP[0].KHbbe": "1.3"}),
    ("z2_45", "s01", {"ZkegR[1].z": "45"}),
    # 死变体记录（改档输出不动，内核另有主键，勿再试）：x2 文件改写（r4b 大轮扫经 z2 变更生效、
    # z2=39 基态惰性）、DIN 基座的 betm/KA 单改
    ("Sigma70", "s01", {"ZP[0].Sigma": _d2r(70)}),
    ("din_official", "din03", {}),
    ("din_b25", "din03", {"ZR[0].b": "25", "ZR[1].b": "25"}),
    ("din_z16", "din03", {"ZkegR[0].z": "16"}),
]


def _setkey(text: str, key: str, val) -> str:
    text, n = re.subn(rf"^{re.escape(key)}=[^¶\r\n]*¶",
                      lambda _m: f"{key}={val}¶", text, flags=re.MULTILINE)
    if n != 1:
        raise SystemExit(f"变体键 {key} 替换 {n} 处（应为 1）")
    return text


def _norm(v) -> object:
    if v is None:
        return None
    s = str(v).strip()
    if s == "":
        return None
    try:
        f = float(s)
        return int(f) if f == int(f) and abs(f) < 1e15 and re.fullmatch(r"-?\d+", s) else f
    except ValueError:
        return s


def main() -> None:
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    texts = {n: (KS_EXAMPLE / f).read_text("utf-16") for n, f in _BASES.items()}
    result: dict[str, dict] = {}
    ksoft = win32com.client.Dispatch("KISSsoftCOM.KISSsoft")
    try:
        ksoft.SetSilentMode(True)
        ksoft.GetModule("Z070", True)
        for label, base, ch in CASES:
            t0 = time.time()
            text = texts[base]
            for k, v in ch.items():
                text = _setkey(text, k, v)
            cf = CASES_DIR / f"{label}.z70"
            cf.write_text(text, "utf-16")
            ksoft.LoadFile(str(cf))
            retv = ksoft.CalculateRetVal()
            if not retv:
                raise SystemExit(f"金样案 {label} 判废（CalculateRetVal=False）——不入金样")
            # 变体须真正生效：内核静默忽略的键会把官方案原值当变体结果收进
            # 金样（死变体先例见 spec 批2 节）——逐键回读对账（ocr medium）
            for ck, cv in ch.items():
                got = _norm(ksoft.GetVar(ck))
                try:
                    took = (got is not None
                            and math.isclose(float(got), float(cv), rel_tol=1e-9))
                except (TypeError, ValueError):
                    took = str(got).strip() == str(cv).strip()
                if not took:
                    raise SystemExit(f"金样案 {label} 变体键 {ck} 未生效"
                                     f"（写入 {cv!r}，读回 {got!r}）——中止防陈旧值入库")
            vals = {v: _norm(ksoft.GetVar(v)) for v in VARS}
            for must in ("ZP[0].Ft", "ZPP[0].Fuss.SF", "ZP[0].Flanke.sigH0", "ZPP[0].Flanke.SH",
                         "ZP[0].KV.KV", "ZPP[1].Fuss.SF"):
                if vals.get(must) is None:
                    raise SystemExit(f"金样案 {label} 核心量 {must} 为空——中止防陈旧值入库")
            result[label] = {"file": _BASES[base], "changes": ch, "expect": vals}
            print(f"{label:14} retv=True SF1={vals['ZPP[0].Fuss.SF']:.6f} "
                  f"SF2={vals['ZPP[1].Fuss.SF']:.6f} SH={vals['ZPP[0].Flanke.SH']:.6f} "
                  f"({time.time() - t0:.1f}s)", flush=True)
    finally:
        try:
            ksoft.ReleaseModule()
        except Exception:
            pass

    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    # 原子写：半截写坏会截断既有金样档（docstring 承诺失败不覆盖旧档）
    tmp = GOLDEN.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({
        "source": "KISSsoft 2026 Z070 official examples S01(ISO 10300:2001-B) + 03(DIN 3991) "
                  "+ file variants (COM GetVar, CalculateRetVal-gated), 2026-10-03",
        "note": "容差分档（docs/specs/bevel-hypoid-z70.md 批2节）：几何/ε/力/ZE/装配闭式量 1e-9；"
                "快照表消费量（Yε/Yβ/YK/ρD/hF/R→YF/YS/σF0/σH0/σ 全链与 SF/SH）2e-3；"
                "DIN 案 Y 系数闭式 1e-9 但齿形链共用 ISO 快照表故整体 2e-3 档；"
                "KV/KHα 为内核自动机值回喂（组件显式输入）。v/P 展示量不对账（内核隐速度）。",
        "harvest": "python tools/gen_bevel_gear_kisssoft.py",
        "cases": result,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, GOLDEN)
    print(f"saved: {GOLDEN} ({len(result)} cases)")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1) from None
