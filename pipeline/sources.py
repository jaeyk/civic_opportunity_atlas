"""Load raw inputs. Census files are downloaded once and cached in raw_data/geo/."""

import urllib.request
from pathlib import Path

import geopandas as gpd
import pandas as pd

from . import config as C


def _cached(url: str) -> Path:
    C.GEO.mkdir(parents=True, exist_ok=True)
    path = C.GEO / url.rsplit("/", 1)[-1]
    if not path.exists():
        print(f"  downloading {path.name} ...")
        tmp = path.with_suffix(path.suffix + ".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.rename(path)
    return path


def _require(path: Path) -> Path:
    if not path.exists():
        raise SystemExit(f"Missing {path.relative_to(C.ROOT)}. Run ./get_full_data.sh first.")
    return path


def county_counts() -> pd.DataFrame:
    return pd.read_csv(C.COUNTY_COUNTS, dtype={"FIPS": str}).drop(columns=["Geolocation"])


COUNT_COLS = ["n", "civic_org_sum", "civic_opp_sum", "volunteer_sum",
              "membership_sum", "take_action_sum", "events_sum"]


def zcta_counts() -> pd.DataFrame:
    """One row per ZCTA.

    A few ZCTAs appear twice in MapAgora: a stray row with one organization
    whose IRS state differs (e.g. 04103 under MA as well as ME). Merge them:
    sum the counts and keep the state and covariates of the larger row.
    """
    z = pd.read_csv(_require(C.ZCTA_COUNTS), dtype={"ZCTA": str})
    z = z.sort_values("n", ascending=False)
    sums = z.groupby("ZCTA")[COUNT_COLS].sum()
    first = z.drop_duplicates("ZCTA").set_index("ZCTA").drop(columns=COUNT_COLS)
    return first.join(sums).reset_index()


def org_types(level: str) -> pd.DataFrame:
    """Organization-type counts for civic-opportunity providers, one row per place × type."""
    if level == "county":
        df = pd.read_csv(C.COUNTY_TYPES, dtype={"FIPS": str}).rename(columns={"FIPS": "place_id"})
    else:
        df = pd.read_csv(_require(C.ZCTA_TYPES), dtype={"ZCTA": str}).rename(columns={"ZCTA": "place_id"})
    return df[df["class"].notna() & (df["class"] != "NA")][["place_id", "class", "n"]]


def county_rucc() -> pd.DataFrame:
    """USDA Rural-Urban Continuum Code (2013) per county: 1-3 metro, 4-9 nonmetro."""
    df = pd.read_csv(C.COUNTY_CLASSES, dtype={"FIPStxt": str}, encoding="latin-1")
    return pd.DataFrame({
        "FIPS": df["FIPStxt"].str.zfill(5),
        "county_name": df["County"],
        "rucc": pd.to_numeric(df["RuralUrbanContinuumCode2013"], errors="coerce"),
    })


def county_shapes() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(C.COUNTY_SHAPES)
    return gdf[["GEOID", "NAMELSAD", "STUSPS", "geometry"]].rename(columns={"GEOID": "FIPS"})


def zcta_shapes() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(f"zip://{_cached(C.ZCTA_SHAPES_URL)}")
    return gdf[["ZCTA5CE20", "geometry"]].rename(columns={"ZCTA5CE20": "ZCTA"})


def state_shapes() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(f"zip://{_cached(C.STATE_SHAPES_URL)}")
    return gdf[~gdf["STUSPS"].isin(C.NOT_STATES)][["STUSPS", "NAME", "geometry"]]


def zcta_county_relationship() -> pd.DataFrame:
    """Census 2020 ZCTA-to-county relationship: land area of each ZCTA × county part."""
    df = pd.read_csv(_cached(C.ZCTA_COUNTY_URL), sep="|", dtype=str, encoding="utf-8-sig")
    df = df[df["GEOID_ZCTA5_20"].notna()]
    return pd.DataFrame({
        "ZCTA": df["GEOID_ZCTA5_20"],
        "FIPS": df["GEOID_COUNTY_20"],
        "county_name": df["NAMELSAD_COUNTY_20"],
        "land_part": pd.to_numeric(df["AREALAND_PART"]),
        "zcta_land": pd.to_numeric(df["AREALAND_ZCTA5_20"]),
    })
