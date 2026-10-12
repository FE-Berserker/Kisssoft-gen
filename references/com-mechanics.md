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
- F020 起可用 `GetVarAsJson("模块名")` 一次 dump 全部变量（比 RPT 全且双精度）；注意判废案的部分量仍在 dump（材料链先于有效性检查）。**按模块可用性有别**：Z50 / K010 传任何模块名拼写均回 `{"status_code":"not_found"}`，整模块 dump 走不通时回落 RPT 花括号集 + GetVar 实测（见 Z50 / K10 两节）。
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
- Z 系齿轮（Z011 二轮实测，2026-10-06）：**检测尺寸藏在 `ZR[i].KM.*` 命名空间**——`KM.Wk.nul/.E/.i` 公法线、`KM.k` 跨齿数、`KM.DMeff` 有效量径、`KM.MdK`/`KM.MrK` 双球/单球距（裸名 `ZR[0].Wk` 回偏差四元组且非公称值）；而 `sn/sc/hac/dFf 公称/Linv/KsiFa/h/ha/hf/cp` 为 **report-only**（KVAR 无名、GetVar 全空串，`.nul` 后缀也不达），只能走报告文本或由公差链间接印证。变量名普查：`scripts/kdb_export.py` 导 `kdb/KVAR.KDB`（3104 行，按 MODULE 列过滤）。

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

## 文件变体与报告补充（Z50 beveloid 实测，2026-10-08）

- **双 BOM 陷阱（最高优先）**：官方存档 `raw.decode('utf-16-le')` 后首字符仍是 U+FEFF；若写回时再前置 `b'\xff\xfe'` 则文件变双 BOM，`LoadFile` **静默回落空模块默认态**——症状三联：几何变量全 0（如 `ZR[0].z=0`）、`CalculateRetVal()` False、`Message()` 零条。正确姿势：BOM 存在时先剥 `raw[:2]` 再 decode，写回恰好一个 BOM。此坑会让整轮变体矩阵"全废"且无任何报错。
- `ReportWithParameters(infile, outfile, show, type)` 的 **infile 必须带 `.rpt` 扩展名**（官方 COM 帮助 help/e/9748.htm）：裸模板名不报错，只出 ~11KB 纯封面 RTF。type：0=RTF（含数据级）/1=RTF/2=HTML/10=TXT/20=TXT(Unicode)/1000/1001=pprpt。
- 报告正文语言/单位跟随**应用级设置**：`SetLanguage(7)` 只部分汉化（部分标题仍英文）；文件键 `calculation.units` 翻转不改报告单位（英制算例仍打 hp/psi）。
- Z50（beveloid，`GetModule("Z50")`，文件内 MODULE=Z050）官方算例带 `RechSt.RechenMethID=10010`（仅几何）：强度链整体关闭——SF/SH 全 0、报告跳过强度章节、Overview 的 "Calculation method" 打空。改回模块默认 `10030` + 补载荷（`ZS.Pnominal` kW、`ZR[0].nnominal` rpm）即激活 ISO 6336:2006 方法 B 全套齿根/齿面强度。注意 `ZS.Pnominal` 在档内出现 **2 次**，须同改。
- `GetVarAsJson` 对 Z50 传任何模块名拼写（Z050/Z50/z50/空串/*）均回 `not_found`——该通道按模块不可靠，dump 变量走 RPT 花括号集 + GetVar 实测。
- 官方 Z50 变厚齿轮报告模板结构：`Z050la0.rpt` 为全报告（几何 5/测量 6/齿根 7/齿面 8/胶合/公差/寿命 12），强度子模板复用 Z010ISO* 系列；`Z050resd.rpt` 为结果速览表（含 `ZPP[i].Fuss.SF`）。

## GUI 侧输入展开不因 COM 计算触发（K10 公差/配合冒烟，2026-10-12）

- K010（`GetModule("K010")`，官方算例 `01 Tolerance Calculation.K10`）冒烟通过：`CalculateRetVal()` True，RPT 花括号集 11 个输出变量（`k10.TolName` + 两路公称/最大最小极限/上下偏差）全部有值——模块本身运行正常。
- **公差带代号不被 COM 侧展开**：`k10.Dat[i].Toleranzfeld=H7/g6` 存档 + 计算后，逐行 `ObTol/UntTol` 仍为存储值原样吐回（预埋哨兵实测原值回显）——「代号 → 偏差」换算只发生在 GUI 录入路径；根对象亦无任何 K10 专属方法（pywin32 `GetIDsOfNames` 逐名探测 Apply/Expand/Recalc/Update Tolerance 全 MISS）。
- 行值规整陷阱：档内写入 `ObTol < UntTol` 后读回**自动交换**（上限取 max、下限取 min）——哨兵实验判读时勿把交换误当换算。
- 对账口径：官方算例存档内的已展开偏差可信（H7/80 → +0.030/0、H7/16 → +0.018/0，实测符合 ISO 286-1）；要新组合就自算 ISO 286 或走 GUI 授权存档，勿指望 COM 侧展开。
- 标量块 `k10.TolName` / `k10.Nennmass1/2` / `ObMass1/2` / `UntMass1/2` 是**活的子计算器**（疑由档内 `TolID` + 行数据实时推导：公称实测 = 首行名义 − 其余行名义之和，两点吻合；语义未钉死）——对账先钉口径，勿当算例正文的确定性输出。
- 方法存在性快查：comtypes 缺席时用 pywin32 `ks._oleobj_.GetIDsOfNames(0, 名)` 逐名探测（本节 K10 方法面即由此钉死）。
- **K10 全矩阵真值的绕道路线（2026-10-12 实证）**：K10 不展开代号，但 **M10（圆柱过盈）内核对 `m01{w,n}.tol.bez` 公差代号做服务端展开**——tol.max/min 埋哨兵后算即被替换为该直径的正确 ISO 值（且用官方细分子段，如 s@24-30=35）。任意 (直径, 字母, IT) 的 KISSsoft 真值 = M10 文件变体（换 `m01allg.df` + 代号）→ CalculateRetVal → GetVar `m01{w,n}.tol.max/min`。约束：df>di 且 df<da 几何须有效（df>da 时轴侧回读被脏值污染；配合类型被拒/retval=False 不影响展开精度）；undefined 组合（如 t6@<24）内核回退化 0/0 而非拒绝（pyffalo 按 ISO 脚注拒，域语义差异）。`m01allg.uebermass[0..2]`=[均值,最小,最大] 过盈三档，与 M010 pressure 同约定。330 格对账 324 逐位一致（6 格即 t6<24 域语义）。

## 会话中毒：无效模块名会毁掉整个 COM 会话（过盈族冒烟，2026-10-12）

- 给 `GetModule` 传无效模块名会让**整个 COM 会话进入损坏状态**：之后即使换回完全正确的模块名，`CalculateRetVal()` 恒返回 False、`GetVar` 全空、`LoadFile` 静默失败。实测矩阵（官方算例 02）：`M10` / `M010` → True；`M01` → com_error「服务器出现意外情况」；`M02` / `M020` → 静默 False。**最阴的是 M02/M020 之后**，同一会话里再 `GetModule("M01B")` 也再也起不来——从外部看症状与「模块本身坏了」一模一样。
- **对策：一案一个 COM 会话**（收割器里每案单独 `Dispatch` + `finally: ReleaseModule(); del ks`）。既有收割器靠「先 ReleaseModule 再换模块」跨案复用会话，在模块名全对时可行；但只要有一案探错名字，后续全部静默废掉——本 skill 的收割器一律独立会话。
- 附带一条：模块名与存档内 `MODULE` 键不一致是常态（`GetModule("M10")` 与 `GetModule("M010")` 都能正常载同一个 `.M10` 存档），别拿存档键反推 COM 名。

## 过盈接触族专项（M10 / M010 / M1B，2026-10-12 冒烟 + 收割）

- **`GetVarAsJson` 在过盈族完全不可用**：`M01B` / `M1B` / `m01b` / `M010` / `M10` / `m01n` / 空串一律回 `not_found`（与 Z50 / K010 / K015 同款，属 COM 服务通病非过盈特例）。dump 走 RPT 花括号集 + GetVar 逐名。
- **RPT 模板是 UTF-16**：挖变量集须 `read_bytes().decode("utf-16-le")` 后再正则 `\{([A-Za-z0-9_.\[\]]+)\}`；按 latin-1/utf-8 读会得 0 键（看起来像「模板没变量」）。M010 全模板 18 个文件合计 **227 个唯一键**，是过盈族变量名录的权威来源。
- **变量分族**：毂（内件 Nabe）= `m01n.*`、轴（外件 Welle）= `m01w.*`、全局几何/载荷 = `m01allg.*`、**结果侧主压力与安全系数 = `m01r.*`**、压装系数 = `m01M.*`、许用基准 = `m01sollSi.*`。
- **主压力键是 `m01r.p[0..2]`**，不在 `m01n` 族下。`m01n.pressure[0..2]` 是**外压直给输入**（多层件的对账入口），单层无环算例恒全 0。早期按 `m01n.p` / `contact` / `pm` 等名猜「无直读键」是错的——按 RPT 花括号集查就不会漏。
- **滑动安全系数键是 `m01r.si[0..2]`**，同样在 r 族。按直觉试 `m01n.si` / `m01w.si` / `Sr` / `SR` / `Si` 等 3 族 × 5 候选名**全部读空**——只此一组命中。定位这类「结果量在别的族」的办法就是扫 RPT 花括号集。
- **三档下标语义 = 公差带档序 `[均值, 最小, 最大]`，同一档序贯穿所有量；但每个量的最坏档下标不同**（最坏是取最小值还是最大值随量而异）。实测算例 02：
  - 压力 `p` [121.28, 81.73, 154.42] 递增 → 最坏（最大）= `[2]`
  - 滑动 `si` = `p` × 0.0706778839（严格同比例）递增 → 最坏（**最小**）= `[1]`
  - 毂 `sigmaViMF` [636.98, 438.67, 793.71] 递增 → 最坏（最大）= `[2]`
  - 毂 `SiRm` = Rm/σViMF（两案乘积恒 700 / 1200）**递减** → 最坏（最小）= `[2]`
  - 恒等式可直接当健全性判据：`si[k] = p[k] × 0.0706778839`、`SiRm[k] × sigmaViMF[k] = Rm`。
  - pyffalo 侧（`InterferenceFit` / `MultiInterferenceFit`）统一 `[max, min, mean]` 且安全系数**一律取最坏档**，故对账映射为 `SiRm/SiRe ↔ [2]`、`Sr ↔ si[1]`。下标取错会得 ~1.8 倍假偏差——本次冒烟最初 9 项「不符」全部由此产生。
- **应力符号**：KISSsoft 报幅值（正数），pyffalo 按力学惯例带符号（压应力为负）。轴侧对账取幅值，否则恒差一个负号。
- **死键与派生快照**（四探针钉死：文件变体改 `l` 50→100、`df` 60→80、`Mb` 10→40）：
  - `m01r.pr` ≡ 0.0、`m01r.my` ≡ 0.16 —— 死键，三变体全不变。
  - `m01r.temp` / `tempW` / `tempWM` **不是死键但极易误读**：随 `df` 变（60→80 时 211.30→191.74）、不随 `l` / `Mb` 变，是内核算出的**最大许用温度**（过盈耗尽临界温升），不是输入温度回显。
  - `m01r.Fpress[0..2]` = **压入力 [kN]**（随 `l` 线性：50→100 时 69.59→139.19；随 `df` 反比）。`FpressLMont[0]` = `Fpress[0]` × 0.8125（= 1−3/16，三变体精确恒定，口径未钉死，record 档）。
  - `m01r.faktLMont` = 1.3（压装系数）、`m01r.faktmy` = 1.6（拆卸系数）——pyffalo 侧未移植（其 `K_adhesion` 默认 1.4 是另一套粘着口径，勿混）。
  - `m01sollSi.*` = **许用安全系数设定值**（无量纲，RmW=1.5 / ReN=1.0 / Ru=1.2 / SpW=SpN=1.0，两案恒同）——设计输入非计算结果。KISSsoft 屈服档用 1.0，pyffalo Baseline 默认 1.5（基线可改，非公式差异）。
  - `m01w.tolOut` / `m01n.tolOut` 在模板集内但内核不回吐（毂外径公差带单层无环时不参与计算）。毂外径 `da` 单层算例从 `m01n.da` 读。
- **M010 内核不反算环链**：help 所述「由软件按顺序过盈链计算」是 GUI Definition 工作流（算完写回缓存），文件/COM 路径的外压是直给输入——环层几何/公差/粗糙度改写后对 p0 零影响。直给模式下界面 ≥2 无压力输入，pyffalo 的 `MultiInterferenceFit` 因此把外层环 `Delta` 与 `Ring_S` 显式置 `None`（不产无载假值），与 KISSsoft 报告同样不报环应力——**共同盲区，不是差异**。联立模式（pyffalo 独有，按环层公差带反算）无 KISSsoft 金样可对，只能靠「单层退化逐位 + 耦合解回喂直给模式复现自身」双重自洽校验。
- **M010 专用变量族**：多层件在 `m01allg.fitsCount` 记环层数，`m01n.tolDa_max/min` 记毂外径公差带；直给档的 `m01r.p[0..2]` 与单层件同键同义，可交叉复核两套金样。
