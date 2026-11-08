\set ON_ERROR_STOP on
\pset format csv

CREATE TEMP TABLE facet_benchmark_runs (
    run INTEGER NOT NULL,
    elapsed_ms DOUBLE PRECISION NOT NULL,
    group_count BIGINT NOT NULL
);

DO $benchmark$
DECLARE
    warmup_groups BIGINT;
    groups_found BIGINT;
    started_at TIMESTAMPTZ;
    elapsed DOUBLE PRECISION;
    run_number INTEGER;
BEGIN
    EXECUTE $sql$
        WITH grouped_counts AS (
            SELECT 'topic'::text AS group_by, topic::text AS value, count(*) AS documents
            FROM wikipedia_articles
            GROUP BY topic
            UNION ALL
            SELECT 'article_type', article_type::text, count(*)
            FROM wikipedia_articles
            GROUP BY article_type
            UNION ALL
            SELECT
                'date_modified_5year',
                to_char(buckets.period_start, 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                count(articles.id)
            FROM generate_series(
                timestamp '2000-01-01',
                timestamp '2025-01-01',
                interval '5 years'
            ) AS buckets(period_start)
            LEFT JOIN wikipedia_articles AS articles
              ON articles.date_modified >= buckets.period_start
             AND articles.date_modified < buckets.period_start + interval '5 years'
            GROUP BY buckets.period_start
        )
        SELECT count(*) FROM grouped_counts
    $sql$ INTO warmup_groups;

    FOR run_number IN 1..5
    LOOP
        started_at := clock_timestamp();
        EXECUTE $sql$
            WITH grouped_counts AS (
                SELECT 'topic'::text AS group_by, topic::text AS value, count(*) AS documents
                FROM wikipedia_articles
                GROUP BY topic
                UNION ALL
                SELECT 'article_type', article_type::text, count(*)
                FROM wikipedia_articles
                GROUP BY article_type
                UNION ALL
                SELECT
                    'date_modified_5year',
                    to_char(buckets.period_start, 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                    count(articles.id)
                FROM generate_series(
                    timestamp '2000-01-01',
                    timestamp '2025-01-01',
                    interval '5 years'
                ) AS buckets(period_start)
                LEFT JOIN wikipedia_articles AS articles
                  ON articles.date_modified >= buckets.period_start
                 AND articles.date_modified < buckets.period_start + interval '5 years'
                GROUP BY buckets.period_start
            )
            SELECT count(*) FROM grouped_counts
        $sql$ INTO groups_found;
        elapsed := extract(epoch FROM clock_timestamp() - started_at) * 1000;

        INSERT INTO facet_benchmark_runs (run, elapsed_ms, group_count)
        VALUES (run_number, elapsed, groups_found);
    END LOOP;
END
$benchmark$;

SELECT
    'SQL GROUP BY' AS method,
    round((percentile_cont(0.5) WITHIN GROUP (ORDER BY elapsed_ms))::numeric, 3)
        AS median_ms,
    string_agg(round(elapsed_ms::numeric, 3)::text, ';' ORDER BY run) AS runs_ms,
    max(group_count) AS number_of_groups
FROM facet_benchmark_runs;
