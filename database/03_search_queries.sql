\set ON_ERROR_STOP on
\timing on

-- 1a. Wyszukiwanie słowa w indeksie pełnotekstowym.
SELECT count(*) AS full_text_matches
FROM wikipedia_articles
WHERE search_vector @@ plainto_tsquery('english', 'run');

-- 1b. To samo słowo wyszukiwane przez LIKE (bez użycia indeksu GIN).
SELECT count(*) AS like_matches
FROM wikipedia_articles
WHERE title LIKE '%run%'
   OR text LIKE '%run%';

-- 2. Fraza: słowa po kolei i obok siebie, po analizie języka angielskiego.
SELECT count(*) AS phrase_matches
FROM wikipedia_articles
WHERE search_vector @@ phraseto_tsquery('english', 'United States');

-- 3. history AND (war OR peace) AND NOT fiction.
SELECT count(*) AS boolean_matches
FROM wikipedia_articles
WHERE search_vector @@ to_tsquery(
    'english',
    'history & (war | peace) & !fiction'
);
