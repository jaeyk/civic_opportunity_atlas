#!/bin/bash
# Download the MapAgora datasets NOT bundled with the dashboard
# (organization-level and ZIP-level data) from Harvard Dataverse.
# Source: https://doi.org/10.7910/DVN/IRCA7C
# Files land in raw_data/mapagora_full/ (git-ignored; Dataset 1 is large).

set -euo pipefail

OUT_DIR="$(cd "$(dirname "$0")" && pwd)/raw_data/mapagora_full"
API="https://dataverse.harvard.edu/api/access/datafile"
mkdir -p "$OUT_DIR"

# file_id  output_name  [query]
download() {
  local id="$1" name="$2" query="${3:-}"
  if [ -s "$OUT_DIR/$name" ]; then
    echo "Skipping $name (already present)"
    return
  fi
  echo "Downloading $name ..."
  curl -fL --retry 3 -o "$OUT_DIR/$name.part" "$API/$id$query"
  mv "$OUT_DIR/$name.part" "$OUT_DIR/$name"
}

# Dataset 1: organization-level, de-identified nonprofits (~1.7M rows, ~44 MB parquet)
download 11183939 ind_org_df.parquet
# ZIP code (ZCTA)-level aggregated civic opportunity counts
download 11186534 zcta_counts_cov.csv "?format=original"
# ZIP code (ZCTA)-level civic opportunity provider types
download 11186536 zcta_civic_org_type.csv "?format=original"
# Dataset README
download 11542316 README.md

echo "Done. Files in $OUT_DIR:"
ls -lh "$OUT_DIR"
