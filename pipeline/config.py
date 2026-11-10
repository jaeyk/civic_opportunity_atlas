"""Paths and constants shared by the pipeline."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RAW = ROOT / "raw_data"
FULL = RAW / "mapagora_full"   # fetched by ./get_full_data.sh
GEO = RAW / "geo"              # Census downloads, cached
OUT = ROOT / "data" / "processed"

COUNTY_COUNTS = RAW / "cnty_counts_cov.csv"
COUNTY_TYPES = RAW / "cnty_civic_org_type.csv"
COUNTY_CLASSES = RAW / "County_Classifications.csv"   # USDA ERS, RUCC 2013
COUNTY_SHAPES = RAW / "counties.gpkg"
ZCTA_COUNTS = FULL / "zcta_counts_cov.csv"
ZCTA_TYPES = FULL / "zcta_civic_org_type.csv"
ORGS = FULL / "ind_org_df.parquet"

CENSUS = "https://www2.census.gov/geo"
ZCTA_SHAPES_URL = f"{CENSUS}/tiger/GENZ2020/shp/cb_2020_us_zcta520_500k.zip"
STATE_SHAPES_URL = f"{CENSUS}/tiger/GENZ2020/shp/cb_2020_us_state_20m.zip"
ZCTA_COUNTY_URL = f"{CENSUS}/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_county20_natl.txt"

# Rates and clustering
RATE_PER = 10_000     # show rates per 10,000 residents
MIN_POP = 100         # below this, a place is shown but not ranked, clustered, or peered
PERMUTATIONS = 999
ALPHA = 0.05
SEED = 20250101
PROJ = "EPSG:5070"    # USA Contiguous Albers Equal Area

NOT_STATES = {"PR", "VI", "GU", "AS", "MP"}
NON_CONTIGUOUS = {"AK", "HI"} | NOT_STATES

# Four forms of civic opportunity (MapAgora)
OPPORTUNITIES = {
    "membership_sum": "Membership",
    "volunteer_sum": "Volunteering",
    "events_sum": "Public events",
    "take_action_sum": "Civic & political action",
}

# Community context used to find peer places (ACS / CDC SVI, via MapAgora)
CONTEXT = {
    "POV150": "Below 150% of poverty line",
    "BROAD": "No broadband",
    "NOHSDP": "No high school diploma",
    "UNEMP": "Unemployed",
    "REMNRTY": "Racial/ethnic minority",
    "SNGPNT": "Single-parent households",
}
N_PEERS = 10

# Organization types: org-level code -> label used in the aggregate files
ORG_TYPES = {
    "religious": "Religious",
    "socialfraternal": "Social & Fraternal",
    "foundation": "Foundations",
    "hobby": "Hobby & Sports",
    "education": "Education",
    "professional": "Professional",
    "community": "Community",
    "arts": "Arts & Cultural",
    "youth": "Youth",
    "health": "Healthcare",
    "econ": "Economic",
    "unions": "Unions",
    "housing": "Housing",
    "research": "Research & Think Tank",
    "civic": "Political",
}
