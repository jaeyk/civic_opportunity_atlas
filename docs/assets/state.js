import { chrome, audienceBanner, getJSON, getState, param, fmt, pct, ratioText, esc, placeURL, tip, downloadCSV } from "./common.js";

chrome("state.html");
audienceBanner(document.getElementById("for"));
const $ = (s) => document.getElementById(s);

const STATE_NAMES = { AL: "Alabama", AK: "Alaska", AZ: "Arizona", AR: "Arkansas", CA: "California", CO: "Colorado", CT: "Connecticut", DE: "Delaware", DC: "District of Columbia", FL: "Florida", GA: "Georgia", HI: "Hawaii", ID: "Idaho", IL: "Illinois", IN: "Indiana", IA: "Iowa", KS: "Kansas", KY: "Kentucky", LA: "Louisiana", ME: "Maine", MD: "Maryland", MA: "Massachusetts", MI: "Michigan", MN: "Minnesota", MS: "Mississippi", MO: "Missouri", MT: "Montana", NE: "Nebraska", NV: "Nevada", NH: "New Hampshire", NJ: "New Jersey", NM: "New Mexico", NY: "New York", NC: "North Carolina", ND: "North Dakota", OH: "Ohio", OK: "Oklahoma", OR: "Oregon", PA: "Pennsylvania", RI: "Rhode Island", SC: "South Carolina", SD: "South Dakota", TN: "Tennessee", TX: "Texas", UT: "Utah", VT: "Vermont", VA: "Virginia", WA: "Washington", WV: "West Virginia", WI: "Wisconsin", WY: "Wyoming" };
const FEWER = 0.75;

const COLS = [
  { key: "label", label: "Place", fmt: (v, r) => `<a href="${placeURL(r.id)}">${esc(v)}</a>` },
  { key: "population", label: "Residents", fmt: (v) => fmt(v) },
  { key: "orgs", label: "Organizations", fmt: (v) => fmt(v) },
  { key: "any_opp", label: "Listing a way to get involved", fmt: (v) => fmt(v) },
  { key: "rate_any", label: "Per 10,000 residents", fmt: (v) => fmt(v, 1) },
  { key: "vs_any", label: "vs. similar places", fmt: ratioText },
  { key: "vs_membership", label: "Membership vs. similar", fmt: ratioText },
  { key: "vs_volunteer", label: "Volunteering vs. similar", fmt: ratioText },
  { key: "vs_events", label: "Events vs. similar", fmt: ratioText },
  { key: "vs_take_action", label: "Civic action vs. similar", fmt: ratioText },
  { key: "POV150", label: "Below 150% poverty", fmt: pct },
  { key: "BROAD", label: "No broadband", fmt: pct },
  { key: "rurality", label: "Area type", fmt: (v) => esc(v ?? "–") },
];

let data = null, rows = [], sort = { key: "population", dir: -1 };

async function init() {
  const meta = await getJSON("data/meta.json");
  const st = (param("st") || "NC").toUpperCase();
  $("st").innerHTML = meta.states.map((s) => `<option value="${s}"${s === st ? " selected" : ""}>${STATE_NAMES[s] || s}</option>`).join("");
  if (param("level") === "zips") $("level").value = "zips";
  for (const k of ["rural", "below"]) if (param(k)) $(k).value = param(k);
  for (const id of ["st", "level", "rural", "below"]) $(id).addEventListener("change", id === "st" ? load : update);
  $("name").addEventListener("input", update);
  $("csv").addEventListener("click", exportCSV);
  await load();
}

async function load() {
  const st = $("st").value;
  const u = new URL(location.href); u.searchParams.set("st", st); history.replaceState(null, "", u);
  data = await getState(st);
  update();
}

function currentRows(ignoreBelow = false) {
  const level = $("level").value, cols = data.columns;
  const all = data[level].map((a) => {
    const r = Object.fromEntries(cols.map((c, i) => [c, a[i]]));
    r.label = level === "zips" ? `${r.name}${r.town ? " · " + r.town : ""}` : r.name;
    return r;
  });
  const rural = $("rural").value, below = ignoreBelow ? "" : $("below").value, q = $("name").value.trim().toLowerCase();
  return all.filter((r) => (!rural || r.rurality === rural)
    && (!below || (r[below] != null && r[below] <= FEWER))
    && (!q || r.label.toLowerCase().includes(q) || (r.county || "").toLowerCase().includes(q)));
}

function update() {
  // keep filters in the URL so a view can be bookmarked or shared
  const u = new URL(location.href);
  for (const k of ["level", "rural", "below"]) { const v = $(k).value; if (v && !(k === "level" && v === "counties")) u.searchParams.set(k, v); else u.searchParams.delete(k); }
  history.replaceState(null, "", u);
  rows = currentRows();
  const level = $("level").value;
  const st = $("st").value;
  const t = data.totals;
  $("stats").innerHTML = [
    [fmt(data.population), `residents in ${STATE_NAMES[st] || st}`],
    [fmt(t.orgs), "nonprofit organizations"],
    [fmt(t.any_opp), "list a way to get involved"],
    [fmt((t.any_opp / data.population) * 10000, 1), "per 10,000 residents"],
  ].map(([b, s]) => `<div class="stat"><b>${b}</b><span>${s}</span></div>`).join("");
  const below = $("below");
  $("flag-note").textContent = below.value
    ? `Red dots: ${below.options[below.selectedIndex].text.toLowerCase()} less common than in similar places.` : "";
  drawScatter(level, currentRows(true));
  drawTable();
}

function drawScatter(level, context) {
  const pts = context.filter((r) => r.POV150 != null && r.rate_any != null);
  // Size the drawing to the container so labels stay readable on phones
  const W = Math.max(300, Math.min(900, $("scatter").clientWidth - 32 || 640));
  const H = Math.round(Math.min(340, Math.max(240, W * 0.55))), L = 44, B = 34, T = 10, R = 12;
  if (!pts.length) { $("scatter").innerHTML = `<p class="muted">No places to show with these filters.</p>`; return; }
  const xs = pts.map((r) => r.POV150), ys = pts.map((r) => r.rate_any).sort((a, b) => a - b);
  const xMax = Math.max(...xs) * 1.05, yMax = ys[Math.floor(ys.length * 0.98)] * 1.1 || 1;  // trim extreme outliers
  const X = (v) => L + (v / xMax) * (W - L - R), Y = (v) => H - B - (Math.min(v, yMax) / yMax) * (H - B - T);
  const below = $("below").value;
  const ticks = (max, n) => Array.from({ length: n + 1 }, (_, i) => (max / n) * i);
  const grid = ticks(yMax, 4).map((v) => `<line class="gridline" x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${L - 6}" y="${Y(v) + 4}" text-anchor="end">${fmt(v, 0)}</text>`).join("")
    + ticks(xMax, 4).map((v) => `<text x="${X(v)}" y="${H - B + 16}" text-anchor="middle">${fmt(v, 0)}%</text>`).join("");
  const r = level === "zips" ? 3 : 4.5;
  pts.sort((a, b) => (below && a[below] != null && a[below] <= FEWER) - (below && b[below] != null && b[below] <= FEWER));
  const dots = pts.map((p) => {
    const flag = below && p[below] != null && p[below] <= FEWER;
    return `<circle class="pt${flag ? " flag" : ""}" cx="${X(p.POV150)}" cy="${Y(p.rate_any)}" r="${r}" data-id="${p.id}"
      data-tip="${esc(p.label)}<br>${fmt(p.rate_any, 1)} per 10,000 · ${pct(p.POV150)} below 150% poverty"></circle>`;
  }).join("");
  $("scatter").innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Scatter plot of civic opportunity per resident against poverty">
    ${grid}<text x="${(W + L) / 2}" y="${H - 2}" text-anchor="middle">Residents below 150% of poverty line</text>
    <text transform="translate(12 ${(H - B) / 2}) rotate(-90)" text-anchor="middle">Per 10,000 residents</text>${dots}</svg>`;
  $("scatter").querySelectorAll("circle").forEach((c) => {
    c.addEventListener("mousemove", (e) => tip(c.dataset.tip, e));
    c.addEventListener("mouseleave", () => tip(null));
    c.addEventListener("click", () => { location.href = placeURL(c.dataset.id); });
    c.style.cursor = "pointer";
  });
}

function drawTable() {
  const { key, dir } = sort;
  rows.sort((a, b) => {
    const x = a[key], y = b[key];
    if (x == null) return 1; if (y == null) return -1;
    return (typeof x === "string" ? x.localeCompare(y) : x - y) * dir;
  });
  const shown = rows.slice(0, 500);
  $("count").textContent = `${fmt(rows.length)} places${rows.length > 500 ? " (showing 500; download for all)" : ""}`;
  $("table").innerHTML = `<thead><tr>${COLS.map((c) =>
    `<th data-key="${c.key}"${c.key === key ? ` aria-sort="${dir > 0 ? "ascending" : "descending"}"` : ""} scope="col">${c.label}</th>`).join("")}</tr></thead>
    <tbody>${shown.map((r) => `<tr>${COLS.map((c) => `<td>${c.fmt(r[c.key], r)}</td>`).join("")}</tr>`).join("")}</tbody>`;
  $("table").querySelectorAll("th").forEach((th) => th.addEventListener("click", () => {
    sort = { key: th.dataset.key, dir: sort.key === th.dataset.key ? -sort.dir : (th.dataset.key === "label" ? 1 : -1) };
    drawTable();
  }));
}

function exportCSV() {
  const keys = ["id", "label", "county", "population", "rurality", "orgs", "any_opp", "rate_any", "pctile_any",
    "vs_any", "vs_membership", "vs_volunteer", "vs_events", "vs_take_action", "POV150", "BROAD", "NOHSDP", "UNEMP", "REMNRTY", "SNGPNT"];
  const header = ["place_id", "place", "county", "residents", "area_type", "organizations", "listing_any_opportunity",
    "per_10k_smoothed", "national_percentile", "vs_similar_any", "vs_similar_membership", "vs_similar_volunteering",
    "vs_similar_events", "vs_similar_civic_action", "pct_below_150_poverty", "pct_no_broadband", "pct_no_hs_diploma",
    "pct_unemployed", "pct_minority", "pct_single_parent"];
  downloadCSV(`civic-opportunity-${$("st").value}-${$("level").value}.csv`, header, rows.map((r) => keys.map((k) => r[k])));
}

init();
