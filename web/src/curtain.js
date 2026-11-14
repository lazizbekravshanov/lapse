import { color, setup, pressureScale, pressureAxis, INK, MUTED } from "./draw.js";

const M = { l: 70, r: 52, t: 10, b: 34 };

export function drawCurtain(canvas, { trend, ds, lats, latStep, sel, agree }) {
  const { ctx, w, h } = setup(canvas);
  const levels = ds.levels_hpa;
  const scale = pressureScale(levels, M.t, h - M.b);
  const x = (lat) => M.l + (lat + 90) / 180 * (w - M.l - M.r);
  const cw = (w - M.l - M.r) / lats.length;

  const all = trend.slope.flat().filter((v) => v != null).map(Math.abs).sort((a, b) => a - b);
  const max = all.length ? all[Math.floor(all.length * 0.98)] || 1 : 1;

  ctx.clearRect(0, 0, w, h);
  levels.forEach((p, i) => {
    const [y0, y1] = scale.edges[i];
    lats.forEach((lat, j) => {
      const v = trend.slope[i][j];
      if (v == null) return;
      const sig = trend.sig[i][j] === 1;
      const x0 = x(lat - latStep / 2);
      ctx.fillStyle = color(v, max, sig ? 1 : 0.28);
      ctx.fillRect(x0, y0, cw + 0.5, y1 - y0 + 0.5);
      if (!sig) {                                   // hatch = not proven
        ctx.save(); ctx.beginPath(); ctx.rect(x0, y0, cw, y1 - y0); ctx.clip();
        ctx.strokeStyle = "rgba(31,42,68,.28)"; ctx.lineWidth = 0.7; ctx.beginPath();
        for (let k = -40; k < cw + 40; k += 6) { ctx.moveTo(x0 + k, y1); ctx.lineTo(x0 + k + (y1 - y0), y0); }
        ctx.stroke(); ctx.restore();
      }
    });
  });

  // Where the two datasets disagree: a small ring.
  if (agree) {
    agree.levels_hpa.forEach((p, a) => {
      const i = levels.indexOf(p);
      if (i < 0) return;
      const [y0, y1] = scale.edges[i];
      lats.forEach((lat, j) => {
        const st = agree.status[a][j];
        if (st !== 3 && !(st === 2 && agree.ci_overlap[a][j] === 0)) return;
        ctx.strokeStyle = st === 3 ? "#000" : "rgba(0,0,0,.55)"; ctx.lineWidth = st === 3 ? 1.6 : 1;
        ctx.beginPath(); ctx.arc(x(lat), (y0 + y1) / 2, Math.min(cw, y1 - y0) / 2.6, 0, 6.3); ctx.stroke();
      });
    });
  }

  // Flip line: where warming below turns into cooling above.
  ctx.strokeStyle = INK; ctx.lineWidth = 1.6; ctx.setLineDash([5, 4]); ctx.beginPath();
  let pen = false;
  lats.forEach((lat, j) => {
    const f = trend.flip_hpa[j];
    if (f == null) { pen = false; return; }
    const px = x(lat), py = scale.y(f);
    pen ? ctx.lineTo(px, py) : ctx.moveTo(px, py); pen = true;
  });
  ctx.stroke(); ctx.setLineDash([]);

  // Selection.
  if (sel.lat != null) {
    ctx.strokeStyle = INK; ctx.lineWidth = 2;
    ctx.strokeRect(x(lats[sel.lat] - latStep / 2), M.t, cw, h - M.b - M.t);
  }
  if (sel.level != null) {
    const yy = scale.y(levels[sel.level]);
    ctx.fillStyle = INK; ctx.beginPath();
    ctx.moveTo(M.l - 1, yy); ctx.lineTo(M.l - 9, yy - 5); ctx.lineTo(M.l - 9, yy + 5); ctx.fill();
  }

  // Axes.
  pressureAxis(ctx, scale, M.l - 10, "left");
  pressureAxis(ctx, scale, w - M.r, "right");
  ctx.fillStyle = MUTED; ctx.textAlign = "center"; ctx.textBaseline = "top";
  for (const lat of [-90, -60, -30, 0, 30, 60, 90]) {
    ctx.fillText(lat === 0 ? "Equator" : `${Math.abs(lat)}°${lat < 0 ? "S" : "N"}`, x(lat), h - M.b + 8);
  }

  canvas._hit = (px, py) => {
    const j = Math.floor((px - M.l) / cw);
    if (j < 0 || j >= lats.length || py < M.t || py > h - M.b) return null;
    let i = levels.findIndex((_, k) => py >= scale.edges[k][0] && py <= scale.edges[k][1]);
    return i < 0 ? null : { lat: j, level: i };
  };
  return max;
}
