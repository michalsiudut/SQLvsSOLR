#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "$ROOT/database/compare_facets.py" \
  --sql "$ROOT/csv/sql_facet_counts.csv" \
  --solr "$ROOT/csv/solr_facet_counts.csv" \
  --output "$ROOT/csv/facet_comparison.csv"

python3 "$ROOT/database/plot_facets.py" \
  --comparison "$ROOT/csv/facet_comparison.csv" \
  --sql-timing "$ROOT/csv/sql_facets_results.csv" \
  --solr-timing "$ROOT/csv/solr_facets_results.csv" \
  --output "$ROOT/svg/facet_comparison.svg"
