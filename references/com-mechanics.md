# KISSsoft COM 机制坑全集（通用，模块无关）

各模块特有的坑（死键 / 派生快照 / 单位笔误等）在收割器 docstring 与 pyffalo `docs/KISSSOFT.md` 专项节；本文只收**跨模块通用**的机制知识，均有实战翻车记录背书。

## 调用形态

- ProgID `KISSsoftCOM.KISSsoft`（`bin\KISSsoftCOM2026.exe`）；失效重跑 `bin\KISSsoftCOM2026_Register.bat`（管理员）。
- `GetModule(name, True)` 返回值在类型库标注 VT_VOID 且实际为空——`LoadFile / Calculate / CalculateRetVal / GetVar / SetVar / ReleaseModule / SetSilentMode / Report*` 全部在**根对象**上调用，模块对象拿不到也不需要（W10 实测）。
- **跨模块切换必须先 `ReleaseModule()`**，否则后续 GetVar 全空（W50↔W51 实测）。`finally` 里释放，释放失败不带走收割结果。
- 方法签名拿不准时，用 comtypes `LoadTypeLibEx` 读 `bin/KISSsoftCOM.exe` 内嵌类型库（Z91 曾据此确认 `Report(1p)` / `ReportWithParameters(4p)`）。

## 判废与取值

- `Calculate()` 返回 True **不代表**结果刷新（陈旧 SetVar 下假成功）。判废唯一判据是 `CalculateRetVal()`；部分模块（K14）两者语义一致，但统一用 RetVal 版不吃亏。
- 判废后 GetVar 回吐**上次计算的陈旧值**（F30 实测）——健全性过滤必须以 RetVal 前置，勿把垃圾值当真值入库。
- GetVar 归一化：异常 / None / 空串 → None；数值串 → float；带 `¶` 尾的剥掉再试。None 不进金样。
- 输出变量权威名录 = 报告模板 `rpt\*.RPT` 的**花括号集** + GetVar 实测；**KVAR 注册表缺登/错登**（K14 的 pH/pm、M60 的 ν 均错）勿信。
- F020 起可用 `GetVarAsJson("模块名")` 一次 dump 全部变量（比 RPT 全且双精度）；注意判废案的部分量仍在 dump（材料链先于有效性检查）。
- 报告通道：`ReportWithParameters(模板名, 输出.rtf, 0, 0)` 生成官方报告（配合 `SetSilentMode`），文本可逐项对账（Z91 预紧块反推的主证据）。

## SetVar 陈旧值陷阱与文件变体路线（最重要的一条）

- `SetVar` 后 `Calculate` 返回 True 但结果不刷新（读回新值、消费值仍旧）——W10 / K14 / Z91 多模块复现，**改输入一律走文件变体**。
- 官方算例存档是 UTF-16 明文、紧凑 `key=value¶`（等号两侧无空格；带空格解析会失败并静默回退旧档）。变体 = 读原文 → 锚定**行首**正则替换（`^key=[^¶\r\n]*¶`，命中数 ≠1 即废——防 KISSsoft 版本改键名后裸 sub 静默产出错参数变体）→ 写 UTF-16 → `LoadFile` **绝对路径**。
- 相对路径 LoadFile 会静默失败回落默认态（M1B 实测：症状 nu=0.1 / l=0）。
- Z09A 族例外：存档**只从安装目录载入**，tmp 变体 LoadFile 静默回落默认态——变体须写 `C:\KISSsoft 2026\example\` 下，用后即删。
- 派生变量（如 Z91 的中心距 a、z2）SetVar / 改档均被静默重算回原值——主控变量（ZahneZ / 传动比 i）才是真输入，扫描前先分清主从。
- 材料库锁：库材料（DBID ≠19999）的 Rm/Rp 等快照改档无效，内核按 DBID 从库重读；own-input 要 **DBID=19999 + 全部出现处同改**（W10 的 `shafts[0].material.DBID` 在文件里出现两次，只改第一处会被第二处覆盖——症状：Kf 跨 Rm 逐位不变）。
- 反例（勿走）：M2A 调研期 PowerShell 探针 SetVar 扫描**全零不可信**（同值 no-op 也判废）；扫描一律 Python + pywin32。

## 公差四元组与变量名实测（Z011 探针，2026-10-06）

- 带公差的几何量（da/df/x/san/Wk…）GetVar 回吐**四元组多行串**：`nul=<公称>¶E=<上偏差>¶i=<下偏差>¶m=<均值>`——对账取 `nul` 行的公称值，勿把整串当 float。
- 存档键 ≈ COM 变量名（`ZR[0].dB` 直取即中），但**部分键名不达**：Z011 实测 `ZR[0].sn / .ha / .hf` GetVar 回空串——变量名录以 RPT 模板花括号集为准（勿信存档键全集）。
- 存档文件本身即离线基准：UTF-16 键值文本内含 KISSsoft 计算缓存值（如 `ZR[0].dB=15.9747…`），无 COM/席位也能对账（本节即由此交叉验证）。

## PowerShell 边界

只读 dump（LoadFile + Calculate + GetVar + Report）可用 PowerShell 原生 COM：`New-Object -ComObject 'KISSsoftCOM.KISSsoft'`——免 pywin32，Z91/Z90 调研期大量使用。**SetVar / 扫描不用 PowerShell**（见上反例）。

## license 与进程

- 每次 Dispatch 另起 `KISSsoftCOM2026.exe` 占一个席位；网络单席位时与用户开着的 KISSsoft.exe 互斥（被拒表现：Dispatch 后调用异常）。
- 批量扫描时长任务注意进程残留：脚本 finally 释放 + 异常路径也要能退出。

## 产物纪律（pyffalo 侧约定）

- 金样 JSON 带 `source / note / harvest / cases` 四键；`note` 是容差分档与口径注记的**唯一权威**（测试与文档引用它）。
- 失败不覆盖旧档：全部案通过健全性过滤后一次性写盘。
- 幂等：重跑与仓内金样逐字节一致；载荷内的 `harvest` 命令串是历史记录，保持原样。
- 快照（`tools/data/**`）入 pyffalo 仓由 seed 离线消费；扫描器只产快照，不直接碰 `database.db`。
