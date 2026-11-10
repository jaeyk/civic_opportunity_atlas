# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project direction

A static web tool where community members (1) learn the structure of civic opportunity in their county and ZIP code (what kinds of opportunity exist, to what extent, and provided by what kinds of organizations), (2) suggest and vote on the engagement opportunities their community needs, and (3) share strategies across communities. Built on the MapAgora datasets (SNF Agora Institute, Johns Hopkins).

- **Language:** Python for the data pipeline and site build. Don't add R.
- **Hosting:** GitHub Pages, which serves static files only, so no Django or other server. Python builds static pages and JSON; the browser handles interactivity.
- **Writes (suggestions, votes, strategies):** Firebase on the free Spark plan, called from the browser: Firestore + Firebase Auth (Anonymous for users, Google for the moderator) + App Check with reCAPTCHA. Cloud Functions are not available on Spark, so all integrity lives in `firestore.rules`. Votes use doc ID `{postId}_{uid}`, and rules require the post's score to change by exactly the vote delta in the same batch (`getAfter()`). Watch the read quota (50k reads/day): paginate and cache.
- **Community model: Reddit-style and pseudonymous.** Users get an auto-generated handle through anonymous sign-in; no real names; email is optional (only to keep a handle across devices). Each county and ZIP has a board next to its data profile. Posts are "We need…" (suggestions) or "This worked…" (strategies), with up/down votes, comments, and Hot/Top/New sorting. Strategies can be cross-posted between boards. One vote per handle per post, enforced in the database. Publish scores only, never who voted.
- **Pre-moderation (hate-speech filtering):** every post and comment is inserted as `pending`, enforced by Firestore security rules (create only with `status == 'pending'`), not just in the UI. The public sees only `approved` (queries must filter on status, because rules aren't filters); authors see their own pending/denied items. Only users with a doc in the `moderators` collection can change status, and the project owner (Jae Yeon Kim, signed in with Google, not anonymously) is the sole moderator for now. A moderator-only queue page offers Approve / Deny with an optional reason. Moderation is manual only; no automatic hate-speech classifier (user decision). Handles are auto-generated only. Votes are not moderated and count only on approved posts.
- **Abuse mitigation:** a human-check challenge before a new handle is created, rate limits, separate display of votes from new handles, a report button.
- **Data use:** community contributions are NOT used for research, so no IRB is needed. Ship a short plain-language privacy note.
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
