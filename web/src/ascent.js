// The ascent: scroll, and the page rises from the ground to the top of the record.
// The altitude, the reading and the colour of the page follow the scroll position.
// It only reads numbers the pipeline computed; it computes none.
import { color, kmOf, fmt, VERDICT } from "./draw.js";

const PHRASE = { "Mount Everest": "As high as Mount Everest.", "Airliners cruise": "Where airliners cruise.", "Ozone layer": "Inside the ozone layer.",
  "Weather balloons pop": "Where weather balloons pop.", "Highest skydive": "As high as the highest skydive." };
const START = 0.06, END = 0.94;

export function initAscent({ section, stage, play, get, onSettle }) {
  const $ = (id) => document.getElementById(id);
  let raf = 0, timer = 0, auto = 0, level = -1;

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
    stage.style.backgroundColor = phase === "climb" && proven ? color(s, d.scale.max, 0.09) : "transparent";
    $("skyMark")?.setAttribute("transform", `translate(0 ${d.scale.y(km).toFixed(1)})`);
    if (phase !== "climb") return;
    const at = kmOf(d.levels[i]);                          // the number shown is a height that was actually measured
    $("altKm").textContent = Math.round(at);
    const mark = d.content.landmarks.find((m) => Math.abs(m.km - at) < 1.6);
    const layer = d.content.layers.find((l) => at >= l.from_km && at < l.to_km);
    $("altWhere").textContent = at < 1 ? "Where we live." : mark ? (PHRASE[mark.label] ?? mark.label + ".") : layer ? layer.plain + "." : "";
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
      const k = Math.min(1, (t - t0) / ms);
      window.scrollTo(0, from + (to - from) * k);
      auto = k < 1 ? requestAnimationFrame(tick) : 0;
      if (!auto) play.textContent = "Play the ascent";
    };
    auto = requestAnimationFrame(tick);
  });

  return {
    update,
    toLevel(i) {                                           // jump to one measured height
      const d = get(); if (!d) return;
      const q = START + (kmOf(d.levels[i]) / d.scale.maxKm) * (END - START);
      window.scrollTo({ top: section.offsetTop + q * (section.offsetHeight - window.innerHeight), behavior: "smooth" });
    },
  };
}
