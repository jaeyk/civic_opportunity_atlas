"""Tests for the data pipeline.

Unit tests run anywhere. Tests on built tables are skipped until you run
`python -m pipeline.build` (and ./get_full_data.sh before that).
"""

import numpy as np
import pandas as pd
import pytest

from pipeline import config as C
from pipeline.geography import rurality, zcta_county_crosswalk
from pipeline.metrics import empirical_bayes
from pipeline.providers import ALL_ORGS, OPPORTUNITY_FLAGS, merge_networks, provider_matrix

OPPS = [v for v in OPPORTUNITY_FLAGS.values()]


# ---- unit tests ----------------------------------------------------------------

def test_empirical_bayes_shrinks_small_places_more():
    events = np.array([0, 1, 50, 5000])
    base = np.array([10, 10, 10_000, 1_000_000])
    eb = empirical_bayes(events, base)
    overall = events.sum() / base.sum()
    raw = events / base
    # Small places move most of the way to the overall rate; big ones barely move
    assert abs(eb[1] - overall) < abs(raw[1] - overall)
    assert np.isclose(eb[3], raw[3], rtol=0.05)


def test_empirical_bayes_missing_population_is_nan():
    eb = empirical_bayes([1, 2], [np.nan, 0])
    assert np.isnan(eb).all()


def test_rurality_labels():
    assert list(rurality(pd.Series([1, 3, 4, 7, 8, 9]))) == [
        "Metro", "Metro", "Small town", "Small town", "Rural", "Rural"]


def test_crosswalk_picks_largest_land_share():
    rel = pd.DataFrame({"ZCTA": ["00001", "00001", "00002"], "FIPS": ["A", "B", "C"],
                        "county_name": ["a", "b", "c"], "land_part": [30, 70, 0],
                        "zcta_land": [100, 100, 0]})
    x = zcta_county_crosswalk(rel)
    assert x.loc[x["primary"], "FIPS"].tolist() == ["B", "C"]
    assert np.isclose(x.groupby("ZCTA")["land_share"].sum(), 1).all()


def test_networks_merge_and_offer_if_any_chapter_does():
    orgs = pd.DataFrame({
        "id": [1, 2, 3], "FIPS": ["X", "X", "X"], "grouping_value": ["g", "g", "h"],
        "org_type": ["Type not identified", "Youth", "Religious"],
        "opp_binary": [0, 1, 1], "membership": [0, 1, 0], "volunteer": [0, 0, 1],
        "events": [0, 0, 0], "take_action": [0, 0, 0]})
    units = merge_networks(orgs, "FIPS")
    assert len(units) == 2                                  # g's two chapters count once
    g = units[units["grouping_value"] == "g"].iloc[0]
    assert g["membership"] == 1 and g["org_type"] == "Youth"  # classified type wins
    m = provider_matrix(units)
    assert m.query("opportunity == @ALL_ORGS")["n"].sum() == 2


# ---- tests on built tables -----------------------------------------------------

def _load(name):
    path = C.OUT / f"{name}.parquet"
    if not path.exists():
        pytest.skip("run `python -m pipeline.build` first")
    return pd.read_parquet(path)


@pytest.mark.parametrize("level,id_col", [("county", "FIPS"), ("zcta", "ZCTA")])
def test_place_ids_unique(level, id_col):
    assert _load(f"places_{level}")[id_col].is_unique


@pytest.mark.parametrize("level,id_col", [("county", "FIPS"), ("zcta", "ZCTA")])
def test_type_breakdown_sums_to_place_totals(level, id_col):
    places = _load(f"places_{level}").set_index(id_col)
    prov = _load(f"providers_{level}")
    sums = prov.groupby(["place_id", "opportunity"])["n"].sum().unstack().reindex(places.index).fillna(0)
    assert (sums["Any civic opportunity"] == places["any_opp"]).all()
    assert (sums["Volunteering"] == places["volunteer"]).all()
    assert (sums[ALL_ORGS] == places["orgs"]).all()


def test_peers_exclude_self_and_have_ten():
    peers = _load("peers_county")
    assert (peers["place_id"] != peers["peer_id"]).all()
    assert (peers.groupby("place_id").size() == C.N_PEERS).all()


def test_matches_published_aggregates():
    import json
    meta = json.loads((C.OUT / "build_meta.json").read_text())
    assert min(meta["zcta"]["matches_published"].values()) == 1.0
    assert min(meta["county"]["matches_published"].values()) > 0.99
