import fs from "node:fs/promises";
const UA = { "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36", "Referer": "https://quote.eastmoney.com/" };
const jget = async (u, n = 6) => { let e; for (let i = 0; i < n; i++) { try { const r = await fetch(u, { headers: UA, keepalive: false }); if (!r.ok) throw new Error("HTTP " + r.status); return await r.json(); } catch (x) { e = x; await new Promise(r => setTimeout(r, 350 * (i + 1))); } } throw e; };
const pool = async (items, n, fn) => { const out = new Array(items.length); let i = 0; await Promise.all(Array.from({ length: n }, async () => { while (true) { const k = i++; if (k >= items.length) return; try { out[k] = await fn(items[k]); } catch (e) { out[k] = { __error: e.message, code: items[k].f12 }; } } })); return out; };
const secid = c => (/^(6|9|688|689)/.test(c) ? "1." : "0.") + c;
const BOARD = c => /^(688|689)/.test(c) ? 0.20 : /^(300|301|302)/.test(c) ? 0.20 : /^(8|4|920)/.test(c) ? 0.30 : 0.10;
const r2 = x => Math.round(x * 100) / 100;

const FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048";
const seen = new Map();
let pageFail = 0;
for (let pn = 1; pn <= 90; pn++) {
  let d;
  try { d = await jget("https://push2.eastmoney.com/api/qt/clist/get?pn=" + pn + "&pz=100&po=1&np=1&fltt=2&invt=2&fid=f3&fs=" + encodeURIComponent(FS) + "&fields=f2,f3,f8,f10,f12,f14,f20,f21,f62,f100"); }
  catch (e) { if (++pageFail > 3) break; continue; }
  const diff = d?.data?.diff; if (!diff || !diff.length) break;
  let added = 0; for (const s of diff) if (s?.f12 && !seen.has(s.f12)) { seen.set(s.f12, s); added++; }
  const mn = Math.min(...diff.map(s => typeof s.f3 === "number" ? s.f3 : 999));
  if (diff.length < 100 || mn < 2.5 || added === 0) break;
}
const all = [...seen.values()].filter(s => typeof s.f3 === "number" && typeof s.f2 === "number" && s.f2 > 0);
const F = {};
F.universe = all.length;
const band = all.filter(s => s.f3 >= 3 && s.f3 <= 5);
F["①涨幅3-5%"] = band.length;
const nb = band.filter(s => !/ST|退/.test(s.f14 || ""));
F["剔除ST/退市"] = nb.length;
const cap = nb.filter(s => (s.f20 || 0) < 2e10);
F["③总市值<200亿"] = cap.length;
const vr = cap.filter(s => (s.f10 || 0) > 1);
F["④量比>1"] = vr.length;
const to = vr.filter(s => s.f8 >= 5 && s.f8 <= 10);
F["⑤换手5-10%"] = to.length;

const rows = await pool(to, 6, async (s) => {
  const k = await jget("https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=" + secid(s.f12) + "&klt=101&fqt=0&end=20500101&lmt=12&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61");
  const bars = (k?.data?.klines || []).map(l => { const p = l.split(","); return { date: p[0], close: +p[2], high: +p[3], pct: +p[8] }; });
  const lim = BOARD(s.f12) * (/ST/.test(s.f14 || "") && BOARD(s.f12) === 0.10 ? 0.5 : 1);
  const hist = bars.slice(0, -1); const rec = hist.slice(-4); const hits = [];
  rec.forEach((b, i) => {
    const prev = hist[hist.length - rec.length + i - 1]; if (!prev) return;
    const up = r2(prev.close * (1 + lim));
    if (b.high >= up - 0.005) hits.push({ d: b.date.slice(5), closed: b.close >= up - 0.005, pct: b.pct });
  });
  if (!hits.length) return { code: s.f12, skip: true };
  const t = await jget("https://push2his.eastmoney.com/api/qt/stock/trends2/get?secid=" + secid(s.f12) + "&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58&iscr=0&ndays=1");
  const pre = t?.data?.preClose;
  const tr = (t?.data?.trends || []).map(l => { const p = l.split(","); return { t: p[0].slice(11, 16), price: +p[2], high: +p[3], low: +p[4], avg: +p[7] }; }).filter(x => x.price > 0);
  // ① 全天在均价线之上（按收盘价判断“运行在线上”，同时统计最低价刺破线的次数）
  const belowBars = tr.filter(b => b.price < b.avg).length;
  const belowLow = tr.filter(b => b.low < b.avg).length;
  const maxBelow = tr.reduce((m, b) => Math.max(m, (b.avg - b.price) / b.avg), 0);
  const belowIdx = tr.map((b, i) => (b.price < b.avg ? i : -1)).filter(i => i >= 0);
  const lastBelow = belowIdx.length ? belowIdx[belowIdx.length - 1] : -1;
  const lastBelowT = lastBelow >= 0 ? tr[lastBelow].t : null;
  const pmBars = tr.filter(b => b.t >= "13:30");
  const pmBelow = pmBars.filter(b => b.price < b.avg).length;
  const openOnly = lastBelow >= 0 ? lastBelowT <= "10:00" : true;
  // ② 14:30 后创当天新高（用分钟最高价）
  const tail = tr.filter(b => b.t >= "14:30"); const head = tr.filter(b => b.t < "14:30");
  const hiAll = Math.max(...tr.map(b => b.high)); const hiAllT = tr.find(b => b.high === hiAll).t;
  const hiHead = Math.max(...head.map(b => b.high)); const hiTail = Math.max(...tail.map(b => b.high));
  const hiTailT = tail.find(b => b.high === hiTail).t;
  const tailHigh = hiTail > hiHead + 1e-9;
  // ③ 新高后回踩，不破均价线
  const tailIdx = tr.findIndex(b => b.t === hiTailT);
  const after = tr.slice(tailIdx + 1);
  const lowAfter = after.length ? after.reduce((a, b) => (b.low < a.low ? b : a)) : null;
  const last = tr[tr.length - 1];
  const pb = lowAfter ? (hiTail - lowAfter.low) / hiTail : 0;
  const brkAfter = lowAfter ? lowAfter.low < lowAfter.avg : false;
  const minGapAfter = lowAfter ? +((lowAfter.low - lowAfter.avg) / lowAfter.avg * 100).toFixed(2) : null;
  const aboveAll = belowBars === 0;
  const hold = !brkAfter;
  const pullback = pb >= 0.0015 && after.length >= 3;
  const s6 = aboveAll && tailHigh && pullback && hold;
  const s6Loose = openOnly && tailHigh && pullback && hold;
  return {
    code: s.f12, name: s.f14, pct: s.f3, price: s.f2, tok: s.f8, vr: s.f10, cap: +(s.f20 / 1e8).toFixed(1), floatCap: +(s.f21 / 1e8).toFixed(1),
    ind: s.f100, flow: Math.round((s.f62 || 0) / 1e4), pre,
    hits, nHits: hits.length, board: BOARD(s.f12) * 100,
    belowBars, belowLow, belowPct: +(belowBars / tr.length * 100).toFixed(1), pmBelow, maxBelow: +(maxBelow * 100).toFixed(2), lastBelowT, openOnly,
    hiAll, hiAllT, hiHead, hiTail, hiTailT, tailGap: +((hiTail - hiAll) / hiAll * 100).toFixed(2),
    pb: +(pb * 100).toFixed(2), brkAfter, hold, pullback, aboveAll, tailHigh, s6, s6Loose, minGapAfter,
    vsAvg: +((last.price - last.avg) / last.avg * 100).toFixed(2), last, avg: last.avg, lastT: last.t,
    _tr: tr,
  };
});

const hits = rows.filter(r => r && !r.__error && !r.skip);
F["②近4日涨停记忆"] = hits.length;
F["⑥分时三信号全中(严格)"] = hits.filter(r => r.s6).length;
F["⑥三信号(线下仅在开盘30-60分钟内)"] = hits.filter(r => r.s6Loose).length;

const stamp = new Date().toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false });
const out = { stamp, funnel: F, at: new Date().toISOString(), rows: hits.map(({ _tr, ...r }) => r) };
await fs.mkdir("/Users/joker/coding/ashare-trade/results/min", { recursive: true });
await fs.writeFile("/Users/joker/coding/ashare-trade/results/final_scan.json", JSON.stringify(out, null, 2));
for (const r of hits) await fs.writeFile("/Users/joker/coding/ashare-trade/results/min/" + r.code + ".json", JSON.stringify({ code: r.code, name: r.name, pre: r.pre, pct: r.pct, tok: r.tok, vr: r.vr, cap: r.cap, tr: r._tr }));

console.log("时间", stamp);
console.log(JSON.stringify(F));
for (const r of hits.sort((a, b) => b.s6 - a.s6 || b.s6Loose - a.s6Loose || a.belowBars - b.belowBars))
  console.log((r.s6 ? "PASS " : r.s6Loose ? "NEAR " : "---- ") + r.code, r.name, r.pct + "%", "价" + r.price, "换" + r.tok + "%", "量比" + r.vr, r.cap + "亿", "| 涨停" + r.hits.map(h => h.d + (h.closed ? "封" : "触")).join(","),
    "| 线下" + r.belowPct + "% 最深" + r.maxBelow + "% 末次" + r.lastBelowT, "午后" + r.pmBelow,
    "| 日高" + r.hiAll + "@" + r.hiAllT, "尾高" + r.hiTail + "@" + r.hiTailT, "新高" + r.tailHigh, "差" + r.tailGap + "%",
    "| 回踩" + r.pb + "%", "守均价" + r.hold + "(" + r.minGapAfter + "%)", "| 距均价+" + r.vsAvg + "%");
