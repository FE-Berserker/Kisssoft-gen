"""KISSsoft M2A 平键官方算例金样收割 + Kλ 三维曲面 COM 扫描 + DIN 6885 剖面快照。

三件事（对应 docs/specs/key-joint-m2a.md）：

1. ``harvest()``（默认）：对 3 个官方算例（08/09/10 Keys DIN 6892 Example 1-3.M2A）
   经 KISSsoftCOM 计算并 GetVar 全量变量，写
   ``tests/golden/key_joint/kisssoft_m2a.json`` 供
   ``tests/unit/test_kisssoft_m2a_golden.py`` 逐位对账（全链闭式复现，1e-9 档）。
2. ``--scan-klambda``：Kλ（内核「Lastverteilungsfaktor」，Niemann 图版数据）是
   (l_tr/d_w, D/d_w, a0/l_tr) 三维分段线性曲面（探针 6 因子化检验否定降维：
   a0 修正量在 D=150/200/300 下分别为 +0.0266/+0.0093/+0.0012），a0≥l_tr 钳位、
   D≥3d_w 饱和。以算例 1 为基座（载荷/材料对 Kλ 零影响，探针 3 钉死）扫
   16×7×6=672 点（iANZ=1/2 两面）入 ``tools/data/key_joint/klambda_scan.json.gz``，
   ``tools/gen_key_joint_seeds.py`` 据此建 ``Key_Joint_KLambda`` 表，
   ``pyffalo.data.key_joint.klambda()`` 三线性插值。三官方算例坐标
   (93/120, 200/120, 1.0)、(91/60, 120/60, 55/91)、(163/210, 569.5/210, 84.5/163)
   恰在轴节点上 → 金样逐位。
3. ``--profile``：解析随包 ``dat/M02A-001.DAT``（DIN 6885.1:1968 剖面表，26 行，
   d=8..500；t1.max/t2.max 列是公差带宽不是槽深）入
   ``tools/data/key_joint/din6885_profile.csv``，seed 建 ``Key_Profile`` 表
   （NEXT_BIGGER：取 DMax ≥ d 的首行）。

COM 形态（Z92/W070 扫描机同款）：``SetSilentMode(True)`` + ``GetModule("M02A",
True)`` + 文件变体（UTF-16 明文 ``key=value¶`` 行替换）+ ``LoadFile`` +
``CalculateRetVal()`` 唯一可信判据 + ``GetVar`` + ``ReleaseModule``。**PowerShell
版探针不可信**（同值 no-op 变体静默判废全零，见 docs/KISSSOFT.md M2A 专项段）。

用法::

    python scripts/gen_key_joint_kisssoft.py               # 金样收割
    python scripts/gen_key_joint_kisssoft.py --scan-klambda
    python scripts/gen_key_joint_kisssoft.py --profile
"""

from __future__ import annotations

import csv
import gzip
import json
import re
import sys
from pathlib import Path

import pyffalo_root

REPO = pyffalo_root.repo_root()
GOLDEN = REPO / "tests/golden/key_joint/kisssoft_m2a.json"
SCAN_OUT = REPO / "tools/data/key_joint/klambda_scan.json.gz"
PROFILE_CSV = REPO / "tools/data/key_joint/din6885_profile.csv"
KISS_DAT = Path("C:/KISSsoft 2026/dat/M02A-001.DAT")
CASES_DIR = REPO / "tmp/m2a_harvest_cases"

#: 官方算例 → 金样案名（M2A 文件在 KISSsoft 安装目录，不入库）
KISS_EXAMPLE = Path("C:/KISSsoft 2026/example")
CASES = [
    ("08 Keys (DIN 6892 Example 1).M2A", "din6892_ex1", []),
    ("09 Keys (DIN 6892 Example 2).M2A", "din6892_ex2", []),
    ("10 Keys (DIN 6892 Example 3).M2A", "din6892_ex3", []),
    # 质量门 CR13：三官方算例剪切轨均不绑定，补一例极端窄键档（b=3，
    # 毂侧 htN 缩到 2.5 → 挤压轨 S=0.934 控制且**两侧一致**——b=1.5/2 探针
    # 证实内核剪切轨恒不绑定（implied tau_zul ≥762@Rp=800），真实内核式
    # 不可反推，组件取 DIN von Mises R_p/√3（保守，见 spec 已知边界））
    ("09 Keys (DIN 6892 Example 2).M2A", "din6892_ex2_narrow_key",
     [("m02Ak.b", 3), ("m02Ak.bKeil", 3)]),
]

#: 收割变量（报告模板 M02ALe0.RPT 花括号名录 + 输入回显；缺失记 null）
HARVEST_VARS = [
    # 全局载荷与系数
    "m02Aa.Methode", "m02Aa.MomArt", "m02Aa.Mnenn", "m02Aa.Mmax", "m02Aa.Meq",
    "m02Aa.TRmin", "m02Aa.TmaxRuck", "m02Aa.NL", "m02Aa.NW",
    "m02Aa.iANZ", "m02Aa.ieff", "m02Aa.phiFak", "m02Aa.StossFak",
    "m02Aa.Feq", "m02Aa.Fmax", "m02Aa.Knueq", "m02Aa.Knumax",
    "m02Aa.KReq", "m02Aa.KR", "m02Aa.fw", "m02Aa.Klamda",
    # 轴侧（Welle）
    "m02Aw.dWa", "m02Aw.lW", "m02Aw.htW", "m02Aw.s1",
    "m02Aw.fs", "m02Aw.fH", "m02Aw.peq", "m02Aw.pmax", "m02Aw.pzul", "m02Aw.fL",
    "m02Aw.Resulteq", "m02Aw.Resultmax", "m02Aw.ResultW",
    "m02Aw.mat.Rp", "m02Aw.mat.Rm", "m02Aw.mat.typ", "m02Aw.mat.behandlung",
    # 毂侧（Nabe）
    "m02An.lN", "m02An.htN", "m02An.s2", "m02An.D1", "m02An.a0", "m02An.D",
    "m02An.fs", "m02An.fH", "m02An.peq", "m02An.pmax", "m02An.pzul", "m02An.fL",
    "m02An.Resulteq", "m02An.Resultmax", "m02An.ResultN",
    "m02An.mat.Rp", "m02An.mat.Rm", "m02An.mat.typ", "m02An.mat.behandlung",
    # 键（Keil）
    "m02Ak.b", "m02Ak.h", "m02Ak.d", "m02Ak.r1MaxK",
    "m02Ak.t1.min", "m02Ak.t2.min",
    "m02Ak.fs", "m02Ak.fH", "m02Ak.pzul", "m02Ak.fL",
    "m02Ak.Resulteq", "m02Ak.Resultmax", "m02Ak.ResultP", "m02Ak.tauKeil",
    "m02Ak.mat.Rp", "m02Ak.mat.Rm", "m02Ak.mat.typ", "m02Ak.mat.behandlung",
]

#: Kλ 扫描网格（l/d_w × D/d_w × a0/l_tr；基座=算例 1，d_w=120 固定）。
#: D 轴从 150 起步——D/d_w ≤ 1.1（毂壁 (D−d)/2 ≤ 0.05·d）内核整列判废
#: （扫描实测 192 点全落在这两列，物理上即无毂材料可变形）。
SCAN_D_W = 120.0
SCAN_L = [36, 48, 60, 72, 84, 93, 108, 120, 132, 144, 168, 192, 216, 240, 264, 288]
SCAN_D = [150, 180, 200, 240, 300, 360, 480]
SCAN_A0F = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
#: 官方算例锚点（比值三元组 l/d_w, D/d_w, a0/l_tr）——不在网格轴节点上，
#: 换算到基座绝对尺寸单独补扫，保证金样逐位；同时验证 Kλ 纯为三比值
#: 函数（补扫值须等于算例原生 Kλ：ex2→1.3328241758、ex3→1.0951942740）。
SCAN_EXTRA_RATIOS = [
    ("din6892_ex2", 91 / 60, 120 / 60, 55 / 91),
    ("din6892_ex3", 163 / 210, 569.5 / 210, 84.5 / 163),
]
SCAN_BASE = KISS_EXAMPLE / "08 Keys (DIN 6892 Example 1).M2A"

_PROFILE_ROW = re.compile(
    r"^\s*(\d+(?:\.\d*)?)\s+(\d+(?:\.\d*)?)\s+(\d+(?:\.\d*)?)\s+"
    r"(\d+(?:\.\d*)?)\s+(\d+(?:\.\d*)?)\s+(\d+(?:\.\d*)?)\s+"
    r"(\d+(?:\.\d*)?)\s+(\d+(?:\.\d*)?)\s+(\d+(?:\.\d*)?)\s+(\d+(?:\.\d*)?)\s*$")


def _setkey(text: str, key: str, val) -> str:
    """文件变体单键改写（锚定行首；¶ 为 KISSsoft 存档行分隔符 U+00B6）。

    repl 用 lambda 隔离：值含 ``\\g``/``\\1`` 类反斜杠序列时不会被
    re.sub 当组引用解析（当前调用点全为数值，防患于未然）。
    """
    out, n = re.subn(rf"^{re.escape(key)}=[^¶]*¶",
                     lambda _m, key=key, val=val: f"{key}={val}¶",
                     text, flags=re.MULTILINE)
    if n != 1:
        raise SystemExit(f"M2A 变体键改写失败 {key}={val}（命中 {n} 处）")
    return out


def _getvar(ksoft, var: str):
    """GetVar 兜底：COM 变体类型不稳（数值偶发字符串形态），统一转 float。"""
    try:
        val = ksoft.GetVar(var)
    except Exception:  # noqa: BLE001 — 变量在该方法/构型下不存在属正常
        return None
    if isinstance(val, str):
        try:
            return float(val)
        except ValueError:
            return val or None
    return val


def harvest() -> int:
    """三官方算例全变量收割 → tests/golden/key_joint/kisssoft_m2a.json。"""
    import win32com.client as client

    CASES_DIR.mkdir(parents=True, exist_ok=True)
    cases: dict[str, dict] = {}
    ksoft = client.Dispatch("KISSsoftCOM.KISSsoft")
    try:
        ksoft.SetSilentMode(True)
        ksoft.GetModule("M02A", True)
        for i, (fname, name, changes) in enumerate(CASES):
            src = KISS_EXAMPLE / fname
            text = src.read_text("utf-16")
            for key, val in changes:
                text = _setkey(text, key, val)
            # 就地复制算例到 tmp 再 LoadFile（保持原始文件零改动）
            local = CASES_DIR / f"golden_{i:02d}.M2A"
            local.write_text(text, "utf-16")
            ksoft.LoadFile(str(local))
            if not ksoft.CalculateRetVal():
                raise SystemExit(f"{fname}: CalculateRetVal=False")
            expect = {v: _getvar(ksoft, v) for v in HARVEST_VARS}
            missing = [v for v, x in expect.items() if x is None]
            if missing:
                raise SystemExit(f"{fname}: 变量缺失 {missing}")
            cases[name] = {"file": fname, "expect": expect}
            print(f"{name}: {len(expect)} 变量", flush=True)
    finally:
        try:
            ksoft.ReleaseModule()
        except Exception:  # noqa: BLE001, S110
            pass
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(json.dumps({
        "source": "KISSsoft 2026 M02A official examples 08/09/10 (DIN 6892), COM GetVar",
        "note": "torque Nm; lengths mm; pressure/strength N/mm²; safeties dimensionless. "
                "t1/t2 = profile t1.min/t2.min (Nuttiefe Minimalwert); r1 = m02Ak.r1MaxK.",
        "harvest": "python tools/gen_key_joint_kisssoft.py",
        "cases": cases,
    }, ensure_ascii=False, indent=1), "utf-8")
    print(f"→ {GOLDEN}")
    return 0


def scan_klambda() -> int:
    """Kλ 三维曲面扫描（iANZ=1/2 两个键数面）→ klambda_scan.json.gz。

    双键面为独立曲面（探针：Kλ₂/Kλ₁ 比值 1.03~1.19 随 l/d 与 D 变化，
    非常数偏移），两遍各 672 点。官方算例全为单键（锚点在 iANZ=1 面）。
    """
    import win32com.client as client

    CASES_DIR.mkdir(parents=True, exist_ok=True)
    base_text = SCAN_BASE.read_text("utf-16")
    points: list[dict] = []
    failed: list[dict] = []
    ksoft = client.Dispatch("KISSsoftCOM.KISSsoft")
    try:
        ksoft.SetSilentMode(True)
        ksoft.GetModule("M02A", True)
        n_total = 2 * len(SCAN_L) * len(SCAN_D) * len(SCAN_A0F)
        n = 0
        for ianz in (1, 2):
            for l_tr in SCAN_L:
                for d_hub in SCAN_D:
                    for a0f in SCAN_A0F:
                        n += 1
                        a0 = round(a0f * l_tr, 6)
                        t = base_text
                        for key, val in (("m02Aa.iANZ", ianz),
                                         ("m02Aw.lW", l_tr), ("m02An.lN", l_tr),
                                         ("m02An.D1", d_hub), ("m02An.D2", d_hub),
                                         ("m02An.a0", a0)):
                            t = _setkey(t, key, val)
                        case = CASES_DIR / f"kl{ianz}_{l_tr:g}_{d_hub:g}_{a0f:g}.M2A"
                        case.write_text(t, "utf-16")
                        ksoft.LoadFile(str(case))
                        if not ksoft.CalculateRetVal():
                            failed.append({"keys": ianz, "l": l_tr, "D": d_hub, "a0": a0})
                            continue
                        kl = _getvar(ksoft, "m02Aa.Klamda")
                        peq = _getvar(ksoft, "m02Aw.peq")
                        if kl is None or kl <= 0:
                            failed.append({"keys": ianz, "l": l_tr, "D": d_hub, "a0": a0})
                            continue
                        points.append({"keys": ianz, "l": l_tr, "D": d_hub,
                                       "a0f": a0f, "KLamda": kl, "peq_w": peq})
                        if n % 120 == 0:
                            print(f"  {n}/{n_total} …", flush=True)
        # 官方算例锚点补扫（比值 → 基座绝对尺寸；单键面）
        for name, lod, dod, aol in SCAN_EXTRA_RATIOS:
            l_tr = round(SCAN_D_W * lod, 9)
            d_hub = round(SCAN_D_W * dod, 9)
            a0 = round(SCAN_D_W * lod * aol, 9)
            t = base_text
            for key, val in (("m02Aw.lW", l_tr), ("m02An.lN", l_tr),
                             ("m02An.D1", d_hub), ("m02An.D2", d_hub),
                             ("m02An.a0", a0)):
                t = _setkey(t, key, val)
            case = CASES_DIR / f"kl_extra_{name}.M2A"
            case.write_text(t, "utf-16")
            ksoft.LoadFile(str(case))
            if not ksoft.CalculateRetVal():
                raise SystemExit(f"锚点 {name} 判废")
            kl = _getvar(ksoft, "m02Aa.Klamda")
            print(f"锚点 {name}: Kλ={kl!r}（比值 {lod:.6f}/{dod:.6f}/{aol:.6f}）",
                  flush=True)
            points.append({"keys": 1, "l": l_tr, "D": d_hub, "a0f": aol,
                           "KLamda": kl, "peq_w": _getvar(ksoft, "m02Aw.peq"),
                           "LOverD": lod, "DOverD": dod, "A0OverL": aol,
                           "anchor": name})
    finally:
        try:
            ksoft.ReleaseModule()
        except Exception:  # noqa: BLE001, S110
            pass
    if failed:
        print(f"判废点 {len(failed)}: {failed[:10]}")
    # 按行完整性收点：三线性插值要求规则网格——某 (keys, l) 行缺点（内核
    # 对过短键长判废）则整行丢弃。锚点（anchor 键）不进规则网格。
    anchors = [p for p in points if "anchor" in p]
    grid_pts = [p for p in points if "anchor" not in p]
    by_row: dict[tuple[int, float], list[dict]] = {}
    for p in grid_pts:
        by_row.setdefault((p["keys"], p["l"]), []).append(p)
    full_rows = {row: pts for row, pts in by_row.items()
                 if len(pts) == len(SCAN_D) * len(SCAN_A0F)}
    dropped = sorted(set(by_row) - set(full_rows))
    if dropped:
        # 整表覆盖写快照前硬失败：部分 COM 失败会把已发布 l/d 域静默缩小，
        # 用户在原本合法的工况上收到域错误（质量门 CR12）
        raise SystemExit(
            f"扫描出现不完整 (keys, l) 行（内核判废域），拒绝覆盖快照：{dropped}——"
            "若为内核域收缩请显式改小 SCAN_L/SCAN_D 后重扫")
    if len(full_rows) < 24:
        raise SystemExit(f"完整行不足：{len(full_rows)}（{sorted(full_rows)}）")
    points = [p for row in sorted(full_rows) for p in full_rows[row]] + anchors
    n_kept = len(full_rows) * len(SCAN_D) * len(SCAN_A0F)
    SCAN_OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(SCAN_OUT, "wt", encoding="utf-8") as fh:
        json.dump({
            "source": f"KISSsoft 2026 M02A COM scan, base=08 Keys ex1, d_w={SCAN_D_W:g}",
            "axes": {"keys": [1, 2], "l": sorted({row[1] for row in full_rows}),
                     "D": SCAN_D, "a0f": SCAN_A0F},
            "points": points,
        }, fh, ensure_ascii=False)
    print(f"→ {SCAN_OUT}（{n_kept} 点 + {len(anchors)} 锚点）")
    return 0


def extract_profile() -> int:
    """dat/M02A-001.DAT（DIN 6885.1:1968）→ tools/data/key_joint/din6885_profile.csv。

    列序 d, b, h, t1.min, t1.max(公差带), t2.min, t2.max(公差带), r1.max, r1.min, a；
    快照只取槽深 min 值与圆角上下限（内核口径：Nuttiefe Minimalwert）。
    """
    rows = []
    for line in KISS_DAT.read_text(encoding="cp1252", errors="replace").splitlines():
        m = _PROFILE_ROW.match(line)
        if not m:
            continue
        d_max, b, h, t1, _t1b, t2, _t2b, r1max, r1min, a = (float(g) for g in m.groups())
        rows.append([d_max, b, h, t1, t2, r1max, r1min, a])
    if len(rows) != 26:
        raise SystemExit(f"DIN 6885.1 剖面行数异常：{len(rows)}（应 26）")
    PROFILE_CSV.parent.mkdir(parents=True, exist_ok=True)
    with PROFILE_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["DMax", "B", "H", "T1", "T2", "R1Max", "R1Min", "A"])
        w.writerows(rows)
    print(f"→ {PROFILE_CSV}（{len(rows)} 行）")
    return 0


def main(argv: list[str]) -> int:
    if "--scan-klambda" in argv:
        return scan_klambda()
    if "--profile" in argv:
        return extract_profile()
    return harvest()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
