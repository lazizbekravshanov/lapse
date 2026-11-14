import { setup, pressureScale, pressureAxis, INK, MUTED, LINE } from "./draw.js";

const M = { l: 70, r: 46, t: 10, b: 34 };

// p: {slope, lo, hi, sig} arrays by level. other: same for the second dataset (optional).
export function drawProfile(canvas, { p, levels, other, otherLevels, units, selLevel }) {
  const { ctx, w, h } = setup(canvas);
  const scale = pressureScale(levels, M.t, h - M.b);
  const vals = [...p.lo, ...p.hi, ...(other ? other.slope : [])].filter((v) => v != null).map(Math.abs);
  const max = (vals.length ? Math.max(...vals) : 1) * 1.1 || 1;
  const x = (v) => M.l + (v + max) / (2 * max) * (w - M.l - M.r);
  const order = levels.map((_, i) => i).sort((a, b) => levels[b] - levels[a]);   // ground first

  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = LINE; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(x(0), M.t); ctx.lineTo(x(0), h - M.b); ctx.stroke();

  // uncertainty band
  const ok = order.filter((i) => p.slope[i] != null);
  ctx.fillStyle = "rgba(31,42,68,.13)"; ctx.beginPath();
  ok.forEach((i, k) => { const yy = scale.y(levels[i]); k ? ctx.lineTo(x(p.lo[i]), yy) : ctx.moveTo(x(p.lo[i]), yy); });
  [...ok].reverse().forEach((i) => ctx.lineTo(x(p.hi[i]), scale.y(levels[i])));
  ctx.fill();

  if (other) {
    const oo = otherLevels.map((_, i) => i).sort((a, b) => otherLevels[b] - otherLevels[a])
      .filter((i) => other.slope[i] != null);
    ctx.strokeStyle = "#e2703a"; ctx.lineWidth = 2; ctx.setLineDash([6, 4]); ctx.beginPath();
    oo.forEach((i, k) => { const px = x(other.slope[i]), py = scale.y(otherLevels[i]); k ? ctx.lineTo(px, py) : ctx.moveTo(px, py); });
    ctx.stroke(); ctx.setLineDash([]);
  }

  ctx.strokeStyle = INK; ctx.lineWidth = 2; ctx.beginPath();
  ok.forEach((i, k) => { const px = x(p.slope[i]), py = scale.y(levels[i]); k ? ctx.lineTo(px, py) : ctx.moveTo(px, py); });
  ctx.stroke();
  ok.forEach((i) => {
    const px = x(p.slope[i]), py = scale.y(levels[i]);
    ctx.beginPath(); ctx.arc(px, py, i === selLevel ? 5.5 : 3, 0, 6.3);
    ctx.fillStyle = p.sig[i] === 1 ? INK : "#fbf7ee"; ctx.fill();
    ctx.strokeStyle = i === selLevel ? "#e2703a" : INK; ctx.lineWidth = i === selLevel ? 2.5 : 1; ctx.stroke();
  });

  pressureAxis(ctx, scale, M.l - 10, "left");
  pressureAxis(ctx, scale, w - M.r, "right");
  ctx.fillStyle = MUTED; ctx.textAlign = "center"; ctx.textBaseline = "top";
  for (const v of [-max / 1.1, 0, max / 1.1]) ctx.fillText((v > 0 ? "+" : "") + v.toFixed(2), x(v), h - M.b + 4);
  ctx.fillText(units, (M.l + w - M.r) / 2, h - 14);

  canvas._hit = (px, py) => {
    let best = null, d = 1e9;
    levels.forEach((lv, i) => { const dd = Math.abs(scale.y(lv) - py); if (dd < d) { d = dd; best = i; } });
    return best == null ? null : { level: best };
  };
}
