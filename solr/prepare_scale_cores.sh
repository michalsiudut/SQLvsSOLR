#!/usr/bin/env bash
set -euo pipefail

CONTAINER="${SOLR_CONTAINER:-lab3-solr}"
SOLR_URL="${SOLR_URL:-http://localhost:8983/solr}"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

for core in wikipedia_50000 wikipedia_250000; do
  docker exec "$CONTAINER" /opt/solr/bin/solr create -c "$core" -d _default
  curl --fail --silent --show-error \
    -H 'Content-Type: application/json' \
    --data-binary "@$ROOT/solr/schema.json" \
    "$SOLR_URL/$core/schema" >/dev/null
  curl --fail --silent --show-error \
    -X POST \
    -H 'Content-Type: application/json' \
    --data '{"set-user-property":{"update.autoCreateFields":"false"}}' \
    "$SOLR_URL/$core/config" >/dev/null
  printf 'Prepared core: %s\n' "$core"
done

printf '\nThe 500000-record dataset uses the existing wikipedia core.\n'
