// The hero picture: one column of air, ground at the bottom, edge of space at the top.
// Colour is the direction and speed of change at each height. It reads numbers the
// pipeline computed and draws them; it computes nothing itself.
import { color, kmOf, fmt, VERDICT } from "./draw.js";

const W = 320, H = 520, X0 = 150, X1 = 226, TOP = 22, BOTTOM = 498;
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

export function drawSky(el, { col, levels, units, selLevel, content, labelOf, compact }) {
  const km = levels.map(kmOf);
  const order = km.map((_, i) => i).sort((a, b) => km[a] - km[b]);                 // ground first
  const topKm = Math.ceil(Math.max(...km) / 10) * 10;
  const y = (k) => BOTTOM - (Math.min(k, topKm) / topKm) * (BOTTOM - TOP);
  const max = Math.max(0.1, ...col.slope.filter((s) => s != null).map(Math.abs));
  const edge = (n) => (n === 0 ? 0 : n === order.length ? Math.min(topKm, km[order[n - 1]] + (km[order[n - 1]] - km[order[n - 2]]) / 2)
    : (km[order[n - 1]] + km[order[n]]) / 2);

  let bands = "", hatch = "", sel = "";
  order.forEach((i, n) => {
    const y1 = y(edge(n)), y0 = y(edge(n + 1)), s = col.slope[i], v = col.verdict[i];
    const none = s == null || v == null;
    const alpha = none ? 1 : v === VERDICT.NOT_PROVEN ? 0.3 : v === VERDICT.LIKELY ? 0.75 : 1;
    const tip = `About ${Math.round(km[i])} km up: ` + (none ? "no measurements" : `${fmt(s)} ${units}, ${labelOf(v)}`);
    bands += `<rect data-level="${i}" x="${X0}" y="${y0.toFixed(1)}" width="${X1 - X0}" height="${Math.max(1, y1 - y0 + 0.6).toFixed(1)}" fill="${none ? "#f4f4f5" : color(s, max, alpha)}"><title>${esc(tip)}</title></rect>`;
    if (!none && v === VERDICT.DISPUTED) hatch += `<rect x="${X0}" y="${y0.toFixed(1)}" width="${X1 - X0}" height="${(y1 - y0).toFixed(1)}" fill="url(#skyHatch)" pointer-events="none"/>`;
    if (i === selLevel) {
      const mid = (y0 + y1) / 2;
      sel = `<rect x="${X0 - 3}" y="${(y0 - 1).toFixed(1)}" width="${X1 - X0 + 6}" height="${(y1 - y0 + 2).toFixed(1)}" fill="none" stroke="#0a0a0a" stroke-width="2" rx="3" pointer-events="none"/>`
        + `<text class="strong" x="${X1 + 12}" y="${(mid + 4).toFixed(1)}">${Math.round(km[i])} km${s == null ? "" : "  " + esc(fmt(s))}</text>`;
    }
  });

  let ticks = "";
  for (let k = 0; k <= topKm; k += 10) {
    ticks += `<line x1="${X1}" x2="${X1 + 5}" y1="${y(k)}" y2="${y(k)}" stroke="#d4d4d8"/>`
      + (Math.abs(y(k) - (selLevel == null ? -99 : y(km[selLevel]))) < 12 ? "" : `<text x="${X1 + 12}" y="${y(k) + 4}">${k === 0 ? "ground" : k + " km"}</text>`);
  }
  let marks = "";
  for (const m of content.landmarks) {
    if (m.km > topKm) continue;
    if (compact) break;
    marks += `<line x1="${X0 - 8}" x2="${X0}" y1="${y(m.km)}" y2="${y(m.km)}" stroke="#a1a1aa"/><text x="${X0 - 12}" y="${y(m.km) + 4}" text-anchor="end">${esc(m.label)}</text>`;
  }
  let flip = "";
  if (col.flip_hpa != null) {
    const fy = y(kmOf(col.flip_hpa));
    flip = `<line x1="${X0 - 8}" x2="${X1 + 8}" y1="${fy}" y2="${fy}" stroke="#0a0a0a" stroke-dasharray="4 3"/>`
      + (compact ? "" : `<text class="strong" x="${X0 - 12}" y="${fy - 6}" text-anchor="end">direction flips</text>`);
  }
  el.innerHTML = `<svg viewBox="${compact ? `${X0 - 16} 0 ${X1 - X0 + 84}` : `0 0 ${W}`} ${H}" role="img" aria-label="Change at every height from the ground to ${topKm} km">
    <defs><clipPath id="skyClip"><rect x="${X0}" y="${TOP}" width="${X1 - X0}" height="${BOTTOM - TOP}" rx="12"/></clipPath>
    <pattern id="skyHatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" stroke="#0a0a0a" stroke-width="1.2"/></pattern></defs>
    <g clip-path="url(#skyClip)">${bands}${hatch}</g>
    <rect x="${X0}" y="${TOP}" width="${X1 - X0}" height="${BOTTOM - TOP}" rx="12" fill="none" stroke="#e4e4e7"/>
    ${ticks}${marks}${flip}${sel}
    <g id="skyMark" transform="translate(0 ${BOTTOM})" pointer-events="none"><line x1="${X0 - 14}" x2="${X1 + 6}" y1="0" y2="0" stroke="#1d1d1f" stroke-width="2.5"/><circle cx="${X0 - 14}" cy="0" r="6" fill="#1d1d1f"/></g></svg>`;
  return { y, topKm, max, maxKm: Math.max(...km) };
}
