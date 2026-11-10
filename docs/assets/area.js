import { chrome, audienceBanner, attachSearch, getPlace, getState, getJSON, param, fmt, esc, placeURL, compareClass, LEGEND_HTML, tip } from "./common.js";

chrome("area.html");
audienceBanner(document.getElementById("for"));
const $ = (s) => document.getElementById(s);

let ids = (param("ids") || "").split(",").filter(Boolean);
let meta;

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
  history.replaceState(null, "", u);
  meta = meta || await getJSON("data/meta.json");

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
  const tot = {};
  for (const k of ["orgs", "any_opp", "membership", "volunteer", "events", "take_action"]) tot[k] = places.reduce((s, p) => s + p.totals[k], 0);
  const T = meta.types.length, O = meta.opportunities.length;
  const grid = Array.from({ length: T }, (_, i) => Array.from({ length: O }, (_, j) => places.reduce((s, p) => s + p.grid.n[i][j], 0)));

  const states = [...new Set(places.map((p) => p.state))];
  let ref = null, refName = "";
  if (states.length === 1) {
    const s = await getState(states[0]);
    ref = { pop: s.population, grid: s.grid_n, totals: s.totals };
    refName = `the state of ${states[0]}`;
  }

  $("stats").innerHTML = [
    [fmt(places.length), `place${places.length > 1 ? "s" : ""}`],
    [fmt(pop), "residents"],
    [fmt(tot.orgs), "nonprofit organizations"],
    [fmt(tot.any_opp), "list a way to get involved"],
    [pop ? fmt((tot.any_opp / pop) * 10000, 1) : "–", ref ? `per 10,000 residents (state: ${fmt((ref.totals.any_opp / ref.pop) * 10000, 1)})` : "per 10,000 residents"],
  ].map(([b, s]) => `<div class="stat"><b>${b}</b><span>${s}</span></div>`).join("");

  $("grid-note").textContent = ref
    ? `How many organizations of each kind in this area list each opportunity. Shading compares the area with ${refName}, per resident; ▲ more, ▼ fewer.`
    : "How many organizations of each kind in this area list each opportunity. This area spans more than one state, so it isn't shaded against a state.";

  const all = O - 1;
  const order = [...Array(T).keys()].filter((i) => grid[i][all] > 0)
    .sort((a, b) => (meta.types[a] === "Type not identified") - (meta.types[b] === "Type not identified") || grid[b][0] - grid[a][0]);
  const short = { "Any civic opportunity": "Any opportunity" };
  $("grid").innerHTML = `<thead><tr><th>Kind of organization</th>${meta.opportunities.slice(0, all).map((o) => `<th class="num">${short[o] || o}</th>`).join("")}<th class="num">All organizations of this kind</th></tr></thead><tbody>${
    order.map((i) => `<tr><td class="rowhead">${esc(meta.types[i])}</td>${meta.opportunities.slice(0, all).map((o, j) => {
      const n = grid[i][j];
      const rate = ref ? (ref.grid[i][j] / ref.pop) * 10000 : null;
      const [cls, glyph] = ref ? compareClass(n, rate, pop) : ["c-none", ""];
      const t = `${esc(meta.types[i])} · ${esc(o)}: ${fmt(n)} in this area${ref ? `<br>At the state's rate: about ${fmt((rate * pop) / 10000, 1)}` : ""}`;
      return `<td class="cell ${cls}" data-tip="${t}">${fmt(n)}${glyph ? `<span class="glyph">${glyph}</span>` : ""}</td>`;
    }).join("")}<td class="plain">${fmt(grid[i][all])}</td></tr>`).join("")}</tbody>`;
  $("grid").querySelectorAll("td[data-tip]").forEach((td) => {
    td.addEventListener("mousemove", (e) => tip(td.dataset.tip, e));
    td.addEventListener("mouseleave", () => tip(null));
  });
  $("legend").innerHTML = ref ? LEGEND_HTML : "";

  $("parts").innerHTML = `<thead><tr><th>Place</th><th>Residents</th><th>Organizations</th><th>Listing a way to get involved</th><th>Per 10,000 residents</th></tr></thead><tbody>${
    places.map((p) => `<tr><td><a href="${placeURL(p.id)}">${esc(p.name)}</a></td><td>${fmt(p.population)}</td><td>${fmt(p.totals.orgs)}</td><td>${fmt(p.totals.any_opp)}</td><td>${p.population ? fmt((p.totals.any_opp / p.population) * 10000, 1) : "–"}</td></tr>`).join("")
  }</tbody>`;
}

refresh();
