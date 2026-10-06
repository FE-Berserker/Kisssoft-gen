# kisssoft-golden

KISSsoft 2026 COM 金样机与对账工具链（ZCode skill，用户级 `~/.zcode/skills/kisssoft-golden`）。

pyffalo 仓本身不调用 KISSsoft（运行时零依赖）；全部「调用 KISSsoft」的脚本——COM 探针 / 参数扫描 / 金样收割 / KDB·DAT 逆向 / 官方案例库镜像——集中在本仓。产物（金样 JSON、数据快照、例库镜像）写回某个 pyffalo checkout，由 pyffalo 的 golden 测试与 seed 脚本离线消费。2026-10 自 pyffalo `tools/` 迁出（原样快照为首个 commit，其后为路径改造，可 diff 审计）。

## 用法

- 环境：Windows + 本机 KISSsoft 2026 + pywin32（pyffalo 的 `.venv` 即可）。COM 占 license 席位。
- 定位 pyffalo checkout：设 `PYFFALO_ROOT`，或直接在 pyffalo 仓库根运行脚本。
- 例：`python scripts/gen_clamp_connection_kisssoft.py`（金样收割）；`python scripts/gen_key_joint_kisssoft.py --scan-klambda`（系数扫描）。选官方算例先查 `references/example-catalog.md`（example/ 全量 278 案清单，`python scripts/gen_example_catalog.py` 再生）。逐脚本对应关系见 `references/module-index.md`，COM 机制坑见 `references/com-mechanics.md`，工作流与配方见 `SKILL.md`。

## 自检

    ruff check .
    python -m pytest tests/ -q   # 离线，不碰 COM；可用 pyffalo 的 venv 跑

## 许可

脚本源自 pyffalo 仓（GPL-3.0-or-later），随仓携带 `LICENSE`，同许可分发。
