// The ascent: scroll, and the page rises from the ground to the top of the record.
// The altitude, the reading and the colour of the page follow the scroll position.
// It only reads numbers the pipeline computed; it computes none.
import { color, kmOf, fmt, VERDICT } from "./draw.js";
import { iconFor, iconSvg } from "./sky.js";

const PHRASE = { "Mount Everest": "As high as Mount Everest.", "Airliners cruise": "Where airliners cruise.", "Ozone layer": "Inside the ozone layer.",
  "Weather balloons pop": "Where weather balloons pop.", "Highest skydive": "As high as the highest skydive." };
const START = 0.06, END = 0.94;

export function initAscent({ section, stage, play, get, onSettle }) {
  const $ = (id) => document.getElementById(id), sky = $("sky");
  let raf = 0, timer = 0, auto = 0, level = -1, shown = -1;
  const rail = $("rail"), rgb = (v, max) => color(v, max, 1).match(/\d+/g).slice(0, 3).join(" ");

  const progress = () => Math.max(0, Math.min(1, (window.scrollY - section.offsetTop) / Math.max(1, section.offsetHeight - window.innerHeight)));
  const nearest = (d, km) => d.levels.reduce((best, p, i) => (Math.abs(kmOf(p) - km) < Math.abs(kmOf(d.levels[best]) - km) ? i : best), 0);

  function frame() {
    raf = 0;
    const d = get();
    if (!d || !d.col) return;
    const p = progress(), phase = p < START ? "intro" : p > END ? "top" : "climb";
    const km = phase === "intro" ? 0 : phase === "top" ? d.scale.maxKm : ((p - START) / (END - START)) * d.scale.maxKm;
    const i = nearest(d, km), s = d.col.slope[i], v = d.col.verdict[i], proven = s != null && v != null && v !== VERDICT.NOT_PROVEN;
    level = phase === "climb" ? i : -1;
    stage.dataset.phase = phase;
    $("skyMark")?.setAttribute("transform", `translate(0 ${d.scale.y(km).toFixed(1)})`);

    // Colour follows the climb. The rate is blended between the two nearest measured
    // heights so the page shifts smoothly from warm to cool; unproven heights stay pale.
    const order = d.levels.map((_, n) => n).sort((a, b) => kmOf(d.levels[a]) - kmOf(d.levels[b]));
    const hiAt = order.findIndex((n) => kmOf(d.levels[n]) >= km), b = order[Math.max(0, hiAt)], a = order[Math.max(0, hiAt - 1)];
    const span = kmOf(d.levels[b]) - kmOf(d.levels[a]), f = span > 0 ? (km - kmOf(d.levels[a])) / span : 0;
    const sa = d.col.slope[a] ?? 0, sb = d.col.slope[hiAt < 0 ? a : b] ?? 0, blend = hiAt < 0 ? sa : sa + (sb - sa) * Math.max(0, Math.min(1, f));
    const strength = Math.min(1, Math.abs(blend) / d.scale.max) * (proven ? 1 : 0.25);
    const third = Math.max(1, Math.floor(order.length / 3)), mean = (list) => list.reduce((t, n) => t + (d.col.slope[n] ?? 0), 0) / list.length;
    stage.style.setProperty("--tone", rgb(blend, d.scale.max));
    stage.style.setProperty("--k", strength.toFixed(3));
    stage.style.setProperty("--low", rgb(mean(order.slice(0, third)) * 2, d.scale.max));
    stage.style.setProperty("--high", rgb(mean(order.slice(-third)) * 2, d.scale.max));
    rail.style.transform = `scaleX(${p.toFixed(4)})`;
    rail.style.opacity = p > 0 && p < 1 ? 1 : 0;
    rail.style.backgroundColor = phase === "climb" && strength > 0.2 ? `rgb(${rgb(blend, d.scale.max)})` : "";
    if (phase !== "climb") { shown = -1; return; }
    if (i !== shown) {                                    // a new height: let the reading settle in
      shown = i;
      $("altBody").animate([{ opacity: 0, transform: "translateY(8px)" }, { opacity: 1, transform: "none" }], { duration: 280, easing: "cubic-bezier(.2,.7,.2,1)" });
    }
    const at = kmOf(d.levels[i]);                          // the number shown is a height that was actually measured
    $("altKm").textContent = Math.round(at);
    const mark = d.content.landmarks.find((m) => Math.abs(m.km - at) < 1.6);
    const layer = d.content.layers.find((l) => at >= l.from_km && at < l.to_km);
    const where = at < 1 ? "Where we live." : mark ? (PHRASE[mark.label] ?? mark.label + ".") : layer ? layer.plain + "." : "";
    const icon = at < 1 ? "home" : mark ? iconFor(mark.label) : null;
    if ($("altWhere").dataset.is !== where) { $("altWhere").dataset.is = where; $("altWhere").innerHTML = (icon ? iconSvg(icon) : "") + where; }
    for (const g of sky.querySelectorAll(".lm")) g.classList.toggle("on", Math.abs(Number(g.dataset.km) - at) < 1.6);
    const rate = $("altRate"), w = d.words;
    if (s == null || v == null) { rate.className = "rate"; rate.textContent = "No measurements here."; $("altLabel").hidden = true; $("altSay").textContent = d.variable.limit_note || ""; return; }
    rate.className = "rate " + (proven ? (s > 0 ? "up" : "down") : "");
    rate.textContent = `${fmt(s)} ${d.variable.trend_units_plain}`;
    $("altLabel").hidden = false; $("altLabel").textContent = d.label(v);
    const subject = w.subject.charAt(0).toUpperCase() + w.subject.slice(1);
    $("altSay").textContent = proven ? `${subject} is ${s > 0 ? w.up : w.down} here. ${d.reason(d.col.reason[i])}`
      : "Too small or too irregular to tell apart from chance. That is not the same as no change.";
  }
  const update = () => { if (!raf) raf = requestAnimationFrame(frame); };
  const stop = () => { if (auto) { cancelAnimationFrame(auto); auto = 0; play.textContent = "Play the ascent"; } };

  window.addEventListener("scroll", () => {
    update();
    clearTimeout(timer);
    timer = setTimeout(() => { if (level >= 0 && !auto) onSettle(level); }, 350);      // let the charts below catch up
  }, { passive: true });
  window.addEventListener("resize", update);
  for (const ev of ["wheel", "touchstart", "keydown"]) window.addEventListener(ev, stop, { passive: true });

  play.addEventListener("click", () => {
    if (auto) { stop(); return; }
    const from = section.offsetTop, to = from + section.offsetHeight - window.innerHeight, t0 = performance.now(), ms = 16000;
    play.textContent = "Pause";
    const tick = (t) => {
      const k = Math.min(1, (t - t0) / ms), eased = k * k * (3 - 2 * k);          // ease in and out
      window.scrollTo(0, from + (to - from) * eased);
      auto = k < 1 ? requestAnimationFrame(tick) : 0;
      if (!auto) play.textContent = "Play the ascent";
    };
    auto = requestAnimationFrame(tick);
  });

  // Drag the column to scrub through the heights.
  const jump = (e) => {
    const d = get(), box = sky.querySelector("svg")?.getBoundingClientRect();
    if (!d || !box) return;
    const km = Math.min(d.scale.maxKm, d.scale.kmAt(((e.clientY - box.top) / box.height) * d.scale.viewHeight));
    window.scrollTo(0, section.offsetTop + (START + (km / d.scale.maxKm) * (END - START)) * (section.offsetHeight - window.innerHeight));
  };
  sky.addEventListener("pointerdown", (e) => { stop(); sky.setPointerCapture(e.pointerId); sky.dataset.drag = "1"; jump(e); });
  sky.addEventListener("pointermove", (e) => { if (sky.dataset.drag) jump(e); });
  for (const ev of ["pointerup", "pointercancel"]) sky.addEventListener(ev, () => { delete sky.dataset.drag; });

  // Arrow keys step one measured height at a time.
  window.addEventListener("keydown", (e) => {
    if (!["ArrowUp", "ArrowDown"].includes(e.key) || e.target.closest?.("input, select, textarea, canvas, summary, button")) return;
    const d = get(), p = progress();
    if (!d || p >= 1 || window.scrollY < section.offsetTop - 10) return;
    const order = d.levels.map((_, n) => n).sort((a, b) => kmOf(d.levels[a]) - kmOf(d.levels[b]));
    const here = level < 0 ? (p < START ? -1 : order.length) : order.indexOf(level), next = here + (e.key === "ArrowUp" ? 1 : -1);
    if (next < 0 || next >= order.length) return;
    e.preventDefault();
    const q = START + (kmOf(d.levels[order[next]]) / d.scale.maxKm) * (END - START);
    window.scrollTo({ top: section.offsetTop + q * (section.offsetHeight - window.innerHeight) + 2, behavior: "smooth" });
  });

  return {
    update, sync: frame,
    toLevel(i) {                                           // jump to one measured height
      const d = get(); if (!d) return;
      const q = START + (kmOf(d.levels[i]) / d.scale.maxKm) * (END - START);
      window.scrollTo({ top: section.offsetTop + q * (section.offsetHeight - window.innerHeight), behavior: "smooth" });
    },
  };
}
