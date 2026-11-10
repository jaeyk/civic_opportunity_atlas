// Shared helpers: header/footer, search, data loading, formatting.

export const LINKS = {
  paper: "https://www.nature.com/articles/s41597-025-05353-6",
  dataverse: "https://doi.org/10.7910/DVN/IRCA7C",
  github: "https://github.com/snfagora/american_civic_opportunity_datasets",
  project: "https://snfagora.github.io/modern_agora_dashboard/#about",
  nhb: "https://www.nature.com/articles/s41562-023-01743-1",
  maintainer: "https://jaeyk.github.io/",
  email: "jaekim@unc.edu",
};

export const MEASURES = [
  ["any_opp", "Any way to get involved"],
  ["membership", "Membership"],
  ["volunteer", "Volunteering"],
  ["events", "Public events"],
  ["take_action", "Civic & political action"],
];

export const CONTEXT_LABELS = {
  POV150: "Below 150% of poverty line",
  BROAD: "No broadband",
  NOHSDP: "No high school diploma",
  UNEMP: "Unemployed",
  REMNRTY: "Racial/ethnic minority",
  SNGPNT: "Single-parent households",
};

export const AUDIENCES = {
  foundation: {
    label: "For foundations",
    text: "Compare places with others like them, see where kinds of opportunity are less common, and export the list for your team.",
  },
  university: {
    label: "For universities",
    text: "Add the ZIP codes around your campus to see which kinds of organizations offer which opportunities nearby.",
  },
  government: {
    label: "For state and local governments",
    text: "See every county and ZIP code in your state, compared with similar places and with local conditions. Export for your GIS or planning team.",
  },
  organizer: {
    label: "For organizers",
    text: "Look up your place, then print the profile or share its link and QR code to bring others into the conversation.",
  },
};

const cache = new Map();
export async function getJSON(path) {
  if (!cache.has(path)) {
    cache.set(path, fetch(path).then((r) => {
      if (!r.ok) throw new Error(`${r.status} ${path}`);
      return r.json();
    }));
  }
  return cache.get(path);
}
export const getPlace = (id) => getJSON(`data/p/${id}.json`);
export const getState = (st) => getJSON(`data/s/${st}.json`);

export const fmt = (n, d = 0) =>
  n == null || Number.isNaN(n) ? "–" : Number(n).toLocaleString("en-US", { maximumFractionDigits: d, minimumFractionDigits: d });
export const pct = (n) => (n == null ? "–" : `${fmt(n, 0)}%`);
// Infinity: some here, none expected from similar places
export const ratioText = (r) => (r == null ? "–" : !Number.isFinite(r) ? "more (0 expected)" : `${r.toFixed(r >= 10 ? 0 : 1)}×`);
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const param = (k) => new URLSearchParams(location.search).get(k);

// ---- header / footer -----------------------------------------------------------
export function chrome(current) {
  const nav = [
    ["index.html", "Home"], ["state.html", "Explore a state"], ["area.html", "Combine places"], ["about.html", "About the data"],
  ];
  document.querySelector("header.site-header").innerHTML = `
    <div class="wrap">
      <a class="brand" href="index.html">Civic Opportunity Atlas <span>· MapAgora</span></a>
      <nav class="nav" aria-label="Main">${nav.map(([h, t]) => `<a href="${h}"${h === current ? ' aria-current="page"' : ""}>${t}</a>`).join("")}</nav>
    </div>`;
  document.querySelector("footer.site-footer").innerHTML = `
    <div class="wrap cols">
      <div>
        <h3>Civic Opportunity Atlas</h3>
        <p>Built on the MapAgora datasets from the SNF Agora Institute at Johns Hopkins University.</p>
        <p>Maintained by <a href="${LINKS.maintainer}">Jae Yeon Kim</a>, UNC Chapel Hill · <a href="mailto:${LINKS.email}">${LINKS.email}</a></p>
      </div>
      <div>
        <h3>Questions about the data?</h3>
        <ul>
          <li><a href="${LINKS.paper}">Data paper (Scientific Data, 2025)</a></li>
          <li><a href="${LINKS.dataverse}">Harvard Dataverse</a> · <a href="${LINKS.github}">GitHub</a></li>
          <li><a href="${LINKS.project}">Mapping the Modern Agora project</a></li>
        </ul>
      </div>
      <div>
        <h3>On this site</h3>
        <ul>
          <li><a href="about.html">About the data and its limits</a></li>
          <li><a href="about.html#sources">Data sources</a></li>
          <li><a href="about.html#cite">How to cite</a></li>
        </ul>
      </div>
    </div>`;
}

export function audienceBanner(el) {
  const a = AUDIENCES[param("for")];
  if (!a || !el) return;
  el.innerHTML = `<b>${a.label}</b>${a.text}`;
  el.classList.remove("hidden");
}

// ---- search ----------------------------------------------------------------------
let index = null;
async function loadIndex() {
  if (!index) index = (await getJSON("data/search.json")).map(([id, label, st]) => ({ id, label, st, low: label.toLowerCase() }));
  return index;
}

export function search(q, limit = 8) {
  if (!index) return [];
  q = q.trim().toLowerCase();
  if (!q) return [];
  const zip = /^\d{3,5}$/.test(q);
  const hits = [];
  for (const r of index) {
    if (zip ? r.id.startsWith("z" + q) : r.low.includes(q)) {
      const starts = zip || r.low.startsWith(q) || r.low.includes("· " + q);
      hits.push([starts ? 0 : 1, r.id[0] === "c" ? 0 : 1, r.label.length, r]);
      if (hits.length > 400) break;
    }
  }
  hits.sort((a, b) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2]);
  return hits.slice(0, limit).map((h) => h[3]);
}

// Attach typeahead to an <input> inside .search. onPick(record) is called on choice.
export function attachSearch(input, onPick) {
  const box = input.closest(".search");
  const list = document.createElement("ul");
  list.setAttribute("role", "listbox");
  list.className = "hidden";
  box.appendChild(list);
  let results = [], active = -1;

  const render = () => {
    if (!results.length) { list.classList.add("hidden"); return; }
    list.innerHTML = results.map((r, i) =>
      `<li><button type="button" role="option" data-i="${i}" class="${i === active ? "active" : ""}">${esc(r.label)}<span class="kind">${r.id[0] === "c" ? "County" : "ZIP code"}</span></button></li>`).join("");
    list.classList.remove("hidden");
  };
  input.addEventListener("focus", loadIndex, { once: true });
  input.addEventListener("input", async () => {
    await loadIndex();
    results = search(input.value);
    active = results.length ? 0 : -1;
    render();
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { active = Math.min(active + 1, results.length - 1); render(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { active = Math.max(active - 1, 0); render(); e.preventDefault(); }
    else if (e.key === "Enter" && results[active]) { e.preventDefault(); pick(results[active]); }
    else if (e.key === "Escape") { results = []; render(); }
  });
  list.addEventListener("mousedown", (e) => {
    const b = e.target.closest("button[data-i]");
    if (b) { e.preventDefault(); pick(results[+b.dataset.i]); }
  });
  input.addEventListener("blur", () => setTimeout(() => list.classList.add("hidden"), 150));
  function pick(r) { results = []; render(); onPick(r); }
}

export const placeURL = (id) => `place.html?id=${id}`;

// ---- organization-type picker ----------------------------------------------------
// A dropdown of checkboxes: "All kinds" (the default) or any mix of types, whose
// counts are added together. Selection is kept in the URL as ?types=Youth,Education.
export const UNTYPED = "Type not identified";
export function typesFromURL(types) {
  const want = (param("types") || "").split(",").filter(Boolean);
  return types.map((t, i) => [t, i]).filter(([t]) => t !== UNTYPED && want.includes(t)).map(([, i]) => i);
}
export function typesToURL(u, types, picked) {
  if (picked.length) u.searchParams.set("types", picked.map((i) => types[i]).join(",")); else u.searchParams.delete("types");
}
export function typePicker(el, types, picked, onChange) {
  const opts = types.map((t, i) => [t, i]).filter(([t]) => t !== UNTYPED);
  el.classList.add("type-picker");
  el.innerHTML = `<summary></summary><div class="type-menu" role="group" aria-label="Kinds of organization">
    <label><input type="checkbox" data-all> All kinds (total)</label><hr>
    ${opts.map(([t, i]) => `<label><input type="checkbox" value="${i}"> ${esc(t)}</label>`).join("")}
    <p class="muted">Pick one kind, or several to add them together.</p></div>`;
  const all = el.querySelector("[data-all]"), boxes = [...el.querySelectorAll("input[value]")];
  const sync = () => {
    all.checked = picked.length === 0;
    boxes.forEach((b) => { b.checked = picked.includes(+b.value); });
    el.querySelector("summary").textContent = typeLabel(types, picked);
  };
  all.addEventListener("change", () => { picked = []; sync(); onChange(picked); });
  boxes.forEach((b) => b.addEventListener("change", () => {
    picked = boxes.filter((x) => x.checked).map((x) => +x.value);
    sync(); onChange(picked);
  }));
  document.addEventListener("click", (e) => { if (!el.contains(e.target)) el.open = false; });
  sync();
}
export function typeLabel(types, picked) {
  if (!picked.length) return "All kinds (total)";
  if (picked.length <= 2) return picked.map((i) => types[i]).join(" + ");
  return `${picked.length} kinds combined`;
}
// "youth organizations", "youth and education organizations", "organizations of 3 kinds"
export function typeNoun(meta, picked) {
  if (!picked.length) return "organizations";
  const ph = picked.map((i) => meta.type_phrases[meta.types[i]] || meta.types[i].toLowerCase());
  if (ph.length === 1) return `${ph[0]} organizations`;
  if (ph.length === 2) return `${ph[0]} and ${ph[1]} organizations`;
  return `organizations of the ${ph.length} chosen kinds`;
}
// ---- comparison shading ------------------------------------------------------------
// A count here vs. the count expected from a comparison rate (per 10,000) for this
// population. Same rule as pipeline/site_data.py: needs ~5+ organizations on one side.
export const MIN_COUNT = 5;
export function compareClass(n, rate, pop) {
  if (rate == null || !pop) return ["c-none", ""];
  const expected = (rate * pop) / 10000;
  if (Math.max(n, expected) < MIN_COUNT) return ["c-none", ""];
  const r = expected > 0 ? n / expected : Infinity;
  if (r >= 2) return ["c-more-2", "▲▲"];
  if (r >= 1.33) return ["c-more-1", "▲"];
  if (r > 0.75) return ["c-same", ""];
  if (r > 0.5) return ["c-fewer-1", "▼"];
  return ["c-fewer-2", "▼▼"];
}
export const LEGEND_HTML = `
  <span><i class="c-fewer-2"></i>Far fewer ▼▼</span><span><i class="c-fewer-1"></i>Fewer ▼</span>
  <span><i class="c-same"></i>About the same</span><span><i class="c-more-1"></i>More ▲</span>
  <span><i class="c-more-2"></i>Far more ▲▲</span><span><i class="c-none"></i>Too few to compare</span>`;

// ---- small tooltip ---------------------------------------------------------------
let tipEl;
export function tip(html, e) {
  if (!tipEl) { tipEl = document.createElement("div"); tipEl.className = "tip hidden"; document.body.appendChild(tipEl); }
  if (!html) { tipEl.classList.add("hidden"); return; }
  tipEl.innerHTML = html;
  tipEl.classList.remove("hidden");
  const x = Math.min(e.clientX + 12, innerWidth - tipEl.offsetWidth - 8);
  const y = Math.max(e.clientY - tipEl.offsetHeight - 12, 8);
  tipEl.style.left = `${x}px`; tipEl.style.top = `${y}px`;
}

export function downloadCSV(name, header, rows) {
  const q = (v) => (v == null ? "" : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v));
  const csv = [header, ...rows].map((r) => r.map(q).join(",")).join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}
