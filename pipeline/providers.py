"""What kinds of civic opportunity exist, to what extent, and provided by whom.

Built from the organization-level MapAgora file (Dataset 1) with the rule that
reproduces the published county counts:

  1. drop organizations whose mailing address is a P.O. box (is_po == 1)
  2. merge local chapters of the same network (grouping_value) within a place
  3. a merged network offers an opportunity if any of its chapters does

The central table is long format, one row per place × organization type ×
opportunity, with the count of organizations ("providers").
"""

import pandas as pd

from . import config as C

UNCLASSIFIED = "Type not identified"
ALL_ORGS = "All organizations"

# flag column in the org file -> opportunity label
OPPORTUNITY_FLAGS = {
    "opp_binary": "Any civic opportunity",
    "membership": "Membership",
    "volunteer": "Volunteering",
    "events": "Public events",
    "take_action": "Civic & political action",
}
# place-total column names
TOTAL_COLS = {"opp_binary": "any_opp", "membership": "membership",
              "volunteer": "volunteer", "events": "events", "take_action": "take_action"}


def load_orgs() -> pd.DataFrame:
    if not C.ORGS.exists():
        raise SystemExit("Missing organization-level data. Run ./get_full_data.sh first.")
    o = pd.read_parquet(C.ORGS, columns=["id", "FIPS", "ZCTA", "is_po", "grouping_value",
                                        "predicted", *OPPORTUNITY_FLAGS])
    o = o[o["is_po"] == 0].copy()
    o["org_type"] = o["predicted"].map(C.ORG_TYPES).fillna(UNCLASSIFIED)
    # Organizations without a network id stand alone
    o["grouping_value"] = o["grouping_value"].fillna("org" + o["id"].astype(str))
    return o.drop(columns=["predicted", "is_po"])


def merge_networks(orgs: pd.DataFrame, id_col: str) -> pd.DataFrame:
    """One unit per place × network. A unit offers an opportunity if any chapter does.

    Its type is a classified chapter's type when one exists.
    """
    o = orgs.dropna(subset=[id_col])
    o = o.assign(_unclassified=o["org_type"].eq(UNCLASSIFIED)).sort_values("_unclassified")
    agg = {flag: "max" for flag in OPPORTUNITY_FLAGS} | {"org_type": "first"}
    return (o.groupby([id_col, "grouping_value"], sort=False).agg(agg)
            .reset_index().rename(columns={id_col: "place_id"}))


def place_totals(units: pd.DataFrame) -> pd.DataFrame:
    """Per place: number of organizations and of providers of each opportunity."""
    g = units.groupby("place_id")
    out = g.size().rename("orgs").to_frame()
    for flag, col in TOTAL_COLS.items():
        out[col] = g[flag].sum()
    out["typed_share"] = 1 - units["org_type"].eq(UNCLASSIFIED).groupby(units["place_id"]).mean()
    return out.reset_index()


def provider_matrix(units: pd.DataFrame) -> pd.DataFrame:
    """Long table: place_id, org_type, opportunity, n (organizations).

    'All organizations' counts every organization of that type, whether or not it
    offers anything, so a place can see which types are present but inactive.
    """
    long = units.melt(id_vars=["place_id", "org_type"], value_vars=list(OPPORTUNITY_FLAGS),
                      var_name="flag", value_name="offers")
    long = long[long["offers"] == 1]
    counts = (long.groupby(["place_id", "org_type", "flag"]).size().rename("n").reset_index())
    counts["opportunity"] = counts["flag"].map(OPPORTUNITY_FLAGS)
    allorgs = units.groupby(["place_id", "org_type"]).size().rename("n").reset_index()
    allorgs["opportunity"] = ALL_ORGS
    return pd.concat([counts.drop(columns="flag"), allorgs], ignore_index=True)


def compare_with_peers(matrix: pd.DataFrame, population: pd.Series,
                       peers: pd.DataFrame) -> pd.DataFrame:
    """Add per-10k rates, the peer-place median, and the gap (place minus peers).

    Missing combinations count as zero. Rows where both the place and its peers
    have zero are dropped to keep the table sparse.
    """
    sep = "||"
    m = matrix.copy()
    m["per_10k"] = m["n"] / m["place_id"].map(population) * C.RATE_PER
    m["key"] = m["org_type"] + sep + m["opportunity"]
    wide = m.pivot_table(index="place_id", columns="key", values="per_10k", fill_value=0)
    wide = wide.reindex(population.index, fill_value=0)   # places with no orgs are all zeros

    pairs = peers[["place_id", "peer_id"]]
    peer_med = pairs.join(wide, on="peer_id").drop(columns="peer_id").groupby("place_id").median()
    peer_med.columns.name = "key"
    peer_long = peer_med.stack().rename("peer_median_per_10k").reset_index()
    peer_long[["org_type", "opportunity"]] = peer_long["key"].str.split(sep, n=1, expand=True, regex=False)
    peer_long = peer_long.drop(columns="key")
    m = m.drop(columns="key")

    out = m.merge(peer_long, on=["place_id", "org_type", "opportunity"], how="outer")
    out["n"] = out["n"].fillna(0).astype(int)
    out["per_10k"] = out["per_10k"].fillna(0).where(out["place_id"].map(population).gt(0))
    out["gap_per_10k"] = out["per_10k"] - out["peer_median_per_10k"]
    keep = (out["n"] > 0) | out["peer_median_per_10k"].fillna(0).gt(0)
    return out[keep].sort_values(["place_id", "opportunity", "org_type"]).reset_index(drop=True)
