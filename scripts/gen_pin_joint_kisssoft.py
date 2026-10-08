"""PinJoint（KISSsoft M3A）金样收割器。

幂等重跑：官方算例 08 Pins.M3A + 文件变体（UTF-16 ``key=value¶`` 行尾、锚定
行首替换、末行无 ¶ 兼容、绝对路径 LoadFile）→ ``CalculateRetVal`` 唯一判据 →
``GetVar`` 全变量收割；全部案通过健全性过滤后一次性写
``tests/golden/pin_joint/kisssoft_m3a.json``（失败不覆盖旧档）。

COM 形态照 ``gen_clamp_connection_kisssoft.py``。公式链口径见
``docs/specs/pin-joint-m3a.md``「背景口径」。反直觉发现（详见 spec）：
- cd/ck/ckp/dn/sb 均为派生快照（文件值惰性）；
- 弹簧销 × 纯剪构型（verbind∈{0,1,4}）belast 被内核钳为静载（回显即 0），
  销剪许用切 Fzul 路线 τzul = Fzul_{matStift}·1000/(2·as)；
- 弹簧销 W = 0.9994930426171028·π·sb·(d−sb)²/4（薄环式内核常数）；
- v1 的 as 内核 quirk：d·ls/2（实心/槽销）/ sb·ls/2（弹簧销）；
- v2 弯矩杠杆是 lb（RPT 备注写 s 为笔误）；v3 einbau=1 弯矩 F·ts/12；
- NormID<10020 任意值静默按实心销算（回落带，见证案 norm10011）。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pyffalo_root

ROOT = pyffalo_root.repo_root()
sys.path.insert(0, str(ROOT / "src"))

KS_EXAMPLE = Path(r"C:\KISSsoft 2026\example")
CASES_DIR = ROOT / "tmp" / "m3a_harvest_cases"
GOLDEN = ROOT / "tests" / "golden" / "pin_joint" / "kisssoft_m3a.json"

#: 官方算例基座（唯一 .M3A 算例）
_BASES = {"ex08": "08 Pins.M3A"}

V4 = [("m03a.verbind", 4), ("m03a.Tn", 1000), ("m03a.nb", 4),
      ("m03a.dcirc", 100), ("m03a.t1", 10), ("m03a.t2", 12)]

#: 案集（name, base, changes）——覆盖矩阵：五构型基座与单因子 / einbau 弯矩
#: 三式 / belast×销类 cd 双表 / own-input 材料 / 弹簧销五型清点与 d 扫描 /
#: Fzul 双路线（matStift 分支）/ 惰性见证（SollSi、matStift 实心、NormID
#: 回落带）/ NEXT_BIGGER 上下界。
CASES: list[tuple[str, str, list[tuple[str, object]]]] = [
    # ---- v3 双剪螺栓基座 + 单因子 ----
    ("ex08", "ex08", []),
    ("v3_d10", "ex08", [("m03a.d", 10)]),
    ("v3_ts12", "ex08", [("m03a.ts", 12)]),
    ("v3_tg10", "ex08", [("m03a.tg", 10)]),
    ("v3_ka15", "ex08", [("m03a.ka", 1.5)]),
    ("v3_f3000", "ex08", [("m03a.F", 3000)]),
    # ---- einbau 弯矩三式 ----
    ("v3_eb0", "ex08", [("m03a.einbau", 0)]),
    ("v3_eb1", "ex08", [("m03a.einbau", 1)]),
    ("v3_eb1_ts20_tg12", "ex08", [("m03a.einbau", 1), ("m03a.ts", 20),
                                  ("m03a.tg", 12)]),
    ("v3_eb0_ts20_tg5", "ex08", [("m03a.einbau", 0), ("m03a.ts", 20),
                                 ("m03a.tg", 5)]),
    # ---- belast × cd（实心）----
    ("v3_belast0", "ex08", [("m03a.belast", 0)]),
    ("v3_belast2", "ex08", [("m03a.belast", 2)]),
    # ---- own-input 材料（DBID=19999 快照权威）----
    ("own_pin", "ex08", [("m03ab.mat.DBID", 19999), ("m03ab.mat.Rm", 800)]),
    ("own_rod", "ex08", [("m03aw.mat.DBID", 19999), ("m03aw.mat.Rm", 600)]),
    ("own_fork", "ex08", [("m03an.mat.DBID", 19999), ("m03an.mat.Rm", 300)]),
    # ---- 惰性见证 ----
    ("witness_sollsi", "ex08", [("m03a.SollSi_taub", 2)]),
    ("witness_tn_v3", "ex08", [("m03a.Tn", 500)]),
    ("witness_norm10011", "ex08", [("m03a.NormID", 10011)]),
    ("witness_matstift_solid", "ex08", [("m03a.matStift", 1)]),
    # ---- v0 横销受扭 ----
    ("v0_base", "ex08", [("m03a.verbind", 0), ("m03a.Tn", 500)]),
    ("v0_dw20", "ex08", [("m03a.verbind", 0), ("m03a.Tn", 500),
                         ("m03a.dw", 20)]),
    ("v0_sn5", "ex08", [("m03a.verbind", 0), ("m03a.Tn", 500),
                        ("m03a.sn", 5)]),
    ("v0_dw20_sn6", "ex08", [("m03a.verbind", 0), ("m03a.Tn", 500),
                             ("m03a.dw", 20), ("m03a.sn", 6),
                             ("m03a.dn", 99)]),
    ("v0_d10", "ex08", [("m03a.verbind", 0), ("m03a.Tn", 500),
                        ("m03a.d", 10)]),
    # ---- v1 纵销受扭 ----
    ("v1_base", "ex08", [("m03a.verbind", 1), ("m03a.Tn", 500)]),
    ("v1_ls15", "ex08", [("m03a.verbind", 1), ("m03a.Tn", 500),
                         ("m03a.ls", 15)]),
    ("v1_d6_ls20", "ex08", [("m03a.verbind", 1), ("m03a.Tn", 500),
                            ("m03a.d", 6), ("m03a.ls", 20)]),
    # ---- v2 导向销受弯 ----
    ("v2_base", "ex08", [("m03a.verbind", 2)]),
    ("v2_s15", "ex08", [("m03a.verbind", 2), ("m03a.s", 15)]),
    ("v2_lb20", "ex08", [("m03a.verbind", 2), ("m03a.lb", 20)]),
    ("v2_s5_lb15", "ex08", [("m03a.verbind", 2), ("m03a.s", 5),
                            ("m03a.lb", 15)]),
    ("v2_f3000", "ex08", [("m03a.verbind", 2), ("m03a.F", 3000)]),
    # ---- v4 环形单剪 ----
    ("v4_base", "ex08", V4),
    ("v4_nb6", "ex08", V4 + [("m03a.nb", 6)]),
    ("v4_dc150", "ex08", V4 + [("m03a.dcirc", 150)]),
    ("v4_t1_8", "ex08", V4 + [("m03a.t1", 8)]),
    ("v4_d10", "ex08", V4 + [("m03a.d", 10)]),
    # ---- 圆头槽销（ck/ckp 派生 0.7/0.8）----
    ("grv_v3", "ex08", [("m03a.NormID", 10020)]),
    ("grv_belast0", "ex08", [("m03a.NormID", 10020), ("m03a.belast", 0)]),
    ("grv_v2", "ex08", [("m03a.NormID", 10020), ("m03a.verbind", 2)]),
    ("grv_v0", "ex08", [("m03a.NormID", 10020), ("m03a.verbind", 0),
                        ("m03a.Tn", 500)]),
    ("grv_v4", "ex08", [("m03a.NormID", 10020)] + V4),
    # ---- 弹簧销 001 卷制重型：基座 / d 扫 / belast ----
    ("sp_base", "ex08", [("m03a.NormID", 10030)]),
    ("sp_d3", "ex08", [("m03a.NormID", 10030), ("m03a.d", 3)]),
    ("sp_d6", "ex08", [("m03a.NormID", 10030), ("m03a.d", 6)]),
    ("sp_d10", "ex08", [("m03a.NormID", 10030), ("m03a.d", 10)]),
    ("sp_d16", "ex08", [("m03a.NormID", 10030), ("m03a.d", 16)]),
    ("sp_d20", "ex08", [("m03a.NormID", 10030), ("m03a.d", 20)]),
    ("sp_d7", "ex08", [("m03a.NormID", 10030), ("m03a.d", 7)]),
    ("sp_d1", "ex08", [("m03a.NormID", 10030), ("m03a.d", 1)]),
    ("sp_belast0", "ex08", [("m03a.NormID", 10030), ("m03a.belast", 0)]),
    ("sp_belast2", "ex08", [("m03a.NormID", 10030), ("m03a.belast", 2)]),
    # ---- 弹簧销其余四型 @d=8 + 少量 d 扫 ----
    ("sp40_d8", "ex08", [("m03a.NormID", 10040)]),
    ("sp40_d20", "ex08", [("m03a.NormID", 10040), ("m03a.d", 20)]),
    ("sp50_d8", "ex08", [("m03a.NormID", 10050)]),
    ("sp50_d2", "ex08", [("m03a.NormID", 10050), ("m03a.d", 2)]),
    ("sp60_d8", "ex08", [("m03a.NormID", 10060)]),
    ("sp60_d12", "ex08", [("m03a.NormID", 10060), ("m03a.d", 12)]),
    ("sp70_d8", "ex08", [("m03a.NormID", 10070)]),
    ("sp70_d20", "ex08", [("m03a.NormID", 10070), ("m03a.d", 20)]),
    # ---- 弹簧销弯曲构型（dat 路线 ×cd_spring）----
    ("sp_v2", "ex08", [("m03a.NormID", 10030), ("m03a.verbind", 2)]),
    ("sp_v2_belast2", "ex08", [("m03a.NormID", 10030), ("m03a.verbind", 2),
                               ("m03a.belast", 2)]),
    # ---- 弹簧销纯剪构型（强制静载 + Fzul 路线 + matStift 分支）----
    ("sp_v0", "ex08", [("m03a.NormID", 10030), ("m03a.verbind", 0),
                       ("m03a.Tn", 500)]),
    ("sp_v0_ms1", "ex08", [("m03a.NormID", 10030), ("m03a.verbind", 0),
                           ("m03a.Tn", 500), ("m03a.matStift", 1)]),
    ("sp_v1", "ex08", [("m03a.NormID", 10030), ("m03a.verbind", 1),
                       ("m03a.Tn", 500)]),
    ("sp_v4", "ex08", [("m03a.NormID", 10030)] + V4),
    ("sp_v4_ms1", "ex08", [("m03a.NormID", 10030), ("m03a.matStift", 1)] + V4),
    ("sp_v4_belast2", "ex08", [("m03a.NormID", 10030), ("m03a.belast", 2)] + V4),
    ("sp40_v4", "ex08", [("m03a.NormID", 10040)] + V4),
]

#: 收割变量名录（KVAR 36 条 + RPT 花括号集 + 控制枚举回显）
VARS = [
    "m03a.verbind", "m03a.einbau", "m03a.belast", "m03a.matStift",
    "m03a.NormID", "m03a.NormName",
    "m03a.cd", "m03a.ck", "m03a.ckp", "m03a.d", "m03a.F", "m03a.Tn",
    "m03a.ka", "m03a.tg", "m03a.ts", "m03a.t1", "m03a.t2", "m03a.ls",
    "m03a.lb", "m03a.dn", "m03a.dw", "m03a.dcirc", "m03a.sn", "m03a.s",
    "m03a.sb", "m03a.nb",
    "m03a.faktp", "m03a.faktsigma", "m03a.fakttau",
    "m03a.SollSi_pb", "m03a.SollSi_taub", "m03a.SollSi_sigmab",
    "m03a.SollSi_pw", "m03a.SollSi_pn",
    "m03ab.mat.DBID", "m03ab.mat.bez", "m03ab.mat.Rm",
    "m03aw.mat.DBID", "m03aw.mat.bez", "m03aw.mat.Rm",
    "m03an.mat.DBID", "m03an.mat.bez", "m03an.mat.Rm",
    "m03a.mb", "m03a.taub", "m03a.w", "m03a.pn", "m03a.pw", "m03a.pb",
    "m03a.pd", "m03a.pmb",
    "m03a.pzulw", "m03a.pzuln", "m03a.pzulb", "m03a.tauzulb",
    "m03a.sigmazulb",
    "m03a.sigmab", "m03a.as", "m03a.ss1", "m03a.ss2", "m03a.ss3",
    "m03a.sw1", "m03a.sn1",
    "m03a.Fzul1", "m03a.Fzul2", "m03a.Fp",
]


def _setkey(text: str, key: str, val) -> str:
    """锚定行首替换（末行无 ¶ 兼容；命中数 ≠1 即废）。"""
    pat = re.compile(rf"^{re.escape(key)}=[^¶\r\n]*", re.MULTILINE)
    n = len(pat.findall(text))
    if n != 1:
        raise SystemExit(f"变体键 {key} 替换 {n} 处（应为 1）")
    return pat.sub(lambda _m: f"{key}={val}", text, count=1)


def _getvar(ksoft, name: str):
    """COM 变量归一化：异常 / None / 空串 → None；数值串 → float。"""
    try:
        raw = ksoft.GetVar(name)
    except Exception:
        return None
    if raw is None or raw == "":
        return None
    s = str(raw).rstrip("\u00b6").strip()
    try:
        return float(s)
    except ValueError:
        return s


#: 健全性必查（结果量缺一即废）
_REQUIRED = ("m03a.as", "m03a.taub", "m03a.pw", "m03a.pn", "m03a.pzulw",
             "m03a.pzuln", "m03a.pzulb", "m03a.tauzulb", "m03a.sigmazulb",
             "m03a.ss2", "m03a.sw1")


def main() -> int:
    import win32com.client as client

    texts = {n: (KS_EXAMPLE / f).read_text("utf-16")
             for n, f in _BASES.items()}
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    ksoft = client.Dispatch("KISSsoftCOM.KISSsoft")
    cases: dict[str, dict] = {}
    try:
        ksoft.SetSilentMode(True)
        ksoft.GetModule("M03A", True)
        for idx, (name, base, changes) in enumerate(CASES, start=1):
            t = texts[base]
            for key, val in changes:
                t = _setkey(t, key, val)
            case = CASES_DIR / f"m3a_{idx:03d}_{name}.M3A"
            case.write_text(t, "utf-16")
            ksoft.LoadFile(str(case))
            ok = ksoft.CalculateRetVal()
            if not ok:
                raise SystemExit(f"[{name}] CalculateRetVal=False（金样案须全部可算）")
            expect = {v: _getvar(ksoft, v) for v in VARS}
            for key in _REQUIRED:
                if expect[key] is None:
                    raise SystemExit(f"[{name}] 结果变量 {key} 为空")
            cases[name] = {"file": _BASES[base],
                           "changes": [[k, v] for k, v in changes],
                           "expect": expect}
            print(f"[{idx:02d}/{len(CASES)}] {name}: v={expect['m03a.verbind']:g} "
                  f"tau={expect['m03a.taub']:.6g} tauzul={expect['m03a.tauzulb']:.6g} "
                  f"ss2={expect['m03a.ss2']:.6g}")
    finally:
        try:
            ksoft.ReleaseModule()
        except Exception:
            pass  # noqa: S110 —— 释放失败不带走收割结果
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(json.dumps({
        "source": "KISSsoft 2026 M03A official example 08 Pins + file variants "
                  "(COM GetVar, CalculateRetVal-gated), 2026-10-08",
        "note": "单位：几何 mm、力 N、扭矩 Tn 为 N·m（组件内 Tn 为 N·mm，测试映射 ×1000）、"
                "mb 为 N·mm、Fzul 为 kN。cd/ck/ckp/dn/sb 均为派生快照（文件值惰性）；"
                "belast 0/1/2 = 静/交变/脉动，cd 实心槽销 {1.0/0.5/0.7}、弹簧销 {1.0/0.375/0.75}；"
                "弹簧销 × 纯剪构型（verbind∈{0,1,4}）belast 内核钳为静载（回显 0）且销剪许用走 "
                "Fzul 路线 τzul = Fzul_{matStift}·1000/(2·as)（不乘 cd）；"
                "v1 的 as = d·ls/2（实心/槽销）/ sb·ls/2（弹簧销，内核 quirk）、W 恒 0；"
                "v2 弯矩杠杆 lb（RPT 备注 s 为笔误）；v3 einbau∈{0,1,2} 弯矩 "
                "F·(ts+tg)/4 / F·ts/12 / F·tg/4；v0 毂径 dn = dw+2·sn 派生"
                "（文件值惰性）、p_b = 4·Tn·KA/(d·(dn²−dw²))；"
                "v1 弹簧销 sigmazulb=190 为内核孤立怪值（v1 无弯曲不消费，测试跳过该量）；"
                "NormID<10020 任意值静默按实心销算（回落带，witness_norm10011 见证，"
                "测试映射 <10020 → 10010）。",
        "harvest": "python tools/gen_pin_joint_kisssoft.py",
        "cases": cases,
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"金样落盘：{GOLDEN}（{len(cases)} 案）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
