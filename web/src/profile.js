import { setup, heightScale, heightAxis, minus, INK, MUTED, LINE, ACCENT, PAPER, VERDICT } from "./draw.js";

// col: {slope, lo, hi, verdict} per level. other: the second dataset's column (optional).
export function drawProfile(canvas, { col, levels, other, otherLevels, units, selLevel }) {
  const { ctx, w, h } = setup(canvas);
  const M = { l: 58, r: 14, t: 12, b: 34 };
  const scale = heightScale(levels, M.t, h - M.b);
  const vals = [...col.lo, ...col.hi, ...(other ? other.slope : [])].filter((v) => v != null).map(Math.abs);
  const max = (vals.length ? Math.max(...vals) : 1) * 1.08 || 1;
  const x = (v) => M.l + (v + max) / (2 * max) * (w - M.l - M.r);
  const order = levels.map((_, i) => i).sort((a, b) => levels[b] - levels[a]);   // ground first
  const ok = order.filter((i) => col.slope[i] != null);

  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = LINE; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(x(0), M.t); ctx.lineTo(x(0), h - M.b); ctx.stroke();

  ctx.fillStyle = "rgba(10,10,10,.09)"; ctx.beginPath();                        // the range
  ok.forEach((i, k) => { const yy = scale.y(levels[i]); k ? ctx.lineTo(x(col.lo[i]), yy) : ctx.moveTo(x(col.lo[i]), yy); });
  [...ok].reverse().forEach((i) => ctx.lineTo(x(col.hi[i]), scale.y(levels[i])));
  ctx.fill();

  if (other) {                                                                  // second dataset, dashed
    const oo = otherLevels.map((_, i) => i).sort((a, b) => otherLevels[b] - otherLevels[a])
      .filter((i) => other.slope[i] != null && otherLevels[i] >= scale.pmin && otherLevels[i] <= scale.pmax);
    ctx.strokeStyle = ACCENT; ctx.lineWidth = 2; ctx.setLineDash([6, 4]); ctx.beginPath();
    oo.forEach((i, k) => { const px = x(Math.max(-max, Math.min(max, other.slope[i]))), py = scale.y(otherLevels[i]); k ? ctx.lineTo(px, py) : ctx.moveTo(px, py); });
    ctx.stroke(); ctx.setLineDash([]);
  }

  ctx.strokeStyle = INK; ctx.lineWidth = 2; ctx.beginPath();
  ok.forEach((i, k) => { const px = x(col.slope[i]), py = scale.y(levels[i]); k ? ctx.lineTo(px, py) : ctx.moveTo(px, py); });
  ctx.stroke();

  // One marker shape per label, so it reads without colour.
  ok.forEach((i) => {
    const px = x(col.slope[i]), py = scale.y(levels[i]), v = col.verdict[i], r = i === selLevel ? 6 : 3.6;
    ctx.beginPath(); ctx.arc(px, py, r, 0, 6.3);
    ctx.fillStyle = v === VERDICT.CLEAR ? INK : v === VERDICT.LIKELY ? "#9ca3af" : PAPER; ctx.fill();
    ctx.strokeStyle = i === selLevel ? ACCENT : INK; ctx.lineWidth = i === selLevel ? 2.5 : 1; ctx.stroke();
    if (v === VERDICT.DISPUTED) {
      ctx.strokeStyle = INK; ctx.lineWidth = 1.4; ctx.beginPath();
      ctx.moveTo(px - r, py - r); ctx.lineTo(px + r, py + r); ctx.moveTo(px + r, py - r); ctx.lineTo(px - r, py + r); ctx.stroke();
    }
  });

  heightAxis(ctx, scale, M.l - 6, false);
  ctx.fillStyle = MUTED; ctx.textAlign = "center"; ctx.textBaseline = "top";
  for (const v of [-max / 1.08, 0, max / 1.08]) ctx.fillText(minus((v > 0 ? "+" : "") + v.toFixed(2)), x(v), h - M.b + 4);
  ctx.fillText(units, (M.l + w - M.r) / 2, h - 14);

  canvas._hit = (px, py) => {
    let best = null, d = 1e9;
    ok.forEach((i) => { const dd = Math.abs(scale.y(levels[i]) - py); if (dd < d) { d = dd; best = i; } });
    return best == null ? null : { level: best };
  };
}
