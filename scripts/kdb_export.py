"""Export every table of KISSsoft ``*.KDB`` files to per-table CSV files.

Usage::

    python scripts/kdb_export.py <folder-or-file> [-o OUTPUT_DIR]

Creates ``OUTPUT_DIR/<KDB-stem>/<TABLE>.csv`` (UTF-8 BOM, Excel-friendly)
plus ``OUTPUT_DIR/index.csv`` listing every exported table. Multi-language
pool strings (``#TS(de¬en¬...)TS~``) are reduced to their first (German)
variant; the raw values stay available through ``tools/kdb_reader.py``.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from kdb_reader import KdbFile, first_language  # noqa: E402

#: KDB 内部表名消毒（文件名非法字符 + 路径分隔符——外部文件内容不进路径）
_SAFE_NAME = re.compile(r'[\\/:*?"<>|]')


def cell(value) -> object:
    if isinstance(value, str):
        return first_language(value).replace("\r", " ").replace("\n", " ")
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    return value


def export_file(kdb_path: Path, out_root: Path) -> list[dict]:
    kdb = KdbFile(str(kdb_path))
    out_dir = out_root / _SAFE_NAME.sub("_", kdb_path.stem)
    out_dir.mkdir(parents=True, exist_ok=True)
    index = []
    for name, tab in kdb.tables.items():
        safe = _SAFE_NAME.sub("_", name)
        csv_path = out_dir / f"{safe}.csv"
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh)
            writer.writerow(tab.columns)
            for row in tab.records:
                writer.writerow([cell(row[c]) for c in tab.columns])
        index.append({
            "file": kdb_path.name, "table": name,
            "rows": tab.n_records, "columns": len(tab.fields),
            "csv": str(csv_path.relative_to(out_root)),
        })
        print(f"  {kdb_path.name}:{name:16s} {tab.n_records:6d} rows x {len(tab.fields):3d} cols")
    return index


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", help="KDB file or folder containing *.KDB files")
    ap.add_argument("-o", "--output", default=None,
                    help="output folder (default: <source>/exports)")
    args = ap.parse_args()

    src = Path(args.source)
    files = [src] if src.is_file() else sorted(src.glob("*.KDB"))
    if not files:
        sys.exit(f"no *.KDB found under {src}")
    out_root = (Path(args.output) if args.output
                else (src if src.is_dir() else src.parent) / "exports")
    out_root.mkdir(parents=True, exist_ok=True)

    index = []
    for f in files:
        print(f"== {f.name} ==")
        index += export_file(f, out_root)

    with open(out_root / "index.csv", "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=["file", "table", "rows", "columns", "csv"])
        writer.writeheader()
        writer.writerows(index)
    total_rows = sum(e["rows"] for e in index)
    print(f"\n{len(index)} tables / {total_rows} rows -> {out_root}")


if __name__ == "__main__":
    main()
