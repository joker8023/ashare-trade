#!/usr/bin/env node
// 尾盘选股 6 步漏斗：涨幅3-5% + 近3-4日涨停记忆 + 市值<200亿 + 量比>1 + 换手5-10% + 分时图三信号
import fs from "node:fs/promises";

const UA = {
  "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
  "Referer": "https://quote.eastmoney.com/",
  "Accept": "*/*",
};

async function jget(url, tries = 3) {
  let lastErr;
  for (let i = 0; i < tries; i++) {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 15000);
      const r = await fetch(url, { headers: UA, signal: ctrl.signal });
      clearTimeout(t);
      if (!r.ok) throw new Error("HTTP " + r.status);
      const txt = await r.text();
      return JSON.parse(txt);
    } catch (e) {
      lastErr = e;
      await new Promise((res) => setTimeout(res, 250 * (i + 1)));
    }
  }
  throw new Error("fetch failed: " + lastErr.message + " :: " + url.slice(0, 120));
}

async function pool(items, n, fn) {
  const out = new Array(items.length);
  let idx = 0;
  await Promise.all(
    Array.from({ length: Math.min(n, items.length) }, async () => {
      while (true) {
        const i = idx++;
        if (i >= items.length) return;
        try { out[i] = await fn(items[i], i); } catch (e) { out[i] = { __error: e.message }; }
      }
    })
  );
  return out;
}

const BOARD = (code) => {
  if (/^(688|689)/.test(code)) return { name: "科创板", limit: 0.20 };
  if (/^(300|301|302)/.test(code)) return { name: "创业板", limit: 0.20 };
  if (/^(8|4|920)/.test(code)) return { name: "北交所", limit: 0.30 };
  return { name: "主板", limit: 0.10 };
};
const secid = (code) => (/^(6|9|688|689)/.test(code) ? "1." : "0.") + code;
const r2 = (x) => Math.round(x * 100) / 100;

// ---------------- 1. 全市场快照 ----------------
const FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048";
async function snapshot() {
  const seen = new Map();
  for (let pn = 1; pn <= 90; pn++) {
    const u =
      "https://push2.eastmoney.com/api/qt/clist/get?pn=" + pn +
      "&pz=100&po=1&np=1&fltt=2&invt=2&fid=f3&fs=" + encodeURIComponent(FS) +
      "&fields=f2,f3,f8,f10,f12,f14,f20,f21,f62,f100";
    const d = await jget(u);
    const diff = d?.data?.diff;
    if (!diff || !diff.length) break;
    let added = 0;
    for (const s of diff) if (s?.f12 && !seen.has(s.f12)) { seen.set(s.f12, s); added++; }
    const minPct = Math.min(...diff.map((s) => (typeof s.f3 === "number" ? s.f3 : 999)));
    if (diff.length < 100 || minPct < 2.5 || added === 0) break;
  }
  return [...seen.values()];
}

// ---------------- 2. 日线（涨停记忆） ----------------
async function klines(code) {
  const u = "https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=" + secid(code) +
    "&klt=101&fqt=0&end=20500101&lmt=12&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61";
  const d = await jget(u);
  const raw = d?.data?.klines || [];
  return raw.map((line) => {
    const p = line.split(",");
    return { date: p[0], open: +p[1], close: +p[2], high: +p[3], low: +p[4], vol: +p[5], pct: +p[8] };
  });
}

function limitMemory(bars, code, isST) {
  // bars: 升序，最后一根是今天
  const bd = BOARD(code);
  const lim = isST && bd.name === "主板" ? 0.05 : bd.limit;
  const hist = bars.slice(0, -1); // 排除今天
  const recent = hist.slice(-4); // 最近 4 个交易日
  const hits = [];
  for (let i = 0; i < recent.length; i++) {
    const idx = hist.length - recent.length + i;
    const prev = hist[idx - 1];
    const b = recent[i];
    if (!prev) continue;
    const up = r2(prev.close * (1 + lim));
    const closedAt = b.close >= up - 0.005;
    const touched = b.high >= up - 0.005;
    const nDaysAgo = hist.length - idx;
    if (touched) hits.push({ date: b.date, nDaysAgo, closedAt, touched, pct: b.pct, up });
  }
  return { limitPct: lim, board: bd.name, hits, recent: recent.map((b) => ({ d: b.date, pct: b.pct })) };
}

// ---------------- 3. 分时 ----------------
async function trends(code) {
  const u = "https://push2his.eastmoney.com/api/qt/stock/trends2/get?secid=" + secid(code) +
    "&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58&iscr=0&ndays=1";
  const d = await jget(u);
  const raw = d?.data?.trends || [];
  return raw.map((line) => {
    const p = line.split(",");
    return { t: p[0], price: +p[2], high: +p[3], low: +p[4], avg: +p[7] };
  }).filter((x) => x.price > 0);
}

function intradaySignals(tr) {
  if (tr.length < 60) return { ok: false, reason: "分时数据不足(" + tr.length + ")" };
  const hm = (t) => t.slice(11, 16);
  // 1) 全天在均价线之上（strict: 0 根在均价线下；loose: 线下占比<15% 且最深不破0.5%）
  let below = 0, maxBelowPct = 0;
  for (const b of tr) {
    const gap = (b.price - b.avg) / b.avg;
    if (gap < 0) { below++; if (-gap > maxBelowPct) maxBelowPct = -gap; }
  }
  const aboveAllDay = below === 0;
  const aboveLoose = below / tr.length < 0.15 && maxBelowPct <= 0.005;
  // 2) 14:30 后创出当天新高
  const tail = tr.filter((b) => hm(b.t) >= "14:30");
  const head = tr.filter((b) => hm(b.t) < "14:30");
  if (!tail.length) return { ok: false, reason: "无14:30后数据" };
  const hiHead = Math.max(...head.map((b) => b.price));
  const hiAll = Math.max(...tr.map((b) => b.price));
  const hiTailBar = tail.reduce((a, b) => (b.price > a.price ? b : a), tail[0]);
  const tailNewHigh = hiTailBar.price > hiHead + 1e-9 && hiTailBar.price >= hiAll - 1e-9;
  // 3) 新高后回踩，但不跌破均价线
  const afterIdx = tr.findIndex((b) => b.t === hiTailBar.t);
  const after = tr.slice(afterIdx + 1);
  let pullbackPct = 0, minGapPct = null, brokeAvg = false, lowAfterT = null;
  if (after.length) {
    const lowAfter = after.reduce((a, b) => (b.price < a.price ? b : a), after[0]);
    pullbackPct = (hiTailBar.price - lowAfter.price) / hiTailBar.price;
    minGapPct = (lowAfter.price - lowAfter.avg) / lowAfter.avg;
    lowAfterT = hm(lowAfter.t);
    brokeAvg = lowAfter.price < lowAfter.avg;
  }
  const hasPullback = pullbackPct >= 0.0015 && after.length >= 3;
  const holdsAvg = after.length ? !brokeAvg : true;
  const openBar = tr[0];
  const last = tr[tr.length - 1];
  return {
    ok: aboveAllDay && tailNewHigh && hasPullback && holdsAvg,
    okLoose: aboveLoose && tailNewHigh && hasPullback && holdsAvg,
    score: (aboveAllDay ? 2 : aboveLoose ? 1 : 0) + (tailNewHigh ? 2 : 0) + (hasPullback ? 1 : 0) + (holdsAvg ? 1 : 0),
    aboveAllDay, aboveLoose, belowBars: below, maxBelowPct: +(maxBelowPct * 100).toFixed(2), belowRatio: +(below / tr.length * 100).toFixed(1),
    tailNewHigh, hiHead, hiAll, hiTail: hiTailBar.price, hiTailTime: hm(hiTailBar.t),
    hasPullback, pullbackPct: +(pullbackPct * 100).toFixed(2), lowAfterT,
    holdsAvg, minGapPct: minGapPct === null ? null : +(minGapPct * 100).toFixed(2),
    open: openBar.price, last: { t: hm(last.t), price: last.price, avg: last.avg },
    vsAvgPct: +((last.price - last.avg) / last.avg * 100).toFixed(2),
    bars: tr.length,
  };
}

// ---------------- main ----------------
const t0 = Date.now();
const snap = await snapshot();
const out = { runAt: new Date().toISOString(), universe: snap.length, funnel: {}, picks: [] };
out.funnel.universe = snap.length;

const valid = snap.filter((s) => typeof s.f3 === "number" && typeof s.f2 === "number" && s.f2 > 0);
const band = valid.filter((s) => s.f3 >= 3 && s.f3 <= 5);
out.funnel.band3to5 = band.length;

const noST = band.filter((s) => !/ST|退/.test(s.f14 || ""));
out.funnel.excludeST = noST.length;

const capOK = noST.filter((s) => (s.f20 || 0) < 2e10);
out.funnel.capLt200y = capOK.length;

const vrOK = capOK.filter((s) => (s.f10 || 0) > 1);
out.funnel.volRatioGt1 = vrOK.length;

const toOK = vrOK.filter((s) => s.f8 >= 5 && s.f8 <= 10);
out.funnel.turnover5to10 = toOK.length;

// 涨停记忆
const kmem = await pool(toOK, 6, async (s) => {
  const bars = await klines(s.f12);
  const m = limitMemory(bars, s.f12, /ST/.test(s.f14 || ""));
  return { ...s, _mem: m };
});
const memOK = kmem.filter((s) => s && !s.__error && s._mem && s._mem.hits.length > 0);
out.funnel.limitMemory = memOK.length;

// 分时
const withTrend = await pool(memOK, 5, async (s) => {
  const tr = await trends(s.f12);
  return { ...s, _sig: intradaySignals(tr), _tr: tr };
});
out.funnel.intradayOK = withTrend.filter((x) => x && x._sig && x._sig.ok).length;

out.funnel.intradayLoose = withTrend.filter((x) => x && x._sig && x._sig.okLoose).length;
for (const s of withTrend.sort((a, b) => (b._sig?.ok ? 1 : 0) - (a._sig?.ok ? 1 : 0) || (b._sig?.score||0) - (a._sig?.score||0) || b.f3 - a.f3)) {
  if (!s || s.__error) continue;
  out.picks.push({
    code: s.f12, name: s.f14, industry: s.f100,
    pct: s.f3, price: s.f2, turnover: s.f8, volRatio: s.f10,
    capYi: +(s.f20 / 1e8).toFixed(1), floatCapYi: +(s.f21 / 1e8).toFixed(1),
    mainInflowWan: Math.round((s.f62 || 0) / 1e4),
    board: s._mem.board, limitPct: s._mem.limitPct * 100,
    limitHits: s._mem.hits.map((h) => h.date + (h.closedAt ? "(封板)" : "(触板)") + " " + h.pct.toFixed(2) + "%"),
    recentPct: s._mem.recent,
    signal: s._sig,
  });
}

await fs.writeFile("/Users/joker/coding/ashare-trade/results/tail_pick_" + out.runAt.slice(0, 10) + ".json", JSON.stringify(out, null, 2));

console.log(JSON.stringify(out.funnel));
console.log("耗时 " + ((Date.now() - t0) / 1000).toFixed(1) + "s, 候选 " + out.picks.length);
for (const p of out.picks) {
  console.log(
    (p.signal.ok ? "✅" : "  ") + " " + p.code + " " + p.name + " " + p.pct + "% 价" + p.price +
    " 换手" + p.turnover + "% 量比" + p.volRatio + " 市值" + p.capYi + "亿 主力" + p.mainInflowWan + "万 | " +
    p.limitHits.join(",") + " | 均价上方:" + p.signal.aboveAllDay + " 尾盘新高:" + p.signal.tailNewHigh +
    " 回踩" + p.signal.pullbackPct + "% 不破均价:" + p.signal.holdsAvg
  );
}
