# R7-D 非对称交易周期设计（entry 快 / exit 慢）

> 作者：strategist（fork 任务）· 日期 2026-11-09
> 约束：team/harness.py 只读，本文件含 patch 草案但不改动 harness；只写本文件；
> 允许小窗口冒烟验证语义（已做，只读分析，无全量跑批）。
> 通用口径（全部实验组锁定）：amihud_60 / N=4 / 主板（剔688/689/北交所/创业板）/
> 市值 5~30 分位 / ADV>500万 / TP45（t收盘触发→t+1收盘卖出）/
> fresh5万 / realistic整手 lot100 slip0.002 / full300相位0 / warmup2024。
> 冻结基线：BASE_R30（R30）fresh +102.07%（挑战线）；BASE_R7（R7）fresh +63.5%，
> Gross +99.0% vs R30 Gross +117.0%（ΔGross 缺口 18pp）；R7-A2 已冻结，不许再调。

---

## 0. 一句话动机

R7 的病不在“看得太勤”，而在“卖得太勤”：2026 年 R7 信号周间交集均值 77%（14天68% / 21天58% / 28天53%，见 §8），每周全仓清仓等于为 23% 的信号增量支付 100% 的双边成本。R7-A2 证明“精选跳过”有效，但走到了另一个极端（全年只执行 2~4 次切换、期末 82% 现金，属于“赚了就躺”）。R7-D 把 entry 与 exit 解耦：entry 保持 R7 的发现速度，exit 按信号寿命慢放，用结构化的慢退出替代 U 值的一刀切跳过。

---

## 1. 四组实验（entry 统一 R7，exit 分档）

- D1：entry R7 + exit R7（持有满7天整批到期）。语义对照组：必须复现 BASE_R7（Δ≤0.5pp），否则实现有 bug。1 条 spec。
- D2：entry R7 + exit R14（持有满14天到期）。退出周期x2。1 条 spec。
- D3：entry R7 + exit R21（持有满21天到期）。退出周期x3。1 条 spec。
- D4：entry R7 + signal-based 退出（信号死亡才卖，见 §3）。K=8 一档（D4a）+ K=12 一档（D4b）。2 条 spec。

共 5 条 spec，4 组。D2/D3 到期卖出按每只票独立 entry 时间计时（不是整组合到期），D4 无固定到期、只按 §3 死亡判定 + §5 max_hold 熔断。

预期排序（先验假设，错了就认）：换手 D1 > D2 > D3 ≈ D4；Gross 未知，靠 §10 验收。

---

## 2. Entry 规则（四组完全一致）

1. Entry 网格：full300 锚点、每 7 个交易日一个信号日 t（与现有 grid_positions R=7 一致），执行日 t+1 收盘买入。
2. 选股：picks_at(t) Top4（amihud_60，现有 one_pick 逻辑，只用 t 及以前数据）。
3. 买入集合 = Top4 减去当前持仓（无论退出组是什么，新出现即买，不做 U/overlap 门控——门控是 A2 路线，D 路线 entry 不设门，保持发现速度纯粹）。
4. 单票目标权重等权（见 §4）。若在仓 4 只全未到期且 Top4 全是新面孔，则本次只买入资金允许范围内的前 M 只（按排名顺位），剩余顺延至下次 entry。该顺延必须计入 asym_deferred_buys 日志。

---

## 3. Exit 规则（卖出触发全集与优先级）

触发全集（按判定优先级排序，高优先先挂 pending）：

1. 风险退出（本设计不启用 trailing/fixed，字段留 None；若未来启用，走现有 daily 判断，优先级最高，与现有 simulate (1) 段顺序一致）。
2. TP45：现有 exit.take_profit=0.45 复用——每日收盘判断（tp_trigger=close）、t 触发→t+1 收盘卖出（stop_exec=next）。TP 卖出后资金留现金，不立即补仓（现有语义：等下一 entry 日）。
3. max_hold_days 到期：复用现有 exit.max_hold_days（daily 计数器 (pos - h[pos]) >= H，pending next 卖出，reason=max_hold_days）。H 见 §5。
4. 信号死亡卖出（R7-D 新增，调仓执行日通道判定，reason=signal_death）：
   D1/D2/D3：持仓年龄 age = 执行日 − 建仓执行日 ≥ exit_R（7/14/21）即死亡。年龄用执行日计数（与 h[pos] 同口径，pos 是执行日），无未来函数。
   D4a/D4b：在 exit 执行日（沿用 entry 网格日，即每 7 天检查一次）计算 ranked_order(t)（t=信号日=执行日−1，只用 t 及以前数据）：持仓票因子排名 > K（K=8 / 12）即死亡，t+1 收盘卖出。判定是单次制（一次跌出即卖，不做二次确认；确认制列为失败后备选，不预跑，理由见 §11-R3）。
5. 期末强制清算：eval_end 日收盘后，对仍持有头寸按现实费率估算清算成本并从净值扣除（现有 equity 已含市值，验收时 reported_total − liq_cost = forced_total，规则B；A2 实测差值 <0.6pp，D 系列沿用同一算法）。

交互顺序（沿用现有 simulate 先后顺序，不新增时序语义）：每日先执行 pending（TP/max_hold 到期单，(0)段），再做 exit/entry 判定（(2)段）。同一标的同日既触发 TP 又信号死亡 → TP 先挂 pending，调仓段先清 pending 再处理信号死亡集合（天然去重：已卖出者移出 holds，不会 double-sell）。

---

## 4. 买入资金来源与权重公式（与 gate-partial 逻辑一致）

- 资金池 = 空闲现金 + 本执行日卖出所得（信号死亡 + 到期 + TP pending 已在 (0) 段落袋的部分）。不卖出保留仓去凑钱（慢退出的意义就是不制造卖出）。
- 目标：等权。设本执行日目标持有集合 T（含保留 R 与新买 B），|T| = k（D1/D2/D3 稳态 k=4；D4 及 TP 缺口期 k 可能 <4，缺口即低暴露，设计内成本）：per = eq_before × expo(1.0) × vol_scale × (1/k) / budget_pad。其中 eq_before = 调仓前权益（现金+持股市值），与现有 gate-partial 分支（harness simulate“部分调仓按调仓前权益定等权目标”注释）完全一致；全量换仓（D1 首建/整批到期重合日）沿用 budget = cash × …（两者数学等价，现金约等于权益时一致，保持与 BASE 的可比性）。
- 整手：sh = floor(per/px/100)×100，sh≤0 跳过；notional+fee>cash 时按 min(per, cash/budget_pad) 重算一次，再不够则跳过并计 asym_skipped_buys（现有 (2) 段买入逻辑原文复用，一字不改）。
- 单票权重上限 mw：沿用 selector.max_weight（本批 None，不启用）。

---

## 5. max_hold_days：三选一论证（28 / 42 / 63 → 选 42 为主）

只读信号层实测（2026 窗口，R7 网格 29 段，amihud_60 Top4）：入选票存续（留在 Top8 内）分布为 7天档19 / 14天档14 / 21天档14 / 28天档10 / 35天档10 / 42天档9 / 49天档10 / 56天档5 / 63天档6 / ≥70天档19（n=120）。中位存续约 28~35 天，16% 在 7 天内死亡，16% 存活超 70 天（右偏长尾）。Top12 分布基本相同（±1 计数）。

- 28 太短：中位处一刀切，约半数自然存续被提前终结，叠加 TP45 后实际持有期更短，退化成“R28 全量+TP”，失去非对称意义；且 28 天档本身是个小波峰（10/120），在波峰处设卡会制造人为换手。
- 63 太长：右尾（≥70天档 16%）本质是幸存者 + 2026 牛市 regime 的混合体；OOS 熊市（2024式 −30%）下 63 天无熔断暴露过大；且与 D4 signal-based 语义冲突（长尾票本应由排名死亡接管，63 天 cap 近乎虚设）。
- 42 选中：覆盖约 75% 自然存续分位；= 6 个 entry 周期 = 2 个 R21 周期 = 1.5 个 R30 周期，与 TP45 形成“时间×空间”双熔断（TP 管盈利兑现，42天管时间价值衰减）；D4a/b 的死亡判定若因排名抖动漏杀，42 天兜底。

执行：exit.max_hold_days=42（复用现有字段与 daily/pending 链路，零新代码）。28/63 列为敏感性附录（各 1 条，不在本批 5 条内；仅当 D4 主结果进入三关后才跑）。

---

## 6. 新买入与慢退出持仓的权重再平衡规则

1. 只买不调：保留仓不做再平衡卖出（任何再平衡卖出都等于重造换手，与立项目标自相矛盾）。权重漂移（某票涨成 40%）不处理——这是慢退出的已知代价，由 max_single_name_pnl_share / top3 归因表显式披露，不藏。
2. 新买入按 §4 per 等权买入；若保留 3 只 + 新买 1 只，新票目标 = 组合 1/4（按 eq_before 计），不存在 gate-partial 修复前的“N倍低配”bug（已在 harness 现有 partial 分支修复，D 沿用）。
3. TP 缺口期（某票止盈后现金闲置到下次 entry）：k<4，per 按实际 k 计算，新票买得稍大，自动回补暴露——这是期望行为，不是 bug。
4. 上限保护：若保留 4 只全未到期且 Top4 全新（极端 regime 切换），本次新买入上限 = 可用资金允许只数（按排名顺位截断），截断名单写入 asym_deferred_buys，下次 entry 优先补（仍按当时信号重算，不保留过期名单）。

---

## 7. 无未来函数论证（逐项）

- entry picks picks_at(t)：close/volume/amount/shares ≤t，adv20/shares 快照（已知局限）。现有 one_pick，t 日收盘及以前。
- exit 排名 ranked_order(t)：同一因子行，t 日截面排名。现有函数，t 及以前。
- 年龄 age：执行日计数器 pos − h[pos]，h[pos] 为建仓执行日。计数器，无价格未来信息。
- TP45 / max_hold 触发：t 日收盘价 vs 建仓价/最高价。现有 (1) 段，t 收盘触发。
- 执行价：close_ff[pos]（t+1 收盘，停牌 ffill 沿用现有 suspend_exec=ffill）。现有 (0)/(2) 段，不用 t+1 开盘。
- 设计期 dwell/overlap 统计（§8）：只用于选 exit_R/max_hold 参数，执行代码零引用，决策零输入。

shares 当前快照前视、幸存者偏差、无 ST 过滤——与 BASE 完全同源同偏，只做组间比较时偏差方向一致，不单独修正（沿用主台账风险声明）。

---

## 8. 只读验证摘要（本设计已做的两个无写盘分析）

方法：sys.path.insert(0,team) 后 import harness as H，bundle() + picks_at/ranked_order/universe_matrix，2026 窗口，未写任何文件（harness.py 未动）。

1. 信号重叠（29 个 R7 信号日）：Top4 交集均值 7天77% / 14天68% / 21天58% / 28天53%。→ 每周全换为 23% 增量付 100% 成本，D2/D3 有信号基础。
2. 存续分布（120 票次，前 30 信号日起始跟踪 70 天）：见 §5 表。→ max_hold=42 覆盖约75%分位；K=8/12 分布几乎一致，D4a/b 差异将主要来自中段票，预期两者 Gross 接近、换手 D4a 略低。
3. 换手预测（信号层名义事件数，未含 TP/整手）：BASE_R7=176；R14=100（−43%）；R21=85（−52%）；SIG8/SIG12=65（−63%，两者信号层一致，差异将在 TP 交互与整手中体现）。→ 非对称语义成立：exit 越慢，信号层换手越低；ΔGross 是否 >0 由实盘验收判定（§10），此处不预支结论。

---

## 9. harness 实现接口建议（patch 草案，不实施）

新增 rebalance_gate 类型（与现有 overlap/cost_aware/rank_hold/dynamic 四类型并列，默认 None 行为零变化）：rebalance_gate type=asymmetric，参数 entry_R=7，exit_R=21（D1/D2/D3 用 7/14/21；D4 设 null，无固定到期只走 exit_rank），exit_rank=8（D4 用 8/12；D1~D3 为 null），max_hold=42（直通现有 exit.max_hold_days，二者必须相等，normalize 时校验）。

simulate 改动清单（行号以 2026-11-09 版 harness 为准）：

1. grid_positions（约975行）：entry 网格保持 range(warm, n-1, entry_R)；不新增 exit 网格——exit 到期按每票 h[pos]+exit_R 独立判定（D1~D3），D4 排名检查复用 entry 信号日（pos−1），与现有 hold_exempt 调用点同位置。
2. simulate (2) 段调仓分支（约1427~1439行）：elif rebalance_gate 分支新增 asymmetric 处理函数 apply_asymmetric_gate(b, cfg, umask, pos−1, holds, picks)，返回 (do_rebal, sell_list, buy_list, gate_info)，其中 sell_list = 到期/死亡票（D4 需 umask → need_umask（约1168行）条件增加 or gate type==asymmetric），buy_list = picks − holds。首建（holds 为空）沿用现有 first_build 语义直接建仓。
3. 买入段（约1448~1457行）：partial 判定扩展为 gate_info.mode==partial or gate==asymmetric（R7-D 恒用 eq_before 定 per，见 §4；D1 整批到期日数学等价，无需特判）。
4. 每日 exit 段（约1349行）：max_hold_days 复用，一字不动。
5. rebal.append（约1475行）：新增 asym_entry_n/asym_exit_n/asym_death_n/asym_hold_age_max/asym_deferred_buys 五字段（诊断与归因用）。
6. parse_rebalance_gate（约502行）：新增 asymmetric 分支校验（entry_R≥1；exit_R/exit_rank 恰其一为非空；max_hold ≥ exit_R 或 ≥21）。

门控核心伪代码：输入 t_sig、holds 字典 {j: entry_pos}、picks；sell 先收年龄到期票（exit_R 非空时 (t_sig+1)−pe ≥ exit_R），再收排名死亡票（exit_rank 非空时 ranked_order 名次 > exit_rank）；去重；buy = picks − holds；返回是否动作及双方名单与 gate_info（含 overlap/exit_n/entry_n）。

---

## 10. 对照组与晋级条件（含 ΔGross>0 必要条件的计算法）

- 对照组：BASE_R7（同参 R7 全量，预期复现 +63.5%；D1 与其 Δ≤0.5pp 为实现正确性门，不过则 D2~D4 数字一律作废）+ BASE_R30（+102.07% 挑战线）。
- 成功标准（沿用主线，逐字）：2026 fresh > +102.07% 且 ΔGross > 0 且现实成本整手全计且 5 档相位无孤点且剔 Top3 有效且 2025H2/OOS 无退化且期末强制清算闭环。
- ΔGross>0 计算法（A2 教训：成本依赖型门控禁用于 Gross 对比）：
  步骤1. 同决策序列零成本重跑：cost={mode:fixed, one_way:0, lot_size:1}，其余字段与原 spec 逐字节一致 → Gross_fresh = gross_row.fresh_total。
  步骤2. 决策一致性证明：asymmetric 门控输入只有（排名，年龄），与成本无关，故零成本重跑的 sell/buy 序列与 realistic 原跑逐笔一致（用 trades 的 (exit_date, code) 集合相等校验，不等则该组 Gross 作废重查）。
  步骤3. ΔGross = Gross_D − Gross_BASE_R7；必要条件：ΔGross > 0（多赚的必须不止是省出来的；若 ΔGross≤0 即使 ΔNet>0 也只能算“成本优化”，不算“交易经济性改善”，不得晋级）。

---

## 11. 本设计的 3 个最大风险点

R1（regime 风险，最大）：慢退出在单边牛市里天然占优。2026 小微盘普涨，持有越久赚得越多可能是 regime 红利而非机制 alpha；OOS 熊市（2024式 −30% 回撤）下 R21/信号退出的 3 倍持有期 = 3 倍暴露时间。缓释：max_hold=42 熔断器 + 验收强制 2024 MDD 与 2025H2（任一退化即 FAIL，不讨论）；D4 的排名死亡在熊市中应更快杀票，若 2024 下 D4 换手反而高于 2026，视为机制自适应证据（加分项，非必要）。

R2（低暴露/现金拖累 + 权重漂移）：慢退出 + TP45 现金闲置 → 实际暴露可能长期 <0.8（A2 已现期末 82% 现金）；保留仓不调权 → 单票漂移无人管。若 D4 靠“不交易”而不是“选得准”赢，fresh_exposure 会显著低于 BASE_R7。缓释：验收必看 fresh_exposure 与 forced_total（规则B）；若某组 Net 超线但暴露 <0.7，降级为“现金管理效应”，不得对标 BASE_R30（满暴露基准）。

R3（退出端噪声回流）：D4 单次跌出即卖，会把 entry 端好不容易丢掉的 R7 噪声从退出端请回来（排名在 K 边界抖动的票被反复买卖）；若改二次确认制，又引入最长 7 天延迟暴露。缓释：D4a/b 主跑单次制；若 D4 换手 ≥ D2（即退出端比 R14 还忙），直接判 D4 机制失败，不启动确认制补救（纪律：不为失败机制打补丁）；TP 交互归因必须拆分（TP退出笔数占比、信号死亡占比、到期占比三栏），若某组 exit_R 名存实亡（>70% 退出实际是 TP），则该组结论改为“TP 效应”，R7-D 不认领。

---

## 附录 A. spec 草案（5 条：字段全列，值按 §1 表）

- D1_R7D_exitR7：selector amihud_60 n=4 size 0.05-0.30 adv>500万 主板池；R=7 entry_R=7 exit_R=7 exit_rank=null max_hold=42；TP45；realistic 5万 lot100 slip0.002；exposure 1.0；window warmup2024/eval20260105-20261104；full300 phase0。
- D2_R7D_exitR14：同上，exit_R=14。
- D3_R7D_exitR21：同上，exit_R=21。
- D4a_R7D_sigK8：同上，exit_R=null exit_rank=8。
- D4b_R7D_sigK12：同上，exit_R=null exit_rank=12。
- exit 统一 take_profit=0.45 max_hold_days=42 stop_exec=next；timing=none。（完整 JSON 由 backtester 按附录模板展开，含 window/anchor/cost/portfolio 全字段。）

---

## 附录 B. 只读验证原始数（§8 来源，可复算）

- overlap：7天0.77 / 14天0.68 / 21天0.58 / 28天0.53（29信号日均值）。
- dwell Top8：7:19 / 14:14 / 21:14 / 28:10 / 35:10 / 42:9 / 49:10 / 56:5 / 63:6 / ≥70:19（n=120）。
- dwell Top12：7:19 / 14:14 / 21:13 / 28:9 / 35:10 / 42:10 / 49:9 / 56:6 / 63:7 / ≥70:19。
- 信号层名义换手事件：BASE_R7=176 / R14=100 / R21=85 / SIG8=65 / SIG12=65（29段，TP/整手未计）。
