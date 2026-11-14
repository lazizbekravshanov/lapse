// Shared drawing helpers.
export const INK = "#1f2a44", MUTED = "#6b6a66", LINE = "#d9cfbb";
const COOL = [44, 90, 140], MID = [243, 234, 216], WARM = [200, 73, 43];

export function color(v, max, alpha = 1) {
  if (v == null) return `rgba(0,0,0,0)`;
  const x = Math.max(-1, Math.min(1, v / max));
  const to = x < 0 ? COOL : WARM, k = Math.abs(x) ** 0.7;
  const c = MID.map((m, i) => Math.round(m + (to[i] - m) * k));
  return `rgba(${c[0]},${c[1]},${c[2]},${alpha})`;
}

// Sharp canvas on high-density screens. Returns a 2D context in CSS pixels.
export function setup(canvas) {
  const w = canvas.clientWidth || canvas.width;
  const dpr = window.devicePixelRatio || 1;
  if (!canvas.dataset.ratio) canvas.dataset.ratio = canvas.height / canvas.width;
  const hh = Math.round(w * Number(canvas.dataset.ratio));
  canvas.width = Math.round(w * dpr); canvas.height = Math.round(hh * dpr);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.font = "12px ui-sans-serif, system-ui, sans-serif";
  return { ctx, w, h: hh };
}

// Pressure axis: log scale, ground at the bottom.
export function pressureScale(levels, top, bottom) {
  const lp = levels.map(Math.log), lo = Math.min(...lp), hi = Math.max(...lp);
  const pad = 0.12;
  const y = (p) => top + (Math.log(p) - lo + pad) / (hi - lo + 2 * pad) * (bottom - top);
  // cell edges half-way (in log) between neighbouring levels
  const order = levels.map((p, i) => i).sort((a, b) => levels[a] - levels[b]);
  const edges = new Array(levels.length);
  order.forEach((idx, k) => {
    const up = k === 0 ? lp[idx] - pad : (lp[idx] + lp[order[k - 1]]) / 2;
    const dn = k === order.length - 1 ? lp[idx] + pad : (lp[idx] + lp[order[k + 1]]) / 2;
    edges[idx] = [y(Math.exp(up)), y(Math.exp(dn))];
  });
  return { y, edges, pmin: Math.min(...levels), pmax: Math.max(...levels) };
}

export const altKm = (p) => 7 * Math.log(1000 / p);
export const fmt = (v, d = 2) => (v == null ? "n/a" : (v > 0 ? "+" : "") + v.toFixed(d));
export const latName = (lat) => (Math.abs(lat) < 0.01 ? "the equator" : `${Math.abs(lat)}°${lat > 0 ? "N" : "S"}`);

export function pressureAxis(ctx, scale, x, side = "left") {
  ctx.fillStyle = MUTED; ctx.textBaseline = "middle";
  for (const p of [1000, 500, 200, 100, 50, 20, 10, 5, 2, 1, 0.3, 0.1]) {
    const y = scale.y(p);
    if (p < scale.pmin * 0.99 || p > scale.pmax * 1.01) continue;
    ctx.textAlign = side === "left" ? "right" : "left";
    const label = side === "left" ? `${p} hPa` : `${Math.round(altKm(p))} km`;
    ctx.fillText(label, side === "left" ? x - 6 : x + 6, y);
  }
}
