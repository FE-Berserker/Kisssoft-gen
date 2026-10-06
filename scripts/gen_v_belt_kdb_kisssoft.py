"""KISSsoft Z090 带型固有参数收割器（COM DinIdK 扫描 → CSV 快照）。

经 KISSsoftCOM 对官方算例 ``01 V Belt.Z90``（SPZ-CONTI）做文件变体，逐
``z090k.DinIdK``（10090..10340 步 10，26 个）读取 KDB 固有参数四标量
``belt.vmax / belt.elast / belt.massPerM / belt.my`` 与 ``z090k.DinName``
回显，输出 ``tools/data/kisssoft/v_belt_kdb.csv`` 作为
``tools/gen_v_belt_seeds.py`` 的数据源快照。

机制要点（2026-10-05 两轮探针钉死，tmp/z90_dinidk_probe 产物）：

- **DinIdK 是 KDB 主键**（不是 UI 下拉的 ``belt.Typ``——旧 spec「Typ=1/2
  空数据、≥3 回落」的现象根源即此：Typ 序与 KDB 行无关，改 Typ 不换带型）；
- 26 个 ID 覆盖 dat 009-034（美制 6 + XP-CONTI 4 + Classic 3 + 窄型
  CONTI 4 + Multiflex 9）；**dat 001-008（SP*-Fenner 1997 目录 + 旧 XP
  formgezahnt 系）无 KDB 行**——KISSsoft 自身无此 8 型固有参数（组件侧
  对齐拒算，见 docs/specs/vbelt-z90-m2.md）；
- Z000.KDB 数字区（0x3c1ee 起 34 组 × 0x54 字节）与 ID 行存在一对错位
  的尾段（组 20-26 的行尾 ID 与数据不匹配），故四标量以 DinIdK 直读为
  唯一权威，数字区逆向仅作旁证（SPZ-CONTI 四值逐位互证）。

锚点断言：SPZ-CONTI（10220）四值 == (50, 44308, 0.072, 1.3)
（与一期 COM 采集的库内现值逐位）。

用法::

    python scripts/gen_v_belt_kdb_kisssoft.py            # COM 扫描 → 快照
    python scripts/gen_v_belt_kdb_kisssoft.py --check     # 只验仓内快照锚点
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import pyffalo_root

REPO = pyffalo_root.repo_root()
EXAMPLE = Path(r"C:/KISSsoft 2026/example/01 V Belt.Z90")
DAT_DIR = REPO / "tools/data/z90_dat"
OUT_CSV = REPO / "tools/data/kisssoft/v_belt_kdb.csv"
CASES_DIR = REPO / "tmp/z90_kdb_cases"
SOURCE = "KISSsoft 2026 Z090 COM sweep (DinIdK 10090..10340; belt.vmax/elast/massPerM/my)"

#: DinIdK → (dat 序, Code, 截面 token, 族)。dat 序与 Code 依据 DinName 回显
#: （探针 2026-10-05）与 dat 头 ``-- Norm:`` 行互证；截面 token 用于收割
#: 期断言（dat 头必须含该 token）；族供预紧/挠度检验分支与 Auto 标注。
ID_MAP: dict[int, tuple[int, str, str, str]] = {
    10090: (10, "3V-9N", "3V", "USA"),
    10100: (12, "5V-15N", "5V", "USA"),
    10110: (14, "8V-25N", "8V", "USA"),
    10120: (9, "3V-9J", "3V", "USA"),
    10130: (11, "5V-15J", "5V", "USA"),
    10140: (13, "8V-25J", "8V", "USA"),
    10150: (15, "XPA-FOZ", "XPA", "CONTI"),
    10160: (16, "XPB-FOZ", "XPB", "CONTI"),
    10170: (17, "XPC-FOZ", "XPC", "CONTI"),
    10180: (18, "XPZ-FOZ", "XPZ", "CONTI"),
    10190: (19, "5-CLASSIC", "5", "CONTI"),
    10200: (20, "6Y-CLASSIC", "6", "CONTI"),
    10210: (21, "8-CLASSIC", "8", "CONTI"),
    10220: (22, "SPZ-CONTI", "SPZ", "CONTI"),
    10230: (23, "SPA-CONTI", "SPA", "CONTI"),
    10240: (24, "SPB-CONTI", "SPB", "CONTI"),
    10250: (25, "SPC-CONTI", "SPC", "CONTI"),
    10260: (26, "8-MF", "8", "CONTI"),
    10270: (27, "10Z-MF", "10", "CONTI"),
    10280: (28, "13A-MF", "13", "CONTI"),
    10290: (29, "17B-MF", "17", "CONTI"),
    10300: (30, "20-MF", "20", "CONTI"),
    10310: (31, "22C-MF", "22", "CONTI"),
    10320: (32, "25-MF", "25", "CONTI"),
    10330: (33, "32D-MF", "32", "CONTI"),
    10340: (34, "40E-MF", "40", "CONTI"),
}

#: 无 KDB 行的 8 型（dat 001-008，1997 目录系）：Code 由 dat 头 Norm 判读
#: （005-008 实序 XPA/XPB/XPC/XPZ——formgez/formgezahnt 1997 匿名目录）
NO_KDB_DATS = {
    1: "SPA-FENNER", 2: "SPB-FENNER", 3: "SPC-FENNER", 4: "SPZ-FENNER",
    5: "XPA-V1997", 6: "XPB-V1997", 7: "XPC-V1997", 8: "XPZ-V1997",
}


def dat_norm_token(dat_no: int) -> str:
    """dat 头 ``-- Norm:`` 行（latin-1）——收割期与截面 token 互证。"""
    path = next(DAT_DIR.glob(f"Z090-{dat_no:03d}.[Dd][Aa][Tt]"))
    head = path.read_text(encoding="latin-1", errors="replace")[:2000]
    m = re.search(r"--\s*Norm:\s*(.+)", head)
    return m.group(1).strip() if m else ""


def make_variant(path: Path, dinid: int) -> None:
    with EXAMPLE.open(encoding="utf-16", newline="") as fh:
        text = fh.read()
    text = re.sub(r"^z090k\.DinIdK=[^¶]*¶", f"z090k.DinIdK={dinid}¶",
                  text, flags=re.MULTILINE)
    with path.open("w", encoding="utf-16", newline="") as fh:
        fh.write(text)


def sweep() -> int:
    import win32com.client as client

    CASES_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    ksoft = client.Dispatch("KISSsoftCOM.KISSsoft")
    try:
        ksoft.SetSilentMode(True)
        ksoft.GetModule("Z090", True)
        for dinid, (dat_no, code, token, family) in sorted(ID_MAP.items()):
            norm = dat_norm_token(dat_no)
            if token not in norm:
                raise SystemExit(
                    f"dat {dat_no:03d} 头 Norm={norm!r} 不含截面 token "
                    f"{token!r}——ID 映射表与 dat 内容不符，中止")
            case = CASES_DIR / f"id{dinid}.Z90"
            make_variant(case, dinid)
            ksoft.LoadFile(str(case))
            # CalculateRetVal=False 只挡算例功率校核（PN/n1 对该带型超
            # 域判废），KDB 标量在判废前已解析、GetVar 照常可读（探针
            # 26 ID 实证：仅 7 个 ok=True 但四标量全部非零返回）
            ok = bool(ksoft.CalculateRetVal())
            name = str(ksoft.GetVar("z090k.DinName"))
            vmax = float(ksoft.GetVar("belt.vmax"))
            elast = float(ksoft.GetVar("belt.elast"))
            q = float(ksoft.GetVar("belt.massPerM"))
            mu = float(ksoft.GetVar("belt.my"))
            if not ok:
                print(f"{dinid} ({code}): 算例工况判废（KDB 标量照常采集）",
                      flush=True)
            if vmax not in (0.0, 30.0, 50.0) or q <= 0.0 or mu <= 0.0:
                raise SystemExit(
                    f"{dinid} ({code}) 四标量异常 (vmax={vmax:g}, q={q:g}, "
                    f"mu={mu:g})——KDB 读取失败，中止")
            rows.append({
                "DinIdK": dinid, "DatNo": dat_no, "Code": code,
                "DinName": name, "Family": family,
                "vmax_ms": round(vmax, 6), "elast_N": round(elast, 6),
                "q_kgm": round(q, 6), "mu": round(mu, 6),
                "Source": SOURCE,
            })
            print(f"{dinid} {code:<11} family={family:<7} vmax={vmax:g} "
                  f"elast={elast:g} q={q:g} mu={mu:g}  {name}", flush=True)
    finally:
        try:
            ksoft.ReleaseModule("Z090")
        except Exception:  # noqa: BLE001
            pass
    write_rows(rows)
    return 0


def write_rows(rows: list[dict]) -> None:
    anchor = next(r for r in rows if r["Code"] == "SPZ-CONTI")
    assert (anchor["vmax_ms"], anchor["elast_N"], anchor["q_kgm"],
            anchor["mu"]) == (50.0, 44308.0, 0.072, 1.3), "SPZ-CONTI 锚点漂移"
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} 型 -> {OUT_CSV}")


def check() -> int:
    """仓内快照锚点 + 完整性核对（离线，CI 可跑）。"""
    with OUT_CSV.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 26, f"快照应 26 行，实为 {len(rows)}"
    anchor = next(r for r in rows if r["Code"] == "SPZ-CONTI")
    assert (float(anchor["vmax_ms"]), float(anchor["elast_N"]),
            float(anchor["q_kgm"]), float(anchor["mu"])) == (
        50.0, 44308.0, 0.072, 1.3), "SPZ-CONTI 锚点漂移"
    assert all(float(r["q_kgm"]) > 0 for r in rows), "存在零行（扫描异常）"
    print(f"{OUT_CSV}: 26 型锚点核对通过")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="只验仓内快照锚点（离线）")
    args = ap.parse_args(argv)
    return check() if args.check else sweep()


if __name__ == "__main__":
    sys.exit(main())
