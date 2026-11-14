// Reads the files written by the pipeline. Format: docs/data-contract.md
const BASE = "data/";
const cache = new Map();

async function get(path) {
  if (!cache.has(path)) {
    cache.set(path, fetch(BASE + path).then((r) => {
      if (!r.ok) throw new Error(`${path}: ${r.status}`);
      return r.json();
    }));
  }
  return cache.get(path);
}

export const loadManifest = () => get("manifest.json");
export const loadTrend = (ds, v, period, mask) => get(`trend/${ds}/${v}/${period}__${mask}.json`);
export const loadSeries = (ds, v, latIdx) =>
  get(`series/${ds}/${v}/${latIdx == null ? "global" : "lat_" + String(latIdx).padStart(2, "0")}.json`);
export const loadAgreement = (file) => get(file);

// "2002-09" + n months -> array of {y, m, t} where t is a month count
export function monthAxis(start, n) {
  const [y0, m0] = start.split("-").map(Number);
  const out = [];
  for (let i = 0; i < n; i++) {
    const k = y0 * 12 + (m0 - 1) + i;
    out.push({ y: Math.floor(k / 12), m: (k % 12) + 1, t: k });
  }
  return out;
}
export const monthKey = (s) => { const [y, m] = s.split("-").map(Number); return y * 12 + (m - 1); };
