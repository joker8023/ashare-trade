#!/usr/bin/env node
/**
 * A股尾盘六步选股 —— 六步漏斗量化实现
 *
 * 用法（在项目根目录）:
 *   node .dsh/skills/ashare-six-step-screen/scripts/screen.mjs
 *   node .../screen.mjs --pct 3 5 --cap 200 --vr 1 --turn 5 10 --days 4
 *   node .../screen.mjs --pct 5 8 --breadth --charts 3
 *
 * 输出: results/screen_<时间戳>.json + 控制台表格 + results/min/<code>.json (供画图)
 */
import fs from "node:fs/promises";
import path from "node:path";

const ROOT = process.cwd();
const OUT_DIR = path.join(ROOT, "results");
const MIN_DIR = path.join(OUT_DIR, "min");

// ---------- 参数 ----------
const argv = process.argv.slice(2);
const opt = { pctLo: 3, pctHi: 5, capMax: 200, vrMin: 1, turnLo: 5, turnHi: 10, days: 4, charts: 0, breadth: false, out: null, quiet: false };
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === "--pct") { opt.pctLo = +argv[++i]; opt.pctHi = +argv[++i]; }
  else if (a === "--cap") opt.capMax = +argv[++i];
  else if (a === "--vr") opt.vrMin = +argv[++i];
  else if (a === "--turn") { opt.turnLo = +argv[++i]; opt.turnHi = +argv[++i]; }
  else if (a === "--days") opt.days = +argv[++i];
  else if (a === "--charts") opt.charts = +argv[++i];
  else if (a === "--breadth") opt.breadth = true;
  else if (a === "--out") opt.out = argv[++i];
  else if (a === "--quiet") opt.quiet = true;
}

const UA = {
  "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
  "Referer": "https://quote.eastmoney.com/",
};

async function jget(url, tries = 6) {
  let last;
  for (let i = 0; i < tries; i++) {
    try {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 15000);
      const res = await fetch(url, { headers: UA, signal: ctrl.signal });
      clearTimeout(timer);
      if (!res.ok) throw new Error("HTTP " + res.status);
      return await res.json();
    } catch (e) {
      last = e;
      await new Promise((r) => setTimeout(r, 300 + 250 * i));
    }
  }
  throw new Error("请求失败 " + last.message + " :: " + url.slice(0, 120));
}

async function pool(items, n, fn) {
  const out = new Array(items.length);
  let idx = 0;
  await Promise.all(
    Array.from({ length: Math.min(n, items.length) }, async () => {
      while (true) {
        const i = idx++;
        if (i >= items.length) return;
        try { out[i] = await fn(items[i], i); }
        catch (e) { out[i] = { __error: e.message, code: items[i].f12 }; }
      }
    })
  );
  return out;
}

// ---------- 板块规则 ----------
function limitPctOf(code, name) {
  const isST = /ST/i.test(name || "");
  if (/^(688|689)/.test(code)) return 0.20;               // 科创板
  if (/^(300|301|302)/.test(code)) return 0.20;            // 创业板（含创业板ST）
  if (/^(8|4|920)/.test(code)) return 0.30;                // 北交所
  return isST ? 0.05 : 0.10;                               // 主板 / 主板ST
}
const secidOf = (code) => (/^(6|9|688|689)/.test(code) ? "1." : "0.") + code;
const round2 = (x) => Math.round(x * 100) / 100;

// ---------- 市场环境 ----------
const INDEXES = [["上证指数", "1.000001"], ["深证成指", "0.399001"], ["创业板指", "0.399006"], ["科创50", "1.000688"], ["北证50", "0.899050"]];

async function marketRegime() {
  const idx = [];
  for (const [n, s] of INDEXES) {
    try {
      const d = await jget("https://push2.eastmoney.com/api/qt/stock/get?secid=" + s + "&fields=f43,f60,f170");
      if (d?.data) idx.push({ name: n, pct: +(d.data.f170 / 100).toFixed(2) });
    } catch { /* 指数缺失不阻断 */ }
  }
  const hot = idx.reduce((a, b) => (b.pct > (a?.pct ?? -99) ? b : a), null);
  return { indexes: idx, extreme: hot && hot.pct >= 5 ? hot.name + " " + (hot.pct >= 0 ? "+" : "") + hot.pct + "%" : null };
}

const FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048";

async function fetchUniverse() {
  const seen = new Map();
  let pageFail = 0;
  const floor = opt.pctLo - 0.6;
  for (let pn = 1; pn <= 90; pn++) {
    let d;
    try {
      d = await jget("https://push2.eastmoney.com/api/qt/clist/get?pn=" + pn + "&pz=100&po=1&np=1&fltt=2&invt=2&fid=f3&fs=" + encodeURIComponent(FS) +
        "&fields=f2,f3,f8,f10,f12,f14,f20,f21,f62,f100");
    } catch { if (++pageFail > 3) break; continue; }
    const diff = d?.data?.diff;
    if (!diff || !diff.length) break;
    let added = 0;
    for (const s of diff) if (s?.f12 && !seen.has(s.f12)) { seen.set(s.f12, s); added++; }
    const minPct = Math.min(...diff.map((s) => (typeof s.f3 === "number" ? s.f3 : 999)));
    if (diff.length < 100 || minPct < floor || (added === 0 && pn > 2)) break;
  }
  return [...seen.values()];
}

async function breadth() {
  const seen = new Map();
  for (let pn = 1; pn <= 70; pn++) {
    let d;
    try { d = await jget("https://push2.eastmoney.com/api/qt/clist/get?pn=" + pn + "&pz=100&po=1&np=1&fltt=2&invt=2&fid=f3&fs=" + encodeURIComponent(FS) + "&fields=f3,f12"); }
    catch { continue; }
    const df = d?.data?.diff;
    if (!df || !df.length) break;
    let added = 0;
    for (const s of df) if (s?.f12 && !seen.has(s.f12)) { seen.set(s.f12, s); added++; }
    if (df.length < 100 || (added === 0 && pn > 2)) break;
    await new Promise((r) => setTimeout(r, 100));
  }
  const arr = [...seen.values()].filter((s) => typeof s.f3 === "number");
  const c = (lo, hi) => arr.filter((s) => s.f3 >= lo && s.f3 < hi).length;
  return { sample: arr.length, up: arr.filter((s) => s.f3 > 0).length, limit: c(9.8, 999), mid: c(5, 9.8), band: c(opt.pctLo, opt.pctHi), low: c(2.5, 3) };
}

// ---------- 个股数据 ----------
async function kline(code) {
  const d = await jget("https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=" + secidOf(code) +
    "&klt=101&fqt=0&end=20500101&lmt=" + (opt.days + 8) +
    "&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61");
  return (d?.data?.klines || []).map((l) => {
    const p = l.split(",");
    return { date: p[0], open: +p[1], close: +p[2], high: +p[3], low: +p[4], pct: +p[8] };
  });
}

function limitMemory(bars, code, name) {
  const lim = limitPctOf(code, name);
  const hist = bars.slice(0, -1);               // 排除今天
  const recent = hist.slice(-opt.days);          // 最近 N 个交易日
  const hits = [];
  recent.forEach((b, i) => {
    const prev = hist[hist.length - recent.length - 1 + i];
    if (!prev) return;
    const up = round2(prev.close * (1 + lim));
    if (b.high >= up - 0.005) {
      hits.push({ date: b.date, zt: b.close >= up - 0.005, pct: b.pct, up, daysAgo: hist.length - (hist.length - recent.length + i) });
    }
  });
  return { lim, hits };
}

async function trends(code) {
  const d = await jget("https://push2his.eastmoney.com/api/qt/stock/trends2/get?secid=" + secidOf(code) +
    "&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58&iscr=0&ndays=1");
  return {
    pre: d?.data?.preClose,
    tr: (d?.data?.trends || []).map((l) => {
      const p = l.split(",");
      // p[0] 形如 "2026-11-27 09:31"；p[2]=最新价 p[3]=最高 p[4]=最低 p[7]=均价(VWAP)
      return { t: p[0].slice(11, 16), price: +p[2], high: +p[3], low: +p[4], avg: +p[7] };
    }).filter((x) => x.price > 0),
  };
}

/** 第⑥步：分时三信号 + 全量诊断 */
function intradaySignals(tr) {
  if (tr.length < 60) return { ok: false, reason: "分时数据不足(" + tr.length + "根)" };
  // 信号1：股价全天运行在均价线之上
  const belowBars = tr.filter((b) => b.price < b.avg);
  const belowLow = tr.filter((b) => b.low < b.avg).length;
  const maxBelow = tr.reduce((m, b) => Math.max(m, (b.avg - b.price) / b.avg), 0);
  const belowIdx = tr.map((b, i) => (b.price < b.avg ? i : -1)).filter((i) => i >= 0);
  const lastBelowT = belowIdx.length ? tr[belowIdx[belowIdx.length - 1]].t : null;
  const pmBelow = tr.filter((b) => b.t >= "13:30" && b.price < b.avg).length;
  const aboveAll = belowBars.length === 0;
  const openOnly = lastBelowT === null || lastBelowT <= "10:00";

  // 信号2：14:30 后创当天新高（用分钟最高价，不能用收盘价）
  const head = tr.filter((b) => b.t < "14:30");
  const tail = tr.filter((b) => b.t >= "14:30");
  if (!tail.length) return { ok: false, reason: "无 14:30 后数据" };
  const hiAll = Math.max(...tr.map((b) => b.high));
  const hiAllT = tr.find((b) => b.high === hiAll).t;
  const hiHead = Math.max(...head.map((b) => b.high));
  const hiTail = Math.max(...tail.map((b) => b.high));
  const hiTailT = tail.find((b) => b.high === hiTail).t;
  const tailNewHigh = hiTail > hiHead + 1e-9;
  const tailGap = +((hiTail - hiAll) / hiAll * 100).toFixed(2);

  // 信号3：创新高后回踩，但不破均价线
  const after = tr.slice(tr.findIndex((b) => b.t === hiTailT) + 1);
  const lowAfter = after.length ? after.reduce((a, b) => (b.low < a.low ? b : a)) : null;
  const pullback = lowAfter ? (hiTail - lowAfter.low) / hiTail : 0;
  const brokeAvg = lowAfter ? lowAfter.low < lowAfter.avg : false;
  const gapToAvg = lowAfter ? +((lowAfter.low - lowAfter.avg) / lowAfter.avg * 100).toFixed(2) : null;
  const hasPullback = pullback >= 0.0015 && after.length >= 3;
  const holdsAvg = !brokeAvg;

  const last = tr[tr.length - 1];
  const fails = [];
  if (!aboveAll) fails.push("① 全天 " + (belowBars.length / tr.length * 100).toFixed(1) + "% 时间在均价线下方（最深 " + (maxBelow * 100).toFixed(2) + "%，末次 " + lastBelowT + "，午后 " + pmBelow + " 根）");
  if (!tailNewHigh) fails.push("② 日高 " + hiAll.toFixed(2) + "@" + hiAllT + "，14:30 后最高 " + hiTail.toFixed(2) + "@" + hiTailT + "，" + (tailGap === 0 ? "仅回抽到日高未突破" : "差 " + tailGap.toFixed(2) + "%"));
  const canCheck3 = tailNewHigh && after.length >= 3;
  if (canCheck3 && !hasPullback) fails.push("③ 新高后无明显回踩（仅 " + (pullback * 100).toFixed(2) + "%）");
  if (canCheck3 && !holdsAvg) fails.push("③ 新高后回踩跌破均价线（" + gapToAvg + "%）");

  const near = (!aboveAll && openOnly) || (!tailNewHigh && tailGap >= -1.0) || (canCheck3 && (!hasPullback || !holdsAvg) && gapToAvg !== null && gapToAvg >= -0.3);

  return {
    ok: fails.length === 0,
    fails, near,
    aboveAll, belowBars: belowBars.length, belowLow, maxBelow: +(maxBelow * 100).toFixed(2), lastBelowT, pmBelow, openOnly,
    hiAll, hiAllT, hiHead, hiTail, hiTailT, tailNewHigh, tailGap,
    pullback: +(pullback * 100).toFixed(2), holdsAvg, gapToAvg,
    last, vsAvg: +((last.price - last.avg) / last.avg * 100).toFixed(2),
    bars: tr.length,
  };
}

// ---------- 主流程 ----------
const started = Date.now();
const now = new Date();
const hhmm = now.toLocaleTimeString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false }).slice(0, 5);

const universe = await fetchUniverse();
const valid = universe.filter((s) => typeof s.f3 === "number" && typeof s.f2 === "number" && s.f2 > 0);

const F = {};
F["抓取样本(涨幅≥" + (opt.pctLo - 0.6).toFixed(1) + "%)"] = valid.length;
const band = valid.filter((s) => s.f3 >= opt.pctLo && s.f3 <= opt.pctHi);
F["①涨幅 " + opt.pctLo + "-" + opt.pctHi + "%"] = band.length;
const nb = band.filter((s) => !/ST|退/i.test(s.f14 || ""));
F["剔除ST/退市"] = nb.length;
const cap = nb.filter((s) => (s.f20 || 0) < opt.capMax * 1e8);
F["③总市值<" + opt.capMax + "亿"] = cap.length;
const vrf = cap.filter((s) => (s.f10 || 0) > opt.vrMin);
F["④量比>" + opt.vrMin] = vrf.length;
const tof = vrf.filter((s) => s.f8 >= opt.turnLo && s.f8 <= opt.turnHi);
F["⑤换手 " + opt.turnLo + "-" + opt.turnHi + "%"] = tof.length;

const evaluated = await pool(tof, 6, async (s) => {
  const bars = await kline(s.f12);
  const mem = limitMemory(bars, s.f12, s.f14);
  if (!mem.hits.length) return { code: s.f12, skip: true };
  const { pre, tr } = await trends(s.f12);
  const sig = intradaySignals(tr);
  return {
    code: s.f12, name: s.f14, industry: s.f100,
    pct: s.f3, price: s.f2, turnover: s.f8, volRatio: s.f10,
    capYi: +(s.f20 / 1e8).toFixed(1), floatCapYi: +(s.f21 / 1e8).toFixed(1),
    mainInflowWan: Math.round((s.f62 || 0) / 1e4),
    limitPct: mem.lim * 100,
    hits: mem.hits.map((h) => h.date.slice(5) + (h.zt ? "封板" : "触板") + " " + h.pct.toFixed(2) + "%"),
    ztCount: mem.hits.filter((h) => h.zt).length,
    pre, sig, _tr: tr,
  };
});

const hits = evaluated.filter((r) => r && !r.__error && !r.skip);
F["②近 " + opt.days + " 日涨停记忆"] = hits.length;
F["⑥分时三信号全中"] = hits.filter((r) => r.sig.ok).length;

const tier = (r) => (r.sig.ok ? "A" : r.sig.near && r.sig.fails.length === 1 ? "B" : "C");
hits.sort((a, b) => "ABC".indexOf(tier(a)) - "ABC".indexOf(tier(b)) || b.ztCount - a.ztCount || b.volRatio - a.volRatio);

const regime = await marketRegime();
const br = opt.breadth ? await breadth() : null;

const stamp = now.toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false });
const bj = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).formatToParts(now).reduce((a, p) => (a[p.type] = p.value, a), {});
const fname = bj.year + bj.month + bj.day + "_" + bj.hour + bj.minute;
const result = {
  generatedAt: now.toISOString(),
  stamp,
  params: opt,
  funnel: F,
  regime,
  breadth: br,
  candidates: hits.map(({ _tr, ...r }) => ({ ...r, tier: tier(r) })),
};

// ---------- 输出 ----------
await fs.mkdir(MIN_DIR, { recursive: true });
const outPath = opt.out ? path.resolve(ROOT, opt.out) : path.join(OUT_DIR, "screen_" + fname + ".json");
await fs.writeFile(outPath, JSON.stringify(result, null, 2));
for (const r of hits) {
  await fs.writeFile(path.join(MIN_DIR, r.code + ".json"),
    JSON.stringify({ code: r.code, name: r.name, pre: r.pre, pct: r.pct, tok: r.turnover, vr: r.volRatio, cap: r.capYi, tr: r._tr }));
}

const line = (s) => process.stdout.write(s + "\n");
const fmtPct = (v) => (v >= 0 ? "+" : "") + v + "%";
if (!opt.quiet) {
  line("══════ A股尾盘六步选股 ══════");
  line("时间 " + stamp + (hhmm < "14:30" ? "  ⚠️ 早于 14:30，换手/量比为盘中值，①⑤步口径偏小" : ""));
  if (regime.indexes.length) line("指数 " + regime.indexes.map((i) => i.name + " " + (i.pct >= 0 ? "+" : "") + i.pct + "%").join(" · "));
  if (br) line("宽度 样本" + br.sample + " 只，涨≥9.8% " + br.limit + "，5-9.8% " + br.mid + "，" + opt.pctLo + "-" + opt.pctHi + "% " + br.band);
  line("漏斗 " + Object.entries(F).map(([k, v]) => k + "=" + v).join(" → "));
  if (regime.extreme) line("⚠️ 市场情绪极端（" + regime.extreme + "）：目标涨幅区间可能是全市场滞涨股，需在报告中提示用户");
  line("");
  if (!hits.length) line("无候选：①-⑤ 或 ② 已全部筛除。");
  for (const r of hits) {
    line(tier(r) + "  " + r.code + " " + r.name + "  " + r.pct + "%  价" + r.price + "  换手" + r.turnover + "%  量比" + r.volRatio + "  市值" + r.capYi + "亿  主力" + r.mainInflowWan + "万");
    line("   涨停记忆: " + r.hits.join(" / ") + "   |   " + r.industry);
    if (r.sig.ok) line("   ✅ 分时三信号全中；现价距均价 " + fmtPct(r.sig.vsAvg) + "，尾盘新高 " + r.sig.hiTail + "@" + r.sig.hiTailT + "，回踩 " + r.sig.pullback + "% 未破均价");
    else for (const f of r.sig.fails) line("   ✗ " + f);
    line("   现价" + r.sig.last.price + " @" + r.sig.last.t + "  均价" + r.sig.last.avg + "  距线 " + fmtPct(r.sig.vsAvg));
  }
  line("");
  line("结果已写入 " + path.relative(ROOT, outPath));
  if (opt.charts > 0 && hits.length) {
    const codes = hits.slice(0, opt.charts).map((r) => "results/min/" + r.code + ".json").join(" ");
    line("画分时图： .venv/bin/python .dsh/skills/ashare-six-step-screen/scripts/render_fenshi.py " + codes);
  }
}
console.log(JSON.stringify(F));
