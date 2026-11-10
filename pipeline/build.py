"""Build all tables for the site.

    .venv/bin/python -m pipeline.build

Writes to data/processed/ (git-ignored; regenerate any time):

    places_{level}.parquet     one row per county / ZIP code (level = county, zcta):
                               organizations, providers of each opportunity, raw and
                               smoothed rates per 10k residents, national percentiles,
                               rurality, community context, cold/hot spot cluster
    providers_{level}.parquet  place × organization type × opportunity: how many
                               organizations of each type offer each opportunity,
                               per 10k residents, vs. the median of peer places
    peers_{level}.parquet      the 10 most similar places (by context) for each place
    zcta_county.parquet        every ZIP × county pair with its share of the ZIP's land
    build_meta.json            settings, headline numbers, and validation checks
"""

import json
import time
import warnings
from datetime import date

import numpy as np
import pandas as pd

from . import config as C
from . import sources
from .clusters import lisa_rate
from .geography import rurality, zcta_county_crosswalk
from .metrics import add_percentiles, add_rates
from .peers import find_peers
from .providers import TOTAL_COLS, compare_with_peers, load_orgs, merge_networks, place_totals, provider_matrix

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

COUNTS = ["orgs", *TOTAL_COLS.values()]
RANKED = [f"{c}_per_10k_eb" for c in TOTAL_COLS.values()]
# Our totals vs. the published MapAgora aggregates (validation only)
PUBLISHED = {"orgs": "n", "any_opp": "civic_org_sum", "membership": "membership_sum",
             "volunteer": "volunteer_sum", "events": "events_sum", "take_action": "take_action_sum"}
CONTEXT_COLS = ["TotalPopulation", *C.CONTEXT]


def _eligible(df: pd.DataFrame) -> pd.Series:
    return df["TotalPopulation"].ge(C.MIN_POP)


def _assemble(base: pd.DataFrame, id_col: str, units: pd.DataFrame, meta: dict) -> pd.DataFrame:
    """Join our org-level totals to a place list that carries population and context."""
    totals = place_totals(units).rename(columns={"place_id": id_col})
    places = base.merge(totals, on=id_col, how="left", suffixes=("_published", ""))
    places[COUNTS] = places[COUNTS].fillna(0).astype(int)
    meta["matches_published"] = {
        ours: round(float((places[ours] == places[f"{pub}"]).mean()), 4)
        for ours, pub in PUBLISHED.items()}
    meta["units_outside_place_list"] = int((~totals[id_col].isin(base[id_col])).sum())
    return places.drop(columns=list(PUBLISHED.values()))


def _clusters(places: pd.DataFrame, shapes, id_col: str, meta: dict) -> pd.DataFrame:
    """LISA on providers of any opportunity per resident, lower 48 + DC, eligible places."""
    gdf = shapes.merge(places, on=id_col, how="inner")
    gdf = gdf[_eligible(gdf) & gdf["state"].notna() & ~gdf["state"].isin(C.NON_CONTIGUOUS)]
    res = lisa_rate(gdf, "any_opp", "TotalPopulation")
    meta.update(global_morans_i=round(res.attrs["global_i"], 4),
                global_morans_p=res.attrs["global_p"], islands_linked=res.attrs["n_islands"])
    res[id_col] = gdf[id_col].to_numpy()
    out = places.merge(res, on=id_col, how="left")
    out["cluster"] = out["cluster"].fillna("Not analyzed")
    return out


def _finish(places: pd.DataFrame, id_col: str, units: pd.DataFrame, shapes, meta: dict):
    places = add_rates(places, COUNTS)
    places = add_percentiles(places, RANKED, _eligible(places))
    places = _clusters(places, shapes, id_col, meta)
    peers = find_peers(places, id_col, _eligible(places))
    population = places.set_index(id_col)["TotalPopulation"]
    providers = compare_with_peers(provider_matrix(units), population, peers)
    meta.update(places=len(places), eligible=int(_eligible(places).sum()),
                with_peers=int(peers["place_id"].nunique()),
                clusters=places["cluster"].value_counts().to_dict(),
                provider_rows=len(providers))
    return places, providers, peers


def build_county(orgs: pd.DataFrame, meta: dict):
    shapes = sources.county_shapes()
    base = sources.county_counts().merge(sources.county_rucc(), on="FIPS", how="left")
    base = base.merge(shapes[["FIPS", "NAMELSAD"]], on="FIPS", how="left")
    base["name"] = base["NAMELSAD"].fillna(base["county_name"]) + ", " + base["state"]
    base["rurality"] = rurality(base["rucc"])
    base = base[["FIPS", "name", "state", "rucc", "rurality", *CONTEXT_COLS, *PUBLISHED.values()]]

    units = merge_networks(orgs, "FIPS")
    places = _assemble(base, "FIPS", units, meta)
    return _finish(places, "FIPS", units, shapes, meta)


def build_zcta(orgs: pd.DataFrame, counties: pd.DataFrame, meta: dict):
    xwalk = zcta_county_crosswalk(sources.zcta_county_relationship())
    primary = xwalk[xwalk["primary"]][["ZCTA", "FIPS"]]

    base = sources.zcta_counts().merge(primary, on="ZCTA", how="left")
    base = base.merge(counties[["FIPS", "name", "rucc", "rurality"]].rename(
        columns={"name": "county"}), on="FIPS", how="left")
    base["name"] = "ZIP " + base["ZCTA"]
    base = base[["ZCTA", "name", "state", "FIPS", "county", "rucc", "rurality",
                 *CONTEXT_COLS, *PUBLISHED.values()]]
    meta["no_county_match"] = int(base["FIPS"].isna().sum())

    units = merge_networks(orgs, "ZCTA")
    places = _assemble(base, "ZCTA", units, meta)
    places, providers, peers = _finish(places, "ZCTA", units, sources.zcta_shapes(), meta)
    return places, providers, peers, xwalk


def main():
    t0 = time.time()
    C.OUT.mkdir(parents=True, exist_ok=True)
    meta = {"built": date.today().isoformat(),
            "settings": {"rate_per": C.RATE_PER, "min_pop": C.MIN_POP,
                         "permutations": C.PERMUTATIONS, "alpha": C.ALPHA,
                         "seed": C.SEED, "n_peers": C.N_PEERS},
            "county": {}, "zcta": {}}

    print("Loading organizations ...")
    orgs = load_orgs()
    meta["orgs_used"] = len(orgs)
    print("Counties ...")
    county, county_prov, county_peers = build_county(orgs, meta["county"])
    print("ZIP codes ...")
    zcta, zcta_prov, zcta_peers, xwalk = build_zcta(orgs, county, meta["zcta"])

    tables = {"places_county": county, "providers_county": county_prov, "peers_county": county_peers,
              "places_zcta": zcta, "providers_zcta": zcta_prov, "peers_zcta": zcta_peers,
              "zcta_county": xwalk}
    for name, df in tables.items():
        df.to_parquet(C.OUT / f"{name}.parquet", index=False)
        print(f"  {name:<17} {len(df):>9,} rows")
    (C.OUT / "build_meta.json").write_text(json.dumps(meta, indent=2, default=str))
    print(json.dumps(meta, indent=2, default=lambda v: int(v) if isinstance(v, np.integer) else str(v)))
    print(f"Done in {time.time() - t0:.0f}s -> {C.OUT.relative_to(C.ROOT)}/")


if __name__ == "__main__":
    main()
