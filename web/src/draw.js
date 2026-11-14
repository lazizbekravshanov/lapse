// Shared drawing helpers.
export const INK = "#1f2a44", MUTED = "#6b6a66", LINE = "#d9cfbb", ACCENT = "#e2703a", PAPER = "#fbf7ee";
const COOL = [44, 90, 140], MID = [243, 234, 216], WARM = [200, 73, 43];
export const VERDICT = { NOT_PROVEN: 0, LIKELY: 1, CLEAR: 2, DISPUTED: 3 };

export function color(v, max, alpha = 1) {
  if (v == null) return "rgba(0,0,0,0)";
  const x = Math.max(-1, Math.min(1, v / max));
  const to = x < 0 ? COOL : WARM, k = Math.abs(x) ** 0.7;
  const c = MID.map((m, i) => Math.round(m + (to[i] - m) * k));
  return `rgba(${c[0]},${c[1]},${c[2]},${alpha})`;
}

// Sharp canvas on high-density screens. Returns a 2D context in CSS pixels.
export function setup(canvas) {
  if (!canvas.dataset.ratio) canvas.dataset.ratio = canvas.height / canvas.width;
  const w = canvas.clientWidth || canvas.width;
  const h = Math.round(w * Number(canvas.dataset.ratio));
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.font = "12px ui-sans-serif, system-ui, sans-serif";
  return { ctx, w, h };
}

export const kmOf = (hpa) => 7 * Math.log(1000 / hpa);       // approximate, for labels
export const hpaOf = (km) => 1000 * Math.exp(-km / 7);
export const minus = (s) => String(s).replace("-", "−");
export const fmt = (v, d = 2) => (v == null ? "n/a" : minus((v > 0 ? "+" : "") + v.toFixed(d)));
export const latName = (lat) => (Math.abs(lat) < 0.01 ? "the equator" : `${Math.abs(lat)}°${lat > 0 ? "N" : "S"}`);

// Height axis: log pressure, ground at the bottom.
export function heightScale(levels, top, bottom) {
  const lp = levels.map(Math.log), lo = Math.min(...lp), hi = Math.max(...lp), pad = 0.12;
  const y = (p) => top + (Math.log(p) - lo + pad) / (hi - lo + 2 * pad) * (bottom - top);
  const order = levels.map((_, i) => i).sort((a, b) => levels[a] - levels[b]);   // top of the air first
  const edges = new Array(levels.length);
  order.forEach((idx, k) => {
    const up = k === 0 ? lp[idx] - pad : (lp[idx] + lp[order[k - 1]]) / 2;
    const dn = k === order.length - 1 ? lp[idx] + pad : (lp[idx] + lp[order[k + 1]]) / 2;
    edges[idx] = [y(Math.exp(up)), y(Math.exp(dn))];
  });
  return { y, edges, pmin: Math.min(...levels), pmax: Math.max(...levels), order };
}

// Kilometres first, the pressure beside it in small grey text.
export function heightAxis(ctx, scale, x, withHpa = true) {
  ctx.textBaseline = "middle"; ctx.textAlign = "right";
  let last = -99;
  for (const p of [1000, 500, 200, 100, 50, 20, 10, 5, 2, 1, 0.3, 0.1]) {
    if (p < scale.pmin * 0.99 || p > scale.pmax * 1.01) continue;
    const y = scale.y(p);
    if (Math.abs(y - last) < 15) continue;
    last = y;
    ctx.font = "12px ui-sans-serif, system-ui, sans-serif"; ctx.fillStyle = INK;
    ctx.fillText(`${Math.round(kmOf(p))} km`, x - (withHpa ? 52 : 8), y);
    if (withHpa) {
      ctx.font = "10px ui-sans-serif, system-ui, sans-serif"; ctx.fillStyle = MUTED;
      ctx.fillText(`${p} hPa`, x - 8, y);
    }
  }
  ctx.font = "12px ui-sans-serif, system-ui, sans-serif";
}

// One texture drawn across many cells at once, so it reads as a continuous pattern.
export function texture(ctx, rects, kind, box) {
  if (!rects.length) return;
  ctx.save(); ctx.beginPath();
  for (const [x, y, w, h] of rects) ctx.rect(x, y, w, h);
  ctx.clip();
  const [x0, y0, x1, y1] = box, span = y1 - y0;
  ctx.beginPath();
  if (kind === "hatch" || kind === "cross") {
    for (let k = x0 - span; k < x1; k += 6) { ctx.moveTo(k, y1); ctx.lineTo(k + span, y0); }
  }
  if (kind === "cross") {
    for (let k = x0; k < x1 + span; k += 6) { ctx.moveTo(k, y1); ctx.lineTo(k - span, y0); }
  }
  if (kind === "dots") {
    ctx.fillStyle = "rgba(251,247,238,.85)";
    for (let yy = y0 + 2; yy < y1; yy += 5) for (let xx = x0 + ((yy - y0) % 10 < 5 ? 2 : 4.5); xx < x1; xx += 5) ctx.rect(xx, yy, 1.4, 1.4);
    ctx.fill();
  } else {
    ctx.strokeStyle = kind === "cross" ? "rgba(31,42,68,.75)" : "rgba(31,42,68,.3)";
    ctx.lineWidth = kind === "cross" ? 1 : 0.7; ctx.stroke();
  }
  ctx.restore();
}
