"""KISSsoft K014 通用赫兹接触金样收割（COM GetVar 逐变量）。

对官方算例 04 与 13 个文件变体案（konf 1-8 全构型 + α 30°/90° + 钢×铝
异材料 + 铝接触对）经 KISSsoftCOM 计算并收割全量变量，写
``tests/golden/hertz/kisssoft_k14.json`` 供 ``tests/unit/test_kisssoft_k14_golden.py``
对账。

``--scan`` 模式：线接触趋近量 δ 的 R/leff/F 三维扫描（Norden 柱-面 /
Weber-Banaschek 柱-柱两式常数反推证据，21 案）→
``tools/data/hertz_k14/norden_scan.json``（常数已收口进
``components/methods/_hertz.py``，扫描快照仅存证）。

COM 形态（W070 收割器同款）：``SetSilentMode(True)`` + ``GetModule("K014",
True)`` + 文件变体（UTF-16 明文 ``key=value¶`` 行替换）+ ``LoadFile`` +
``CalculateRetVal()`` 唯一可信判据 + ``GetVar`` + ``ReleaseModule``。

K014 特有口径（2026-10-02 调研钉死，docs/specs/k14-hertz.md）：

- **SetVar 陈旧值陷阱**：``konf`` 扫描 4+ 档 Calculate 后回吐旧值——
  一律文件变体（本收割器全部走变体）；
- **alpha 文件值 = 角度(°)×57.29578**（双重度→弧度换算怪癖：写 30 需
  落盘 1718.8734，GetVar 读回 0.5236 rad；α=90° 结果与交换体 1 两直径
  逐位一致——机制互证）；
- **pH 负号 = 压缩约定**（|pH| 为峰值）；kraft konf0-8 = 总力 [N]；
- **材料自填**走 ``DBID=19999``（Eigene Eingabe 哨兵）+ ``mat.E/ny``
  两键直改；
- **ft（Rz 粗糙度）为幽灵变量**：文件变体 0~50 全档输出逐位不变
  （文档/UI/KVAR 三处无此输入）——收割仅回显、不消费。

用法::

    python tools/gen_hertz_k14_kisssoft.py            # 金样收割
    python tools/gen_hertz_k14_kisssoft.py --scan     # δ 扫描存证
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GOLDEN = REPO / "tests/golden/hertz/kisssoft_k14.json"
SCAN_OUT = REPO / "tools/data/hertz_k14/norden_scan.json"
KISS_EXAMPLE = Path("C:/KISSsoft 2026/example/04 Hertzian Pressure.K14")
VARIANT_DIR = REPO / "tmp/k14_golden_cases"

#: 收割变量——输入回显（含 ft 幽灵变量与轮廓路径空串）
_INPUT_VARS = ("k14.konf", "k14.kraft", "k14.leff", "k14.D1", "k14.D2",
               "k14.D3", "k14.D4", "k14.alpha", "k14.ft",
               "k14a.mat.E", "k14a.mat.ny", "k14b.mat.E", "k14b.mat.ny")
#: 收割变量——结果（a=长半轴[mm]、b=短半轴/半宽[mm]、del[mm]、pm/pH
#: [N/mm²]、tauhmax1/2 + 深度；平面槽位读回 DBL_MAX 属正常）
_RESULT_VARS = ("k14.a", "k14.b", "k14.del", "k14.pm", "k14.pH",
                "k14.tauhmax1", "k14.ztauhmax1",
                "k14.tauhmax2", "k14.ztauhmax2")

_ALU_A = {"k14a.mat.DBID": 19999, "k14a.mat.bez": "Eigene Eingabe",
          "k14a.mat.E": 70000, "k14a.mat.ny": 0.34}
_ALU_B = {"k14b.mat.DBID": 19999, "k14b.mat.bez": "Eigene Eingabe",
          "k14b.mat.E": 70000, "k14b.mat.ny": 0.34}

#: 金样案（官方 04 原文件 + 文件变体）；alpha 落盘值 = 度数×57.29578
CASES: dict[str, dict | None] = {
    "konf0_ball_ball": None,  # 官方算例 04 原文件（konf=0 D25×D50 F=100）
    "konf1_ball_cyl": {"k14.konf": 1, "k14.D1": 25, "k14.D2": 50,
                       "k14.leff": 10, "k14.kraft": 1000},
    "konf2_ball_ellipsoid": {"k14.konf": 2, "k14.D1": 25, "k14.D2": 50,
                             "k14.D4": 200, "k14.kraft": 100},
    "konf3_ball_plane": {"k14.konf": 3, "k14.D1": 25, "k14.kraft": 100},
    "konf4_alpha0": {"k14.konf": 4, "k14.D1": 25, "k14.D3": 200,
                     "k14.D2": 50, "k14.D4": 100, "k14.alpha": 0,
                     "k14.kraft": 100},
    "konf4_alpha30": {"k14.konf": 4, "k14.D1": 25, "k14.D3": 200,
                      "k14.D2": 50, "k14.D4": 100,
                      "k14.alpha": round(30 * 57.29577951308232, 6),
                      "k14.kraft": 100},
    "konf4_alpha90": {"k14.konf": 4, "k14.D1": 25, "k14.D3": 200,
                      "k14.D2": 50, "k14.D4": 100,
                      "k14.alpha": round(90 * 57.29577951308232, 6),
                      "k14.kraft": 100},
    "konf5_ellipsoid_cyl": {"k14.konf": 5, "k14.D1": 25, "k14.D3": 200,
                            "k14.D2": 50, "k14.leff": 10,
                            "k14.kraft": 1000},
    "konf6_ellipsoid_plane": {"k14.konf": 6, "k14.D1": 25, "k14.D3": 200,
                              "k14.kraft": 100},
    "konf7_cyl_cyl": {"k14.konf": 7, "k14.D1": 25, "k14.D2": 50,
                      "k14.leff": 10, "k14.kraft": 1000},
    "konf8_cyl_plane": {"k14.konf": 8, "k14.D1": 25, "k14.leff": 10,
                        "k14.kraft": 1000},
    "mat_diff_steel_alu": {"k14.konf": 0, "k14.D1": 25, "k14.D2": 50,
                           "k14.kraft": 100, **_ALU_B},
    "mat_alu_cyl_cyl": {"k14.konf": 7, "k14.D1": 25, "k14.D2": 50,
                        "k14.leff": 10, "k14.kraft": 1000,
                        **_ALU_A, **_ALU_B},
    "mat_alu_cyl_plane": {"k14.konf": 8, "k14.D1": 25, "k14.leff": 10,
                          "k14.kraft": 1000, **_ALU_A, **_ALU_B},
}

#: δ 扫描矩阵（Norden/Weber 常数反推证据；leff 恒 10）
SCAN_JOBS: dict[str, dict] = {
    **{f"k7_F{f}": {"k14.konf": 7, "k14.D1": 25, "k14.D2": 50,
                    "k14.leff": 10, "k14.kraft": f}
       for f in (250, 500, 1000, 2000, 4000)},
    **{f"k7_D2_{d}": {"k14.konf": 7, "k14.D1": 25, "k14.D2": d,
                      "k14.leff": 10, "k14.kraft": 1000}
       for d in (50, 100, 200, 400)},
    **{f"k7_D1_{d}": {"k14.konf": 7, "k14.D1": d, "k14.D2": 50,
                      "k14.leff": 10, "k14.kraft": 1000}
       for d in (50, 100, 200)},
    **{f"k7_L{L}": {"k14.konf": 7, "k14.D1": 25, "k14.D2": 50,
                    "k14.leff": L, "k14.kraft": 1000}
       for L in (5, 20, 40)},
    **{f"k8_F{f}": {"k14.konf": 8, "k14.D1": 25, "k14.leff": 10,
                    "k14.kraft": f}
       for f in (500, 1000, 2000)},
    **{f"k8_D1_{d}": {"k14.konf": 8, "k14.D1": d, "k14.leff": 10,
                      "k14.kraft": 1000}
       for d in (50, 100, 200)},
}


def _getvar(ksoft, name: str):
    """GetVar → float | str | None（缺失/空记 None；非数值串原样保留）。"""
    try:
        raw = ksoft.GetVar(name)
    except Exception:  # noqa: BLE001 — 变量不存在时 COM 层可能抛错
        return None
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return str(raw)


def _write_variant(name: str, overrides: dict) -> Path:
    """官方 04 文件变体（UTF-16 ``key=value¶`` 行替换）→ tmp 副本。"""
    if not KISS_EXAMPLE.exists():
        raise SystemExit(f"未找到 KISSsoft 算例：{KISS_EXAMPLE}")
    text = KISS_EXAMPLE.read_text("utf-16")
    for key, val in overrides.items():
        # [^¶\r\n]*：不跨行——目标行缺 ¶ 终止符时宁可替换失败也不吞行
        text, n = re.subn(rf"^{re.escape(key)}=[^¶\r\n]*¶",
                          f"{key}={val}¶", text, flags=re.MULTILINE)
        if n != 1:
            raise SystemExit(f"[{name}] 变体键 {key} 替换 {n} 处（应为 1）")
    VARIANT_DIR.mkdir(parents=True, exist_ok=True)
    out = VARIANT_DIR / f"{name}.K14"
    out.write_text(text, "utf-16")
    return out


def _collect(ksoft, path: Path, name: str, *, out_name: str) -> dict:
    """LoadFile + CalculateRetVal + 全变量收割（坏输入 SystemExit 保产物）。

    结果变量缺一即判废（_getvar 把 COM 错误塌缩成 None——变量改名 /
    读失败不允许以 null 混进金样，错误应在收割端暴露）。
    """
    ksoft.LoadFile(str(path))
    if not ksoft.CalculateRetVal():
        raise SystemExit(
            f"[{name}] 计算失败（CalculateRetVal=False）——"
            f"{out_name} 保持原样，修复后重跑")
    record = {
        "file": path.name,
        "input": {v: _getvar(ksoft, v) for v in _INPUT_VARS},
        "expect": {v: _getvar(ksoft, v) for v in _RESULT_VARS},
    }
    e = record["expect"]
    missing = [v for v in _RESULT_VARS if e.get(v) is None]
    if missing:
        raise SystemExit(f"[{name}] 结果变量缺失 {missing}（变量改名/读失败？），"
                         f"{out_name} 保持原样")
    ph, bb = e.get("k14.pH"), e.get("k14.b")
    if not isinstance(ph, float) or not isinstance(bb, float):
        raise SystemExit(f"[{name}] pH/b 非数值（{ph!r}/{bb!r}），判废")
    if ph >= 0 or bb <= 0:
        raise SystemExit(
            f"[{name}] pH={ph}（应<0=压缩号）/ b={bb}（应>0），判废")
    return record


def harvest() -> int:
    import win32com.client as client

    cases: dict[str, dict] = {}
    ksoft = client.Dispatch("KISSsoftCOM.KISSsoft")
    try:
        ksoft.SetSilentMode(True)
        ksoft.GetModule("K014", True)
        for name, overrides in CASES.items():
            path = (KISS_EXAMPLE if overrides is None
                    else _write_variant(name, overrides))
            record = _collect(ksoft, path, name, out_name=GOLDEN.name)
            cases[name] = record
            e = record["expect"]
            print(f"[{name}] a={e.get('k14.a')} b={e.get('k14.b')} "
                  f"del={e.get('k14.del')} pH={e.get('k14.pH')} "
                  f"tau1={e.get('k14.tauhmax1')}@{e.get('k14.ztauhmax1')}",
                  flush=True)
    finally:
        try:
            ksoft.ReleaseModule()
        except Exception:  # noqa: BLE001, S110
            pass

    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(
        json.dumps({
            "source": ("KISSsoft 2026 K014 COM GetVar 逐变量收割"
                       "（2026-10-02；官方算例 04 原文件 + 文件变体案；"
                       "收割器 tools/gen_hertz_k14_kisssoft.py 幂等重跑）"),
            "note": ("单位口径：几何 mm、kraft=N（konf0-8 总力）、del=mm、"
                     "pm/pH=N/mm²（pH 负号=压缩约定，对账取 |pH|）、"
                     "alpha 读回 rad（文件落盘 = 度数×57.29578）；平面槽位 "
                     "D 读回 DBL_MAX 属正常；ft 为幽灵变量仅回显不消费；"
                     "konf=9 任意接触二期不收割"),
            "cases": cases,
        }, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"{len(cases)} 案 → {GOLDEN}")
    return 0


def scan() -> int:
    """线接触 δ 扫描（Norden/Weber 常数反推证据快照，21 案）。"""
    import win32com.client as client

    cases: dict[str, dict] = {}
    ksoft = client.Dispatch("KISSsoftCOM.KISSsoft")
    try:
        ksoft.SetSilentMode(True)
        ksoft.GetModule("K014", True)
        for name, overrides in SCAN_JOBS.items():
            path = _write_variant(name, overrides)
            record = _collect(ksoft, path, name, out_name=SCAN_OUT.name)
            cases[name] = {
                "input": record["input"],
                "expect": record["expect"],
            }
            print(f"[{name}] b={record['expect'].get('k14.b')} "
                  f"del={record['expect'].get('k14.del')}", flush=True)
    finally:
        try:
            ksoft.ReleaseModule()
        except Exception:  # noqa: BLE001, S110
            pass

    SCAN_OUT.parent.mkdir(parents=True, exist_ok=True)
    SCAN_OUT.write_text(
        json.dumps({
            "source": ("KISSsoft 2026 K014 线接触 δ 扫描（2026-10-02；"
                       "Norden 柱-面 c*=3.4955 材料不变量 / Weber-Banaschek "
                       "柱-柱 a(E*) 钢 0.4768 铝 0.4365 两点插值的反推证据）"),
            "cases": cases,
        }, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"{len(cases)} 案 → {SCAN_OUT}")
    return 0


def main(argv: list[str]) -> int:
    if "--scan" in argv:
        return scan()
    return harvest()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
