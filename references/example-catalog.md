# KISSsoft 2026 官方算例全量目录（example/ 遍历生成）

> 源：`C:\KISSsoft 2026\example`（371 个文件）。由 `scripts/gen_example_catalog.py` 只读遍历生成（不碰 COM、不占 license 席位）；无 KISSsoft 的机器直接读本档。再生：`python scripts/gen_example_catalog.py [example根]`。
>
> 逐案调用 = COM `LoadFile("<example根>/<文件名>")` **绝对路径**（Z09A 族只认安装目录内路径）；调用配方与机制坑见 SKILL.md 与 references/com-mechanics.md。
> 统计：计算案例 278（47 个模块）、KISSsys 系统档 48（S20×26 + KPRO×22）、附件 45（CSV×8、DUI×6、DXF×1、PCH×1、SKRIPT×11、STEP×12、TXT×6）。

## 模块总表

| 模块 | 内容 | 案例 | pyffalo 对应 | 收割器（scripts/） | 镜像（examples/kisssoft/） |
| --- | --- | --- | --- | --- | --- |
| A10 | 齿轮同步器 | 1 | 未移植（按需） | — | — |
| A20 | 联轴器 | 1 | DiscCouplingEstimate 估算级（精算按需） | — | — |
| F10 | 压簧（圆柱 + 圆锥） | 2 | HelicalCompressionSpring 已覆盖 | — | F010 |
| F20 | 拉伸弹簧 DIN EN 13906-2 | 1 | HelicalTensionSpring 已移植 | gen_extension_spring_kisssoft.py | f020_tension_spring |
| F30 | 腿弹簧 DIN EN 13906-3 | 1 | LegSpring 已移植 | gen_leg_spring_kisssoft.py | f030_leg_spring |
| F40 | 碟形弹簧 | 1 | DiscSpring 已覆盖 | — | F040 |
| F50 | 扭杆弹簧 DIN 2091 | 1 | TorsionBarSpring 已移植 | gen_torsion_bar_kisssoft.py | f050_torsion_bar |
| K10 | 公差计算 | 1 | ToleranceAnalysis 已覆盖 | — | — |
| K12 | FKM 结构件应力分析 | 2 | 未移植（按需） | — | — |
| K14 | 赫兹压力与任意接触（konf 0-9） | 3 | HertzContact 已移植（konf9 二期） | gen_hertz_k14_kisssoft.py | K014、k014_configs |
| K15 | 塑料件管理 | 1 | 未移植（按需） | — | — |
| K17 | 滚珠丝杠直线驱动 | 1 | 未移植（按需） | — | — |
| K19 | DFT 分析合成 | 1 | SignalAnalysis 已覆盖（部分） | — | — |
| K25 | 载荷谱生成 | 3 | SignalAnalysis、RainflowCounting 已覆盖 | — | — |
| M10 | 圆柱过盈连接 | 2 | InterferenceFit 已覆盖 | — | M010 |
| M1B | 圆锥过盈连接（Kollmann / DIN 7190-2） | 3 | ConicalInterferenceFit 已移植 | gen_conical_fit_kisssoft.py | m1b_conical_fit |
| M1C | 剖分轮毂夹紧连接 | 2 | ClampConnection 已移植 | gen_clamp_connection_kisssoft.py | m01c_clamp |
| M2A | 平键 DIN 6892 | 3 | KeyJoint 已移植 | gen_key_joint_kisssoft.py | m02a_keys |
| M2B | 矩形花键 DIN ISO 14 | 1 | SplineShaft 已覆盖 | — | M02B |
| M2C | 花键强度（Niemann） | 1 | InvoluteSpline 族已对齐（金样 pyffalo tests/golden/spline/） | — | — |
| M2D | 多边形轴连接 DIN 32711/12 | 1 | PolygonShaftJoint 已移植 | gen_polygon_shaft_kisssoft.py | m02d_polygon |
| M2E | 半圆键 DIN 6888 | 1 | WoodruffKeyJoint 已移植 | gen_woodruff_key_kisssoft.py | m02e_woodruff |
| M3A | 销连接 | 1 | 未移植（小件按需） | — | — |
| M40 | 螺栓 VDI 2230 | 7 | Bolt、BoltJoint、FlangeBolt 已对齐 | gen_bolt_m40_kisssoft.py、scan_bolt_m40_kisssoft.py | m40_bolt |
| M50 | 挡圈（Seeger，轴用 / 孔用） | 2 | RetainingRing 已覆盖 | — | M050 |
| M60 | Hirth 端面齿盘（Voith 目录） | 2 | HirthCoupling 已移植 | gen_hirth_coupling_kisssoft.py | m060_hirth |
| W10 | 轴（DIN 743 / FKM 强度、Campbell / 临界转速） | 28 | ShaftStrength、ShaftBeam 已移植 | harvest_kisssoft_w10.py | w10_shafts |
| W50 | 深沟球轴承（ISO 281 / TS 16281 寿命链） | 2 | 寿命链并入 DeepGrooveBallBearing | gen_kisssoft_w50.py | W050 |
| W51 | 圆柱滚子轴承（内几何精算） | 3 | 寿命链并入 CylindricalRollerBearing | gen_kisssoft_w50.py | W051 |
| W70 | 径向滑动轴承（ISO 7902 / DIN 31652·57） | 7 | PlainJournalBearing 已移植 | gen_plain_journal_kisssoft.py | w070_plain_journal |
| W7C | 推力滑动轴承（ISO 12130 / DIN 31653·54） | 2 | PlainThrustBearing 已移植 | gen_plain_thrust_kisssoft.py | w07c_plain_thrust |
| Z11 | 圆柱齿轮几何（含 Topping / 实测偏差 / 脚本变体） | 25 | SingleGear、GearPair 已覆盖 | — | — |
| Z12 | 圆柱齿轮承载（ISO 6336 / DIN 3990 / AGMA / API，含修形变体） | 41 | GearPair 已覆盖 | — | — |
| Z13 | 齿条副 | 3 | 未移植（小众按需） | — | — |
| Z14 | 行星轮系（含失准变体） | 4 | PlanetaryGear、PlanetaryGearRatio 已覆盖 | — | — |
| Z15 | 三齿轮轮系（DIN 3990） | 3 | PlanetaryGearRatio 已覆盖 | — | — |
| Z16 | 四齿轮 / 多功率分流 | 4 | PlanetaryGearRatio 已覆盖 | — | — |
| Z17 | 交错轴斜齿轮（Niemann） | 8 | 未移植（小众按需） | — | — |
| Z40 | 扇形 / 非圆齿轮 | 2 | 未移植（小众按需） | — | — |
| Z50 | beveloid 齿轮（冠状修形） | 3 | 未移植（小众按需） | — | — |
| Z60 | 面齿轮 | 2 | 未移植（小众按需） | — | — |
| Z70 | 锥齿轮 / 准双曲面（ISO 10300 / DIN 3991 / AGMA / Klingelnberg） | 26 | BevelGearPair、HypoidGearPair 已移植 | gen_bevel_gear_kisssoft.py、gen_hypoid_gear_kisssoft.py | z070_bevel、z070_hypoid |
| Z80 | 蜗杆副（DIN 3996） | 10 | WormGear 已覆盖（不移植，可对账） | — | — |
| Z90 | V 带传动 | 1 | VBeltDrive 已移植 | gen_v_belt_kdb_kisssoft.py（探针族 kisssoft_com_probe/_scan/_catalog） | Z90 |
| Z91 | 同步带传动（四方法族） | 2 | SynchronousBeltDrive 已移植 | harvest_kisssoft_z91.py | z091_02_toothed_belt、z091_03_toothed_belt_tension_pulley |
| Z92 | 滚子链传动（DIN ISO 10823 / 606） | 1 | RollerChainDrive 已移植 | gen_roller_chain_power_kisssoft.py、parse_kisssoft_kdb.py | Z92 |
| Z9A | 花键（DIN 5480 / ISO 4156 / AGMA 6123 / DIN 5481·5482 齿廓库）（55 案大头为 DIN5481_*/DIN5482_* 齿廓库批量案） | 55 | InvoluteSpline、SplineShaft、SplineAGMA 已对齐 | —（对账期 tmp 探针；金样 pyffalo tests/golden/spline/） | — |
| S20/KPRO | KISSsys 系统级齿轮箱（轴-轴承-箱体刚度耦合 / NVH / 效率） | 48 | 不建议移植（与装配模式 + ANSYS + ROSS 路线重叠） | — | — |

## 逐案清单（模块 × 文件名排序）

### A10 齿轮同步器 —— 1 案

pyffalo：未移植（按需）；收割器：—；镜像：—

- `01 Gear Synchroniser.A10`

### A20 联轴器 —— 1 案

pyffalo：DiscCouplingEstimate 估算级（精算按需）；收割器：—；镜像：—

- `02 Coupling.A20`

### F10 压簧（圆柱 + 圆锥） —— 2 案

pyffalo：HelicalCompressionSpring 已覆盖；收割器：—；镜像：F010

- `01 Compression Spring.F10`
- `02 Conical Compression Spring.F10`

### F20 拉伸弹簧 DIN EN 13906-2 —— 1 案

pyffalo：HelicalTensionSpring 已移植；收割器：gen_extension_spring_kisssoft.py；镜像：f020_tension_spring

- `03 Tension Spring.F20`

### F30 腿弹簧 DIN EN 13906-3 —— 1 案

pyffalo：LegSpring 已移植；收割器：gen_leg_spring_kisssoft.py；镜像：f030_leg_spring

- `04 Leg Spring.F30`

### F40 碟形弹簧 —— 1 案

pyffalo：DiscSpring 已覆盖；收割器：—；镜像：F040

- `05 Disk Spring.F40`

### F50 扭杆弹簧 DIN 2091 —— 1 案

pyffalo：TorsionBarSpring 已移植；收割器：gen_torsion_bar_kisssoft.py；镜像：f050_torsion_bar

- `06 Torsion Bar Spring.F50`

### K10 公差计算 —— 1 案

pyffalo：ToleranceAnalysis 已覆盖；收割器：—；镜像：—

- `01 Tolerance Calculation.K10`

### K12 FKM 结构件应力分析 —— 2 案

pyffalo：未移植（按需）；收割器：—；镜像：—

- `02 Stress Analysis (FKM 62).K12`
- `03 Stress Analysis (FKM 63).K12`

### K14 赫兹压力与任意接触（konf 0-9） —— 3 案

pyffalo：HertzContact 已移植（konf9 二期）；收割器：gen_hertz_k14_kisssoft.py；镜像：K014、k014_configs

- `04 Hertzian Pressure.K14`
- `05 Arbitrary Contact.K14`
- `06 Arbitrary Contact 2.K14`

### K15 塑料件管理 —— 1 案

pyffalo：未移植（按需）；收割器：—；镜像：—

- `07 Linear Drive.K15`

### K17 滚珠丝杠直线驱动 —— 1 案

pyffalo：未移植（按需）；收割器：—；镜像：—

- `09 Plastics Manager.K17`

### K19 DFT 分析合成 —— 1 案

pyffalo：SignalAnalysis 已覆盖（部分）；收割器：—；镜像：—

- `10 Load Spectrum Generator (Time Series to LDD).K19`

### K25 载荷谱生成 —— 3 案

pyffalo：SignalAnalysis、RainflowCounting 已覆盖；收割器：—；镜像：—

- `11 DFT Analysis.K25`
- `12 DFT Synthesis (single-sided).K25`
- `13 DFT Synthesis (double-sided).K25`

### M10 圆柱过盈连接 —— 2 案

pyffalo：InterferenceFit 已覆盖；收割器：—；镜像：M010

- `01 Cylindrical Interference Fit.M10`
- `02 Cylindrical Interference Fit (Outer Rings).M10`

### M1B 圆锥过盈连接（Kollmann / DIN 7190-2） —— 3 案

pyffalo：ConicalInterferenceFit 已移植；收割器：gen_conical_fit_kisssoft.py；镜像：m1b_conical_fit

- `03 Conical Interference Fit.M1B`
- `04 Conical Interference Fit (With Nut).M1B`
- `05 Conical Interference Fit (DIN 7190 2).M1B`

### M1C 剖分轮毂夹紧连接 —— 2 案

pyffalo：ClampConnection 已移植；收割器：gen_clamp_connection_kisssoft.py；镜像：m01c_clamp

- `06 Clamped connections (Split hub).M1C`
- `07 Clamped connections (Split hub lever).M1C`

### M2A 平键 DIN 6892 —— 3 案

pyffalo：KeyJoint 已移植；收割器：gen_key_joint_kisssoft.py；镜像：m02a_keys

- `08 Keys (DIN 6892 Example 1).M2A`
- `09 Keys (DIN 6892 Example 2).M2A`
- `10 Keys (DIN 6892 Example 3).M2A`

### M2B 矩形花键 DIN ISO 14 —— 1 案

pyffalo：SplineShaft 已覆盖；收割器：—；镜像：M02B

- `11 Straight Sided Spline.M2B`

### M2C 花键强度（Niemann） —— 1 案

pyffalo：InvoluteSpline 族已对齐（金样 pyffalo tests/golden/spline/）；收割器：—；镜像：—

- `13 Spline (Strength Only).M2C`

### M2D 多边形轴连接 DIN 32711/12 —— 1 案

pyffalo：PolygonShaftJoint 已移植；收割器：gen_polygon_shaft_kisssoft.py；镜像：m02d_polygon

- `17 Polygon.M2D`

### M2E 半圆键 DIN 6888 —— 1 案

pyffalo：WoodruffKeyJoint 已移植；收割器：gen_woodruff_key_kisssoft.py；镜像：m02e_woodruff

- `18 Woodruff Key.M2E`

### M3A 销连接 —— 1 案

pyffalo：未移植（小件按需）；收割器：—；镜像：—

- `08 Pins.M3A`

### M40 螺栓 VDI 2230 —— 7 案

pyffalo：Bolt、BoltJoint、FlangeBolt 已对齐；收割器：gen_bolt_m40_kisssoft.py、scan_bolt_m40_kisssoft.py；镜像：m40_bolt

- `01 Bolts (VDI 2230 Example 1).M40`
- `02 Bolts (VDI 2230 Example 2).M40`
- `03 Bolts (VDI 2230 Example 3).M40`
- `04 Bolts (VDI 2230 Example 4).M40`
- `05 Bolts (VDI 2230 Example 5).M40`
- `06 Bolts (Flange Connection).M40`
- `07 Bolts (High Temperature).M40`

### M50 挡圈（Seeger，轴用 / 孔用） —— 2 案

pyffalo：RetainingRing 已覆盖；收割器：—；镜像：M050

- `09 Shaft Ring.M50`
- `10 Bore Ring.M50`

### M60 Hirth 端面齿盘（Voith 目录） —— 2 案

pyffalo：HirthCoupling 已移植；收割器：gen_hirth_coupling_kisssoft.py；镜像：m060_hirth

- `11 Hirth (Voith).M60`
- `12 Hirth (Custom).M60`

### W10 轴（DIN 743 / FKM 强度、Campbell / 临界转速） —— 28 案

pyffalo：ShaftStrength、ShaftBeam 已移植；收割器：harvest_kisssoft_w10.py；镜像：w10_shafts

- `01 Shafts.W10`
- `02 Shafts (Flex Pin).W10`
- `03 Shafts.W10`
- `04 Shafts (Campbell Diagram - Jeffcott Rotor).W10`
- `05 Motor Shaft.W10`
- `06 Wind Turbine Main Shaft.W10`
- `07 Truck Transmission.W10`
- `08 Gearbox Output To Generator.W10`
- `09 DCT Transmission Input.W10`
- `10 Turboprop Turbine.W10`
- `11 Marine POD Propulsion.W10`
- `12 Herringbone Gear With Journal Bearings.W10`
- `13 Shafts (Reliability).W10`
- `14 Pinion Shaft for Gear Pair Example 01.W10`
- `15 Gear Shaft for Gear Pair Example 01.W10`
- `16 Pinion Shaft for Gear Pair Example 06a.W10`
- `17 Gear Shaft for Gear Pair Example 06a.W10`
- `18 Pinion Shaft for Bevel Gear Example 10a.W10`
- `19 Gear Shaft for Bevel Gear Example 10a.W10`
- `20 Shafts LS With Different R.W10`
- `21 Shaft with SKF Cloud Services.W10`
- `22 Shaft with Timken Cloud Services.W10`
- `s2_var1.W10`
- `s2_var3.W10`
- `s3_var1.W10`
- `s3_var3.W10`
- `s4_var1.W10`
- `s4_var2.W10`

### W50 深沟球轴承（ISO 281 / TS 16281 寿命链） —— 2 案

pyffalo：寿命链并入 DeepGrooveBallBearing；收割器：gen_kisssoft_w50.py；镜像：W050

- `01 Deep Groove.W50`
- `02 Tapered Roller.W50`

### W51 圆柱滚子轴承（内几何精算） —— 3 案

pyffalo：寿命链并入 CylindricalRollerBearing；收割器：gen_kisssoft_w50.py；镜像：W051

- `03 Deep Groove (Inner Geometry).W51`
- `04 Deep Groove (Fine Sizing).W51`
- `05 Cylindrical Roller (Inner Geometry).W51`

### W70 径向滑动轴承（ISO 7902 / DIN 31652·57） —— 7 案

pyffalo：PlainJournalBearing 已移植；收割器：gen_plain_journal_kisssoft.py；镜像：w070_plain_journal

- `07 Plain Journal Bearing (ISO 7902).W70`
- `08 Plain Journal Bearing (ISO 7902 Low Speed).W70`
- `09 Plain Journal Bearing (Niemann High Speed).W70`
- `10 Plain Journal Bearing (Spiegel Grease).W70`
- `11 Plain Journal Bearing (DIN 31652).W70`
- `12 Plain Journal Bearing (DIN 31657).W70`
- `15 Plain Journal Bearing (ISO 7902 incl. analytic).W70`

### W7C 推力滑动轴承（ISO 12130 / DIN 31653·54） —— 2 案

pyffalo：PlainThrustBearing 已移植；收割器：gen_plain_thrust_kisssoft.py；镜像：w07c_plain_thrust

- `13 Plain Thrust Bearing (DIN 31653).W7C`
- `14 Plain Thrust Bearing (ISO 12130, DIN 31654).W7C`

### Z11 圆柱齿轮几何（含 Topping / 实测偏差 / 脚本变体） —— 25 案

pyffalo：SingleGear、GearPair 已覆盖；收割器：—；镜像：—

- `01 Spur.Z11`
- `01a Spur (Topping Tool).Z11`
- `02 Spur Plastic.Z11`
- `03 Helical (Form Grinding).Z11`
- `04 Spur (Grinding Notch).Z11`
- `05 Spur (Protuberance).Z11`
- `06 Helical (Protuberance EV S1G1).Z11`
- `07 Helical (Semi Topping EV S1G2).Z11`
- `08 Helical (Short Lead Hobbing).Z11`
- `08a Helical (Short Lead Hobbing and Grinding).Z11`
- `09 Inner (Gear With Shaper).Z11`
- `10 Helical (PSK EV S2G1).Z11`
- `11 Spur (PSK Internal Hub).Z11`
- `12 Helical (Honing EV S2G1).Z11`
- `13 Spur (Dressing Disc).Z11`
- `14 Helical (Dressing Disc HCR).Z11`
- `15 Helical (Twist EV S1G1).Z11`
- `16 Helical (Tolerance Band from GAMA).Z11`
- `17 Helical (Hobbing Process and Rollout).Z11`
- `18 Spur (Profile Milling).Z11`
- `20 Helical (Asymmetric).Z11`
- `21 Straight Flank (Park Lock).Z11`
- `22 Spur (Elliptic Root With Hob).Z11`
- `23 Spur (Sprocket DXF).Z11`
- `24 Spur (Tooth Form Steps).Z11`

### Z12 圆柱齿轮承载（ISO 6336 / DIN 3990 / AGMA / API，含修形变体） —— 41 案

pyffalo：GearPair 已覆盖；收割器：—；镜像：—

- `01 Spur (ISO 6336).Z12`
- `01a Spur (Topological Modification).Z12`
- `01b Spur (Elliptic root).Z12`
- `01c Spur (Measured Deviation).Z12`
- `01d Spur (Script).Z12`
- `02 Deep Tooth Form (Plastic).Z12`
- `03 Double Helical Speed Increaser.Z12`
- `04 Inner (VDI 2737 Example).Z12`
- `05 Spur Plastic (VDI 2545).Z12`
- `06 Helical (DIN 3990).Z12`
- `06a Helical With Shafts (DIN 3990).Z12`
- `07 Helical (AGMA 2001).Z12`
- `08 Gear Pump External.Z12`
- `09 Spur With Premachining (Grinding).Z12`
- `09a Spur With Premachining (Short Lead).Z12`
- `10 Helical (API 613).Z12`
- `11 Helical With Flank Fracture (ISO 6336).Z12`
- `12 Spur Plastic (VDI 2736 Example 1 Dry Run).Z12`
- `13 Helical (GOST 21354-87 Appendix 11).Z12`
- `14 Spur Sintered (Bending SN Curve From File).Z12`
- `15 Asymmetric (ISO 6336).Z12`
- `16 Helical (Time Series to LDD).Z12`
- `17 FZG Test A-83-90 Stage 12 (ISO 14635-1).Z12`
- `18 FZG Test A10-166-120 Stage 10 (ISO 14635-2).Z12`
- `19 Helical (EV S1).Z12`
- `20 Helical (EV S2).Z12`
- `21 Helical (Waviness Simulation Hobbing).Z12`
- `FZG Test A-24_9-120 Stage12 (DIN3990-4).Z12`
- `FZG Test A-8_3-90 Stage12 (DIN3990-4).Z12`
- `FZG Test A10-16_6-120 Stage12 (DIN3990-4).Z12`
- `test_gears.Z12`
- `z1z2_V0_ReferenceVariant.Z12`
- `z1z2_V1_MacroMicroOpt.Z12`
- `z3z4_V0_ReferenceVariant.Z12`
- `z3z4_V1_MacroMicroOpt.Z12`
- `z3z4_calc_var1.Z12`
- `z3z4_calc_var2.Z12`
- `z3z4_calc_var3.Z12`
- `z5z6_calc_var1.Z12`
- `z5z6_calc_var2.Z12`
- `z5z6_calc_var3.Z12`

### Z13 齿条副 —— 3 案

pyffalo：未移植（小众按需）；收割器：—；镜像：—

- `01 Spur Rack and Pinion.Z13`
- `02 Helical Rack And Pinion.Z13`
- `03 Double Helical Rack And Pinion (Asymmetric).Z13`

### Z14 行星轮系（含失准变体） —— 4 案

pyffalo：PlanetaryGear、PlanetaryGearRatio 已覆盖；收割器：—；镜像：—

- `01 Spur Planetary (ISO 6336).Z14`
- `01a Spur Planetary (Misalignment).Z14`
- `02 Spur Planetary (AGMA 2101).Z14`
- `03 Helical Planetary (Annex E Shaft For Planet).Z14`

### Z15 三齿轮轮系（DIN 3990） —— 3 案

pyffalo：PlanetaryGearRatio 已覆盖；收割器：—；镜像：—

- `01 Three Gears (DIN 3990).Z15`
- `02 Three Gears Plastic (VDI 2736).Z15`
- `03 Three gears (GMF).Z15`

### Z16 四齿轮 / 多功率分流 —— 4 案

pyffalo：PlanetaryGearRatio 已覆盖；收割器：—；镜像：—

- `04 Double Pinion Planetary (3 power paths).Z16`
- `04 Four Gears (ISO 6336).Z16`
- `05 Double Pinion Planetary (5 power paths).Z16`
- `06 Double Pinion Planetary (6 power paths).Z16`

### Z17 交错轴斜齿轮（Niemann） —— 8 案

pyffalo：未移植（小众按需）；收割器：—；镜像：—

- `01 Helical (Niemann).Z17`
- `02 Worm Plastic (VDI 2545).Z17`
- `03 Helical (Geometry).Z17`
- `04 Worm (Thickness Optimization).Z17`
- `05 Worm Plastic (VDI 2736 Example 1).Z17`
- `06 Worm Plastic (VDI 2736 Example 2).Z17`
- `07 Power Skiving (for 10 Helical PSK).z17`
- `10 Pinion And Rack.Z17`

### Z40 扇形 / 非圆齿轮 —— 2 案

pyffalo：未移植（小众按需）；收割器：—；镜像：—

- `01 Continuous rotation.Z40`
- `02 Sector Gear.Z40`

### Z50 beveloid 齿轮（冠状修形） —— 3 案

pyffalo：未移植（小众按需）；收割器：—；镜像：—

- `01 Spur Beveloid (Crowning).Z50`
- `02 Helical Beveloid.Z50`
- `03 Spur Beveloid (Zero Backlash).Z50`

### Z60 面齿轮 —— 2 案

pyffalo：未移植（小众按需）；收割器：—；镜像：—

- `01 Face Gear.Z60`
- `02 Face Gear (Offset and Shaft Angle).Z60`

### Z70 锥齿轮 / 准双曲面（ISO 10300 / DIN 3991 / AGMA / Klingelnberg） —— 26 案

pyffalo：BevelGearPair、HypoidGearPair 已移植；收割器：gen_bevel_gear_kisssoft.py、gen_hypoid_gear_kisssoft.py；镜像：z070_bevel、z070_hypoid

- `01 Bevel (KN 3028 FH).z70`
- `02 Hypoid (ISO 10300 FH).z70`
- `03 Bevel (DIN 3991 FH).z70`
- `04 Bevel (Differential Static).z70`
- `04a Bevel (Differential ISO 10300 Tooth Form).z70`
- `04b Bevel (Differential ISO 10300 Modified Static).z70`
- `04c Bevel (Differential Spherical Involute).z70`
- `05 Bevel (AGMA 2003 FM).z70`
- `06 Bevel (Straight Fig 1).z70`
- `06a Bevel With Shafts For CA (Straight Fig 1).z70`
- `07 Bevel (AGMA 929 Annex C Example FM).Z70`
- `08 Bevel (KN 3025 Palloid FH).Z70`
- `09 Hypoid (KN 3026 Palloid FH).Z70`
- `10 Hypoid (KN 3029 Zyklo Palloid FH).Z70`
- `11 Hypoid (GEMS Example 1 FM).Z70`
- `12 Bevel (GEMS Example 2 FM).Z70`
- `13 Hypoid (GEMS Example 1 FH).Z70`
- `14 Bevel (GEMS Example 2 FH).Z70`
- `15 Bevel (DNVGL-CG-0036_2019).Z70`
- `BevelGear 1 (Face Hobbing).z70`
- `S01 Bevel (ISO 10300 Sample 1 FM).Z70`
- `S02 Hypoid (ISO 10300 Sample 2 FM).Z70`
- `S03 Hypoid (ISO 10300 Sample 3 FH).Z70`
- `S04 Hypoid (ISO 10300 Sample 4 FH).Z70`
- `S05 Hypoid (ISO 23509 Sample 5 FH).Z70`
- `S06 Bevel (ISO 23509 Sample 6).Z70`

### Z80 蜗杆副（DIN 3996） —— 10 案

pyffalo：WormGear 已覆盖（不移植，可对账）；收割器：—；镜像：—

- `01 Worm (DIN 3996 Example 1).Z80`
- `02 Worm (DIN 3996 Example 2).Z80`
- `03 Worm (DIN 3996 Example 3).Z80`
- `04 Worm (EDIN 3996-2018 Example 1).Z80`
- `05 Worm (EDIN 3996-2018 Example 2).Z80`
- `06 Worm (EDIN 3996-2018 Example 3).Z80`
- `07 Worm (ISO TS 14521 Example 1).Z80`
- `08 Worm (ISO TS 14521 Example 2).Z80`
- `09 Worm (ISO TS 14521 Example 3).Z80`
- `10 Worm (AGMA 6135).Z80`

### Z90 V 带传动 —— 1 案

pyffalo：VBeltDrive 已移植；收割器：gen_v_belt_kdb_kisssoft.py（探针族 kisssoft_com_probe/_scan/_catalog）；镜像：Z90

- `01 V Belt.Z90`

### Z91 同步带传动（四方法族） —— 2 案

pyffalo：SynchronousBeltDrive 已移植；收割器：harvest_kisssoft_z91.py；镜像：z091_02_toothed_belt、z091_03_toothed_belt_tension_pulley

- `02 Toothed Belt.Z91`
- `03 Toothed Belt (Tension Pulley).Z91`

### Z92 滚子链传动（DIN ISO 10823 / 606） —— 1 案

pyffalo：RollerChainDrive 已移植；收割器：gen_roller_chain_power_kisssoft.py、parse_kisssoft_kdb.py；镜像：Z92

- `04 Chain Drive.Z92`

### Z9A 花键（DIN 5480 / ISO 4156 / AGMA 6123 / DIN 5481·5482 齿廓库）（55 案大头为 DIN5481_*/DIN5482_* 齿廓库批量案） —— 55 案

pyffalo：InvoluteSpline、SplineShaft、SplineAGMA 已对齐；收割器：—（对账期 tmp 探针；金样 pyffalo tests/golden/spline/）；镜像：—

- `12 Spline (DIN 5480).Z9a`
- `12a Curved tooth coupling (DIN 5480).Z9a`
- `14 Spline (ANSI B92 1).Z9A`
- `15 Spline (ISO 4156 With Resistance).Z9A`
- `16 Spline (AGMA 6123).Z9a`
- `DIN5481_10x12_a11-A11_fein.Z9A`
- `DIN5481_12x14_a11-A11_fein.Z9A`
- `DIN5481_15x17_a11-A11_fein.Z9A`
- `DIN5481_17x20_a11-A11_fein.Z9A`
- `DIN5481_21x24_a11-A11_fein.Z9A`
- `DIN5481_26x30_a11-A11_fein.Z9A`
- `DIN5481_30x34_a11-A11_fein.Z9A`
- `DIN5481_36x40_a11-A11_fein.Z9A`
- `DIN5481_40x44_a11-A11_fein.Z9A`
- `DIN5481_45x50_a11-A11_fein.Z9A`
- `DIN5481_50x55_a11-A11_fein.Z9A`
- `DIN5481_55x60_a11-A11_fein.Z9A`
- `DIN5481_7x8_a11-A11_fein.Z9A`
- `DIN5481_8x10_a11-A11_fein.Z9A`
- `DIN5482_100x94_e9-H10.Z9A`
- `DIN5482_15x12_e9-H10.Z9A`
- `DIN5482_17x14_e9-H10.Z9A`
- `DIN5482_18x15_e9-H10.Z9A`
- `DIN5482_20x17_e9-H10.Z9A`
- `DIN5482_22x19_e9-H10.Z9A`
- `DIN5482_25x22_e9-H10.Z9A`
- `DIN5482_28x25_e9-H10.Z9A`
- `DIN5482_30x27_e9-H10.Z9A`
- `DIN5482_32x28_e9-H10.Z9A`
- `DIN5482_35x31_e9-H10.Z9A`
- `DIN5482_38x34_e9-H10.Z9A`
- `DIN5482_40x36_e9-H10.Z9A`
- `DIN5482_42x38_e9-H10.Z9A`
- `DIN5482_45x41_e9-H10.Z9A`
- `DIN5482_48x44_e9-H10.Z9A`
- `DIN5482_50x45_e9-H10.Z9A`
- `DIN5482_52x47_e9-H10.Z9A`
- `DIN5482_55x50_e9-H10.Z9A`
- `DIN5482_58x53_e9-H10.Z9A`
- `DIN5482_60x55_e9-H10.Z9A`
- `DIN5482_62x57_e9-H10.Z9A`
- `DIN5482_65x60_e9-H10.Z9A`
- `DIN5482_68x62_e9-H10.Z9A`
- `DIN5482_70x64_e9-H10.Z9A`
- `DIN5482_72x66_e9-H10.Z9A`
- `DIN5482_75x69_e9-H10.Z9A`
- `DIN5482_78x72_e9-H10.Z9A`
- `DIN5482_80x74_e9-H10.Z9A`
- `DIN5482_82x76_e9-H10.Z9A`
- `DIN5482_85x79_e9-H10.Z9A`
- `DIN5482_88x82_e9-H10.Z9A`
- `DIN5482_90x84_e9-H10.Z9A`
- `DIN5482_92x86_e9-H10.Z9A`
- `DIN5482_95x89_e9-H10.Z9A`
- `DIN5482_98x92_e9-H10.Z9A`

### KPRO KISSsys 工程模板（与 .S20 系统模型配套） —— 22 案

pyffalo：不建议移植（同 S20）；收割器：—；镜像：—

- `Automotive.kpro`
- `Bearings.kpro`
- `Belts and Chains.kpro`
- `Bevel and Hypoid gears.kpro`
- `Beveloid gears.kpro`
- `Connections.kpro`
- `Crossed helical gears.kpro`
- `Face gears.kpro`
- `Gear pair.kpro`
- `Non circular gears.kpro`
- `Pinion with rack.kpro`
- `Planetary gear.kpro`
- `Shaft-Hub-Connections (only DIN 5481).kpro`
- `Shaft-Hub-Connections (only DIN 5482).kpro`
- `Shaft-Hub-Connections.kpro`
- `Shafts.kpro`
- `Single gear.kpro`
- `Springs.kpro`
- `Systems.kpro`
- `Three and four gears train.kpro`
- `Various.kpro`
- `Worms with enveloping worm wheel.kpro`

### S20 KISSsys 系统级齿轮箱（轴-轴承-箱体刚度耦合 / NVH / 效率）（.S20 系统模型与 .kpro 工程模板成对） —— 26 案

pyffalo：不建议移植（与装配模式 + ANSYS + ROSS 路线重叠）；收割器：—；镜像：—

- `01 Cylindrical Gear Stage.S20`
- `02 Three Gear Train.S20`
- `03 Planetary Gear Stage.S20`
- `04 Compound Planetary Gearbox.S20`
- `04a Compound Planetary Gearbox (stationary pin with power split).S20`
- `05 Two Speed Gearbox.S20`
- `06 EV Transmission (Housing and Gearbody).S20`
- `06a EV Transmission (Forced response).S20`
- `07 EV Planetary Transmission.S20`
- `08 Hypoid Rear Axle Gearbox.S20`
- `08a Hypoid Rear Axle Gearbox (stiffness matrix differential pinion).S20`
- `09 Tractor Gearbox.S20`
- `10 Bicycle Planetary Gearbox.S20`
- `11 Power Split Gearbox.S20`
- `12 Double Helical Highspeed Gearbox.S20`
- `13 Integral Compressor Highspeed Gearbox.S20`
- `14 Bevel Helical Planetary Gearbox.S20`
- `15 Bevel Cylindrical Gearbox.S20`
- `15a Bevel Cylindrical Gearbox (Variants).S20`
- `16 Wind Turbine Gearbox.S20`
- `17 Twin Engine Helicopter Gearbox.S20`
- `18 Five Stage Fine Pitch Gearbox.s20`
- `19 Worm Stage.s20`
- `20 Crossed Helical Stage.s20`
- `21 Lightweight Planetary Differential.S20`
- `22 Timing Gears Formula1.S20`

