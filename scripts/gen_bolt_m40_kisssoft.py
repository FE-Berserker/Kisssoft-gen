"""M40 螺栓 KISSsoft 金样收割机（官方七例 → tests/golden/bolt/）。

骨架照 gen_plain_journal_kisssoft.py：SetSilentMode + GetModule("M040")
+ LoadFile 官方原档 + CalculateRetVal fail-fast（False 即 SystemExit，
不覆盖旧金样）+ GetVar 逐变量 + finally ReleaseModule。

口径（对账 2026-10-02 钉死，详见 docs/specs/bolt-kisssoft-m40.md）：
- 结果键几乎全不落盘（算例文件只缓存 ~10 个 m04r 量），必须 COM GetVar。
- 变量名权威来源：rpt/M040Le0.RPT 花括号名录。
- m04r.FM ↔ pyffalo FMmax（拧紧达到值）；m04r.FMmin/FMmax 是「需求
  装配预紧力」（R7/R8 口径），与 pyffalo 的能力口径语义不同，仅记录。
- konfig.art/wahl 七例均不落盘（预紧定义方式文件不可改）。
- KISSsoft 的 m04t.lk 不含垫圈厚度（lkEff 才是含垫圈修正值）。

用法（需本机 KISSsoft 2026 + license）::

    python tools/gen_bolt_m40_kisssoft.py
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GOLDEN = REPO / "tests" / "golden" / "bolt" / "kisssoft_m40.json"
KISS_EXAMPLE = Path("C:/KISSsoft 2026/example")

#: (官方文件名, 金样案名, 对标范围)
CASES = (
    ("01 Bolts (VDI 2230 Example 1).M40", "vdi_ex1", "full"),
    ("02 Bolts (VDI 2230 Example 2).M40", "vdi_ex2_flange", "record"),
    ("03 Bolts (VDI 2230 Example 3).M40", "vdi_ex3_hollow", "deltap"),
    ("04 Bolts (VDI 2230 Example 4).M40", "vdi_ex4_bending", "record"),
    ("05 Bolts (VDI 2230 Example 5).M40", "vdi_ex5_annular", "deltap"),
    ("06 Bolts (Flange Connection).M40", "flange_conn", "deltap"),
    ("07 Bolts (High Temperature).M40", "high_temp_300c", "deltap"),
)

#: 输入锚键（读回入金样 input 层，供测试复刻与漂移检查）
_INPUT_VARS = (
    "m04g.bez", "m04g.d", "m04g.P", "m04g.A0",
    "m04s.l", "m04s.l1", "m04s.lGW", "m04s.dw", "m04s.da", "m04s.di",
    "m04s.Re", "m04s.Rm", "m04s.E", "m04s.ETemp", "m04s.ReTemp",
    "m04t.lk", "m04t.lkEff", "m04t.DA", "m04t.DA_s", "m04t.dh",
    "m04t.hi[0]", "m04t.hi[1]", "m04t.hi[2]", "m04t.maxPlatte",
    "m04mat.mat[0].E", "m04mat.mat[0].pzul", "m04mat.mat[1].E",
    "m04u.s[0]", "m04u.d2[0]", "m04u.s[1]", "m04u.d2[1]",
    "m04m.d2", "m04m.m", "m04s.u",
    "m04my.G", "m04my.K", "m04alpha.A",
    "m04n.SVwahl", "m04n.ak", "m04n.lA", "m04n.wert",
    "m04f.AO", "m04f.AU", "m04f.Q", "m04f.BetrTempSchraube",
    "m04f.BetrTempTeile",
    "m04konfig.n", "m04konfig.d", "m04konfig.Mt", "m04konfig.Mb",
    "m04konfig.my", "m04konfig.ra",
)

#: 结果变量（M040Le0.RPT 名录核对）
_RESULT_VARS = (
    "m04t.delta", "m04s.delta", "m04s.phin", "m04s.phien", "m04n.wert",
    "m04t.DAGr", "m04t.deltapx", "m04t.deltazu",
    "m04r.FM", "m04r.FMmin", "m04r.FMmax", "m04r.Fz",
    "m04r.SF", "m04r.SD", "m04r.SG", "m04r.SA", "m04r.SP", "m04r.SEngage",
    "m04s.MG", "m04r.MA", "m04r.MA_sp", "m04r.MLOS",
    "m04r.sigAzul", "m04r.siga", "m04r.ND",
    "m04s.FSmax", "m04s.sigmaredB", "m04s.sigmaz", "m04s.taus",
    "m04r.pK", "m04r.pM", "m04r.pKzul", "m04r.mges", "m04r.meff",
    "m04r.fzSetz", "m04r.streck", "m04r.kv", "m04r.checkdeltapzu",
    "m04r.calcmeff", "m04konfig.art", "m04konfig.wahl",
)


def _getvar(ks, name: str):
    """GetVar 归一：异常/空 → None；数值转 float；其余保留字符串。"""
    try:
        raw = ks.GetVar(name)
    except Exception:
        return None
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return s


def main() -> None:
    import win32com.client as client  # 函数体内 import：无 COM 环境可收集

    ks = client.Dispatch("KISSsoftCOM.KISSsoft")
    ks.SetSilentMode(True)
    ks.GetModule("M040", True)
    cases: dict[str, dict] = {}
    try:
        for fname, name, scope in CASES:
            ks.LoadFile(str(KISS_EXAMPLE / fname))
            anchor = _getvar(ks, "m04g.bez")
            if not anchor:
                raise SystemExit(f"锚键失败 m04g.bez（{fname} 未载入？），金样保持原样")
            rv = ks.CalculateRetVal()
            if not rv:
                raise SystemExit(f"CalculateRetVal=False（{fname}），金样保持原样")
            row = {"file": fname, "scope": scope,
                   "input": {k: _getvar(ks, k) for k in _INPUT_VARS},
                   "expect": {k: _getvar(ks, k) for k in _RESULT_VARS}}
            cases[name] = row
            print(f"[{name:16s}] δP={row['expect']['m04t.delta']:.6e} "
                  f"Φ={row['expect']['m04s.phin']:.6f} "
                  f"FM={row['expect']['m04r.FM']:.2f} "
                  f"SF={row['expect']['m04r.SF']:.4f} SD={row['expect']['m04r.SD']:.4f}",
                  flush=True)
    finally:
        try:
            ks.ReleaseModule()
        except Exception:
            pass

    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(json.dumps({
        "source": "KISSsoft 2026 M40 COM GetVar 逐变量收割（2026-10-02；"
                  "官方算例 01-07 原文件）",
        "note": "单位：几何 mm、力 N、力矩 N·m（m04 命名空间）、应力 MPa、"
                "柔度 mm/N。m04r.FM ↔ pyffalo FMmax（拧紧达到值）；"
                "m04r.FMmin/FMmax 是需求装配预紧力（R7/R8），仅记录。"
                "scope：full=全链对标；deltap=仅 δP 直构对标；record=仅入库"
                "（多栓折算/弯曲体/高温链为 pyffalo 范围外）。",
        "cases": cases,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nsaved {len(cases)} cases -> {GOLDEN}")


if __name__ == "__main__":
    main()
