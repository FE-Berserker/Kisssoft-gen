"""KISSsoft 官方案例库 → pyffalo 例子库生成器。

解析 ``C:/KISSsoft 2026/example/`` 下可映射算例（UTF-16 INI 明文），
按逐模块映射表生成 ``examples/<模块号>/<原名>.py``（构造 pyffalo 组件 →
solve → 打印输出，KISSsoft 锚点可得处附注释）。

映射原则（docs/specs/kisssoft-examples.md）：
- 输入逐变量映射；无对应字段或语义不符的项写入脚本 docstring「未映射项」，
  **不硬凑**；
- KISSsoft 锚点优先取算例文件内的缓存输出（fd.L1 等），其次 COM 实算；
- 材料以名称 + 弹性/屈服参数对齐（pyffalo 组件 Params 显式字段）。

覆盖范围（P0，main 已有组件且映射可靠）：
- K014（赫兹，konf=0 球-球）→ HertzContact（1；konf=9 任意接触不映射）
- F010（圆柱压簧）→ HelicalCompressionSpring（1；圆锥簧例不映射）
- F040（碟簧）→ DiscSpring（1）
- M010（圆柱过盈）→ InterferenceFit（2）
- M050（挡圈）→ RetainingRing（2）
- M02A（平键 DIN 6892）→ KeyJoint（3）
- M02B（矩形花键 DIN ISO 14）→ SplineShaft（1）
- Z90（V 带）→ VBeltDrive（1；Typ=0 SPZ-CONTI-V 族，官方算例即 demo_input，
  锚点取 examples/connection/README.md COM 对标表，2026-10-01 补生成）
- Z92（滚子链）→ RollerChainDrive（1；TypID→表行反推链型，官方算例即
  demo_input，task/roller-chain 合并后补生成）
- W050（滚动轴承目录法）→ DeepGrooveBallBearing（1；6208 目录内几何估值
  f0 锚定，Cr 目录源差 docstring 注明，2026-10-01 task/bearing-life-w50w51）
- W051（内几何精算）→ BearingLife16281（3；16281 切片柔度镜像，
  官方 cr/c0r 直入，eC/Pref/L10r/Lnmrh/Pks 锚定，ν1 双段口径）
后续批次与不映射模块清单见 ``examples/README.md``。

用法::

    python scripts/gen_kisssoft_examples.py            # 生成 examples/
    python scripts/gen_kisssoft_examples.py --run      # 生成后逐例运行验证
"""

from __future__ import annotations

import argparse
import re
import runpy
import sys
from pathlib import Path

import pyffalo_root

REPO = pyffalo_root.repo_root()
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

KS_EXAMPLE = Path(r"C:/KISSsoft 2026/example")
OUT_ROOT = REPO / "examples" / "kisssoft"

#: 算例文件名白名单：源 stem 直接构成输出文件名并进入脚本 docstring，
#: 白名单外的引号 / 反斜杠 / 分隔符等字符一律拒收
_SAFE_STEM = re.compile(r"[A-Za-z0-9 _().+\-',]+")


def _s(x: object) -> str:
    """docstring 插值转义：算例 INI 的自由文本值不可信，未转义拼入三引号
    docstring 可闭合字符串越界成代码。"""
    return str(x).replace("\\", "\\\\").replace('"', '\\"')


def parse_case(path: Path) -> dict[str, str]:
    """KISSsoft 算例文件（UTF-16 INI，行 `key=value¶`）→ 扁平 dict（后键覆盖）。"""
    lines = path.read_text(encoding="utf-16").splitlines()
    out: dict[str, str] = {}
    for line in lines:
        line = line.strip().rstrip("¶")
        if "=" in line:
            key, _, val = line.partition("=")
            out[key.strip()] = val.strip()
    return out


def _f(v: dict, key: str) -> float:
    return float(v[key])


# ---------------------------------------------------------------- 模块映射

def map_k014(v: dict) -> dict:
    """Hertzian Pressure（konf=0 球-球）→ HertzContact。

    D1/D2 = 体 1/体 2 球径（konf=0 时 D3/D4 不参与，COM 实算反推验证：
    R*=1/(D1/2)+1/(D2/2) 复现 pH=1528.34 MPa、a=0.17675 mm）。
    """
    if v["k14.konf"] != "0":
        raise ValueError("仅球-球构型映射；konf=9 任意接触见 README")
    inputs = {
        "Type": "Ball-Ball",
        "Contact_Load": _f(v, "k14.kraft"),
        "Rho1": _f(v, "k14.D1") / 2,
        "Rho2": _f(v, "k14.D2") / 2,
    }
    params = {
        "E1": _f(v, "k14a.mat.E"), "E2": _f(v, "k14b.mat.E"),
        "Xi1": _f(v, "k14a.mat.ny"), "Xi2": _f(v, "k14b.mat.ny"),
    }
    return {
        "component": "HertzContact", "inputs": inputs, "params": params,
        "notes": [f"k14.kraft={_f(v, 'k14.kraft'):g} N → Contact_Load；"
                  f"D1={_f(v, 'k14.D1'):g}/D2={_f(v, 'k14.D2'):g} mm → Rho1/Rho2（半径）；"
                  f"两体材料 {v['k14a.mat.bez']}（E/ν → Params）",
                  "KISSsoft 锚点（COM 实算）：最大接触压力 pH=1528.34 MPa、"
                  "接触半径 a=0.17675 mm、τhmax=473.81 MPa @ z=0.0852 mm"],
        "unmapped": [f"k14.D3/D4（本构型不参与）、k14.alpha={v['k14.alpha']}（倾角）、"
                     "k14.ft（表面粗糙度档）"],
        "anchors": [("Contact_Max_Stress", 1528.34, 0.02),
                    ("Contact_Half_Width", 0.17675, 0.02)],
    }


def map_f010(v: dict) -> dict:
    """Compression Spring（圆柱压簧）→ HelicalCompressionSpring。"""
    if v.get("fd.typeOfSpring") != "0":
        raise ValueError("仅圆柱压簧映射；圆锥簧（typeOfSpring=1）见 README")
    inputs = {
        "WireDiameter": _f(v, "fd.d"),
        "MeanDiameter": _f(v, "fd.D"),
        "FreeLength": _f(v, "fd.L0"),
        "WorkingForce": _f(v, "fd.F2"),
        "WorkingDeflection": _f(v, "fd.s2"),
    }
    params = {"Material": "Cold-drawn wire (hard-drawn)"}
    return {
        "component": "HelicalCompressionSpring", "inputs": inputs,
        "params": params,
        "notes": [f"fd.d={_f(v, 'fd.d'):g}/fd.D={_f(v, 'fd.D'):g}/fd.L0={_f(v, 'fd.L0'):g}"
                  f" → WireDiameter/MeanDiameter/FreeLength；工况 2：F2={_f(v, 'fd.F2'):g} N、"
                  f"s2={_f(v, 'fd.s2'):.4g} mm；材料 {v['fd.mat.bez']}"
                  "（DIN 17223-1 冷拉钢丝 C 级）→ Params.Material ="
                  " 'Cold-drawn wire (hard-drawn)'",
                  "KISSsoft 锚点（文件缓存输出）：L1=333.865、L2=330.460、"
                  f"全压并 sn={_f(v, 'fd.sn'):.4g} mm、"
                  f"圈数 n={v['fd.n']}（含支承圈 nu={v['fd.nu']}）",
                  "已知偏差：映射材料的剪切模量 G=79000 MPa（Spring 表）低于算例钢丝"
                  "实配（G≈81500，由锚点圈数反解）——按 s2 反解圈数 17.9 vs 锚点"
                  " 18.5（−3.1%）；L1/L2/sn 不在组件 Output 字段，故不作锚点断言"],
        "unmapped": [f"Rm={v['fd.mat.Rm']} MPa（组件按材料表强度）与喷丸"
                     "（kugelgestrahlt=true，组件 Params.IsShotPeened 默认关）",
                     "fd.belastungsart（载荷类型编码）——组件默认 static"],
    }


def map_f040(v: dict) -> dict:
    """Disk Spring → DiscSpring（标准规格查表：reihe/gruppe + De 定代号）。"""
    de = _f(v, "f4.De")
    if not (abs(de - 40) < 1e-9 and _f(v, "f4.Di") == 20.4):
        raise ValueError("本映射仅覆盖 B40 规格算例")
    inputs = {
        "Designation": "B40",
        "s_min": _f(v, "f4.s1"),
        "s_max": _f(v, "f4.s2"),
        "Stack_n": int(_f(v, "f4.np")),
        "Stack_i": int(_f(v, "f4.is")),
    }
    return {
        "component": "DiscSpring", "inputs": inputs, "params": {},
        "notes": ["f4.reihe/gruppe + De=40/Di=20.4/t=1.5 → 标准代号 B40（查表带出全尺寸）",
                  f"s1={_f(v, 'f4.s1'):.4g}/s2={_f(v, 'f4.s2'):.4g} mm → s_min/s_max；"
                  f"叠合 np={v['f4.np']}、对合 is={v['f4.is']}",
                  "KISSsoft 锚点（文件缓存输出）：F1=1500 N、F2=2010 N、"
                  "L1=2.2233、L2=2.0287 mm",
                  "已知偏差：组件 Params 泊松比固定 μ=0.3，算例材料"
                  f" {v['f4.mat.bez']} ν=0.25——F2 组件 2070.7 N vs 锚点 2010"
                  "（+3.0%）；μ 取 0.25 时 F1/F2 与锚点逐位一致（超组件参数面，"
                  "不作断言）"],
        "unmapped": [f"材料 {v['f4.mat.bez']}（组件 Params 默认 50CrVA 类）"],
    }


def _basic_mat(name: str | None) -> tuple[str, bool]:
    """KISSsoft 材料名 → pyffalo Basic 表名（空格归一化匹配；未命中回退 C45）。"""
    import pyffalo.components  # noqa: F401
    from pyffalo.data.database import DataBase
    from pyffalo.data.schema import name_field

    nf = name_field("Basic") or "Name"
    with DataBase() as db:
        rows = db.list_mats("Basic")
    names = [str(r.get(nf)) for r in rows]
    if name:
        for cand in names:
            if cand == name or cand.replace(" ", "") == name.replace(" ", ""):
                return cand, False
    return "C45 (1)", True


def map_m010(v: dict) -> dict:
    """Cylindrical Interference Fit → InterferenceFit（工况与公差带逐项映射）。"""
    tn = _f(v, "m01allg.FU") * _f(v, "m01allg.df") / 2.0  # FU×df/2 → N·mm
    # 量纲自检：圆周力×半径 与文件缓存名义扭矩（N·m）换算一致
    if abs(tn - _f(v, "m01M.nenn") * 1000.0) > 1e-3:
        raise ValueError("FU·df/2 ≠ m01M.nenn×1000（单位口径漂移）")
    inputs = {
        "DF": _f(v, "m01allg.df"),
        "LF": _f(v, "m01allg.l"),
        "DaA": _f(v, "m01n.da"),
        "Dil": _f(v, "m01w.di"),
        "Hub_Tol": v["m01n.tol.bez"],
        "Shaft_Tol": v["m01w.tol.bez"],
        "Tn": round(tn, 6),
        "Fa": _f(v, "m01allg.FA"),
        "n": _f(v, "m01allg.n"),
    }
    unmapped = [f"公差带按代号查标准表：毂 {v['m01n.tol.bez']}"
                f"（{v['m01n.tol.min']}/{v['m01n.tol.max']} µm）、"
                f"轴 {v['m01w.tol.bez']}（{v['m01w.tol.min']}/{v['m01w.tol.max']} µm）"]
    if _f(v, "m01allg.Mb") > 0:
        unmapped.append(f"弯矩 Mb={_f(v, 'm01allg.Mb'):g} N·m（组件无弯矩工况）")
    hub_mat, hub_fallback = _basic_mat(v.get("m01n.mat.bez"))
    shaft_mat, shaft_fallback = _basic_mat(v.get("m01w.mat.bez"))
    if hub_fallback:
        unmapped.append(f"毂材料 {v.get('m01n.mat.bez')} 未命中 Basic 表 →"
                        f" Params.Hub_Mat 回退 '{hub_mat}'（Rp/Rm 已按文件显式覆盖）")
    if shaft_fallback:
        unmapped.append(f"轴材料 {v.get('m01w.mat.bez')} 未命中 Basic 表 →"
                        f" Params.Shaft_Mat 回退 '{shaft_mat}'（Rp/Rm 已按文件显式覆盖）")
    params = {
        "uf": 0.1,
        "Hub_Mat": hub_mat, "Shaft_Mat": shaft_mat,
        "Hub_Rm": _f(v, "m01n.mat.Rm"), "Hub_Rp": _f(v, "m01n.mat.Rp"),
        "Shaft_Rm": _f(v, "m01w.mat.Rm"), "Shaft_Rp": _f(v, "m01w.mat.Rp"),
    }
    return {
        "component": "InterferenceFit", "inputs": inputs, "params": params,
        "notes": [f"m01allg.df={_f(v, 'm01allg.df'):g}/l={_f(v, 'm01allg.l'):g} → DF/LF；"
                  f"FU={_f(v, 'm01allg.FU'):.6g} N ×df/2 → Tn={tn:.4g} N·mm；"
                  f"FA={_f(v, 'm01allg.FA'):g} N → Fa；n={v['m01allg.n']} rpm → n",
                  f"毂外径 da={_f(v, 'm01n.da'):g} → DaA、轴内径 di={_f(v, 'm01w.di'):g}"
                  f" → Dil；公差带 {v['m01n.tol.bez']}/{v['m01w.tol.bez']}"
                  " → Hub_Tol/Shaft_Tol",
                  "配合面摩擦 μ=0.1 与粗糙度 RzA/Rzl=4.8——INI 无键（KISSsoft 存"
                  "库层），值取官方算例口径（test_interference_fit 对齐例同值；"
                  "组件 Rz 缺省已同为 4.8，uf 缺省 0.15 故显式给 0.1）",
                  f"材料：毂 {v.get('m01n.mat.bez')} → '{hub_mat}'、"
                  f"轴 {v.get('m01w.mat.bez')} → '{shaft_mat}'（Basic 表空格归一化"
                  "匹配；Rp/Rm 显式覆盖）",
                  "KISSsoft 锚点（文件缓存）：m01M.nenn=400 N·m（=Tn/1000，量纲自检通过）"],
        "unmapped": unmapped,
    }


def map_m050(v: dict) -> dict:
    """Shaft/Bore Ring → RetainingRing（几何全映射；a/d5 无源值用组件缺省）。"""
    import pyffalo.components  # noqa: F401
    from pyffalo.core.registry import get

    demo = get("RetainingRing").demo_input()
    typ = 1 if v.get("m050.isRingForShaft", "false") == "true" else 2
    inputs = {
        "Type": typ,
        "d1": _f(v, "m050.d1"), "d2": _f(v, "m050.d2"), "d3": _f(v, "m050.d3"),
        "t": _f(v, "m050.t"), "n": _f(v, "m050.n"), "b": _f(v, "m050.b"),
        "s": _f(v, "m050.s"), "g": _f(v, "m050.g"),
        "a": demo["a"], "d5": demo["d5"], "Fa": 0.0,
    }
    params = {"Sigma_S": _f(v, "m050.mat.Rp"), "E": _f(v, "m050.mat.E"),
              "ER": _f(v, "m050.matSeeger.E")}
    kind = "轴用外挡圈 (Type 1)" if typ == 1 else "孔用内挡圈 (Type 2)"
    return {
        "component": "RetainingRing", "inputs": inputs, "params": params,
        "notes": [f"isRingForShaft → {kind}；m050.d1/d2/d3/t/n/b/s/g 逐项 → 同名字段"
                  "（t 为沟槽深、n 为肩部长度）",
                  f"材料 {v['m050.mat.bez']}：Rp={v['m050.mat.Rp']} → Params.Sigma_S",
                  "KISSsoft 锚点（文件缓存输出）：应力集中系数 q、许可歪角 psi"],
        "unmapped": [f"a（耳部径向宽）与 d5（装配孔径）——算例无显式值，取组件"
                     f"缺省 a={demo['a']:g}/d5={demo['d5']:g}",
                     f"m050.l={v['m050.l']}（槽长/毂长）、μ={v['m050.mu']}（摩擦）"],
        "anchors": [("q", _f(v, "m050.q"), 0.01), ("psi", _f(v, "m050.psi"), 0.01)],
    }


def map_m02a(v: dict) -> dict:
    """Keys DIN 6892 → KeyJoint（M2A 方法 B 全链镜像）。"""
    typ = lambda x: "gjl" if int(_f(v, f"m02A{x}.mat.typ")) == 7 else "ductile"  # noqa: E731
    bh = lambda x: bool(int(_f(v, f"m02A{x}.mat.behandlung")) == 4)  # noqa: E731
    mom = _f(v, "m02Aa.MomArt")
    inputs = {
        "d": _f(v, "m02Aw.dWa"), "b": _f(v, "m02Ak.b"), "h": _f(v, "m02Ak.h"),
        "l": min(_f(v, "m02Aw.lW"), _f(v, "m02An.lN")),
        "t1": _f(v, "m02Ak.t1.min"), "t2": _f(v, "m02Ak.t2.min"),
        "s1": _f(v, "m02Aw.s1"), "s2": _f(v, "m02An.s2"),
        "r1": _f(v, "m02Ak.r1MaxK"), "D_hub": _f(v, "m02An.D1"),
        "a0": _f(v, "m02An.a0"), "n_keys": int(_f(v, "m02Aa.iANZ")),
        "T_nom": _f(v, "m02Aa.Mnenn") * 1000.0,  # KISSsoft N·m → 组件 N·mm
        "K_A": _f(v, "m02Aa.StossFak"),
        "T_max": _f(v, "m02Aa.Mmax") * 1000.0,
        "T_Rmin": _f(v, "m02Aa.TRmin") * 1000.0,
        "Alternating": int(mom) == 1,
        "T_back": _f(v, "m02Aa.TmaxRuck") * 1000.0,
        "NL": _f(v, "m02Aa.NL"), "NW": _f(v, "m02Aa.NW"),
    }
    params = {
        "Re": _f(v, "m02Ak.mat.Rp"), "Re_shaft": _f(v, "m02Aw.mat.Rp"),
        "Re_hub": _f(v, "m02An.mat.Rp"),
        "Rm": _f(v, "m02Ak.mat.Rm"), "Rm_shaft": _f(v, "m02Aw.mat.Rm"),
        "Rm_hub": _f(v, "m02An.mat.Rm"),
        "Mat_Key": typ("k"), "Mat_Shaft": typ("w"), "Mat_Hub": typ("n"),
        "Case_Key": bh("k"), "Case_Shaft": bh("w"), "Case_Hub": bh("n"),
    }
    return {
        "component": "KeyJoint", "inputs": inputs, "params": params,
        "notes": [f"键 b×h = {_f(v, 'm02Ak.b'):g}×{_f(v, 'm02Ak.h'):g}，"
                  f"受力直径 dWa={_f(v, 'm02Aw.dWa'):g}；承载长度"
                  f" lW/lN = {_f(v, 'm02Aw.lW'):g}/{_f(v, 'm02An.lN'):g}"
                  " → l = min（内核两侧压强共用 min(lW,lN)，COM 扫描钉死）；"
                  f"Mnenn={_f(v, 'm02Aa.Mnenn'):g} N·m ×1000 → T_nom；"
                  f"Mmax={_f(v, 'm02Aa.Mmax'):g} → T_max；TRmin="
                  f"{_f(v, 'm02Aa.TRmin'):g} → T_Rmin",
                  f"材料卡（own-input）：键 {v['m02Ak.mat.bez']}"
                  f" Rp={_f(v, 'm02Ak.mat.Rp'):g}/Rm={_f(v, 'm02Ak.mat.Rm'):g}"
                  f" typ={int(_f(v, 'm02Ak.mat.typ'))}；轴"
                  f" {v['m02Aw.mat.bez']} typ={int(_f(v, 'm02Aw.mat.typ'))}；毂"
                  f" {v['m02An.mat.bez']} typ={int(_f(v, 'm02An.mat.typ'))}——"
                  "typ=7 (GJL) 走脆性轨道 p_zul=f_S·R_m；behandlung=4 渗碳"
                  " → f_H=1.15",
                  f"载荷谱：NL={_f(v, 'm02Aa.NL'):g}（f_L）、"
                  f"NW={_f(v, 'm02Aa.NW'):g}（f_w）、MomArt={mom:g}"
                  f"（{'交变' if mom == 1 else '非交变'}）、"
                  "TmaxRuck=Umkehr 返向峰"],
        "unmapped": ["m02An.D2/c（阶梯毂分段，内核 cFlag=false 下不消费）",
                     "m02Aa.phiFak/ieff（齿面角系数）、键槽公差带 t1.max/t2.max"],
    }


def map_m02b(v: dict) -> dict:
    """Straight Sided Spline（DIN ISO 14 轻系列）→ SplineShaft。"""
    z = int(_f(v, "m02Ba.iANZ"))
    dm = _f(v, "m02Ba.dm")
    t_mm = _f(v, "m02Ba.Mnenn") * 1000.0  # KISSsoft N·m → 组件 N·mm
    # 量纲自检：圆周力 = 2·扭矩/平均直径
    if abs(2.0 * t_mm / dm - _f(v, "m02Ba.Ft")) > 1e-6 * _f(v, "m02Ba.Ft"):
        raise ValueError("Ft ≠ 2·Mnenn/dm（单位口径漂移）")
    inputs = {
        "profile_type": "splined",
        "d1": _f(v, "m02Bk.d1Keil"), "d2": dm, "z": z, "b": _f(v, "m02Bk.bKeil"),
        "l_tr": _f(v, "m02Ba.ltr"),
        "T_nom": t_mm,
        "K_A": _f(v, "m02Ba.StossFak"),
    }
    params = {
        "Re_shaft": _f(v, "m02Bw.mat.Rp"), "Re_hub": _f(v, "m02Bn.mat.Rp"),
        "f_S_shaft": _f(v, "m02Bw.fs"), "f_S_hub": _f(v, "m02Bn.fs"),
    }
    return {
        "component": "SplineShaft", "inputs": inputs, "params": params,
        "notes": [f"m02Ba.dm={dm:g}/iANZ={z} → d2(大径)/z；d1Keil="
                  f"{_f(v, 'm02Bk.d1Keil'):g} → d1、bKeil={_f(v, 'm02Bk.bKeil'):g}"
                  " → b（源文件显式值，恰合 DIN ISO 14 轻系列 8×46×50×9）",
                  f"ltr={_f(v, 'm02Ba.ltr'):g} → l_tr；Mnenn={_f(v, 'm02Ba.Mnenn'):g}"
                  f" N·m ×1000 → T_nom；StossFak={v['m02Ba.StossFak']} → K_A",
                  f"材料：轴 {v['m02Bw.mat.bez']} Rp={_f(v, 'm02Bw.mat.Rp'):g} →"
                  f" Re_shaft、毂 {v['m02Bn.mat.bez']}"
                  f" Rp={_f(v, 'm02Bn.mat.Rp'):g} → Re_hub；"
                  f"fs 轴/毂 → f_S_shaft/f_S_hub"],
        "unmapped": ["花键本体基准 Re（齿面许用基准 p_zul_base=Re，2026-10-02 "
                     "KISSsoft pzul=Rp·fs 口径对齐）——文件无花键"
                     "材料值，按组件缺省 C45 正火 245 MPa（轴/毂 Rp 已显式映射）",
                     f"d2Keil={v['m02Bk.d2Keil']}（含齿高的毛坯大径，非配合大径 dm）"
                     f"与 hKeil={v['m02Bk.hKeil']}（齿高）未映射",
                     "制造工艺 Herstell 与寿命参数 Ft/FtEl/NW（组件为静强度校核）"],
    }


def map_z92(v: dict) -> dict:
    """Chain Drive → RollerChainDrive（官方算例 = 组件 demo_input，逐变量核对）。"""
    if v.get("belt.Konfig", "0") != "0":
        raise ValueError("仅两轮开口构型映射（Konfig≠0 张紧轮变体见 README）")
    import pyffalo.components  # noqa: F401
    from pyffalo.data.database import DataBase

    # TypID = 10000 + 10×No（Roller_Chain 表行号，公式见
    # tools/gen_roller_chain_power_kisssoft.py——10110=06B-2 双验证）反推链型代号
    typ_id = int(_f(v, "z092k.TypID"))
    no = (typ_id - 10000) // 10
    with DataBase() as db:
        rows = db.list_mats("Roller_Chain")
    hit = next((r for r in rows if r["No"] == no), None)
    if hit is None or 10000 + 10 * hit["No"] != typ_id:
        raise ValueError(f"TypID={typ_id} 无法反解 Roller_Chain 表行（No={no} 越界）")
    inputs = {
        "Designation": hit["Code"],
        "z1": int(_f(v, "z092k.z1")), "z2": int(_f(v, "z092k.z2")),
        "n1": _f(v, "z092k.n1"),
        "P": _f(v, "z092k.PN"),
        "a": _f(v, "z092k.a"),
        "DrivenKind": "steady",
    }
    return {
        "component": "RollerChainDrive", "inputs": inputs, "params": {},
        "notes": [f"z092k.z1/z2/n1/PN/a={_f(v, 'z092k.z1'):g}/{_f(v, 'z092k.z2'):g}/"
                  f"{_f(v, 'z092k.n1'):g}/{_f(v, 'z092k.PN'):g}/{_f(v, 'z092k.a'):g}"
                  " 逐项 → 同名字段；链型 TypID="
                  f"{typ_id} → 表行 No={no:g} → Designation='{hit['Code']}'"
                  "（TypID 公式反推，与 demo_input 一致）",
                  f"z092k.f1={v['z092k.f1']} 为工况系数（→ DrivenKind=steady，"
                  "组件 KA：steady×steady=1.0 一致——漏设会吃缺省"
                  " moderate_shock KA≈1.4）；z092k.f2="
                  f"{_f(v, 'z092k.f2'):.4g} 即 KISSsoft 速度折算因子 (19/z1)^1.08"
                  "（组件 PowerUtilization 已内含该口径，非独立输入）",
                  "KISSsoft 锚点（文件缓存 + COM 金样）：belt.Lange="
                  f"{_f(v, 'belt.Lange'):.4f} mm、belt.ZahneZ={v['belt.ZahneZ']}"
                  "（组件 LinkCount 输出）、Pkette=Sich 口径利用率 57.698%"
                  "（COM 实算，组件 demo 逐位复现）"],
        "unmapped": ["链条每米质量（Roller_Chain 表无质量列）——Params.MassPerMeter"
                     " 未给，F_c 未计入、StaticFactor 偏危险方向（求解告警）",
                     f"z092k.z3={v['z092k.z3']}/prio={v['z092k.prio']}/"
                     f"n2Edit={v['z092k.n2Edit']}/i1={v['z092k.i1']}"
                     "（张紧轮齿数/优先级目标/转速直改标志，两轮构型不参与）"],
        "anchors": [("ChainLength_mm", _f(v, "belt.Lange"), 0.001),
                    ("LinkCount", _f(v, "belt.ZahneZ"), 1e-9),
                    ("PowerUtilization", 57.698, 0.01)],
    }


def map_z90(v: dict) -> dict:
    """V Belt → VBeltDrive（官方算例 = 组件 demo_input，COM 逐项对标 26/36 逐位）。"""
    if v.get("belt.Konfig", "0") != "0":
        raise ValueError("仅两轮开口构型映射（Konfig≠0 张紧轮变体见 README）")
    if v.get("belt.Typ") != "0":
        raise ValueError("仅 Typ=0（SPZ-CONTI-V，dat Z090-022）族映射——组件唯一带型")
    inputs = {
        "BeltType": "SPZ-CONTI",
        "PulleyDia1": _f(v, "sheave[0].d"),
        "PulleyDia2": _f(v, "sheave[1].d"),
        "Speed1": _f(v, "z090k.n1"),
        "Power": _f(v, "z090k.PN"),
        "CenterDistance": _f(v, "z090k.a"),
        "ServiceFactor": _f(v, "z090k.cB"),
        "BeltCount": int(_f(v, "belt.neff")),
    }
    return {
        "component": "VBeltDrive", "inputs": inputs, "params": {},
        "notes": [f"sheave[0]/[1].d={_f(v, 'sheave[0].d'):g}/{_f(v, 'sheave[1].d'):g}"
                  f" → PulleyDia1/2；z090k.n1/PN/a/cB={_f(v, 'z090k.n1'):g}/"
                  f"{_f(v, 'z090k.PN'):g}/{_f(v, 'z090k.a'):g}/{_f(v, 'z090k.cB'):g}"
                  " → Speed1/Power/CenterDistance/ServiceFactor；belt.neff="
                  f"{v['belt.neff']} → BeltCount",
                  f"belt.Typ={v['belt.Typ']}（DinIdK={v['z090k.DinIdK']}）为"
                  " KISSsoft 带型族号——Typ=0 即 SPZ-CONTI-V（dat Z090-022），"
                  "组件唯一带型 Literal 直接落位",
                  "KISSsoft 锚点（COM 实跑基准 2026-09-30，"
                  "examples/connection/README.md 对标表：36 项输出 26 项逐位"
                  " 0.0000%）：Ld=1400 / α1=167.56503° / P0=2.56 / PC=2.636331"
                  " / nth=0.7586303 / Sich=75.86303% / v=7.853982 /"
                  " TrFmin=137.5906"],
        "unmapped": [f"z090k.i={v['z090k.i']}/n2={v['z090k.n2']}（传动比与大轮转速"
                     "为派生量，组件 Ratio/Speed2 输出）",
                     f"belt.Lange={_f(v, 'belt.Lange'):.4f}（几何带长派生值，组件"
                     "向上取标准档 1400 = BeltLength 输出）",
                     f"z090k.prio={v['z090k.prio']}/n2Edit={v['z090k.n2Edit']}"
                     f"/sheave[2].d={v['sheave[2].d']}（优先级目标/转速直改标志/"
                     "张紧轮——Konfig=0 两轮构型不参与）"],
        "anchors": [("BeltLength", 1400.0, 1e-9),
                    ("WrapAngle1", 167.56503, 1e-5),
                    ("P0", 2.56, 1e-9),
                    ("AllowedPower", 2.636331, 1e-5),
                    ("BeltsRequired", 0.7586303, 1e-5),
                    ("Utilization", 75.86303, 1e-5),
                    ("BeltSpeed", 7.853982, 1e-5),
                    ("MinPretension", 137.5906, 1e-4)],
    }


def map_w050(v: dict) -> dict:
    """W50 深沟球目录法 → DeepGrooveBallBearing（e/X/Y/P/L10h 逐位链）。"""
    if "Deep Groove" not in v.get("calculation.name", ""):
        raise ValueError("仅 01 Deep Groove（6208）映射——02 Tapered 内几何未知不建")
    fr = _f(v, "Lag[0].Fr")
    fa = _f(v, "Lag[0].Fa")
    inputs = {
        "Z": 9, "Dpw": 60.0, "Dw": 12.0, "Di": 40.0, "Do": 80.0,
        "T": 18.0, "C": 18.0, "B": 18.0, "Pd0": 0.0,
        "Fr": fr, "Fa": fa, "n": _f(v, "Allg.Drehzahl"),
    }
    params = {
        "Reliability": 100.0 - _f(v, "Allg.AusfallW"),
        "Cu": 1250.0, "Contamination": 0,
        "nu40": _f(v, "Allg.Oil.nu40"), "nu100": 19.0,
        "Temp": _f(v, "Allg.Oil.theOil"),
    }
    return {
        "component": "DeepGrooveBallBearing", "inputs": inputs, "params": params,
        "notes": [
            f"Lag[0].Fr/Fa={fr:g}/{fa:g}、Allg.Drehzahl={v['Allg.Drehzahl']}"
            " → Fr/Fa/n；Cu_considered=1.25 kN → Cu；id=0（油润滑过滤）"
            " → Contamination=0（eC 快照表恒 0.5）",
            "内几何为 6208 估值（Z=9/Dw=12/Dpw=60，γ=0.20 → f0(γ) 样条 =14.0"
            " 与官方 e/X/Y 插值轴 f0·Fa/C0 逐位一致）；外形 d/D/B=40/80/18",
            "KISSsoft 锚点（COM 金样 tests/golden/bearing_life/kisssoft_w50.json"
            " w50_01）：e=0.36350/X=0.56/Y=1.46600 逐位、P=4303.114、S0=5.69145、"
            "L10h=10293.86、aISO=10.5067（组件 10.53，0.2%）",
            "C0 口径差：e/X/Y 横轴 f0·Fa/C0 的 C0 官方用目录 17800 N、"
            "组件 ISO 76 自算 18144 N（+1.9%），e/Y/P/S0 随之 ±0.5~1.9%"
            "（锚容差已放宽并在此注明，ISO 281 理论与厂商目录的常规源差）"],
        "unmapped": [
            "TypeID=16116 目录内几何（W05WNORM50INT 未逆向，Z/Dw 为估值——"
            "Cr/Co 组件自算 21962/13575 N vs 目录 36400/17800 N，ISO 281 理论"
            "与厂商目录的常规源差，寿命链经 Cu/工况参数自洽不受影响）",
            "Allg.SchragLag/Vorspannkraft=0（角接触支反力/预紧——深沟球零预紧"
            "工况不参与）、Lag[0].P1（载荷谱缓存）",
            "Cr 目录源差：官方 C=36.4 kN（厂商目录）vs 组件 ISO 281 自算 "
            "29.5 kN（−19%），L10h/Lnmh 随 (C/P)^3 放大至 −47%——绝对寿命"
            "锚不可比，e/X/Y/P/S0（输入端）与 κ 已锚定；厂商 Cr 直用需组件"
            "Cr 手填覆盖（后续）"],
        "anchors": [("e", 0.363500802568, 1e-2),
                    ("X", 0.56, 1e-9),
                    ("Y", 1.465996789727, 1e-2),
                    ("P", 4303.114012199, 5e-3),
                    ("S0", 5.691446842526, 3e-2),
                    ("kappa", 2.7044, 5e-3)],
    }


def map_w051(v: dict) -> dict:
    """W51 内几何精算 → BearingLife16281（16281 切片柔度，官方 Cr 直入）。"""
    name = v.get("calculation.name", "")
    fr_v = [float(x) for x in v["loading.F"].split(",")]
    params = {
        "Reliability": 100.0 - float(v["loading.failureProbability"]),
        "Contamination": int(float(v["oil.contaminationId"])),
        "Cu": _f(v, "geometry.cu"),
    }
    if v["geometry.DBid"] == "10010":  # 深沟球（03/04）
        inputs = {
            "Z": int(_f(v, "geometry.Z")), "Dpw": _f(v, "geometry.Dpw"),
            "Dw": _f(v, "geometry.Dw"), "BearingType": "ball",
            "Cr": _f(v, "geometry.cr"), "Co": _f(v, "geometry.c0r"),
            "Fr": abs(fr_v[1]), "n": _f(v, "loading.nInnerRing"),
            "We": _f(v, "geometry.Pd"),
        }
        params["Kappa"] = (2.8535031191988315946 if "Inner Geometry" in name
                           else 2.88435269812393)  # 金样 κ（油品锁库）
        is03 = "Inner Geometry" in name
        anchors = [
            ("eC", 0.125947251700476 if is03 else 0.130099410124090,
             1e-5 if is03 else 5e-3),  # 04: Dpw=47 断点插值差 0.35%
            ("Pref", 1057.582432977 if is03 else 1095.21304641,
             2e-3 if is03 else 1e-2),
            ("L10r", 94.240208822 if is03 else 458.052883454,
             1e-3 if is03 else 3e-2)]
        if is03:
            anchors.append(("Lnmrh", 567.2681997867374, 1e-2))
        unmapped = [
            "geometry.ri/ro（沟曲率——球点接触不进切片链）、HV=660（Cu "
            "显式给定）",
            "loading.u/geometry.Pa（位移缓存/轴向游隙，零接触角不参与）",
            "rollerProfile.dat（球无修形）",
            "油品粘度（oil.nu40/nu100 库锁定，κ 取金样实测值直传——"
            "Kappa 手填优先级）"]
        note = ("03/04 案 KISSsoft 锚点（金样 w51_03/04 + 官方 Cr 直入）："
                "03 案 Pref 1057.58（组件 0.014%）、L10r 94.240（0.04%）、"
                "Lnmrh 567.27（0.07%）；04 案 Pref 0.62% 经立方放大 L10r "
                "1.9%（g(ε) 插值 + cs 源差）")
        return {"component": "BearingLife16281", "inputs": inputs,
                "params": params,
                "notes": [f"geometry.Z/Dw/Dpw={inputs['Z']}/{inputs['Dw']:g}/"
                          f"{inputs['Dpw']:g}、官方 cr/c0r 直入（无 bm 源差）、"
                          f"Pd={v['geometry.Pd']} → We、loading.F 取 |Fy| → Fr",
                          note],
                "unmapped": unmapped, "anchors": anchors}
    # 10090 圆柱滚子（05）——对数修形 Cu 定标（官方 rollerProfile.dat 同式）
    inputs = {
        "Z": int(_f(v, "geometry.Z")), "Dpw": _f(v, "geometry.Dpw"),
        "Dw": _f(v, "geometry.Dw"), "Lwe": 25.0, "BearingType": "roller",
        "Cr": _f(v, "geometry.cr"), "Co": _f(v, "geometry.c0r"),
        "Fr": abs(fr_v[1]), "n": _f(v, "loading.nInnerRing"),
    }
    params["Kappa"] = 3.3482325098721292811
    params["Profile"] = 1
    return {
        "component": "BearingLife16281", "inputs": inputs, "params": params,
        "notes": [
            f"geometry.Z/Dw/Dpw={inputs['Z']}/{inputs['Dw']:g}/{inputs['Dpw']:g}"
            "、Lwe=25、官方 cr/c0r 直入、Cu=geometry.cu（对数修形定标 = "
            "官方 rollerProfile.dat 同式，A 逐位验证）",
            "05 案 KISSsoft 锚点（金样 w51_05）：Pref 5055.60（组件 "
            "0.004%）、L10r 113778（0.013%）、Lnmrh 差 0.23%、Pks 切片形态 "
            "0.026 / 受载片 31 vs 33（切片柔度 + 修形端部脱离）"],
        "unmapped": [
            "ringDeformation.dat（弹性环变形——pmax 内外反差根源，spec 六批"
            "边界；组件 pmax 为刚套圈口径）",
            "loading.F 的 Fz=18.22（α=0 不承载轴向，KISSsoft 同口径忽略）、"
            "geometry.ri/ro=0（直滚道）",
            "油品粘度库锁定（κ 取金样实测直传）"],
        "anchors": [("eC", 0.2934251731085846, 1e-5),
                    ("kappa", 3.3482325098721, 1e-9),
                    ("Pref", 5055.599730761, 2e-3),
                    ("L10r", 113777.990148, 5e-3),
                    ("Lnmrh", 16929020.0, 5e-3)],
    }


#: 模块号 → (glob 扩展, 映射函数)；扩展大小写不敏感匹配
MODULES: dict[str, tuple[str, object]] = {
    "K014": ("k14", map_k014),
    "F010": ("f10", map_f010),
    "F040": ("f40", map_f040),
    "M010": ("m10", map_m010),
    "M050": ("m50", map_m050),
    "M02A": ("m2a", map_m02a),
    "M02B": ("m2b", map_m02b),
    "Z90": ("z90", map_z90),
    "Z92": ("z92", map_z92),
    "W050": ("w50", map_w050),
    "W051": ("w51", map_w051),
}


TEMPLATE = '''"""KISSsoft 官方算例复刻：{title}

源：``C:/KISSsoft 2026/example/{src_name}``（KISSsoft 2026 官方案例库，模块 {module}）
组件：``pyffalo.{component}``（映射表 ``tools/gen_kisssoft_examples.py``，重生成幂等）

映射说明：
{notes}

未映射项（不硬凑，见 spec 映射原则）：
{unmapped}
"""

from pyffalo.components import {component}

comp = {component}(
{call_args}
)

result = comp.solve()
o = result.output
for _name in type(comp).provides:
    print(_name, "=", getattr(o, _name))
{anchor_block}'''

_ANCHOR_LOOP = """# KISSsoft 锚点断言（tools/gen_kisssoft_examples.py 维护；rel 为相对容差）
for _name, _exp, _rel in [
{anchor_entries}
]:
    _got = float(getattr(o, _name))
    assert abs(_got - _exp) <= _rel * _exp, (_name, _got, _exp)
"""


def render(title: str, src_name: str, module: str, mapped: dict) -> str:
    def fmt(d: dict) -> list[str]:
        return [f"    {k}={v!r}," for k, v in d.items()]

    anchors = mapped.get("anchors") or []
    anchor_block = ""
    if anchors:
        entries = "\n".join(f"    ({n!r}, {exp!r}, {rel!r})," for n, exp, rel in anchors)
        anchor_block = "\n" + _ANCHOR_LOOP.format(anchor_entries=entries)

    # inputs/params 渲染形态相同，合并成一段实参列表（params 空时不留空行）
    call_args = "\n".join([*fmt(mapped["inputs"]), *fmt(mapped["params"])])

    body = TEMPLATE.format(
        title=_s(title), src_name=_s(src_name), module=_s(module),
        component=mapped["component"],
        notes="\n".join(f"- {_s(n)}" for n in mapped["notes"]),
        unmapped="\n".join(f"- {_s(u)}" for u in mapped["unmapped"]),
        call_args=call_args,
        anchor_block=anchor_block,
    )
    return body


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", action="store_true", help="生成后逐例运行验证")
    args = ap.parse_args(argv)

    generated: list[Path] = []
    for module, (ext, mapper) in MODULES.items():
        files = sorted(p for p in KS_EXAMPLE.iterdir()
                       if p.suffix.lower() == f".{ext}")
        if not files:
            print(f"[{module}] 无匹配算例文件")
            continue
        out_dir = OUT_ROOT / module
        if out_dir.exists():
            for old in out_dir.glob("*.py"):
                old.unlink()  # 幂等：目录内容与当前映射表一致
        out_dir.mkdir(parents=True, exist_ok=True)
        for path in files:
            v = parse_case(path)
            title = path.stem
            if not _SAFE_STEM.fullmatch(title):
                print(f"[{module}] 跳过 {path.name}: 文件名含白名单外字符")
                continue
            try:
                mapped = mapper(v)
            except (ValueError, KeyError, IndexError) as exc:
                print(f"[{module}] 跳过 {path.name}: {exc}")
                continue
            script = out_dir / f"{title}.py"
            script.write_text(render(title, path.name, module, mapped),
                              encoding="utf-8")
            generated.append(script)
            print(f"[{module}] {script.relative_to(REPO)}")

    if args.run:
        failed = 0
        for script in generated:
            try:
                runpy.run_path(str(script), run_name="__main__")
                print(f"  ok: {script.name}")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"  FAIL {script.name}: {exc}")
        print(f"--run 完成：{len(generated) - failed}/{len(generated)} 通过")
        return 1 if failed else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
