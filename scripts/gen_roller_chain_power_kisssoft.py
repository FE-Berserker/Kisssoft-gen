"""KISSsoft Z92 额定功率曲线快照生成器（COM 扫描，ISO 10823 口径）。

经 KISSsoftCOM 对 Z092 逐链型 × 转速扫描 ``Pkette``（最大可传递功率 =
min(Pc1 链板疲劳, Pc2 滚子/套筒疲劳, Pc3 销套磨损)），输出
``tools/data/kisssoft/roller_chain_power_curve.csv`` 作为
``tools/gen_roller_chain_power_seeds.py`` 的数据源快照。

无界面 COM 模式的 Z92 约束（实测，2026.0）：

- ``SetVar`` 改输入后 ``Calculate`` 一律失败；**必须文件变体 + LoadFile**
  （``.Z92`` 为 UTF-16 明文，``key=value¶`` 行替换）。
- 任何使链节数 X 离开算例缓存值 104 的改动（改 a / 改 p / 直改 ZahneZ）→
  计算失败（belt 布置重排不可用）。对策：``a = (104 − z1)·p/2``（z1=z2 时
  X = 2a/p + z 精确成立），X 恒 104。
- ``TypID = 10000 + 10×(KDB CSV 行号 + 1)``（10110=06B-2 官方算例证实，
  10130=08A-1、10200=10A-1、10260=12A-1、10290=12B-1 求解层复核）。
- ``SetSilentMode(True)`` 抑制模态框（否则 Calculate 挂起）。

扫描口径：z1=z2=19（f2=1）、单排（Kp=1）、X=104、PN=5 kW —— ``Pkette``
即功率表标定值 P0。链型自检：Typ/Fu/p 与 KDB 快照逐项断言。

用法::

    python tools/gen_roller_chain_power_kisssoft.py            # 扫描 → 快照
    python tools/gen_roller_chain_power_kisssoft.py --dry-run  # 只生成变体不跑 COM
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXAMPLE = Path(r"C:/KISSsoft 2026/example/04 Chain Drive.Z92")
PROFILES = REPO / "tools/data/kisssoft/roller_chain_profiles.csv"
OUT_CSV = REPO / "tools/data/kisssoft/roller_chain_power_curve.csv"
CASES_DIR = REPO / "tmp/z92_sweep_cases"
SOURCE = "KISSsoft 2026 Z092 COM sweep (z1=19, simplex, X=104; ISO 10823)"

X_LOCK = 104
Z1 = 19
SPEEDS = [50, 75, 100, 150, 200, 300, 400, 600, 800, 900, 960, 1000,
          1200, 1400, 1500, 1800, 2000]
#: 扫描链型（KDB designation → 功率表 Code）：手册表 12 型 + 06B-1（组件 demo）
SCAN = ["06B-1", "08A-1", "08B-1", "10A-1", "10B-1", "12A-1", "12B-1",
        "16A-1", "16B-1", "20A-1", "20B-1", "24A-1", "24B-1"]

#: Pc2 坠落区判据：Pkette 低于已见峰值 25% 记录末点后截断（≈手册「-」判废档）
FALLOFF_FRACTION = 0.25


def load_profiles() -> dict[str, dict]:
    with PROFILES.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return {r["designation"]: {**r, "_row": i} for i, r in enumerate(rows)}


def typ_id(row: int) -> int:
    return 10000 + 10 * (row + 1)


def make_variant(path: Path, edits: dict[str, str]) -> None:
    with EXAMPLE.open(encoding="utf-16", newline="") as fh:
        text = fh.read()
    for k, v in edits.items():
        # 命中数闸（同 gen_torsion_bar 等 _setkey 口径）：键缺失（KISSsoft
        # 版本变动改键名）时裸 re.sub 会静默写出未改写的变体——COM 路径
        # 的 Typ/Fu 自检不覆盖 z092k.a/PN，错参数会一路喂进快照 CSV
        text, n = re.subn(rf"^{re.escape(k)}=[^¶]*¶", f"{k}={v}¶", text,
                          flags=re.MULTILINE)
        if n != 1:
            raise SystemExit(f"Z92 变体键改写失败 {k}={v}（命中 {n} 处）")
    with path.open("w", encoding="utf-16", newline="") as fh:
        fh.write(text)


def _case_edits(profiles: dict[str, dict], desig: str) -> tuple[str, dict[str, str], float]:
    """链型 → (code, 变体基础键值, 期望 Fu)——dry 变体生成与 COM 扫描共用。"""
    prof = profiles[desig]
    code = desig.removesuffix("-1")
    p = float(prof["p_mm"])
    a = (X_LOCK - Z1) * p / 2
    base = {
        "z092k.TypID": str(typ_id(prof["_row"])),
        "z092k.z1": str(Z1), "z092k.z2": str(Z1),
        "z092k.PN": "5", "z092k.a": repr(a),
    }
    return code, base, float(prof["tensile_Q_kN"])


def sweep(dry: bool) -> int:
    profiles = load_profiles()
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    if dry:
        # --dry-run 只生成变体：不 import win32com、不 Dispatch——不依赖
        # COM 注册即可生成与检查变体内容（算例模板 EXAMPLE 仍取自
        # KISSsoft 安装目录，main() 有存在性门控；2026-10 勘误：原实现
        # COM 初始化在 dry 判断之前，dry 连 COM 都躲不开）
        for desig in SCAN:
            code, base_edits, _fu = _case_edits(profiles, desig)
            for n in SPEEDS:
                edits = {**base_edits, "z092k.n1": str(n), "z092k.n2": str(n)}
                case = CASES_DIR / f"{code}_n{n}.Z92"
                make_variant(case, edits)
                print(f"[dry] {code} n={n} -> {case.name}")
        print(f"[dry] {len(SCAN)} 型 × {len(SPEEDS)} 档 -> {CASES_DIR}")
        return 0
    out_rows: list[dict] = []
    import win32com.client as client

    ksoft = client.Dispatch("KISSsoftCOM.KISSsoft")
    try:
        ksoft.SetSilentMode(True)
        ksoft.GetModule("Z092", True)
        for desig in SCAN:
            code, base_edits, fu_expect = _case_edits(profiles, desig)
            peak = 0.0
            stopped = False
            for n in SPEEDS:
                if stopped:
                    break
                edits = {**base_edits, "z092k.n1": str(n), "z092k.n2": str(n)}
                case = CASES_DIR / f"{code}_n{n}.Z92"
                make_variant(case, edits)
                ksoft.LoadFile(str(case))
                ok = ksoft.CalculateRetVal()
                if not ok:
                    print(f"{code}: n={n} 计算失败 → 截断（更高档判废）", flush=True)
                    stopped = True
                    continue
                typ = ksoft.GetVar("z092k.Typ")
                fu = float(ksoft.GetVar("z092k.Fu"))
                if typ != code or abs(fu - fu_expect) > 0.15:
                    print(f"{code}: 自检失败 Typ={typ} Fu={fu}（期望 {fu_expect}）→ 跳过该型",
                          flush=True)
                    stopped = True
                    continue
                p0 = float(ksoft.GetVar("z092k.Pkette"))
                pc = (float(ksoft.GetVar("z092k.Pc1")),
                      float(ksoft.GetVar("z092k.Pc2")),
                      float(ksoft.GetVar("z092k.Pc3")))
                out_rows.append({
                    "Code": code, "Speed_rpm": n, "P0_kW": round(p0, 4),
                    "Pc1_kW": round(pc[0], 4), "Pc2_kW": round(pc[1], 4),
                    "Pc3_kW": round(pc[2], 4), "Source": SOURCE,
                })
                peak = max(peak, p0)
                print(f"{code} n={n:>4}: P0={p0:8.4f}  (Pc1={pc[0]:.2f} "
                      f"Pc2={pc[1]:.2f} Pc3={pc[2]:.2f})", flush=True)
                if p0 < FALLOFF_FRACTION * peak:
                    print(f"{code}: n={n} 进入坠落区（{p0:.2f} < 25%×{peak:.2f}）→ 截断",
                          flush=True)
                    stopped = True
    finally:
        try:
            ksoft.ReleaseModule()
        except Exception:  # noqa: BLE001, S110
            pass
    if not out_rows:
        # 全部链型首档即判废/自检失败：显式失败并保留原快照——原实现先
        # 以 "w" 打开再取 out_rows[0]，既 IndexError 又已截断仓内 CSV
        raise SystemExit(
            "COM 扫描未产出任何断点（各链型首档即判废/自检失败）——"
            "不写快照，保留既有 CSV")
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0]))
        w.writeheader()
        w.writerows(out_rows)
    print(f"{len(out_rows)} 断点 -> {OUT_CSV}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="只生成变体文件不跑 COM")
    args = ap.parse_args(argv)
    if not EXAMPLE.exists():
        raise SystemExit(f"未找到 KISSsoft 算例：{EXAMPLE}")
    return sweep(dry=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
