"""定位 pyffalo 仓库根——skill 各脚本的输出落点（tests/golden、tools/data、tmp）。

本 skill 的收割器 / 扫描器 / 快照器全部把结果写回某个 pyffalo checkout，
脚本自身不再随仓库走，故仓库根按以下优先级解析：

1. 环境变量 ``PYFFALO_ROOT``（目录下须存在 ``src/pyffalo``）；
2. 从当前工作目录逐级上溯，找含 ``src/pyffalo`` 的祖先目录
   （在 pyffalo 仓库根或其子目录里运行即命中）；
3. 都没有 → 显式报错退出（不走静默相对路径，防止金样/快照写错地方）。
"""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    env = os.environ.get("PYFFALO_ROOT")
    if env:
        root = Path(env).resolve()
        if (root / "src" / "pyffalo").is_dir():
            return root
        raise SystemExit(
            f"PYFFALO_ROOT={env} 不是 pyffalo 仓库（缺 src/pyffalo 子目录）")
    cwd = Path.cwd().resolve()
    for cand in (cwd, *cwd.parents):
        if (cand / "src" / "pyffalo").is_dir():
            return cand
    raise SystemExit(
        "未定位到 pyffalo 仓库：请在仓库内运行，或设 PYFFALO_ROOT 指向 checkout 根")
