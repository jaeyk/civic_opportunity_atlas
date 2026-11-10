"""The site must claim only what the data supports (see CLAUDE.md)."""

import json
import random
import re

import pytest

from pipeline import site_data as S

FORBIDDEN = re.compile(r"\b(need|needs|needed|partner|partners|worked|should|lack|lacks|"
                       r"desert|deserts|gap to fill)\b", re.I)


def _sample(n=1500):
    files = sorted((S.DATA / "p").glob("*.json"))
    if not files:
        pytest.skip("run `python -m pipeline.site_data` first")
    random.seed(7)
    return [json.loads(f.read_text()) for f in random.sample(files, min(n, len(files)))]


def test_no_forbidden_claims_in_generated_text():
    for rec in _sample():
        texts = rec["findings"] + [c[k] for c in rec["observations"]
                                   for k in ("title", "text", "question")]
        for t in texts:
            assert not FORBIDDEN.search(t), (rec["id"], t)


def test_every_card_has_confidence_and_question():
    for rec in _sample():
        assert 1 <= len(rec["observations"]) <= 5
        for c in rec["observations"]:
            assert c["confidence"]["level"] in {"low", "moderate", "higher"}
            assert c["question"].endswith("?")


def test_small_places_are_not_compared():
    for rec in _sample():
        if rec["totals"]["any_opp"] < S.MIN_COUNT:
            assert not any("similar places" in f for f in rec["findings"]), rec["id"]
            assert rec["observations"][0]["kind"] == "small", rec["id"]


def test_grid_matches_totals():
    col = S.OPPS.index("Any civic opportunity")
    for rec in _sample(300):
        assert sum(row[col] for row in rec["grid"]["n"]) == rec["totals"]["any_opp"]
