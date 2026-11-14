// Reads the files written by the pipeline (docs/data-contract.md) and the
// hand-written words in content/glossary.json. No statistics happen here.
const cache = new Map();

async function get(path) {
  if (!cache.has(path)) {
    cache.set(path, fetch(path).then((r) => {
      if (!r.ok) throw new Error(`${path}: ${r.status}`);
      return r.json();
    }));
  }
  return cache.get(path);
}

export const loadManifest = () => get("data/manifest.json");
export const loadGlossary = () => get("content/glossary.json");
export const loadTrend = (ds, v, period, mask) => get(`data/trend/${ds}/${v}/${period}__${mask}.json`);
export const loadPairs = (ds, v, period) => get(`data/pairs/${ds}/${v}/${period}.json`);
export const loadSeries = (ds, v, place) => get(`data/series/${ds}/${v}/${
  place.region ? "region_" + place.region : "lat_" + String(place.lat).padStart(2, "0")}.json`);

// "2002-09" + n months -> [{y, m, t}] where t counts months
export function monthAxis(start, n) {
  const [y0, m0] = start.split("-").map(Number);
  return Array.from({ length: n }, (_, i) => {
    const k = y0 * 12 + (m0 - 1) + i;
    return { y: Math.floor(k / 12), m: (k % 12) + 1, t: k };
  });
}
export const monthKey = (s) => { const [y, m] = s.split("-").map(Number); return y * 12 + (m - 1); };
