# 模块 → 脚本 → 落点 索引

金样 / 快照路径均相对 pyffalo checkout 根（由 `scripts/pyffalo_root.py` 解析）。「权威文档」= pyffalo 仓内该模块公式链与机制坑的记录处；本表不复制内容，只给坐标。

| 模块 | 脚本（scripts/） | pyffalo 组件 | 金样 / 快照 | 权威文档 |
| --- | --- | --- | --- | --- |
| Z90 V 带 | gen_v_belt_kdb_kisssoft.py（DinIdK 四标量 COM 扫描）；kisssoft_com_probe / _scan / _catalog.py（探针 / 18 工况扫描 / 目录扫描） | VBeltDrive | `tools/data/kisssoft/v_belt_kdb.csv`、`tools/data/z90_dat/` | docs/specs/vbelt-z90.md、vbelt-z90-m2.md |
| Z91 同步带 | harvest_kisssoft_z91.py（KDB Z091NORM + dat 插值表离线收割） | SynchronousBeltDrive | `tools/data/belt_sync_source.json.gz`、`tests/golden/synchronous_belt/` | docs/specs/synchronous-belt.md、sync-belt-pulley-3d.md |
| Z92 滚子链 | parse_kisssoft_kdb.py（Z092TYP 快照）、gen_roller_chain_power_kisssoft.py（功率断点 COM 扫描，`--dry-run` 离线） | RollerChainDrive | `tools/data/kisssoft/roller_chain_{profiles,power_curve}.csv` | docs/specs/roller-chain.md、roller-chain-m2.md |
| W10 轴强度 | harvest_kisssoft_w10.py（probe / section / scan-shoulder / scan-const / scan-size / scan-surface） | ShaftStrength、ShaftBeam | `tools/data/din743/*`、`tests/golden/shaft_strength/` | docs/specs/shaft-strength-w10.md |
| W50/W51 轴承寿命 | gen_kisssoft_w50.py（金样 + aISO/eC 曲面扫描） | DeepGrooveBallBearing / CylindricalRollerBearing / TaperRollerBearing | `tests/golden/bearing_life/` | docs/specs/bearing-life-w50w51.md |
| W70/W7C 滑动轴承 | gen_plain_journal_kisssoft.py、gen_plain_thrust_kisssoft.py（均带 `--scan` 特性扫描） | PlainJournalBearing、PlainThrustBearing | `tools/data/plain_bearing/*.json.gz`、`tests/golden/plain_bearing/` | docs/specs/plain-bearing.md |
| K14 赫兹接触 | gen_hertz_k14_kisssoft.py（`--scan` δ 扫描存证） | HertzContact | `tools/data/hertz_k14/norden_scan.json`、`tests/golden/hertz/` | docs/specs/k14-hertz.md |
| M40 螺栓 VDI 2230 | gen_bolt_m40_kisssoft.py（金样）、scan_bolt_m40_kisssoft.py（63+ 变体标定扫描） | Bolt、BoltJoint、FlangeBolt | `tools/data/bolt/m40_scan.json.gz`、`tests/golden/bolt/` | docs/specs/bolt-kisssoft-m40.md |
| M60 Hirth 齿盘 | gen_hirth_coupling_kisssoft.py（`--profile` 目录 99 行快照） | HirthCoupling | `tools/data/hirth_coupling/voith_profile.csv`、`tests/golden/hirth_coupling/` | docs/specs/hirth-serration-m60.md |
| M1B 圆锥过盈 | gen_conical_fit_kisssoft.py | ConicalInterferenceFit | `tests/golden/conical_fit/` | docs/specs/conical-interference-fit-m1b.md |
| M1C 夹紧连接 | gen_clamp_connection_kisssoft.py（**新收割器标准骨架**） | ClampConnection | `tests/golden/clamp_connection/` | docs/specs/clamp-connection-m1c.md |
| M2A 平键 | gen_key_joint_kisssoft.py（`--scan-klambda` 672×2 曲面、`--profile` DIN 6885 剖面） | KeyJoint | `tools/data/key_joint/`、`tests/golden/key_joint/` | docs/specs/key-joint-m2a.md |
| M2D 多边形轴 | gen_polygon_shaft_kisssoft.py（`--sections` 截面量 + Wp 扫描、`--profile` DAT 剖面） | PolygonShaftJoint | `tools/data/polygon_shaft/`、`tests/golden/polygon_shaft/` | docs/specs/polygon-shaft-m2d.md |
| M2E 半圆键 | gen_woodruff_key_kisssoft.py（`--scan-dt` 288 行、`--profile` DAT 剖面） | WoodruffKeyJoint | `tools/data/woodruff_key/`、`tests/golden/woodruff_key/` | docs/specs/woodruff-key-m2e.md |
| Z70 锥齿轮 / 准双曲面 | gen_bevel_gear_kisssoft.py、gen_hypoid_gear_kisssoft.py | BevelGearPair、HypoidGearPair | `tests/golden/bevel_gear/`、`tests/golden/hypoid_gear/` | docs/specs/bevel-hypoid-z70.md |
| F20 拉伸弹簧 | gen_extension_spring_kisssoft.py（`--scan-wire` 线材松弛 LSQ、`--golden`） | HelicalTensionSpring | `tools/data/spring_wire/wire_harvest.json`、`tests/golden/extension_spring/` | docs/specs/extension-spring-f20.md |
| F30 腿簧 | gen_leg_spring_kisssoft.py | LegSpring | `tests/golden/leg_spring/` | docs/specs/leg-spring-f30.md |
| F50 扭杆弹簧 | gen_torsion_bar_kisssoft.py | TorsionBarSpring | `tests/golden/torsion_bar_spring/` | docs/specs/torsion-bar-f50.md |
| 例库镜像 | gen_kisssoft_examples.py（官方算例 → `examples/kisssoft/`，`--run` 逐例验证） | — | `examples/kisssoft/**` | docs/specs/kisssoft-examples.md |

## 无常驻收割器的模块（对账经一次性探针，记录在 pyffalo 文档）

| 模块 | 说明 | 金样 | 权威文档 |
| --- | --- | --- | --- |
| Z09A / M02B / M02C 花键 + AGMA 6123 | 对账期探针为 tmp 一次性脚本（`spline_com_dump*.ps1` 等，tmp 不入库，重跑再生） | `tests/golden/spline/kisssoft_spline.json` | docs/KISSSOFT.md「花键专项对账」「AGMA 6123-C16 专项」 |
| M010 多层过盈 | 探针在 pyffalo tmp/spline_recon（M010 对账会话）；内核外压直给口径已钉死 | `tests/golden/interference_fit_multi/kisssoft_m010_02.json` | docs/specs/multi-interference-fit.md |
| DIN 5466 | step-0 探针走通后**缓建**（无 ground truth） | — | docs/KISSSOFT.md「DIN 5466 路径」 |

后续新模块的收割器**写进本仓 scripts/ 并更新本表**，不再回 pyffalo tools/。
