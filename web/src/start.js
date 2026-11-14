// The guided start: three questions that set the view. No data logic here.
const HEIGHTS = [
  { id: "ground", label: "Near the ground", hint: "about 1 km up", hpa: 925 },
  { id: "weather", label: "In the weather layer", hint: "about 8 km up", hpa: 300 },
  { id: "calm", label: "In the calm layer above", hint: "about 32 km up", hpa: 10 },
  { id: "all", label: "Show me every height", hint: "", hpa: null },
];

export function initStart(root, manifest, onGo) {
  const variables = [];
  for (const d of manifest.datasets) for (const v of d.variables) if (!variables.some((x) => x.id === v.id)) variables.push(v);
  const pick = { where: "global", height: "all", what: variables[0].id };
  const group = (key, title, items) => `
    <fieldset><legend>${title}</legend>
      ${items.map((it) => `<button type="button" class="chip" data-key="${key}" data-value="${it.id}" aria-pressed="${pick[key] === it.id}">
        ${it.label}${it.hint ? `<small>${it.hint}</small>` : ""}</button>`).join("")}
    </fieldset>`;
  root.innerHTML = `
    <h2>What do you want to investigate?</h2>
    ${group("where", "Where?", manifest.regions)}
    ${group("height", "How high?", HEIGHTS)}
    ${group("what", "What?", variables.map((v) => ({ id: v.id, label: v.label })))}
    <div class="go"><button type="button" id="startGo">Show me</button>
      <button type="button" class="link" id="startSkip">Skip, let me explore</button></div>`;
  root.addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    pick[chip.dataset.key] = chip.dataset.value;
    root.querySelectorAll(`.chip[data-key="${chip.dataset.key}"]`).forEach((c) => c.setAttribute("aria-pressed", c === chip));
  });
  root.querySelector("#startGo").addEventListener("click", () => onGo({
    region: pick.where, variable: pick.what, hpa: HEIGHTS.find((x) => x.id === pick.height).hpa,
  }));
  root.querySelector("#startSkip").addEventListener("click", () => onGo(null));
}
