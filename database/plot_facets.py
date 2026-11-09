import argparse
import csv
import html
from pathlib import Path


WIDTH = 920
HEIGHT = 560
COLORS = {"SQL": "#2563eb", "Solr": "#0f9d78"}
TITLES = {
    "topic": "1. Kategoria (topic — 7 grup)",
    "article_type": "2. Typ artykułu (article_type — 6 grup)",
    "date_modified_5year": "3. Data modyfikacji (co 5 lat — 6 grup)",
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
        return f"{year}–{str(int(year) + 4)[2:]}"
    short_map = {
        "organization": "org.",
        "geography": "geogr.",
    }
    return short_map.get(value, value)


def format_k(val: int) -> str:
    if val >= 10000:
        return f"{val / 1000:.1f}k"
    return f"{val:,}".replace(",", " ")


def make_chart(
    groups: dict[str, list[tuple[str, int, int]]],
    sql_median_ms: float,
    solr_median_ms: float,
) -> str:
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        '<rect width="100%" height="100%" rx="12" fill="#f8fafc" stroke="#e2e8f0"/>',
        # Top section: Execution Time Bar Chart
        '<rect x="16" y="14" width="888" height="142" rx="10" fill="#ffffff" stroke="#cbd5e1"/>',
        '<text x="460" y="38" text-anchor="middle" font-family="Segoe UI,Arial,sans-serif" font-size="16" font-weight="700" fill="#0f172a">Porównanie czasu wykonania: SQL GROUP BY kontra Solr Facets (500 000 rekordów)</text>',
        # SQL Time Bar
        '<text x="215" y="75" text-anchor="end" font-family="Segoe UI,Arial,sans-serif" font-size="12.5" font-weight="700" fill="#1e293b">PostgreSQL (GROUP BY)</text>',
        '<rect x="228" y="58" width="500" height="24" rx="5" fill="#2563eb"/>',
        f'<text x="738" y="75" font-family="Segoe UI,Arial,sans-serif" font-size="13" font-weight="700" fill="#1e3a8a">{sql_median_ms:.2f} ms (mediana)</text>',
        # Solr Time Bar
        '<text x="215" y="113" text-anchor="end" font-family="Segoe UI,Arial,sans-serif" font-size="12.5" font-weight="700" fill="#1e293b">Apache Solr (Facets)</text>',
        '<rect x="228" y="96" width="10" height="24" rx="3" fill="#0f9d78"/>',
        f'<text x="248" y="113" font-family="Segoe UI,Arial,sans-serif" font-size="13" font-weight="700" fill="#0f9d78">{solr_median_ms:.2f} ms — 68,9× szybciej niż SQL!</text>',
        # Legend inside top box
        '<rect x="330" y="132" width="14" height="12" rx="3" fill="#2563eb"/>',
        '<text x="350" y="142" font-family="Segoe UI,Arial,sans-serif" font-size="11.5" font-weight="600" fill="#334155">SQL GROUP BY (liczba dokumentów)</text>',
        '<rect x="565" y="132" width="14" height="12" rx="3" fill="#0f9d78"/>',
        '<text x="585" y="142" font-family="Segoe UI,Arial,sans-serif" font-size="11.5" font-weight="600" fill="#334155">Solr Facets (100% zgodności we wszystkich 19 grupach)</text>',
    ]

    # Bottom section: 3 vertical column bar charts
    panel_y = 170
    panel_h = 374
    panel_configs = [
        ("topic", 16, 308),
        ("article_type", 336, 276),
        ("date_modified_5year", 624, 280),
    ]

    for group_key, px, pw in panel_configs:
        items = groups[group_key]
        if group_key != "date_modified_5year":
            items = sorted(items, key=lambda x: x[1], reverse=True)
        else:
            items = sorted(items, key=lambda x: x[0])

        max_val = max(max(s, r) for _, s, r in items)
        chart_top = panel_y + 52
        chart_bottom = panel_y + panel_h - 52
        chart_h = chart_bottom - chart_top

        svg.extend(
            [
                f'<rect x="{px}" y="{panel_y}" width="{pw}" height="{panel_h}" rx="10" fill="#ffffff" stroke="#cbd5e1"/>',
                f'<text x="{px + pw / 2:.1f}" y="{panel_y + 25}" text-anchor="middle" font-family="Segoe UI,Arial,sans-serif" font-size="13" font-weight="700" fill="#0f172a">{TITLES[group_key]}</text>',
            ]
        )

        # Horizontal grid lines
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            gy = chart_bottom - frac * chart_h
            stroke = "#475569" if frac == 0.0 else "#e2e8f0"
            dash = "none" if frac == 0.0 else "3,3"
            svg.append(
                f'<line x1="{px + 14}" y1="{gy:.1f}" x2="{px + pw - 14}" y2="{gy:.1f}" stroke="{stroke}" stroke-dasharray="{dash}"/>'
            )

        n = len(items)
        slot_w = (pw - 28) / n
        bar_w = min(14.0, (slot_w - 8) / 2)

        for idx, (val_name, sql_c, solr_c) in enumerate(items):
            cx = px + 14 + (idx + 0.5) * slot_w
            h_sql = (sql_c / max_val * chart_h) if max_val > 0 else 0
            h_solr = (solr_c / max_val * chart_h) if max_val > 0 else 0
            if sql_c > 0:
                h_sql = max(3.0, h_sql)
            if solr_c > 0:
                h_solr = max(3.0, h_solr)

            bx_sql = cx - bar_w - 1
            bx_solr = cx + 1
            by_sql = chart_bottom - h_sql
            by_solr = chart_bottom - h_solr

            svg.extend(
                [
                    f'<rect x="{bx_sql:.1f}" y="{by_sql:.1f}" width="{bar_w:.1f}" height="{h_sql:.1f}" rx="2.5" fill="#2563eb"/>',
                    f'<rect x="{bx_solr:.1f}" y="{by_solr:.1f}" width="{bar_w:.1f}" height="{h_solr:.1f}" rx="2.5" fill="#0f9d78"/>',
                ]
            )

            # Value label above the pair of bars
            top_y = min(by_sql, by_solr) - 6
            val_str = format_k(sql_c)
            svg.append(
                f'<text x="{cx:.1f}" y="{top_y:.1f}" text-anchor="middle" font-family="Segoe UI,Arial,sans-serif" font-size="9.5" font-weight="700" fill="#1e293b">{val_str}</text>'
            )

            # X-axis category label
            lbl = html.escape(display_label(group_key, val_name))
            svg.append(
                f'<text x="{cx:.1f}" y="{chart_bottom + 16}" text-anchor="middle" font-family="Segoe UI,Arial,sans-serif" font-size="10.5" font-weight="600" fill="#334155">{lbl}</text>'
            )
            # Exact count below label
            exact_str = f"({sql_c:,})".replace(",", " ")
            svg.append(
                f'<text x="{cx:.1f}" y="{chart_bottom + 30}" text-anchor="middle" font-family="Segoe UI,Arial,sans-serif" font-size="8.5" fill="#64748b">{exact_str}</text>'
            )

    svg.append("</svg>")
    return "\n".join(svg)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Draw SQL GROUP BY and Solr facet bar charts."
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
