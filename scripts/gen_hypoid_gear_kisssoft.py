"""Z70 hypoid 金样收割机（HypoidGearPair 对账；幂等，失败不覆盖旧档）。

- 基座：官方《S02 Hypoid (ISO 10300 Sample 2 FM)》（ISO10300-H 域）
- 变体：R5 实测 live 设计输入（z1/z2/de2/偏置 a/b/βm1/Σ）——几何由内核重解后
  全套报告量（δ/dm/βm2/zv/zvn/dB/mn）一并收割，金样测试直接回喂组件输入面
- KV/KHα：内核自动机值收割回喂；T1 由 Ft·dm1/2000 反解（内核口径逐位）
- 产出：tests/golden/hypoid_gear/kisssoft_z70_hypoid.json
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
GOLDEN = REPO / "tests" / "golden" / "hypoid_gear" / "kisssoft_z70_hypoid.json"
CASES_DIR = REPO / "tmp" / "z70_hypoid_golden_cases"

_BASE = "S02 Hypoid (ISO 10300 Sample 2 FM).Z70"

VARS = [
    "RechSt.RechenMethID",
    "ZkegR[0].z", "ZkegR[1].z", "ZR[0].b", "ZS.Geo.mn", "ZS.Geo.alfn",
    "ZP[0].Sigma", "ZkegP[0].a", "ZS.Geo.betab",
    "ZkegR[0].WI.betm", "ZkegR[1].WI.betm",
    "ZkegR[0].delta", "ZkegR[1].delta", "ZkegR[1].de",
    "ZkegR[0].dm", "ZkegR[1].dm",
    "ZR[0].z", "ZR[0].zn", "ZR[0].d", "ZR[0].dB", "ZR[0].x_YF", "ZkegR[0].XS",
    "ZR[1].z", "ZR[1].zn", "ZR[1].d", "ZR[1].dB", "ZR[1].x_YF", "ZkegR[1].XS",
    "ZP[0].Eps.a", "ZP[0].Eps.b", "ZP[0].Ft",
    "ZS.KA", "ZP[0].KV.KV", "ZP[0].KHa", "ZkegP[0].KHbbe",
    "ZP[0].KV.cStr", "ZP[0].KV.cg", "ZP[0].KV.mRed",
    "ZP[0].KV.n", "ZP[0].KV.nE1", "ZP[0].KV.ya",
    "ZkegR[0].nnominal",
    "ZP[0].Fuss.Yeps", "ZP[0].Fuss.Ybet", "ZkegP[0].YK", "ZkegP[0].ZK",
    "ZP[0].Flanke.ZE", "ZP[0].Flanke.Zeps",
    "ZPP[0].Fuss.YF", "ZPP[0].Fuss.YS", "ZPP[0].Fuss.sFn", "ZPP[0].Fuss.hF",
    "ZPP[0].Fuss.roF", "ZPP[0].Fuss.alfen",
    "ZPP[0].Fuss.sigF0", "ZPP[0].Fuss.sigF", "ZPP[0].Fuss.sigFP", "ZPP[0].Fuss.SF",
    "ZPP[1].Fuss.YF", "ZPP[1].Fuss.YS", "ZPP[1].Fuss.sigF0",
    "ZPP[1].Fuss.sigFP", "ZPP[1].Fuss.SF",
    "ZPP[1].Fuss.hF", "ZPP[1].Fuss.roF", "ZPP[1].Fuss.alfen", "ZPP[1].Fuss.sFn",
    "ZPP[1].Flanke.sigHP", "ZPP[1].Flanke.SH",
    "ZP[0].Flanke.sigH0", "ZP[0].Flanke.sigH",
    "ZPP[0].Flanke.sigHP", "ZPP[0].Flanke.SH",
]

_d2r = lambda d: repr(math.radians(d))  # noqa: E731

CASES: list[tuple[str, dict[str, object]]] = [
    ("official", {}),
    ("z1_11", {"ZkegR[0].z": "11"}),
    ("z1_16", {"ZkegR[0].z": "16"}),
    ("z1_20", {"ZkegR[0].z": "20"}),
    ("z2_38", {"ZkegR[1].z": "38"}),
    ("z2_50", {"ZkegR[1].z": "50"}),
    ("b26", {"ZR[0].b": "26", "ZR[1].b": "26"}),
    ("b36", {"ZR[0].b": "36", "ZR[1].b": "36"}),
    ("betm1_45", {"ZkegR[0].WI.betm": _d2r(45)}),
    ("betm1_55", {"ZkegR[0].WI.betm": _d2r(55)}),
    ("a10", {"ZkegP[0].a": "10"}),
    ("a20", {"ZkegP[0].a": "20"}),
    ("a25", {"ZkegP[0].a": "25"}),
    ("de2_160", {"ZkegR[1].de": "160"}),
    ("de2_180", {"ZkegR[1].de": "180"}),
    ("Sigma80", {"ZP[0].Sigma": _d2r(80)}),
    ("Sigma100", {"ZP[0].Sigma": _d2r(100)}),
    ("KA1.0", {"ZS.KA": "1.0"}),
    ("KA1.5", {"ZS.KA": "1.5"}),
    ("KHbbe1.0", {"ZkegP[0].KHbbe": "1.0"}),
    ("KHbbe1.3", {"ZkegP[0].KHbbe": "1.3"}),
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
    base = (KS_EXAMPLE / _BASE).read_text("utf-16")
    result: dict[str, dict] = {}
    ksoft = win32com.client.Dispatch("KISSsoftCOM.KISSsoft")
    try:
        ksoft.SetSilentMode(True)
        ksoft.GetModule("Z070", True)
        for label, ch in CASES:
            t0 = time.time()
            text = base
            for k, v in ch.items():
                text = _setkey(text, k, v)
            cf = CASES_DIR / f"{label}.z70"
            cf.write_text(text, "utf-16")
            ksoft.LoadFile(str(cf))
            retv = ksoft.CalculateRetVal()
            if not retv:
                raise SystemExit(f"金样案 {label} 判废（CalculateRetVal=False）——不入金样")
            # 变体须真正生效：内核静默忽略的键会把官方案原值当变体结果收进
            # 金样——逐键回读对账（ocr medium，与 bevel 收割器同款）。
            # b 键豁免：hypoid 几何由内核重解，写 26 → 重解 27.82（官方金样即此口径，
            # σF0 随 b 写入显著变化即生效证据；等值检查会误杀派生输入）
            _derived_b = {"ZR[0].b", "ZR[1].b"}
            for ck, cv in ch.items():
                if ck in _derived_b:
                    continue
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
            for must in ("ZP[0].Ft", "ZPP[0].Fuss.SF", "ZP[0].Flanke.sigH0",
                         "ZPP[0].Flanke.SH", "ZP[0].KV.KV", "ZR[0].dB", "ZR[0].zn"):
                if vals.get(must) is None:
                    raise SystemExit(f"金样案 {label} 核心量 {must} 为空——中止防陈旧值入库")
            result[label] = {"file": _BASE, "changes": ch, "expect": vals}
            print(f"{label:14} retv=True SF1={vals['ZPP[0].Fuss.SF']:.6f} "
                  f"SH={vals['ZPP[0].Flanke.SH']:.6f} ({time.time() - t0:.1f}s)", flush=True)
    finally:
        try:
            ksoft.ReleaseModule()
        except Exception:
            pass

    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    # 原子写：半截写坏会截断既有金样档（docstring 承诺失败不覆盖旧档）
    tmp = GOLDEN.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({
        "source": "KISSsoft 2026 Z070 official example S02 Hypoid (ISO 10300 Sample 2 FM) "
                  "+ file variants on live design inputs (COM GetVar, "
                  "CalculateRetVal-gated), 2026-10-03",
        "note": "容差分档（docs/specs/bevel-hypoid-z70.md 批 4 节）：几何闭式量（Ft/ZE）1e-9；"
                "εα 4e-5/εβ 表 1e-2；报告直取量逐位；hypoid 表消费链（Yβ/YK/ρD/R→YF/YS/"
                "σF0/σH0/σ/SF/SH）1e-1 首版档（散点 66 案稀疏域，S02 系坐标离格最近邻）；"
                "几何由内核重解——组件输入面消费收割的报告量全套。",
        "harvest": "python tools/gen_hypoid_gear_kisssoft.py",
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
