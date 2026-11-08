\set ON_ERROR_STOP on
\timing on

UPDATE wikipedia_articles
SET search_vector = to_tsvector(
    'english',
    coalesce(title, '') || ' ' || coalesce(text, '')
);

CREATE INDEX IF NOT EXISTS idx_wikipedia_articles_search
ON wikipedia_articles USING GIN (search_vector);

ANALYZE wikipedia_articles;
