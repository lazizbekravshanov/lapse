import { color, setup, heightScale, heightAxis, texture, hpaOf, INK, MUTED, VERDICT } from "./draw.js";

// trend: one trend file. sel: {place, level}. content: glossary (layers, landmarks).
export function drawCurtain(canvas, { trend, ds, lats, latStep, regions, sel, content }) {
  const { ctx, w, h } = setup(canvas);
  const wide = w > 640;
  const M = { l: wide ? 104 : 58, r: wide ? 196 : 10, t: 12, b: 34 };
  const levels = ds.levels_hpa;
  const scale = heightScale(levels, M.t, h - M.b);
  const x = (lat) => M.l + (lat + 90) / 180 * (w - M.l - M.r);
  const cw = (w - M.l - M.r) / lats.length;
  const box = [M.l, M.t, w - M.r, h - M.b];

  const all = trend.slope.flat().filter((v) => v != null).map(Math.abs).sort((a, b) => a - b);
  const max = all.length ? all[Math.floor(all.length * 0.98)] || 1 : 1;
  const ALPHA = { [VERDICT.NOT_PROVEN]: 0.22, [VERDICT.LIKELY]: 0.72, [VERDICT.CLEAR]: 1, [VERDICT.DISPUTED]: 1 };
  const groups = { hatch: [], dots: [], cross: [] };

  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#f4f4f5"; ctx.fillRect(box[0], box[1], box[2] - box[0], box[3] - box[1]);   // no data
  levels.forEach((p, i) => {
    const [y0, y1] = scale.edges[i];
    lats.forEach((lat, j) => {
      const v = trend.slope[i][j], verdict = trend.verdict[i][j];
      if (v == null || verdict == null) return;
      const rect = [x(lat - latStep / 2), y0, cw + 0.5, y1 - y0 + 0.5];
      ctx.fillStyle = "#ffffff"; ctx.fillRect(...rect);
      ctx.fillStyle = color(v, max, ALPHA[verdict]); ctx.fillRect(...rect);
      if (verdict === VERDICT.NOT_PROVEN) groups.hatch.push(rect);
      if (verdict === VERDICT.LIKELY) groups.dots.push(rect);
      if (verdict === VERDICT.DISPUTED) groups.cross.push(rect);
    });
  });
  for (const kind of Object.keys(groups)) texture(ctx, groups[kind], kind, box);

  // Flip line: where a rise below turns into a fall above.
  ctx.strokeStyle = INK; ctx.lineWidth = 1.6; ctx.setLineDash([5, 4]); ctx.beginPath();
  let pen = false;
  lats.forEach((lat, j) => {
    const f = trend.flip_hpa[j];
    if (f == null) { pen = false; return; }
    pen ? ctx.lineTo(x(lat), scale.y(f)) : ctx.moveTo(x(lat), scale.y(f)); pen = true;
  });
  ctx.stroke(); ctx.setLineDash([]);

  // Selection: one ring around the Earth, or a whole region.
  ctx.strokeStyle = INK; ctx.lineWidth = 2;
  if (sel.place.lat != null) {
    ctx.strokeRect(x(lats[sel.place.lat] - latStep / 2), M.t, cw, h - M.b - M.t);
  } else {
    const r = regions.find((q) => q.id === sel.place.region);
    if (r) ctx.strokeRect(x(r.lat[0]) + 1, M.t + 1, x(r.lat[1]) - x(r.lat[0]) - 2, h - M.b - M.t - 2);
  }
  if (sel.level != null) {
    const yy = scale.y(levels[sel.level]);
    ctx.fillStyle = INK; ctx.beginPath();
    ctx.moveTo(M.l - 1, yy); ctx.lineTo(M.l - 8, yy - 5); ctx.lineTo(M.l - 8, yy + 5); ctx.fill();
  }

  // Axes.
  heightAxis(ctx, scale, M.l - 6, wide);
  ctx.fillStyle = MUTED; ctx.textAlign = "center"; ctx.textBaseline = "top";
  for (const lat of wide ? [-90, -45, 0, 45, 90] : [-90, 0, 90]) {
    const label = lat === 0 ? "Equator" : Math.abs(lat) === 90 ? (lat < 0 ? "South Pole" : "North Pole") : `${Math.abs(lat)}°${lat < 0 ? "S" : "N"}`;
    ctx.textAlign = lat === -90 ? "left" : lat === 90 ? "right" : "center";
    ctx.fillText(label, x(lat), h - M.b + 8);
  }

  // Right margin: named layers and everyday landmarks.
  if (wide && content) {
    const x0 = w - M.r + 8;
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    for (const layer of content.layers) {
      const ya = Math.max(M.t, kmToY(scale, layer.to_km)), yb = Math.min(h - M.b, kmToY(scale, layer.from_km));
      if (yb - ya < 30) continue;
      ctx.strokeStyle = MUTED; ctx.lineWidth = 1; ctx.beginPath();
      ctx.moveTo(x0 + 5, ya + 2); ctx.lineTo(x0, ya + 2); ctx.lineTo(x0, yb - 2); ctx.lineTo(x0 + 5, yb - 2); ctx.stroke();
      ctx.save(); ctx.translate(x0 + 14, (ya + yb) / 2); ctx.rotate(-Math.PI / 2);
      ctx.fillStyle = INK; ctx.font = "11px ui-sans-serif, system-ui, sans-serif";
      const text = `${layer.plain} (${layer.science})`;
      ctx.fillText(ctx.measureText(text).width < yb - ya - 8 ? text : layer.plain, 0, 0);
      ctx.restore();
    }
    ctx.textAlign = "left"; ctx.font = "11px ui-sans-serif, system-ui, sans-serif";
    for (const mark of content.landmarks) {
      const yy = kmToY(scale, mark.km);
      if (yy < M.t + 6 || yy > h - M.b - 4) continue;
      ctx.strokeStyle = MUTED; ctx.beginPath(); ctx.moveTo(x0 + 24, yy); ctx.lineTo(x0 + 30, yy); ctx.stroke();
      ctx.fillStyle = MUTED; ctx.fillText(`${mark.label}, ${Math.round(mark.km)} km`, x0 + 33, yy);
    }
  }

  canvas._hit = (px, py) => {
    const j = Math.floor((px - M.l) / cw);
    if (j < 0 || j >= lats.length || py < M.t || py > h - M.b) return null;
    const i = levels.findIndex((_, k) => py >= scale.edges[k][0] && py <= scale.edges[k][1]);
    return i < 0 ? null : { lat: j, level: i };
  };
  return max;
}

const kmToY = (scale, km) => scale.y(Math.max(scale.pmin * 0.9, Math.min(scale.pmax, hpaOf(km))));
