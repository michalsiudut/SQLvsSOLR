\set ON_ERROR_STOP on

CREATE TABLE wikipedia_articles (
    id BIGINT PRIMARY KEY,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    topic TEXT NOT NULL,
    article_type TEXT NOT NULL,
    date_modified TIMESTAMP NOT NULL,
    search_vector TSVECTOR NOT NULL DEFAULT ''::tsvector
);
