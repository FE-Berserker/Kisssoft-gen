"""KISSsoft COM 目录采集（文件副本法）：对 34 个带型改写算例副本的
``belt.Typ`` 行再 LoadFile（SetVar 改 Typ 不触发 KDB 重绑定，文件载入
才绑定），dump 每型 KDB 固有参数与查表量锚点。

用法：

    uv run python tools/kisssoft_com_catalog.py [输出 json]
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

CASE = Path(r"C:\KISSsoft 2026\example\01 V Belt.Z90")

VARS = [
    "z090k.DinName", "belt.elast", "belt.massPerM", "belt.vmax", "belt.my",
    "z090k.powerNR", "z090k.powerAdd", "z090k.factorAngle",
    "z090k.factorLength", "z090k.factorINCR", "z090k.ScheibenBreite",
]


def variant_file(typ: int) -> Path:
    """算例副本：belt.Typ=typ。

    原文件行结构为 ``内容¶\\r\\n``（U+00B6 段落符 + CRLF），splitlines
    会吞掉 ¶ 致 KISSsoft 解析失败——按含 ¶ 的整段文本替换，其余字节
    原样保留。
    """
    text = CASE.read_bytes().decode("utf-16")
    old = "belt.Typ=0¶"
    assert text.count(old) == 1, text.count(old)
    out = Path(tempfile.gettempdir()) / f"z90_typ{typ}.Z90"
    out.write_bytes(text.replace(old, f"belt.Typ={typ}¶").encode("utf-16"))
    return out


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else "tmp/z90_catalog.json"

    import win32com.client

    ksoft = win32com.client.Dispatch("KISSsoftCOM.KISSsoft")
    try:
        ksoft.SetSilentMode(True)
    except Exception:  # noqa: BLE001
        pass
    ksoft.GetModule("Z090", True)

    catalog = {}
    for typ in range(34):
        entry: dict[str, str] = {}
        try:
            ksoft.LoadFile(str(variant_file(typ)))
            ksoft.Calculate()
            for var in VARS:
                try:
                    entry[var] = str(ksoft.GetVar(var))
                except Exception as exc:  # noqa: BLE001
                    entry[var] = f"<ERR {exc}>"
        except Exception as exc:  # noqa: BLE001
            entry["__load__"] = f"<ERR {exc}>"
        catalog[str(typ)] = entry
        name = entry.get("z090k.DinName", "?")
        p0 = entry.get("z090k.powerNR", "?")
        print(f"Typ {typ:2d}: {name}  P0={p0}")
    ksoft.ReleaseModule()

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(catalog, fh, ensure_ascii=False, indent=1)
    print(f"saved -> {out_path}")


if __name__ == "__main__":
    main()
