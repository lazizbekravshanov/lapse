import { loadManifest, loadGlossary, loadTrend, loadSeries, loadPairs, monthAxis, monthKey } from "./data.js";
import { drawCurtain } from "./curtain.js";
import { drawProfile } from "./profile.js";
import { drawSeries } from "./series.js";
import { kmOf, fmt, latName } from "./draw.js";
import { answer, detail, labelOf, placeShort, wordsFor } from "./words.js";
import { CASES } from "./cases.js";
import { initStart } from "./start.js";

const $ = (id) => document.getElementById(id);
const state = { dataset: null, variable: "t", period: null, mask: "none", place: { region: "global" }, hpa: 10, witness: true };
let manifest, content, live = null;      // live = { def, step } while a case file is open
let current = {};                        // what the last render loaded

// --- reading the manifest -----------------------------------------------------
const ds = (id = state.dataset) => manifest.datasets.find((d) => d.id === id);
const variable = () => ds().variables.find((v) => v.id === state.variable);
const datasetsWith = (v) => manifest.datasets.filter((d) => d.variables.some((x) => x.id === v))
  .sort((a, b) => (a.kind === "satellite" ? -1 : 0) - (b.kind === "satellite" ? -1 : 0));
const witnessOf = (d = state.dataset, v = state.variable, p = state.period) =>
  manifest.witness.find((w) => w.dataset === d && w.variable === v && w.period === p);
const overlapPeriod = (d, v) => (ds(d).periods.find((p) => witnessOf(d, v, p.id)) || ds(d).periods[0]).id;

function nearestLevel(hpa, d = ds()) {
  let best = 0;
  d.levels_hpa.forEach((p, i) => { if (Math.abs(Math.log(p / hpa)) < Math.abs(Math.log(d.levels_hpa[best] / hpa))) best = i; });
  return best;
}

function normalize() {
  if (!ds() || !variable()) {
    const options = datasetsWith(state.variable);
    if (options.length) state.dataset = (options.find((d) => d.id === state.dataset) || options[0]).id;
    else { state.dataset = manifest.datasets[0].id; state.variable = ds().variables[0].id; }
  }
  if (!ds().periods.some((p) => p.id === state.period)) state.period = overlapPeriod(state.dataset, state.variable);
  if (!manifest.masks.some((m) => m.id === state.mask)) state.mask = "none";
  const okLat = state.place.lat != null && state.place.lat >= 0 && state.place.lat < manifest.lat_centers.length;
  const okRegion = state.place.region && manifest.regions.some((r) => r.id === state.place.region);
  if (!okLat && !okRegion) state.place = { region: "global" };
  if (!(state.hpa > 0)) state.hpa = 10;
}

// --- the address bar holds the view, so any view can be shared ----------------
function writeUrl() {
  const q = new URLSearchParams({ d: state.dataset, v: state.variable, p: state.period, m: state.mask,
    at: state.place.region ?? "lat" + state.place.lat, h: String(state.hpa), w: state.witness ? "1" : "0" });
  history.replaceState(null, "", "#" + q);
}
function readUrl() {
  const q = new URLSearchParams(location.hash.slice(1));
  if (!q.has("d")) return false;
  const at = q.get("at") || "global";
  Object.assign(state, { dataset: q.get("d"), variable: q.get("v") || "t", period: q.get("p"), mask: q.get("m") || "none",
    place: at.startsWith("lat") ? { lat: Number(at.slice(3)) } : { region: at }, hpa: Number(q.get("h")) || 10, witness: q.get("w") !== "0" });
  return true;
}

// --- one column of air out of a trend file ------------------------------------
function column(t) {
  if (state.place.region) return t.regions[state.place.region];
  const j = state.place.lat, pick = (k) => t[k].map((r) => r[j]);
  return { slope: pick("slope"), lo: pick("lo"), hi: pick("hi"), verdict: pick("verdict"), reason: pick("reason"),
    step: t.step ? pick("step") : null, flip_hpa: t.flip_hpa[j] };
}

function keepFn(period) {
  const mask = manifest.masks.find((m) => m.id === state.mask);
  const out = manifest.events.filter((e) => mask.exclude.includes(e.id)).map((e) => [monthKey(e.start), monthKey(e.end)]);
  const a = monthKey(period.start), b = monthKey(period.end);
  return (t) => t >= a && t <= b && !out.some(([s, e]) => t >= s && t <= e);
}

function fill(select, items, value) {
  select.innerHTML = items.map((i) => `<option value="${i.id}">${i.label}</option>`).join("");
  select.value = value;
}

function syncControls() {
  const variables = [];
  for (const d of manifest.datasets) for (const v of d.variables) if (!variables.some((x) => x.id === v.id)) variables.push(v);
  fill($("variable"), variables, state.variable);
  fill($("dataset"), datasetsWith(state.variable), state.dataset);
  fill($("period"), ds().periods.map((p) => ({ id: p.id, label: `${p.label}: ${p.start.slice(0, 4)} to ${p.end.slice(0, 4)}` })), state.period);
  fill($("mask"), manifest.masks, state.mask);
  const places = manifest.regions.map((r) => ({ id: r.id, label: r.label }));
  if (state.place.lat != null) places.push({ id: "lat", label: placeShort(state.place, manifest) });
  fill($("place"), places, state.place.region ?? "lat");
  const w = witnessOf();
  $("witness").checked = state.witness && !!w;
  $("witness").disabled = !w;
  $("witnessLabel").textContent = w ? `Show the second dataset (${ds(w.with_dataset).label})` : "No second dataset for this view";
  const v = variable();
  $("explain").textContent = `${v.label}: ${v.explain} ${v.limit_note || ""} Source: ${ds().label}. ${ds().note}`;
}

// --- drawing everything -------------------------------------------------------
async function render() {
  normalize();
  syncControls();
  const d = ds(), v = variable(), period = d.periods.find((p) => p.id === state.period);
  const level = nearestLevel(state.hpa);
  const trend = await loadTrend(d.id, v.id, state.period, state.mask);
  const w = witnessOf();
  const other = w ? await loadTrend(w.with_dataset, v.id, w.with_period, state.mask).catch(() => null) : null;
  const col = column(trend), otherCol = other && state.witness ? column(other) : null;
  current = { trend, other, col, level, period };

  const max = drawCurtain($("curtain"), { trend, ds: d, lats: manifest.lat_centers, latStep: manifest.lat_step,
    regions: manifest.regions, sel: { place: state.place, level }, content });
  $("legmin").textContent = `${fmt(-max)} ${v.trend_units_plain}`;
  $("legmax").textContent = `${fmt(max)} ${v.trend_units_plain}`;

  const place = placeShort(state.place, manifest);
  $("profileTitle").textContent = `Every height: ${place}`;
  $("profileNote").textContent = otherCol ? `Dashed orange line: ${ds(w.with_dataset).label}.` : "";
  drawProfile($("profile"), { col, levels: d.levels_hpa, other: otherCol, otherLevels: w ? ds(w.with_dataset).levels_hpa : null,
    units: v.trend_units_plain, selLevel: level });

  const hpa = d.levels_hpa[level];
  const series = await loadSeries(d.id, v.id, state.place);
  const mask = manifest.masks.find((m) => m.id === state.mask);
  const events = manifest.events.filter((e) => !e.datasets || e.datasets.includes(d.id));
  $("seriesTitle").textContent = `Month by month: ${v.label.toLowerCase()}, ${place}, about ${Math.round(kmOf(hpa))} km up`;
  drawSeries($("series"), { y: series.anom[level], axis: monthAxis(d.time.start, d.time.n), slope: col.slope[level],
    events, masked: mask.exclude, keep: keepFn(period), units: v.units_plain });

  $("answer").textContent = answer({ col, levels: d.levels_hpa, place: state.place, variable: v, manifest });
  $("detail").textContent = detail({ col, i: level, levels: d.levels_hpa, variable: v, manifest, years: trend.span.years });
  $("curtain").setAttribute("aria-label", `Map of trends by latitude and height. ${$("answer").textContent}`);

  renderPairs(await loadPairs(d.id, v.id, state.period).catch(() => null));
  if (live) await renderCase();
  writeUrl();
}

function renderPairs(pairs) {
  const d = ds(), v = variable(), w = wordsFor(v), u = v.trend_units_plain, box = $("pairs");
  const km = (hpa) => Math.round(kmOf(hpa));
  const items = [];
  for (const p of pairs ? pairs.vertical : []) {
    const where = p.where.region ? manifest.regions.find((r) => r.id === p.where.region).label : `Ring at ${latName(manifest.lat_centers[p.where.lat])}`;
    const at = p.where.region ?? "lat" + p.where.lat;
    items.push(`<li><button type="button" class="link" data-at="${at}" data-hpa="${p.high.hpa}">${where}</button>:
      ${p.low.slope > 0 ? w.up : w.down} ${fmt(p.low.slope)} near ${km(p.low.hpa)} km, ${p.high.slope > 0 ? w.up : w.down} ${fmt(p.high.slope)} near ${km(p.high.hpa)} km</li>`);
  }
  for (const p of pairs ? pairs.horizontal.slice(0, 4) : []) {
    const a = latName(manifest.lat_centers[p.a.lat]), b = latName(manifest.lat_centers[p.b.lat]);
    items.push(`<li>Near ${km(p.hpa)} km: <button type="button" class="link" data-at="lat${p.a.lat}" data-hpa="${p.hpa}">${a}</button> ${fmt(p.a.slope)},
      <button type="button" class="link" data-at="lat${p.b.lat}" data-hpa="${p.hpa}">${b}</button> ${fmt(p.b.slope)}</li>`);
  }
  box.hidden = !items.length;
  $("pairList").innerHTML = items.join("");
  $("pairUnits").textContent = `Numbers are in ${u}. Only "${labelOf(manifest, 1)}" and "${labelOf(manifest, 2)}" trends are listed. Dataset: ${d.label}.`;
}

// --- case files ---------------------------------------------------------------
function caseAvailable(def) {
  const first = def.steps[0].set;
  return def.id === "jump" ? !!ds("merra2") : datasetsWith(first.variable).length > 0;
}

function applyStep() {
  const merged = {};
  for (let i = 0; i <= live.step; i++) Object.assign(merged, live.def.steps[i].set);
  const d = ds(merged.dataset) ? merged.dataset : datasetsWith(merged.variable)[0].id;
  const period = merged.period === "overlap" ? overlapPeriod(d, merged.variable) : ds(d).periods[0].id;
  Object.assign(state, { dataset: d, variable: merged.variable, period, mask: merged.mask, place: { ...merged.place }, hpa: merged.hpa, witness: merged.witness });
}

async function renderCase() {
  const d = ds(), v = variable(), w = wordsFor(v), wit = witnessOf();
  const byMask = {};
  for (const m of manifest.masks) byMask[m.id] = await loadTrend(d.id, v.id, state.period, m.id).catch(() => null);
  const col = (m) => column(byMask[m || state.mask] || current.trend);
  const i = (hpa) => nearestLevel(hpa);
  const otherCol = current.other ? column(current.other) : null;
  const otherAt = (hpa) => { const lv = ds(wit.with_dataset).levels_hpa; const k = lv.indexOf(d.levels_hpa[i(hpa)]); return k < 0 ? null : otherCol.slope[k]; };
  const h = {
    km: (hpa) => Math.round(kmOf(d.levels_hpa[i(hpa)])),
    rate: (hpa, m) => `${fmt(col(m).slope[i(hpa)])} ${v.trend_units_plain}`,
    verb: (hpa, m) => (col(m).slope[i(hpa)] > 0 ? w.upPast : w.downPast),
    label: (hpa, m) => `"${labelOf(manifest, col(m).verdict[i(hpa)])}"`,
    share: (hpa, a, b) => Math.abs(col(b).slope[i(hpa)] - col(a).slope[i(hpa)]) / Math.abs(col(a).slope[i(hpa)]),
    step: (hpa) => fmt(col().step ? col().step[i(hpa)] : null, 1),
    total: (hpa) => `${fmt(col().slope[i(hpa)] * current.trend.span.years / 10, 1)} ${v.units_plain}`,
    bigger: (hpa) => col().step && Math.abs(col().step[i(hpa)]) > Math.abs(col().slope[i(hpa)] * current.trend.span.years / 10),
    hasOther: () => !!otherCol,
    otherName: () => ds(wit.with_dataset).label,
    other: (hpa) => (otherAt(hpa) == null ? "no value" : `${fmt(otherAt(hpa))} ${v.trend_units_plain}`),
    since: () => current.trend.span.start.slice(0, 4),
    years: () => Math.round(current.trend.span.years),
  };
  const n = live.def.steps.length;
  $("caseTitle").textContent = `${live.def.title}: ${live.def.question}`;
  $("caseText").textContent = live.def.steps[live.step].say(h);
  $("caseCount").textContent = `Step ${live.step + 1} of ${n}`;
  $("caseBack").disabled = live.step === 0;
  $("caseNext").textContent = live.step === n - 1 ? "Finish" : "Next";
}

function openCase(def) { live = { def, step: 0 }; $("case").hidden = false; applyStep(); render(); $("case").scrollIntoView({ block: "nearest" }); }
function closeCase() { live = null; $("case").hidden = true; }

// --- wiring -------------------------------------------------------------------
function bind() {
  const user = (fn) => (e) => { closeCase(); fn(e); render(); };
  $("variable").addEventListener("change", user((e) => { state.variable = e.target.value; state.dataset = datasetsWith(e.target.value)[0].id; state.period = null; }));
  $("dataset").addEventListener("change", user((e) => { state.dataset = e.target.value; state.period = null; }));
  $("period").addEventListener("change", user((e) => { state.period = e.target.value; }));
  $("mask").addEventListener("change", user((e) => { state.mask = e.target.value; }));
  $("place").addEventListener("change", user((e) => { if (e.target.value !== "lat") state.place = { region: e.target.value }; }));
  $("witness").addEventListener("change", user((e) => { state.witness = e.target.checked; }));
  $("copy").addEventListener("click", () => { navigator.clipboard?.writeText(location.href).then(() => { $("copy").textContent = "Link copied"; }, () => {}); });

  const pos = (c, e) => { const r = c.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  $("curtain").addEventListener("click", user((e) => {
    const hit = e.currentTarget._hit?.(...pos(e.currentTarget, e));
    if (hit) { state.place = { lat: hit.lat }; state.hpa = ds().levels_hpa[hit.level]; }
  }));
  $("profile").addEventListener("click", user((e) => {
    const hit = e.currentTarget._hit?.(...pos(e.currentTarget, e));
    if (hit) state.hpa = ds().levels_hpa[hit.level];
  }));

  // Arrow keys: left and right move around the Earth, up and down change the height.
  const keys = (e) => {
    const d = ds(), order = d.levels_hpa.map((_, i) => i).sort((a, b) => d.levels_hpa[b] - d.levels_hpa[a]);
    const at = order.indexOf(nearestLevel(state.hpa));
    const n = manifest.lat_centers.length, lat = state.place.lat ?? Math.floor(n / 2);
    if (e.key === "ArrowUp") state.hpa = d.levels_hpa[order[Math.min(order.length - 1, at + 1)]];
    else if (e.key === "ArrowDown") state.hpa = d.levels_hpa[order[Math.max(0, at - 1)]];
    else if (e.key === "ArrowLeft" && e.currentTarget.id === "curtain") state.place = { lat: Math.max(0, lat - 1) };
    else if (e.key === "ArrowRight" && e.currentTarget.id === "curtain") state.place = { lat: Math.min(n - 1, lat + 1) };
    else return;
    e.preventDefault(); closeCase(); render();
  };
  $("curtain").addEventListener("keydown", keys);
  $("profile").addEventListener("keydown", keys);

  const tip = $("tip");
  $("curtain").addEventListener("mousemove", (e) => {
    const hit = e.currentTarget._hit?.(...pos(e.currentTarget, e)), t = current.trend;
    if (!hit || !t) { tip.hidden = true; return; }
    const v = variable(), s = t.slope[hit.level][hit.lat], hp = ds().levels_hpa[hit.level];
    tip.textContent = `Ring at ${latName(manifest.lat_centers[hit.lat])}, about ${Math.round(kmOf(hp))} km up\n`
      + (s == null ? "No measurements here" : `${fmt(s)} ${v.trend_units_plain}\nvery likely between ${fmt(t.lo[hit.level][hit.lat])} and ${fmt(t.hi[hit.level][hit.lat])}\n${labelOf(manifest, t.verdict[hit.level][hit.lat])}`);
    tip.style.left = Math.min(e.clientX + 14, window.innerWidth - 250) + "px"; tip.style.top = e.clientY + 14 + "px"; tip.hidden = false;
  });
  $("curtain").addEventListener("mouseleave", () => { tip.hidden = true; });

  $("pairs").addEventListener("click", (e) => {
    const b = e.target.closest("[data-at]");
    if (!b) return;
    closeCase();
    state.place = b.dataset.at.startsWith("lat") ? { lat: Number(b.dataset.at.slice(3)) } : { region: b.dataset.at };
    state.hpa = Number(b.dataset.hpa);
    render(); $("answerCard").scrollIntoView({ behavior: "smooth", block: "start" });
  });

  $("caseButtons").innerHTML = CASES.filter(caseAvailable).map((c) => `<button type="button" data-case="${c.id}">${c.title}</button>`).join("");
  $("caseButtons").addEventListener("click", (e) => { const b = e.target.closest("[data-case]"); if (b) openCase(CASES.find((c) => c.id === b.dataset.case)); });
  $("caseNext").addEventListener("click", () => { if (live.step === live.def.steps.length - 1) { closeCase(); return; } live.step++; applyStep(); render(); });
  $("caseBack").addEventListener("click", () => { live.step--; applyStep(); render(); });
  $("caseClose").addEventListener("click", closeCase);

  $("startOpen").addEventListener("click", () => { $("start").hidden = false; $("startOpen").hidden = true; });
  let timer;
  window.addEventListener("resize", () => { clearTimeout(timer); timer = setTimeout(render, 120); });
}

function showStart(show) { $("start").hidden = !show; $("startOpen").hidden = show; }

function onStart(choice) {
  showStart(false);
  if (choice) {
    closeCase();
    state.variable = choice.variable; state.dataset = datasetsWith(choice.variable)[0].id; state.period = null;
    state.place = { region: choice.region }; state.mask = "none";
    normalize();
    if (choice.hpa) state.hpa = choice.hpa;
    else {                                   // "every height": open on the strongest labelled change
      loadTrend(state.dataset, state.variable, state.period, "none").then((t) => {
        const c = t.regions[choice.region], lv = ds().levels_hpa;
        let best = null;
        lv.forEach((_, i) => { if (c.verdict[i] >= 1 && c.verdict[i] <= 2 && (best == null || Math.abs(c.slope[i]) > Math.abs(c.slope[best]))) best = i; });
        if (best != null) state.hpa = lv[best];
        render();
      });
      return;
    }
  }
  render();
}

async function start() {
  try {
    [manifest, content] = await Promise.all([loadManifest(), loadGlossary()]);
  } catch (err) {
    $("answer").textContent = "No data found. Run `python -m lapse export` in the repository first.";
    return;
  }
  if (manifest.synthetic) { $("banner").hidden = false; $("banner").textContent = "Synthetic demo data. These are not NASA measurements."; }
  $("legend").innerHTML = [2, 1, 0, 3].map((c) => manifest.verdicts.find((v) => v.code === c))
    .map((v) => `<li><i class="sw sw-${v.id}"></i><span><strong>${v.label}.</strong> ${v.meaning}</span></li>`).join("");
  $("glossary").innerHTML = content.terms.map((t) => `<div><dt>${t.plain} <small>${t.science}</small></dt><dd>${t.explain}</dd></div>`).join("");
  const m = manifest.method;
  $("method").textContent = `How the numbers are made: ${m.slope} slope, ${m.test}, false discovery rate ${m.fdr_q}. Heights in km are approximate. Data last processed ${manifest.generated_at.slice(0, 10)}.`;
  const fromUrl = readUrl();
  if (!fromUrl) state.dataset = datasetsWith("t")[0]?.id ?? manifest.datasets[0].id;
  initStart($("start"), manifest, onStart);
  showStart(!fromUrl);
  bind();
  window.lapse = { state, render };
  await render();
}
start();
