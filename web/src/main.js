import { loadManifest, loadCatalog, loadGlossary, setRoutes, loadTrend, loadSeries, loadPairs, monthAxis, monthKey } from "./data.js";
import { drawCurtain } from "./curtain.js";
import { drawProfile } from "./profile.js";
import { drawSeries } from "./series.js";
import { kmOf, hpaOf, fmt, latName } from "./draw.js";
import { answer, brief, detail, labelOf, reasonOf, placeShort, wordsFor } from "./words.js";
import { drawSky } from "./sky.js";
import { initAsk } from "./ask.js";
import { initAscent } from "./ascent.js";
import { CITIES } from "./cities.js";
import { CASES } from "./cases.js";

const $ = (id) => document.getElementById(id);
const state = { dataset: null, variable: "t", period: null, mask: "none", method: null, place: { region: "global" }, hpa: 10, witness: true };
let manifest, catalog, content, live = null;      // live = { def, step } while a case file is open
let current = {};                        // what the last render loaded
let ascent = null;

// --- reading the manifest -----------------------------------------------------
const ds = (id = state.dataset) => manifest.datasets.find((d) => d.id === id);
const variable = () => ds().variables.find((v) => v.id === state.variable);
const datasetsWith = (v) => manifest.datasets.filter((d) => d.variables.some((x) => x.id === v));
// "Auto" is decided once, by the hub (manifest.auto). The site only reads it.
const autoDataset = (v) => manifest.auto[v].dataset;
const autoPeriod = (d, v) => manifest.auto[v].periods[d];
const witnessOf = (d = state.dataset, v = state.variable, p = state.period) =>
  manifest.witness.find((w) => w.dataset === d && w.variable === v && w.period === p);

function nearestLevel(hpa, d = ds()) {
  let best = 0;
  d.levels_hpa.forEach((p, i) => { if (Math.abs(Math.log(p / hpa)) < Math.abs(Math.log(d.levels_hpa[best] / hpa))) best = i; });
  return best;
}

function normalize() {
  if (!ds() || !variable()) {
    const options = datasetsWith(state.variable);
    if (options.length) state.dataset = options.some((d) => d.id === state.dataset) ? state.dataset : autoDataset(state.variable);
    else { state.dataset = manifest.datasets[0].id; state.variable = ds().variables[0].id; }
  }
  if (!ds().periods.some((p) => p.id === state.period)) state.period = autoPeriod(state.dataset, state.variable);
  if (!manifest.masks.some((m) => m.id === state.mask)) state.mask = "none";
  if (!catalog.methods.some((m) => m.id === state.method)) state.method = catalog.defaults.method;
  const okLat = state.place.lat != null && state.place.lat >= 0 && state.place.lat < manifest.lat_centers.length;
  const okRegion = state.place.region && manifest.regions.some((r) => r.id === state.place.region);
  if (!okLat && !okRegion) state.place = { region: "global" };
  if (!(state.hpa > 0)) state.hpa = 10;
}

// --- the address bar holds the view, so any view can be shared ----------------
function writeUrl() {
  const q = new URLSearchParams({ d: state.dataset, v: state.variable, p: state.period, m: state.mask,
    t: state.method, at: state.place.region ?? "lat" + state.place.lat, h: String(state.hpa), w: state.witness ? "1" : "0" });
  history.replaceState(null, "", "#" + q);
}
function readUrl() {
  const q = new URLSearchParams(location.hash.slice(1));
  if (!q.has("d")) return false;
  const at = q.get("at") || "global";
  Object.assign(state, { dataset: q.get("d"), variable: q.get("v") || "t", period: q.get("p"), mask: q.get("m") || "none", method: q.get("t"),
    place: at.startsWith("lat") ? { lat: Number(at.slice(3)) } : { region: at }, hpa: Number(q.get("h")) || 10, witness: q.get("w") !== "0" });
  return true;
}

// --- one column of air out of a trend file ------------------------------------
function column(t) {
  if (state.place.region) return t.regions[state.place.region];
  const j = state.place.lat, pick = (k) => t[k].map((r) => r[j]);
  return { slope: pick("slope"), lo: pick("lo"), hi: pick("hi"), verdict: pick("verdict"), reason: pick("reason"),
    agree: pick("agree"), step: t.step ? pick("step") : null, flip_hpa: t.flip_hpa[j] };
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
  fill($("period"), ds().periods.map((p) => ({ id: p.id, label: `${p.label}: ${p.start.slice(0, 4)} to ${p.end.slice(0, 4)}` })), state.period);
  fill($("mask"), manifest.masks, state.mask);
  const places = manifest.regions.map((r) => ({ id: r.id, label: r.label }));
  if (state.place.lat != null) places.push({ id: "lat", label: placeShort(state.place, manifest) });
  fill($("place"), places, state.place.region ?? "lat");
  const w = witnessOf();
  $("witness").checked = state.witness && !!w;
  $("witness").disabled = !w;
  $("witnessLabel").textContent = w ? `Show the second dataset (${ds(w.with_dataset).label})` : "No second dataset for this view";
  const chip = (id, label, on, full = label) => `<button type="button" class="chip" data-id="${id}" aria-pressed="${on}" title="${full}" aria-label="${full}">${label}</button>`;
  const short = { global: "Globe", north_mid: "North", south_mid: "South", t: "Temperature" };
  $("pickWhat").innerHTML = variables.map((x) => chip(x.id, short[x.id] ?? x.label, x.id === state.variable, x.label)).join("");
  $("pickWhere").innerHTML = places.map((x) => chip(x.id, short[x.id] ?? x.label, x.id === (state.place.region ?? "lat"), x.label)).join("");
  const v = variable();
  $("explain").textContent = `${v.label}: ${v.explain} ${v.limit_note || ""}`;
  renderTools();
}

// --- the toolbox: every tool the hub offers, in one place ---------------------
const autoChoice = () => {
  const d = autoDataset(state.variable);
  return { dataset: d, method: catalog.defaults.method, period: autoPeriod(d, state.variable) };
};
const onAuto = () => { const a = autoChoice(); return a.dataset === state.dataset && a.method === state.method && a.period === state.period; };

function renderTools() {
  const card = (kind, id, on, off, title, tag, text, small) => `
    <button type="button" class="card" data-tool="${kind}" data-id="${id}" aria-pressed="${on}" ${off ? "disabled" : ""}>
      <strong>${title}</strong>${tag ? `<em>${tag}</em>` : ""}<span>${text}</span><small>${small}</small></button>`;
  const can = datasetsWith(state.variable).map((d) => d.id), v = variable();
  $("toolData").innerHTML = manifest.datasets.map((d) => card("dataset", d.id, d.id === state.dataset, !can.includes(d.id),
    d.label, d.kind === "satellite" ? "Measured from orbit" : "Model + measurements",
    can.includes(d.id) ? d.note : `Does not measure ${v.label.toLowerCase()}.`,
    `${d.time.start.slice(0, 4)} to ${d.time.end.slice(0, 4)}, ${d.levels_hpa.length} heights. ${d.source}`)).join("");
  $("toolMethod").innerHTML = catalog.methods.map((m) => card("method", m.id, m.id === state.method, false,
    m.label, m.recommended ? "Recommended" : m.sound ? "" : "Comparison only", m.plain + (m.caution ? " " + m.caution : ""), m.science)).join("");
  $("toolChecks").innerHTML = catalog.checks.map((c) => `<li><strong>${c.label}.</strong> ${c.plain}</li>`).join("");
  $("auto").setAttribute("aria-pressed", onAuto());
  const a = autoChoice();
  $("autoNote").textContent = onAuto() ? `Auto is on: ${ds(a.dataset).label}, ${catalog.methods.find((m) => m.id === a.method).label.toLowerCase()} method.`
    : "You chose the tools yourself. Press Auto to go back to the recommended ones.";
}

async function renderCompare(level) {
  const d = ds(), v = variable(), hpa = d.levels_hpa[level];
  const rows = [];
  for (const m of catalog.methods) {
    const t = await loadTrend(d.id, v.id, state.period, state.mask, m.id).catch(() => null);
    const c = t ? column(t) : null;
    if (!c || c.slope[level] == null) { rows.push(`<tr><td>${m.label}</td><td colspan="4">No result</td></tr>`); continue; }
    rows.push(`<tr class="${m.id === state.method ? "on" : ""}"><td><button type="button" class="link" data-tool="method" data-id="${m.id}">${m.label}</button>${m.sound ? "" : " <small>(comparison only)</small>"}</td>
      <td>${fmt(c.slope[level])}</td><td>${fmt(c.lo[level])} to ${fmt(c.hi[level])}</td>
      <td>${c.verdict[level] === 0 ? "No" : "Yes"}</td><td>${labelOf(manifest, c.verdict[level])}</td></tr>`);
  }
  const mine = current.col, n = catalog.sound_methods.length, k = mine.agree ? mine.agree[level] : null;
  const w = wordsFor(v), dir = mine.slope[level] > 0 ? w.upNoun : w.downNoun;
  $("compareTitle").textContent = `Does the method change the answer? ${placeShort(state.place, manifest)}, about ${Math.round(kmOf(hpa))} km up`;
  $("compareRows").innerHTML = rows.join("");
  $("compareUnits").textContent = `Rates are in ${v.trend_units_plain}.`;
  $("compareNote").textContent = k == null ? "" : k === n ? `All ${n} sound methods find a ${dir} here. The choice of method does not change the answer.`
    : k === 0 ? `None of the ${n} sound methods can prove a ${dir} here.`
    : `Only ${k} of the ${n} sound methods find a ${dir} here. The answer depends on the method, so treat it with care.`;
}

// --- drawing everything -------------------------------------------------------
async function render() {
  normalize();
  syncControls();
  const d = ds(), v = variable(), period = d.periods.find((p) => p.id === state.period);
  const level = nearestLevel(state.hpa);
  const trend = await loadTrend(d.id, v.id, state.period, state.mask, state.method);
  const w = witnessOf();
  const other = w ? await loadTrend(w.with_dataset, v.id, w.with_period, state.mask, state.method).catch(() => null) : null;
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
  const b = brief({ col, levels: d.levels_hpa, place: state.place, variable: v, manifest });
  const lines = (text) => text.split(/(?<=\.) /).map((x) => `<span>${x}</span>`).join("");
  $("lead").innerHTML = lines(b.headline);
  const top = Math.round(Math.max(...d.levels_hpa.map(kmOf)));
  $("sub").textContent = state.place.lat != null
    ? `The band of sky at ${latName(manifest.lat_centers[state.place.lat])}, all the way around the Earth, not one city. Scroll to rise through ${Math.round(trend.span.years)} years of NASA measurements.`
    : `Scroll to rise through ${Math.round(trend.span.years)} years of NASA measurements, from the ground to ${top} km up.`;
  // Guess first: one question whose answer the headline does not give away.
  const guess = $("guess"), key = [state.dataset, state.variable, state.period, state.mask, state.method, JSON.stringify(state.place)].join("|");
  guess.hidden = !(b.up && b.down);
  if (!guess.hidden && guess.dataset.key !== key) {
    const upLow = kmOf(d.levels_hpa[b.up.i]) < kmOf(d.levels_hpa[b.down.i]);
    guess.dataset.key = key;
    guess.options = [{ text: `The ${b.up.word} ${upLow ? "below" : "above"}`, rate: col.slope[b.up.i] }, { text: `The ${b.down.word} ${upLow ? "above" : "below"}`, rate: col.slope[b.down.i] }];
    guess.units = v.trend_units_plain;
    $("guessA").innerHTML = guess.options.map((o, n) => `<button type="button" class="chip" data-n="${n}">${o.text}</button>`).join("");
    $("guessOut").textContent = "";
  }
  $("topTitle").innerHTML = lines(b.up && b.down ? "One sky. Two directions." : b.headline);
  $("source").textContent = `${v.label}, ${b.where.charAt(0).toLowerCase() + b.where.slice(1)}. ${d.label}, ${trend.span.start.slice(0, 4)} to ${trend.span.end.slice(0, 4)}.`;
  const tile = (t, cls) => (t ? `<div class="stat ${cls}"><b>${fmt(col.slope[t.i])}</b><span>${v.trend_units_plain}</span><span>near ${Math.round(kmOf(d.levels_hpa[t.i]))} km · ${labelOf(manifest, col.verdict[t.i]).toLowerCase()}</span></div>` : "");
  $("stats").innerHTML = tile(b.up, "up") + tile(b.down, "down")
    + (b.flipKm == null ? "" : `<div class="stat"><b>${b.flipKm} km</b><span>where the direction flips</span></div>`);
  $("tally").textContent = b.tally;
  current.scale = drawSky($("sky"), { col, levels: d.levels_hpa, units: v.trend_units_plain, selLevel: null, content,
    labelOf: (c) => labelOf(manifest, c), compact: window.matchMedia("(max-width: 900px)").matches });
  current.view = { col, levels: d.levels_hpa, variable: v, content, scale: current.scale, words: wordsFor(v),
    label: (c) => labelOf(manifest, c), reason: (c) => reasonOf(manifest, c) };
  $("detail").textContent = detail({ col, i: level, levels: d.levels_hpa, variable: v, manifest, years: trend.span.years })
    + ` Tools used: ${d.label}, ${catalog.methods.find((m) => m.id === state.method).label.toLowerCase()} method.`;
  $("curtain").setAttribute("aria-label", `Map of trends by latitude and height. ${$("answer").textContent}`);

  await renderCompare(level);
  renderPairs(await loadPairs(d.id, v.id, state.period, state.method).catch(() => null));
  if (live) await renderCase();
  writeUrl();
  ascent?.sync();
}

function renderPairs(pairs) {
  const d = ds(), v = variable(), w = wordsFor(v), u = v.trend_units_plain, box = $("pairs");
  const km = (hpa) => Math.round(kmOf(hpa));
  const near = (hpa) => (km(hpa) < 1 ? "near the ground" : `near ${km(hpa)} km`);
  const items = [];
  for (const p of pairs ? pairs.vertical : []) {
    const where = p.where.region ? manifest.regions.find((r) => r.id === p.where.region).label : `Ring at ${latName(manifest.lat_centers[p.where.lat])}`;
    const at = p.where.region ?? "lat" + p.where.lat;
    items.push(`<li><button type="button" class="link" data-at="${at}" data-hpa="${p.high.hpa}">${where}</button>:
      ${p.low.slope > 0 ? w.up : w.down} ${fmt(p.low.slope)} ${near(p.low.hpa)}, ${p.high.slope > 0 ? w.up : w.down} ${fmt(p.high.slope)} ${near(p.high.hpa)}</li>`);
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
  const d = ds(merged.dataset) ? merged.dataset : autoDataset(merged.variable);
  const period = merged.period === "overlap" ? autoPeriod(d, merged.variable) : ds(d).periods[0].id;
  Object.assign(state, { dataset: d, variable: merged.variable, period, mask: merged.mask, method: catalog.defaults.method,
    place: { ...merged.place }, hpa: merged.hpa, witness: merged.witness });
}

async function renderCase() {
  const d = ds(), v = variable(), w = wordsFor(v), wit = witnessOf();
  const byMask = {};
  for (const m of manifest.masks) byMask[m.id] = await loadTrend(d.id, v.id, state.period, m.id, state.method).catch(() => null);
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
  $("variable").addEventListener("change", user((e) => { state.variable = e.target.value; state.dataset = autoDataset(e.target.value); state.period = null; }));
  $("tools").addEventListener("click", (e) => {
    const b = e.target.closest("[data-tool]");
    if (!b || b.disabled) return;
    closeCase();
    if (b.dataset.tool === "dataset") { state.dataset = b.dataset.id; state.period = null; }
    if (b.dataset.tool === "method") state.method = b.dataset.id;
    if (b.dataset.tool === "auto") Object.assign(state, autoChoice());
    render();
  });
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
    render().then(() => ascent.toLevel(nearestLevel(state.hpa)));
  });

  $("caseButtons").innerHTML = CASES.filter(caseAvailable).map((c) => `<button type="button" data-case="${c.id}">${c.title}</button>`).join("");
  $("caseButtons").addEventListener("click", (e) => { const b = e.target.closest("[data-case]"); if (b) openCase(CASES.find((c) => c.id === b.dataset.case)); });
  $("caseNext").addEventListener("click", () => { if (live.step === live.def.steps.length - 1) { closeCase(); return; } live.step++; applyStep(); render(); });
  $("caseBack").addEventListener("click", () => { live.step--; applyStep(); render(); });
  $("caseClose").addEventListener("click", closeCase);

  $("pickWhat").addEventListener("click", user((e) => { const b = e.target.closest("[data-id]"); if (b) { state.variable = b.dataset.id; state.dataset = autoDataset(b.dataset.id); state.period = null; } }));
  $("pickWhere").addEventListener("click", user((e) => { const b = e.target.closest("[data-id]"); if (b && b.dataset.id !== "lat") state.place = { region: b.dataset.id }; }));
  $("guessA").addEventListener("click", (e) => {
    const pick = e.target.closest("[data-n]"), g = $("guess");
    if (!pick) return;
    const win = Math.abs(g.options[0].rate) >= Math.abs(g.options[1].rate) ? 0 : 1, lose = 1 - win;
    for (const c of $("guessA").children) { c.disabled = true; c.setAttribute("aria-pressed", String(Number(c.dataset.n) === win)); }
    $("guessOut").textContent = `${Number(pick.dataset.n) === win ? "Right." : "Not this time."} ${g.options[win].text}: ${fmt(g.options[win].rate)} against ${fmt(g.options[lose].rate)} ${g.units}. Now climb through it.`;
  });
  // Above you: the band of latitude you are in. The location never leaves the browser.
  const aboveLat = (lat) => {
    let best = 0;
    manifest.lat_centers.forEach((c, i) => { if (Math.abs(c - lat) < Math.abs(manifest.lat_centers[best] - lat)) best = i; });
    closeCase(); state.place = { lat: best };
    render().then(() => window.scrollTo({ top: $("ascent").offsetTop, behavior: "smooth" }));
  };
  const askCity = () => { $("cityBox").hidden = false; $("city").focus(); };
  $("cities").innerHTML = Object.keys(CITIES).sort().map((c) => `<option value="${c}">`).join("");
  $("above").addEventListener("click", () => {
    $("cityBox").hidden = false;
    if (!navigator.geolocation) return askCity();
    navigator.geolocation.getCurrentPosition((pos) => aboveLat(pos.coords.latitude), askCity, { maximumAge: 600000, timeout: 8000 });
  });
  $("city").addEventListener("change", (e) => {
    const text = e.target.value.trim(), name = Object.keys(CITIES).find((c) => c.toLowerCase() === text.toLowerCase());
    const m = text.match(/^(-?\d+(?:\.\d+)?)\s*°?\s*([nsNS])?$/), lat = name ? CITIES[name] : m ? Number(m[1]) * (/s/i.test(m[2] || "") ? -1 : 1) : null;
    if (lat == null || Math.abs(lat) > 90) { $("aboveNote").textContent = "Not in the list. Type a latitude instead, for example 39 N."; return; }
    $("aboveNote").textContent = `${name ?? "That latitude"} sits in the band at ${latName(manifest.lat_centers.reduce((a, c) => (Math.abs(c - lat) < Math.abs(a - lat) ? c : a))) }.`;
    aboveLat(lat);
  });
  $("sky").addEventListener("click", (e) => { const b = e.target.closest("[data-level]"); if (b) ascent.toLevel(Number(b.dataset.level)); });
  let timer;
  window.addEventListener("resize", () => { clearTimeout(timer); timer = setTimeout(render, 120); });
}

// The ask box found something: move every chart to it.
function showFromAsk(args) {
  closeCase();
  if (args.what && manifest.auto[args.what]) { state.variable = args.what; state.dataset = autoDataset(args.what); state.period = null; }
  if (args.data && args.data !== "auto" && ds(args.data)) { state.dataset = args.data; state.period = null; }
  if (args.method && args.method !== "auto") state.method = args.method;
  if (args.where != null) {
    const where = String(args.where).toLowerCase(), m = where.match(/^(-?\d+(?:\.\d+)?)\s*([ns])?/);
    if (manifest.regions.some((r) => r.id === where)) state.place = { region: where };
    else if (m) {
      const lat = Number(m[1]) * (m[2] === "s" ? -1 : 1);
      let best = 0;
      manifest.lat_centers.forEach((c, i) => { if (Math.abs(c - lat) < Math.abs(manifest.lat_centers[best] - lat)) best = i; });
      state.place = { lat: best };
    }
  }
  normalize();
  const want = args.hpa > 0 ? Number(args.hpa) : args.km != null ? hpaOf(Number(args.km)) : null;
  if (want) state.hpa = ds().levels_hpa[nearestLevel(want)];          // snap to a real measured height
  render().then(() => ascent.toLevel(nearestLevel(state.hpa)));
}

async function start() {
  try {
    [manifest, catalog, content] = await Promise.all([loadManifest(), loadCatalog(), loadGlossary()]);
    setRoutes(catalog.routes);
  } catch (err) {
    $("lead").textContent = "No data found. Run `python -m lapse export` in the repository first.";
    return;
  }
  if (manifest.synthetic) { $("banner").hidden = false; $("banner").textContent = "Synthetic demo data. These are not NASA measurements."; }
  $("legend").innerHTML = [2, 1, 0, 3].map((c) => manifest.verdicts.find((v) => v.code === c))
    .map((v) => `<li><i class="sw sw-${v.id}"></i><span><strong>${v.label}.</strong> ${v.meaning}</span></li>`).join("");
  $("glossary").innerHTML = content.terms.map((t) => `<div><dt>${t.plain} <small>${t.science}</small></dt><dd>${t.explain}</dd></div>`).join("");
  const m = manifest.method;
  $("method").textContent = `Every number comes from the tools listed above, with a false discovery rate of ${m.fdr_q}. Heights in km are approximate. Data last processed ${manifest.generated_at.slice(0, 10)}.`;
  const fromUrl = readUrl();
  if (!fromUrl) state.dataset = manifest.auto.t?.dataset ?? manifest.datasets[0].id;
  bind();
  ascent = initAscent({ section: $("ascent"), stage: $("stage"), play: $("play"), get: () => current.view,
    onSettle: (i) => { if (i !== nearestLevel(state.hpa)) { state.hpa = ds().levels_hpa[i]; render(); } } });
  initAsk({ section: $("ask"), form: $("askForm"), input: $("askInput"), button: $("askGo"), out: $("askOut"),
    tryBox: $("askTry"), note: $("askNote"), onShow: showFromAsk });
  window.lapse = { state, render };
  await render();
}
start();
