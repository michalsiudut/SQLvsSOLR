\set ON_ERROR_STOP on
BEGIN;

CREATE TABLE IF NOT EXISTS solr_sync_outbox (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    operation TEXT NOT NULL CHECK (operation IN ('upsert', 'delete')),
    doc_id TEXT NOT NULL,
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    synced_at TIMESTAMPTZ,
    CHECK (
        (operation = 'upsert' AND payload IS NOT NULL)
        OR (operation = 'delete' AND payload IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_solr_sync_outbox_pending
    ON solr_sync_outbox (event_id)
    WHERE synced_at IS NULL;

CREATE OR REPLACE FUNCTION enqueue_wikipedia_article_solr_sync()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $function$
BEGIN
    IF TG_OP = 'DELETE' THEN
        INSERT INTO solr_sync_outbox (operation, doc_id)
        VALUES ('delete', OLD.id::text);
        RETURN OLD;
    END IF;

    IF TG_OP = 'UPDATE' AND OLD.id IS DISTINCT FROM NEW.id THEN
        INSERT INTO solr_sync_outbox (operation, doc_id)
        VALUES ('delete', OLD.id::text);
    END IF;

    INSERT INTO solr_sync_outbox (operation, doc_id, payload)
    VALUES (
        'upsert',
        NEW.id::text,
        jsonb_build_object(
            'id', NEW.id::text,
            'title', NEW.title,
            'text', NEW.text,
            'topic', NEW.topic,
            'article_type', NEW.article_type,
            'date_modified',
                to_char(NEW.date_modified, 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
        )
    );
    RETURN NEW;
END
$function$;

DROP TRIGGER IF EXISTS wikipedia_articles_solr_sync
    ON wikipedia_articles;

CREATE TRIGGER wikipedia_articles_solr_sync
AFTER INSERT OR UPDATE OR DELETE ON wikipedia_articles
FOR EACH ROW
EXECUTE FUNCTION enqueue_wikipedia_article_solr_sync();
COMMIT;
