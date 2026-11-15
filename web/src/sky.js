// The hero picture: one column of air, ground at the bottom, the top of the record at the top.
// Colour is the direction and speed of change at each height. It reads numbers the
// pipeline computed and draws them; it computes nothing itself.
import { color, kmOf, fmt, VERDICT } from "./draw.js";

const W = 344, H = 520, X0 = 172, X1 = 248, TOP = 22, BOTTOM = 498;
// Small line drawings for the heights people already know. 24 x 24, drawn for this project.
const ICONS = {
  home: '<path d="M4 11.5 12 4l8 7.5"/><path d="M6.5 10v9.5h11V10"/><path d="M10.5 19.5v-5h3v5"/>',
  mountain: '<path d="M2 20 9.5 6.5l3.2 5.4 2-3L22 20z"/><path d="m7.6 10 1.9 1.5 1.4-2"/>',
  plane: '<path class="solid" d="M21.5 12c0 .8-.9 1.4-2 1.4h-5.2L9.7 21h-2l2.4-7.6H5.7L4 15.6H2.5L3.5 12l-1-3.6H4l1.7 2.2h4.4L7.7 3h2l4.6 7.6h5.2c1.1 0 2 .6 2 1.4z"/>',
  shield: '<path d="M12 3 19 6v5c0 4.4-2.9 8.2-7 10-4.1-1.8-7-5.6-7-10V6z"/><path d="m9 11.8 2.2 2.200L15.2 10"/>',
  balloon: '<path d="M12 3a6 6 0 0 1 6 6c0 3.3-2.7 6.3-6 7.800C8.7 15.3 6 12.3 6 9a6 6 0 0 1 6-6z"/><path d="M12 16.800V21"/><path d="M10.8 18.200h2.4"/>',
  parachute: '<path d="M3 11a9 9 0 0 1 18 0c-1.5-1.2-3-1.2-4.5 0-1.5-1.2-3-1.2-4.5 0-1.5-1.2-3-1.2-4.5 0-1.5-1.2-3-1.2-4.5 0z"/><path d="m3 11 9 9.500L21 11"/><path d="M12 11v9.5"/>',
  dot: '<circle cx="12" cy="12" r="3"/>',
};
export const iconFor = (label) => { const l = label.toLowerCase(); return /everest|mount/.test(l) ? "mountain" : /airliner|plane|jet/.test(l) ? "plane"
  : /ozone/.test(l) ? "shield" : /balloon/.test(l) ? "balloon" : /skydive|parachut/.test(l) ? "parachute" : /live|ground|home/.test(l) ? "home" : "dot"; };
export const iconSvg = (name) => `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] ?? ICONS.dot}</svg>`;

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
  for (const m of [{ km: 0, label: "Where we live" }, ...content.landmarks]) {
    if (m.km > topKm) continue;
    const yy = y(m.km) - (m.km === 0 ? 4 : 0);                                   // keep the ground marker above the column's edge
    const crowded = col.flip_hpa != null && Math.abs(yy - y(kmOf(col.flip_hpa))) < 14;      // leave room for "direction flips"
    marks += `<g class="lm" data-km="${m.km}"><g class="ico" transform="translate(${X0 - 46} ${(yy - 9).toFixed(1)}) scale(.75)">${ICONS[iconFor(m.label)]}</g>`
      + (compact || crowded ? "" : `<text x="${X0 - 53}" y="${(yy + 4).toFixed(1)}" text-anchor="end">${esc(m.label)}</text>`) + "</g>";
  }
  let flip = "";
  if (col.flip_hpa != null) {
    const fy = y(kmOf(col.flip_hpa));
    flip = `<line x1="${X0 - 8}" x2="${X1 + 8}" y1="${fy}" y2="${fy}" stroke="#0a0a0a" stroke-dasharray="4 3"/>`
      + (compact ? "" : `<text class="strong" x="${X0 - 28}" y="${fy - 6}" text-anchor="end">direction flips</text>`);
  }
  el.innerHTML = `<svg viewBox="${compact ? `${X0 - 50} 0 ${X1 - X0 + 118}` : `0 0 ${W}`} ${H}" role="img" aria-label="Change at every height from the ground to ${topKm} km">
    <defs><clipPath id="skyClip"><rect x="${X0}" y="${TOP}" width="${X1 - X0}" height="${BOTTOM - TOP}" rx="12"/></clipPath>
    <pattern id="skyHatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" stroke="#0a0a0a" stroke-width="1.2"/></pattern></defs>
    <g clip-path="url(#skyClip)">${bands}${hatch}</g>
    <rect x="${X0}" y="${TOP}" width="${X1 - X0}" height="${BOTTOM - TOP}" rx="12" fill="none" stroke="#e4e4e7"/>
    ${ticks}${marks}${flip}${sel}
    <g id="skyMark" transform="translate(0 ${BOTTOM})" pointer-events="none"><line x1="${X0 - 14}" x2="${X1 + 6}" y1="0" y2="0" stroke="#1d1d1f" stroke-width="2.5"/><circle cx="${X0 - 14}" cy="0" r="6" fill="#1d1d1f"/></g></svg>`;
  const kmAt = (yy) => Math.max(0, Math.min(topKm, ((BOTTOM - yy) / (BOTTOM - TOP)) * topKm));    // inverse of y()
  return { y, kmAt, viewHeight: H, topKm, max, maxKm: Math.max(...km) };
}
