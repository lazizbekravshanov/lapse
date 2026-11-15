// Turns numbers from the pipeline into plain sentences. It never computes a trend,
// a range or a label: it only reads them and chooses words.
import { kmOf, fmt, latName, VERDICT } from "./draw.js";

export function wordsFor(variable) {
  return variable.id === "t"
    ? { subject: "the air", up: "warming", down: "cooling", upNoun: "warming", downNoun: "cooling", upPast: "warmed", downPast: "cooled" }
    : { subject: variable.label.toLowerCase(), up: "rising", down: "falling", upNoun: "rise", downNoun: "fall", upPast: "risen", downPast: "fallen" };
}

export const labelOf = (manifest, code) => manifest.verdicts.find((v) => v.code === code)?.label ?? "No data";
export const reasonOf = (manifest, code) => manifest.reasons.find((r) => r.code === code)?.text ?? "";

export function placePhrase(place, manifest) {
  if (place.region) return manifest.regions.find((r) => r.id === place.region).phrase;
  return `In the ring around the Earth at ${latName(manifest.lat_centers[place.lat])}`;
}
export function placeShort(place, manifest) {
  if (place.region) return manifest.regions.find((r) => r.id === place.region).label;
  return `Ring at ${latName(manifest.lat_centers[place.lat])}`;
}

const km = (hpa) => Math.round(kmOf(hpa));

// The short answer for a whole column of air.
export function answer({ col, levels, place, variable, manifest }) {
  const w = wordsFor(variable), where = placePhrase(place, manifest), u = variable.trend_units_plain;
  const idx = levels.map((_, i) => i).filter((i) => col.slope[i] != null && col.verdict[i] != null);
  if (!idx.length) return `${where}, there are no measurements for this.`;
  const count = (code) => idx.filter((i) => col.verdict[i] === code).length;
  const good = idx.filter((i) => col.verdict[i] === VERDICT.CLEAR || col.verdict[i] === VERDICT.LIKELY);
  const up = good.filter((i) => col.slope[i] > 0), down = good.filter((i) => col.slope[i] < 0);
  const strongest = (list) => {
    const clear = list.filter((i) => col.verdict[i] === VERDICT.CLEAR);
    return (clear.length ? clear : list).reduce((a, b) => (Math.abs(col.slope[b]) > Math.abs(col.slope[a]) ? b : a));
  };
  const one = (i, word) => `Strongest ${word}: ${fmt(col.slope[i])} ${u} near ${km(levels[i])} km ("${labelOf(manifest, col.verdict[i])}").`;
  const tally = `Of ${idx.length} heights checked: ${count(2)} "${labelOf(manifest, 2)}", ${count(1)} "${labelOf(manifest, 1)}", `
    + `${count(0)} "${labelOf(manifest, 0)}", ${count(3)} "${labelOf(manifest, 3)}".`;

  if (!good.length) {
    return `${where}, no height shows a change we can call likely or clear. "${labelOf(manifest, 0)}" does not mean nothing changed. ${tally}`;
  }
  const mean = (list) => list.reduce((a, i) => a + kmOf(levels[i]), 0) / list.length;
  let lead;
  if (up.length && down.length) {
    lead = mean(up) < mean(down)
      ? `${where}, ${w.subject} is ${w.up} low down and ${w.down} higher up.`
      : `${where}, ${w.subject} is ${w.down} low down and ${w.up} higher up.`;
  } else {
    lead = `${where}, ${w.subject} is ${up.length ? w.up : w.down}, and no height shows a likely change the other way.`;
  }
  const parts = [lead];
  if (up.length) parts.push(one(strongest(up), w.upNoun));
  if (down.length) parts.push(one(strongest(down), w.downNoun));
  if (up.length && down.length && col.flip_hpa != null) parts.push(`The direction flips at about ${km(col.flip_hpa)} km.`);
  parts.push(tally);
  return parts.join(" ");
}

// The precise reading at one height.
export function detail({ col, i, levels, variable, manifest, years }) {
  const hpa = levels[i], s = col.slope[i];
  const head = `At about ${km(hpa)} km (${hpa} hPa)`;
  if (s == null || col.verdict[i] == null) {
    return `${head}: no measurements here. ${variable.limit_note || "This height may be below the ground at this place."}`;
  }
  const u = variable.trend_units_plain, label = labelOf(manifest, col.verdict[i]), why = reasonOf(manifest, col.reason[i]);
  const range = `very likely between ${fmt(col.lo[i])} and ${fmt(col.hi[i])}`;
  if (col.verdict[i] === VERDICT.NOT_PROVEN) {
    return `${head}: ${label}. Our best estimate is ${fmt(s)} ${u}, but the true value is ${range}, so we cannot tell a real change from chance.`;
  }
  const total = `Over the ${years} years of data that adds up to about ${fmt(s * years / 10, 1)} ${variable.units_plain}.`;
  return `${head}: ${label}. ${fmt(s)} ${u}, ${range}. ${total} ${why}`;
}

// The same facts as answer(), in parts, for the headline and the three tiles.
export function brief({ col, levels, place, variable, manifest }) {
  const w = wordsFor(variable), where = placePhrase(place, manifest);
  const idx = levels.map((_, i) => i).filter((i) => col.slope[i] != null && col.verdict[i] != null);
  const good = idx.filter((i) => col.verdict[i] === VERDICT.CLEAR || col.verdict[i] === VERDICT.LIKELY);
  const up = good.filter((i) => col.slope[i] > 0), down = good.filter((i) => col.slope[i] < 0);
  const strongest = (list) => {
    const clear = list.filter((i) => col.verdict[i] === VERDICT.CLEAR);
    return (clear.length ? clear : list).reduce((a, b) => (Math.abs(col.slope[b]) > Math.abs(col.slope[a]) ? b : a));
  };
  const mean = (list) => list.reduce((a, i) => a + kmOf(levels[i]), 0) / list.length;
  const tile = (list, word) => (list.length ? { i: strongest(list), word } : null);
  let claim;
  if (!idx.length) claim = "there are no measurements for this.";
  else if (!good.length) claim = `no height shows a change we can call likely or clear.`;
  else if (up.length && down.length) claim = mean(up) < mean(down) ? `${w.subject} is ${w.up} low down and ${w.down} higher up.` : `${w.subject} is ${w.down} low down and ${w.up} higher up.`;
  else claim = `${w.subject} is ${up.length ? w.up : w.down} at every height where the change is proven.`;
  const count = (code) => idx.filter((i) => col.verdict[i] === code).length;
  return {
    where, claim, up: tile(up, w.up), down: tile(down, w.down),
    flipKm: up.length && down.length && col.flip_hpa != null ? km(col.flip_hpa) : null,
    tally: idx.length ? `${idx.length} heights checked: ${count(2)} clear, ${count(1)} likely, ${count(0)} not proven yet, ${count(3)} disputed.` : "",
  };
}
