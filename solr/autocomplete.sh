#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[[:alnum:]]+$ || ${#1} -gt 50 ]]; then
  printf 'Usage: %s <1-50 character alphanumeric-prefix>\n' "$0" >&2
  exit 2
fi

SOLR_URL="${SOLR_URL:-http://localhost:8983/solr}"
CORE="${SOLR_CORE:-wikipedia}"

curl --fail --silent --show-error --get \
  "${SOLR_URL%/}/${CORE}/select" \
  --data-urlencode "q=title_prefix:$1" \
  --data-urlencode 'rows=10' \
  --data-urlencode 'fl=id,title,score' \
  --data-urlencode 'sort=score desc,id asc' \
  --data-urlencode 'wt=json'
printf '\n'
