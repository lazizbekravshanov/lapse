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
export const loadCatalog = () => get("data/catalog.json");
export const loadGlossary = () => get("content/glossary.json");

// The hub publishes where each answer lives (catalog.routes). Paths are built from
// those templates, never typed in here.
let routes = null;
export const setRoutes = (r) => { routes = r; };
const fillRoute = (template, values) => "data/" + template.replace(/\{(\w+)(?::02d)?\}/g, (m, key) =>
  (m.includes(":02d") ? String(values[key]).padStart(2, "0") : values[key]));

export const loadTrend = (dataset, variable, period, mask, method) =>
  get(fillRoute(routes.trend, { dataset, variable, period, mask, method }));
export const loadPairs = (dataset, variable, period, method) =>
  get(fillRoute(routes.pairs, { dataset, variable, period, method }));
export const loadSeries = (dataset, variable, place) => get(place.region
  ? fillRoute(routes.series_region, { dataset, variable, region: place.region })
  : fillRoute(routes.series_lat, { dataset, variable, lat: place.lat }));

// "2002-09" + n months -> [{y, m, t}] where t counts months
export function monthAxis(start, n) {
  const [y0, m0] = start.split("-").map(Number);
  return Array.from({ length: n }, (_, i) => {
    const k = y0 * 12 + (m0 - 1) + i;
    return { y: Math.floor(k / 12), m: (k % 12) + 1, t: k };
  });
}
export const monthKey = (s) => { const [y, m] = s.split("-").map(Number); return y * 12 + (m - 1); };
