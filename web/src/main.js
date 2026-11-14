import { loadManifest, loadTrend, loadSeries, loadAgreement, monthAxis, monthKey } from "./data.js";
import { drawCurtain } from "./curtain.js";
import { drawProfile } from "./profile.js";
import { drawSeries } from "./series.js";
import { altKm, fmt, latName } from "./draw.js";

const $ = (id) => document.getElementById(id);
const state = { dataset: null, variable: "t", period: "airs_era", mask: "none", lat: null, level: null, witness: false };
let manifest;

const CASES = {
  fingerprint: { dataset: "merra2", variable: "t", period: "airs_era", mask: "none", lat: null, hpa: 1, witness: true },
  hunga: { dataset: "merra2", variable: "t", period: "airs_era", mask: "none", latDeg: -17.5, hpa: 20, witness: false },
  witness: { dataset: "merra2", variable: "t", period: "full", mask: "none", lat: null, hpa: 3, witness: false },
};

const ds = () => manifest.datasets.find((d) => d.id === state.dataset);
const variable = () => ds().variables.find((v) => v.id === state.variable) || ds().variables[0];
const otherDs = () => manifest.datasets.find((d) => d.id !== state.dataset && d.variables.some((v) => v.id === state.variable));

function fill(select, items, value) {
  select.innerHTML = items.map((i) => `<option value="${i.id}">${i.label}</option>`).join("");
  select.value = value;
}

function nearestLevel(hpa) {
  const lv = ds().levels_hpa;
  let best = 0;
  lv.forEach((p, i) => { if (Math.abs(Math.log(p / hpa)) < Math.abs(Math.log(lv[best] / hpa))) best = i; });
  return best;
}

function syncControls() {
  fill($("dataset"), manifest.datasets, state.dataset);
  if (!ds().variables.some((v) => v.id === state.variable)) state.variable = ds().variables[0].id;
  fill($("variable"), ds().variables, state.variable);
  fill($("period"), manifest.periods, state.period);
  fill($("mask"), manifest.masks, state.mask);
  $("witness").checked = state.witness;
  $("witness").disabled = !otherDs();
  $("explain").textContent = `${variable().label}: ${variable().explain} Source: ${ds().label}. ${ds().note}`;
}

function keepFn() {
  const period = manifest.periods.find((p) => p.id === state.period);
  const mask = manifest.masks.find((m) => m.id === state.mask);
  const ev = manifest.events.filter((e) => mask.exclude.includes(e.id)).map((e) => [monthKey(e.start), monthKey(e.end)]);
  const a = period.start ? monthKey(period.start) : -Infinity, b = period.end ? monthKey(period.end) : Infinity;
  return (t) => t >= a && t <= b && !ev.some(([s, e]) => t >= s && t <= e);
}

function verdict(p, levels, flip) {
  const v = variable(), u = v.trend_units;
  const up = v.id === "t" ? "warming" : "rising", down = v.id === "t" ? "cooling" : "falling";
  const subject = v.id === "t" ? "the air" : v.label.toLowerCase();
  const column = v.id === "t" ? "the same air column" : `${v.label.toLowerCase()} in the same air column`;
  const where = state.lat == null ? "Averaged over the whole globe" : `At ${latName(manifest.lat_centers[state.lat])}`;
  const sig = levels.map((_, i) => i).filter((i) => p.sig[i] === 1);
  if (!sig.length) return `${where}, no height shows a change that passes the test. That means "not proven", not "no change".`;
  const pos = sig.filter((i) => p.slope[i] > 0), neg = sig.filter((i) => p.slope[i] < 0);
  const strongest = (list) => list.reduce((a, b) => (Math.abs(p.slope[b]) > Math.abs(p.slope[a]) ? b : a));
  const say = (i, word) => `${word} by ${fmt(p.slope[i])} ${u} near ${Math.round(altKm(levels[i]))} km`;
  let s;
  if (pos.length && neg.length) {
    s = `${where}, ${column} is ${say(strongest(pos), up)} and ${say(strongest(neg), down)}.`;
    if (flip != null) s += ` The sign flips at about ${Math.round(altKm(flip))} km.`;
  } else {
    const list = pos.length ? pos : neg;
    s = `${where}, ${subject} is ${say(strongest(list), pos.length ? up : down)}, and no height shows a proven change the other way.`;
  }
  const share = Math.round(100 * sig.length / levels.filter((_, i) => p.slope[i] != null).length);
  return `${s} ${share}% of heights pass the significance test.`;
}

async function render() {
  syncControls();
  const d = ds(), v = variable();
  const trend = await loadTrend(d.id, v.id, state.period, state.mask);
  if (state.level == null || state.level >= d.levels_hpa.length) state.level = nearestLevel(50);

  const other = state.witness ? otherDs() : null;
  let agree = null, otherTrend = null;
  if (other) {
    otherTrend = await loadTrend(other.id, v.id, state.period, state.mask).catch(() => null);
    const a = manifest.agreement.find((x) => x.variable === v.id && x.mask === state.mask && x.period === state.period
      && [x.a, x.b].includes(d.id) && [x.a, x.b].includes(other.id));
    if (a) agree = await loadAgreement(a.file);
  }

  const max = drawCurtain($("curtain"), { trend, ds: d, lats: manifest.lat_centers, latStep: manifest.lat_step, sel: state, agree });
  $("legmin").textContent = `${fmt(-max)} ${v.trend_units}`;
  $("legmax").textContent = `${fmt(max)} ${v.trend_units}`;

  const pick = (t) => (state.lat == null ? t.global
    : { slope: t.slope.map((r) => r[state.lat]), lo: t.lo.map((r) => r[state.lat]), hi: t.hi.map((r) => r[state.lat]), sig: t.sig.map((r) => r[state.lat]) });
  const p = pick(trend);
  const flip = state.lat == null ? trend.global.flip_hpa : trend.flip_hpa[state.lat];
  const place = state.lat == null ? "Whole globe" : latName(manifest.lat_centers[state.lat]);
  $("profileTitle").textContent = `Profile: ${place}`;
  drawProfile($("profile"), { p, levels: d.levels_hpa, other: otherTrend ? pick(otherTrend) : null,
    otherLevels: other ? other.levels_hpa : null, units: v.trend_units, selLevel: state.level });

  const series = await loadSeries(d.id, v.id, state.lat);
  const hpa = d.levels_hpa[state.level];
  const mask = manifest.masks.find((m) => m.id === state.mask);
  $("seriesTitle").textContent = `History: ${v.label.toLowerCase()}, ${place}, ${hpa} hPa (about ${Math.round(altKm(hpa))} km)`;
  drawSeries($("series"), { y: series.anom[state.level], axis: monthAxis(d.time.start, d.time.n), slope: p.slope[state.level],
    events: manifest.events, masked: mask.exclude, keep: keepFn(), units: v.units });

  // Does leaving out an event change the answer at the selected height?
  let note = "";
  const here = p.slope[state.level];
  for (const m of manifest.masks) {
    if (m.id === state.mask || here == null) continue;
    const alt = await loadTrend(d.id, v.id, state.period, m.id).catch(() => null);
    if (!alt) continue;
    const q = pick(alt), there = q.slope[state.level];
    if (there == null) continue;
    const flipped = q.sig[state.level] !== p.sig[state.level];
    if (flipped || Math.abs(there - here) > 0.25 * Math.max(Math.abs(here), Math.abs(there))) {
      note = ` At ${Math.round(altKm(hpa))} km the trend is ${fmt(here)} ${v.trend_units} with "${mask.label}" and ${fmt(there)} with "${m.label}"`
        + (flipped ? `, and the test result changes.` : `.`) + ` Treat this height with care.`;
      break;
    }
  }
  $("verdict").textContent = verdict(p, d.levels_hpa, flip) + note;
}

function bind() {
  for (const id of ["dataset", "variable", "period", "mask"]) {
    $(id).addEventListener("change", (e) => { state[id] = e.target.value; if (id === "dataset") state.level = null; render(); });
  }
  $("witness").addEventListener("change", (e) => { state.witness = e.target.checked; render(); });
  $("globe").addEventListener("click", () => { state.lat = null; render(); });

  const pos = (c, e) => { const r = c.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  $("curtain").addEventListener("click", (e) => {
    const hit = e.currentTarget._hit?.(...pos(e.currentTarget, e));
    if (hit) { state.lat = hit.lat; state.level = hit.level; render(); }
  });
  $("profile").addEventListener("click", (e) => {
    const hit = e.currentTarget._hit?.(...pos(e.currentTarget, e));
    if (hit) { state.level = hit.level; render(); }
  });
  const tip = $("tip");
  $("curtain").addEventListener("mousemove", async (e) => {
    const hit = e.currentTarget._hit?.(...pos(e.currentTarget, e));
    if (!hit) { tip.hidden = true; return; }
    const d = ds(), v = variable(), t = await loadTrend(d.id, v.id, state.period, state.mask);
    const s = t.slope[hit.level][hit.lat];
    const hp = d.levels_hpa[hit.level];
    tip.textContent = `${latName(manifest.lat_centers[hit.lat])}, ${hp} hPa (~${Math.round(altKm(hp))} km)\n`
      + (s == null ? "no data" : `${fmt(s)} ${v.trend_units}  [${fmt(t.lo[hit.level][hit.lat])} to ${fmt(t.hi[hit.level][hit.lat])}]\n`
      + (t.sig[hit.level][hit.lat] === 1 ? "passes the test" : "not proven"));
    tip.style.left = e.clientX + 14 + "px"; tip.style.top = e.clientY + 14 + "px"; tip.hidden = false;
  });
  $("curtain").addEventListener("mouseleave", () => { tip.hidden = true; });

  document.querySelectorAll("[data-case]").forEach((b) => b.addEventListener("click", () => {
    const c = CASES[b.dataset.case];
    if (!manifest.datasets.some((d) => d.id === c.dataset)) return;
    Object.assign(state, { dataset: c.dataset, variable: c.variable, period: c.period, mask: c.mask, witness: c.witness });
    state.lat = c.latDeg == null ? null : manifest.lat_centers.findIndex((x) => Math.abs(x - c.latDeg) < manifest.lat_step / 2);
    state.level = nearestLevel(c.hpa);
    render();
  }));
  let timer;
  window.addEventListener("resize", () => { clearTimeout(timer); timer = setTimeout(render, 120); });
}

async function start() {
  try {
    manifest = await loadManifest();
  } catch (err) {
    $("verdict").textContent = "No data found. Run `lapse demo` in the pipeline folder first.";
    return;
  }
  if (manifest.synthetic) {
    $("banner").hidden = false;
    $("banner").textContent = "Synthetic demo data. These are not NASA measurements.";
  }
  const m = manifest.method;
  $("method").textContent = `Method: ${m.slope} slope, ${m.test}. Cells are flagged at a false discovery rate of ${m.fdr_q}. `
    + `Trends are per ${m.trend_per}. Heights in km are approximate.`;
  state.dataset = manifest.datasets[0].id;
  if (!manifest.periods.some((p) => p.id === state.period)) state.period = manifest.periods[0].id;
  bind();
  window.lapse = { state, render };          // handy in the browser console
  await render();
}
start();
