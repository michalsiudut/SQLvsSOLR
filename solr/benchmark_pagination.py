import argparse
import csv
import json
import statistics
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode
from urllib.request import urlopen


def fetch_page(
    base_url: str,
    core: str,
    rows: int,
    cursor_mark: str | None = None,
    start: int | None = None,
) -> tuple[list[str], str | None, int]:
    params: dict[str, str | int] = {
        "q": "*:*",
        "sort": "id asc",
        "rows": rows,
        "fl": "id",
        "wt": "json",
    }
    if cursor_mark is not None:
        params["cursorMark"] = cursor_mark
    elif start is not None:
        params["start"] = start
    url = f"{base_url.rstrip('/')}/{core}/select?{urlencode(params)}"
    with urlopen(url, timeout=120) as response:
        payload = json.load(response)
    if payload["responseHeader"]["status"] != 0:
        raise RuntimeError(f"Solr pagination request failed: {payload}")
    if payload["responseHeader"].get("partialResults"):
        raise RuntimeError("Solr returned partial results during pagination.")
    ids = [str(doc["id"]) for doc in payload["response"]["docs"]]
    next_mark = payload.get("nextCursorMark")
    total = int(payload["response"]["numFound"])
    return ids, next_mark, total


def fetch_cursor_page(
    base_url: str, core: str, start: int, rows: int
) -> tuple[list[str], int]:
    cursor_mark = "*"
    all_ids: list[str] = []
    requests = 0
    expected_total: int | None = None
    target_end = start + rows
    while len(all_ids) < target_end:
        ids, next_mark, total = fetch_page(
            base_url, core, rows, cursor_mark=cursor_mark
        )
        requests += 1
        if expected_total is not None and total != expected_total:
            raise RuntimeError("Solr document count changed during the cursor scan.")
        expected_total = total
        all_ids.extend(ids)
        if next_mark is None:
            raise RuntimeError("Solr response did not contain nextCursorMark.")
        if next_mark == cursor_mark:
            break
        cursor_mark = next_mark
    page = all_ids[start:target_end]
    if len(page) != rows:
        raise RuntimeError(
            f"CursorMark reached only {len(page)} of {rows} documents "
            f"at offset {start}."
        )
    return page, requests


def fetch_start_page(
    base_url: str, core: str, start: int, rows: int
) -> tuple[list[str], int]:
    ids, _, total = fetch_page(base_url, core, rows, start=start)
    if start + rows > total or len(ids) != rows:
        raise RuntimeError(
            f"Requested start={start}, rows={rows} beyond the available "
            f"{total} documents."
        )
    return ids, total


def measure(
    operation: Callable[[], tuple[list[str], int]], repetitions: int
) -> tuple[list[str], int, list[float]]:
    expected_ids: list[str] | None = None
    request_count = 0
    latencies: list[float] = []
    for _ in range(repetitions):
        started_at = time.perf_counter()
        ids, requests = operation()
        latencies.append((time.perf_counter() - started_at) * 1000)
        if expected_ids is not None and ids != expected_ids:
            raise RuntimeError("Repeated pagination runs returned different IDs.")
        expected_ids = ids
        request_count = requests
    if expected_ids is None:
        raise RuntimeError("No pagination runs were completed.")
    return expected_ids, request_count, latencies


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare a distant Solr start/rows page with cursorMark."
    )
    parser.add_argument("--url", default="http://localhost:8983/solr")
    parser.add_argument("--core", default="wikipedia")
    parser.add_argument("--start", type=int, default=100_000)
    parser.add_argument("--rows", type=int, default=1_000)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument(
        "--output", type=Path, default=Path("csv/pagination_results.csv")
    )
    args = parser.parse_args()
    if args.start < 1:
        parser.error("--start must be at least 1 for a distant-page benchmark")
    if args.rows < 1 or args.start % args.rows:
        parser.error("--rows must be positive and --start divisible by --rows")
    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")

    start_operation = lambda: (
        fetch_start_page(args.url, args.core, args.start, args.rows)[0],
        1,
    )
    cursor_operation = lambda: fetch_cursor_page(
        args.url, args.core, args.start, args.rows
    )

    warm_start_ids, _ = fetch_start_page(
        args.url, args.core, args.start, args.rows
    )
    warm_cursor_ids, _ = fetch_cursor_page(
        args.url, args.core, args.start, args.rows
    )
    if warm_start_ids != warm_cursor_ids:
        raise RuntimeError(
            "The warm-up page differs between start/rows and cursorMark."
        )

    start_ids, start_requests, start_runs = measure(
        start_operation, args.repetitions
    )
    cursor_ids, cursor_requests, cursor_runs = measure(
        cursor_operation, args.repetitions
    )
    if start_ids != cursor_ids:
        raise RuntimeError(
            "The distant page returned different IDs with start/rows and cursorMark."
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(
            [
                "core",
                "start",
                "rows",
                "method",
                "requests",
                "median_ms",
                "runs_ms",
                "documents",
            ]
        )
        for method, requests, runs in (
            ("start/rows", start_requests, start_runs),
            ("cursorMark", cursor_requests, cursor_runs),
        ):
            writer.writerow(
                [
                    args.core,
                    args.start,
                    args.rows,
                    method,
                    requests,
                    f"{statistics.median(runs):.3f}",
                    ";".join(f"{run:.3f}" for run in runs),
                    len(start_ids),
                ]
            )
            print(
                f"{method}: median {statistics.median(runs):.3f} ms "
                f"over {requests} request(s)"
            )
    print(f"Identical page verified: {len(start_ids)} document IDs.")
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
