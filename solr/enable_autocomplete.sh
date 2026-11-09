#!/usr/bin/env bash
set -euo pipefail

SOLR_URL="${SOLR_URL:-http://localhost:8983/solr}"
CORE="${SOLR_CORE:-wikipedia}"
SCHEMA_URL="${SOLR_URL%/}/${CORE}/schema"

curl --fail --silent --show-error \
  -H 'Content-Type: application/json' \
  --data '{"add-field-type":{"name":"title_prefix_type","class":"solr.TextField","indexAnalyzer":{"tokenizer":{"class":"solr.KeywordTokenizerFactory"},"filters":[{"class":"solr.LowerCaseFilterFactory"},{"class":"solr.EdgeNGramFilterFactory","minGramSize":1,"maxGramSize":50}]},"queryAnalyzer":{"tokenizer":{"class":"solr.KeywordTokenizerFactory"},"filters":[{"class":"solr.LowerCaseFilterFactory"}]}}}' \
  "$SCHEMA_URL"
printf '\n'

curl --fail --silent --show-error \
  -H 'Content-Type: application/json' \
  --data '{"add-field":{"name":"title_prefix","type":"title_prefix_type","indexed":true,"stored":false,"multiValued":false}}' \
  "$SCHEMA_URL"
printf '\n'

curl --fail --silent --show-error \
  -H 'Content-Type: application/json' \
  --data '{"add-copy-field":{"source":"title","dest":"title_prefix"}}' \
  "$SCHEMA_URL"
printf '\n'

printf 'Edge-ngram prefix field configured. Reindex documents with solr/load_data.py.\n'
