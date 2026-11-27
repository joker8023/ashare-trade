import fs from "node:fs/promises";
const UA = { "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36", "Referer": "https://quote.eastmoney.com/" };
const jget = async (u, n = 8) => { let e; for (let i = 0; i < n; i++) { try { const r = await fetch(u, { headers: UA }); if (!r.ok) throw new Error("HTTP " + r.status); return await r.json(); } catch (x) { e = x; await new Promise(r => setTimeout(r, 300 + 200 * i)); } } throw e; };
const FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048";
const seen = new Map();
for (let pn = 1; pn <= 70; pn++) {
  let d; try { d = await jget("https://push2.eastmoney.com/api/qt/clist/get?pn=" + pn + "&pz=100&po=1&np=1&fltt=2&invt=2&fid=f3&fs=" + encodeURIComponent(FS) + "&fields=f3,f12,f14"); } catch { continue; }
  const df = d?.data?.diff; if (!df || !df.length) break;
  let add = 0; for (const s of df) if (s?.f12 && !seen.has(s.f12)) { seen.set(s.f12, s); add++; }
  const mn = Math.min(...df.map(s => typeof s.f3 === "number" ? s.f3 : 999));
  if (df.length < 100 || (add === 0 && pn > 2)) break;
  await new Promise(r => setTimeout(r, 120));
}
const arr = [...seen.values()].filter(s => typeof s.f3 === "number");
const cnt = (lo, hi) => arr.filter(s => s.f3 >= lo && s.f3 < hi).length;
const res = { 采样: arr.length, "涨停(>=9.8)": cnt(9.8, 999), "5-9.8%": cnt(5, 9.8), "3-5%": cnt(3, 5), "2.5-3%": cnt(2.5, 3) };
console.log(JSON.stringify(res));
