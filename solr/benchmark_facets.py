import argparse
import csv
import json
import statistics
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


def fetch_facets(base_url: str, core: str) -> tuple[float, dict]:
    params = urlencode(
        [
            ("q", "*:*"),
            ("rows", "0"),
            ("facet", "true"),
            ("facet.field", "topic"),
            ("facet.field", "article_type"),
            ("facet.mincount", "0"),
            ("facet.range", "date_modified"),
            ("f.date_modified.facet.range.start", "2000-01-01T00:00:00Z"),
            ("f.date_modified.facet.range.end", "2030-01-01T00:00:00Z"),
            ("f.date_modified.facet.range.gap", "+5YEARS"),
            ("wt", "json"),
        ]
    )
    url = f"{base_url.rstrip('/')}/{core}/select?{params}"
    started_at = time.perf_counter()
    with urlopen(url, timeout=120) as response:
        payload = json.load(response)
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    if payload["responseHeader"]["status"] != 0:
        raise RuntimeError(f"Solr facet query failed for core {core}: {payload}")
    return elapsed_ms, payload


def write_counts(payload: dict, path: Path) -> None:
    facet_counts = payload["facet_counts"]
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["group_by", "value", "documents"])
        for field, counts in facet_counts["facet_fields"].items():
            if len(counts) % 2:
                raise ValueError(f"Unexpected facet response for {field}: {counts}")
            for index in range(0, len(counts), 2):
                writer.writerow([field, counts[index], counts[index + 1]])

        range_counts = facet_counts["facet_ranges"]["date_modified"]["counts"]
        if len(range_counts) % 2:
            raise ValueError(f"Unexpected date-range facet response: {range_counts}")
        for index in range(0, len(range_counts), 2):
            writer.writerow(
                ["date_modified_5year", range_counts[index], range_counts[index + 1]]
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark Solr category and date-range facets."
    )
    parser.add_argument("--url", default="http://localhost:8983/solr")
    parser.add_argument("--core", default="wikipedia")
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path("solr_facets_results.csv"))
    parser.add_argument(
        "--counts-output",
        type=Path,
        default=Path("solr_facet_counts.csv"),
    )
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")

    fetch_facets(args.url, args.core)
    runs = [fetch_facets(args.url, args.core) for _ in range(args.repetitions)]
    latencies = [elapsed for elapsed, _ in runs]
    median_ms = statistics.median(latencies)
    final_payload = runs[-1][1]

    with args.output.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["method", "median_ms", "runs_ms", "matched_rows"])
        writer.writerow(
            [
                "Solr facets",
                f"{median_ms:.3f}",
                ";".join(f"{elapsed:.3f}" for elapsed in latencies),
                final_payload["response"]["numFound"],
            ]
        )

    write_counts(final_payload, args.counts_output)
    print(
        f"Solr facets: client median {median_ms:.3f} ms "
        f"({args.repetitions} warm runs), "
        f"{final_payload['response']['numFound']} documents"
    )
    print(f"Timing saved to {args.output}")
    print(f"Facet counts saved to {args.counts_output}")


if __name__ == "__main__":
    main()
