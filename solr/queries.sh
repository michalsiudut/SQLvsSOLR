#!/usr/bin/env bash
set -euo pipefail

SOLR_URL="${SOLR_URL:-http://localhost:8983/solr}"
CORE="${SOLR_CORE:-wikipedia}"
SELECT_URL="${SOLR_URL%/}/${CORE}/select"

printf '%s\n' '1) Wyszukiwanie słowa: run'
curl --fail --silent --show-error --get "$SELECT_URL" \
  --data-urlencode 'q=run' \
  --data-urlencode 'defType=edismax' \
  --data-urlencode 'qf=title^3 text' \
  --data-urlencode 'rows=10' \
  --data-urlencode 'sort=score desc' \
  --data-urlencode 'fl=id,title,score'
printf '\n\n%s\n' '2) Wyszukiwanie frazy: "United States"'
curl --fail --silent --show-error --get "$SELECT_URL" \
  --data-urlencode 'q="United States"' \
  --data-urlencode 'defType=edismax' \
  --data-urlencode 'qf=title^3 text' \
  --data-urlencode 'rows=10' \
  --data-urlencode 'sort=score desc' \
  --data-urlencode 'fl=id,title,score'
printf '\n\n%s\n' '3) history AND (war OR peace) AND NOT fiction'
curl --fail --silent --show-error --get "$SELECT_URL" \
  --data-urlencode 'q=(history AND (war OR peace) AND NOT fiction)' \
  --data-urlencode 'defType=edismax' \
  --data-urlencode 'qf=title^3 text' \
  --data-urlencode 'q.op=AND' \
  --data-urlencode 'rows=10' \
  --data-urlencode 'sort=score desc' \
  --data-urlencode 'fl=id,title,score'
printf '\n\n%s\n' '4) eDisMax ranking, facets and highlighting for "run"'
curl --fail --silent --show-error --get "$SELECT_URL" \
  --data-urlencode 'q=run' \
  --data-urlencode 'defType=edismax' \
  --data-urlencode 'qf=title^3 text' \
  --data-urlencode 'rows=10' \
  --data-urlencode 'sort=score desc' \
  --data-urlencode 'fl=id,title,score,topic,article_type' \
  --data-urlencode 'facet=true' \
  --data-urlencode 'facet.field=topic' \
  --data-urlencode 'facet.field=article_type' \
  --data-urlencode 'facet.limit=20' \
  --data-urlencode 'hl=true' \
  --data-urlencode 'hl.fl=text' \
  --data-urlencode 'hl.snippets=2' \
  --data-urlencode 'hl.fragsize=180' \
  --data-urlencode 'hl.simple.pre=<em>' \
  --data-urlencode 'hl.simple.post=</em>' \
  --data-urlencode 'wt=json'
printf '\n'
