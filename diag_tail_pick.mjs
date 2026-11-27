import fs from "node:fs/promises";
const UA = { "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36", "Referer": "https://quote.eastmoney.com/" };
const jget = async (u, n = 3) => { let e; for (let i = 0; i < n; i++) { try { const r = await fetch(u, { headers: UA }); if (!r.ok) throw new Error("HTTP " + r.status); return await r.json(); } catch (x) { e = x; await new Promise(r => setTimeout(r, 200 * (i + 1))); } } throw e; };
const pool = async (items, n, fn) => { const out = []; let i = 0; await Promise.all(Array.from({ length: n }, async () => { while (true) { const k = i++; if (k >= items.length) return; try { out.push(await fn(items[k])); } catch (e) { out.push({ __error: e.message, code: items[k].f12 }); } } })); return out; };
const secid = c => (/^(6|9|688|689)/.test(c) ? "1." : "0.") + c;
const BOARD = c => /^(688|689)/.test(c) ? 0.20 : /^(300|301|302)/.test(c) ? 0.20 : /^(8|4|920)/.test(c) ? 0.30 : 0.10;
const r2 = x => Math.round(x * 100) / 100;

const FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048";
const seen = new Map();
for (let pn = 1; pn <= 90; pn++) {
  const d = await jget("https://push2.eastmoney.com/api/qt/clist/get?pn=" + pn + "&pz=100&po=1&np=1&fltt=2&invt=2&fid=f3&fs=" + encodeURIComponent(FS) + "&fields=f2,f3,f8,f10,f12,f14,f20,f21,f62,f100");
  const diff = d?.data?.diff; if (!diff || !diff.length) break;
  let added = 0; for (const s of diff) if (s?.f12 && !seen.has(s.f12)) { seen.set(s.f12, s); added++; }
  const mn = Math.min(...diff.map(s => typeof s.f3 === "number" ? s.f3 : 999));
  if (diff.length < 100 || mn < 2.5 || added === 0) break;
}
const all = [...seen.values()].filter(s => typeof s.f3 === "number" && typeof s.f2 === "number" && s.f2 > 0);
const band = all.filter(s => s.f3 >= 3 && s.f3 <= 5 && !/ST|退/.test(s.f14 || ""));
const c1 = band.filter(s => (s.f20 || 0) < 2e10 && (s.f10 || 0) > 1 && s.f8 >= 5 && s.f8 <= 10);

const rows = await pool(c1, 6, async (s) => {
  const k = await jget("https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=" + secid(s.f12) + "&klt=101&fqt=0&end=20500101&lmt=12&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61");
  const bars = (k?.data?.klines || []).map(l => { const p = l.split(","); return { date: p[0], close: +p[2], high: +p[3], pct: +p[8] }; });
  const lim = BOARD(s.f12) * (/(ST)/.test(s.f14 || "") && BOARD(s.f12) === 0.10 ? 0.5 : 1);
  const hist = bars.slice(0, -1); const rec = hist.slice(-4); const hits = [];
  rec.forEach((b, i) => {
    const prev = hist[hist.length - rec.length + i - 1]; if (!prev) return;
    const up = r2(prev.close * (1 + lim));
    if (b.high >= up - 0.005) hits.push({ d: b.date, closed: b.close >= up - 0.005, pct: b.pct, nd: hist.length - (hist.length - rec.length + i) });
  });
  if (!hits.length) return { code: s.f12, name: s.f14, skip: true };
  const t = await jget("https://push2his.eastmoney.com/api/qt/stock/trends2/get?secid=" + secid(s.f12) + "&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58&iscr=0&ndays=1");
  const tr = (t?.data?.trends || []).map(l => { const p = l.split(","); return { t: p[0].slice(11, 16), price: +p[2], avg: +p[7] }; }).filter(x => x.price > 0);
  const hm = x => x.t;
  const belowAll = tr.filter(b => b.price < b.avg).length;
  const pm = tr.filter(b => hm(b) >= "13:30");
  const belowPm = pm.filter(b => b.price < b.avg).length;
  const tail = tr.filter(b => hm(b) >= "14:30"); const head = tr.filter(b => hm(b) < "14:30");
  const hiAll = Math.max(...tr.map(b => b.price)); const hiAllT = tr.find(b => b.price === hiAll).t;
  const hiHead = Math.max(...head.map(b => b.price)); const hiTail = Math.max(...tail.map(b => b.price));
  const hiTailT = tail.find(b => b.price === hiTail).t;
  const after = tr.slice(tr.findIndex(b => b.t === hiTailT) + 1);
  const lowAfter = after.length ? after.reduce((a, b) => (b.price < a.price ? b : a)) : null;
  const last = tr[tr.length - 1];
  const pb = lowAfter ? (hiTail - lowAfter.price) / hiTail : 0;
  const brk = lowAfter ? after.some(b => b.price < b.avg) : false;
  return {
    code: s.f12, name: s.f14, pct: s.f3, price: s.f2, tok: s.f8, vr: s.f10, cap: +(s.f20 / 1e8).toFixed(1), ind: s.f100, flow: Math.round((s.f62 || 0) / 1e4),
    hits: hits.map(h => h.d.slice(5) + (h.closed ? "封" : "触")), nHits: hits.length,
    belowAll, belowAllPct: +(belowAll / tr.length * 100).toFixed(0), belowPm, bars: tr.length,
    hiAll, hiAllT, hiHead, hiTail, hiTailT, tailGap: +((hiTail - hiAll) / hiAll * 100).toFixed(2),
    pb: +(pb * 100).toFixed(2), brk, vsAvg: +((last.price - last.avg) / last.avg * 100).toFixed(2), lastT: last.t,
    avg: last.avg, minGapAfter: lowAfter ? +((lowAfter.price - lowAfter.avg) / lowAfter.avg * 100).toFixed(2) : null,
  };
});

const ok = rows.filter(r => r && !r.__error && !r.skip);
ok.sort((a, b) => b.nHits - a.nHits || a.belowAll - b.belowAll);
await fs.writeFile("/Users/joker/coding/ashare-trade/results/tail_pick_detail_" + new Date().toISOString().slice(0, 16).replace(/[:T]/g, "") + ".json", JSON.stringify({ at: new Date().toISOString(), c1: c1.length, ok }, null, 2));

console.log("第5步后 39 只中的涨停记忆命中:", ok.length, "/", c1.length);
for (const r of ok) {
  console.log(
    r.code, r.name, r.pct + "%", "价" + r.price, "换" + r.tok + "%", "量比" + r.vr, r.cap + "亿", r.ind,
    "| 涨停:", r.hits.join(","),
    "| 全天价<均价 " + r.belowAllPct + "%, 午后" + r.belowPm + "根",
    "| 日高" + r.hiAll + "@" + r.hiAllT, "尾盘高" + r.hiTail + "@" + r.hiTailT, "差" + r.tailGap + "%",
    "| 回踩" + r.pb + "%", "破均价:" + r.brk, "| 现价距均价+" + r.vsAvg + "%"
  );
}
