import { line, scaleLinear, scaleThreshold } from "d3";
import data from "../../data/site-data.json";
import geo from "../../data/geo.json";
import { fmt } from "../lib";

export type Metric = "burden30" | "burden50" | "birth20" | "birth25";

interface Observation {
  fips: string;
  year: number;
  burden30: number | null;
  burden50?: number | null;
  birth20: number | null;
  birth25: number | null;
}

interface AtlasData {
  years: number[];
  rows: Observation[];
}

export const atlas = (data as typeof data & { m10Atlas?: AtlasData }).m10Atlas;
export const states = geo.states.filter((state) => state.d).sort((a, b) => a.name.localeCompare(b.name));
export const dcPosition = geo.dots.find(([,, fips]) => fips === "11");
export const geographicViewBox = "0 0 " + geo.width + " " + geo.height;
export const fallbackFips = "06";

const values = new Map(atlas?.rows.map((row) => [row.fips + ":" + row.year, row]));
export const metrics: Record<Metric, {
  title: string;
  unit: string;
  thresholds: number[];
  extent: [number, number];
  ticks: number[];
}> = {
  burden30: {
    title: "Rent burden (30% or more)",
    unit: "% of renter households",
    thresholds: [40, 45, 50, 55],
    extent: [35, 65],
    ticks: [35, 45, 55, 65],
  },
  burden50: {
    title: "Severe rent burden (50% or more)",
    unit: "% of renter households",
    thresholds: [18, 21, 24, 27],
    extent: [15, 35],
    ticks: [15, 20, 25, 30, 35],
  },
  birth20: {
    title: "Birth rate, ages 20–24",
    unit: "births per 1,000 women aged 20–24",
    thresholds: [40, 55, 70, 85],
    extent: [20, 120],
    ticks: [20, 45, 70, 95, 120],
  },
  birth25: {
    title: "Birth rate, ages 25–29",
    unit: "births per 1,000 women aged 25–29",
    thresholds: [60, 80, 100, 120],
    extent: [25, 175],
    ticks: [25, 75, 125, 175],
  },
};

export const availableMetrics = (Object.keys(metrics) as Metric[]).filter(
  (metric) => atlas?.rows.some((row) => row[metric] != null),
);

export const colors = ["#f0e1d0", "#dec0a5", "#c88f72", "#a55340", "#7d2926"];
const scales = Object.fromEntries(
  availableMetrics.map((key) => [key, scaleThreshold<number, string>(metrics[key].thresholds, colors)]),
) as Partial<Record<Metric, (value: number) => string>>;

export function observation(fips: string, year: number, metric: Metric) {
  return values.get(fips + ":" + year)?.[metric] ?? null;
}

export function display(value: number | null, metric: Metric) {
  if (value === null) return "Not available";
  const rounded = Number(value.toFixed(1));
  const crossesThreshold = metrics[metric].thresholds.some((threshold) => value < threshold && rounded === threshold);
  // Keep the displayed value on the correct side of the map's color threshold.
  return fmt(value, crossesThreshold ? 3 : 1) + (metric.startsWith("burden") ? "%" : "");
}

export function atlasColor(value: number | null, metric: Metric) {
  return value === null ? "url(#atlas-missing)" : scales[metric]?.(value) ?? "url(#atlas-missing)";
}

export function legend(metric: Metric) {
  const edges = metrics[metric].thresholds;
  return colors.map((color, i) => ({
    color,
    label: i === 0 ? "<" + edges[0] : i === edges.length ? "≥" + edges[i - 1] : edges[i - 1] + "–<" + edges[i],
  }));
}

export const trendViewBox = "0 0 344 172";
export const trendPlot = { left: 35, right: 332, top: 12, bottom: 137 };

export function trend(fips: string, metric: Metric, year: number) {
  const start = atlas?.years[0] ?? year;
  const end = atlas?.years.at(-1) ?? year;
  const years = Array.from({ length: end - start + 1 }, (_, i) => start + i);
  const series = years.map((y) => ({ year: y, value: observation(fips, y, metric) }));
  const x = scaleLinear([start, end], [trendPlot.left, trendPlot.right]);
  const y = scaleLinear(metrics[metric].extent, [trendPlot.bottom, trendPlot.top]);
  const observed = observation(fips, year, metric);
  return {
    path: line<(typeof series)[number]>().defined((d) => d.value !== null).x((d) => x(d.year)).y((d) => y(d.value!))(series),
    ticks: metrics[metric].ticks.map((v) => ({ value: v, position: y(v) })),
    yearTicks: [start, 2019, 2021, end].map((v) => ({ value: v, position: x(v) })),
    series,
    gap: x(2020),
    selected: { x: x(year), y: observed === null ? null : y(observed) },
  };
}
