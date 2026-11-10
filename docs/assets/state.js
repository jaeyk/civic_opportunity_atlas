import { chrome, audienceBanner, getJSON, getState, param, fmt, pct, ratioText, esc, placeURL, tip, downloadCSV } from "./common.js";

chrome("state.html");
audienceBanner(document.getElementById("for"));
const $ = (s) => document.getElementById(s);

const STATE_NAMES = { AL: "Alabama", AK: "Alaska", AZ: "Arizona", AR: "Arkansas", CA: "California", CO: "Colorado", CT: "Connecticut", DE: "Delaware", DC: "District of Columbia", FL: "Florida", GA: "Georgia", HI: "Hawaii", ID: "Idaho", IL: "Illinois", IN: "Indiana", IA: "Iowa", KS: "Kansas", KY: "Kentucky", LA: "Louisiana", ME: "Maine", MD: "Maryland", MA: "Massachusetts", MI: "Michigan", MN: "Minnesota", MS: "Mississippi", MO: "Missouri", MT: "Montana", NE: "Nebraska", NV: "Nevada", NH: "New Hampshire", NJ: "New Jersey", NM: "New Mexico", NY: "New York", NC: "North Carolina", ND: "North Dakota", OH: "Ohio", OK: "Oklahoma", OR: "Oregon", PA: "Pennsylvania", RI: "Rhode Island", SC: "South Carolina", SD: "South Dakota", TN: "Tennessee", TX: "Texas", UT: "Utah", VT: "Vermont", VA: "Virginia", WA: "Washington", WV: "West Virginia", WI: "Wisconsin", WY: "Wyoming" };
const MEASURE_WORDS = { vs_any: "a way to get involved", vs_membership: "membership", vs_volunteer: "volunteering", vs_events: "public events", vs_take_action: "civic or political action" };
const FEWER = 0.75;

// Three soft bands with the site's evidence rule (pipeline/site_data.py: MIN_COUNT, 0.75 / 1.33):
// a place is shaded only if ~5+ organizations stand behind the comparison, so tiny places
// with a couple of organizations don't dominate the map.
const COUNT_FOR = { vs_any: "any_opp", vs_membership: "membership", vs_volunteer: "volunteer", vs_events: "events", vs_take_action: "take_action" };
const MIN_COUNT = 5;
function band(r, m) {
  const ratio = r ? r[m] : null;
  if (ratio == null) return ["none", "Too few to compare"];
  const n = r[COUNT_FOR[m]] ?? 0, expected = ratio > 0 ? n / ratio : 0;
  if (Math.max(n, expected) < MIN_COUNT) return ["none", "Too few to compare"];
  if (ratio >= 1.33) return ["more-1", "More than similar places"];
  if (ratio <= 0.75) return ["fewer-1", "Fewer than similar places"];
  return ["same", "About the same as similar places"];
}

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

let data = null, all = [], rows = [], sort = { key: "population", dir: -1 };

async function init() {
  const meta = await getJSON("data/meta.json");
  const st = (param("st") || "CA").toUpperCase();   // default: California
  $("st").innerHTML = meta.states.map((s) => `<option value="${s}"${s === st ? " selected" : ""}>${STATE_NAMES[s] || s}</option>`).join("");
  if (param("level") === "zips") $("level").value = "zips";
  if (param("rural")) $("rural").value = param("rural");
  if (param("measure")) $("measure").value = param("measure");
  if (param("below")) { $("measure").value = param("below"); $("only").checked = true; }   // older links
  if (param("only") === "1") $("only").checked = true;
  $("st").addEventListener("change", load);
  $("level").addEventListener("change", () => { buildRows(); update(true); });
  for (const id of ["rural", "measure", "only"]) $(id).addEventListener("change", () => update(id === "measure"));
  $("name").addEventListener("input", () => update(false));
  $("csv").addEventListener("click", exportCSV);
  addEventListener("resize", debounce(() => drawMap(), 200));
  await load();
}

async function load() {
  data = await getState($("st").value);
  buildRows();
  update(true);
}

function buildRows() {
  const level = $("level").value, cols = data.columns;
  all = data[level].map((a) => {
    const r = Object.fromEntries(cols.map((c, i) => [c, a[i]]));
    r.label = level === "zips" ? `${r.name}${r.town ? " · " + r.town : ""}` : r.name;
    return r;
  });
}

// Plain-language takeaway: highest- vs. lowest-poverty quarter of places
function takeaway() {
  const st = STATE_NAMES[$("st").value] || $("st").value;
  const unit = $("level").value === "zips" ? "ZIP codes" : "counties";
  const ok = all.filter((r) => r.POV150 != null && r.rate_any != null && r.population >= 100).sort((a, b) => a.POV150 - b.POV150);
  if (ok.length < 12) return "";
  const q = Math.floor(ok.length / 4);
  const med = (xs) => { const v = xs.map((r) => r.rate_any).sort((a, b) => a - b); return v[Math.floor(v.length / 2)]; };
  const low = med(ok.slice(0, q)), high = med(ok.slice(-q));
  const r = high / low;
  const how = r < 0.85 ? "fewer" : r > 1.15 ? "more" : "about as many";
  return `In ${st}, the quarter of ${unit} with the most poverty have ${how} organizations listing a way to get involved per resident (typically ${fmt(high, 1)} per 10,000) than the quarter with the least poverty (${fmt(low, 1)}).`;
}

function filtered() {
  const rural = $("rural").value, q = $("name").value.trim().toLowerCase();
  return (r) => (!rural || r.rurality === rural) && (!q || r.label.toLowerCase().includes(q) || (r.county || "").toLowerCase().includes(q));
}

function update(redrawMap) {
  const u = new URL(location.href);
  u.searchParams.set("st", $("st").value);
  for (const k of ["level", "rural", "measure"]) {
    const v = $(k).value;
    if (v && !(k === "level" && v === "counties") && !(k === "measure" && v === "vs_any")) u.searchParams.set(k, v); else u.searchParams.delete(k);
  }
  u.searchParams.delete("below");
  if ($("only").checked) u.searchParams.set("only", "1"); else u.searchParams.delete("only");
  history.replaceState(null, "", u);

  const keep = filtered(), m = $("measure").value;
  rows = all.filter((r) => keep(r) && (!$("only").checked || band(r, m)[0] === "fewer-1"));
  const st = $("st").value, t = data.totals;
  $("stats").innerHTML = [
    [fmt(data.population), `residents in ${STATE_NAMES[st] || st}`],
    [fmt(t.orgs), "nonprofit organizations"],
    [fmt(t.any_opp), "list a way to get involved"],
    [fmt((t.any_opp / data.population) * 10000, 1), "per 10,000 residents"],
  ].map(([b, s]) => `<div class="stat"><b>${b}</b><span>${s}</span></div>`).join("");
  $("takeaway").textContent = takeaway();
  $("map-measure").textContent = MEASURE_WORDS[m];
  if (redrawMap) drawMap(); else restyleMap();
  drawTable();
}

// ---- map --------------------------------------------------------------------------
let shapes = { key: null, fc: null, outline: null };

async function drawMap() {
  const st = $("st").value, z = $("level").value === "zips";
  const key = `${st}-${z ? "z" : "c"}`;
  const box = $("map");
  if (shapes.key !== key) {
    box.innerHTML = `<p class="loading">Loading map…</p>`;
    try {
      shapes = { key, fc: await getJSON(`data/g/${key}.json`), outline: z ? await getJSON(`data/g/${st}-c.json`) : null };
    } catch { box.innerHTML = `<p class="muted">Map not available for this state.</p>`; return; }
  }
  const d3 = window.d3;
  const W = Math.max(300, box.clientWidth - 16);
  // Center the projection on the state itself, so Alaska's Aleutians (past 180°) don't wrap around
  const proj = d3.geoMercator().rotate([-d3.geoCentroid(shapes.fc)[0], 0]).fitWidth(W, shapes.fc);
  const path = d3.geoPath(proj);
  let [[, y0], [, y1]] = path.bounds(shapes.fc);
  let H = Math.ceil(y1 - y0) + 4;
  if (H > W * 0.75) {                       // tall states (e.g. Alaska): fit inside a capped box
    H = Math.round(W * 0.75);
    proj.fitSize([W, H], shapes.fc);
  } else {
    proj.translate([proj.translate()[0], proj.translate()[1] - y0 + 2]);
  }
  const byId = Object.fromEntries(all.map((r) => [r.id, r]));
  const places = shapes.fc.features.map((f) => `<path class="place" data-id="${f.properties.id}" d="${path(f)}"></path>`).join("");
  const outline = shapes.outline ? shapes.outline.features.map((f) => `<path class="outline" d="${path(f)}"></path>`).join("") : "";
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Map of ${esc(STATE_NAMES[st] || st)} ${z ? "ZIP codes" : "counties"}">${places}${outline}</svg>`;
  box.querySelectorAll("path.place").forEach((el) => {
    const r = byId[el.dataset.id];
    el.addEventListener("mousemove", (e) => tip(tipHTML(r, el.dataset.id), e));
    el.addEventListener("mouseleave", () => tip(null));
    el.addEventListener("click", () => { location.href = placeURL(el.dataset.id); });
  });
  restyleMap();
}

function tipHTML(r, id) {
  if (!r) return "No data for this area";
  const m = $("measure").value, [, words] = band(r, m);
  return `<b>${esc(r.label)}</b><br>${esc(MEASURE_WORDS[m][0].toUpperCase() + MEASURE_WORDS[m].slice(1))}: ${esc(words.toLowerCase())}${r[m] != null ? ` (${ratioText(r[m])})` : ""}<br>${fmt(r.any_opp)} of ${fmt(r.orgs)} organizations list a way to get involved`;
}

function restyleMap() {
  const box = $("map"), m = $("measure").value, keep = filtered();
  const byId = Object.fromEntries(all.map((r) => [r.id, r]));
  box.querySelectorAll("path.place").forEach((el) => {
    const r = byId[el.dataset.id];
    const [cls] = band(r, m);
    el.setAttribute("class", `place f-${cls}${r && !keep(r) ? " dim" : ""}`);
  });
  $("map-legend").innerHTML = [["fewer-1", "Fewer"], ["same", "About the same"], ["more-1", "More"], ["none", "Too few to compare"]]
    .map(([c, t]) => `<span><i class="m-${c}"></i>${t}</span>`).join("")
    + `<span class="muted">· than similar places, per resident</span>`;
}

// ---- table ------------------------------------------------------------------------
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

function debounce(fn, ms) { let t; return () => { clearTimeout(t); t = setTimeout(fn, ms); }; }

init();
