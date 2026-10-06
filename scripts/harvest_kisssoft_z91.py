"""从本机 KISSsoft 2026 安装收割 Z091 同步带带型数据 → ``tools/data/belt_sync_source.json.gz``。

两个来源拼合（互相独立、入库前互证）：

- ``kdb/Z000.KDB`` 的 ``Z091NORM`` 表（29 行带型标量）：字符串块
  （每行 9 个 UTF-16LE 串：MODUL/CREATE_BY + 5 个空时间戳 + NAME + FLINK）
  与数值块（每行 9 个 double，记录步长 124 B）分离存储；数值块用 AT10
  锚点序列 ``(10, 30, 0, 0.0058)`` 定位后按步长回退对齐。
- ``dat/Z091-*.DAT``（29 个带型的插值表，纯文本）：``:TABLE LIST`` /
  ``:TABLE FUNCTION``（``INPUT X/Y ... TREAT LINEAR|NEXT_BIGGER|LOG``，
  ``*`` 为非法格 → null）。

CALCMETHOD（1=RPP / 2=GT / 3=AT / 4=PG）不在 Z091NORM 数值块里：以
2026-09-30 COM 收割的 22 个带型 ``z091k.calcMethode`` 为锚（本文件
``_COM_ANCHORS``），其余 7 个按族判定并由 DAT 表结构断言（方法 3 有
ATFUspez 无 powerNR；方法 2 有 powerAdd）。

COM 收割口径备注：``belt.elast`` 是按实际带宽换算值 = KDB 原值 ×
beff/bnom（PG5 实测 3333.33 = 1500 × 20/9）；本脚本存 KDB 原值，组件
侧按需换算。预紧口径 TESTMETHOD/TESTFACTOR 语义见 KISSsoft 手册第 52
章（1/2/3/4 四种预紧式 + 因子；首版组件不消费，仅为数据完备入库）。

用法（仅装有 KISSsoft 的机器可跑；产物快照随仓库入库）::

    python tools/harvest_kisssoft_z91.py [KISSsoft安装目录]

默认 ``C:/KISSsoft 2026``；输出 ``tools/data/belt_sync_source.json.gz``
（幂等重写），``gen_belt_sync_seeds.py`` 消费。
"""

from __future__ import annotations

import gzip
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KISS = Path("C:/KISSsoft 2026")
OUT = ROOT / "tools" / "data" / "belt_sync_source.json.gz"

#: 短代号（稳定入库键）← FLINK 文件名。顺序即快照行序（= KDB 字符串块序）。
_CODE_BY_FILE: dict[str, str] = {
    "Z091-001.DAT": "RPP-XL", "Z091-002.DAT": "RPP-L", "Z091-003.DAT": "RPP-H",
    "Z091-004.DAT": "RPP8", "Z091-005.DAT": "RPP14",
    "Z091-006.DAT": "RPP8HPR", "Z091-007.DAT": "RPP14HPR",
    "Z091-008.DAT": "PG3", "Z091-009.DAT": "PG5", "Z091-010.DAT": "PG8",
    "Z091-011.DAT": "PG14",
    "Z091-012.DAT": "GT8", "Z091-013.DAT": "GT14",  # COM DinName 标注不再供货
    "Z091-014.DAT": "AT5", "Z091-014a.DAT": "AT5G3",
    "Z091-015.DAT": "AT10", "Z091-015a.DAT": "AT10G3",
    "Z091-016.DAT": "AT20",
    "Z091-017.DAT": "RPP8PAN",
    "Z091-018.DAT": "GT2-8", "Z091-019.DAT": "GT2-14",
    "Z091-020.DAT": "AT3", "Z091-020a.DAT": "AT3G3",
    "Z091-021.DAT": "RPP8GOLD", "Z091-022.DAT": "RPP14GOLD",
    "Z091-023.DAT": "RPP8SILVER", "Z091-024.DAT": "RPP14SILVER",
    "Z091-025.DAT": "GTC8", "Z091-026.DAT": "GTC14",
}

#: 2026-09-30 COM 收割锚（DinName → (calcMethode, Teilung, Vmax, elast×beff/bnom,
#: massPerM, bnom)）；elast 项按 beff=20 的算例文件换算回 KDB 原值 = com×bnom/20。
_COM_ANCHORS: dict[str, tuple[int, float, float, float, float, float]] = {
    "XL-ISORAN-RPP-(FENNER)": (1, 5.08, 30, 1450, 0.0027, 25.4),
    "L-ISORAN-RPP-(FENNER)": (1, 9.525, 30, 2350, 0.0038, 25.4),
    "H-ISORAN-RPP-(FENNER)": (1, 12.7, 30, 6700, 0.0053, 25.4),
    "8mm-ISORAN-RPP-(FENNER)": (1, 8, 30, 7300, 0.0064, 25.4),
    "14mm-ISORAN-RPP-(FENNER)": (1, 14, 30, 10300, 0.0033, 25.4),
    "RP8mm-Pirelli-RPP-HPR": (1, 8, 30, 7000, 0.0064, 20),
    "RP14mm-Pirelli-RPP-HPR": (1, 14, 30, 10000, 0.0099, 40),
    "PG3mm-Power-Grip-HTD": (4, 3, 30, 600, 0.0015, 6),
    "PG5mm-Power-Grip-HTD": (4, 5, 30, 1500, 0.003, 9),
    "PG8mm-Power-Grip-HTD": (4, 8, 30, 7000, 0.006, 20),
    "PG14mm-Power-Grip-HTD": (4, 14, 30, 10000, 0.01, 40),
    "GT8mm-Poly-Chain-GT": (2, 8, 30, 7000, 0.0046, 62),
    "GT14mm-Poly-Chain-GT": (2, 14, 30, 10000, 0.0079, 125),
    "AT5mm-BRECOflex": (3, 5, 30, 0, 0.0033, 12),
    "AT5 GEN III-SYNCHROFLEX": (3, 5, 30, 0, 0.0036, 12),
    "AT10mm-BRECOflex": (3, 10, 30, 0, 0.0058, 12),
    "AT10 GEN III-SYNCHROFLEX": (3, 10, 30, 0, 0.0073, 12),
    "AT20mm-BRECOflex": (3, 20, 30, 0, 0.0096, 12),
    "8mm-DAYCO-RPP-(Panther)": (1, 8, 30, 0, 0.005, 20),
    "8mm-ISORAN-RPP-GOLD (Megadyne)": (1, 8, 30, 0, 0.0055, 20),
    "14mm-ISORAN-RPP-GOLD (Megadyne)": (1, 14, 30, 0, 0.0101, 40),
    "8mm-ISORAN-RPP-SILVER (Megadyne)": (1, 8, 30, 0, 0.0057, 20),
}

#: 计算方法按 code（COM 收割 22 型 + 其余 7 型按族判定，DAT 结构断言兜底）。
_METHOD_BY_CODE: dict[str, int] = {
    "RPP-XL": 1, "RPP-L": 1, "RPP-H": 1, "RPP8": 1, "RPP14": 1,
    "RPP8HPR": 1, "RPP14HPR": 1,
    "PG3": 4, "PG5": 4, "PG8": 4, "PG14": 4,
    "GT8": 2, "GT14": 2,
    "AT5": 3, "AT5G3": 3, "AT10": 3, "AT10G3": 3, "AT20": 3,
    "RPP8PAN": 1, "RPP8GOLD": 1, "RPP14GOLD": 1, "RPP8SILVER": 1,
    "RPP14SILVER": 1, "GTC8": 2, "GTC14": 2,
    "GT2-8": 2, "GT2-14": 2, "AT3": 3, "AT3G3": 3,
}

_STRIDE = 124  # Z091NORM 数值块每记录字节数（72 B double + 52 B 指针/整数）
_REAL_FIELDS = ("pitch", "vmax", "elast", "mass_per_m", "fs", "bnom",
                "test_method", "test_factor", "dehnung")
_AT10_ANCHOR = (10.0, 30.0, 0.0, 0.0058)


def parse_kdb_z091norm(kdb: Path) -> list[dict]:
    """Z091NORM 29 行：字符串块（NAME/FLINK）+ 数值块（9 double/行）。"""
    data = kdb.read_bytes()
    marker = "Z091NORM".encode("utf-16-le")
    flink_re = re.compile(r"Z091-\d+[aA]?\.dat", re.IGNORECASE)

    def read_str(p: int) -> tuple[str, int]:
        out = bytearray()
        while data[p:p + 2] != b"\x00\x00":
            if p + 2 > len(data):
                raise ValueError("字符串区截断：EOF 前无 UTF-16 终止符")
            out += data[p:p + 2]
            p += 2
        return out.decode("utf-16-le"), p + 2

    records: list[dict] = []
    for m in re.finditer(re.escape(marker), data):
        pos, strs = m.start(), []
        try:
            for _ in range(9):
                s, pos = read_str(pos)
                strs.append(s)
        except (IndexError, UnicodeDecodeError, ValueError):
            continue
        if flink_re.fullmatch(strs[-1]):
            records.append({"name": strs[-2], "flink": strs[-1], "mod_off": m.start()})
    assert len(records) == 29, f"Z091NORM 字符串块应 29 行，实得 {len(records)}"

    at10 = b"".join(struct.pack("<d", v) for v in _AT10_ANCHOR)
    anchor = data.find(at10)
    assert anchor > 0, "AT10 锚点序列未命中（KDB 布局漂移？）"
    idx = next(i for i, r in enumerate(records) if r["flink"] == "Z091-015.DAT")
    base = anchor - idx * _STRIDE
    for i, r in enumerate(records):
        vals = struct.unpack("<9d", data[base + i * _STRIDE:base + i * _STRIDE + 72])
        for key, v in zip(_REAL_FIELDS, vals, strict=True):
            r[key] = v
        assert 0 < r["pitch"] < 30 and r["vmax"] > 0 and r["bnom"] > 0, r
    return records


def parse_dat(path: Path) -> dict[str, dict]:
    """单带型 .DAT 的全部表块 → {表名: 结构化 dict}。"""
    text = path.read_bytes().decode("cp1252")
    tables: dict[str, dict] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith(":TABLE"):
            kind, name = line.split(None, 2)[1:3]
            i += 1
            inputs: list[tuple[str, str]] = []
            while not lines[i].strip().startswith("DATA"):
                m = re.match(r"INPUT\s+([XY])\s+\S+\s+TREAT\s+(\w+)", lines[i].strip())
                if m:
                    inputs.append((m.group(1), m.group(2)))
                i += 1
            rows: list[list[str]] = []
            i += 1
            while not lines[i].strip().startswith("END"):
                toks = lines[i].split()
                if toks:
                    rows.append(toks)
                i += 1
            tables[name.split(".")[-1]] = _block(kind, inputs, rows)
        i += 1
    assert tables, f"{path.name} 未解析出任何表块"
    return tables


def _num(tok: str) -> float | None:
    # 部分 DAT 文件（017/021-026，德文注释）用德式小数逗号
    return None if tok == "*" else float(tok.replace(",", "."))


def _block(kind: str, inputs: list[tuple[str, str]], rows: list[list[str]]) -> dict:
    if kind == "LIST":
        vals = [float(r[1].replace(",", ".")) for r in rows]
        while vals and vals[-1] == 0.0:  # 行尾 0 为列表终止符（非档位）
            vals.pop()
        return {"kind": "list", "values": vals}
    if len(inputs) == 1:
        assert len(rows) == 2, f"一维表应 2 行（轴+值），实得 {len(rows)}"
        return {"kind": "func1", "treat": inputs[0][1],
                "x": [_num(t) for t in rows[0]], "y": [_num(t) for t in rows[1]]}
    assert len(inputs) == 2, f"二维表 INPUT 行异常：{inputs}"
    z_rows = []
    for r in rows[1:]:
        cells = [_num(t) for t in r[1:]]
        # 原厂个别行少尾格（如 Z091-002 powerNR 的 6200/7000 行）：右补
        # null 按非法区处理，不造数；多格截断
        cells = cells[:len(rows[0])] + [None] * (len(rows[0]) - len(cells))
        z_rows.append(cells)
    return {"kind": "func2", "treat_x": inputs[0][1], "treat_y": inputs[1][1],
            "x": [_num(t) for t in rows[0]],
            "y": [float(r[0].replace(",", ".")) for r in rows[1:]],
            "z": z_rows}


def _check_method(code: str, method: int, tables: dict[str, dict]) -> None:
    """计算方法与 DAT 表结构互证（方法 3 周向力体系 / powerAdd 仅方法 2 可有）。"""
    has_at = "ATFUspez" in tables
    has_power = "powerNR" in tables
    has_add = "powerAdd" in tables
    if method == 3:
        assert has_at and not has_power, f"{code}: 方法 3 应有 ATFUspez 无 powerNR"
    else:
        assert has_power and not has_at, f"{code}: 方法 {method} 应有 powerNR 无 ATFUspez"
        # powerAdd 在方法 2 内可选（GTC/GT-Carbon 2008 目录无此表）
        assert not has_add or method == 2, f"{code}: powerAdd 只应出现在方法 2"


def harvest(kiss_dir: Path) -> dict:
    kdb_rows = parse_kdb_z091norm(kiss_dir / "kdb" / "Z000.KDB")
    profiles = []
    for r in kdb_rows:
        flink = r["flink"]
        code = _CODE_BY_FILE[flink]
        tables = parse_dat(kiss_dir / "dat" / flink)
        name = r["name"]
        method = _METHOD_BY_CODE[code]
        _check_method(code, method, tables)
        anchor = _COM_ANCHORS.get(name)
        if anchor is not None:
            a_m, a_p, a_v, a_e, a_q, a_b = anchor
            assert (a_m, a_p, a_v, a_q, a_b) == (
                method, round(r["pitch"], 6), round(r["vmax"], 6),
                round(r["mass_per_m"], 6), round(r["bnom"], 6),
            ), f"{code} 标量与 COM 锚点不符：{r}"
            assert abs(a_e - r["elast"]) <= 6e-4 * max(a_e, 1.0), f"{code} elast 不符"
        profiles.append({
            "code": code, "din_name": name, "file": flink,
            "discontinued": "不再供货" in name, "method": method,
            **{k: r[k] for k in _REAL_FIELDS},
            "tables": tables,
        })
    return {"meta": {
        "harvested": "2026-09-30",
        "source": f"{kiss_dir.name}: kdb/Z000.KDB Z091NORM + dat/Z091-*.DAT",
        "com_anchors": f"COM GetVar 收割 {len(_COM_ANCHORS)} 型（elast 为 KDB 原值口径）",
    }, "profiles": profiles}


def main(argv: list[str]) -> None:
    kiss = Path(argv[1]) if len(argv) > 1 else DEFAULT_KISS
    snap = harvest(kiss)
    payload = json.dumps(snap, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(gzip.compress(payload, mtime=0))
    n_pow = sum(1 for p in snap["profiles"] if "powerNR" in p["tables"])
    n_at = sum("ATFUspez" in p["tables"] for p in snap["profiles"])
    print(f"OK {OUT.relative_to(ROOT)}: {len(snap['profiles'])} 型"
          f"（功率表法 {n_pow} / AT 周向力法 {n_at}），"
          f"{len(payload) / 1024:.0f} KiB(gzip 前)")


if __name__ == "__main__":
    main(sys.argv)
