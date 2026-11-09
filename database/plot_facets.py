import argparse
import csv
import html
from pathlib import Path


WIDTH = 1200
HEIGHT = 600
PANEL_WIDTH = 365
PANEL_GAP = 25
PANEL_TOP = 145
ROW_HEIGHT = 48
LABEL_WIDTH = 100
BAR_WIDTH = 165
COLORS = {"SQL": "#2563eb", "Solr": "#0f9d78"}
TITLES = {
    "topic": "TOPIC",
    "article_type": "ARTICLE TYPE",
    "date_modified_5year": "MODIFIED DATE",
}


def read_comparison(path: Path) -> dict[str, list[tuple[str, int, int]]]:
    groups: dict[str, list[tuple[str, int, int]]] = {}
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            group = row["group_by"]
            if group not in TITLES:
                raise ValueError(f"Unknown comparison group in {path}: {group}")
            groups.setdefault(group, []).append(
                (row["value"], int(row["sql_documents"]), int(row["solr_documents"]))
            )
    missing = set(TITLES) - groups.keys()
    if missing:
        raise ValueError(
            f"Missing comparison groups in {path}: {', '.join(sorted(missing))}"
        )
    return groups


def read_median(path: Path, expected_method: str) -> float:
    with path.open(newline="", encoding="utf-8") as source:
        rows = [
            row
            for row in csv.DictReader(source)
            if row["method"] == expected_method
        ]
    if len(rows) != 1:
        raise ValueError(f"Expected one '{expected_method}' result in {path}")
    return float(rows[0]["median_ms"])


def display_label(group: str, value: str) -> str:
    if group == "date_modified_5year":
        year = value[:4]
        return f"{year}–{int(year) + 4}"
    return value


def make_chart(
    groups: dict[str, list[tuple[str, int, int]]],
    sql_median_ms: float,
    solr_median_ms: float,
) -> str:
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        '<rect width="100%" height="100%" fill="#f3f6fb"/>',
        '<text x="600" y="40" text-anchor="middle" font-family="Arial,sans-serif" font-size="25" font-weight="700" fill="#172033">SQL GROUP BY vs. Solr Facets</text>',
        f'<text x="600" y="68" text-anchor="middle" font-family="Arial,sans-serif" font-size="13" fill="#536176">500,000 articles  •  SQL median: {sql_median_ms:.3f} ms  •  Solr median: {solr_median_ms:.3f} ms</text>',
        '<rect x="440" y="88" width="13" height="13" rx="3" fill="#2563eb"/>',
        '<text x="460" y="99" font-family="Arial,sans-serif" font-size="12" fill="#35445a">SQL GROUP BY</text>',
        '<rect x="585" y="88" width="13" height="13" rx="3" fill="#0f9d78"/>',
        '<text x="605" y="99" font-family="Arial,sans-serif" font-size="12" fill="#35445a">Solr Facet</text>',
    ]

    all_match = True
    for panel_index, group in enumerate(TITLES):
        x = 25 + panel_index * (PANEL_WIDTH + PANEL_GAP)
        values = sorted(groups[group], key=lambda item: max(item[1], item[2]), reverse=True)
        max_count = max(max(sql_value, solr_value) for _, sql_value, solr_value in values)
        panel_height = 78 + len(values) * ROW_HEIGHT
        svg.extend(
            [
                f'<rect x="{x}" y="118" width="{PANEL_WIDTH}" height="{panel_height}" rx="14" fill="#ffffff" stroke="#e0e6ef"/>',
                f'<text x="{x + 18}" y="148" font-family="Arial,sans-serif" font-size="14" font-weight="700" letter-spacing="1" fill="#26354a">{TITLES[group]}</text>',
                f'<text x="{x + PANEL_WIDTH - 18}" y="148" text-anchor="end" font-family="Arial,sans-serif" font-size="11" fill="#78869a">{len(values)} groups</text>',
            ]
        )
        for index, (value, sql_value, solr_value) in enumerate(values):
            y = PANEL_TOP + 39 + index * ROW_HEIGHT
            label = html.escape(display_label(group, value))
            svg.append(
                f'<text x="{x + 18}" y="{y + 3}" font-family="Arial,sans-serif" font-size="11" fill="#35445a">{label}</text>'
            )
            for offset, name, count in (
                (8, "SQL", sql_value),
                (24, "Solr", solr_value),
            ):
                width = max(1, count / max_count * BAR_WIDTH) if count else 0
                svg.extend(
                    [
                        f'<rect x="{x + 18 + LABEL_WIDTH}" y="{y + offset - 8}" width="{BAR_WIDTH}" height="11" rx="5.5" fill="#edf1f7"/>',
                        f'<rect x="{x + 18 + LABEL_WIDTH}" y="{y + offset - 8}" width="{width:.1f}" height="11" rx="5.5" fill="{COLORS[name]}"/>',
                        f'<text x="{x + 18 + LABEL_WIDTH + BAR_WIDTH + 6}" y="{y + offset + 1}" font-family="Arial,sans-serif" font-size="10" fill="#536176">{count:,}</text>',
                    ]
                )
            all_match = all_match and sql_value == solr_value

    verdict = (
        "All SQL and Solr group counts match."
        if all_match
        else "Differences are listed in csv/facet_comparison.csv."
    )
    svg.extend(
        [
            f'<text x="600" y="580" text-anchor="middle" font-family="Arial,sans-serif" font-size="11" fill="#536176">{verdict} Counts use the same dataset and date buckets.</text>',
            "</svg>",
        ]
    )
    return "\n".join(svg)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Draw SQL GROUP BY and Solr facet count comparisons."
    )
    parser.add_argument(
        "--comparison",
        type=Path,
        default=Path("csv/facet_comparison.csv"),
    )
    parser.add_argument(
        "--sql-timing",
        type=Path,
        default=Path("csv/sql_facets_results.csv"),
    )
    parser.add_argument(
        "--solr-timing",
        type=Path,
        default=Path("csv/solr_facets_results.csv"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("svg/facet_comparison.svg")
    )
    args = parser.parse_args()

    groups = read_comparison(args.comparison)
    sql_median_ms = read_median(args.sql_timing, "SQL GROUP BY")
    solr_median_ms = read_median(args.solr_timing, "Solr facets")
    args.output.write_text(
        make_chart(groups, sql_median_ms, solr_median_ms),
        encoding="utf-8",
    )
    print(f"Chart saved to {args.output}")


if __name__ == "__main__":
    main()
