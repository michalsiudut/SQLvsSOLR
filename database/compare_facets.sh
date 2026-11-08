#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "$ROOT/database/compare_facets.py" \
  --sql "$ROOT/sql_facet_counts.csv" \
  --solr "$ROOT/solr_facet_counts.csv" \
  --output "$ROOT/facet_comparison.csv"

python3 "$ROOT/database/plot_facets.py" \
  --comparison "$ROOT/facet_comparison.csv" \
  --sql-timing "$ROOT/sql_facets_results.csv" \
  --solr-timing "$ROOT/solr_facets_results.csv" \
  --output "$ROOT/facet_comparison.svg"
