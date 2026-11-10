"""Local Moran's I (LISA) on Empirical Bayes-standardized rates: civic cold and hot spots."""

import numpy as np
import pandas as pd
import geopandas as gpd
from libpysal.weights import KNN, Queen
from libpysal.weights.util import attach_islands
from esda.moran import Moran_Local_Rate, Moran_Rate

from . import config as C

LABELS = {1: "Hot spot", 2: "Low among high", 3: "Cold spot", 4: "High among low"}


def lisa_rate(gdf: gpd.GeoDataFrame, events: str, base: str) -> pd.DataFrame:
    """Cluster label for each row of `gdf` (already filtered to the analysis set).

    Queen contiguity; places with no touching neighbor are linked to their
    nearest one. Returns columns local_i, p_value, cluster, indexed like gdf.
    Global Moran's I and its p-value are stored in .attrs.
    """
    g = gdf.to_crs(C.PROJ).reset_index(drop=True)
    w = Queen.from_dataframe(g, use_index=False, silence_warnings=True)
    n_islands = len(w.islands)
    if n_islands:
        w = attach_islands(w, KNN.from_dataframe(g, k=1, use_index=False))
    w.transform = "r"

    e = g[events].to_numpy(dtype=float)
    b = g[base].to_numpy(dtype=float)
    glob = Moran_Rate(e, b, w, adjusted=True, permutations=C.PERMUTATIONS)
    lisa = Moran_Local_Rate(e, b, w, adjusted=True, permutations=C.PERMUTATIONS, seed=C.SEED)

    quad = pd.Series(lisa.q).map(LABELS)
    out = pd.DataFrame({
        "local_i": lisa.Is,
        "p_value": lisa.p_sim,
        "cluster": np.where(lisa.p_sim < C.ALPHA, quad, "Not significant"),
    }, index=gdf.index)
    out.attrs.update(global_i=float(glob.I), global_p=float(glob.p_sim), n_islands=n_islands)
    return out
