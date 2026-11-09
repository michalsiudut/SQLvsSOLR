#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-lab3-postgres}"
POSTGRES_DB="${POSTGRES_DB:-lab3}"
POSTGRES_USER="${POSTGRES_USER:-lab3}"
DOCKER_COMMAND="${DOCKER_COMMAND:-sudo docker}"
read -r -a DOCKER_ARGS <<< "$DOCKER_COMMAND"
OUTPUT="$ROOT/csv/sql_top10.csv"

SQL=$(cat <<'SQL'
WITH searches(query_name, tsquery) AS (
    VALUES
        ('run', plainto_tsquery('english', 'run')),
        ('phrase', phraseto_tsquery('english', 'United States')),
        ('boolean', to_tsquery('english', 'history & (war | peace) & !fiction'))
),
ranked AS (
    SELECT
        searches.query_name,
        articles.id,
        row_number() OVER (
            PARTITION BY searches.query_name
            ORDER BY ts_rank_cd(articles.search_vector, searches.tsquery) DESC,
                     articles.id::text ASC
        ) AS position
    FROM wikipedia_articles AS articles
    CROSS JOIN searches
    WHERE articles.search_vector @@ searches.tsquery
)
SELECT query_name, id
FROM ranked
WHERE position <= 10
ORDER BY query_name, position
SQL
)

mkdir -p "$ROOT/csv"
printf 'query,id\n' > "$OUTPUT"
"${DOCKER_ARGS[@]}" exec "$POSTGRES_CONTAINER" \
  psql -X -q -A -t -F ',' -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "$SQL" >> "$OUTPUT"
printf 'SQL top-10 IDs saved to %s\n' "$OUTPUT"
