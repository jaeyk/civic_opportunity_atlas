# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project direction

A static civic engagement tool that meets people where they are: residents, organizers, universities, state and local governments, and foundations learn the structure of civic opportunity in their county and ZIP code (what kinds of opportunity exist, to what extent, and provided by what kinds of organizations) and find strategies that worked in similar places. Built on the MapAgora datasets (SNF Agora Institute, Johns Hopkins).

**Learning, not polling.** Voting is not part of the plan (user decision); don't emphasize or add it. **No moderator role:** the public never submits free text (no posts, comments or user listings). So the site is fully static: no accounts, no database, no Firebase.

Place page structure (reads top to bottom): plain-language findings → who provides what (org type × opportunity grid vs. peers) → compared with places like yours (10 peers) → action cards (gap, local org types that could fill it, curated strategies) → print the profile / conversation guide.

Planned features:
- Entry by ZIP code or town name; optional "What are you trying to do?" paths per audience (find partners, decide where to invest, site a program, find who to organize with).
- Area profiles: any set of ZIPs/counties (campus neighborhood, city, service region); selection lives in the URL.
- Equity view: opportunity against poverty, broadband, education, minority share.
- Gap ranking with filters; CSV and GeoJSON export.
- "Present but inactive" organization types (present, offering nothing): potential partners.
- Curated strategy library: written by the team as files in the repo, tagged by place context.
- Printable one-page profile, a conversation guide (discussion questions generated from the place's findings), a QR code per place, and an embeddable widget.
- Meeting people where they are: phone-first, small pages, works on slow connections, plain language, Spanish next.

- **Language:** Python for the data pipeline and site build. Don't add R.
- **Hosting:** GitHub Pages, which serves static files only. Python builds static pages and JSON; the browser handles interactivity.
- **Old dashboard (don't repeat):** exploration-first national map with a 1-5 index, primary-org-type map, sortable table, state/county compare pages, Civic Quest game. The new tool is answer-first and action-oriented instead.
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
