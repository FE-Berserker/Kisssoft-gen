"""KISSsoft COM 探针：加载 Z90 官方算例并求解，dump 全部输出变量。

用途：vbelt-z90 对齐任务的基准采集（「与 KISSsoft 完全一致」的靶值）。
COM 形态见 KISSsoft-TUT-91：``Dispatch('KISSsoftCOM.KISSsoft')`` →
``GetModule('Z090')`` → ``LoadFile`` → ``SetVar``（字符串）→ ``Calculate``
→ ``GetVar``（字符串）。变量名来自手册 §65.16 与报告模板
``rpt\\Z090*.RPT``；不存在的变量按 try/except 逐个探测。

用法：

    uv run python tools/kisssoft_com_probe.py [算例路径] [输出 json]

注意：COM 会另起 ``KISSsoftCOM2026.exe`` 占一个 license 席位。
"""

from __future__ import annotations

import json
import sys

#: 输出变量探测清单（几何 / 承载 / 运动学 / 受力 / 双预紧链 / 带型参数）
VARS = [
    # 几何
    "z090k.i", "z090k.a", "belt.Lange", "sheave[0].umschl", "sheave[1].umschl",
    "z090k.ScheibenBreite", "z090k.n2", "z090k.n3",
    # 承载
    "z090k.Pmax", "z090k.powerNR", "z090k.powerAdd", "z090k.factorAngle",
    "z090k.factorLength", "z090k.factorINCR", "belt.nth", "belt.neff",
    "z090k.Sich",
    # 运动学
    "z090k.v", "belt.hz", "z090k.sch",
    # 受力
    "z090k.T1", "z090k.T2", "belt.fcirc", "belt.fcent",
    # 预紧——目录法（检验力 / 压深 → Trummkraft → 轴载）
    "z090k.Fdefkat", "z090k.defkat", "z090k.TrF", "z090k.LeerTrF",
    "z090k.LastTrF", "belt.vKritLeer", "belt.vKritLast", "belt.beltSpann",
    "sheave[0].AxKftBet", "sheave[0].AxKftSt", "sheave[1].AxKftBet",
    "sheave[1].AxKftSt",
    # 预紧——Niemann 最小值链
    "z090k.TrFmin", "z090k.LeerTrFmin", "z090k.LastTrFmin",
    "z090k.vKritLeermin", "z090k.vKritLastmin", "z090k.beltSpannmin",
    "z090k.AxKftBetmin1", "z090k.AxKftStmin1",
    # 带型固有参数（KDB）
    "belt.elast", "belt.massPerM", "belt.vmax", "belt.my", "z090k.DinName",
]


def main() -> None:
    case = sys.argv[1] if len(sys.argv) > 1 else (
        r"C:\KISSsoft 2026\example\01 V Belt.Z90")
    out_path = sys.argv[2] if len(sys.argv) > 2 else "tmp/z90_probe.json"

    import win32com.client

    ksoft = win32com.client.Dispatch("KISSsoftCOM.KISSsoft")
    ksoft.GetModule("Z090", True)
    ksoft.LoadFile(case)
    ksoft.Calculate()

    result: dict[str, str] = {"__case__": case}
    for var in VARS:
        try:
            result[var] = str(ksoft.GetVar(var))
        except Exception as exc:  # noqa: BLE001
            result[var] = f"<ERR {exc}>"

    ksoft.ReleaseModule()
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
    for key, val in result.items():
        print(f"{key:28s} = {val}")


if __name__ == "__main__":
    main()
