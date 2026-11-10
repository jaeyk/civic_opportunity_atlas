# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project direction

A static web tool where community members, organizers and foundations (1) learn the structure of civic opportunity in their county and ZIP code (what kinds of opportunity exist, to what extent, and provided by what kinds of organizations), (2) vote on which kinds of opportunity their community needs, and (3) find strategies that worked in similar places. Built on the MapAgora datasets (SNF Agora Institute, Johns Hopkins).

**No moderator role (user decision): the public never submits free text.** No posts, comments, user-written strategies or user-added listings. Anything that would need moderation is out of scope.

Planned features:
- Place profiles (county, ZIP): what kinds of opportunity exist, how much, by which organization types, vs. 10 peer places.
- Needs voting from a fixed list of categories (opportunity × organization type), anonymous, one vote per person per choice; results shown next to the data ("requests vs. what exists").
- Gap finder: places below their peers on a given opportunity/type; filters; CSV export.
- "Present but inactive" organization types (organizations present but offering nothing).
- Service-area profiles: a set of ZIPs/counties combined; the selection lives in the URL.
- Printable one-page brief per place; embeddable profile widget.
- Curated strategy library: written by the team as files in the repo, tagged by place context, surfaced as "worked in places like yours".

- **Language:** Python for the data pipeline and site build. Don't add R.
- **Hosting:** GitHub Pages, which serves static files only, so no Django or other server. Python builds static pages and JSON; the browser handles interactivity.
- **Votes only:** Firebase on the free Spark plan, called from the browser: Firestore + Firebase Anonymous Auth + App Check (reCAPTCHA). No handles, no accounts with names or emails. Cloud Functions are not available on Spark, so integrity lives in `firestore.rules`: a vote doc ID is `{placeId}_{categoryId}_{uid}`, a category must be on the fixed list, and the tally doc must change by exactly the vote in the same batch (`getAfter()`). Publish tallies only, never who voted. Watch the read quota (50k reads/day): read tally docs, not individual votes, and cache.
- **Data use:** votes are NOT used for research, so no IRB is needed. Ship a short plain-language privacy note.
- The old Quarto/R dashboard and Flask prototype live on the `archive/quarto-dashboard` branch (tag `quarto-dashboard-final`). Mine them for logic, but don't restore them to main.

## Commands

```bash
.venv/bin/pip install -r requirements.txt
./get_full_data.sh                      # fetch org/ZIP-level data into raw_data/mapagora_full/
.venv/bin/python -m pipeline.build      # build tables -> data/processed/ (~1 min)
.venv/bin/python -m pytest tests        # unit tests + checks on built tables
```

## Pipeline (`pipeline/`)

- `providers.py` is the core: from the org-level file, compute place × org type × opportunity counts ("what kinds, how much, by whom").
- `metrics.py` (Empirical Bayes rates, percentiles), `peers.py` (10 nearest places on context: log population, RUCC, SVI measures; never on civic outcomes), `clusters.py` (LISA cold/hot spots), `geography.py` (ZIP→county crosswalk, rurality), `sources.py` (loaders + cached Census downloads), `build.py` (orchestration, writes parquet + `build_meta.json`).
- Civic deserts were deliberately removed (user decision). Don't reintroduce them.

## Data

- `raw_data/cnty_counts_cov.csv` (one row per county) and `raw_data/mapagora_full/zcta_counts_cov.csv` (one row per ZIP) hold civic opportunity counts, per-capita measures (`*_normalized` = per 100,000 residents) and ACS/SVI covariates.
- `raw_data/cnty_civic_org_type.csv` / `zcta_civic_org_type.csv` hold organization-type breakdowns.
- `raw_data/mapagora_full/ind_org_df.parquet` holds 1.77M de-identified orgs. `predicted` is the ML type (15 classes, about 50% missing). Location is ZIP/county only.
- **Counting rule (reproduces the published count files: ZIP 100%, county 99%+):** drop `is_po == 1`, merge orgs sharing `grouping_value` within the place, and a merged unit offers an opportunity if ANY chapter does (`max`). The pipeline uses this one rule everywhere.
- The published type file used a different rule (no network merge: `opp_binary == 1 & is_po == 0 & predicted not NA`), so its type counts differ slightly from ours. Ours are internally consistent with the totals.
- Untyped providers are kept as "Type not identified" (about 38% of providers). Always show that share; never hide it.
- MapAgora's ZIP file has 3 ZCTAs duplicated with a stray one-org row in another state; `sources.zcta_counts()` merges them.
- Per-capita rates are unstable for small populations; smooth them (Empirical Bayes) before ranking or mapping.
- `raw_data/mapagora_full/`, `raw_data/geo/`, `data/processed/` and `outputs/` are git-ignored and regenerated.

## Deployment

The new tool will be served by GitHub Pages from a static build. The old Quarto site was retired, and Pages needs re-enabling once the new build exists. There is no GitHub Actions workflow: the user chose not to use Actions for deployment.
