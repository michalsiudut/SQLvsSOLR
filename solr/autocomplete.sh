#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || -z "$1" ]]; then
  printf 'Usage: %s <word-prefix>\n' "$0" >&2
  exit 2
fi

SOLR_URL="${SOLR_URL:-http://localhost:8983/solr}"
CORE="${SOLR_CORE:-wikipedia}"

curl --fail --silent --show-error --get \
  "${SOLR_URL%/}/${CORE}/terms" \
  --data-urlencode 'terms=true' \
  --data-urlencode 'terms.fl=title' \
  --data-urlencode "terms.prefix=$1" \
  --data-urlencode 'terms.limit=10' \
  --data-urlencode 'terms.sort=count' \
  --data-urlencode 'wt=json'
printf '\n'
