// The "ask the data" box. It sends the question to /api/ask, where the agent harness
// answers from the published NASA results. Nothing here writes or checks an answer.
const TRY = ["Is the Arctic warming?", "What is happening 30 km up?", "Did the 2022 volcano change the trend at 32 km?",
  "Do the two NASA datasets agree at 41 km?", "Can I trust these numbers?"];
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

export async function initAsk({ section, form, input, button, out, tryBox, note, onShow }) {
  let info;
  try {
    const r = await fetch("api/ask");
    if (!r.ok) throw new Error(r.status);
    info = await r.json();
  } catch { section.hidden = true; return; }                 // a plain file host has no ask service
  const byRule = info.model.startsWith("rules");
  note.textContent = byRule ? "No AI model is connected right now, so answers are picked by simple rules from the same data."
    : `Sentences written by ${info.model}. It can only read these NASA results, and its numbers are checked before you see them.`;
  for (const q of TRY) { const b = el("button", "chip", q); b.type = "button"; tryBox.append(b); }
  tryBox.addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { input.value = b.textContent; form.requestSubmit(); } });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const question = input.value.trim();
    if (!question) return;
    button.disabled = true; button.textContent = "Reading…";
    out.hidden = false; out.replaceChildren(el("p", "small", "Reading NASA's records…"));
    let res;
    try {
      const r = await fetch("api/ask", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ question }) });
      res = await r.json();
    } catch { res = { error: "The answer service could not be reached. Try again in a moment." }; }
    button.disabled = false; button.textContent = "Ask";
    out.replaceChildren();
    if (res.error) { out.append(el("p", "a", res.error)); return; }
    for (const para of res.answer.split(/\n\n+/)) out.append(el("p", "a", para));
    if (!res.answered) return;
    const badges = el("div", "badges");
    if (res.checked) badges.append(el("span", "badge ok", "✓ Every number traced to NASA data"));
    badges.append(el("span", "badge", res.model.startsWith("rules") ? "Answered by rule, no AI model" : `Written by ${res.model}`));
    out.append(badges);
    if (res.sources.length) {
      const d = el("details"), ul = el("ul");
      d.append(el("summary", null, `Read from ${res.sources.length} file${res.sources.length > 1 ? "s" : ""}`));
      for (const s of res.sources) {
        const li = el("li"), path = s.file.replace(/^web\//, "");
        if (path.includes("*")) li.textContent = `${s.product}: ${path}`;
        else { const a = el("a", null, path); a.href = path; a.target = "_blank"; a.rel = "noopener"; li.append(`${s.product}: `, a); }
        ul.append(li);
      }
      d.append(ul); out.append(d);
    }
    for (const n of res.notes) out.append(el("p", "small", n));
    const step = res.steps.find((s) => s.ok && (s.args.where != null || s.args.km != null || s.args.hpa != null || s.args.what != null));
    if (step) {
      const go = el("div", "go"), b = el("button", "ghost", "Show this on the charts");
      b.type = "button"; b.addEventListener("click", () => onShow(step.args));
      go.append(b); out.append(go);
    }
  });
}
