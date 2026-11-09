#!/usr/bin/env python3
"""Civic cold spots and civic deserts at the ZIP code level.

Adapts the method of MIT Civic Data Design Lab's "Ghost Cities of China"
(Williams et al. 2018, Cities): score every residential unit by the amenities
it offers, then use spatial clustering to find contiguous areas that score low.

    Ghost Cities                      This script
    -------------------------------   ---------------------------------------------
    residential grid cells            ZIP codes (ZCTAs) with >= MIN_POP residents
    amenity score                     civic opportunity per resident, Empirical
                                      Bayes-smoothed so tiny ZIPs don't dominate
    low-score cells, clustered        Local Moran's I (LISA) on the smoothed rate:
                                      significant low-low clusters = civic cold spots
    ground truthing                   compare who lives in cold spots (poverty,
                                      broadband, education, unemployment, minority)

A civic desert (Kim, de Vries & Han 2025) is the extreme case: a ZIP where
nonprofits exist but none offer membership, volunteering, events, or civic
action (n > 0 and civic_org_sum == 0).

Inputs
    raw_data/mapagora_full/zcta_counts_cov.csv   run ./get_full_data.sh first
    Census 2020 cartographic boundaries          downloaded once to raw_data/geo/

Outputs (outputs/civic_cold_spots/)
    cold_spots_map.png        LISA cluster map, lower 48 + DC
    civic_deserts_map.png     one dot per civic-desert ZIP, all 50 states + DC
    cold_spot_profile.png     who lives in cold spots vs. the rest
    civic_cold_spots.html     interactive map (cold spots, hot spots, deserts)
    zip_results.csv           every ZIP: rates, LISA statistic, p-value, cluster
    summary.txt               headline numbers

Run from the project root (uses the project .venv):
    .venv/bin/pip install -r scripts/requirements.txt
    .venv/bin/python scripts/civic_cold_spots.py
"""

from pathlib import Path
import urllib.request
import warnings

import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from libpysal.weights import KNN, Queen  # noqa: E402
from libpysal.weights.util import attach_islands  # noqa: E402
from esda.moran import Moran_Local_Rate, Moran_Rate  # noqa: E402
import folium  # noqa: E402

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

# ---- Parameters ---------------------------------------------------------------
MIN_POP = 100        # "residential" ZIP: at least this many residents (ACS)
PERMUTATIONS = 999   # conditional permutations for LISA pseudo p-values
ALPHA = 0.05         # significance level for cluster membership
SEED = 20250101      # makes permutation p-values reproducible
PROJ = "EPSG:5070"   # USA Contiguous Albers Equal Area (meters)

ROOT = Path(__file__).resolve().parents[1]
ZIP_CSV = ROOT / "raw_data" / "mapagora_full" / "zcta_counts_cov.csv"
GEO_DIR = ROOT / "raw_data" / "geo"
OUT = ROOT / "outputs" / "civic_cold_spots"

CENSUS = "https://www2.census.gov/geo/tiger/GENZ2020/shp"
ZCTA_ZIP = "cb_2020_us_zcta520_500k.zip"
STATE_ZIP = "cb_2020_us_state_20m.zip"

NOT_STATES = {"PR", "VI", "GU", "AS", "MP"}
NON_CONTIGUOUS = {"AK", "HI"} | NOT_STATES

# ---- Colors (validated: blue/red pass CVD and contrast checks) ---------------
COLD = "#2a78d6"     # cold spot / civic desert
HOT = "#e34948"      # hot spot
CONTEXT = "#d4d3cf"  # analyzed, not in a cluster
NODATA = "#efeeea"   # not analyzed (few residents or no MapAgora record)
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT2 = "#52514e"

SOURCE = ("Source: MapAgora (Kim, de Vries & Han 2025), doi:10.7910/DVN/IRCA7C; "
          "Census 2020 ZCTA boundaries.")


def download(name: str) -> Path:
    """Download a Census cartographic boundary file once and cache it."""
    GEO_DIR.mkdir(parents=True, exist_ok=True)
    path = GEO_DIR / name
    if not path.exists():
        print(f"Downloading {name} ...")
        tmp = path.with_suffix(".part")
        urllib.request.urlretrieve(f"{CENSUS}/{name}", tmp)
        tmp.rename(path)
    return path


def round_coords(geoms, decimals=4):
    """Round coordinates (~10 m) to keep the interactive map's file small."""
    return gpd.GeoSeries(
        shapely.transform(geoms.values, lambda c: np.round(c, decimals)),
        index=geoms.index, crs=geoms.crs)


def load_data():
    if not ZIP_CSV.exists():
        raise SystemExit("ZIP-level data not found. Run ./get_full_data.sh first.")

    z = pd.read_csv(ZIP_CSV, dtype={"ZCTA": str})
    z["desert"] = (z["n"] > 0) & (z["civic_org_sum"] == 0)

    zcta = gpd.read_file(f"zip://{download(ZCTA_ZIP)}")[["ZCTA5CE20", "geometry"]]
    zcta = zcta.rename(columns={"ZCTA5CE20": "ZCTA"}).merge(z, on="ZCTA", how="left")

    states = gpd.read_file(f"zip://{download(STATE_ZIP)}")
    states = states[~states["STUSPS"].isin(NOT_STATES)]
    return z, zcta, states


def run_lisa(zcta: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Local Moran's I on Empirical Bayes-standardized civic opportunity rates."""
    res = zcta[
        zcta["TotalPopulation"].ge(MIN_POP)
        & zcta["state"].notna()
        & ~zcta["state"].isin(NON_CONTIGUOUS)
    ].to_crs(PROJ).reset_index(drop=True)

    w = Queen.from_dataframe(res, use_index=False, silence_warnings=True)
    if w.islands:  # ZIPs with no touching neighbor: link to their nearest one
        w = attach_islands(w, KNN.from_dataframe(res, k=1, use_index=False))
    w.transform = "r"

    events = res["civic_opp_sum"].to_numpy(dtype=float)
    base = res["TotalPopulation"].to_numpy(dtype=float)

    glob = Moran_Rate(events, base, w, adjusted=True, permutations=PERMUTATIONS)
    lisa = Moran_Local_Rate(events, base, w, adjusted=True,
                            permutations=PERMUTATIONS, seed=SEED)

    quad = pd.Series(lisa.q).map({1: "Hot spot", 2: "Low among high",
                                  3: "Cold spot", 4: "High among low"})
    res["opp_per_10k"] = events / base * 1e4
    res["local_i"] = lisa.Is
    res["p_value"] = lisa.p_sim
    res["cluster"] = np.where(lisa.p_sim < ALPHA, quad, "Not significant")
    res.attrs.update(global_i=glob.I, global_p=glob.p_sim,
                     national_rate=events.sum() / base.sum() * 1e4,
                     n_islands=len(Queen.from_dataframe(
                         res, use_index=False, silence_warnings=True).islands))
    return res


def style_axes(ax, title, subtitle):
    """Title + subtitle anchored to the figure's top-left, clear of the map."""
    ax.set_axis_off()
    fig = ax.figure
    fig.text(0.02, 0.975, title, fontsize=16, fontweight="bold", color=TEXT, va="top")
    fig.text(0.02, 0.935, subtitle, fontsize=11, color=TEXT2, va="top")


def plot_cold_spots(res, states, out):
    lower48 = states[~states["STUSPS"].isin(NON_CONTIGUOUS)].to_crs(PROJ)
    colors = res["cluster"].map({"Cold spot": COLD, "Hot spot": HOT}).fillna(CONTEXT)

    fig = plt.figure(figsize=(12, 8), facecolor=SURFACE)
    ax = fig.add_axes([0, 0.06, 1, 0.84])
    lower48.plot(ax=ax, color=NODATA, linewidth=0)
    res.plot(ax=ax, color=colors, linewidth=0)
    lower48.boundary.plot(ax=ax, color=SURFACE, linewidth=0.6)

    n_cold = (res["cluster"] == "Cold spot").sum()
    pop_cold = res.loc[res["cluster"] == "Cold spot", "TotalPopulation"].sum()
    style_axes(ax, f"{n_cold:,} ZIP codes form civic cold spots",
               f"Clusters of ZIP codes with low civic opportunity per resident, "
               f"home to {pop_cold / 1e6:.1f} million people (lower 48 + DC)")
    ax.legend(handles=[
        Patch(color=COLD, label="Cold spot: low, surrounded by low"),
        Patch(color=HOT, label="Hot spot: high, surrounded by high"),
        Patch(color=CONTEXT, label="Not in a cluster"),
        Patch(color=NODATA, label=f"Not analyzed (<{MIN_POP} residents or no data)"),
    ], loc="lower left", frameon=False, fontsize=9, labelcolor=TEXT2)
    fig.text(0.02, 0.02,
             f"Local Moran's I on Empirical Bayes-smoothed civic opportunity rates, "
             f"queen contiguity, {PERMUTATIONS} permutations, p < {ALPHA}.\n{SOURCE}",
             fontsize=8, color=TEXT2)
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)


def plot_deserts(zcta, z, states, out):
    pts = zcta[zcta["desert"].eq(True) & ~zcta["state"].isin(NOT_STATES)].copy()
    pts["geometry"] = pts.representative_point()
    pts = gpd.sjoin(pts, states[["geometry"]], predicate="within").drop(columns="index_right")
    st = states.copy()

    # Inset-free layout: draw the lower 48, then Alaska and Hawaii in small axes
    fig = plt.figure(figsize=(12, 8), facecolor=SURFACE)
    ax = fig.add_axes([0, 0.08, 1, 0.82])
    for code, rect, crs in [("AK", [0.02, 0.10, 0.22, 0.22], "EPSG:3338"),
                            ("HI", [0.24, 0.10, 0.12, 0.12], "ESRI:102007")]:
        iax = fig.add_axes(rect)
        st[st["STUSPS"] == code].to_crs(crs).plot(ax=iax, color=CONTEXT, linewidth=0)
        p = pts[pts["state"] == code].to_crs(crs)
        if len(p):
            p.plot(ax=iax, color=COLD, markersize=2, linewidth=0)
        iax.set_axis_off()
        if code == "AK":
            iax.set_xlim(-2.3e6, 1.6e6)
    l48 = st[~st["STUSPS"].isin(NON_CONTIGUOUS)].to_crs(PROJ)
    l48.plot(ax=ax, color=CONTEXT, edgecolor=SURFACE, linewidth=0.6)
    pts[~pts["state"].isin(NON_CONTIGUOUS)].to_crs(PROJ).plot(
        ax=ax, color=COLD, markersize=2.2, linewidth=0, alpha=0.85)

    n_all = int(z["desert"].sum())
    not_drawn = n_all - len(pts)
    style_axes(ax, f"{n_all:,} ZIP codes are civic deserts",
               f"{100 * z['desert'].mean():.1f}% of ZIP codes with nonprofits: "
               f"nonprofits exist, but none offer membership, volunteering, events, or civic action")
    ax.legend(handles=[Line2D([], [], marker="o", color=COLD, linestyle="",
                              markersize=6, label="Civic desert ZIP code (one dot each)")],
              loc="upper right", frameon=False, fontsize=9, labelcolor=TEXT2)
    fig.text(0.02, 0.02,
             f"{not_drawn:,} desert ZIP codes have no 2020 ZCTA boundary (e.g. P.O.-box-only "
             f"ZIPs) or lie outside the 50 states + DC and are not drawn.\n{SOURCE}",
             fontsize=8, color=TEXT2)
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    return not_drawn


def plot_profile(res, out):
    """Dumbbell: median of each community indicator, cold spots vs. elsewhere."""
    measures = {"POV150": "Below 150% of poverty line",
                "BROAD": "No broadband",
                "NOHSDP": "No high school diploma",
                "UNEMP": "Unemployed",
                "REMNRTY": "Racial/ethnic minority"}
    cold = res["cluster"] == "Cold spot"
    rows = [(label, res.loc[cold, col].median(), res.loc[~cold, col].median())
            for col, label in measures.items()]

    fig, ax = plt.subplots(figsize=(9, 4.6), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    for i, (label, c, o) in enumerate(rows):
        ax.plot([o, c], [i, i], color=CONTEXT, linewidth=2, zorder=1)
        ax.scatter(o, i, s=80, color=TEXT2, zorder=2, edgecolor=SURFACE, linewidth=2)
        ax.scatter(c, i, s=80, color=COLD, zorder=3, edgecolor=SURFACE, linewidth=2)
        ax.text(max(c, o) + 1, i, f"{c:.1f}% vs {o:.1f}%", va="center",
                fontsize=9, color=TEXT2)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows], color=TEXT, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlim(0, max(max(r[1], r[2]) for r in rows) * 1.35)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.tick_params(axis="x", colors=TEXT2, labelsize=9, length=0)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color="#e8e7e3", linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.legend(handles=[
        Line2D([], [], marker="o", color=COLD, linestyle="", markersize=8, label="Cold-spot ZIP codes"),
        Line2D([], [], marker="o", color=TEXT2, linestyle="", markersize=8, label="All other ZIP codes"),
    ], loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False,
       fontsize=9, labelcolor=TEXT2, borderaxespad=0.3, handletextpad=0.3)
    ax.set_title("Who lives in civic cold spots?", loc="left", fontsize=14,
                 fontweight="bold", color=TEXT, pad=30)
    fig.text(0.01, -0.02, "Median share of residents (ACS, via MapAgora). Residential "
             "ZIP codes in the lower 48 + DC.", fontsize=8, color=TEXT2)
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    return rows


def interactive_map(res, zcta, out):
    def fmt(df):
        df = df.copy()
        df["pop_fmt"] = df["TotalPopulation"].map(lambda v: f"{v:,.0f}" if pd.notna(v) else "n/a")
        df["rate_fmt"] = df["opp_per_10k"].map(lambda v: f"{v:.1f}") if "opp_per_10k" in df else ""
        return df

    m = folium.Map(location=[38.5, -96], zoom_start=4, tiles="CartoDB positron",
                   prefer_canvas=True)
    for name, color, show in [("Cold spot", COLD, True), ("Hot spot", HOT, False)]:
        sub = fmt(res[res["cluster"] == name]).to_crs(4326)
        sub["geometry"] = round_coords(sub.simplify(0.01, preserve_topology=True))
        folium.GeoJson(
            sub[["ZCTA", "state", "pop_fmt", "n", "rate_fmt", "geometry"]],
            name=f"{name}s ({len(sub):,} ZIPs)", show=show,
            style_function=lambda _, c=color: {"fillColor": c, "color": c,
                                               "weight": 0.4, "fillOpacity": 0.55},
            tooltip=folium.GeoJsonTooltip(
                ["ZCTA", "state", "pop_fmt", "n", "rate_fmt"],
                ["ZIP", "State", "Residents", "Nonprofits", "Civic opportunities per 10k residents"]),
        ).add_to(m)

    deserts = zcta[zcta["desert"].eq(True)].copy()
    deserts["geometry"] = deserts.representative_point()
    deserts = fmt(deserts).to_crs(4326)
    deserts["geometry"] = round_coords(deserts.geometry)
    deserts["n"] = deserts["n"].astype(int)
    folium.GeoJson(
        deserts[["ZCTA", "state", "pop_fmt", "n", "geometry"]],
        name=f"Civic deserts ({len(deserts):,} ZIPs)", show=True,
        marker=folium.CircleMarker(radius=3, weight=0.6, color=SURFACE,
                                   fill=True, fill_color=COLD, fill_opacity=0.9),
        tooltip=folium.GeoJsonTooltip(["ZCTA", "state", "pop_fmt", "n"],
                                      ["ZIP", "State", "Residents", "Nonprofits (none offer civic opportunity)"]),
    ).add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    m.get_root().html.add_child(folium.Element(
        f"<div style='position:fixed;bottom:24px;left:12px;z-index:9999;max-width:280px;"
        f"background:{SURFACE};padding:10px 12px;border-radius:8px;"
        f"box-shadow:0 1px 4px rgba(0,0,0,.2);font:13px/1.4 system-ui,sans-serif;color:{TEXT}'>"
        f"<b style='font-size:15px'>Civic cold spots &amp; deserts</b><br>"
        f"<span style='color:{TEXT2}'><b style='color:{COLD}'>Cold spots</b>: clusters of ZIP codes "
        f"with low civic opportunity per resident. <b style='color:{COLD}'>Dots</b>: civic deserts, "
        f"where nonprofits exist but none offer civic opportunity.</span><br>"
        f"<span style='color:{TEXT2};font-size:11px'>Source: MapAgora, doi:10.7910/DVN/IRCA7C</span></div>"))
    m.get_root().header.add_child(folium.Element("<title>Civic Cold Spots</title>"))
    m.save(out)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    z, zcta, states = load_data()

    print("Running Local Moran's I (this takes a minute)...")
    res = run_lisa(zcta)

    plot_cold_spots(res, states, OUT / "cold_spots_map.png")
    not_drawn = plot_deserts(zcta, z, states, OUT / "civic_deserts_map.png")
    profile = plot_profile(res, OUT / "cold_spot_profile.png")
    interactive_map(res, zcta, OUT / "civic_cold_spots.html")

    cols = ["ZCTA", "state", "TotalPopulation", "n", "civic_org_sum", "civic_opp_sum",
            "opp_per_10k", "local_i", "p_value", "cluster"]
    table = z[["ZCTA", "desert"]].merge(res[cols], on="ZCTA", how="left")
    table["cluster"] = table["cluster"].fillna("Not analyzed")
    table.sort_values("ZCTA").to_csv(OUT / "zip_results.csv", index=False)

    cold = res["cluster"] == "Cold spot"
    a = res.attrs
    lines = [
        f"ZIP codes in MapAgora:                     {len(z):,}",
        f"Civic deserts (all states):                {int(z['desert'].sum()):,} "
        f"({100 * z['desert'].mean():.1f}%); {not_drawn:,} not mappable",
        f"Analyzed for clustering (lower 48 + DC, >= {MIN_POP} residents): {len(res):,}",
        f"National rate: {a['national_rate']:.1f} civic opportunities per 10k residents",
        f"Global Moran's I (EB rate): {a['global_i']:.3f} (pseudo p = {a['global_p']:.3f})",
        "Clusters (p < {}): {}".format(ALPHA, res["cluster"].value_counts().to_dict()),
        f"Residents in cold spots: {res.loc[cold, 'TotalPopulation'].sum():,.0f} "
        f"({100 * res.loc[cold, 'TotalPopulation'].sum() / res['TotalPopulation'].sum():.1f}%)",
        f"Civic deserts inside cold spots: {int(res.loc[cold, 'desert'].sum()):,} "
        f"of {int(res['desert'].sum()):,} analyzed deserts",
        f"ZIPs with no touching neighbor (linked to nearest): {a['n_islands']}",
        "Community profile (median %, cold spots vs. others):",
        *[f"  {label:<28} {c:5.1f}  vs {o:5.1f}" for label, c, o in profile],
    ]
    (OUT / "summary.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nOutputs in {OUT}")


if __name__ == "__main__":
    main()
