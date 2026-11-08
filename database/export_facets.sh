#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-lab3-postgres}"

sudo docker exec -i "$POSTGRES_CONTAINER" \
  psql -X -q -U lab3 -d lab3 \
  < "$ROOT/database/07_facets_group_by.sql" \
  > "$ROOT/sql_facets_results.csv"

sudo docker exec -i "$POSTGRES_CONTAINER" \
  psql -X -q -U lab3 -d lab3 \
  < "$ROOT/database/08_export_facet_counts.sql" \
  > "$ROOT/sql_facet_counts.csv"

printf 'Wrote SQL timing to %s\n' "$ROOT/sql_facets_results.csv"
printf 'Wrote SQL facet counts to %s\n' "$ROOT/sql_facet_counts.csv"
