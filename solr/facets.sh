#!/usr/bin/env bash
set -euo pipefail

SOLR_URL="${SOLR_URL:-http://localhost:8983/solr}"
CORE="${SOLR_CORE:-wikipedia}"

curl --fail --silent --show-error --get \
  "${SOLR_URL%/}/${CORE}/select" \
  --data-urlencode 'q=*:*' \
  --data-urlencode 'rows=0' \
  --data-urlencode 'facet=true' \
  --data-urlencode 'facet.field=topic' \
  --data-urlencode 'facet.field=article_type' \
  --data-urlencode 'facet.mincount=0' \
  --data-urlencode 'facet.range=date_modified' \
  --data-urlencode 'f.date_modified.facet.range.start=2000-01-01T00:00:00Z' \
  --data-urlencode 'f.date_modified.facet.range.end=2030-01-01T00:00:00Z' \
  --data-urlencode 'f.date_modified.facet.range.gap=+5YEARS' \
  --data-urlencode 'wt=json'
printf '\n'
