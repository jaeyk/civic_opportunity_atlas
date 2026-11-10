"""ZIP-to-county assignment and rurality labels."""

import pandas as pd


def rurality(rucc: pd.Series) -> pd.Series:
    """Collapse RUCC 2013 codes: 1-3 metro, 4-7 nonmetro (urban), 8-9 rural."""
    labels = pd.cut(rucc, bins=[0, 3, 7, 9], labels=["Metro", "Small town", "Rural"])
    return labels.astype("string")


def zcta_county_crosswalk(rel: pd.DataFrame) -> pd.DataFrame:
    """Every ZCTA × county pair with its share of the ZCTA's land, plus a primary-county flag.

    A ZIP is assigned to the county holding the largest share of its land.
    """
    rel = rel.copy()
    rel["land_share"] = (rel["land_part"] / rel["zcta_land"]).where(rel["zcta_land"] > 0)
    # Water-only ZCTAs have zero land; fall back to equal shares
    rel["land_share"] = rel["land_share"].fillna(1 / rel.groupby("ZCTA")["FIPS"].transform("size"))
    rel = rel.sort_values(["ZCTA", "land_share"], ascending=[True, False])
    rel["primary"] = ~rel.duplicated("ZCTA")
    return rel[["ZCTA", "FIPS", "county_name", "land_share", "primary"]].reset_index(drop=True)
