"""gen_roller_chain_power_kisssoft.py 离线回归（2026-10 审计行为缺陷 #4）：

- ``--dry-run`` 全程不碰 COM（原实现 Dispatch/GetModule 在 dry 判断之前，
  无 KISSsoft 的机器跑 dry 直接 ImportError/DispatchError）；
- COM 全判废（CalculateRetVal 恒 0）时显式 SystemExit 且**不**截断仓内
  快照 CSV（原实现先以 "w" 打开再取 out_rows[0]——IndexError 之外快照
  已被清空）。

KISSsoft 算例与 COM 均为合成替身（模块常量 monkeypatch 到 tmp_path），
CI 离线可跑；真机收割链路的口径见 tools 脚本 docstring。
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

_TOOL = Path(__file__).resolve().parents[2] / "tools" / "gen_roller_chain_power_kisssoft.py"
_spec = importlib.util.spec_from_file_location("gen_roller_chain_power_kisssoft", _TOOL)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _patch_paths(monkeypatch, tmp_path) -> Path:
    """EXAMPLE/OUT_CSV/CASES_DIR 指到临时目录；EXAMPLE 为合成 utf-16 算例。

    返回哨兵快照路径（"SENTINEL"）——断言收割失败时不被 "w" 截断。
    """
    example = tmp_path / "04 Chain Drive.Z92"
    keys = ("z092k.TypID", "z092k.z1", "z092k.z2", "z092k.PN",
            "z092k.a", "z092k.n1", "z092k.n2")
    example.write_text("".join(f"{k}=0¶\n" for k in keys), encoding="utf-16")
    out_csv = tmp_path / "roller_chain_power_curve.csv"
    out_csv.write_text("SENTINEL", encoding="utf-8")
    monkeypatch.setattr(mod, "EXAMPLE", example)
    monkeypatch.setattr(mod, "OUT_CSV", out_csv)
    monkeypatch.setattr(mod, "CASES_DIR", tmp_path / "cases")
    return out_csv


def test_dry_run_offline(monkeypatch, tmp_path, capsys):
    """--dry-run 生成全部变体、不碰快照，且全程不 import win32com。"""
    out_csv = _patch_paths(monkeypatch, tmp_path)
    # sys.modules 里塞 None：import win32com 即 ImportError——dry 路径若
    # 碰 COM（原实现的函数级 import）本测试立即红
    monkeypatch.setitem(sys.modules, "win32com", None)
    assert mod.sweep(dry=True) == 0
    cases = sorted((tmp_path / "cases").glob("*.Z92"))
    assert len(cases) == len(mod.SCAN) * len(mod.SPEEDS)
    text = cases[0].read_text(encoding="utf-16")
    assert "z092k.PN=5¶" in text          # 基础键值替换生效
    assert "z092k.TypID=0¶" not in text    # TypID 已按 KDB 行号改写
    assert out_csv.read_text(encoding="utf-8") == "SENTINEL"  # dry 不写快照
    assert "[dry]" in capsys.readouterr().out


def test_make_variant_missing_key_raises(monkeypatch, tmp_path):
    """变体键缺失（KISSsoft 版本变动改键名）显式 SystemExit——裸 re.sub
    会静默写出未改写的变体，错参数喂进快照（ocr bug/low）。"""
    example = tmp_path / "04 Chain Drive.Z92"
    example.write_text("z092k.z1=0¶\n", encoding="utf-16")
    monkeypatch.setattr(mod, "EXAMPLE", example)
    out = tmp_path / "variant.Z92"
    with pytest.raises(SystemExit, match="改写失败"):
        mod.make_variant(out, {"z092k.z1": "19", "z092k.NOT_EXIST": "5"})
    assert not out.exists()  # 失败不落半成品变体


def test_empty_harvest_keeps_snapshot(monkeypatch, tmp_path):
    """COM 全判废（CalculateRetVal 恒 0）：显式 SystemExit 且快照原样。"""
    out_csv = _patch_paths(monkeypatch, tmp_path)

    class _Ksoft:
        def SetSilentMode(self, on): ...

        def GetModule(self, name, flag): ...

        def LoadFile(self, path): ...

        def CalculateRetVal(self): return 0  # 一律计算失败 → 各链型首档判废

        def ReleaseModule(self): ...

    fake = types.ModuleType("win32com")
    fake_client = types.ModuleType("win32com.client")
    fake_client.Dispatch = lambda *a, **k: _Ksoft()
    fake.client = fake_client
    monkeypatch.setitem(sys.modules, "win32com", fake)
    monkeypatch.setitem(sys.modules, "win32com.client", fake_client)
    with pytest.raises(SystemExit, match="未产出任何断点"):
        mod.sweep(dry=False)
    assert out_csv.read_text(encoding="utf-8") == "SENTINEL"  # 未被 "w" 截断
