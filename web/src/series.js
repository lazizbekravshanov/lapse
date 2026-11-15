import { setup, minus, INK, MUTED, LINE, ACCENT } from "./draw.js";
import { monthKey } from "./data.js";

const TINT = { volcano: "rgba(220,38,38,.12)", data_change: "rgba(37,99,235,.14)" };

// y: one value per month. axis: [{y, m, t}]. keep(t): does this month count for the trend?
export function drawSeries(canvas, { y, axis, slope, events, masked, keep, units }) {
  const { ctx, w, h } = setup(canvas);
  const M = { l: 62, r: 16, t: 40, b: 28 };
  const pts = y.map((v, i) => ({ v, t: axis[i].t })).filter((d) => d.v != null);
  ctx.clearRect(0, 0, w, h);
  if (!pts.length) {
    ctx.fillStyle = MUTED; ctx.textAlign = "center"; ctx.fillText("No measurements at this height here.", w / 2, h / 2);
    return;
  }
  const t0 = axis[0].t, t1 = axis[axis.length - 1].t;
  const sorted = pts.map((d) => d.v).sort((a, b) => a - b);
  const span = Math.max(Math.abs(sorted[Math.floor(sorted.length * 0.005)]), Math.abs(sorted[Math.ceil(sorted.length * 0.995) - 1])) * 1.15 || 1;
  const x = (t) => M.l + (t - t0) / (t1 - t0) * (w - M.l - M.r);
  const yy = (v) => M.t + (span - v) / (2 * span) * (h - M.t - M.b);

  let row = 0;
  for (const e of events) {
    const a = Math.max(monthKey(e.start), t0), b = Math.min(monthKey(e.end) + 1, t1);
    if (b <= a) continue;
    ctx.fillStyle = TINT[e.kind] || "rgba(0,0,0,.08)";
    ctx.fillRect(x(a), M.t, Math.max(3, x(b) - x(a)), h - M.t - M.b);
    const text = e.label + (masked.includes(e.id) ? " (left out)" : "");
    const right = x(a) + ctx.measureText(text).width > w - M.r;
    ctx.fillStyle = MUTED; ctx.textAlign = right ? "right" : "left"; ctx.textBaseline = "bottom";
    ctx.fillText(text, right ? Math.min(w - M.r, x(b)) : x(a) + 2, M.t - 4 - (row++ % 2) * 15);
  }

  ctx.strokeStyle = LINE; ctx.beginPath(); ctx.moveTo(M.l, yy(0)); ctx.lineTo(w - M.r, yy(0)); ctx.stroke();
  for (const d of pts) {
    ctx.fillStyle = keep(d.t) ? "rgba(10,10,10,.3)" : "rgba(10,10,10,.1)";
    ctx.fillRect(x(d.t) - 1, yy(Math.max(-span, Math.min(span, d.v))) - 1, 2.2, 2.2);
  }

  ctx.strokeStyle = INK; ctx.lineWidth = 1.8; ctx.beginPath();                  // 12-month average
  let pen = false;
  for (let i = 11; i < y.length; i++) {
    const win = y.slice(i - 11, i + 1);
    if (win.some((v) => v == null)) { pen = false; continue; }
    const px = x(axis[i].t - 5.5), py = yy(win.reduce((a, b) => a + b, 0) / 12);
    pen ? ctx.lineTo(px, py) : ctx.moveTo(px, py); pen = true;
  }
  ctx.stroke();

  // The published trend, drawn through the middle of the months that count.
  if (slope != null) {
    const used = pts.filter((d) => keep(d.t));
    if (used.length) {
      const perMonth = slope / 120;
      const res = used.map((d) => d.v - perMonth * d.t).sort((a, b) => a - b);
      const c = res[Math.floor(res.length / 2)], a = used[0].t, b = used[used.length - 1].t;
      ctx.strokeStyle = ACCENT; ctx.lineWidth = 2.5; ctx.beginPath();
      ctx.moveTo(x(a), yy(c + perMonth * a)); ctx.lineTo(x(b), yy(c + perMonth * b)); ctx.stroke();
    }
  }

  ctx.fillStyle = MUTED; ctx.textBaseline = "middle"; ctx.textAlign = "right";
  for (const v of [-span / 1.15, 0, span / 1.15]) ctx.fillText(minus((v > 0 ? "+" : "") + v.toFixed(1)) + " " + units, M.l - 6, yy(v));
  ctx.textAlign = "center"; ctx.textBaseline = "top";
  const step = w < 520 ? 10 : 5;
  for (let yr = Math.ceil(t0 / 12 / step) * step; yr * 12 <= t1; yr += step) ctx.fillText(String(yr), x(yr * 12), h - M.b + 6);
}
