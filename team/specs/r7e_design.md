# R7-E 双时间尺度选股设计（冻结 A2 之后的新分支）

状态：设计稿，未跑批。A2（cost_aware lam1.0/ov3，+91.7%）已冻结，不许再调。
本设计只新增选股信号，不动调仓门控、不动执行/成本口径。
通用口径：amihud 系 / N=4 / 市值 5~30 分位 / ADV>500万 / 剔688/689/北交所/创业板 /
TP45（t收盘触发、t+1收盘卖）/ fresh5万 / realistic整手 lot100 slip0.002 / full300相位0 / warmup2024。
挑战线：2026 fresh +102.07%（BASE_R30），且 DeltaGross>0、现实成本全计、5档相位无孤点、
剔Top3有效、2025H2/OOS无退化、期末强制清算闭环。

## 0. 背景数（已确认，不重复论证）

- BASE_R30（amihud_60/N4/R30/TP45）：净 +102.07%，Gross +117.0%。
- BASE_R7（同参 R7）：净 +63.5%，Gross +99.0%，DeltaGross 缺口 18pp，另加成本 17.6% vs 4.9%。
- A2 结论：门控把净差距从 -38.6pp 收到 -10.4pp，但 Gross 仍差约 20pp——
  R7 的问题一半在成本，一半在信号本身。R7-E 负责后一半：让 7 天网格的每一次调仓都有新信息可交易。

## 1. 融合公式

    Score_i = alpha * S7,i + (1 - alpha) * S30,i，  alpha in {0.25, 0.50, 0.75}

- S7、S30 均为截面百分位排名（rank pct=True，只对当期有限值排名），融合前已无量纲，alpha 即权重本义。
- NaN 规则（严格版）：任一腿为 NaN 则融合分记 NaN（不回退），保证 alpha 在全样本上可解释。
  S30（amihud_60）覆盖率最低（约97.9%），融合覆盖约97.5%，损失可忽略；universe/pool 逻辑不变。
- S30 固定二选一：amihud_60（中期主力）或 amihud（20d）。S7 见第2节。
- 冒烟验证（2026-10 截面，经 fac_matrix 实测）：alpha=0.25 时 top4 与纯 S30 重叠 1/4；
  alpha>=0.5 时重叠 0/4——融合确实改变选股，R7 网格将交易知情换手而非噪声换手。

## 2. S7 候选前视安全审计（逐个结论：全部只用 t 及以前数据，可用）

- amihud_5：abs(ret)/amt 的 5 日均值。用当日成交额，但与已在产的 amihud_20/60 同构，属标准 Amihud 定义。可用。
- rev5：-(c_t/c_{t-5}-1)。纯价格滞后。可用。
- low_vol + params window=5：过去5日收益滚动std取负。f_low_vol 已支持 window 透传（冒烟通过）。可用。
- max20 + params window=5：过去5日最大单日收益取负。透传已验证。可用。
- turnover + params window=5：换手率5日均值取负。可用（低优先：与 Amihud 同族，增量信息小）。
- amount_level + params window=5：成交额5日均值取负。可用（低优先，同族）。

纪律：S7 逐个先跑单腿诊断（覆盖率/换手量级），不合并且跑；单腿不计入 9 组尝试预算。
bias20（写死20日）不采用；如需乖离类短窗口必须新增函数，本次不做，保持改动最小。
冒烟覆盖率：8 个因子在测试截面有限率 97.9%~99.6%，params 透传正常。

## 3. alpha 选择：滚动 OOS（禁止用 2026 收益挑 alpha）

使用现有 run_spec 直接输出的列，不改 harness：

- 训练 2024-01-01~2024-12-31，指标 total_2024（连续口径，warmup 预热）：
  3 个 S7 候选按 2024 排名，只保留前 2 名 S7，淘汰 1 个。
- 验证 2025-01-01~2025-12-31，指标 total_2025：对 surviving S7 在 alpha 三档中取验证最优。
  端点规则：选 0.25/0.75 需比 0.50 高至少 5pp，否则回退 0.50；且所选 alpha 在 2024 同组内不得垫底（防跨年度反转）。
- 锁定测试 2026-01-05~2026-11-04，指标 fresh_total 等全套门：冻结 (S7, alpha)，只跑一次 2026 fresh + 全套压力。

平滑性要求：0.50 必须落在 [best-3pp, best] 内，否则记 SMOOTHNESS_WARNING（即使验证最优也不得宣称稳定）。
2024 与 2025 同属小微盘牛市：本方案只能防年内过拟合，不能防跨体制过拟合，必须在结论 limitations 声明。

## 4. 三组 spec 草案（JSON 片段，需新 selector 类型 dual_scale，见第5节）

E1：短窗非流动性 x 中期非流动性（同族不同频，稳健优先）：
    selector.type=dual_scale, n=4, size_range=[0.05,0.30], min_adv=5000000,
    exclude_star/bj/chinext=true, params={alpha:0.5, s7:amihud_5, s7_params:{}, s30:amihud_60, s30_params:{}}
    exit take_profit=0.45, timing none, cost realistic capital50000 lot100 slip0.002, rebalance_days=7

E2：5日反转 x 中期非流动性（跨族，预期换手最高，需重点看 turnover 熔断）：
    selector.type=dual_scale, n=4, 同上池子,
    params={alpha:0.5, s7:rev5, s7_params:{}, s30:amihud_60, s30_params:{}}
    其余同 E1。

E3：5日低波 x 20日非流动性（S30 用短一档，测双短是否更配 R7 网格）：
    selector.type=dual_scale, n=4, 同上池子,
    params={alpha:0.5, s7:low_vol, s7_params:{window:5}, s30:amihud, s30_params:{}}
    其余同 E1。

aX 说明：alpha 为占位符，由第3节 OOS 流程填写锁定值（0.25/0.50/0.75），不得手调。
必加对照臂（诊断用，不计入晋级判据）：alpha=0（即纯 S30 信号跑 R7 网格），用于分离网格效应 vs 信号效应。

## 5. harness 实现路径（推荐：新 selector 类型；harness 只读，以下供 backtester 落子）

推荐 A：新增 FACTORS dual_scale = f_dual_scale，不动其他任何函数。
函数签名建议：f_dual_scale(b, alpha=0.5, s7=amihud_5, s30=amihud_60, s7_params=None, s30_params=None)。
原理：_fac_matrix 按被调函数签名过滤 kwargs（varnames 白名单），该签名天然兼容 spec params；
内部对两条腿分别调 _fac_matrix 取全矩阵后逐行 rank 融合，不要在行循环里调 _fac_row，避免重复计算；
_one_pick / _ranked_order / picks_at / universe_matrix / simulate 零改动（它们只认 type+params）；
cache key 已含 params JSON，alpha 不同自动分槽。_fac 缓存上限 8、融合一次占 3 槽，两条腿加融合结果，
batch 跑多组时建议评估逐出阈值是否需要同步放宽。
不推荐 B（预计算融合矩阵）：要动 _fac_matrix 加分支、缓存 key 语义变化、与现有 params 机制冲突，
改动面大且破坏只加因子的团队约定。
前视 checklist（auditor 复核）：f_dual_scale 内只用 _fac_matrix（全为 rolling/shift 构造）加当期 rank；
禁止任何 shift(-k)；加信号整体 +1 日重跑（LOOKAHEAD_RISK 门），与现有纪律一致。

## 6. Gross 提升机制论证（为什么能补 18pp，而不是把 R7 变回 R30）

1) 缺口分解：BASE_R7 Gross 99.0 vs R30 117.0。R7 网格跑的是慢信号（amihud_60，20~60天记忆）：
   相邻调仓日的 picks 高度重叠，发生的换手多为同分票抖动，换手是噪声、信息量约0，
   还顺带把未到期 thesis 提前砍掉（7 天强制重置 vs 30 天持有论）。A2 已证实：蠢跳省 12pp 成本却丢 21pp Gross。
2) 融合的作用：S7（5天）给每个 7 天调仓点注入当期新信息（冒烟：alpha>=0.5 top4 与纯S30零重叠），
   使换手从噪声换手变为知情换手：换手率不降（仍是 R7 量级），但单位换手的远期 spread 转正。
   可直接用既有 gate_fwd7/fwd14 诊断验证：要求执行组 fwd spread 显著大于跳过组。
3) 为什么不是 R30 复刻：R30 的 Gross 来自持有 30 天吃满流动性溢价加低换手；R7-E 的路径是
   每周用 5 天信息做一次知情再平衡加 S30 锚定 thesis 不漂移。两者 Gross 来源正交：
   若融合无效，表现为 turnover 高企但 fwd spread 约0（可证伪）；对照臂 alpha=0 会复现
   R7网格加纯S30的低Gross加高成本，与 E1~E3 形成差分，证明增量确来自 S7 而非网格本身。
4) 数量目标：Gross 从 99.0 起步，需 DeltaGross >= +18pp（回到 117.0 一线）才有挑战资格；
   熔断线：若 turnover_ann 大于 2 倍 BASE_R7，无论收益多高都判 R7-DESTABILIZED（换手失控），停止该分支。

## 7. 过拟合防控

- 尝试上限：3 S7 x 3 alpha = 9 组，加 1 个 alpha=0 对照臂，
  加（仅当某组全部门通过后才允许的）S7 单腿事后诊断不超过 2 组。S7 单腿预筛不计入（只看覆盖率/换手量级，不看收益）。
- alpha 只能取验证最优档，且端点需 5pp margin、2024 非垫底、中档在 best-3pp 内（第3节）。
- 报告纪律：9 组全量报告，禁止只报最优；2026 只测锁定的一组（并列锁定须如实报告并列数）。
- 2024/2025 同属小微盘牛市，跨体制外推能力未被证明，结论上限为机制候选，与 A2 同级，不得直接晋级实盘。

## 8. 三个最大风险点

风险1（最高）：5天微结构幻觉。小微盘 5 天 Amihud/反转可能度量的是买卖价差反弹而非风险溢价；
realistic slip 0.002/边大概率低估这类名单的真实冲击。强制 slip=0.007 整手压力：
若 Gross 增量在压力下蒸发，则 R7-E 的知情换手是纸面 alpha，就地处决该分支，不许降滑点重跑。

风险2：alpha 的体制过拟合。2024 训练加 2025 验证皆为小微盘牛市，高 alpha（重短窗）在牛市天然占优；
一旦轮动到大盘或熊市，S7 腿可能系统性反向。缓解：2024 一致性门（第3节）加 2025H2 单独披露加文档声明体制局限；
若验证最优 alpha 在 2024 垫底，即使 2025 最优也强制回退 0.50。

风险3：融合脆弱性（rank 尺度加覆盖不对称）。S7（5天）与 S30（60天）截面离散度不同，好在融合前已 pct 化；
真风险在停牌/次新导致的单腿 NaN 不对称：严格版 NaN 规则会把这部分票整体丢弃，
若丢弃票恰是 R7 网格的高 alpha 来源，则融合人为设限。要求报告融合覆盖率与丢弃名单数量级；
若覆盖低于 95%，改用回退版（缺腿时用另腿 rank）并重跑全部流程，不许混用两种规则挑结果。

## 9. 交付与验收接口

- backtester 输入：本文件第4节三组 JSON（alpha 填 OOS 锁定值）加第5节落子 patch（含前视 checklist 自测证据）。
- auditor 复核点：S7 前视（信号整体+1日重跑）、alpha 选择流程是否用了 2026 数据（一票否决项）、
  9 组全报告、熔断线、滑点压力、闭环清算。
- 成功标准：2026 fresh 大于 +102.07% 且 DeltaGross 大于 0 且全套压力门。任一失败则 R7-E 关闭，不开 E4。
- smoke 证据：2026-10 截面 8 因子有限率 97.9%~99.6%，params 透传（window=5）正常，融合语义符合预期。
- 本设计未做任何全量回测；A2 冻结不受影响。
