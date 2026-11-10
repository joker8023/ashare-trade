# R7 晋级门验证方法学（独立复核专用）

- 版本：v1.0 · 2026-11-09 · 作者角色：auditor（独立复核）。
- 通用口径：amihud_60 / N=4 / 市值5~30分位 / ADV>500万 /
  剔688·689·北交所·创业板 / TP45（t收盘触发、t+1收盘卖出）/
  fresh5万 / realistic现实费率整手（lot=100，slip=0.002）/
  full300锚 / warmup2024 / 评估窗2026-01-05~2026-11-04。
- 基准：BASE_R30（R30/TP45/e1.0）2026 fresh净收益 +102.07%（挑战线，复算确认见B.1）。
- 本方法只读 team/runs/batch_星号.csv 与 diags JSON 做判定；复算仅允许单格重跑
  （复现误差≤0.5pp）与小窗口冒烟语义验证，禁止全量跑批。
- team/harness.py 只读；本轮 harness 新增的 rebalance_gate
  （overlap / cost_aware / rank_hold / dynamic，默认关闭）已做只读审计，语义结论见A.4。

---

## A) 晋级门 checker 设计

### A.1 输入

1. team/runs/batch_星号.csv（harness run_spec 行输出），必需列：
   id, fresh_total, fresh_mdd, fresh_win_period, fresh_n_periods, fresh_win_trade,
   fresh_n_trades, fresh_win_month, fresh_top3_pnl_share, fresh_top1_pnl_share,
   fresh_cost_paid_pct, turnover, total_2025, total_2025h2, mdd_2025h2,
   total_2024, mdd_2024, gross_fresh_2026（Gross参考列，缺失则按A.4重算声明）。
2. diags JSON（U诊断与跳过统计），必需字段/每调仓信号：
   gate, overlap, skip布尔, U, dalpha, C, sigma, fwd7, fwd14，
   以及聚合 nskip, nexe, skip_fwd7/14均值, exec_fwd7/14均值。
   fwd星号只允许出现在日志中，严禁回流入任何交易决策（只读审计已确认：
   apply_rebalance_gate 内 fwd7/fwd14 仅写入 info 字典并随 rebal 落盘，
   do_rebal/sell_list/buy_list 的计算只依赖 overlap/dalpha/C/sigma，
   决策路径中无任何 fwd 引用——无未来函数）。
3. 资金闭环快照（fresh口径 detail sim，ev_end 定位取值，禁止用数组末位-1
   取值——全长数组末位超出评估窗，曾导致 forced_total=nan，见B.3）：
   eq_end, expo, nhold, cash_pct, liq_cost, forced_total。

### A.2 输出

每个候选一行判定矩阵，列为 G1..G7 + Wilson备注 + 综合，取值
PASS / FAIL / WARNING，每格必须附证据字符串（数字+来源文件+行id），
禁止只有结论没有证据。

### A.3 七项检查与阈值（具体数字建议）

- G1 挑战线：fresh_total > +102.07%（严格大于，复现误差带0.5pp内按FAIL计）。
  基准复算0.00pp，线本身可信。
- G2 2025H2：total_2025H2 > 0 且 ≥ 基准2025H2 − 20pp。防2026单年拟合。
- G3 相位：同时满足：(a) 5档极差 max−min ≤ 30pp；(b) ≥3/5档通过三线
  （fresh≥60% 且 mdd≥−15% 且段胜率口径一致）；(c) 最差档 ≥ 中位数 − 30pp
  （反孤点）。任一条不满足即FAIL。A2最优组极差39pp，天然FAIL。
- G4 exTOP3双判：数字判要求剔除后 fresh_total ≥ +60% 且保留率 ≥50%；
  机制判要求剔除后新Top3占比必须 ≤55%，否则即使数字过也只能给WARNING
  （集中度机制再生不等于分散化）。A2剔除后+83~105%但新Top3达63~81%。
- G5 stress08：slip=0.007现实整手重跑，fresh_total ≥ +60% 且相对base版回撤 ≤15pp。
- G6 OOS无退化：total_2025 > 0；total_2024 > 0；2024 mdd 不比基准差超5pp。小盘策略熊市底线。
- G7 闭环：forced_total 与 fresh_total 差值绝对值 ≤ 1.0pp（实测各策略≤0.6pp），
  且必须披露终态三件套：cash_pct / expo / nhold。防藏浮亏与藏空仓。

小样本 Wilson 报告规则（95%下界，结论中必须与点估计并列，禁止单报点估计）：

- 段胜率 5/6=83.3%（R30基准）：下界 43.6%。
- 段胜率 17/27=63.0%（R7-A2）：下界 44.2%。
- 按笔 9/11=81.8%（A2 fresh，n=11，不可作证据）：下界 52.3%。
- 按笔 15/24=62.5%（R30 fresh）：下界 42.7%。
- 月胜率 7/10=70%：下界 39.7%；月胜率 8/10=80%：下界 49.0%。

推论：R30的83.3%段胜率与A2的81.8%按笔在统计上都不能证明≥60~80%
（下界42~52%），任何高胜率表述必须降级为描述性语言。

### A.4 DeltaGross 计算规范（本方法核心反作弊条款）

定义：

- CostDrag = 同决策序列下 Gross − Net（同一决策序列的毛净差）。
- DeltaGross = Gross候选 − Gross基准（均为零成本重跑，cost固定one_way=0）。
- 成功标准要求 DeltaGross>0，其含义是：候选门控在去除成本因素后依然不输基准，
  否则改善100%来自省钱而非选单。

可比性铁律：

1. 零成本重跑仅当门控决策逻辑与成本无关时才可比。
   overlap / rank_hold / dynamic 满足（决策只用交集与排名）；
   cost_aware 不满足——零成本下 C=0 使 U 系统性偏高、跳过更少，决策序列改变。
   因此 cost_aware 的零成本 gross 是上限参考（upper bound），必须标注偏差方向：
   真实同决策Gross位于 Net+已实现成本 与 上报Gross 之间。
2. 同决策真实Gross的诚实近似：(1+Net)×(1+cost_paid_pct) − 1。
   A2（lam1.0/ov3/ph0）：1.917×1.0187−1 ≈ +95.3%，低于BASE_R7的
   同决策Gross +99.0%，更低于R30的 +117.0%。
   结论：A2的+28.2pp净改善中，成本节约解释约15.7pp（17.59%→1.87%），
   其余来自躲掉负期望切换；门控没有创造任何毛收益，DeltaGross<0。
3. 反例校准：R7-A1（纯overlap）省12pp成本却丢21pp Gross（99.0→78.2），
   净仅+3.5pp——蠢跳的Gross代价；R7-B/C省14pp成本丢27pp Gross（99.0→72.1），
   净零改善——硬留旧仓方向错误。两反例是A2归因的必要对照。

### A.5 判定聚合

- 任一G门FAIL → 综合FAIL（不得晋级实盘）。
- 无FAIL但任一WARNING → 综合WARNING（仅可晋级研究）。
- 七门全PASS → 综合PASS（仍需Lead按多重检验计数做data-snooping折减后定稿）。
- 规则A/B违反 → 直接综合FAIL，不看数字（见B.4）。

---

## B) 对 batch_026 与 batch_027 的独立复核

### B.1 复算（3关键格，同一harness重跑，判定标准Δ≤0.5pp即0.005）

- BASE_R30_N4TP45_e100（fresh/mdd/2025H2）：CSV值 +1.0207/−0.1138/0.3242；
  独立重跑 +1.0207/−0.1138/0.3242；Δ=0.00pp；PASS。
- A2 lam1.0/ov3/ph0（R7A2_costaware3_lam10）：CSV值 +0.9170/−0.1171/0.3106；
  独立重跑 +0.9170/−0.1171/0.3106；Δ=0.00pp；PASS。
- A2 lam0.5/ov3/ph+5（最高孤立格+114.71%）：CSV值 +1.1471/−0.1181/0.3015；
  独立重跑 +1.1471/−0.1181/0.3015；Δ=0.00pp；PASS。

诚实声明复核深度：三次重跑与原批共享同一 harness.py 代码路径，验证的是
确定性重放（Δ=0.00pp证明批次数字无手工篡改、无随机性），不等同于第二套
独立实现的对抗审计；审计深度记为 replay-level，此局限不影响下述矩阵判定
（矩阵所用数字本身可信）。

### B.2 七门复核矩阵（A2家族代表格 lam1.0/ov3/ph0；括号内为全家族极值）

- G1：+91.7%，距线−10.4pp；全家族仅lam0.5/ov3的ph0(+109.0%)、ph5(+114.7%)两孤立格超线。判定 FAIL。
- G2：30格2025H2全部为正（+9.6%~+32.3%），代表格+31.1%。判定 PASS。
- G3：代表组5档 71.3/52.8/91.7/64.6/88.7（极差39pp）；最优组lam0.5/ov3极差61pp
  （53.9~114.7）；无一组满足(a)(b)(c)全过。判定 FAIL。
- G4：剔除（probe名单）后+83.7%~+105.4%数字全过，但新Top3达63%~81%
  （lam0.5/ov3组达80.8%），机制再生；且剔除名单取自probe格自身Top3
  （各组自有Top3并不完全一致，如lam0.5/ov2自有Top3含600165），存在挑选偏差。
  判定：数字PASS/机制FAIL → WARNING。
- G5：slip0.007下+70.2%~+112.1%（代表格+86.2%，相对base回撤差−0.4pp）。判定 PASS。
- G6：2025：+130.0% vs 基准+137.7%（−7.7pp）；2024：+47.3% vs +36.7%（+10.6pp），
  mdd −28.5% vs −33.8%。判定 PASS。
- G7：forced与reported差值：BASE_R30 −0.54pp、BASE_R7 −0.44pp、A2各格 −0.1~−0.4pp。
  判定 PASS（附终态披露）。

终态披露（规则B要求，fresh口径）：A2 lam1.0/2.0期末 82%现金+仅剩1持仓
（expo 0.18）——+91.7%是上半年少数交易后空仓躺出来的；lam0.5/ov3期末97%在场
（4持仓）——同家族换lambda即换性格，机制性格不稳定。
综合：G2/G5/G6/G7通过，G1/G3 FAIL，G4 WARNING → 综合FAIL（不得晋级实盘），
符合研究候选定位。

段按笔胜率附加判：A2段63.0%（Wilson下界44.2%）、按笔81.8%（n=11，下界52.3%）、
月70%（下界39.7%）——胜率维度无一可作晋级证据，仅描述。
R30段83.3%下界43.6%同样不可证≥80%，基准的胜率表述亦须同等降级。

### B.3 对Lead已判结论的意见：同意为主，5点修正与补充

1. 同意：A2晋级研究、R7冻结、A1/B/C暂停、lam0.5/ov3两格按规则A不认。
   独立矩阵与Lead结论一致。
2. 修正（归因口径）：Lead称A2改善来自成本加躲掉负期望切换基本成立，但
   按A.4第2条量化后应收紧为——A2改善几乎全部来自成本节约，同决策真实Gross
   约+95.3%仍低于BASE_R7的+99.0%（DeltaGross<0）。即门控没有选出更好的单子，
   只是少付了冤枉钱。躲掉负期望切换的准确含义是少做了负期望动作，
   不是找到了正期望动作。U诊断支持此读法：被执行切换fwd7为+6.6~+11.3%而
   被跳过组约0（lam0.5/ov3跳过组−0.9%/−2.1%）——执行侧是真区分，但全年仅2~4次执行。
3. 修正（exTOP3效力）：数字过关但挑选有偏（名单外生于probe格），且
   80.8%的新Top3说明机制未变。任何剔Top3仍有效的对外表述必须同时给出
   新Top3占比，否则视为违反规则A第3条（只报有利切面）。
4. 补充（平台假象）：ph0下lam1.0/2.0乘ov2/ov3四格精确相等（+0.9170，mdd同值）——
   lambda≥1.0在此处饱和，表面稳定实为同一决策序列被数四遍，与此前
   W2/W5/V6重复计数教训同类。checker必须对跨格逐笔一致做去重门（见B.4）。
5. 补充（工具链bug已修）：复核中发现并由Lead修复三处——rebal追加行多余右括号
   （SyntaxError，已修）、overlap跳过路径缺fwd日志（已补）、部分调仓买入权重
   低配N倍（已按调仓前权益定等权目标修正）、闭环误用全长数组末位导致nan
   （已改用ev_end定位）。复核确认：修复后3格重跑Δ=0.00pp；但batch_026的
   R7B/C数字产自低配版买入权重（部分调仓新票系统性低配），其+63.3%是
   实现瑕疵下的保守值，B/C方向错误的结论不受影响（Gross塌27pp主因是
   留仓本身衰减，非权重bug可解释量级）。

### B.4 规则A（禁挑单格）与规则B（完整闭环）可执行细则

规则A——反 cherry-picking（checker硬门）：

1. 参数邻域必须整表报告（本轮为6组乘5相位=30格+6压力+6剔除=42行
   全量CSV，缺格即FAIL）。
2. 稳定区域定义：候选格与其lambda正负ov正负直接邻格中，至少2格与候选格差距≤15pp
   且三者fresh均大于挑战线−15pp。A2全家族无一满足（lam0.5/ov3的ph0/ph5
   互为孤点：ph−5同组仅+53.9%）。
3. 去重门：同一窗口下trades逐笔一致（允许浮点1e-9）或fresh_total精确到
   小数点后4位全等的跨格结果，只计一次有效证据。本轮ph0四格+0.9170按一格计。
4. 对外引用任一超线格，必须同段引用其同组最差格与极差，否则视为违规引用。

规则B——完整闭环（checker硬门）：

1. 必报六字段（fresh口径，ev_end定位）：eq_end, expo, nhold, cash_pct,
   liq_cost（含最低5元每笔整手）, forced_total；判定 forced与reported差值绝对值≤1.0pp。
2. 未实现拆分：mv_end与cash分别列示；终态高现金（如A2的82%）必须写入
   结论正文，不得只放附表。
3. 跨期继承声明：fresh窗（空仓起步）与连续窗（2025持仓带入）双口径并列；
   用连续窗数字做晋级判定时，必须说明 inherited positions 的影响。
4. U诊断（如用cost_aware类门控）必报：nskip/nexe/skip_fwd均值/exec_fwd均值；
   nexe<5 时按笔与段胜率自动降级为描述性指标（本轮A2 nexe=2~4，触发本条）。
5. 数据完整性声明（CSV无法自证，结论必须逐字携带）：幸存者偏差未修正、
   shares为当前快照（含轻微前视）、未建模涨跌停不可成交、2026仅10个月。

---

## 附录：证据清单

- team/runs/batch_026_r7abc_results.csv（6 spec：BASE_R30/BASE_R7/A1/A2/B/C）。
- team/runs/batch_027_r7a2_neighborhood.csv（42行：30邻域+6 stress08+6 exTOP3）。
- team/runs/batch_027_r7a2_diags.json（6组U分组诊断，ph0 fresh sim）。
- 本复核重跑：3格（BASE_R30 / A2-lam1.0-ov3-ph0 / A2-lam0.5-ov3-ph5），
  run_spec(variants=fresh单项)，Δ=0.00pp（误差带0.5pp内PASS）。
- 方法版本锁定：阈值变更需发新版并重跑全矩阵，禁止追溯性放宽。
