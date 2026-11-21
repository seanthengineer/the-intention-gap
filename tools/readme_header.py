"""Build the README header images from frozen public M11 outputs.

The line is the observed U.S. period total fertility rate (Human Fertility Database estimates
reproduced in data/public/m11/forecast/m11_fc_tfr_backtest_records.csv) and the dashed segment is
the frozen M11 no-change forecast to 2040 (m11_fc_tfr_forecast.csv). No value is computed here
beyond selecting rows. Usage: python -m tools.readme_header [--check]
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKTEST = ROOT / "data" / "public" / "m11" / "forecast" / "m11_fc_tfr_backtest_records.csv"
FORECAST = ROOT / "data" / "public" / "m11" / "forecast" / "m11_fc_tfr_forecast.csv"
OUT_DIR = ROOT / "assets" / "readme"

THEMES = {
    "light": {"bg": "#fbfaf7", "ink": "#1d1d1b", "muted": "#5f5f59", "rule": "#d9d6cc",
              "line": "#1c5cab", "forecast": "#1c5cab"},
    "dark": {"bg": "#0d1117", "ink": "#e6edf3", "muted": "#9aa3ad", "rule": "#30363d",
             "line": "#79b0ff", "forecast": "#79b0ff"},
}

WIDTH, HEIGHT = 1280, 320
PLOT = {"x0": 676.0, "x1": 1220.0, "y0": 64.0, "y1": 248.0}
YEARS = (1953, 2040)
TFR_RANGE = (1.0, 3.9)


def observed_tfr(path: Path = BACKTEST) -> list[tuple[int, float]]:
    """Observed HFD period TFR by year, taken from the no-change backtest records."""
    series: dict[int, float] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["method"] != "naive":
                continue
            year, value = int(row["target"]), float(row["observed"])
            if series.setdefault(year, value) != value:
                raise ValueError(f"conflicting observed TFR for {year}")
    years = sorted(series)
    if not years or years != list(range(years[0], years[-1] + 1)):
        raise ValueError("observed TFR series is empty or has gaps")
    return [(year, series[year]) for year in years]


def forecast_tfr(path: Path = FORECAST) -> list[tuple[int, float]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return sorted((int(row["year"]), float(row["forecast"])) for row in csv.DictReader(handle))


def _x(year: float) -> float:
    span = PLOT["x1"] - PLOT["x0"]
    return PLOT["x0"] + (year - YEARS[0]) / (YEARS[1] - YEARS[0]) * span


def _y(tfr: float) -> float:
    span = PLOT["y1"] - PLOT["y0"]
    return PLOT["y1"] - (tfr - TFR_RANGE[0]) / (TFR_RANGE[1] - TFR_RANGE[0]) * span


def _path(points: list[tuple[int, float]]) -> str:
    return " ".join(f"{'M' if i == 0 else 'L'}{_x(year):.1f},{_y(value):.1f}"
                    for i, (year, value) in enumerate(points))


def render(theme: str, observed: list[tuple[int, float]], forecast: list[tuple[int, float]]) -> str:
    c = THEMES[theme]
    last_year, last_value = observed[-1]
    peak_year, peak_value = max(observed, key=lambda item: item[1])
    end_year, end_value = forecast[-1]
    if not all(TFR_RANGE[0] <= v <= TFR_RANGE[1] for _, v in observed + forecast):
        raise ValueError("a TFR value falls outside the plotted range")
    projected = [(last_year, last_value)] + forecast
    ticks = "".join(
        f'<line x1="{PLOT["x0"]}" x2="{PLOT["x1"]}" y1="{_y(v):.1f}" y2="{_y(v):.1f}" stroke="{c["rule"]}" stroke-width="1"/>'
        f'<text x="{PLOT["x0"] - 10}" y="{_y(v) + 5:.1f}" text-anchor="end" class="axis">{v:.1f}</text>'
        for v in (1.0, 1.5, 2.0, 2.5, 3.0, 3.5))
    years = "".join(
        f'<text x="{_x(y):.1f}" y="{PLOT["y1"] + 24}" text-anchor="middle" class="axis">{y}</text>'
        for y in (1960, 1980, 2000, 2020, 2040))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="t d">
<title id="t">The Intention Gap: will Generation Z have the families they say they want?</title>
<desc id="d">Line chart of the observed U.S. period total fertility rate from {observed[0][0]} to {last_year} (Human Fertility Database): a peak of {peak_value:.2f} births per woman in {peak_year}, falling to {last_value:.2f} in {last_year}. A dashed line holds the {last_year} level flat to {end_year} ({end_value:.3f}), the project's no-change forecast; its historical-error interval failed calibration and is not shown.</desc>
<style>
text {{ font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; fill: {c["ink"]}; }}
.eyebrow {{ font-size: 17px; letter-spacing: 3px; fill: {c["muted"]}; }}
.title {{ font-family: Georgia, "Times New Roman", serif; font-size: 38px; }}
.lede {{ font-size: 19px; fill: {c["muted"]}; }}
.axis {{ font-size: 16px; fill: {c["muted"]}; }}
.note {{ font-size: 17px; fill: {c["ink"]}; }}
.source {{ font-size: 16px; fill: {c["muted"]}; }}
</style>
<rect width="{WIDTH}" height="{HEIGHT}" fill="{c["bg"]}"/>
<text x="48" y="78" class="eyebrow">THE INTENTION GAP</text>
<text x="48" y="132" class="title">Will Generation Z have the</text>
<text x="48" y="178" class="title">families they say they want?</text>
<text x="48" y="222" class="lede">Independent demographic research: stated intentions,</text>
<text x="48" y="248" class="lede">observed births, housing costs and forecasts to 2040.</text>
<text x="48" y="282" class="source">Four linked studies · public U.S. data · results independently recomputed</text>
{ticks}{years}
<path d="{_path(observed)}" fill="none" stroke="{c["line"]}" stroke-width="2.5" stroke-linejoin="round"/>
<path d="{_path(projected)}" fill="none" stroke="{c["forecast"]}" stroke-width="2.5" stroke-dasharray="7 6"/>
<circle cx="{_x(peak_year):.1f}" cy="{_y(peak_value):.1f}" r="3.5" fill="{c["line"]}"/>
<text x="{_x(peak_year) + 9:.1f}" y="{_y(peak_value) - 6:.1f}" class="note">{peak_value:.2f} in {peak_year}</text>
<circle cx="{_x(last_year):.1f}" cy="{_y(last_value):.1f}" r="3.5" fill="{c["line"]}"/>
<text x="{PLOT["x1"]:.1f}" y="{_y(end_value) + 24:.1f}" text-anchor="end" class="note">{last_value:.2f} in {last_year}; {end_value:.3f} in {end_year} if the {last_year} level persists</text>
<text x="{PLOT["x0"]:.1f}" y="{PLOT["y0"] - 26:.1f}" class="note">U.S. period total fertility rate (births per woman)</text>
<text x="{PLOT["x0"]:.1f}" y="{HEIGHT - 14}" class="source">Source: Human Fertility Database (CC BY 4.0). Dashed: no-change forecast.</text>
</svg>
"""


def outputs() -> dict[Path, str]:
    observed, forecast = observed_tfr(), forecast_tfr()
    return {OUT_DIR / f"header-{theme}.svg": render(theme, observed, forecast) for theme in THEMES}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the committed images are out of date")
    args = parser.parse_args(argv)
    stale = []
    for path, text in outputs().items():
        data = text.encode("utf-8")
        if args.check:
            if not path.exists() or path.read_bytes() != data:
                stale.append(path.relative_to(ROOT).as_posix())
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            print(f"wrote {path.relative_to(ROOT).as_posix()}")
    if stale:
        print("out of date: " + ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
