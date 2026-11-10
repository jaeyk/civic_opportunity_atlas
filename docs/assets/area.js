import { chrome, audienceBanner, attachSearch, getPlace, getState, getJSON, param, fmt, esc, placeURL, compareClass, LEGEND_HTML, tip,
  UNTYPED, typePicker, typesFromURL, typesToURL, typeLabel, typeNoun } from "./common.js";

chrome("area.html");
audienceBanner(document.getElementById("for"));
const $ = (s) => document.getElementById(s);

let ids = (param("ids") || "").split(",").filter(Boolean);
let meta, picked = null;   // picked: indices into meta.types; empty = all kinds (the total)

attachSearch($("q"), (r) => {
  if (!ids.includes(r.id)) ids.push(r.id);
  $("q").value = "";
  refresh();
});
$("print").addEventListener("click", () => print());
$("copy").addEventListener("click", async () => {
  try { await navigator.clipboard.writeText(location.href); $("copy").textContent = "Link copied"; } catch { $("copy").textContent = "Copy failed"; }
});

async function refresh() {
  const u = new URL(location.href);
  if (ids.length) u.searchParams.set("ids", ids.join(",")); else u.searchParams.delete("ids");
  meta = meta || await getJSON("data/meta.json");
  if (picked === null) {
    picked = typesFromURL(meta.types);
    typePicker($("types"), meta.types, picked, (p) => { picked = p; refresh(); });
  }
  typesToURL(u, meta.types, picked);
  history.replaceState(null, "", u);

  const places = (await Promise.all(ids.map((id) => getPlace(id).catch(() => null)))).filter(Boolean);
  $("chips").innerHTML = places.map((p) =>
    `<span class="chip">${esc(p.name)}<button type="button" aria-label="Remove ${esc(p.name)}" data-id="${p.id}">×</button></span>`).join("");
  $("chips").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => { ids = ids.filter((x) => x !== b.dataset.id); refresh(); }));

  const levels = new Set(places.map((p) => p.level));
  const counties = new Set(places.filter((p) => p.level === "county").map((p) => p.id));
  const overlap = places.some((p) => p.level === "zcta" && counties.has(p.county_id));
  $("warn").textContent = overlap
    ? "Some ZIP codes here are inside a county you also added, so their organizations are counted twice. Use either the county or its ZIP codes."
    : levels.size > 1 ? "This area mixes counties and ZIP codes. That's fine as long as they don't overlap." : "";

  $("empty").classList.toggle("hidden", places.length > 0);
  $("content").classList.toggle("hidden", places.length === 0);
  if (!places.length) return;

  // combine
  const pop = places.reduce((s, p) => s + (p.population || 0), 0);
  const T = meta.types.length, O = meta.opportunities.length;
  const grid = Array.from({ length: T }, (_, i) => Array.from({ length: O }, (_, j) => places.reduce((s, p) => s + p.grid.n[i][j], 0)));
  const ANY = meta.opportunities.indexOf("Any civic opportunity"), ALL = meta.opportunities.indexOf("All organizations");
  // Totals for one place (or the whole area): all organizations, or only the chosen kinds
  const kindTotals = (g, totals) => picked.length
    ? { orgs: picked.reduce((s, i) => s + g[i][ALL], 0), any_opp: picked.reduce((s, i) => s + g[i][ANY], 0) }
    : totals;
  const sumTotals = {};
  for (const k of ["orgs", "any_opp"]) sumTotals[k] = places.reduce((s, p) => s + p.totals[k], 0);
  const tot = kindTotals(grid, sumTotals);
  const noun = typeNoun(meta, picked);

  const note = $("type-note");
  note.classList.toggle("hidden", !picked.length);
  if (picked.length) {
    const share = sumTotals.orgs ? grid[meta.types.indexOf(UNTYPED)][ALL] / sumTotals.orgs : 0;
    note.textContent = `Showing ${typeLabel(meta.types, picked)}. In this area, ${Math.round(share * 100)}% of organizations have no identified type, so counts by kind leave some out.`;
  }

  const states = [...new Set(places.map((p) => p.state))];
  let ref = null, refName = "";
  if (states.length === 1) {
    const s = await getState(states[0]);
    ref = { pop: s.population, grid: s.grid_n, totals: kindTotals(s.grid_n, s.totals) };
    refName = `the state of ${states[0]}`;
  }

  $("stats").innerHTML = [
    [fmt(places.length), `place${places.length > 1 ? "s" : ""}`],
    [fmt(pop), "residents"],
    [fmt(tot.orgs), picked.length ? noun : "nonprofit organizations"],
    [fmt(tot.any_opp), "list a way to get involved"],
    [pop ? fmt((tot.any_opp / pop) * 10000, 1) : "–", ref ? `per 10,000 residents (state: ${fmt((ref.totals.any_opp / ref.pop) * 10000, 1)})` : "per 10,000 residents"],
  ].map(([b, s]) => `<div class="stat"><b>${b}</b><span>${s}</span></div>`).join("");

  $("grid-note").textContent = ref
    ? `How many ${picked.length > 1 ? "organizations of each chosen kind" : picked.length ? noun : "organizations of each kind"} in this area list each opportunity. Shading compares the area with ${refName}, per resident; ▲ more, ▼ fewer.`
    : `How many ${picked.length ? noun : "organizations of each kind"} in this area list each opportunity. This area spans more than one state, so it isn't shaded against a state.`;

  const all = O - 1;
  const order = [...Array(T).keys()].filter((i) => (picked.length ? picked.includes(i) : grid[i][all] > 0))
    .sort((a, b) => (meta.types[a] === UNTYPED) - (meta.types[b] === UNTYPED) || grid[b][0] - grid[a][0]);
  // Several kinds picked: add a row for them together
  const rows = order.map((i) => ({ name: meta.types[i], n: grid[i], ref: ref && ref.grid[i] }));
  if (picked.length > 1) {
    const add = (g) => g[0].map((_, j) => picked.reduce((s, i) => s + g[i][j], 0));
    rows.push({ name: "Chosen kinds together", n: add(grid), ref: ref && add(ref.grid), total: true });
  }
  const short = { "Any civic opportunity": "Any opportunity" };
  $("grid").innerHTML = `<thead><tr><th>Kind of organization</th>${meta.opportunities.slice(0, all).map((o) => `<th class="num">${short[o] || o}</th>`).join("")}<th class="num">All organizations of this kind</th></tr></thead><tbody>${
    rows.map((row) => `<tr><td class="rowhead">${row.total ? `<b>${esc(row.name)}</b>` : esc(row.name)}</td>${meta.opportunities.slice(0, all).map((o, j) => {
      const n = row.n[j];
      const rate = ref ? (row.ref[j] / ref.pop) * 10000 : null;
      const [cls, glyph] = ref ? compareClass(n, rate, pop) : ["c-none", ""];
      const t = `${esc(row.name)} · ${esc(o)}: ${fmt(n)} in this area${ref ? `<br>At the state's rate: about ${fmt((rate * pop) / 10000, 1)}` : ""}`;
      return `<td class="cell ${cls}" data-tip="${t}">${fmt(n)}${glyph ? `<span class="glyph">${glyph}</span>` : ""}</td>`;
    }).join("")}<td class="plain">${fmt(row.n[all])}</td></tr>`).join("")}</tbody>`;
  $("grid").querySelectorAll("td[data-tip]").forEach((td) => {
    td.addEventListener("mousemove", (e) => tip(td.dataset.tip, e));
    td.addEventListener("mouseleave", () => tip(null));
  });
  $("legend").innerHTML = ref ? LEGEND_HTML : "";

  $("parts").innerHTML = `<thead><tr><th>Place</th><th>Residents</th><th>${picked.length ? "Organizations of the chosen kinds" : "Organizations"}</th><th>Listing a way to get involved</th><th>Per 10,000 residents</th></tr></thead><tbody>${
    places.map((p) => { const t = kindTotals(p.grid.n, p.totals); return `<tr><td><a href="${placeURL(p.id)}">${esc(p.name)}</a></td><td>${fmt(p.population)}</td><td>${fmt(t.orgs)}</td><td>${fmt(t.any_opp)}</td><td>${p.population ? fmt((t.any_opp / p.population) * 10000, 1) : "–"}</td></tr>`; }).join("")
  }</tbody>`;
}

refresh();
