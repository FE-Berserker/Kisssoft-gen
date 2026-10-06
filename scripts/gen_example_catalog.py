"""KISSsoft 2026 官方算例目录（example/）全量清单生成器。

遍历安装目录（只读文件系统，不碰 COM、不占 license 席位），按模块扩展名
归组全部计算案例，生成 ``references/example-catalog.md``（模块总表 + 逐案
清单），供后续 agent / 用户选案调用：每案的调用即 COM ``LoadFile`` 绝对
路径（Z09A 族只认安装目录内路径，见 SKILL.md 配方）。

模块的 pyffalo 对应 / 收割器 / 镜像是**编辑决定**（同 tools/gen_deps_appendix.py
CHANNELS 的口径）：仓内 scripts/ 与 pyffalo examples/kisssoft/ 变动后手工
同步本表 META，重跑再生（幂等：无时间戳，同目录同产出）。

用法：
    python scripts/gen_example_catalog.py [example根目录]   # 缺省 C:/KISSsoft 2026/example
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

DEFAULT_EXAMPLE = Path(r"C:/KISSsoft 2026/example")
OUT = Path(__file__).resolve().parents[1] / "references" / "example-catalog.md"

#: KISSsys 系统级文件（.S20 系统模型 / .kpro 工程模板）——归系统组不入模块表
SYSTEM_EXTS = {"S20", "KPRO"}

#: 算例附件（几何 / 数据 / UI / 脚本支撑），计数不入逐案清单
SUPPORT_EXTS = {"STEP", "CSV", "TXT", "DXF", "PCH", "DUI", "SKRIPT"}

#: 模块元数据（编辑决定）：内容 / pyffalo 对应 / 收割器（本仓 scripts/）/
#: 镜像（pyffalo examples/kisssoft/ 子目录）/ 备注
META: dict[str, dict[str, str]] = {
    "Z11": {"name": "圆柱齿轮几何（含 Topping / 实测偏差 / 脚本变体）",
            "pyffalo": "SingleGear、GearPair 已覆盖",
            "harvester": "—", "mirror": "—"},
    "Z12": {"name": "圆柱齿轮承载（ISO 6336 / DIN 3990 / AGMA / API，含修形变体）",
            "pyffalo": "GearPair 已覆盖", "harvester": "—", "mirror": "—"},
    "Z13": {"name": "齿条副", "pyffalo": "未移植（小众按需）",
            "harvester": "—", "mirror": "—"},
    "Z14": {"name": "行星轮系（含失准变体）",
            "pyffalo": "PlanetaryGear、PlanetaryGearRatio 已覆盖",
            "harvester": "—", "mirror": "—"},
    "Z15": {"name": "三齿轮轮系（DIN 3990）",
            "pyffalo": "PlanetaryGearRatio 已覆盖", "harvester": "—", "mirror": "—"},
    "Z16": {"name": "四齿轮 / 多功率分流",
            "pyffalo": "PlanetaryGearRatio 已覆盖", "harvester": "—", "mirror": "—"},
    "Z17": {"name": "交错轴斜齿轮（Niemann）",
            "pyffalo": "未移植（小众按需）", "harvester": "—", "mirror": "—"},
    "Z40": {"name": "扇形 / 非圆齿轮",
            "pyffalo": "未移植（小众按需）", "harvester": "—", "mirror": "—"},
    "Z50": {"name": "beveloid 齿轮（冠状修形）",
            "pyffalo": "未移植（小众按需）", "harvester": "—", "mirror": "—"},
    "Z60": {"name": "面齿轮", "pyffalo": "未移植（小众按需）",
            "harvester": "—", "mirror": "—"},
    "Z70": {"name": "锥齿轮 / 准双曲面（ISO 10300 / DIN 3991 / AGMA / Klingelnberg）",
            "pyffalo": "BevelGearPair、HypoidGearPair 已移植",
            "harvester": "gen_bevel_gear_kisssoft.py、gen_hypoid_gear_kisssoft.py",
            "mirror": "z070_bevel、z070_hypoid"},
    "Z80": {"name": "蜗杆副（DIN 3996）",
            "pyffalo": "WormGear 已覆盖（不移植，可对账）",
            "harvester": "—", "mirror": "—"},
    "Z90": {"name": "V 带传动",
            "pyffalo": "VBeltDrive 已移植",
            "harvester": "gen_v_belt_kdb_kisssoft.py（探针族 kisssoft_com_probe/_scan/_catalog）",
            "mirror": "Z90"},
    "Z91": {"name": "同步带传动（四方法族）",
            "pyffalo": "SynchronousBeltDrive 已移植",
            "harvester": "harvest_kisssoft_z91.py",
            "mirror": "z091_02_toothed_belt、z091_03_toothed_belt_tension_pulley"},
    "Z92": {"name": "滚子链传动（DIN ISO 10823 / 606）",
            "pyffalo": "RollerChainDrive 已移植",
            "harvester": "gen_roller_chain_power_kisssoft.py、parse_kisssoft_kdb.py",
            "mirror": "Z92"},
    "Z9A": {"name": "花键（DIN 5480 / ISO 4156 / AGMA 6123 / DIN 5481·5482 齿廓库）",
            "pyffalo": "InvoluteSpline、SplineShaft、SplineAGMA 已对齐",
            "harvester": "—（对账期 tmp 探针；金样 pyffalo tests/golden/spline/）",
            "mirror": "—",
            "note": "55 案大头为 DIN5481_*/DIN5482_* 齿廓库批量案"},
    "M10": {"name": "圆柱过盈连接",
            "pyffalo": "InterferenceFit 已覆盖", "harvester": "—", "mirror": "M010"},
    "M1B": {"name": "圆锥过盈连接（Kollmann / DIN 7190-2）",
            "pyffalo": "ConicalInterferenceFit 已移植",
            "harvester": "gen_conical_fit_kisssoft.py", "mirror": "m1b_conical_fit"},
    "M1C": {"name": "剖分轮毂夹紧连接",
            "pyffalo": "ClampConnection 已移植",
            "harvester": "gen_clamp_connection_kisssoft.py", "mirror": "m01c_clamp"},
    "M2A": {"name": "平键 DIN 6892",
            "pyffalo": "KeyJoint 已移植",
            "harvester": "gen_key_joint_kisssoft.py", "mirror": "m02a_keys"},
    "M2B": {"name": "矩形花键 DIN ISO 14",
            "pyffalo": "SplineShaft 已覆盖", "harvester": "—", "mirror": "M02B"},
    "M2C": {"name": "花键强度（Niemann）",
            "pyffalo": "InvoluteSpline 族已对齐（金样 pyffalo tests/golden/spline/）",
            "harvester": "—", "mirror": "—"},
    "M2D": {"name": "多边形轴连接 DIN 32711/12",
            "pyffalo": "PolygonShaftJoint 已移植",
            "harvester": "gen_polygon_shaft_kisssoft.py", "mirror": "m02d_polygon"},
    "M2E": {"name": "半圆键 DIN 6888",
            "pyffalo": "WoodruffKeyJoint 已移植",
            "harvester": "gen_woodruff_key_kisssoft.py", "mirror": "m02e_woodruff"},
    "M3A": {"name": "销连接", "pyffalo": "未移植（小件按需）",
            "harvester": "—", "mirror": "—"},
    "M40": {"name": "螺栓 VDI 2230",
            "pyffalo": "Bolt、BoltJoint、FlangeBolt 已对齐",
            "harvester": "gen_bolt_m40_kisssoft.py、scan_bolt_m40_kisssoft.py",
            "mirror": "m40_bolt"},
    "M50": {"name": "挡圈（Seeger，轴用 / 孔用）",
            "pyffalo": "RetainingRing 已覆盖", "harvester": "—", "mirror": "M050"},
    "M60": {"name": "Hirth 端面齿盘（Voith 目录）",
            "pyffalo": "HirthCoupling 已移植",
            "harvester": "gen_hirth_coupling_kisssoft.py", "mirror": "m060_hirth"},
    "F10": {"name": "压簧（圆柱 + 圆锥）",
            "pyffalo": "HelicalCompressionSpring 已覆盖",
            "harvester": "—", "mirror": "F010"},
    "F20": {"name": "拉伸弹簧 DIN EN 13906-2",
            "pyffalo": "HelicalTensionSpring 已移植",
            "harvester": "gen_extension_spring_kisssoft.py", "mirror": "f020_tension_spring"},
    "F30": {"name": "腿弹簧 DIN EN 13906-3",
            "pyffalo": "LegSpring 已移植",
            "harvester": "gen_leg_spring_kisssoft.py", "mirror": "f030_leg_spring"},
    "F40": {"name": "碟形弹簧",
            "pyffalo": "DiscSpring 已覆盖", "harvester": "—", "mirror": "F040"},
    "F50": {"name": "扭杆弹簧 DIN 2091",
            "pyffalo": "TorsionBarSpring 已移植",
            "harvester": "gen_torsion_bar_kisssoft.py", "mirror": "f050_torsion_bar"},
    "W10": {"name": "轴（DIN 743 / FKM 强度、Campbell / 临界转速）",
            "pyffalo": "ShaftStrength、ShaftBeam 已移植",
            "harvester": "harvest_kisssoft_w10.py", "mirror": "w10_shafts"},
    "W50": {"name": "深沟球轴承（ISO 281 / TS 16281 寿命链）",
            "pyffalo": "寿命链并入 DeepGrooveBallBearing",
            "harvester": "gen_kisssoft_w50.py", "mirror": "W050"},
    "W51": {"name": "圆柱滚子轴承（内几何精算）",
            "pyffalo": "寿命链并入 CylindricalRollerBearing",
            "harvester": "gen_kisssoft_w50.py", "mirror": "W051"},
    "W70": {"name": "径向滑动轴承（ISO 7902 / DIN 31652·57）",
            "pyffalo": "PlainJournalBearing 已移植",
            "harvester": "gen_plain_journal_kisssoft.py", "mirror": "w070_plain_journal"},
    "W7C": {"name": "推力滑动轴承（ISO 12130 / DIN 31653·54）",
            "pyffalo": "PlainThrustBearing 已移植",
            "harvester": "gen_plain_thrust_kisssoft.py", "mirror": "w07c_plain_thrust"},
    "K10": {"name": "公差计算",
            "pyffalo": "ToleranceAnalysis 已覆盖", "harvester": "—", "mirror": "—"},
    "K12": {"name": "FKM 结构件应力分析",
            "pyffalo": "未移植（按需）", "harvester": "—", "mirror": "—"},
    "K14": {"name": "赫兹压力与任意接触（konf 0-9）",
            "pyffalo": "HertzContact 已移植（konf9 二期）",
            "harvester": "gen_hertz_k14_kisssoft.py", "mirror": "K014、k014_configs"},
    "K15": {"name": "塑料件管理", "pyffalo": "未移植（按需）",
            "harvester": "—", "mirror": "—"},
    "K17": {"name": "滚珠丝杠直线驱动", "pyffalo": "未移植（按需）",
            "harvester": "—", "mirror": "—"},
    "K19": {"name": "DFT 分析合成", "pyffalo": "SignalAnalysis 已覆盖（部分）",
            "harvester": "—", "mirror": "—"},
    "K25": {"name": "载荷谱生成", "pyffalo": "SignalAnalysis、RainflowCounting 已覆盖",
            "harvester": "—", "mirror": "—"},
    "A10": {"name": "齿轮同步器", "pyffalo": "未移植（按需）",
            "harvester": "—", "mirror": "—"},
    "A20": {"name": "联轴器", "pyffalo": "DiscCouplingEstimate 估算级（精算按需）",
            "harvester": "—", "mirror": "—"},
    "S20": {"name": "KISSsys 系统级齿轮箱（轴-轴承-箱体刚度耦合 / NVH / 效率）",
            "pyffalo": "不建议移植（与装配模式 + ANSYS + ROSS 路线重叠）",
            "harvester": "—", "mirror": "—",
            "note": ".S20 系统模型与 .kpro 工程模板成对"},
    "KPRO": {"name": "KISSsys 工程模板（与 .S20 系统模型配套）",
             "pyffalo": "不建议移植（同 S20）", "harvester": "—", "mirror": "—"},
}

_UNKNOWN = {"name": "（未登记模块——更新本脚本 META）", "pyffalo": "—",
            "harvester": "—", "mirror": "—"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("example", nargs="?", type=Path, default=DEFAULT_EXAMPLE,
                    help="KISSsoft example 目录（缺省 %(default)s）")
    args = ap.parse_args()
    root: Path = args.example
    if not root.is_dir():
        print(f"example 目录不存在：{root}")
        return 1

    cases: dict[str, list[str]] = defaultdict(list)
    support: dict[str, int] = defaultdict(int)
    n_total = 0
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        n_total += 1
        rel = p.relative_to(root).as_posix()
        ext = p.suffix.lstrip(".").upper()
        if ext in SUPPORT_EXTS:
            support[ext] += 1
        elif ext in SYSTEM_EXTS:
            cases[ext].append(rel)
        else:
            cases[ext].append(rel)  # 模块案例与 KISSsys 同容器，分组时再分

    def mod_key(code: str) -> tuple[int, str]:
        return (0, code) if code not in SYSTEM_EXTS else (1, code)

    lines: list[str] = []
    lines.append("# KISSsoft 2026 官方算例全量目录（example/ 遍历生成）")
    lines.append("")
    lines.append(f"> 源：`{root}`（{n_total} 个文件）。由 `scripts/gen_example_catalog.py` 只读遍历"
                 "生成（不碰 COM、不占 license 席位）；无 KISSsoft 的机器直接读本档。"
                 "再生：`python scripts/gen_example_catalog.py [example根]`。")
    lines.append(">")
    lines.append("> 逐案调用 = COM `LoadFile(\"<example根>/<文件名>\")` **绝对路径**"
                 "（Z09A 族只认安装目录内路径）；调用配方与机制坑见 SKILL.md 与"
                 " references/com-mechanics.md。")
    n_case = sum(len(v) for k, v in cases.items() if k not in SYSTEM_EXTS)
    n_sys = sum(len(v) for k, v in cases.items() if k in SYSTEM_EXTS)
    n_sup = sum(support.values())
    sup_desc = "、".join(f"{k}×{v}" for k, v in sorted(support.items()))
    n_mod = len([k for k in cases if k not in SYSTEM_EXTS])
    lines.append(f"> 统计：计算案例 {n_case}（{n_mod} 个模块）、"
                 f"KISSsys 系统档 {n_sys}"
                 f"（S20×{len(cases.get('S20', []))} + KPRO×{len(cases.get('KPRO', []))}）、"
                 f"附件 {n_sup}（{sup_desc}）。")
    lines.append("")
    lines.append("## 模块总表")
    lines.append("")
    lines.append("| 模块 | 内容 | 案例 | pyffalo 对应 | 收割器（scripts/）"
                 " | 镜像（examples/kisssoft/） |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for code in sorted(cases, key=mod_key):
        if code in SYSTEM_EXTS:
            continue
        m = META.get(code, _UNKNOWN)
        note = f"（{m['note']}）" if "note" in m else ""
        lines.append(f"| {code} | {m['name']}{note} | {len(cases[code])} | "
                     f"{m['pyffalo']} | {m['harvester']} | {m['mirror']} |")
    lines.append(f"| S20/KPRO | {META['S20']['name']} | {n_sys} | "
                 f"{META['S20']['pyffalo']} | — | — |")
    lines.append("")
    lines.append("## 逐案清单（模块 × 文件名排序）")
    lines.append("")
    for code in sorted(cases, key=mod_key):
        m = META.get(code, _UNKNOWN)
        note = f"（{m['note']}）" if "note" in m else ""
        lines.append(f"### {code} {m['name']}{note} —— {len(cases[code])} 案")
        lines.append("")
        lines.append(f"pyffalo：{m['pyffalo']}；收割器：{m['harvester']}；镜像：{m['mirror']}")
        lines.append("")
        for f in sorted(cases[code]):
            lines.append(f"- `{f}`")
        lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"模块 {len([k for k in cases if k not in SYSTEM_EXTS])} 个 / 计算案例 {n_case} 案 / "
          f"KISSsys {n_sys} / 附件 {n_sup} -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
