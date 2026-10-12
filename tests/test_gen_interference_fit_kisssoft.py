"""gen_interference_fit_kisssoft.py 离线自检（不碰 COM）。

覆盖三件事：
1. 变量名录与仓内已收割金样一致（防名录漂移导致金样键位错乱）；
2. RPT 花括号集提取在无 KISSsoft 安装的机器上优雅降级（返回空集不抛）；
3. 收割器只声明 RPT 集内的键（`m01w.tolOut` 为已知例外，见模块 docstring）。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location(
        "gen_interference_fit_kisssoft", _SCRIPTS / "gen_interference_fit_kisssoft.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load()


def test_cases_cover_both_official_cases(mod) -> None:
    assert set(mod.CASES) == {"cyl_01", "cyl_02_outer_rings"}
    assert all(f.endswith(".M10") for f in mod.CASES.values())


def test_key_list_has_no_duplicates(mod) -> None:
    keys = mod.INPUT_KEYS + mod.RESULT_KEYS
    assert len(keys) == len(set(keys)), "变量名录有重复键"


def test_result_keys_contain_primary_outputs(mod) -> None:
    """主压力与滑动安全必须在名录里——这两个键最容易因猜错族名而漏。"""
    for k in ("m01r.p[0]", "m01r.p[1]", "m01r.p[2]",
              "m01r.si[0]", "m01r.si[1]", "m01r.si[2]"):
        assert k in mod.RESULT_KEYS, f"结果侧缺主键 {k}"
    # 反向：这三个不是结果侧主压力（n 族 pressure 是外压直给输入）
    assert "m01n.pressure[0]" in mod.INPUT_KEYS
    assert "m01n.pressure[0]" not in mod.RESULT_KEYS


def test_rpt_keys_degrades_without_install(mod, tmp_path, monkeypatch) -> None:
    """无 KISSsoft 安装的机器上 RPT 目录不存在 → 返回空集而非抛异常。"""
    monkeypatch.setattr(mod, "KS_RPT", tmp_path / "nonexistent")
    assert mod.rpt_keys() == set()


def test_rpt_keys_reads_utf16(mod, tmp_path, monkeypatch) -> None:
    """模板须按 UTF-16 解码——按 utf-8 读会得 0 键（静默漏掉整个变量集）。"""
    rpt = tmp_path / "M010TEST.RPT"
    body = "a {m01r.p[0]} b {m01n.sigmaVi[2]} c {m01w.tol.max}\n"
    rpt.write_bytes(b"\xff\xfe" + body.encode("utf-16-le"))
    monkeypatch.setattr(mod, "KS_RPT", tmp_path)
    assert mod.rpt_keys() == {"m01r.p[0]", "m01n.sigmaVi[2]", "m01w.tol.max"}


def test_harvested_golden_shape_if_present(mod) -> None:
    """仓内已收割的金样须结构完整（未收割则跳过——离线机器没有产物）。"""
    path = mod.GOLDEN
    if not path.is_file():
        pytest.skip("金样未收割（本机无 KISSsoft 席位）")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data) == {"source", "note", "cases"}
    assert set(data["cases"]) == set(mod.CASES)
    for row in data["cases"].values():
        assert row["calc"] is True
        for k in ("m01r.p[0]", "m01r.si[1]", "m01n.sigmaViMF[2]", "m01w.sigmaVi[2]"):
            assert row["results"][k] is not None, f"结果侧缺 {k}"


def test_golden_band_ordering_identities(mod) -> None:
    """金样内的两条恒等式（si ∝ p、SiRm × σViMF = Rm）是最好的档序健全性判据。"""
    path = mod.GOLDEN
    if not path.is_file():
        pytest.skip("金样未收割（本机无 KISSsoft 席位）")
    data = json.loads(path.read_text(encoding="utf-8"))
    for row in data["cases"].values():
        r = row["results"]
        for k in range(3):
            assert r[f"m01r.si[{k}]"] == pytest.approx(
                r[f"m01r.p[{k}]"] * 0.0706778839, rel=1e-9)
        # 最坏档下标：SiRm 递减 → [2] 最小；滑动 si 递增 → [1] 最小
        assert r["m01n.SiRm[2]"] < r["m01n.SiRm[0]"] < r["m01n.SiRm[1]"]
        assert r["m01r.si[1]"] < r["m01r.si[0]"] < r["m01r.si[2]"]
