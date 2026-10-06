"""HirthCoupling（KISSsoft M060）金样收割器。

两个子模式（一次 Dispatch 共用会话）：

- ``--profile``：Voith 目录 99 行快照 →
  ``tools/data/hirth_coupling/voith_profile.csv``（seed 消费）。七列来自
  ``dat/M060-001.DAT`` 明文（name|z|D|d|Trating[Nm]|n|dL）；R_root/S_crown
  为 COM 读回的**内核派生值**——Voith 按 m_i=d/z 分段表导出 r=s（cat_D50
  案暴露 r≠s 且 s 疑似还依赖 l，非闭式），故逐行快照、永不插值。
- ``--golden``（默认）：官方 2 案 + 文件变体 →
  ``tests/golden/hirth_coupling/kisssoft_m60.json``；全部案过收割期闭式
  断言（公式链 vs 内核逐位，rel ≤ 1e-9）后一次性落盘（失败不覆盖旧档）。

COM 形态照 ``gen_torsion_bar_kisssoft.py``：SetSilentMode(True) →
GetModule("M060", True)（返回值丢弃、方法全在根对象）→ 文件变体（UTF-16
key=value¶ 锚定行首严版替换）→ LoadFile **绝对路径** → CalculateRetVal()
唯一判据 → GetVar → finally ReleaseModule。

公式链与判废面（探针 P0~P2f 六轮钉死，docs/specs/hirth-serration-m60.md）::

    He = D·sin(π/z)/(2tanβ)；Hi = d·sin(π/z)/(2tanβ)；Hm = (He+Hi)/2
    Δ  = s + 2(1/sinβ−1)·r；he/hi/hm = H·−Δ；bk = tanβ·(Δ+s)
    G  = z·l·(Hm/cosβ − bk/sinβ)；Az = G·(1 − n·dL²/(D²−d²))
    Fu = 2T/dm；Fa = Fu·tanβ；Fva = ν·Fa；p[i] = (Fva+Fa)/(Az·ηz[i])
    plim[i] = 1.1·(Rp_i 韧性 | Rm_i 脆性 typ==7)；fL[i] = f_l(NL, brittle)
    SF[i] = fL[i]·plim[i]/p[i]

已知边界：m060.Trating 经 GetVar 恒 0（不入金样，组件查表同源）；
目录档（ID=10010）β 锁 30°、r/s 重导出——金样 cat_* 案以读回 r/s 按
自输模式复现（flip_own 案证 ID 不进计算）。
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
from pathlib import Path

import pyffalo_root

ROOT = pyffalo_root.repo_root()
sys.path.insert(0, str(ROOT / "src"))

KS_EXAMPLE = Path(r"C:\KISSsoft 2026\example")
KS_DAT = Path(r"C:\KISSsoft 2026\dat\M060-001.DAT")
CASES_DIR = ROOT / "tmp" / "m60_harvest_cases"
GOLDEN = ROOT / "tests" / "golden" / "hirth_coupling" / "kisssoft_m60.json"
PROFILE_CSV = ROOT / "tools" / "data" / "hirth_coupling" / "voith_profile.csv"

_BASES = {"ex11": "11 Hirth (Voith).M60", "ex12": "12 Hirth (Custom).M60"}

#: 全变量名录（输入回显 + RPT 权威输出集；m060.name/Trating GetVar 不可达）
VARS = [
    "m060.ID", "m060.z", "m060.beta", "m060.D", "m060.d",
    "m060.r", "m060.s", "m060.n", "m060.dL", "m060.T", "m060.nu",
    "m060.NL", "m060.SFmin", "m060.etaz[0]", "m060.etaz[1]",
    "m060.mat[0].DBID", "m060.mat[0].Rp", "m060.mat[0].Rm", "m060.mat[0].typ",
    "m060.mat[1].DBID", "m060.mat[1].Rp", "m060.mat[1].Rm", "m060.mat[1].typ",
    "m060.A", "m060.He", "m060.Hi", "m060.Hm", "m060.he", "m060.hi", "m060.hm",
    "m060.bk", "m060.Fu", "m060.Fa", "m060.Fva",
    "m060.fS[0]", "m060.fS[1]", "m060.fL[0]", "m060.fL[1]",
    "m060.fH[0]", "m060.fH[1]",
    "m060.p[0]", "m060.p[1]", "m060.plim[0]", "m060.plim[1]",
    "m060.SF[0]", "m060.SF[1]",
]

RAD = {15: 0.2617993877991494, 25: 0.4363323129985824,
       30: 0.5235987755982988, 36: 0.6283185307179586,
       40: 0.6981317007977318, 44: 0.767944870877505}

_OWN_MAT0 = {"m060.mat[0].Rp": 500, "m060.mat[0].Rm": 800,
             "m060.mat[0].E": 210000, "m060.mat[0].typ": 6,
             "m060.mat[0].bez": "OwnDuctile"}
_OWN_MAT1_BRITTLE = {"m060.mat[1].Rp": 250, "m060.mat[1].Rm": 400,
                     "m060.mat[1].E": 110000, "m060.mat[1].typ": 7,
                     "m060.mat[1].bez": "OwnGJL"}
_OWN_MAT1_DUCTILE = {"m060.mat[1].Rp": 520, "m060.mat[1].Rm": 820,
                     "m060.mat[1].E": 210000, "m060.mat[1].typ": 6,
                     "m060.mat[1].bez": "OwnDuctile2"}

#: 金样案集（name, base, changes, upserts）——覆盖矩阵：官方双案 / β 六点 /
#: z 四点 / D·d 四点 / r·s 单因子+交叉 / n·dL 孔减 / 齐次 ×1.5 / NL 五点 /
#: ηz 对称+非对称 / ν 三点 / own 材料（延·脆·混合）/ T 缩放 / 目录三行
#: （含 D=900 端档）/ 判废边缘锚（r=3.66 近零 hi、r=0·s=3.2 近零 Az）。
CASES: list[tuple[str, str, list[tuple[str, object]], dict]] = [
    ("voith_ex11", "ex11", [], {}),
    ("custom_ex12", "ex12", [], {}),
    ("beta15", "ex12", [("m060.beta", RAD[15])], {}),
    ("beta25", "ex12", [("m060.beta", RAD[25])], {}),
    ("beta30", "ex12", [("m060.beta", RAD[30])], {}),
    ("beta40", "ex12", [("m060.beta", RAD[40])], {}),
    ("beta44", "ex12", [("m060.beta", RAD[44])], {}),
    ("z12", "ex12", [("m060.z", 12)], {}),
    ("z24", "ex12", [("m060.z", 24)], {}),
    ("z48", "ex12", [("m060.z", 48)], {}),
    ("z72", "ex12", [("m060.z", 72)], {}),
    ("D125", "ex12", [("m060.D", 125)], {}),
    ("D160", "ex12", [("m060.D", 160)], {}),
    ("d65", "ex12", [("m060.d", 65)], {}),
    ("d95", "ex12", [("m060.d", 95)], {}),
    ("r0", "ex12", [("m060.r", 0)], {}),
    ("r1_5", "ex12", [("m060.r", 1.5)], {}),
    ("s0", "ex12", [("m060.s", 0)], {}),
    ("s1_5", "ex12", [("m060.s", 1.5)], {}),
    ("rs_cross", "ex12", [("m060.r", 0.25), ("m060.s", 0.3)], {}),
    ("n0", "ex12", [("m060.n", 0)], {}),
    ("n12", "ex12", [("m060.n", 12)], {}),
    ("dL5", "ex12", [("m060.dL", 5)], {}),
    ("dL20", "ex12", [("m060.dL", 20)], {}),
    ("homog15", "ex12", [("m060.D", 157.5), ("m060.d", 127.5),
                         ("m060.r", 0.75), ("m060.s", 0.9),
                         ("m060.dL", 15)], {}),
    ("nl_1", "ex12", [("m060.NL", 1)], {}),
    ("nl_1e2", "ex12", [("m060.NL", 100)], {}),
    ("nl_1e6", "ex12", [("m060.NL", 1000000)], {}),
    ("nl_1e7", "ex12", [("m060.NL", 10000000)], {}),
    ("etaz_asym", "ex12", [("m060.etaz[0]", 0.75), ("m060.etaz[1]", 0.5)], {}),
    ("etaz_1", "ex12", [("m060.etaz[0]", 1.0), ("m060.etaz[1]", 1.0)], {}),
    ("nu05", "ex12", [("m060.nu", 0.5)], {}),
    ("nu3", "ex12", [("m060.nu", 3.0)], {}),
    ("T300", "ex12", [("m060.T", 300)], {}),
    ("T1500", "ex12", [("m060.T", 1500)], {}),
    ("own_ductile", "ex12", [("m060.mat[0].DBID", 19999),
                             ("m060.mat[1].DBID", 19999)],
     {**_OWN_MAT0, **_OWN_MAT1_DUCTILE}),
    ("own_mixed", "ex12", [("m060.mat[0].DBID", 19999),
                           ("m060.mat[1].DBID", 19999)],
     {**_OWN_MAT0, **_OWN_MAT1_BRITTLE}),
    ("own_brittle", "ex12", [("m060.mat[0].DBID", 19999),
                             ("m060.mat[1].DBID", 19999)],
     {"m060.mat[0].Rp": 260, "m060.mat[0].Rm": 420,
      "m060.mat[0].E": 110000, "m060.mat[0].typ": 7,
      "m060.mat[0].bez": "OwnGJL1", **_OWN_MAT1_BRITTLE}),
    ("cat_H15.092040", "ex11", [("m060.z", 24), ("m060.D", 100),
                                ("m060.d", 60), ("m060.n", 10),
                                ("m060.dL", 9.4)], {}),
    ("cat_H15.092840", "ex11", [("m060.z", 180), ("m060.D", 800),
                                ("m060.d", 670), ("m060.n", 26),
                                ("m060.dL", 17.23)], {}),
    ("cat_H15.097630", "ex11", [("m060.z", 240), ("m060.D", 900),
                                ("m060.d", 760), ("m060.n", 26),
                                ("m060.dL", 17.23)], {}),
    ("edge_r366", "ex12", [("m060.r", 3.66)], {}),
    ("edge_r0s32", "ex12", [("m060.r", 0), ("m060.s", 3.2)], {}),
]


def _setkey(text: str, key: str, val) -> str:
    """锚定行首替换（严版不跨行；lambda 防替换模板转义）。"""
    text, n = re.subn(rf"^{re.escape(key)}=[^¶\r\n]*¶",
                      lambda _m: f"{key}={val}¶", text, flags=re.MULTILINE)
    if n != 1:
        raise SystemExit(f"变体键 {key} 替换 {n} 处（应为 1）")
    return text


def _upsert(text: str, key: str, val) -> str:
    if re.search(rf"^{re.escape(key)}=[^¶\r\n]*¶", text, flags=re.MULTILINE):
        return _setkey(text, key, val)
    if not text.endswith("\n"):
        text += "\r\n"
    return text + f"{key}={val}¶\r\n"


def _getvar(ksoft, name: str):
    try:
        raw = ksoft.GetVar(name)
    except Exception:
        return None
    if raw is None or raw == "":
        return None
    s = str(raw).rstrip("¶").strip()
    try:
        return float(s)
    except ValueError:
        return s


def _closure(name: str, e: dict) -> None:
    """收割期闭式断言：**运行时公式链**（data/hirth_coupling）vs 内核逐位
    （rel ≤ 1e-9，探针实测 ≤3.6e-15）——复用 shipped 闭式而非脚本内副本
    （否则 data 层日后改动不会暴露给收割期断言——质量门 m7）。"""
    from pyffalo.data import hirth_coupling as hc
    from pyffalo.data.key_joint import f_l

    z = int(e["m060.z"])
    beta_deg = math.degrees(float(e["m060.beta"]))
    g = hc.geometry(z, beta_deg, e["m060.D"], e["m060.d"], e["m060.r"],
                    e["m060.s"], int(e["m060.n"]), e["m060.dL"])
    f = hc.forces(e["m060.T"] * 1000.0, e["m060.nu"], beta_deg, g["dm"])
    pairs = {"m060.He": g["He"], "m060.Hi": g["Hi"], "m060.Hm": g["Hm"],
             "m060.he": g["he"], "m060.hi": g["hi"], "m060.hm": g["hm"],
             "m060.bk": g["bk"], "m060.A": g["A_z"],
             "m060.Fu": f["F_u"], "m060.Fa": f["F_a"], "m060.Fva": f["F_va"]}
    for i in (0, 1):
        p = (f["F_va"] + f["F_a"]) / (g["A_z"] * e[f"m060.etaz[{i}]"])
        brittle = int(e[f"m060.mat[{i}].typ"]) == 7
        plim = hc.FS * (e[f"m060.mat[{i}].Rm"] if brittle
                        else e[f"m060.mat[{i}].Rp"])
        fl = f_l(e["m060.NL"], brittle=brittle)
        pairs[f"m060.p[{i}]"] = p
        pairs[f"m060.plim[{i}]"] = plim
        pairs[f"m060.fL[{i}]"] = fl
        pairs[f"m060.fS[{i}]"] = hc.FS
        pairs[f"m060.fH[{i}]"] = hc.FH
        pairs[f"m060.SF[{i}]"] = fl * plim / p
    for k, pred in pairs.items():
        want = e[k]
        if want is None:
            raise SystemExit(f"[{name}] 变量 {k} 收割为空")
        if abs(pred - want) > 1e-9 * max(abs(want), 1.0):
            raise SystemExit(
                f"[{name}] 闭式断言失败 {k}: pred={pred!r} vs kernel={want!r}")


def _harvest(ksoft) -> dict:
    texts = {n: (KS_EXAMPLE / f).read_text("utf-16") for n, f in _BASES.items()}
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    cases: dict[str, dict] = {}
    for name, base, changes, upserts in CASES:
        t = texts[base]
        for key, val in changes:
            t = _setkey(t, key, val)
        for key, val in upserts.items():
            t = _upsert(t, key, val)
        case = CASES_DIR / f"m60_{name}.M60"
        case.write_text(t, "utf-16")
        ksoft.LoadFile(str(case.resolve()))
        anchor_key = changes[0][0] if changes else "m060.T"
        anchor = _getvar(ksoft, anchor_key)
        if not ksoft.CalculateRetVal():
            raise SystemExit(f"[{name}] CalculateRetVal=False（金样案须全部可算）")
        e = {v: _getvar(ksoft, v) for v in VARS}
        required = [v for v in VARS
                    if v not in ("m060.Trating", "m060.SFmin")]
        missing = [k for k in required if e[k] is None]
        if missing:
            raise SystemExit(f"[{name}] 结果变量为空：{missing}")
        _closure(name, e)
        cases[name] = {"file": _BASES[base],
                       "changes": [[k, str(v)] for k, v in changes],
                       "upserts": [[k, str(v)] for k, v in upserts.items()],
                       "anchor": [anchor_key, anchor],
                       "expect": e}
        print(f"[{name}] ok", flush=True)
    return cases


def _dat_rows() -> list[tuple[str, int, float, float, float, int, float]]:
    rows = []
    for ln in KS_DAT.read_text("ascii").splitlines():
        if not ln or ln.startswith("#"):
            continue
        name, z, D, d, tr, n, dl = (p.strip() for p in ln.split("|"))
        rows.append((name, int(z), float(D), float(d), float(tr),
                     int(n), float(dl)))
    if len(rows) != 99:
        raise SystemExit(f"M060-001.DAT 行数 {len(rows)} ≠ 99（DAT 实测 "
                         "99 数据行 + 1 单位行）")
    return rows


def _profile(ksoft) -> None:
    """Voith 目录 99 行快照（DAT 明文列 + 内核派生 r/s COM 读回）。"""
    text = (KS_EXAMPLE / _BASES["ex11"]).read_text("utf-16")
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for no, (name, z, D, d, tr, n, dl) in enumerate(_dat_rows(), start=1):
        t = text
        for key, val in (("m060.z", z), ("m060.D", D), ("m060.d", d),
                         ("m060.n", n), ("m060.dL", dl)):
            t = _setkey(t, key, val)
        case = CASES_DIR / f"m60_prof_{no:03d}.M60"
        case.write_text(t, "utf-16")
        ksoft.LoadFile(str(case.resolve()))
        if not ksoft.CalculateRetVal():
            raise SystemExit(f"[profile {name}] CalculateRetVal=False")
        r = _getvar(ksoft, "m060.r")
        s = _getvar(ksoft, "m060.s")
        if not r or not s or r <= 0 or s <= 0:
            raise SystemExit(f"[profile {name}] r/s 读回异常：{r!r}/{s!r}")
        out.append({"No": no, "Designation": name, "Z": z, "D": D, "DIn": d,
                    "T_Rating": tr, "N_Holes": n, "D_Hole": dl,
                    "R_Root": r, "S_Crown": s})
        print(f"[profile {no:03d}] {name} r=s? {abs(r - s) < 1e-12}", flush=True)
    PROFILE_CSV.parent.mkdir(parents=True, exist_ok=True)
    with PROFILE_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(out[0]))
        writer.writeheader()
        writer.writerows(out)
    print(f"written {PROFILE_CSV} ({len(out)} rows)")


def main() -> int:
    if "--examples" in sys.argv and "--golden" not in sys.argv \
            and "--profile" not in sys.argv:
        _examples()  # 纯 JSON→存档，无 COM
        return 0
    import win32com.client as client

    ksoft = client.Dispatch("KISSsoftCOM.KISSsoft")
    try:
        ksoft.SetSilentMode(True)
        ksoft.GetModule("M060", True)
        if "--profile" in sys.argv:
            _profile(ksoft)
            return 0
        cases = _harvest(ksoft)
    finally:
        try:
            ksoft.ReleaseModule()
        except Exception:
            pass
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(json.dumps({
        "source": "KISSsoft 2026 M060 official examples 11/12 + file variants "
                  "(COM GetVar, PyWin32, CalculateRetVal-gated, 2026-10-03)",
        "note": "单位口径：KISSsoft 存档 T 为 N·m、beta 为 rad（pyffalo 组件 "
                "内 T 为 N·mm 对账 ×1000、Beta 为 °）；Trating 存档 N·m（组件 "
                "T_rating 同单位）。公式链全闭式（spec hirth-serration-m60 实施记"
                "录；探针 P0~P2f 六轮 123+ 案逐位 ≤3.6e-15）：He/Hi=D/d·sin(π/z)/"
                "(2tanβ)（弦齿距）；Δ=s+2(1/sinβ−1)r；bk=tanβ(Δ+s)；G=z·l·"
                "(Hm/cosβ−bk/sinβ)；Az=G·(1−n·dL²/(D²−d²))（孔减面积比）；"
                "Fu=2T/dm、Fa=Fu·tanβ、Fva=ν·Fa；p[i]=(Fva+Fa)/(Az·ηz[i])；"
                "fS≡1.1、fH≡1.0（typ 全域常数）；plim=1.1·Rp（韧性）|1.1·Rm"
                "（脆性 typ==7）；fL=key_joint.f_l(NL, brittle=typ==7) 分侧；"
                "SF[i]=fL[i]·plim[i]/p[i]。判废面（复刻 check）：z≥8（z7 案废）、"
                "0<β<45°、D>d>0、ηz∈(0,1]（1.0 过、1.2/0 案废）、NL≥1、T>0、"
                "ν≥0（ν=0 合法 Fva=0）、有效几何 he>0∧hi>0∧Az>0（r 界 hi>0 绑定 "
                "r*=3.660003、s/D 界 Az>0 绑定——hm>s）。已知边界：目录档"
                "（ID=10010）β 锁 30°、r/s 按 m_i=d/z 内核分段表重导出（cat_D50 "
                "案 r≠s 且 s 疑似含 l 依赖，公式未反推→组件走 99 行快照表）；金样 "
                "cat_* 案以读回 r/s 自输复现（ID 不进计算，flip_own 案证）；"
                "m060.Trating 经 GetVar 恒 0（不入档，组件查 DAT 同源表）；目录档"
                "几何编辑（cat_z60 案内核重导 r/s）组件不建模——改几何须清 "
                "Designation 切自输。",
        "harvest": "python tools/gen_hirth_coupling_kisssoft.py",
        "cases": cases}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"written {GOLDEN} ({len(cases)} cases)")
    if "--examples" in sys.argv:
        _examples()
    return 0


def _examples() -> None:
    """金样 → examples/kisssoft/m060_hirth/ 全量 .pyffalo 镜像（无 COM）。

    组件重构复用金样测试 ``_component``（单源，勿复制粘贴漂移）；镜像与
    金样案集的漂移由 test_hirth_coupling 守护。
    """
    sys.path.insert(0, str(ROOT / "tests/unit"))
    import test_kisssoft_m60_golden as g

    mirror = ROOT / "examples/kisssoft/m060_hirth"
    mirror.mkdir(parents=True, exist_ok=True)
    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    for name, case in data["cases"].items():
        part = g._component(name, case)
        doc = {
            "format": "pyffalo-project", "version": 1,
            "pyffalo": "KISSsoft 2026 M060 镜像",
            "parts": [{"component": "HirthCoupling",
                       "input": part.input.model_dump(),
                       "params": part.params.model_dump(),
                       "baseline": part.baseline.model_dump()}],
            "assembly": {}, "robot": {}, "rotor": {}, "modelica": {},
            "groups": [], "parameters": [], "bindings": {},
        }
        (mirror / f"{name}.pyffalo").write_text(
            json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"written {mirror} ({len(data['cases'])} archives)")


if __name__ == "__main__":
    sys.exit(main())
