#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
CONTAINER="${SOLR_CONTAINER:-lab3-solr}"
CORE="${SOLR_CORE:-wikipedia}"
SOLR_URL="${SOLR_URL:-http://localhost:8983/solr}"

docker exec "$CONTAINER" /opt/solr/bin/solr create -c "$CORE" -d _default

curl --fail --silent --show-error \
  -H 'Content-Type: application/json' \
  --data-binary "@$ROOT/solr/schema.json" \
  "$SOLR_URL/$CORE/schema"

curl --fail --silent --show-error \
  -X POST \
  -H 'Content-Type: application/json' \
  --data '{"set-user-property":{"update.autoCreateFields":"false"}}' \
  "$SOLR_URL/$CORE/config"

printf '\nSolr core "%s" is configured at %s/%s\n' "$CORE" "$SOLR_URL" "$CORE"
