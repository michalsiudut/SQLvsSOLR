import argparse
import csv
import math
from pathlib import Path


COLORS = {"LIKE": "#d62728", "Full text": "#1f77b4", "Solr": "#2ca02c"}
WIDTH = 800
HEIGHT = 500
LEFT = 90
RIGHT = 35
TOP = 55
BOTTOM = 75


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
    y_min = min(y for _, y in points if y > 0)
    y_max = max(y for _, y in points)
    plot_width = WIDTH - LEFT - RIGHT
    plot_height = HEIGHT - TOP - BOTTOM
    log_min, log_max = math.log10(y_min), math.log10(y_max * 1.15)

    def x_pos(value: int) -> float:
        if x_min == x_max:
            return LEFT + plot_width / 2
        return LEFT + (value - x_min) / (x_max - x_min) * plot_width

    def y_pos(value: float) -> float:
        value = max(value, y_min)
        return TOP + (log_max - math.log10(value)) / (log_max - log_min) * plot_height

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="400" y="28" text-anchor="middle" font-family="sans-serif" font-size="18">Search time vs. dataset size (log scale)</text>',
    ]

    for tick in range(math.ceil(log_min), math.floor(log_max) + 1):
        value = 10**tick
        y = y_pos(value)
        svg.append(
            f'<line x1="{LEFT}" y1="{y:.1f}" x2="{WIDTH - RIGHT}" y2="{y:.1f}" stroke="#ddd"/>'
        )
        svg.append(
            f'<text x="{LEFT - 10}" y="{y + 4:.1f}" text-anchor="end" font-family="sans-serif" font-size="12">{value:g}</text>'
        )

    svg.extend(
        [
            f'<line x1="{LEFT}" y1="{TOP}" x2="{LEFT}" y2="{HEIGHT - BOTTOM}" stroke="black"/>',
            f'<line x1="{LEFT}" y1="{HEIGHT - BOTTOM}" x2="{WIDTH - RIGHT}" y2="{HEIGHT - BOTTOM}" stroke="black"/>',
            f'<text x="{(LEFT + WIDTH - RIGHT) / 2:.1f}" y="{HEIGHT - 25}" text-anchor="middle" font-family="sans-serif" font-size="14">Records</text>',
            f'<text x="22" y="{HEIGHT / 2}" transform="rotate(-90 22 {HEIGHT / 2})" text-anchor="middle" font-family="sans-serif" font-size="14">Median query time (ms)</text>',
        ]
    )

    x_ticks = sorted({x for x, _ in points})
    for value in x_ticks:
        x = x_pos(value)
        svg.append(
            f'<line x1="{x:.1f}" y1="{HEIGHT - BOTTOM}" x2="{x:.1f}" y2="{HEIGHT - BOTTOM + 5}" stroke="black"/>'
        )
        svg.append(
            f'<text x="{x:.1f}" y="{HEIGHT - BOTTOM + 22}" text-anchor="middle" font-family="sans-serif" font-size="12">{value:,}</text>'
        )

    for name, values in series.items():
        color = COLORS.get(name, "#555")
        ordered = sorted(values)
        coords = " ".join(
            f"{x_pos(x):.1f},{y_pos(y):.1f}" for x, y in ordered
        )
        svg.append(
            f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2.5"/>'
        )
        for x, y in ordered:
            svg.append(
                f'<circle cx="{x_pos(x):.1f}" cy="{y_pos(y):.1f}" r="4" fill="{color}"/>'
            )

    legend_x = LEFT
    for name in series:
        color = COLORS.get(name, "#555")
        svg.append(
            f'<line x1="{legend_x}" y1="472" x2="{legend_x + 22}" y2="472" stroke="{color}" stroke-width="3"/>'
        )
        svg.append(
            f'<text x="{legend_x + 28}" y="476" font-family="sans-serif" font-size="12">{name}</text>'
        )
        legend_x += 120

    svg.append("</svg>")
    args.output.write_text("\n".join(svg), encoding="utf-8")
    print(f"Chart saved to {args.output}")


if __name__ == "__main__":
    main()
