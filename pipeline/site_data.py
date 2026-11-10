"""Write the static site's data files from the pipeline tables.

    .venv/bin/python -m pipeline.site_data      (after `python -m pipeline.build`)

Writes to docs/data/:
    p/{id}.json        one file per place (id = c + county FIPS, or z + ZIP)
    s/{ST}.json        one file per state: county and ZIP rows for the
                       jurisdiction view, plus state totals for area comparisons
    search.json        [id, label, state] for every place
    meta.json          build date, labels, national totals

Findings and observation cards (each with a discussion question) are written
here, in Python, so the rules about what the data can and can't claim live in one
tested place. See CLAUDE.md: never call a gap a "need", never suggest
partners, never claim anything "worked".
"""

import json
import math
import shutil
import time
from datetime import date

import numpy as np
import pandas as pd

from . import config as C
from .providers import ALL_ORGS, UNCLASSIFIED

SITE = C.ROOT / "docs"
DATA = SITE / "data"

TYPES = [*C.ORG_TYPES.values(), UNCLASSIFIED]
OPPS = ["Any civic opportunity", "Membership", "Volunteering", "Public events",
        "Civic & political action", ALL_ORGS]
# place-table column stem -> (label, lower-case phrase used in sentences)
MEASURES = {
    "any_opp": ("Any civic opportunity", "at least one way to get involved"),
    "membership": ("Membership", "membership"),
    "volunteer": ("Volunteering", "volunteering"),
    "events": ("Public events", "public events"),
    "take_action": ("Civic & political action", "civic or political action"),
}
CONTEXT = list(C.CONTEXT)

# Thresholds for wording comparisons. Totals are smoothed and steadier, so
# they get tighter bands than single organization types.
TOTAL_FEWER, TOTAL_MORE = 0.75, 1.33
TYPE_FEWER, TYPE_MORE = 0.5, 2.0
MIN_COUNT = 5         # a comparison needs at least ~5 organizations on one side

OPP_KEY = {v[0]: k for k, v in MEASURES.items()}
QUESTION_NOUN = {
    "membership": "groups to join",
    "volunteer": "ways to volunteer",
    "events": "public events",
    "take_action": "ways to take civic or political action",
    "any_opp": "ways to get involved",
}


# How each organization type reads inside a sentence ("... foundation organizations ...")
TYPE_PHRASE = {
    "Religious": "religious", "Social & Fraternal": "social and fraternal",
    "Foundations": "foundation", "Hobby & Sports": "hobby and sports",
    "Education": "education", "Professional": "professional", "Community": "community",
    "Arts & Cultural": "arts and cultural", "Youth": "youth", "Healthcare": "health care",
    "Economic": "economic development", "Unions": "union", "Housing": "housing",
    "Research & Think Tank": "research and think tank", "Political": "political",
}


def _tp(typ, cap=False):
    """Organization type as it reads in a sentence; cap=True for sentence starts."""
    t = TYPE_PHRASE.get(typ, typ.lower())
    return t[0].upper() + t[1:] if cap else t


def _count_phrase(n, kind):
    """'No youth organizations', '1 youth organization', '12 youth organizations'."""
    kind = f"{kind} " if kind else ""
    if n == 0:
        return f"no {kind}organizations".capitalize() if kind else "no organizations"
    return f"{_fmt(n)} {kind}organization{'s' if n != 1 else ''}"


def _r(x, nd=2):
    """Round for JSON; NaN -> None."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return round(float(x), nd)


def _fmt(n):
    return f"{int(round(n)):,}"


def _pid(level, raw):
    return ("c" if level == "county" else "z") + raw


def _towns() -> pd.Series:
    """Most common mailing city per ZCTA, title-cased: a readable name for ZIP codes."""
    o = pd.read_parquet(C.ORGS, columns=["ZCTA", "city"]).dropna()
    town = o.groupby("ZCTA")["city"].agg(lambda s: s.value_counts().index[0])
    return town.str.title()


def _confidence(n_orgs, typed_share):
    """How much weight a statement can bear, in plain words."""
    untyped = 1 - typed_share if typed_share == typed_share else 1
    level = "higher" if n_orgs >= 20 and untyped < 0.4 else "moderate" if n_orgs >= 5 else "low"
    return {
        "level": level,
        "text": (f"Based on {_fmt(n_orgs)} organization{'s' if n_orgs != 1 else ''} here; "
                 f"{round(untyped * 100)}% of all organizations here have no identified type."),
    }


# ---- findings and observations --------------------------------------------------

def findings(p: dict) -> list:
    """Three to five plain-language sentences that lead the place page."""
    t, name = p["totals"], p["short_name"]
    out = []
    if t["orgs"] == 0:
        return [f"MapAgora found no nonprofit organizations with a mailing address in {name}."]
    share = t["any_opp"] / t["orgs"]
    orgs = f"{_fmt(t['orgs'])} nonprofit organization{'s' if t['orgs'] != 1 else ''}"
    if t["any_opp"] == 0:
        none = "It does not list" if t["orgs"] == 1 else "None of them list"
        out.append(f"{name} has {orgs}. {none} a way to get involved on a website (membership, "
                   "volunteering, public events, or civic and political action).")
        return out
    out.append(
        f"{name} has {orgs}. {_fmt(t['any_opp'])} of them ({round(share * 100)}%) list at least "
        "one way to get involved on their websites: membership, volunteering, public events, or "
        "civic and political action.")
    opp4 = {k: t[k] for k in ["membership", "volunteer", "events", "take_action"]}
    top = max(opp4, key=opp4.get)
    out.append(f"The most common is {MEASURES[top][1]}, listed by {_fmt(opp4[top])} organizations.")

    g = p["grid"]
    col = OPPS.index("Any civic opportunity")
    typed = [(TYPES[i], row[col]) for i, row in enumerate(g["n"]) if TYPES[i] != UNCLASSIFIED]
    typed_total = sum(n for _, n in typed)
    if typed_total >= 5:
        lead, lead_n = max(typed, key=lambda x: x[1])
        out.append(f"{_tp(lead, True)} organizations are the largest group offering opportunities "
                   f"({round(lead_n / typed_total * 100)}% of those with an identified type).")

    ratio = p["vs_peers"].get("any_opp")
    if ratio is not None and t["any_opp"] >= MIN_COUNT:
        word = ("more" if ratio >= TOTAL_MORE else "fewer" if ratio <= TOTAL_FEWER
                else "about as many")
        out.append(f"Compared with 10 similar places, {name} has {word} organizations offering "
                   "opportunities per resident.")
    untyped_n = g["n"][TYPES.index(UNCLASSIFIED)][col]
    if untyped_n and untyped_n / t["any_opp"] >= 0.25:
        out.append(f"{round(untyped_n / t['any_opp'] * 100)}% of the organizations offering "
                   "opportunities have no identified type, so the breakdown by type is partial.")
    return out


def _evidence(count) -> float:
    """0-1 weight: how many organizations stand behind a comparison."""
    return min(1.0, count / 20)


def observations(p: dict) -> list:
    """Observation cards: a comparison, how confident we can be, and a question.

    Only comparisons the data supports:
    - every comparison needs at least MIN_COUNT organizations on one side
      (here, or expected from similar places of this size);
    - cards are ranked by size of difference x amount of evidence, and
      whole-place comparisons are preferred to single organization types;
    - wording avoids "need", "gap to fill", "partners", and "worked".
    """
    cards = []
    t, name, pop = p["totals"], p["short_name"], p["population"]
    comparable = bool(p["vs_peers"]) and pop and pop >= C.MIN_POP

    if comparable:
        # 1. Each opportunity overall vs. similar places (smoothed rates)
        for key, (label, phrase) in MEASURES.items():
            ratio = p["vs_peers"].get(key)
            if key == "any_opp" or ratio is None:
                continue
            expected = t[key] / ratio if ratio > 0 else 0
            support = max(t[key], expected)
            if support < MIN_COUNT:
                continue
            noun = QUESTION_NOUN[key]
            if ratio <= TOTAL_FEWER:
                cards.append({
                    "kind": "fewer", "score": 1.2 * abs(math.log(ratio)) * _evidence(support),
                    "title": f"Fewer organizations list {phrase}",
                    "text": (f"Per resident, fewer organizations in {name} list {phrase} on their "
                             f"websites than in 10 similar places (about {round(ratio * 100)}% "
                             "of the typical level)."),
                    "confidence": _confidence(round(support), p["typed_share"]),
                    "question": (f"Does that match what people here experience? Where do people "
                                 f"find {noun} now, including outside formal organizations?"),
                })
            elif ratio >= TOTAL_MORE:
                cards.append({
                    "kind": "more", "score": 1.2 * abs(math.log(ratio)) * _evidence(support),
                    "title": f"More organizations list {phrase}",
                    "text": (f"Per resident, more organizations in {name} list {phrase} on their "
                             f"websites than in 10 similar places (about {ratio:.1f} times the "
                             "typical level)."),
                    "confidence": _confidence(round(support), p["typed_share"]),
                    "question": (f"Why are {noun} so common here? Who takes part, and who "
                                 "might not be reached?"),
                })

        # 2. Specific organization types
        g = p["grid"]
        type_cards = []
        for j, opp in enumerate(OPPS[1:5], start=1):
            key = OPP_KEY[opp]
            phrase = MEASURES[key][1]
            for i, typ in enumerate(TYPES):
                peer = g["peer"][i][j]
                if typ == UNCLASSIFIED or peer is None:
                    continue
                n = g["n"][i][j]
                expected = peer * pop / C.RATE_PER
                support = max(n, expected)
                if support < MIN_COUNT:
                    continue
                ratio = n / expected if expected > 0 else math.inf
                # Ranking only: damp ratios built on very small numbers
                damped = (n + 2) / (expected + 2)
                low = _tp(typ)
                if ratio <= TYPE_FEWER:
                    type_cards.append({
                        "kind": "fewer",
                        "score": abs(math.log(damped)) * _evidence(support),
                        "title": f"Few {low} organizations list {phrase}",
                        "text": (f"{_count_phrase(n, low)} here list {phrase}. In similar places "
                                 f"of this size, about {_fmt(expected)} would."),
                        "confidence": _confidence(round(support), p["typed_share"]),
                        "question": (f"Do people here look for {QUESTION_NOUN[key]} through "
                                     f"{low} groups? Where else does that happen?"),
                    })
                elif ratio >= TYPE_MORE:
                    type_cards.append({
                        "kind": "more",
                        "score": abs(math.log(damped)) * _evidence(support),
                        "title": f"{_tp(typ, True)} organizations stand out for {phrase}",
                        "text": (f"{_count_phrase(n, low)} here list {phrase}, compared with "
                                 f"about {_fmt(expected)} in similar places of this size."),
                        "confidence": _confidence(n, p["typed_share"]),
                        "question": (f"What role do {low} organizations play in community life "
                                     "here? Who do they reach, and who might they miss?"),
                    })
        type_cards.sort(key=lambda c: -c["score"])
        cards += [c | {"score": c["score"] * 0.6} for c in type_cards[:2]]

    # 3. Organization types present here that list none of the four
    g = p["grid"]
    col_all, col_any = OPPS.index(ALL_ORGS), OPPS.index("Any civic opportunity")
    quiet = [(TYPES[i], row[col_all] - row[col_any]) for i, row in enumerate(g["n"])
             if TYPES[i] != UNCLASSIFIED]
    quiet = [q for q in quiet if q[1] >= MIN_COUNT]
    if quiet:
        typ, k = max(quiet, key=lambda x: x[1])
        cards.append({
            "kind": "quiet", "score": 0.25,
            "title": f"{_tp(typ, True)} organizations that list no opportunities",
            "text": (f"{_fmt(k)} {_tp(typ)} organizations here list none of the four kinds "
                     "of opportunity on their websites. Many may still offer them without "
                     "saying so online, or have no website at all."),
            "confidence": _confidence(k, p["typed_share"]),
            "question": (f"What do {_tp(typ)} organizations here do in the community? How "
                         "do people find out about them?"),
        })

    cards.sort(key=lambda c: -c["score"])
    picked = []
    for c in cards[:4]:
        c.pop("score")
        picked.append(c)

    if not comparable or t["any_opp"] < MIN_COUNT:
        picked.insert(0, {
            "kind": "small",
            "title": "Too few organizations for firm comparisons",
            "text": (f"{name} has {_count_phrase(t['any_opp'], '')} listing opportunities "
                     "online, too few to compare reliably with similar places. Civic life here "
                     "may run through churches, schools, local government, or informal groups "
                     "that these records don't capture."),
            "confidence": _confidence(t["orgs"], p["typed_share"]),
            "question": ("Where do people here come together, and who brings them together? "
                         "Which of those places would not show up in nonprofit records?"),
        })
    elif not picked:
        picked.append({
            "kind": "similar",
            "title": "Close to similar places",
            "text": (f"On the measures we can compare, {name} looks much like the 10 places "
                     "most similar to it."),
            "confidence": _confidence(t["orgs"], p["typed_share"]),
            "question": ("Numbers can look typical and still miss what matters. What kinds of "
                         "getting involved do people here value most?"),
        })
    return picked


# ---- assembling place files -----------------------------------------------------

def _grid_arrays(providers: pd.DataFrame, ids: pd.Index):
    """Dense arrays [place, type, opportunity] for counts and peer medians."""
    t_idx = {t: i for i, t in enumerate(TYPES)}
    o_idx = {o: i for i, o in enumerate(OPPS)}
    p_idx = pd.Series(np.arange(len(ids)), index=ids)
    pv = providers[providers["place_id"].isin(ids)]
    pi = p_idx.loc[pv["place_id"]].to_numpy()
    ti = pv["org_type"].map(t_idx).to_numpy()
    oi = pv["opportunity"].map(o_idx).to_numpy()
    n = np.zeros((len(ids), len(TYPES), len(OPPS)), dtype=int)
    peer = np.full((len(ids), len(TYPES), len(OPPS)), np.nan)
    n[pi, ti, oi] = pv["n"].to_numpy()
    peer[pi, ti, oi] = pv["peer_median_per_10k"].to_numpy()
    # A missing row with known peers means the peer median is 0 for that cell
    has_peers = pv.groupby("place_id")["peer_median_per_10k"].apply(lambda s: s.notna().any())
    rows_with_peers = p_idx.loc[has_peers[has_peers].index].to_numpy()
    sub = peer[rows_with_peers]
    sub[np.isnan(sub)] = 0
    peer[rows_with_peers] = sub
    return n, peer


def _peer_medians(places, peers, id_col):
    cols = [f"{k}_per_10k_eb" for k in MEASURES] + CONTEXT
    v = places.set_index(id_col)[cols]
    return peers.join(v, on="peer_id").groupby("place_id")[cols].median()


def place_records(level: str, places: pd.DataFrame, providers: pd.DataFrame,
                  peers: pd.DataFrame, towns: pd.Series) -> dict:
    id_col = "FIPS" if level == "county" else "ZCTA"
    places = places[places["state"].notna()].reset_index(drop=True)
    ids = pd.Index(places[id_col])
    n_arr, peer_arr = _grid_arrays(providers, ids)
    pmed = _peer_medians(places, peers, id_col)
    peer_lists = peers.sort_values("rank").groupby("place_id")["peer_id"].apply(list)
    lookup = places.set_index(id_col)

    def label(raw):
        r = lookup.loc[raw]
        if level == "county":
            return r["name"]
        town = towns.get(raw)
        return f"{raw} · {town}, {r['state']}" if town else f"ZIP {raw}, {r['state']}"

    records = {}
    for k, r in enumerate(places.itertuples(index=False)):
        raw = getattr(r, id_col)
        row = lookup.loc[raw]
        pop = row["TotalPopulation"]
        pop = None if pd.isna(pop) else float(pop)
        town = towns.get(raw) if level == "zcta" else None
        if level == "county":
            short = row["name"].rsplit(",", 1)[0]
        else:
            short = f"ZIP {raw}" + (f" ({town})" if town else "")

        totals = {key: int(row[key]) for key in ["orgs", *MEASURES]}
        rates = {key: _r(row[f"{key}_per_10k_eb"]) for key in MEASURES}
        pctile = {key: _r(row[f"{key}_per_10k_eb_pctile"], 0) for key in MEASURES}
        vs_peers = {}
        if raw in pmed.index and pop and pop >= C.MIN_POP:
            for key in MEASURES:
                med = pmed.loc[raw, f"{key}_per_10k_eb"]
                val = row[f"{key}_per_10k_eb"]
                if pd.notna(med) and med > 0 and pd.notna(val):
                    vs_peers[key] = round(float(val / med), 3)

        peer_ids = peer_lists.get(raw, [])
        peer_rows = []
        for pid in peer_ids:
            pr = lookup.loc[pid]
            peer_rows.append({
                "id": _pid(level, pid),
                "name": label(pid),
                "rates": {key: _r(pr[f"{key}_per_10k_eb"]) for key in MEASURES},
            })

        rec = {
            "id": _pid(level, raw), "level": level, "raw": raw,
            "name": label(raw), "short_name": short, "state": row["state"],
            "county": (None if level == "county" or pd.isna(row["county"]) else row["county"]),
            "county_id": (None if level == "county" or pd.isna(row["FIPS"]) else "c" + row["FIPS"]),
            "population": pop,
            "rurality": None if pd.isna(row["rurality"]) else row["rurality"],
            "typed_share": _r(row["typed_share"], 3) if pd.notna(row["typed_share"]) else None,
            "totals": totals, "rates": rates, "pctile": pctile, "vs_peers": vs_peers,
            "context": {c: _r(row[c], 1) for c in CONTEXT},
            "peer_context": ({c: _r(pmed.loc[raw, c], 1) for c in CONTEXT}
                             if raw in pmed.index else None),
            "peers": peer_rows,
            "grid": {
                "n": n_arr[k].tolist(),
                "peer": [[_r(v, 2) for v in row_] for row_ in peer_arr[k]],
            },
        }
        rec["typed_share"] = rec["typed_share"] if rec["typed_share"] is not None else 0.0
        rec["findings"] = findings(rec)
        rec["observations"] = observations(rec)
        records[rec["id"]] = rec
    return records


# ---- state files and search -----------------------------------------------------

STATE_COLS = ["id", "name", "town", "county", "population", "rurality", "orgs", "any_opp",
              "rate_any", "pctile_any", "vs_any", "vs_membership", "vs_volunteer", "vs_events",
              "vs_take_action", *CONTEXT]


def state_rows(records: dict, level: str, towns: pd.Series) -> dict:
    by_state = {}
    for rec in records.values():
        if rec["level"] != level:
            continue
        vp = rec["vs_peers"]
        by_state.setdefault(rec["state"], []).append([
            rec["id"], rec["short_name"] if level == "county" else rec["raw"],
            towns.get(rec["raw"]) if level == "zcta" else None,
            rec["county"], rec["population"], rec["rurality"],
            rec["totals"]["orgs"], rec["totals"]["any_opp"], rec["rates"]["any_opp"],
            rec["pctile"]["any_opp"], vp.get("any_opp"), vp.get("membership"),
            vp.get("volunteer"), vp.get("events"), vp.get("take_action"),
            *[rec["context"][c] for c in CONTEXT],
        ])
    return by_state


def state_totals(county_records: dict) -> dict:
    """Population, totals, and type × opportunity counts summed over each state's counties."""
    out = {}
    for rec in county_records.values():
        s = out.setdefault(rec["state"], {
            "population": 0.0, "totals": {k: 0 for k in ["orgs", *MEASURES]},
            "grid_n": np.zeros((len(TYPES), len(OPPS)), dtype=int)})
        s["population"] += rec["population"] or 0
        for k in s["totals"]:
            s["totals"][k] += rec["totals"][k]
        s["grid_n"] += np.array(rec["grid"]["n"])
    return out


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, separators=(",", ":"), ensure_ascii=False))


def main():
    t0 = time.time()
    need = [C.OUT / f"{t}.parquet" for t in ("places_county", "places_zcta")]
    if not all(p.exists() for p in need):
        raise SystemExit("Run `python -m pipeline.build` first.")
    if (DATA / "p").exists():
        shutil.rmtree(DATA / "p")
    towns = _towns()

    records = {}
    for level in ("county", "zcta"):
        print(f"{level} pages ...")
        places = pd.read_parquet(C.OUT / f"places_{level}.parquet")
        providers = pd.read_parquet(C.OUT / f"providers_{level}.parquet")
        peers = pd.read_parquet(C.OUT / f"peers_{level}.parquet")
        records.update(place_records(level, places, providers, peers, towns))

    for pid, rec in records.items():
        write_json(DATA / "p" / f"{pid}.json", rec)

    county_recs = {k: v for k, v in records.items() if v["level"] == "county"}
    totals = state_totals(county_recs)
    counties = state_rows(records, "county", towns)
    zips = state_rows(records, "zcta", towns)
    for st in sorted(totals):
        s = totals[st]
        write_json(DATA / "s" / f"{st}.json", {
            "state": st, "population": s["population"], "totals": s["totals"],
            "grid_n": s["grid_n"].tolist(), "columns": STATE_COLS,
            "counties": counties.get(st, []), "zips": zips.get(st, [])})

    search = [[r["id"], r["name"], r["state"]] for r in records.values()]
    search.sort(key=lambda x: (x[0][0], x[1]))
    write_json(DATA / "search.json", search)

    nat = {k: sum(r["totals"][k] for r in county_recs.values()) for k in ["orgs", *MEASURES]}
    write_json(DATA / "meta.json", {
        "built": date.today().isoformat(), "types": TYPES, "opportunities": OPPS,
        "measures": {k: v[0] for k, v in MEASURES.items()},
        "context": C.CONTEXT, "rate_per": C.RATE_PER, "min_pop": C.MIN_POP,
        "national": {"population": sum(r["population"] or 0 for r in county_recs.values()),
                     "totals": nat},
        "states": sorted(totals),
    })
    size = sum(f.stat().st_size for f in DATA.rglob("*.json")) / 1e6
    print(f"Wrote {len(records):,} place files, {len(totals)} state files "
          f"({size:.0f} MB) in {time.time() - t0:.0f}s -> {DATA.relative_to(C.ROOT)}/")


if __name__ == "__main__":
    main()
