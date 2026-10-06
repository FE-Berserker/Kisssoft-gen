"""M40 被夹件柔度/载荷引入变体扫描机（数值锥模型标定数据的生产线）。

背景：pyffalo 的 BoltJoint（VDI 2230 经验闭式锥）与 KISSsoft 2026 M40 对账
发现 δP 差 +37.5%（中大 DA）、Φ 差 −6.4%（KISSsoft 内部 n_eff=0.486 ≠ 表值
0.3459），且 KISSsoft 行为是数值模型（见 docs/specs/bolt-kisssoft-m40.md
「关键事实」）。本脚本在官方算例 01 上做单变量变体扫描，产出数值锥模型
（components/bolt/_cone.py）的标定与 holdout 数据。

COM 机制坑（实测钉死，勿绕）：
1. 根对象直调：GetModule 返回 VT_VOID，LoadFile/Calculate/GetVar 全在
   Dispatch 返回的根对象上调用；SetSilentMode(True) 灭模态框。
2. 库锁：m04s.dw / m04s.E / m04t.dh 是 TypIndex/KlasIndex 的库派生快照，
   直接改写会被 LoadFile 后的库重读覆盖——解锁钥匙 m040DB.TypIndex=10050
   （Own input）；层材料 E 需 m04mat.mat[i].DBID=19999 且文件内两处全改。
3. 连坐：改 m04s.l 触发螺纹长 lGW 库重算（M12 l=80 → b=36），l 变体只锚
   m04s.l 本身，lGW 记录实际生效值不校验。
4. 静默回退：LoadFile 解析失败保留上一文件状态——每次 LoadFile 后必须
   读回锚键（本脚本 mods 即锚键），不一致即弃点。
5. 格式铁律：key=value¶ 紧凑（等号两侧无空格、值尾 ¶）、UTF-16 写盘且
   newline=""（防换行转换破坏 ¶）。
6. 垫圈 m04u.* 在算例 01 有未落盘开关，文件变体探不进（例 03/06 金样当
   天然实验）；KISSsoft 的 lk 不含垫圈厚度。

用法（需本机 KISSsoft 2026 + license，占 1 席位）::

    python scripts/scan_bolt_m40_kisssoft.py          # 全部变体 → tools/data/bolt/m40_scan.json.gz
    python scripts/scan_bolt_m40_kisssoft.py --group sv # 只跑 sv 组

产物：tools/data/bolt/m40_scan.json.gz（gzip JSON 行数组，含既有
tmp/bolt_m40_scan.json 的 49 行历史扫描，group 字段区分批次）；下游消费者
tools/calib_bolt_cone.py（标定）与 tests/unit/test_kisssoft_m40_golden.py
（金样回归，不读本文件产物）。
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
from pathlib import Path

import pyffalo_root

REPO = pyffalo_root.repo_root()
SRC_CASE = Path("C:/KISSsoft 2026/example/01 Bolts (VDI 2230 Example 1).M40")
SRC_FLANGE = Path("C:/KISSsoft 2026/example/02 Bolts (VDI 2230 Example 2).M40")
TMP_CASE = REPO / "tmp" / "m40_scan_variant.M40"
OUT = REPO / "tools" / "data" / "bolt" / "m40_scan.json.gz"
LEGACY_TMP = REPO / "tmp" / "bolt_m40_scan.json"  # 对账期历史扫描（49 行）

RESULTS = [
    "m04t.delta", "m04s.delta", "m04s.phin", "m04s.phien", "m04n.wert",
    "m04t.DAGr", "m04t.lkEff", "m04r.FM", "m04r.FMmin", "m04r.FMmax",
    "m04s.FSmax", "m04r.Fz", "m04s.sigmaredB", "m04r.SF", "m04r.SD",
    "m04r.SG", "m04r.SA", "m04t.deltapx", "m04t.deltazu", "m04s.lGW",
]


def setkey(text: str, key: str, val: float) -> str:
    """多行全局替换 key=<val>¶（同键多行全换，防库重读覆盖手填）。"""
    new, n = re.subn(r"^" + re.escape(key) + r"=.*$",
                     lambda _: f"{key}={float(val)!r}\u00b6", text, flags=re.MULTILINE)
    if n == 0:
        raise KeyError(key)
    return new


def _variants() -> list[dict]:
    """变体清单：每项 name/group/mods（mods 即锚键，l 组例外）。"""
    v: list[dict] = []

    def add(group: str, name: str, mods: dict, anchors: dict | None = None):
        v.append({"group": group, "name": name, "mods": mods,
                  "anchors": anchors if anchors is not None else mods})

    # ---- sv 组：载荷引入面（n_eff 标定）----
    for ak in (0.0, 4.2, 8.0, 12.6, 21.0):        # a=ak/lk 覆盖节点 0/.1/.19/.3/.5
        add("sv", f"ak{ak}", {"m04n.ak": ak})
    for la in (4.2, 8.4, 12.6):                   # b=lA/lk 节点 .1/.2/.3
        add("sv", f"lA{la}", {"m04n.lA": la})
    for sv in (1, 2, 3, 4, 5, 6):
        add("sv", f"SV{sv}", {"m04n.SVwahl": sv})

    # ---- layer 组：层间重分布（q 标定）----
    def layers(maxp: int, his: list[float], es: list[float], name: str):
        mods = {"m04t.maxPlatte": maxp, "m04t.lk": sum(his)}
        for i, h in enumerate(his):
            mods[f"m04t.hi[{i}]"] = h
        for i, e in enumerate(es):
            mods[f"m04mat.mat[{i}].DBID"] = 19999
            mods[f"m04mat.mat[{i}].E"] = e
        add("layer", name, mods)

    layers(2, [21, 21], [205000, 103000], "2L_soft_bottom")
    layers(2, [21, 21], [103000, 205000], "2L_soft_top")
    layers(2, [14, 28], [205000, 103000], "2L_thin_hard")
    layers(3, [14, 14, 14], [205000, 103000, 205000], "3L_soft_core")
    layers(3, [14, 14, 14], [103000, 205000, 103000], "3L_hard_core")
    layers(3, [10, 22, 10], [205000, 103000, 205000], "3L_thinskin")

    # ---- geo 组：dw/dh 补点（TypIndex=10050 解锁）----
    for dw in (16.0, 23.0):
        add("geo", f"dw{dw}", {"m040DB.TypIndex": 10050, "m04s.dw": dw})
    for dh in (11.0, 14.5):
        add("geo", f"dh{dh}", {"m040DB.TypIndex": 10050, "m04t.dh": dh})

    # ---- l 组：螺栓总长耦合（只锚 l，lGW 记录不校验）----
    for lb in (50, 70, 90):
        add("l", f"l{lb}", {"m04s.l": lb}, anchors={"m04s.l": lb})

    # ---- flange 组：法兰 DA' 折算（例 02 基础变体）----
    def flange(name: str, mods: dict):
        add("flange", name, mods)

    flange("n8", {"m04konfig.n": 8})
    flange("n16", {"m04konfig.n": 16})
    flange("n24", {"m04konfig.n": 24})
    flange("ri79", {"m04t.ri": 79})
    flange("ri99", {"m04t.ri": 99})
    flange("ra189", {"m04t.ra": 189})

    return v


def _getvar(ks, name: str):
    try:
        raw = ks.GetVar(name)
    except Exception:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return s


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--group", choices=["sv", "layer", "geo", "l", "flange"],
                    help="只跑指定组")
    args = ap.parse_args()

    import win32com.client as client  # 函数体内 import：无 COM 环境可收集

    variants = _variants()
    if args.group:
        variants = [x for x in variants if x["group"] == args.group]

    rows: list[dict] = []
    if OUT.exists():  # 既有产物按 (group, name) 覆盖合并（局部重跑不丢组）
        with gzip.open(OUT, "rt", encoding="utf-8") as fh:
            for r in json.loads(fh.read()):
                rows.append(r)
    if LEGACY_TMP.exists() and not any(r.get("group") == "legacy" for r in rows):
        for r in json.loads(LEGACY_TMP.read_text(encoding="utf-8")):
            r.setdefault("group", "legacy")
            rows.append(r)

    ks = client.Dispatch("KISSsoftCOM.KISSsoft")
    ks.SetSilentMode(True)
    ks.GetModule("M040", True)
    seen = {(r.get("group"), r.get("name")) for r in rows}
    new_rows = 0
    try:
        for var in variants:
            try:
                src = SRC_FLANGE if var["group"] == "flange" else SRC_CASE
                text = src.read_bytes().decode("utf-16")
                for k, val in var["mods"].items():
                    text = setkey(text, k, val)
                TMP_CASE.parent.mkdir(parents=True, exist_ok=True)
                TMP_CASE.write_bytes(text.encode("utf-16"))
            except Exception as exc:  # 键名漂移/写盘失败只弃本点，不带走整轮
                print(f"[{var['group']:6s} {var['name']:14s}] VARIANT_FAIL {exc!r}",
                      flush=True)
                continue
            try:
                ks.LoadFile(str(TMP_CASE))
                bad = []
                for k, want in var["anchors"].items():
                    got = _getvar(ks, k)
                    if (not isinstance(got, float)
                            or abs(got - float(want)) > 1e-6 * max(1.0, abs(float(want)))):
                        bad.append(f"{k}: want {want} got {got!r}")
                if bad:
                    print(f"[{var['group']:6s} {var['name']:14s}] ANCHOR_FAIL "
                          f"{'; '.join(bad)[:120]}", flush=True)
                    continue
                if not ks.CalculateRetVal():  # False → GetVar 是上一变体残留
                    print(f"[{var['group']:6s} {var['name']:14s}] CALC_FAIL",
                          flush=True)
                    continue
                row = {"group": var["group"], "name": var["name"], "status": "ok",
                       "mods": var["mods"]}
                for key in RESULTS:
                    row[key] = _getvar(ks, key)
                if (var["group"], var["name"]) in seen:
                    rows = [r for r in rows
                            if (r.get("group"), r.get("name")) != (var["group"], var["name"])]
                if all(isinstance(row.get(k), float) for k in
                       ("m04t.delta", "m04s.phin", "m04n.wert", "m04t.DAGr")):
                    rows.append(row)
                    new_rows += 1
                    print(f"[{var['group']:6s} {var['name']:14s}] "
                          f"δP={row['m04t.delta']:.6e} Φ={row['m04s.phin']:.6f} "
                          f"n={row['m04n.wert']:.6f} DAGr={row['m04t.DAGr']:.4f}",
                          flush=True)
                else:
                    print(f"[{var['group']:6s} {var['name']:14s}] EMPTY_RESULT 弃点",
                          flush=True)
            except Exception as exc:
                print(f"[{var['group']:6s} {var['name']:14s}] ERROR {exc!r}",
                      flush=True)
    finally:
        try:
            ks.ReleaseModule()
        except Exception:
            pass

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1)
    print(f"\n{new_rows} new rows; total {len(rows)} -> {OUT}")


if __name__ == "__main__":
    main()
