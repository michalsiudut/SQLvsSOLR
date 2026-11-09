import argparse
import csv
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


CSV_PATH = Path(__file__).resolve().parents[1] / "data-set" / "wikipedia.csv"
REQUIRED_COLUMNS = {
    "id",
    "title",
    "text",
    "topic",
    "article_type",
    "date_modified",
}


def solr_date(value: str) -> str:
    parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    return parsed.replace(tzinfo=timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def post(url: str, body: bytes, content_type: str) -> None:
    request = Request(
        url,
        data=body,
        headers={"Content-Type": content_type},
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            response.read()
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Solr returned HTTP {error.code}: {details}") from error
    except URLError as error:
        raise RuntimeError(f"Could not connect to Solr: {error.reason}") from error


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stream the Wikipedia CSV into an Apache Solr core."
    )
    parser.add_argument("--csv", type=Path, default=CSV_PATH)
    parser.add_argument(
        "--url",
        default=os.environ.get("SOLR_URL", "http://localhost:8983/solr"),
    )
    parser.add_argument(
        "--core", default=os.environ.get("SOLR_CORE", "wikipedia")
    )
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--max-id",
        type=int,
        help="Only load records whose numeric ID is at or below this value.",
    )
    parser.add_argument(
        "--ids-file",
        type=Path,
        help="Load only IDs listed one per line in this file.",
    )
    parser.add_argument(
        "--timing-output",
        type=Path,
        default=Path("csv/solr_import_results.csv"),
        help="CSV file for the load elapsed-time result.",
    )
    args = parser.parse_args()

    if args.batch_size < 1:
        parser.error("--batch-size must be at least 1")
    if args.max_id is not None and args.ids_file is not None:
        parser.error("--max-id and --ids-file cannot be used together")
    if not args.csv.is_file():
        parser.error(f"CSV file not found: {args.csv}")
    selected_ids: set[str] | None = None
    if args.ids_file is not None:
        if not args.ids_file.is_file():
            parser.error(f"IDs file not found: {args.ids_file}")
        selected_ids = {
            line.strip()
            for line in args.ids_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

    endpoint = f"{args.url.rstrip('/')}/{args.core}/update?wt=json"
    batch: list[dict[str, str]] = []
    sent = 0
    started_at = time.perf_counter()

    with args.csv.open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            parser.error(f"CSV is missing required columns: {', '.join(sorted(missing))}")

        for row in reader:
            if selected_ids is not None and row["id"] not in selected_ids:
                continue
            if args.max_id is not None and int(row["id"]) > args.max_id:
                continue
            batch.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "text": row["text"],
                    "topic": row["topic"],
                    "article_type": row["article_type"],
                    "date_modified": solr_date(row["date_modified"]),
                }
            )
            if len(batch) >= args.batch_size:
                post(endpoint, json.dumps(batch, ensure_ascii=False).encode("utf-8"),
                     "application/json; charset=utf-8")
                sent += len(batch)
                batch.clear()
                if sent % 10_000 == 0:
                    print(f"Sent {sent:,} documents", flush=True)

    if batch:
        post(endpoint, json.dumps(batch, ensure_ascii=False).encode("utf-8"),
             "application/json; charset=utf-8")
        sent += len(batch)

    post(
        f"{args.url.rstrip('/')}/{args.core}/update?commit=true&wt=json",
        b"<commit/>",
        "application/xml",
    )
    elapsed_seconds = time.perf_counter() - started_at
    args.timing_output.parent.mkdir(parents=True, exist_ok=True)
    with args.timing_output.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["core", "documents", "elapsed_seconds"])
        writer.writerow([args.core, sent, f"{elapsed_seconds:.3f}"])
    print(f"Committed {sent:,} documents to Solr core '{args.core}'.")
    print(
        f"Import and commit took {elapsed_seconds:.3f} seconds; "
        f"timing saved to {args.timing_output}."
    )


if __name__ == "__main__":
    main()
