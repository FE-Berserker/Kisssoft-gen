"""KISSsoft M1B 官方算例金样收割（COM GetVar 逐变量，幂等，失败不覆盖旧档）。

COM 机制坑（docs/specs/conical-interference-fit-m1b.md 背景口径）：SetSilentMode
先行；GetModule('M01B', True) 返回值丢弃、全部方法在根对象调用；
CalculateRetVal 唯一判据；变量名录 = rpt/M01BLe0.RPT 花括号集 + KVAR 已知量。
03/04 的 Ffmin/af/gamma_max 为内核安全驱动尺寸输出（文件值改写无效）。
用法：``python tools/gen_conical_fit_kisssoft.py``（本机 KISSsoft 2026 + 空闲席位）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GOLDEN = REPO / "tests/golden/conical_fit/kisssoft_m1b.json"
KS_EX = Path("C:/KISSsoft 2026/example")
CASES = {
    "kollmann_03": "03 Conical Interference Fit.M1B",
    "kollmann_nut_04": "04 Conical Interference Fit (With Nut).M1B",
    "din7190_05": "05 Conical Interference Fit (DIN 7190 2).M1B",
}
VARS = json.loads(GOLDEN.read_text(encoding="utf-8"))["cases"]["kollmann_03"]["vars"].keys()


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


def main() -> int:
    import win32com.client as client

    ks = client.Dispatch("KISSsoftCOM.KISSsoft")
    cases: dict[str, dict] = {}
    try:
        ks.SetSilentMode(True)
        try:
            ks.GetModule("M01B", True)
        except Exception:
            ks.GetModule("M01B")
        for name, fname in CASES.items():
            ks.LoadFile(str(KS_EX / fname))
            anchor = _gv(ks, "m01b.beta")
            if anchor is None:
                raise SystemExit(f"[{name}] 锚键失败（未载入？），金样保持原样")
            if not ks.CalculateRetVal():
                raise SystemExit(f"[{name}] CalculateRetVal=False，金样保持原样")
            row = {"file": fname, "calc": True,
                   "vars": {v: _gv(ks, v) for v in VARS}}
            missing = [v for v in ("m01b.p0", "m01b.SR", "m01b.pmit")
                       if row["vars"][v] is None]
            if missing:
                raise SystemExit(f"[{name}] 结果变量缺失 {missing}，金样保持原样")
            cases[name] = row
    finally:
        try:
            ks.ReleaseModule()
        except Exception:  # noqa: BLE001, S110
            pass
    note = json.loads(GOLDEN.read_text(encoding="utf-8"))["note"]
    GOLDEN.write_text(json.dumps(
        {"source": json.loads(GOLDEN.read_text(encoding="utf-8"))["source"],
         "note": note, "cases": cases}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"{len(cases)} 案 → {GOLDEN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
