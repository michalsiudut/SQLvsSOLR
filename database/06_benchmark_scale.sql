\set ON_ERROR_STOP on
\pset format csv
\pset tuples_only on
\echo record_count,method,median_ms,runs_ms,matched_rows

CREATE TEMP TABLE scale_benchmark_runs (
    record_count INTEGER NOT NULL,
    method TEXT NOT NULL,
    run INTEGER NOT NULL,
    elapsed_ms DOUBLE PRECISION NOT NULL,
    matched_rows BIGINT NOT NULL
);

DO $benchmark$
DECLARE
    dataset RECORD;
    search_method TEXT;
    statement TEXT;
    warmup_matches BIGINT;
    matched BIGINT;
    started_at TIMESTAMPTZ;
    elapsed DOUBLE PRECISION;
    run_number INTEGER;
BEGIN
    FOR dataset IN
        SELECT * FROM (VALUES
            ('wikipedia_articles_50000', 50000),
            ('wikipedia_articles_250000', 250000),
            ('wikipedia_articles', 500000)
        ) AS sizes(table_name, record_count)
    LOOP
        FOREACH search_method IN ARRAY ARRAY['LIKE', 'Full text']
        LOOP
            IF search_method = 'LIKE' THEN
                statement := format(
                    'SELECT count(*) FROM %I WHERE title LIKE ''%%run%%'' OR text LIKE ''%%run%%''',
                    dataset.table_name
                );
            ELSE
                statement := format(
                    'SELECT count(*) FROM %I WHERE search_vector @@ plainto_tsquery(''english'', ''run'')',
                    dataset.table_name
                );
            END IF;

            EXECUTE statement INTO warmup_matches;

            FOR run_number IN 1..5
            LOOP
                started_at := clock_timestamp();
                EXECUTE statement INTO matched;
                elapsed := extract(epoch FROM clock_timestamp() - started_at) * 1000;

                INSERT INTO scale_benchmark_runs
                    (record_count, method, run, elapsed_ms, matched_rows)
                VALUES
                    (dataset.record_count, search_method, run_number, elapsed, matched);
            END LOOP;
        END LOOP;
    END LOOP;
END
$benchmark$;

SELECT
    record_count,
    method,
    round((percentile_cont(0.5) WITHIN GROUP (ORDER BY elapsed_ms))::numeric, 3)
        AS median_ms,
    string_agg(round(elapsed_ms::numeric, 3)::text, ';' ORDER BY run) AS runs_ms,
    max(matched_rows) AS matched_rows
FROM scale_benchmark_runs
GROUP BY record_count, method
ORDER BY record_count, method;
