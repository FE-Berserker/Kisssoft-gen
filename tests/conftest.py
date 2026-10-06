"""skill 离线测试环境。

两件事都在收集期完成：

1. 被测脚本 import 期即调用 ``pyffalo_root.repo_root()`` 解析仓库根——离线
   测试没有真实 checkout，先落一个最小假仓（空 ``src/pyffalo`` 包）并把
   ``PYFFALO_ROOT`` 指过去；
2. scripts/ 入 sys.path——被测脚本经 spec_from_file_location 加载后
   ``import pyffalo_root`` 靠它解析。

各测试内再对模块的输出路径属性做 monkeypatch。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_FAKE_PKG = _HERE / "_fake_repo" / "src" / "pyffalo"

_FAKE_PKG.mkdir(parents=True, exist_ok=True)
(_FAKE_PKG / "__init__.py").touch()
os.environ.setdefault("PYFFALO_ROOT", str(_FAKE_PKG.parents[1]))

_SCRIPTS = str(_HERE.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
