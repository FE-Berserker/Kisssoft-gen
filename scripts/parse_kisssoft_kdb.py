"""KISSsoft Z000.KDB 滚子链型表（anfZ092PROFIL / Z092TYP）快照抽取器。

只读 ``C:/KISSsoft 2026/kdb/Z000.KDB``，抽取链型尺寸行导出 CSV，作为
``tools/gen_roller_chain_seeds.py`` 的数据源快照（docs/KISSSOFT.md Z92 专项节）。

布局（2026 版实测）：
- 字符串区：每条记录 9 个 UTF-16LE ``\\0`` 结尾串，依次
  NAME("DIN ISO 606:2012 08B-1"), TYP("08B"), MODUL("Z092TYP"),
  CREATE_BY, CREATE_DATE, CREATE_TIME, UPDATE_BY, UPDATE_DATE, UPDATE_TIME；
- 数字区：紧随字符串区，每行 16 个 double（stride 0x80），前 10 列为
  TEILUNG(p), ANZAHL(排数), D1, D2, B1, B2, BTOT, H2, STATUS, FU(最小抗拉 kN)，
  后 6 列为字符串引用（按 double 读出为非正规浮点，忽略）。

列含义由 ISO 606 公开标准值锚定（08B: p=12.7/d1=8.52/d2=4.45/b1=7.75；
05B-1: Q=4.4 kN；06B-1: Q=8.9 kN），锚点互证在 seed 的 ``_self_check``。

用法::

    python tools/parse_kisssoft_kdb.py [Z000.KDB 路径] [-o 输出 CSV]
"""

from __future__ import annotations

import argparse
import csv
import re
import struct
import sys
from pathlib import Path

DEFAULT_KDB = Path(r"C:/KISSsoft 2026/kdb/Z000.KDB")
DEFAULT_OUT = Path(__file__).parent / "data" / "kisssoft" / "roller_chain_profiles.csv"
NAME_PREFIX = "DIN ISO 606:2012 "
ROW_DOUBLES = 16
STRIDE = ROW_DOUBLES * 8
NUMERIC_COLS = ("p_mm", "strands", "roller_d1_mm", "pin_d2_mm", "inner_b1_mm",
                "outer_b2_mm", "total_btot_mm", "plate_h2_mm")


def _read_utf16z(data: bytes, off: int) -> str:
    """按 UTF-16LE code unit 逐个读取至 0x0000 终止。

    不能用 ``find(b"\\x00\\x00")``：ASCII 字符高位字节恒为 00，与终止符
    相邻时会把「字符高字节 + 终止首字节」误判为终止位置。
    """
    chars: list[str] = []
    limit = len(data) // 2
    pos = off // 2
    while pos < limit:
        unit = data[2 * pos] | (data[2 * pos + 1] << 8)
        if unit == 0:
            break
        chars.append(chr(unit))
        pos += 1
    return "".join(chars)


def parse_records(data: bytes) -> list[dict]:
    """抽取全部 Z092TYP 记录：字符串区条目 + 数字区行。"""
    prefix = NAME_PREFIX.encode("utf-16-le")
    offs = [m.start() for m in re.finditer(re.escape(prefix), data)]
    if not offs:
        raise SystemExit("KDB 中未找到 DIN ISO 606:2012 链型记录")
    records = []
    for off in offs:
        name = _read_utf16z(data, off + len(prefix))
        typ = _read_utf16z(data, off + len(prefix) + 2 * len(name) + 2)
        records.append({"name": name, "typ": typ})
    start = _locate_numeric_region(data, offs[-1])
    if len(data) - start < len(records) * STRIDE:
        raise SystemExit("数字区长度与记录数不符")
    for i, rec in enumerate(records):
        vals = struct.unpack_from(f"<{ROW_DOUBLES}d", data, start + i * STRIDE)
        for key, v in zip(NUMERIC_COLS, vals, strict=False):
            rec[key] = v
        rec["tensile_Q_kN"] = vals[9]
    return records


def _locate_numeric_region(data: bytes, last_name_off: int) -> int:
    """在最后一条字符串记录之后定位数字区行首。

    逐 2 字节偏移试探（KDB 序列化不做对齐填充，行首可落在任意偶偏移），
    要求行 0 与行 6、行 110（共 112 条记录）都通过
    几何有效性（p、排数合理且 d1 < p）；字符串区内的 UTF-16 字节几乎
    不可能同时伪造三行合法 double，故从最后一条 NAME 起直接扫即可。
    """
    window_end = min(len(data) - 111 * STRIDE, last_name_off + 0x2000)
    for cand in range(last_name_off & ~1, window_end, 2):
        rows = [struct.unpack_from(f"<{ROW_DOUBLES}d", data, cand + i * STRIDE)
                for i in (0, 6, 110)]
        if all(5.0 <= r[0] <= 160.0 and r[1] in (1.0, 2.0, 3.0) and 0 < r[2] < r[0]
               for r in rows):
            return cand
    raise SystemExit("未定位到数字区行首")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("kdb", nargs="?", type=Path, default=DEFAULT_KDB)
    ap.add_argument("-o", "--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    data = args.kdb.read_bytes()
    records = parse_records(data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["designation", "series", *NUMERIC_COLS, "tensile_Q_kN"])
        for r in records:
            # 085 等 ANSI 轻型号无系列字母，归 X（其他）
            series = r["typ"][-1] if r["typ"][-1] in "ABCH" else "X"
            w.writerow([r["name"], series, *(round(r[k], 4) for k in NUMERIC_COLS),
                        round(r["tensile_Q_kN"], 3)])
    print(f"{len(records)} 条链型 -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
