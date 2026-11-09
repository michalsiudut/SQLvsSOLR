import argparse
import csv
import json
import statistics
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


CORE_SIZES = (
    ("wikipedia_50000", 50_000),
    ("wikipedia_250000", 250_000),
    ("wikipedia", 500_000),
)


def query_solr(base_url: str, core: str) -> tuple[float, int, int]:
    params = urlencode(
        {
            "q": "run",
            "defType": "edismax",
            "qf": "title^3 text",
            "rows": 0,
            "wt": "json",
        }
    )
    url = f"{base_url.rstrip('/')}/{core}/select?{params}"
    started_at = time.perf_counter()
    with urlopen(url, timeout=120) as response:
        payload = json.load(response)
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    if payload["responseHeader"]["status"] != 0:
        raise RuntimeError(f"Solr query failed for core {core}: {payload}")
    return (
        elapsed_ms,
        int(payload["responseHeader"]["QTime"]),
        int(payload["response"]["numFound"]),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure warmed Solr query latency at three index sizes."
    )
    parser.add_argument(
        "--url", default="http://localhost:8983/solr", help="Solr base URL"
    )
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument(
        "--output", type=Path, default=Path("csv/solr_scale_results.csv")
    )
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")

    with args.output.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(
            [
                "records",
                "method",
                "median_ms",
                "runs_ms",
                "server_qtime_runs_ms",
                "matched_rows",
            ]
        )
        for core, record_count in CORE_SIZES:
            query_solr(args.url, core)
            runs = [query_solr(args.url, core) for _ in range(args.repetitions)]
            latencies = [elapsed for elapsed, _, _ in runs]
            server_times = [server_time for _, server_time, _ in runs]
            matched_rows = runs[-1][2]
            writer.writerow(
                [
                    record_count,
                    "Solr",
                    f"{statistics.median(latencies):.3f}",
                    ";".join(f"{elapsed:.3f}" for elapsed in latencies),
                    ";".join(str(elapsed) for elapsed in server_times),
                    matched_rows,
                ]
            )
            print(
                f"{record_count}: client median "
                f"{statistics.median(latencies):.3f} ms "
                f"(warm, {args.repetitions} runs), "
                f"server QTime {statistics.median(server_times):.1f} ms, "
                f"{matched_rows} matches"
            )

    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
