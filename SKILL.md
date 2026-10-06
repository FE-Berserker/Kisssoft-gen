---
name: kisssoft-golden
description: KISSsoft 2026 COM 金样机与对账工具链：驱动 KISSsoftCOM（探针 / 参数扫描 / 金样收割）、解析 KDB/DAT 安装文件、为 pyffalo 组件移植产出对账金样与数据快照。凡提到 KISSsoft、金样、对账、收割、COM 扫描、KDB、.DAT、ReportWithParameters、官方算例复现，或 Z90/Z91/Z92、W10/W50/W51、W70/W7C、K14、M010/M1B/M1C、M2A/M2D/M2E、M40/M60、F20/F30/F50、Z70 等模块的移植、调研与数值对标时使用。
---

# KISSsoft COM 金样机与对账工具链

pyffalo 运行时**不依赖** KISSsoft；本 skill 承载全部「调用 KISSsoft」的任务：探针、参数扫描、金样收割、KDB/DAT 逆向、官方案例库镜像。产物（`tests/golden/*.json` 金样、`tools/data/**` 快照、`examples/kisssoft/**` 镜像）写回某个 pyffalo checkout，由 pyffalo 仓的 golden 测试离线消费。

## 环境前置（缺一即废）

- Windows + 本机 `C:\KISSsoft 2026`（全套模块）。COM ProgID `KISSsoftCOM.KISSsoft`；失效时管理员重跑 `bin\KISSsoftCOM2026_Register.bat`。
- COM 每次调用另起 `KISSsoftCOM2026.exe` 进程并**占一个 license 席位**——批量出金样前确认席位空闲（用户交互会话常开着 KISSsoft.exe 时注意并发拒绝）。
- 解释器：任意 ≥3.12 且装了 pywin32（pyffalo 的 `.venv` 即可）。只读 dump 亦可走 PowerShell 原生 COM（见 references/com-mechanics.md §PowerShell）。
- **pyffalo checkout 定位**：脚本 import 期经 `scripts/pyffalo_root.py::repo_root()` 解析输出落点——优先环境变量 `PYFFALO_ROOT`，否则从 cwd 逐级上溯找含 `src/pyffalo` 的目录。最省事：在 pyffalo 仓库根运行。

## 脚本清单（scripts/，文件名与 pyffalo 原 tools/ 一致）

| 分组 | 脚本 | 作用 |
| --- | --- | --- |
| 通用 COM | kisssoft_com_probe.py / _scan.py / _catalog.py | Z90 例驱动的探针 / 工况扫描 / 目录扫描（调用形态可复制到任意模块） |
| KDB/DAT 逆向 | kdb_reader.py / kdb_export.py / parse_kisssoft_kdb.py | KISSsoft 二进制 KDB 表读取导出（UTF-16 字符串区 + double 定长 stride）、Z092TYP 快照 |
| 算例目录 | gen_example_catalog.py | 只读遍历 `C:\KISSsoft 2026\example\` 再生 `references/example-catalog.md`（官方算例全量清单，371 文件 / 47 模块 278 案 + KISSsys 48 + 附件 45；选案先查它） |
| 例库镜像 | gen_kisssoft_examples.py | 官方算例库 → pyffalo `examples/kisssoft/` 逐模块映射生成 |
| 收割器 / 扫描器 | gen_&lt;模块&gt;_kisssoft.py、harvest_kisssoft_w10/z91.py、scan_bolt_m40_kisssoft.py | 金样收割（`tests/golden/`）+ 系数表扫描（`tools/data/`），逐件对应关系见 references/module-index.md |

## 标准对账工作流（新模块移植 / 既有模块追口径共用）

1. **读权威文档**：pyffalo `docs/KISSSOFT.md` 对应专项节（公式链 + 机制坑全录）与 `docs/specs/<任务>.md`。勿凭记忆写公式。
2. **选案与探针**：官方算例全量清单在 `references/example-catalog.md`（模块 × 案例 × pyffalo 对应 × 收割器 × 镜像；无 KISSsoft 的机器直接读该档）。选案后跑一遍 dump 全变量（`GetVar` 逐个 try/except，或 `GetVarAsJson`）。
3. **变体扫描钉口径**：文件变体路线改输入（勿 SetVar），单因子扫出公式结构（系数 / 钳位 / 判废面）。
4. **写收割器**：照 `scripts/gen_clamp_connection_kisssoft.py` 骨架（见下方配方），覆盖矩阵成案、幂等重跑。
5. **金样落盘 + 对账**：金样 JSON 入 pyffalo `tests/golden/<族>/`，pyffalo 侧写 golden 测试（挂 `golden` marker），容差分档在测试内注明。
6. **数据快照回填**：内核系数曲面（Kλ / 特性表 / 功率曲线等）扫成 `tools/data/**` 快照，pyffalo 的 seed 脚本离线消费。

## COM 调用配方（canonical，细节与反例见 references/com-mechanics.md）

```python
import win32com.client as client

ksoft = client.Dispatch("KISSsoftCOM.KISSsoft")
try:
    ksoft.SetSilentMode(True)          # 抑制模态警告框，批量必备
    ksoft.GetModule("M01C", True)      # 返回值丢弃（类型库标 VT_VOID），方法全在根对象
    ksoft.LoadFile(str(case))          # 必须绝对路径；变体案先写盘再载
    ok = ksoft.CalculateRetVal()       # 判废唯一判据（Calculate 会假成功）
    val = ksoft.GetVar("m01c.SH")      # 异常/None/空串归一化为 None 再入金样
finally:
    ksoft.ReleaseModule()              # 跨模块切换必须先释放，否则 GetVar 全空
```

改输入一律**文件变体路线**（UTF-16 紧凑 `key=value¶` 行尾、等号两侧无空格、锚定行首替换且命中数 ≠1 即废），不要 SetVar——陈旧值陷阱下 Calculate 照样返回成功而结果不刷新。

## 新收割器配方

复制 `scripts/gen_clamp_connection_kisssoft.py` 骨架，改四处：`_BASES`（官方算例基座）、`CASES`（覆盖矩阵：单因子 + 组合 + 判废边缘 + 惰性见证）、`VARS`（输出变量名录，来源 = RPT 模板花括号集 + 输入回显，**勿信 KVAR**）、`GOLDEN` 落点。铁律：

- 健全性过滤：结果变量缺一即废，None 不进金样；`CalculateRetVal()` 为唯一判据。
- 失败不覆盖旧档：全部案通过后一次性写金样文件。
- 幂等：重跑产出与仓内金样逐字节一致（JSON 载荷里的 `harvest` 命令串保持原样勿改）。
- 每个反直觉发现（死键 / 派生快照 / 单位笔误）写进收割器 docstring 并回灌 pyffalo 的 KISSSOFT.md 专项节——知识随脚本走，文档是公式链唯一权威。

## 深入阅读

- `references/com-mechanics.md` —— COM 机制坑全集（SetVar 陷阱 / 文件变体格式 / 材料库锁 / PowerShell 边界 / 类型库读取 / license）。
- `references/module-index.md` —— 模块 → 脚本 → pyffalo 组件 → 金样/快照落点 → 权威文档 的逐件索引。
- `references/example-catalog.md` —— KISSsoft 官方算例全量目录（47 模块 278 案逐案文件名 + KISSsys 系统档），选案 / 调用的第一入口。
- pyffalo `docs/KISSSOFT.md` 各专项节 —— 公式链与口径的**唯一权威**（本 skill 不重复维护公式）。

## 仓库维护

本 skill 是独立 git 仓（`~/.zcode/skills/kisssoft-golden`），远程同步走 `git push`。改动后自检：`ruff check .` + `python -m pytest tests/ -q`（离线，不碰 COM；可用 pyffalo 的 venv）。真机回归需 KISSsoft 席位，按需逐脚本跑。
