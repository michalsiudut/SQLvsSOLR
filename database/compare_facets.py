import argparse
import csv
from pathlib import Path


def load_counts(path: Path) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            key = (row["group_by"], row["value"])
            if key in counts:
                raise ValueError(f"Duplicate facet count in {path}: {key}")
            counts[key] = int(row["documents"])
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare SQL GROUP BY and Solr facet counts."
    )
    parser.add_argument("--sql", type=Path, default=Path("sql_facet_counts.csv"))
    parser.add_argument("--solr", type=Path, default=Path("solr_facet_counts.csv"))
    parser.add_argument(
        "--output", type=Path, default=Path("facet_comparison.csv")
    )
    args = parser.parse_args()

    sql_counts = load_counts(args.sql)
    solr_counts = load_counts(args.solr)
    if not sql_counts or not solr_counts:
        parser.error("Both SQL and Solr facet count files must contain rows.")

    keys = sorted(sql_counts.keys() | solr_counts.keys())
    with args.output.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(
            ["group_by", "value", "sql_documents", "solr_documents", "difference", "match"]
        )
        for group_by, value in keys:
            sql_value = sql_counts.get((group_by, value), 0)
            solr_value = solr_counts.get((group_by, value), 0)
            writer.writerow(
                [
                    group_by,
                    value,
                    sql_value,
                    solr_value,
                    sql_value - solr_value,
                    "yes" if sql_value == solr_value else "no",
                ]
            )

    mismatches = [
        key
        for key in keys
        if sql_counts.get(key, 0) != solr_counts.get(key, 0)
    ]
    print(
        f"Compared {len(keys)} groups: "
        f"{len(keys) - len(mismatches)} match, {len(mismatches)} differ."
    )
    print(f"Comparison saved to {args.output}")
    if mismatches:
        print("Differences:")
        for group_by, value in mismatches:
            print(
                f"  {group_by} / {value}: "
                f"SQL={sql_counts.get((group_by, value), 0)}, "
                f"Solr={solr_counts.get((group_by, value), 0)}"
            )


if __name__ == "__main__":
    main()
