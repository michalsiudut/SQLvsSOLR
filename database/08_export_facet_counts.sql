\set ON_ERROR_STOP on
\pset format csv

WITH date_buckets AS (
    SELECT period_start
    FROM generate_series(
        timestamp '2000-01-01',
        timestamp '2025-01-01',
        interval '5 years'
    ) AS periods(period_start)
),
date_counts AS (
    SELECT date_trunc('year', date_modified)::timestamp AS modified_year,
        count(*) AS documents
    FROM wikipedia_articles
    WHERE date_modified >= timestamp '2000-01-01'
      AND date_modified < timestamp '2030-01-01'
    GROUP BY 1
),
grouped_counts AS (
    SELECT 'topic'::text AS group_by, topic::text AS value, count(*) AS documents
    FROM wikipedia_articles
    GROUP BY topic
    UNION ALL
    SELECT
        'article_type',
        article_type::text,
        count(*)
    FROM wikipedia_articles
    GROUP BY article_type
    UNION ALL
    SELECT
        'date_modified_5year',
        to_char(buckets.period_start, 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
        coalesce(sum(counts.documents), 0)::bigint
    FROM date_buckets AS buckets
    LEFT JOIN date_counts AS counts
      ON counts.modified_year >= buckets.period_start
     AND counts.modified_year < buckets.period_start + interval '5 years'
    GROUP BY buckets.period_start
)
SELECT group_by, value, documents
FROM grouped_counts
ORDER BY group_by, value;
