"""KISSsoft COM 变工况扫描：Typ=0（SPZ-CONTI → Z090-022.DAT）下采样
功率 / 转速 / 轮径 / 带长 / 工况系数 / 传动比各维，dump 全输出变量，
供 VBeltDrive 受力链（TrF 目录法 / defkat / 轴载 / 临界带速）公式反推
与对拍。

副本改写注意：原算例行结构 ``key=value¶\\r\\n``；由中心距定带长的点
删除 ``belt.Lange`` 行（保留 z090k.a），其余点保留两行（几何自洽值）。

用法：

    python scripts/kisssoft_com_scan.py [输出 json]
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

CASE = Path(r"C:\KISSsoft 2026\example\01 V Belt.Z90").resolve()

VARS = [
    "z090k.i", "z090k.a", "belt.Lange", "sheave[0].umschl",
    "z090k.ScheibenBreite", "z090k.n2",
    "z090k.Pmax", "z090k.powerNR", "z090k.powerAdd", "z090k.factorAngle",
    "z090k.factorLength", "z090k.factorINCR", "belt.nth", "belt.neff",
    "z090k.Sich", "z090k.v", "belt.hz", "z090k.sch",
    "z090k.T1", "z090k.T2", "belt.fcirc", "belt.fcent",
    "z090k.Fdefkat", "z090k.defkat", "z090k.TrF", "z090k.LeerTrF",
    "z090k.LastTrF", "belt.vKritLeer", "belt.vKritLast", "belt.beltSpann",
    "sheave[0].AxKftBet", "sheave[0].AxKftSt",
    "z090k.TrFmin", "z090k.LeerTrFmin", "z090k.LastTrFmin",
    "z090k.vKritLeermin", "z090k.vKritLastmin", "z090k.beltSpannmin",
    "z090k.AxKftBetmin1", "z090k.AxKftStmin1",
]

#: 扫描工况：标签 → (dd1, dd2, n1, P, cB, a)
SCAN = [
    # A 组：变功率（TrF 链随载荷）
    ("P0.5", 100, 200, 1500, 0.5, 1.0, 461.67),
    ("P1",   100, 200, 1500, 1.0, 1.0, 461.67),
    ("P3",   100, 200, 1500, 3.0, 1.0, 461.67),
    ("P5",   100, 200, 1500, 5.0, 1.0, 461.67),
    # B 组：变转速
    ("n500",  100, 200, 500, 2.0, 1.0, 461.67),
    ("n960",  100, 200, 960, 2.0, 1.0, 461.67),
    ("n2900", 100, 200, 2900, 2.0, 1.0, 461.67),
    # C 组：变轮径（带长按几何自洽重算）
    ("dd63",  63, 125, 1500, 2.0, 1.0, 461.67),
    ("dd140", 140, 280, 1500, 2.0, 1.0, 461.67),
    ("dd180", 180, 356, 1500, 2.0, 1.0, 461.67),
    # D 组：变工况系数
    ("cB1.2", 100, 200, 1500, 2.0, 1.2, 461.67),
    ("cB1.5", 100, 200, 1500, 2.0, 1.5, 461.67),
    ("cB2",   100, 200, 1500, 2.0, 2.0, 461.67),
    # E 组：变传动比（i=1 同径 / i=1.5）
    ("i1",   100, 100, 1500, 2.0, 1.0, 461.67),
    ("i1.5", 100, 150, 1500, 2.0, 1.0, 461.67),
    # F 组：变带长（a 按目标带长反解）
    ("L1250", 100, 200, 1500, 2.0, 1.0, None),
    ("L1800", 100, 200, 1500, 2.0, 1.0, None),
    ("L2500", 100, 200, 1500, 2.0, 1.0, None),
]

_F_LEN = {  # F 组目标标准带长（Z090-022 Laenge 系列内）
    "L1250": 1250.0, "L1800": 1800.0, "L2500": 2500.0,
}


def _belt_len(dd1: float, dd2: float, a: float) -> float:
    import math
    return 2.0 * a + math.pi * (dd1 + dd2) / 2.0 + (dd2 - dd1) ** 2 / (4.0 * a)


def _a_from_len(length: float, dd1: float, dd2: float) -> float:
    import math
    x = math.pi * (dd1 + dd2) / 2.0
    y = (dd2 - dd1) ** 2
    return ((length - x) + math.sqrt((length - x) ** 2 - 2.0 * y)) / 4.0


def variant(tag: str, dd1: int, dd2: int, n1: int, p: float, cb: float,
            a: float | None, belt_len: float | None) -> Path:
    """副本：全部行保留（删行会让 KISSsoft 载入异常）。

    F 组（a=None、belt_len 给定）按目标带长反解 a，写自洽的 a / Lange 对；
    其余组按给定 a 现算几何带长写入（KISSsoft 内部再圆整到标准档）。
    """

    if a is None:
        a = _a_from_len(belt_len, dd1, dd2)
    ld = _belt_len(dd1, dd2, a)
    ratio = dd2 / dd1
    text = CASE.read_bytes().decode("utf-16")
    lines = []
    for line in text.split("¶"):
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key == "sheave[0].d":
            lines.append(f"sheave[0].d={dd1}")
        elif key == "sheave[1].d":
            lines.append(f"sheave[1].d={dd2}")
        elif key == "z090k.i":
            # i 是显式输入且锁定反算 dd2——变径必须同步改 i
            lines.append(f"z090k.i={ratio:.6g}")
        elif key == "z090k.n1":
            lines.append(f"z090k.n1={n1}")
        elif key == "z090k.PN":
            lines.append(f"z090k.PN={p}")
        elif key == "z090k.cB":
            lines.append(f"z090k.cB={cb}")
        elif key == "z090k.a":
            lines.append(f"z090k.a={a!r}")
        elif key == "belt.Lange":
            lines.append(f"belt.Lange={ld!r}")
        else:
            lines.append(line)
    out = CASE.parent / f"_scan_{tag}.Z90"
    out.write_bytes("¶".join(lines).encode("utf-16"))
    return out


def _rewrite_neff(path: Path, neff: int) -> Path:
    text = path.read_bytes().decode("utf-16")
    lines = []
    for line in text.split("¶"):
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        lines.append(f"belt.neff={neff}" if key == "belt.neff" else line)
    path.write_bytes("¶".join(lines).encode("utf-16"))
    return path


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else "tmp/z90_scan.json"

    import win32com.client

    ksoft = win32com.client.Dispatch("KISSsoftCOM.KISSsoft")
    ksoft.SetSilentMode(True)
    ksoft.GetModule("Z090", True)

    scan = {}
    for tag, dd1, dd2, n1, p, cb, a in SCAN:
        belt_len = None
        if tag.startswith("L"):
            belt_len = _F_LEN.get(tag)
        entry: dict[str, str] = {"__inputs__": f"dd={dd1}/{dd2} n={n1} "
                               f"P={p} cB={cb} a={a} L={belt_len}"}
        try:
            case_file = variant(tag, dd1, dd2, n1, p, cb, a, belt_len)
            ksoft.LoadFile(str(case_file))
            ksoft.Calculate()
            # 目录法预紧链要求 neff ≥ nth：按理论根数自适应带根数重算
            nth = float(ksoft.GetVar("belt.nth"))
            neff_auto = max(1, math.ceil(nth - 1e-9))
            if neff_auto != 1:
                ksoft.LoadFile(str(_rewrite_neff(case_file, neff_auto)))
                ksoft.Calculate()
            entry["__neff__"] = str(neff_auto)
            for var in VARS:
                try:
                    entry[var] = str(ksoft.GetVar(var))
                except Exception as exc:  # noqa: BLE001
                    entry[var] = f"<ERR {exc}>"
        except Exception as exc:  # noqa: BLE001
            entry["__load__"] = f"<ERR {exc}>"
        scan[tag] = entry
        print(f"{tag:8s} neff={entry.get('__neff__', '?'):>2s} "
              f"TrF={entry.get('z090k.TrF', '?'):>22s} "
              f"nth={entry.get('belt.nth', '?')[:8]} "
              f"defkat={entry.get('z090k.defkat', '?')[:8]}")
    ksoft.ReleaseModule()

    for tag in scan:
        probe = CASE.parent / f"_scan_{tag}.Z90"
        probe.unlink(missing_ok=True)

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(scan, fh, ensure_ascii=False, indent=1)
    print(f"saved -> {out_path}")


if __name__ == "__main__":
    main()
