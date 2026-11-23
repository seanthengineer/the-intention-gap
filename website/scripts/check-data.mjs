import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..");
const d = JSON.parse(readFileSync(join(SITE, "src", "data", "site-data.json"), "utf8"));
const failures = [];
const expect = (label, actual, expected, digits) => {
  const shown = Number(actual).toFixed(digits);
  if (shown !== expected) failures.push(`${label}: data gives ${shown}, published value is ${expected}`);
};

const cal = Object.fromEntries(d.nlsy.calibration.map((c) => [c.range_pct, c]));
expect("NLSY97 observed at 0%", cal["0"].observed_pct, "18.4", 1);
expect("NLSY97 observed at 100%", cal["100"].observed_pct, "73.0", 1);
expect("NLSY97 AUC", d.nlsy.forecast.auc, "0.726", 3);
expect("NLSY97 calibration slope", d.nlsy.slope.value, "0.476", 3);
const h = d.nsfg.headline.all;
expect("NSFG wants", h.wants.est * 100, "69.9", 1);
expect("NSFG intends", h.intends.est * 100, "62.8", 1);
expect("NSFG divergence among wanters", h.divergence_among_wanters.est * 100, "11.2", 1);
expect("NSFG sterility share of divergence", (h.sterility_among_wanters.est / h.divergence_among_wanters.est) * 100, "41.6", 1);
const logit = d.nsfg.model.holdout.find((m) => m.model === "logistic");
expect("NSFG logistic holdout AUC", logit.auc, "0.51", 2);
const prim = d.m10.primary.find((p) => p.role === "primary");
expect("M10 primary estimate", prim.est, "-2.77", 2);
expect("M10 primary CI low", prim.lo, "-5.81", 2);
expect("M10 primary CI high", prim.hi, "0.26", 2);
const f2040 = d.m11.forecast.find((r) => r.year === 2040);
expect("M11 TFR 2040", f2040.f, "1.593", 3);
expect("M11 80% low 2040", f2040.l80, "1.05", 2);
expect("M11 80% high 2040", f2040.u80, "2.42", 2);
const obs2024 = d.m11.observed.find(([y]) => y === 2024);
expect("M11 observed 2024", obs2024[1], "1.593", 3);
const peak = d.m11.observed.reduce((a, b) => (b[1] > a[1] ? b : a));
if (peak[0] !== 1957) failures.push(`TFR peak year is ${peak[0]}, expected 1957`);
expect("M11 peak TFR", peak[1], "3.74", 2);
const ep = Object.fromEntries(d.m11.endpoints.map((e) => [e.c, e]));
expect("Cohort 1995 by 2040", ep[1995].p2040, "1.75", 2);
expect("Cohort 2012 by 2040", ep[2012].p2040, "0.62", 2);
const ari = d.m11.selection.find((s) => s.method === "ari");
expect("ARIMA relative MAE", ari.R, "0.942", 3);
if (d.m11.selection.some((s) => s.qualifies)) failures.push("A forecasting method is marked as qualifying; the published result says none did");
if (d.nsfg.subgroups.some((s) => s.rel.startsWith("suppress") && s.est !== null)) failures.push("A suppressed NSFG estimate carries a value");
if (d.figures.length !== 21) failures.push(`Expected 21 research figures, found ${d.figures.length}`);

const geo = JSON.parse(readFileSync(join(SITE, "src", "data", "geo.json"), "utf8"));
const atlasStates = new Map(geo.states.filter((state) => state.d).map((state) => [state.id, state.name]));
const atlasKeys = new Set();
const atlasYears = [2014, 2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024];
if (atlasStates.size !== 51 || d.m10Atlas.years.join(",") !== atlasYears.join(",")) {
  failures.push("M10 atlas geometry or year coverage differs from the study");
}
for (const row of d.m10Atlas.rows) {
  const key = `${row.fips}/${row.year}`;
  if (atlasKeys.has(key) || !row.name || atlasStates.get(row.fips) !== row.name || !atlasYears.includes(row.year)) {
    failures.push(`M10 atlas duplicate or unjoinable row: ${key}`);
  }
  atlasKeys.add(key);
  if (!Number.isFinite(row.burden30) || !Number.isFinite(row.burden50)
      || row.burden50 < 0 || row.burden50 > row.burden30 || row.burden30 > 100) {
    failures.push(`M10 atlas invalid rent burden: ${key}`);
  }
  if ([row.birth20, row.birth25].some((value) => !Number.isFinite(value) || value < 0)) {
    failures.push(`M10 atlas missing or invalid rate in the verified release: ${key}`);
  }
}
if (atlasKeys.size !== 510) failures.push(`Expected 510 M10 atlas state-years, found ${atlasKeys.size}`);

if (failures.length) {
  console.error("Data check FAILED:\n  " + failures.join("\n  "));
  process.exit(1);
}
console.log("Data check passed: frozen headline values, NSFG suppression, research archive count and M10 atlas FIPS joins.");
