import argparse
import csv
import json
import re
import shlex
import statistics
import subprocess
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


def solr_count(base_url: str, core: str, prefix: str) -> int:
    params = urlencode(
        {
            "q": f"title_prefix:{prefix.lower()}",
            "rows": 0,
            "wt": "json",
        }
    )
    url = f"{base_url.rstrip('/')}/{core}/select?{params}"
    with urlopen(url, timeout=120) as response:
        payload = json.load(response)
    if payload["responseHeader"]["status"] != 0:
        raise RuntimeError(f"Solr prefix query failed: {payload}")
    return int(payload["response"]["numFound"])


def postgres_count(
    docker_command: list[str], container: str, database: str, user: str,
    prefix: str,
) -> int:
    sql_prefix = prefix.replace("'", "''")
    command = [
        *docker_command,
        "exec",
        container,
        "psql",
        "-X",
        "-q",
        "-A",
        "-t",
        "-U",
        user,
        "-d",
        database,
        "-c",
        "SELECT count(*) FROM wikipedia_articles "
        f"WHERE lower(title) LIKE lower('{sql_prefix}%')",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(
            f"PostgreSQL prefix query failed ({result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return int(result.stdout.strip())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare Solr edge-ngram title prefixes with SQL LIKE."
    )
    parser.add_argument("--prefix", default="foot")
    parser.add_argument("--url", default="http://localhost:8983/solr")
    parser.add_argument("--core", default="wikipedia")
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--docker-command", default="sudo docker")
    parser.add_argument("--container", default="lab3-postgres")
    parser.add_argument("--database", default="lab3")
    parser.add_argument("--user", default="lab3")
    parser.add_argument(
        "--output", type=Path, default=Path("csv/autocomplete_results.csv")
    )
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9]{1,50}", args.prefix):
        parser.error("--prefix must contain 1 to 50 letters or digits")
    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")
    docker_command = shlex.split(args.docker_command)
    if not docker_command:
        parser.error("--docker-command cannot be empty")

    queries = {
        "SQL LIKE prefix": lambda: postgres_count(
            docker_command,
            args.container,
            args.database,
            args.user,
            args.prefix,
        ),
        "Solr edge-ngram": lambda: solr_count(args.url, args.core, args.prefix),
    }
    results: list[tuple[str, int, float, list[float]]] = []
    for method, query in queries.items():
        query()
        runs: list[float] = []
        matched_rows: int | None = None
        for _ in range(args.repetitions):
            started_at = time.perf_counter()
            count = query()
            runs.append((time.perf_counter() - started_at) * 1000)
            if matched_rows is not None and count != matched_rows:
                raise RuntimeError(f"{method} returned inconsistent counts.")
            matched_rows = count
        if matched_rows is None:
            raise RuntimeError(f"{method} returned no benchmark runs.")
        results.append(
            (method, matched_rows, statistics.median(runs), runs)
        )

    if results[0][1] != results[1][1]:
        raise RuntimeError(
            f"Prefix result counts differ: SQL={results[0][1]}, "
            f"Solr={results[1][1]}. Check edge-ngram field configuration."
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["prefix", "method", "median_ms", "runs_ms", "matched_rows"])
        for method, matched_rows, median_ms, runs in results:
            writer.writerow(
                [
                    args.prefix.lower(),
                    method,
                    f"{median_ms:.3f}",
                    ";".join(f"{run:.3f}" for run in runs),
                    matched_rows,
                ]
            )
    for method, count, median_ms, _ in results:
        print(f"{method}: {count} matches, client median {median_ms:.3f} ms")
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
