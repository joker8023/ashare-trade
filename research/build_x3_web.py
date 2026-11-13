#!/usr/bin/env python3
"""把 results/paper/x3_web_data.json 注入模板, 生成单文件网页
~/workspace/your_files/x3-tracker.html (可离线打开, 填写内容存浏览器本地)。"""
import json
import os

ROOT = os.path.expanduser("~/workspace/ashare-trade")
with open(os.path.join(ROOT, "results/paper/x3_web_data.json"), encoding="utf-8") as f:
    data = json.load(f)

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>X3 策略持仓跟踪</title>
<style>
  :root { --up:#c0392b; --down:#1e8449; --ink:#1c2733; --mut:#71808f; --line:#e3e8ee; --bg:#f5f7fa; --card:#fff; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif; background:var(--bg); color:var(--ink); font-size:14px; }
  .wrap { max-width:1060px; margin:0 auto; padding:18px 14px 60px; }
  h1 { font-size:21px; margin:4px 0 2px; }
  .sub { color:var(--mut); font-size:12.5px; line-height:1.55; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin:16px 0; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 14px; }
  .card .k { color:var(--mut); font-size:12px; }
  .card .v { font-size:20px; font-weight:700; margin-top:3px; }
  .card .d { font-size:12px; color:var(--mut); margin-top:2px; }
  .pos { color:var(--up); } .neg { color:var(--down); }
  .panel { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px; margin:14px 0; }
  .panel h2 { font-size:15px; margin:0 0 10px; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th, td { padding:6px 7px; border-bottom:1px solid var(--line); text-align:right; white-space:nowrap; }
  th { color:var(--mut); font-weight:600; font-size:12px; }
  td.l, th.l { text-align:left; }
  .scroll { overflow-x:auto; }
  input[type=number] { width:86px; padding:4px 6px; border:1px solid #c9d3dd; border-radius:6px; font-size:13px; text-align:right; }
  input.cap { width:110px; font-size:15px; font-weight:700; }
  .period { background:var(--card); border:1px solid var(--line); border-radius:10px; margin:14px 0; overflow:hidden; }
  .phead { display:flex; flex-wrap:wrap; gap:6px 14px; align-items:baseline; padding:11px 14px; background:#eef3f8; border-bottom:1px solid var(--line); }
  .phead .t { font-weight:700; font-size:14.5px; }
  .phead .meta { color:var(--mut); font-size:12.5px; }
  .phead .sum { margin-left:auto; font-weight:700; }
  .tag { display:inline-block; padding:0 7px; border-radius:8px; font-size:11px; line-height:18px; background:#dfe9f5; color:#2f5b8f; }
  .tag.take { background:#fdeeda; color:#9a6206; }
  .tag.hold { background:#e2f2e6; color:#1e8449; }
  .foot { color:var(--mut); font-size:12px; line-height:1.7; margin-top:18px; }
  button { border:1px solid #c9d3dd; background:#fff; border-radius:7px; padding:5px 12px; font-size:13px; cursor:pointer; }
  .bar { height:7px; border-radius:4px; background:#e8edf2; position:relative; min-width:90px; }
  .bar i { position:absolute; top:0; bottom:0; border-radius:4px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>X3 策略 · 持仓与收益跟踪</h1>
  <div class="sub" id="strategyLine"></div>
  <div class="sub">推荐价口径：买入价 = 调仓执行日开盘价，卖出价 = 平仓日收盘价（止盈单为触发次日收盘）。把「实际价 / 股数」改成你的真实成交后，盈亏、月收益、总收益会自动重算；填写内容只保存在本浏览器。</div>

  <div class="cards">
    <div class="card"><div class="k">本金（可改）</div><div class="v">¥<input class="cap" type="number" id="capital" step="1000"></div><div class="d">收益率均按本金计算</div></div>
    <div class="card"><div class="k">已实现盈亏</div><div class="v" id="sumRealized">–</div><div class="d" id="sumRealizedPct">–</div></div>
    <div class="card"><div class="k">未平仓估值盈亏</div><div class="v" id="sumUnreal">–</div><div class="d" id="sumUnrealNote">–</div></div>
    <div class="card"><div class="k">总收益（已实现+未平仓）</div><div class="v" id="sumTotal">–</div><div class="d" id="sumTotalPct">–</div></div>
  </div>

  <div class="panel">
    <h2>月收益（按平仓月份归集已实现盈亏）</h2>
    <div class="scroll"><table id="monthTable">
      <thead><tr><th class="l">月份</th><th>已实现盈亏</th><th>月收益率</th><th class="l" style="min-width:110px">相对规模</th><th>累计已实现</th></tr></thead>
      <tbody></tbody>
    </table></div>
  </div>

  <div style="display:flex;align-items:center;gap:10px;margin:18px 0 4px">
    <h2 style="font-size:15px;margin:0">各调仓周期</h2>
    <button id="resetBtn">恢复全部推荐值</button>
  </div>
  <div id="periods"></div>

  <div class="foot" id="footNote"></div>
</div>

<script>
const DATA = __DATA__;
const LS_KEY = "x3_tracker_v1";
let store = {};
try { store = JSON.parse(localStorage.getItem(LS_KEY) || "{}"); } catch(e) { store = {}; }
if (!store.entries) store.entries = {};
if (!store.capital) store.capital = DATA.capital_default;

const fmt = (v, d=0) => (v==null || isNaN(v)) ? "–" : Number(v).toLocaleString("zh-CN",{minimumFractionDigits:d, maximumFractionDigits:d});
const pct = v => (v==null || isNaN(v)) ? "–" : (v>=0?"+":"") + v.toFixed(2) + "%";
const cls = v => v > 0 ? "pos" : (v < 0 ? "neg" : "");
const keyOf = (pi, code) => pi + "_" + code;
const capital = () => parseFloat(store.capital) || DATA.capital_default;

function entry(pi, pos) {
  const k = keyOf(pi, pos.code);
  if (!store.entries[k]) store.entries[k] = { buy: pos.buy_px, sell: pos.sell_px, shares: pos.shares };
  return store.entries[k];
}
function save() { localStorage.setItem(LS_KEY, JSON.stringify(store)); }

function posPnl(pi, pos) {
  const e = entry(pi, pos);
  const buy = parseFloat(e.buy), shares = parseFloat(e.shares);
  if (isNaN(buy) || isNaN(shares)) return { pnl:null, open:!!pos.open };
  const hasSell = !(e.sell === "" || e.sell == null || isNaN(parseFloat(e.sell)));
  if (pos.open && !hasSell) {
    if (pos.last_px == null) return { pnl:null, open:true };
    return { pnl:(pos.last_px - buy) * shares, open:true };
  }
  if (!hasSell) return { pnl:null, open:true };
  return { pnl:(parseFloat(e.sell) - buy) * shares, open:false };
}

function refresh() {
  const cap = capital();
  let realized = 0, unreal = 0;
  const months = {};
  DATA.periods.forEach(p => {
    let pPnl = 0, any = false;
    p.positions.forEach(pos => {
      const r = posPnl(p.idx, pos);
      const k = keyOf(p.idx, pos.code);
      const e = entry(p.idx, pos);
      const cost = parseFloat(e.buy) * parseFloat(e.shares);
      const ret = (r.pnl != null && cost > 0) ? r.pnl / cost * 100 : null;
      const pnlEl = document.querySelector(`[data-pnl="${k}"]`);
      if (pnlEl) { pnlEl.textContent = r.pnl == null ? "–" : "¥" + fmt(r.pnl); pnlEl.className = cls(r.pnl || 0); }
      const retEl = document.querySelector(`[data-ret="${k}"]`);
      if (retEl) { retEl.textContent = ret == null ? "–" : pct(ret); retEl.className = cls(ret || 0); }
      if (r.pnl == null) return;
      pPnl += r.pnl; any = true;
      if (r.open) unreal += r.pnl;
      else { realized += r.pnl; const m = (pos.sell_date || "").slice(0,7); months[m] = (months[m] || 0) + r.pnl; }
    });
    const ps = document.querySelector(`[data-psum="${p.idx}"]`);
    if (ps) { ps.textContent = any ? "本期盈亏 ¥" + fmt(pPnl) + "（" + pct(pPnl / cap * 100) + "）" : ""; ps.className = "sum " + cls(pPnl); }
  });
  const set = (id, txt, c) => { const el = document.getElementById(id); el.textContent = txt; el.className = "v " + (c || ""); };
  set("sumRealized", "¥" + fmt(realized), cls(realized));
  document.getElementById("sumRealizedPct").textContent = "收益率 " + pct(realized / cap * 100);
  set("sumUnreal", "¥" + fmt(unreal), cls(unreal));
  document.getElementById("sumUnrealNote").textContent = "按 " + DATA.as_of + " 收盘价估值";
  set("sumTotal", "¥" + fmt(realized + unreal), cls(realized + unreal));
  document.getElementById("sumTotalPct").textContent = "总收益率 " + pct((realized + unreal) / cap * 100);
  const tb = document.querySelector("#monthTable tbody");
  tb.innerHTML = "";
  const mkeys = Object.keys(months).sort();
  const maxAbs = Math.max(1, ...mkeys.map(m => Math.abs(months[m])));
  let cum = 0;
  mkeys.forEach(m => {
    cum += months[m];
    const v = months[m];
    const tr = document.createElement("tr");
    tr.innerHTML = `<td class="l">${m}</td><td class="${cls(v)}">¥${fmt(v)}</td><td class="${cls(v)}">${pct(v/cap*100)}</td>
      <td class="l"><div class="bar"><i style="${v>=0 ? `left:50%;width:${Math.abs(v)/maxAbs*50}%;background:#c0392b` : `right:50%;width:${Math.abs(v)/maxAbs*50}%;background:#1e8449`}"></i></div></td>
      <td>¥${fmt(cum)}</td>`;
    tb.appendChild(tr);
  });
}

function build() {
  document.getElementById("capital").value = store.capital;
  const host = document.getElementById("periods");
  host.innerHTML = "";
  [...DATA.periods].reverse().forEach(p => {
    const div = document.createElement("div");
    div.className = "period";
    const rows = p.positions.map(pos => {
      const e = entry(p.idx, pos);
      const k = keyOf(p.idx, pos.code);
      const tag = pos.reason === "take" ? '<span class="tag take">止盈卖出</span>'
                : pos.open ? '<span class="tag hold">持有中</span>' : '<span class="tag">调仓卖出</span>';
      return `<tr>
        <td class="l"><b>${pos.code}</b> ${pos.name || ""}</td>
        <td>${fmt(pos.buy_px, 2)}</td>
        <td><input type="number" step="0.01" data-k="${k}" data-f="buy" value="${e.buy}"></td>
        <td>${fmt(pos.shares)}</td>
        <td><input type="number" step="100" data-k="${k}" data-f="shares" value="${e.shares}"></td>
        <td>${pos.sell_px == null ? fmt(pos.last_px, 2) + "（最新）" : fmt(pos.sell_px, 2)}</td>
        <td><input type="number" step="0.01" data-k="${k}" data-f="sell" value="${e.sell == null ? "" : e.sell}" placeholder="${pos.open ? "空=按最新价" : ""}"></td>
        <td>${pos.sell_date || "—"}</td>
        <td data-pnl="${k}">–</td>
        <td data-ret="${k}">–</td>
        <td class="l">${tag}</td></tr>`;
    }).join("");
    div.innerHTML = `<div class="phead"><span class="t">第 ${p.idx} 期</span>
      <span class="meta">买入 ${p.buy_date}${p.open ? " · 持有中" : " · 卖出至 " + p.sell_date}</span>
      <span class="sum" data-psum="${p.idx}"></span></div>
      <div class="scroll"><table><thead><tr>
      <th class="l">股票</th><th>推荐买入价</th><th>实际买入价</th><th>推荐股数</th><th>持仓数量</th><th>推荐卖出价</th><th>实际卖出价</th><th>卖出日</th><th>盈亏</th><th>收益率</th><th class="l">类型</th>
      </tr></thead><tbody>${rows}</tbody></table></div>`;
    host.appendChild(div);
  });
  host.querySelectorAll("input[data-k]").forEach(inp => {
    inp.addEventListener("input", () => {
      store.entries[inp.dataset.k][inp.dataset.f] = inp.value === "" ? "" : parseFloat(inp.value);
      save(); refresh();
    });
  });
  refresh();
}

document.getElementById("capital").addEventListener("input", e => { store.capital = parseFloat(e.target.value) || DATA.capital_default; save(); refresh(); });
document.getElementById("resetBtn").addEventListener("click", () => { store = { capital: DATA.capital_default, entries: {} }; save(); build(); });
document.getElementById("strategyLine").textContent = DATA.strategy + " · 数据截至 " + DATA.as_of;
document.getElementById("footNote").innerHTML =
  "口径说明：本页盈亏 = (卖出价 − 买入价) × 股数，未扣佣金/印花税/滑点。模拟器回测（含全部费用）同期总收益 "
  + DATA.sim_total_ret_pct + "%、最大回撤 " + DATA.sim_mdd_pct + "%，可作对照。未平仓期卖出价留空时按最新收盘价估值；填了实际卖出价即按已实现计。"
  + "<br>月收益率 = 当月平仓的已实现盈亏 ÷ 本金。调仓节奏：每 30 个交易日换仓，止盈线 +100%。";
build();
</script>
</body>
</html>
"""

out_dir = os.path.expanduser("~/workspace/your_files")
os.makedirs(out_dir, exist_ok=True)
out = os.path.join(out_dir, "x3-tracker.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False)))
print("wrote", out, os.path.getsize(out), "bytes")
