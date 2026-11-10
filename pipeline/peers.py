"""Peer places: communities with a similar context, used for fair comparisons.

Peers are matched on context (population size, rurality, and social vulnerability
measures), never on civic opportunity itself, so "places like yours" can show
what a similar community has that yours doesn't.
"""

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from . import config as C


def find_peers(df: pd.DataFrame, id_col: str, eligible: pd.Series, k: int = C.N_PEERS) -> pd.DataFrame:
    """k nearest peers for each eligible place on standardized context features.

    Features: log10 population, RUCC code, and the CONTEXT percentages.
    Returns long format: place_id, peer_id, rank (1 = most similar), distance.
    """
    feats = ["log_pop", "rucc", *C.CONTEXT]
    x = df.loc[eligible].assign(log_pop=lambda d: np.log10(d["TotalPopulation"]))
    x = x.dropna(subset=feats)
    z = (x[feats] - x[feats].mean()) / x[feats].std(ddof=0)

    tree = cKDTree(z.to_numpy())
    dist, idx = tree.query(z.to_numpy(), k=k + 1)   # first hit is the place itself
    ids = x[id_col].to_numpy()

    rows = []
    for i, place in enumerate(ids):
        hits = [(ids[j], d) for j, d in zip(idx[i], dist[i]) if ids[j] != place][:k]
        rows += [(place, peer, r + 1, d) for r, (peer, d) in enumerate(hits)]
    return pd.DataFrame(rows, columns=["place_id", "peer_id", "rank", "distance"])


def peer_comparison(values: pd.DataFrame, peers: pd.DataFrame, id_col: str, cols) -> pd.DataFrame:
    """Each place's value next to the median of its peers, for the given columns."""
    v = values.set_index(id_col)[cols]
    med = (peers.join(v, on="peer_id").groupby("place_id")[cols].median()
           .add_suffix("_peer_median"))
    return v.join(med, how="left").reset_index().rename(columns={id_col: "place_id"})
