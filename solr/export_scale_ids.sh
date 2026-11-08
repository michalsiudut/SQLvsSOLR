#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-lab3-postgres}"

sudo docker exec "$POSTGRES_CONTAINER" \
  psql -q -U lab3 -d lab3 -At \
  -c 'SELECT id FROM wikipedia_articles_50000 ORDER BY id' \
  > "$ROOT/solr/wikipedia_50000_ids.txt"

sudo docker exec "$POSTGRES_CONTAINER" \
  psql -q -U lab3 -d lab3 -At \
  -c 'SELECT id FROM wikipedia_articles_250000 ORDER BY id' \
  > "$ROOT/solr/wikipedia_250000_ids.txt"

printf 'Exported exact SQL IDs:\n'
wc -l "$ROOT/solr/wikipedia_50000_ids.txt" \
  "$ROOT/solr/wikipedia_250000_ids.txt"
