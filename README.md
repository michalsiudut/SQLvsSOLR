# Lab 3 — SQL kontra Apache Solr

Projekt porównuje wyszukiwanie pełnotekstowe w PostgreSQL i Apache Solr na
500 000 artykułach z `wikimedia/structured-wikipedia`
(`enwiki_namespace_0`). Dane przygotowuje `data-set/download.py`; ich kontrolę
wykonuje `data-set/check.py`.

## Wymagania

- Docker i Docker Compose nie są wymagane — używane są dwa kontenery Docker.
- Python 3.10+ (loader używa standardowej biblioteki Pythona).
- `curl`.

Testowane środowisko: PostgreSQL 17, Apache Solr 10, Python 3.12.3.

## Uruchomienie usług

Ustaw własne hasło, nie zapisuj go w repozytorium i nie udostępniaj w logach:

```bash
sudo docker run -d --name lab3-postgres --restart unless-stopped \
  -e POSTGRES_DB=lab3 -e POSTGRES_USER=lab3 \
  -e POSTGRES_PASSWORD='USTAW_WLASNE_HASLO' \
  -p 5432:5432 -v lab3_pgdata:/var/lib/postgresql/data postgres:17

sudo docker run -d --name lab3-solr --restart unless-stopped \
  -p 8983:8983 -e SOLR_HEAP=2g solr:10
```

Sprawdzenie:

```bash
sudo docker exec lab3-postgres pg_isready -U lab3 -d lab3
curl -fsS 'http://localhost:8983/solr/admin/info/system?wt=json'
```

## PostgreSQL

Polecenia uruchamiaj z katalogu głównego projektu:

```bash
sudo docker exec -i lab3-postgres psql -U lab3 -d lab3 < database/01_schema.sql
bash database/measure_load.sh
sudo docker exec -i lab3-postgres psql -U lab3 -d lab3 < database/03_search_queries.sql
```

`measure_load.sh` mierzy import i indeksowanie. Jeśli tabela główna jest pusta,
mierzy na niej; jeśli zawiera dane, tworzy tymczasową kopię schematu w
`lab3_load_benchmark`, a po pomiarze usuwa tylko tę tabelę. Wyniki zapisuje do
`csv/postgres_load_results.csv` z informacją, gdzie wykonano pomiar.
Do pomiarów skalowania (tabele 50k/250k; wykonaj tylko raz):

```bash
sudo docker exec -i lab3-postgres psql -U lab3 -d lab3 < database/05_prepare_scale.sql
sudo docker exec -i lab3-postgres psql -X -q -U lab3 -d lab3 < database/06_benchmark_scale.sql > csv/sql_scale_results.csv
python3 database/plot_scale.py
```

Ranking `ts_rank_cd` i porównanie ID z top-10 Solra:

```bash
bash database/export_top10.sh
python3 solr/compare_top10.py
```

Porównanie `GROUP BY` z facetami:

```bash
bash database/export_facets.sh
bash database/compare_facets.sh
```

## Apache Solr

Utworzenie core’u, schematu i import danych:

```bash
sudo bash solr/setup.sh
python3 solr/load_data.py
```

Nie uruchamiaj ponownie `setup.sh` na istniejącym core. Zapytania i
autouzupełnianie:

```bash
bash solr/queries.sh
bash solr/autocomplete.sh foot
python3 solr/benchmark_autocomplete.py --prefix foot
bash solr/facets.sh
```

Loader zapisuje czas importu i commit do `csv/solr_import_results.csv`.
Nowe core’y dostają pole edge-ngram z `schema.json`. Dla istniejącego core’u
uruchom jednorazowo `bash solr/enable_autocomplete.sh`, a następnie ponownie
załaduj CSV przez `python3 solr/load_data.py`, aby wypełnić pole `title_prefix`.
Benchmark porównuje wynik tego pola z `lower(title) LIKE lower('foot%')` i
zapisuje pomiary do `csv/autocomplete_results.csv`.

### Rozszerzenia poziomu 5.0

Pełne stronicowanie po `cursorMark`:

```bash
python3 solr/cursor_mark.py --core wikipedia --rows 1000
```

Porównanie dalekiej strony (domyślnie offset 100 000, 1 000 dokumentów) przez
`start/rows` i `cursorMark`; skrypt sprawdza, czy oba sposoby zwracają te same
ID, mierzy po pięć rozgrzanych powtórzeń i zapisuje wynik w
`csv/pagination_results.csv`:

```bash
python3 solr/benchmark_pagination.py --start 100000 --rows 1000
```

Synchronizacja zmian SQL → Solr używa transakcyjnej kolejki outbox. Trigger
zapisuje INSERT/UPDATE/DELETE w tej samej transakcji co zmiana artykułu;
osobny konsument wysyła oczekujące zdarzenia do core’u `wikipedia` i oznacza
je jako zsynchronizowane dopiero po zatwierdzeniu zmian w Solr. Uruchom
migrację raz:

```bash
sudo docker exec -i lab3-postgres psql -U lab3 -d lab3 < database/09_sync_outbox.sql
```

Uruchom konsumenta w osobnym terminalu i pozostaw go działającego, aby
automatycznie przekazywał nowe zmiany:

```bash
python3 solr/sync_outbox.py --watch
```

Przy domyślnym `sudo docker` najpierw wykonaj `sudo -v`, aby Docker mógł
korzystać z zapisanych uprawnień sudo. Zatrzymaj konsumenta przez Ctrl+C.
Domyślnie sprawdza kolejkę co 2 sekundy; interwał zmienisz przez
`--poll-interval`. Jednorazowe opróżnienie kolejki wykonuje
`python3 solr/sync_outbox.py` bez `--watch`. Uruchamiaj tylko jednego
konsumenta naraz. Zmiana SQL może być już zatwierdzona, zanim konsument
przekaże ją do Solr, więc synchronizacja jest asynchroniczna.

Test integracyjny dodaje cztery rekordy, aktualizuje dwa, usuwa dwa i porównuje
pola SQL z dokumentami Solr po każdej operacji. Ostatnie wykonanie zakończyło
się sukcesem. Przed ponownym uruchomieniem zatrzymaj tryb `--watch` i opróżnij
kolejkę outbox:

```bash
bash solr/test_sync.sh
```

Skalowanie Solra wymaga core’ów `wikipedia_50000` i `wikipedia_250000`.
Szczegóły procedury (eksport ID SQL, dokładne subsety, import i pomiar) opisano
w [sprawozdaniu](./report.html) i skryptach `solr/prepare_scale_cores.sh`,
`solr/export_scale_ids.sh` oraz `solr/benchmark_scale.py`.

## Struktura

- `data-set/` — pobieranie, walidacja i źródłowy CSV (duży plik).
- `database/` — DDL, zapytania, benchmarki i narzędzia porównawcze.
- `solr/` — schemat, setup, loader, zapytania, benchmarki i facety.
- `csv/` — zebrane pomiary i liczności w formacie CSV.
- `svg/` — wykresy wektorowe; wersje PNG są osadzone w PDF.
- `report.html`, `report.pdf` — sprawozdanie i jego źródło HTML.
- `database/measure_load.sh` oraz `solr/load_data.py` — pomiar importu i indeksowania.

CSV z danymi nie jest dołączony do repozytorium. Przed przekazaniem projektu
sprawdź warunki licencyjne źródłowego zbioru i wymagania prowadzącego.

## Status przed oddaniem

Zebrane są pomiary wyszukiwania i facetingu. Rozszerzenia poziomu 5.0 —
`cursorMark` oraz synchronizacja zmian SQL → Solr — są zaimplementowane i
przetestowane. Pełne stronicowanie 500 000 dokumentów zapisano w
`csv/cursor_mark_results.csv`; test integracyjny potwierdził INSERT, UPDATE i
DELETE. Przed oddaniem sprawdź jeszcze, czy masz zachowane czasy importu i
budowy indeksów.
