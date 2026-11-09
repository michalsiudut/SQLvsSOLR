import argparse
import csv
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


QUERIES = {
    "run": "run",
    "phrase": '"United States"',
    "boolean": "(history AND (war OR peace) AND NOT fiction)",
}


def load_sql_ids(path: Path) -> dict[str, list[str]]:
    ids = {name: [] for name in QUERIES}
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            if row["query"] not in ids:
                raise ValueError(f"Unknown SQL query name: {row['query']}")
            ids[row["query"]].append(row["id"])
    for name, query_ids in ids.items():
        if len(query_ids) > 10:
            raise ValueError(f"Expected at most 10 SQL results for {name}.")
    return ids


def fetch_solr_ids(base_url: str, core: str, query: str) -> list[tuple[str, float]]:
    params = {
        "q": query,
        "defType": "edismax",
        "qf": "title^3 text",
        "rows": 10,
        "sort": "score desc,id asc",
        "fl": "id,score",
        "wt": "json",
    }
    if query.startswith("(history"):
        params["q.op"] = "AND"
    url = f"{base_url.rstrip('/')}/{core}/select?{urlencode(params)}"
    with urlopen(url, timeout=120) as response:
        payload = json.load(response)
    if payload["responseHeader"]["status"] != 0:
        raise RuntimeError(f"Solr top-10 query failed for {query!r}: {payload}")
    return [
        (str(doc["id"]), float(doc["score"]))
        for doc in payload["response"]["docs"]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare PostgreSQL ts_rank_cd and Solr eDisMax top-10 IDs."
    )
    parser.add_argument(
        "--sql", type=Path, default=Path("csv/sql_top10.csv")
    )
    parser.add_argument("--url", default="http://localhost:8983/solr")
    parser.add_argument("--core", default="wikipedia")
    parser.add_argument(
        "--comparison-output",
        type=Path,
        default=Path("csv/top10_comparison.csv"),
    )
    parser.add_argument(
        "--solr-output", type=Path, default=Path("csv/solr_top10.csv")
    )
    args = parser.parse_args()

    sql_ids = load_sql_ids(args.sql)
    comparison: list[tuple[str, int, int, list[str]]] = []
    solr_rows: list[tuple[str, int, str, float]] = []
    for name, query in QUERIES.items():
        solr_results = fetch_solr_ids(args.url, args.core, query)
        sql_set = set(sql_ids[name])
        common = [doc_id for doc_id, _ in solr_results if doc_id in sql_set]
        comparison.append(
            (name, len(sql_ids[name]), len(solr_results), common)
        )
        solr_rows.extend(
            (name, position, doc_id, score)
            for position, (doc_id, score) in enumerate(solr_results, start=1)
        )

    args.solr_output.parent.mkdir(parents=True, exist_ok=True)
    with args.solr_output.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["query", "position", "id", "solr_score"])
        writer.writerows(solr_rows)
    args.comparison_output.parent.mkdir(parents=True, exist_ok=True)
    with args.comparison_output.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(
            [
                "query",
                "sql_top10_count",
                "solr_top10_count",
                "overlap_count",
                "overlap_ids",
                "overlap_percent_of_sql",
            ]
        )
        for name, sql_count, solr_count, common in comparison:
            overlap = len(common)
            percentage = 100 * overlap / sql_count if sql_count else 0
            writer.writerow(
                [
                    name,
                    sql_count,
                    solr_count,
                    overlap,
                    ";".join(common),
                    f"{percentage:.1f}",
                ]
            )
            print(
                f"{name}: {overlap} shared IDs "
                f"(SQL={sql_count}, Solr={solr_count})."
            )
    print(f"Comparison saved to {args.comparison_output}")
    print(f"Solr top-10 results saved to {args.solr_output}")


if __name__ == "__main__":
    main()
