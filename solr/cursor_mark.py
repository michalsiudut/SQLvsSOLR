import argparse
import csv
import json
import statistics
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


def fetch_page(
    base_url: str, core: str, cursor_mark: str, rows: int
) -> tuple[dict, float]:
    params = urlencode(
        {
            "q": "*:*",
            "sort": "id asc",
            "cursorMark": cursor_mark,
            "rows": rows,
            "fl": "id",
            "wt": "json",
        }
    )
    url = f"{base_url.rstrip('/')}/{core}/select?{params}"
    started_at = time.perf_counter()
    with urlopen(url, timeout=120) as response:
        payload = json.load(response)
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    if payload["responseHeader"]["status"] != 0:
        raise RuntimeError(f"Solr cursorMark query failed: {payload}")
    if "nextCursorMark" not in payload:
        raise RuntimeError("Solr response did not contain nextCursorMark.")
    return payload, elapsed_ms


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read every document in a Solr core using cursorMark."
    )
    parser.add_argument("--url", default="http://localhost:8983/solr")
    parser.add_argument("--core", default="wikipedia")
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument(
        "--output", type=Path, default=Path("csv/cursor_mark_results.csv")
    )
    args = parser.parse_args()
    if args.rows < 1:
        parser.error("--rows must be at least 1")

    cursor_mark = "*"
    first_page, warmup_ms = fetch_page(
        args.url, args.core, cursor_mark, args.rows
    )
    expected_total = int(first_page["response"]["numFound"])
    cursor_mark = first_page["nextCursorMark"]
    pages = 1
    documents_read = len(first_page["response"]["docs"])
    page_latencies = [warmup_ms]

    while True:
        previous_cursor = cursor_mark
        payload, elapsed_ms = fetch_page(
            args.url, args.core, cursor_mark, args.rows
        )
        page_latencies.append(elapsed_ms)
        pages += 1
        documents_read += len(payload["response"]["docs"])
        cursor_mark = payload["nextCursorMark"]

        if pages % 50 == 0:
            print(f"Read {documents_read:,}/{expected_total:,} documents")

        if cursor_mark == previous_cursor:
            break
        if pages > expected_total + 1:
            raise RuntimeError("cursorMark did not converge to the final page.")

    if documents_read != expected_total:
        raise RuntimeError(
            f"Expected {expected_total:,} documents, read {documents_read:,}."
        )

    with args.output.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(
            [
                "core",
                "documents",
                "rows_per_page",
                "pages",
                "total_client_ms",
                "median_page_ms",
                "warmup_page_ms",
            ]
        )
        writer.writerow(
            [
                args.core,
                documents_read,
                args.rows,
                pages,
                f'{sum(page_latencies):.3f}',
                f"{statistics.median(page_latencies[1:]):.3f}"
                if len(page_latencies) > 1
                else f"{page_latencies[0]:.3f}",
                f"{warmup_ms:.3f}",
            ]
        )

    print(
        f"cursorMark read all {documents_read:,} documents in {pages} pages. "
        f"Median page time after warmup: "
        f"{statistics.median(page_latencies[1:]) if len(page_latencies) > 1 else warmup_ms:.3f} ms"
    )
    print(f"Result saved to {args.output}")


if __name__ == "__main__":
    main()
