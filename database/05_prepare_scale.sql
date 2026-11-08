\set ON_ERROR_STOP on
\timing on

CREATE TABLE wikipedia_articles_50000 AS
SELECT
    id,
    title,
    text,
    topic,
    article_type,
    date_modified,
    to_tsvector('english', coalesce(title, '') || ' ' || coalesce(text, ''))
        AS search_vector
FROM wikipedia_articles
ORDER BY id
LIMIT 50000;

ALTER TABLE wikipedia_articles_50000
    ADD PRIMARY KEY (id);

CREATE INDEX idx_wikipedia_articles_50000_search
    ON wikipedia_articles_50000 USING GIN (search_vector);

ANALYZE wikipedia_articles_50000;

CREATE TABLE wikipedia_articles_250000 AS
SELECT
    id,
    title,
    text,
    topic,
    article_type,
    date_modified,
    to_tsvector('english', coalesce(title, '') || ' ' || coalesce(text, ''))
        AS search_vector
FROM wikipedia_articles
ORDER BY id
LIMIT 250000;

ALTER TABLE wikipedia_articles_250000
    ADD PRIMARY KEY (id);

CREATE INDEX idx_wikipedia_articles_250000_search
    ON wikipedia_articles_250000 USING GIN (search_vector);

ANALYZE wikipedia_articles_250000;

SELECT 'wikipedia_50000' AS core, count(*) AS records, max(id) AS max_id
FROM wikipedia_articles_50000
UNION ALL
SELECT 'wikipedia_250000', count(*), max(id)
FROM wikipedia_articles_250000
ORDER BY records;
