import argparse
import csv
import math
from pathlib import Path


COLORS = {"LIKE": "#dc2626", "Full text": "#2563eb", "Solr": "#0f9d78"}
LABELS = {
    "LIKE": "PostgreSQL LIKE ('%run%')",
    "Full text": "PostgreSQL Full-Text (GIN)",
    "Solr": "Apache Solr (eDisMax)",
}
WIDTH = 920
HEIGHT = 520
LEFT = 105
RIGHT = 75
TOP = 95
BOTTOM = 95


def read_results(path: Path, size_column: str) -> dict[str, list[tuple[int, float]]]:
    series: dict[str, list[tuple[int, float]]] = {}
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            method = row["method"]
            series.setdefault(method, []).append(
                (int(row[size_column]), float(row["median_ms"]))
            )
    return series


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create an SVG scaling chart from SQL and Solr benchmark CSVs."
    )
    parser.add_argument("--sql", type=Path, default=Path("csv/sql_scale_results.csv"))
    parser.add_argument(
        "--solr", type=Path, default=Path("csv/solr_scale_results.csv")
    )
    parser.add_argument("--output", type=Path, default=Path("svg/scale_chart.svg"))
    args = parser.parse_args()

    series = read_results(args.sql, "record_count")
    series.update(read_results(args.solr, "records"))
    points = [point for values in series.values() for point in values]
    if not points:
        parser.error("No benchmark results found in the CSV files.")

    x_min, x_max = min(x for x, _ in points), max(x for x, _ in points)
    y_min = 1.0
    y_max = 1200.0
    plot_width = WIDTH - LEFT - RIGHT
    plot_height = HEIGHT - TOP - BOTTOM
    log_min, log_max = math.log10(y_min), math.log10(y_max)

    def x_pos(value: int) -> float:
        if x_min == x_max:
            return LEFT + plot_width / 2
        return LEFT + (value - x_min) / (x_max - x_min) * plot_width

    def y_pos(value: float) -> float:
        value = max(value, y_min)
        return TOP + (log_max - math.log10(value)) / (log_max - log_min) * plot_height

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        '<rect width="100%" height="100%" rx="12" fill="#f8fafc"/>',
        f'<rect x="16" y="16" width="{WIDTH - 32}" height="{HEIGHT - 32}" rx="10" fill="#ffffff" stroke="#e2e8f0"/>',
        f'<text x="{WIDTH / 2:.0f}" y="48" text-anchor="middle" font-family="Arial,sans-serif" font-size="20" font-weight="700" fill="#0f172a">Skalowanie czasu wyszukiwania wzgledem wielkosci zbioru (skala logarytmiczna)</text>',
        f'<text x="{WIDTH / 2:.0f}" y="70" text-anchor="middle" font-family="Arial,sans-serif" font-size="12.5" fill="#475569">Mediana z 5 powtorzen po rozgrzewce (50 000, 250 000 i 500 000 rekordow)</text>',
    ]

    for tick_val in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000):
        y = y_pos(float(tick_val))
        is_major = tick_val in (1, 10, 100, 1000)
        stroke = "#cbd5e1" if is_major else "#f1f5f9"
        svg.append(
            f'<line x1="{LEFT}" y1="{y:.1f}" x2="{WIDTH - RIGHT}" y2="{y:.1f}" stroke="{stroke}" stroke-dasharray="{"none" if is_major else "4,4"}"/>'
        )
        svg.append(
            f'<text x="{LEFT - 12}" y="{y + 4:.1f}" text-anchor="end" font-family="Arial,sans-serif" font-size="11.5" font-weight="{"700" if is_major else "400"}" fill="#334155">{tick_val} ms</text>'
        )

    svg.extend(
        [
            f'<line x1="{LEFT}" y1="{TOP}" x2="{LEFT}" y2="{HEIGHT - BOTTOM}" stroke="#475569" stroke-width="1.5"/>',
            f'<line x1="{LEFT}" y1="{HEIGHT - BOTTOM}" x2="{WIDTH - RIGHT}" y2="{HEIGHT - BOTTOM}" stroke="#475569" stroke-width="1.5"/>',
            f'<text x="{(LEFT + WIDTH - RIGHT) / 2:.1f}" y="{HEIGHT - 50}" text-anchor="middle" font-family="Arial,sans-serif" font-size="13" font-weight="700" fill="#1e293b">Liczba rekordow w zbiorze</text>',
            f'<text x="34" y="{(TOP + HEIGHT - BOTTOM) / 2:.1f}" transform="rotate(-90 34 {(TOP + HEIGHT - BOTTOM) / 2:.1f})" text-anchor="middle" font-family="Arial,sans-serif" font-size="13" font-weight="700" fill="#1e293b">Mediana czasu zapytania (ms, skala log)</text>',
        ]
    )

    x_ticks = sorted({x for x, _ in points})
    pct_labels = {50000: "50 000 (10%)", 250000: "250 000 (50%)", 500000: "500 000 (100%)"}
    for value in x_ticks:
        x = x_pos(value)
        svg.append(
            f'<line x1="{x:.1f}" y1="{TOP}" x2="{x:.1f}" y2="{HEIGHT - BOTTOM}" stroke="#f1f5f9"/>'
        )
        svg.append(
            f'<line x1="{x:.1f}" y1="{HEIGHT - BOTTOM}" x2="{x:.1f}" y2="{HEIGHT - BOTTOM + 6}" stroke="#475569" stroke-width="1.5"/>'
        )
        label_str = pct_labels.get(value, f"{value:,}")
        svg.append(
            f'<text x="{x:.1f}" y="{HEIGHT - BOTTOM + 22}" text-anchor="middle" font-family="Arial,sans-serif" font-size="12" font-weight="600" fill="#1e293b">{label_str}</text>'
        )

    label_offsets = {
        "LIKE": -12,
        "Full text": -12,
        "Solr": 18,
    }
    for name in ("LIKE", "Full text", "Solr"):
        if name not in series:
            continue
        values = series[name]
        color = COLORS.get(name, "#555")
        ordered = sorted(values)
        coords = " ".join(
            f"{x_pos(x):.1f},{y_pos(y):.1f}" for x, y in ordered
        )
        svg.append(
            f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="3"/>'
        )
        for idx, (x, y) in enumerate(ordered):
            cx, cy = x_pos(x), y_pos(y)
            svg.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5.5" fill="#ffffff" stroke="{color}" stroke-width="3"/>'
            )
            dy = label_offsets.get(name, -10)
            if name == "Full text" and idx == 0:
                dy = -14
            anchor = "start" if idx == 0 else ("end" if idx == len(ordered) - 1 else "middle")
            dx = 6 if idx == 0 else (-6 if idx == len(ordered) - 1 else 0)
            svg.append(
                f'<text x="{cx + dx:.1f}" y="{cy + dy:.1f}" text-anchor="{anchor}" font-family="Arial,sans-serif" font-size="11.5" font-weight="700" fill="{color}">{y:.2f} ms</text>'
            )

    legend_items = ["LIKE", "Full text", "Solr"]
    legend_x = 155
    for name in legend_items:
        color = COLORS.get(name, "#555")
        label = LABELS.get(name, name)
        svg.append(
            f'<rect x="{legend_x}" y="{HEIGHT - 34}" width="18" height="10" rx="3" fill="{color}"/>'
        )
        svg.append(
            f'<text x="{legend_x + 24}" y="{HEIGHT - 25}" font-family="Arial,sans-serif" font-size="12" font-weight="600" fill="#1e293b">{label}</text>'
        )
        legend_x += 235

    svg.append("</svg>")
    args.output.write_text("\n".join(svg), encoding="utf-8")
    print(f"Chart saved to {args.output}")


if __name__ == "__main__":
    main()
