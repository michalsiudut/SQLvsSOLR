import argparse
import csv
import json
import math
import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class SyncEvent:
    event_id: int
    operation: str
    doc_id: str
    payload: dict[str, str] | None


def run_psql(docker_command: list[str], container: str, database: str,
             user: str, query: str, input_text: str | None = None) -> str:
    command = [
        *docker_command,
        "exec",
        "-i",
        container,
        "psql",
        "-X",
        "-q",
        "-A",
        "-t",
        "-F",
        "\t",
        "-U",
        user,
        "-d",
        database,
        "-c",
        query,
    ]
    result = subprocess.run(
        command,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"PostgreSQL command failed ({result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return result.stdout


def fetch_events(
    docker_command: list[str],
    container: str,
    database: str,
    user: str,
    batch_size: int,
) -> list[SyncEvent]:
    query = (
        "SELECT event_id, operation, doc_id, coalesce(payload::text, '') "
        "FROM solr_sync_outbox WHERE synced_at IS NULL "
        f"ORDER BY event_id LIMIT {batch_size}"
    )
    output = run_psql(docker_command, container, database, user, query)
    events: list[SyncEvent] = []
    for line in output.splitlines():
        if not line:
            continue
        fields = line.split("\t", 3)
        if len(fields) != 4:
            raise RuntimeError(f"Unexpected outbox row from psql: {line!r}")
        event_id_text, operation, doc_id, payload_text = fields
        payload = json.loads(payload_text) if payload_text else None
        event = SyncEvent(int(event_id_text), operation, doc_id, payload)
        if event.operation not in {"upsert", "delete"}:
            raise RuntimeError(f"Unsupported outbox operation: {event.operation}")
        if event.operation == "upsert" and (
            event.payload is None or event.payload.get("id") != event.doc_id
        ):
            raise RuntimeError(f"Invalid upsert payload for outbox event {event.event_id}")
        events.append(event)
    return events


def post_json(url: str, document: dict | list) -> None:
    request = Request(
        url,
        data=json.dumps(document, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            result = json.load(response)
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Solr returned HTTP {error.code}: {details}") from error
    except URLError as error:
        raise RuntimeError(f"Could not connect to Solr: {error.reason}") from error
    if result.get("responseHeader", {}).get("status") != 0:
        raise RuntimeError(f"Solr update failed: {result}")


def post_commit(url: str) -> None:
    request = Request(
        f"{url}/update?wt=json",
        data=b"<commit/>",
        headers={"Content-Type": "application/xml"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            result = json.load(response)
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Solr commit failed with HTTP {error.code}: {details}") from error
    except URLError as error:
        raise RuntimeError(f"Could not connect to Solr: {error.reason}") from error
    if result.get("responseHeader", {}).get("status") != 0:
        raise RuntimeError(f"Solr commit failed: {result}")


def acknowledge_events(
    docker_command: list[str],
    container: str,
    database: str,
    user: str,
    event_ids: list[int],
) -> None:
    ids = ", ".join(str(event_id) for event_id in event_ids)
    query = (
        "UPDATE solr_sync_outbox SET synced_at = clock_timestamp() "
        f"WHERE synced_at IS NULL AND event_id IN ({ids})"
    )
    run_psql(docker_command, container, database, user, query)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deliver pending PostgreSQL outbox events to Solr."
    )
    parser.add_argument(
        "--docker-command",
        default=os.environ.get("DOCKER_COMMAND", "sudo docker"),
        help="Docker command, e.g. 'sudo docker' or 'docker'",
    )
    parser.add_argument(
        "--container", default=os.environ.get("POSTGRES_CONTAINER", "lab3-postgres")
    )
    parser.add_argument("--database", default=os.environ.get("POSTGRES_DB", "lab3"))
    parser.add_argument("--user", default=os.environ.get("POSTGRES_USER", "lab3"))
    parser.add_argument(
        "--solr-url", default=os.environ.get("SOLR_URL", "http://localhost:8983/solr")
    )
    parser.add_argument("--core", default=os.environ.get("SOLR_CORE", "wikipedia"))
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument(
        "--watch",
        action="store_true",
        help="poll PostgreSQL continuously and deliver new changes to Solr",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="seconds to wait between empty outbox polls in --watch mode",
    )
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be at least 1")
    if not math.isfinite(args.poll_interval) or args.poll_interval <= 0:
        parser.error("--poll-interval must be a finite number greater than 0")
    docker_command = shlex.split(args.docker_command)
    if not docker_command:
        parser.error("--docker-command cannot be empty")

    update_url = f"{args.solr_url.rstrip('/')}/{args.core}/update?wt=json"
    while True:
        events = fetch_events(
            docker_command,
            args.container,
            args.database,
            args.user,
            args.batch_size,
        )
        if not events:
            if not args.watch:
                print("No pending SQL → Solr events.")
                return
            time.sleep(args.poll_interval)
            continue

        for event in events:
            if event.operation == "upsert":
                post_json(update_url, [event.payload])
            else:
                post_json(update_url, {"delete": {"id": event.doc_id}})

        post_commit(f"{args.solr_url.rstrip('/')}/{args.core}")
        acknowledge_events(
            docker_command,
            args.container,
            args.database,
            args.user,
            [event.event_id for event in events],
        )
        print(f"Synchronized and acknowledged {len(events)} event(s).")


if __name__ == "__main__":
    main()
