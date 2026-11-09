#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-lab3-postgres}"
POSTGRES_DB="${POSTGRES_DB:-lab3}"
POSTGRES_USER="${POSTGRES_USER:-lab3}"
DOCKER_COMMAND="${DOCKER_COMMAND:-sudo docker}"
read -r -a DOCKER_ARGS <<< "$DOCKER_COMMAND"
OUTPUT="$ROOT/csv/postgres_load_results.csv"
BENCHMARK_SCHEMA="lab3_load_benchmark"
BENCHMARK_TABLE="$BENCHMARK_SCHEMA.wikipedia_articles"
MAIN_TABLE="public.wikipedia_articles"

psql_exec() {
  "${DOCKER_ARGS[@]}" exec -i "$POSTGRES_CONTAINER" \
    psql -X -q -A -t -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$1"
}

main_rows="$(psql_exec 'SELECT count(*) FROM public.wikipedia_articles')"
if [[ ! "$main_rows" =~ ^[0-9]+$ ]]; then
  printf 'Could not read the wikipedia_articles row count: %s\n' "$main_rows" >&2
  exit 1
fi

if (( main_rows == 0 )); then
  TARGET_TABLE="$MAIN_TABLE"
  SCOPE="main_table"
  CLEANUP_TABLE=""
else
  TARGET_TABLE="$BENCHMARK_TABLE"
  SCOPE="benchmark_staging"
  CLEANUP_TABLE="$BENCHMARK_TABLE"
  psql_exec "
    CREATE SCHEMA IF NOT EXISTS $BENCHMARK_SCHEMA;
    DROP TABLE IF EXISTS $BENCHMARK_TABLE;
    CREATE TABLE $BENCHMARK_TABLE (
      LIKE $MAIN_TABLE INCLUDING DEFAULTS INCLUDING INDEXES
    );
  "
fi

cleanup() {
  if [[ -n "$CLEANUP_TABLE" ]]; then
    psql_exec "DROP TABLE IF EXISTS $CLEANUP_TABLE" >/dev/null
  fi
}
trap cleanup EXIT

mkdir -p "$(dirname -- "$OUTPUT")"
printf 'stage,records,elapsed_ms,scope\n' > "$OUTPUT"

start_ns="$(date +%s%N)"
copy_result="$("${DOCKER_ARGS[@]}" exec -i "$POSTGRES_CONTAINER" \
  psql -X -q -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "\copy $TARGET_TABLE (id,title,text,topic,article_type,date_modified) FROM STDIN WITH (FORMAT csv, HEADER true)" \
  < "$ROOT/data-set/wikipedia.csv")"
end_ns="$(date +%s%N)"
import_ms="$(( (end_ns - start_ns) / 1000000 ))"
if [[ ! "$copy_result" =~ ^COPY[[:space:]]+([0-9]+)$ ]]; then
  printf 'Unexpected PostgreSQL COPY result: %s\n' "$copy_result" >&2
  exit 1
fi
records="${BASH_REMATCH[1]}"
printf 'postgres_copy,%s,%s,%s\n' "$records" "$import_ms" "$SCOPE" >> "$OUTPUT"

start_ns="$(date +%s%N)"
if [[ "$SCOPE" == "main_table" ]]; then
  "${DOCKER_ARGS[@]}" exec -i "$POSTGRES_CONTAINER" \
    psql -X -q -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    < "$ROOT/database/02_build_full_text_index.sql"
else
  "${DOCKER_ARGS[@]}" exec -i "$POSTGRES_CONTAINER" \
    psql -X -q -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -c "UPDATE $TARGET_TABLE
      SET search_vector = to_tsvector(
        'english', coalesce(title, '') || ' ' || coalesce(text, '')
      );
      CREATE INDEX idx_lab3_load_benchmark_search
        ON $TARGET_TABLE USING GIN (search_vector);
      ANALYZE $TARGET_TABLE;"
fi
end_ns="$(date +%s%N)"
index_ms="$(( (end_ns - start_ns) / 1000000 ))"
printf 'postgres_full_text_index,%s,%s,%s\n' \
  "$records" "$index_ms" "$SCOPE" >> "$OUTPUT"

printf 'PostgreSQL import: %s ms; full-text index build: %s ms.\n' \
  "$import_ms" "$index_ms"
printf 'Timings saved to %s\n' "$OUTPUT"
if [[ "$SCOPE" == "benchmark_staging" ]]; then
  printf 'Existing wikipedia_articles was unchanged; temporary table removed.\n'
else
  printf 'Measured against the empty main wikipedia_articles table.\n'
fi
