#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-lab3-postgres}"
POSTGRES_DB="${POSTGRES_DB:-lab3}"
POSTGRES_USER="${POSTGRES_USER:-lab3}"
SOLR_URL="${SOLR_URL:-http://localhost:8983/solr}"
SOLR_CORE="${SOLR_CORE:-wikipedia}"
DOCKER_COMMAND="${DOCKER_COMMAND:-sudo docker}"
read -r -a DOCKER_ARGS <<< "$DOCKER_COMMAND"
TEST_ID="-$(date +%s%N)"

psql_exec() {
  "${DOCKER_ARGS[@]}" exec "$POSTGRES_CONTAINER" \
    psql -X -q -A -t -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$1"
}

if [[ "$(psql_exec "SELECT to_regclass('public.solr_sync_outbox') IS NOT NULL
  AND EXISTS (SELECT 1 FROM pg_trigger
    WHERE tgname='wikipedia_articles_solr_sync' AND NOT tgisinternal)")" != "t" ]]; then
  echo "Outbox migration or wikipedia_articles_solr_sync trigger is missing." >&2
  exit 1
fi

cleanup() {
  trap - EXIT
  psql_exec "DELETE FROM wikipedia_articles WHERE id=$TEST_ID"
  python3 "$ROOT/solr/sync_outbox.py" --docker-command "$DOCKER_COMMAND" \
    --container "$POSTGRES_CONTAINER" \
    --database "$POSTGRES_DB" --user "$POSTGRES_USER" --solr-url "$SOLR_URL" \
    --core "$SOLR_CORE"
}
trap cleanup EXIT

verify_title() {
  local expected="$1"
  local result
  result="$(curl --fail --silent --show-error --get \
    "$SOLR_URL/$SOLR_CORE/get" \
    --data-urlencode "id=$TEST_ID" \
    --data-urlencode 'wt=json')"
  EXPECTED_TITLE="$expected" RESULT_JSON="$result" \
    python3 -c 'import json, os; doc=json.loads(os.environ["RESULT_JSON"]).get("doc"); expected=os.environ["EXPECTED_TITLE"]; actual=None if doc is None else doc.get("title"); expected=None if expected=="__MISSING__" else expected; assert actual == expected, f"expected {expected!r}, got {actual!r}"'
}

psql_exec "INSERT INTO wikipedia_articles
  (id,title,text,topic,article_type,date_modified,search_vector)
  VALUES ($TEST_ID,'Solr sync test before update','temporary test document','other','general',timestamp '2026-01-01',to_tsvector('english','temporary test document'))"
python3 "$ROOT/solr/sync_outbox.py" --docker-command "$DOCKER_COMMAND" \
  --container "$POSTGRES_CONTAINER" \
  --database "$POSTGRES_DB" --user "$POSTGRES_USER" --solr-url "$SOLR_URL" \
  --core "$SOLR_CORE"
verify_title 'Solr sync test before update'

psql_exec "UPDATE wikipedia_articles
  SET title='Solr sync test after update'
  WHERE id=$TEST_ID"
python3 "$ROOT/solr/sync_outbox.py" --docker-command "$DOCKER_COMMAND" \
  --container "$POSTGRES_CONTAINER" \
  --database "$POSTGRES_DB" --user "$POSTGRES_USER" --solr-url "$SOLR_URL" \
  --core "$SOLR_CORE"
verify_title 'Solr sync test after update'

psql_exec "DELETE FROM wikipedia_articles WHERE id=$TEST_ID"
python3 "$ROOT/solr/sync_outbox.py" --docker-command "$DOCKER_COMMAND" \
  --container "$POSTGRES_CONTAINER" \
  --database "$POSTGRES_DB" --user "$POSTGRES_USER" --solr-url "$SOLR_URL" \
  --core "$SOLR_CORE"
verify_title '__MISSING__'

printf 'INSERT, UPDATE and DELETE synchronization passed for test id %s.\n' "$TEST_ID"
