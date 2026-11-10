import { chrome, attachSearch, placeURL, getPlace, getJSON, param, fmt, pct, esc, MEASURES, CONTEXT_LABELS, tip, compareClass, LEGEND_HTML } from "./common.js";

chrome("");
attachSearch(document.getElementById("q"), (r) => { location.href = placeURL(r.id); });

const id = param("id");
const $ = (s) => document.getElementById(s);

async function main() {
  if (!id) { location.href = "index.html"; return; }
  let p, meta;
  try {
    [p, meta] = await Promise.all([getPlace(id), getJSON("data/meta.json")]);
  } catch {
    $("loading").textContent = "We couldn't find that place. Try searching above.";
    return;
  }
  document.title = `${p.name} · Civic Opportunity Atlas`;
  $("title").textContent = p.name;
  const metaBits = [
    p.population ? `${fmt(p.population)} residents` : "Population not available",
    p.rurality ? `${p.rurality === "Metro" ? "Metro area" : p.rurality}` : null,
    p.county ? `In ${esc(p.county)}` : null,
  ].filter(Boolean);
  $("meta").innerHTML = metaBits.map((b) => `<span>${b}</span>`).join("");

  // actions
  $("print").addEventListener("click", () => print());
  $("guide-link").href = `guide.html?id=${p.id}`;
  if (p.county_id) { $("county-link").href = placeURL(p.county_id); $("county-link").textContent = "See the county"; }
  else { $("county-link").href = `state.html?st=${p.state}`; $("county-link").textContent = `All of ${p.state}`; }
  $("area-link").href = `area.html?ids=${p.id}`;
  const url = new URL(placeURL(p.id), location.href).href;
  $("print-url").textContent = url;
  setupShare(url);

  // findings
  $("findings").innerHTML = p.findings.map((f) => `<li>${esc(f)}</li>`).join("");

  renderGrid(p, meta, "n");
  document.querySelectorAll(".toggle button").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll(".toggle button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    renderGrid(p, meta, b.dataset.mode);
  }));

  renderPeers(p);
  renderCards(p);
  $("loading").classList.add("hidden");
  $("content").classList.remove("hidden");
}

function renderGrid(p, meta, mode) {
  const types = meta.types, opps = meta.opportunities;      // last opp = All organizations
  const all = opps.length - 1;
  const hasPeers = p.peers.length > 0 && p.population >= meta.min_pop;
  $("grid-compare-note").textContent = hasPeers
    ? "Shading compares this place with 10 similar places, per resident; ▲ more, ▼ fewer."
    : "This place is too small, or lacks population data, for comparisons with similar places.";
  const order = types.map((t, i) => i).filter((i) => p.grid.n[i][all] > 0 || p.grid.n[i][0] > 0)
    .sort((a, b) => {
      const unA = types[a] === "Type not identified", unB = types[b] === "Type not identified";
      if (unA !== unB) return unA ? 1 : -1;
      return p.grid.n[b][0] - p.grid.n[a][0] || p.grid.n[b][all] - p.grid.n[a][all];
    });
  const short = { "Any civic opportunity": "Any opportunity", "Civic & political action": "Civic & political action" };
  const head = `<thead><tr><th>Kind of organization</th>${opps.slice(0, all).map((o) => `<th class="num">${short[o] || o}</th>`).join("")}<th class="num">All organizations of this kind</th></tr></thead>`;
  if (!order.length) {
    $("grid").innerHTML = `${head}<tbody><tr><td colspan="${opps.length + 1}" class="muted">No organizations found.</td></tr></tbody>`;
    $("legend").innerHTML = "";
    return;
  }
  const val = (n) => (mode === "rate" && p.population ? fmt((n / p.population) * 10000, 1) : fmt(n));
  const body = order.map((i) => {
    const cells = opps.slice(0, all).map((o, j) => {
      const n = p.grid.n[i][j];
      const [cls, glyph] = hasPeers ? compareClass(n, p.grid.peer[i][j], p.population) : ["c-none", ""];
      const peerTxt = hasPeers && p.grid.peer[i][j] != null
        ? `Similar places: about ${fmt((p.grid.peer[i][j] * p.population) / 10000, 1)} for this population` : "";
      const tipTxt = `${esc(types[i])} · ${esc(o)}: ${fmt(n)} here${peerTxt ? "<br>" + peerTxt : ""}`;
      return `<td class="cell ${cls}" data-tip="${tipTxt}">${val(n)}${glyph ? `<span class="glyph" aria-label="${glyph.includes("▲") ? "more" : "fewer"} than similar places">${glyph}</span>` : ""}</td>`;
    }).join("");
    return `<tr><td class="rowhead">${esc(types[i])}</td>${cells}<td class="plain">${val(p.grid.n[i][all])}</td></tr>`;
  }).join("");
  $("grid").innerHTML = head + `<tbody>${body}</tbody>`;
  $("grid").querySelectorAll("td[data-tip]").forEach((td) => {
    td.addEventListener("mousemove", (e) => tip(td.dataset.tip, e));
    td.addEventListener("mouseleave", () => tip(null));
  });
  $("legend").innerHTML = hasPeers ? LEGEND_HTML : "";
}

function renderPeers(p) {
  if (!p.peers.length) { $("peers-section").classList.add("hidden"); return; }
  const rows = MEASURES.map(([k, label]) => {
    const vals = p.peers.map((x) => x.rates[k]).filter((v) => v != null);
    const mine = p.rates[k];
    const max = Math.max(mine ?? 0, ...vals) * 1.08 || 1;
    const X = (v) => `${(v / max) * 100}%`;
    const dots = p.peers.map((x) => x.rates[k] == null ? "" :
      `<span class="dot peer" style="left:${X(x.rates[k])}" title="${esc(x.name)}: ${fmt(x.rates[k], 1)}"></span>`).join("");
    const me = mine == null ? "" : `<span class="dot place" style="left:${X(mine)}" title="${esc(p.name)}: ${fmt(mine, 1)}"></span>`;
    const ratio = p.vs_peers[k];
    const word = ratio == null ? "" : ratio >= 1.33 ? "more than most similar places" : ratio <= 0.75 ? "fewer than most similar places" : "about typical";
    return `<div class="strip-row"><div class="label"><b>${label}</b><small>${fmt(mine, 1)} per 10,000 · ${word}</small></div>
      <div class="track" role="img" aria-label="${label}: this place ${fmt(mine, 1)} per 10,000 residents compared with 10 similar places">
        <span class="axis"></span>${dots}${me}<span class="tick lo">0</span><span class="tick hi">${fmt(max, 0)}</span></div></div>`;
  });
  $("strips").innerHTML = rows.join("");
  $("peer-list").innerHTML = p.peers.map((x) => `<li><a href="${placeURL(x.id)}">${esc(x.name)}</a></li>`).join("");
  if (p.peer_context) {
    $("ctx").innerHTML = `<thead><tr><th>Matched on (share of residents)</th><th>Here</th><th>Similar places (median)</th></tr></thead><tbody>${
      Object.entries(CONTEXT_LABELS).map(([k, l]) => `<tr><td>${l}</td><td>${pct(p.context[k])}</td><td>${pct(p.peer_context[k])}</td></tr>`).join("")
    }</tbody>`;
  }
}

function renderCards(p) {
  const tag = { more: "More common here", fewer: "Less common here", quiet: "Not listed online", small: "Small numbers", similar: "Typical" };
  $("cards").innerHTML = p.observations.map((c) => `
    <article class="card">
      <span class="tag">${tag[c.kind] || ""}</span>
      <h3>${esc(c.title)}</h3>
      <p>${esc(c.text)}</p>
      <p class="q">${esc(c.question)}</p>
      <p class="conf"><span class="conf-dot conf-${c.confidence.level}"></span><b>${c.confidence.level[0].toUpperCase() + c.confidence.level.slice(1)} confidence.</b> ${esc(c.confidence.text)}</p>
    </article>`).join("");
}

function setupShare(url) {
  const d = $("share-dialog");
  $("share-url").textContent = url;
  $("share").addEventListener("click", () => {
    const box = $("qr");
    if (!box.hasChildNodes() && window.QRCode) new window.QRCode(box, { text: url, width: 180, height: 180 });
    d.showModal();
  });
  $("close-share").addEventListener("click", () => d.close());
  $("copy").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(url); $("copy").textContent = "Copied"; } catch { $("copy").textContent = "Copy failed"; }
  });
}

main();
