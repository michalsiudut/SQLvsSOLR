import argparse
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


FIELDS = ("title", "text", "topic", "article_type")


class SyncTest:
    def __init__(
        self,
        docker_command: str,
        container: str,
        database: str,
        user: str,
        solr_url: str,
        core: str,
    ) -> None:
        self.docker_command = shlex.split(docker_command)
        if not self.docker_command:
            raise ValueError("--docker-command cannot be empty")
        self.container = container
        self.database = database
        self.user = user
        self.solr_url = solr_url.rstrip("/")
        self.core = core
        base_id = -time.time_ns()
        self.ids = [base_id - offset for offset in range(4)]
        self.sync_script = str(Path(__file__).with_name("sync_outbox.py"))

    def psql(self, query: str) -> str:
        command = [
            *self.docker_command,
            "exec",
            "-i",
            self.container,
            "psql",
            "-X",
            "-q",
            "-A",
            "-t",
            "-F",
            "\t",
            "-U",
            self.user,
            "-d",
            self.database,
            "-c",
            query,
        ]
        result = subprocess.run(
            command, capture_output=True, text=True, check=False
        )
        if result.returncode:
            raise RuntimeError(
                f"PostgreSQL command failed ({result.returncode}): "
                f"{result.stderr.strip()}"
            )
        return result.stdout.strip()

    def require_ready(self) -> None:
        status = self.psql(
            "SELECT to_regclass('public.solr_sync_outbox') IS NOT NULL "
            "AND EXISTS (SELECT 1 FROM pg_trigger "
            "WHERE tgname='wikipedia_articles_solr_sync' AND NOT tgisinternal)"
        )
        if status != "t":
            raise RuntimeError(
                "Outbox migration or wikipedia_articles_solr_sync trigger is missing."
            )
        pending = self.psql(
            "SELECT count(*) FROM solr_sync_outbox WHERE synced_at IS NULL"
        )
        if int(pending):
            raise RuntimeError(
                "Refusing to consume pre-existing outbox events; run the normal "
                "consumer first."
            )
        existing = self.psql(
            "SELECT count(*) FROM wikipedia_articles "
            f"WHERE id IN ({self.id_list})"
        )
        if int(existing):
            raise RuntimeError("Generated test IDs already exist; retry the test.")

    @property
    def id_list(self) -> str:
        return ", ".join(str(doc_id) for doc_id in self.ids)

    def run_sync(self) -> None:
        command = [
            sys.executable,
            self.sync_script,
            "--docker-command",
            " ".join(shlex.quote(part) for part in self.docker_command),
            "--container",
            self.container,
            "--database",
            self.database,
            "--user",
            self.user,
            "--solr-url",
            self.solr_url,
            "--core",
            self.core,
        ]
        subprocess.run(command, check=True)

    def insert_documents(self) -> None:
        values = []
        for index, doc_id in enumerate(self.ids):
            title = f"PJN sync test {index} before update"
            text = f"Temporary sync integration document number {index}."
            values.append(
                f"({doc_id},'{title}','{text}','other','general',"
                "timestamp '2026-01-01',"
                f"to_tsvector('english','{title} {text}'))"
            )
        self.psql(
            "INSERT INTO wikipedia_articles "
            "(id,title,text,topic,article_type,date_modified,search_vector) "
            "VALUES " + ", ".join(values)
        )

    def update_documents(self) -> None:
        first, second = self.ids[:2]
        self.psql(
            "UPDATE wikipedia_articles SET "
            "title = 'PJN sync test updated', "
            "text = 'Updated temporary sync integration document.', "
            "topic = 'science', article_type = 'event', "
            "search_vector = to_tsvector('english', "
            "'PJN sync test updated Updated temporary sync integration document.') "
            f"WHERE id IN ({first}, {second})"
        )

    def delete_documents(self) -> None:
        self.psql(f"DELETE FROM wikipedia_articles WHERE id IN ({self.ids[2]}, {self.ids[3]})")

    def sql_state(self) -> dict[str, tuple[str, ...]]:
        result = self.psql(
            "SELECT id::text, title, text, topic, article_type "
            "FROM wikipedia_articles "
            f"WHERE id IN ({self.id_list}) ORDER BY id"
        )
        if not result:
            return {}
        documents: dict[str, tuple[str, ...]] = {}
        for line in result.splitlines():
            fields = line.split("\t")
            if len(fields) != len(FIELDS) + 1:
                raise RuntimeError(f"Unexpected SQL test row: {line!r}")
            documents[fields[0]] = tuple(fields[1:])
        return documents

    def solr_document(self, doc_id: str) -> dict | None:
        params = urlencode({"id": doc_id, "wt": "json"})
        url = f"{self.solr_url}/{self.core}/get?{params}"
        with urlopen(url, timeout=120) as response:
            payload = json.load(response)
        if "doc" not in payload:
            raise RuntimeError(f"Solr realtime-get response has no 'doc': {payload}")
        document = payload["doc"]
        if document is not None and not isinstance(document, dict):
            raise RuntimeError(f"Unexpected Solr realtime-get document: {document!r}")
        return document

    def verify_state(self, expected_count: int, label: str) -> None:
        sql_documents = self.sql_state()
        if len(sql_documents) != expected_count:
            raise RuntimeError(
                f"{label}: expected {expected_count} SQL rows, "
                f"found {len(sql_documents)}."
            )
        for doc_id in self.ids:
            sql_values = sql_documents.get(str(doc_id))
            solr_doc = self.solr_document(str(doc_id))
            if sql_values is None:
                if solr_doc is not None:
                    raise RuntimeError(
                        f"{label}: deleted SQL ID {doc_id} is still in Solr."
                    )
                continue
            if solr_doc is None:
                raise RuntimeError(f"{label}: SQL ID {doc_id} is missing in Solr.")
            solr_values = tuple(str(solr_doc.get(field, "")) for field in FIELDS)
            if sql_values != solr_values:
                raise RuntimeError(
                    f"{label}: SQL and Solr differ for ID {doc_id}: "
                    f"{sql_values!r} != {solr_values!r}"
                )
        print(f"{label}: SQL and Solr agree for {expected_count} documents.")

    def cleanup(self) -> None:
        self.psql(f"DELETE FROM wikipedia_articles WHERE id IN ({self.id_list})")
        self.run_sync()

    def run(self) -> None:
        self.require_ready()
        try:
            self.insert_documents()
            self.run_sync()
            self.verify_state(4, "INSERT")

            self.update_documents()
            self.run_sync()
            self.verify_state(4, "UPDATE")

            self.delete_documents()
            self.run_sync()
            self.verify_state(2, "DELETE")
        finally:
            self.cleanup()
        print("Multi-record INSERT, UPDATE and DELETE synchronization passed.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check multi-record PostgreSQL-to-Solr synchronization."
    )
    parser.add_argument(
        "--docker-command", default="sudo docker"
    )
    parser.add_argument("--container", default="lab3-postgres")
    parser.add_argument("--database", default="lab3")
    parser.add_argument("--user", default="lab3")
    parser.add_argument("--solr-url", default="http://localhost:8983/solr")
    parser.add_argument("--core", default="wikipedia")
    args = parser.parse_args()
    SyncTest(
        args.docker_command,
        args.container,
        args.database,
        args.user,
        args.solr_url,
        args.core,
    ).run()


if __name__ == "__main__":
    main()
