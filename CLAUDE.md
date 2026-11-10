# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project direction

### Audiences (design for them from the first screen)

Four primary audiences: **foundations** (where/how to invest), **universities** (community partnerships and engagement), **state and local governments** (strategic tool for civic engagement offices), **organizers** (understand their community, bring others in). **Community members** are reached through these audiences via shared links, printed profiles and conversation guides; they are not a separate path on the landing page. See the README table for each audience's goals and outputs.

### Landing page

1. One-sentence statement of what the tool is, then a search box: "Enter a ZIP code, town, or county".
2. Four audience doors ("I work at a foundation / university / government agency" / "I'm an organizer"), each with one line on what they'll get, leading to a pre-set view: foundations → compare places / region profile; universities → area around campus; governments → jurisdiction view; organizers → place page + conversation guide.
3. "What you'll learn" strip: the four kinds of opportunity and the organization types, shown with one real example.
4. "What the data can and can't tell you" up front (de-identified, one snapshot, website-based, about 38% of providers untyped).
5. Footer: methods, data source and citation, about.

### Overview

A static civic engagement tool that meets people where they are: its audiences learn the structure of civic opportunity in their county and ZIP code (what kinds of opportunity exist, to what extent, and provided by what kinds of organizations), compare with similar places, and use that to start conversations. Built on the MapAgora datasets (SNF Agora Institute, Johns Hopkins).

**Learning, not polling.** Voting is not part of the plan (user decision); don't emphasize or add it. **No moderator role:** the public never submits free text (no posts, comments or user listings). So the site is fully static: no accounts, no database, no Firebase.

Place page structure (reads top to bottom): plain-language findings → who provides what (org type × opportunity grid vs. peers) → compared with places like yours (10 peers) → observation cards → print the profile / conversation guide.

**Observation cards, not action cards.** Claim only what the data supports. Each card has (1) a comparison with peers in plain words ("fewer youth organizations here list civic action on their websites than in 10 similar places"), (2) how confident we can be (number of organizations behind it, share untyped), (3) a discussion question that hands the "why" and "what next" to the community. Never say a gap is a "need", never suggest specific partners (data is de-identified, and 0 means "no evidence on its website", not "doesn't offer it"), and never claim a strategy "worked" (MapAgora is one snapshot with no outcomes).

Planned features:
- Entry by ZIP code, town or county, plus the four audience doors on the landing page (see above).
- Area profiles: any set of ZIPs/counties (campus neighborhood, city, service region); selection lives in the URL.
- Equity view: opportunity against poverty, broadband, education, minority share.
- Gap ranking with filters; CSV and GeoJSON export.
- Organization types present locally that list no opportunity online: show as a fact with the website caveat, not as "potential partners".
- Optional, separate from the data: curated examples written and sourced by the team as repo files, labeled as examples, not evidence.
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
