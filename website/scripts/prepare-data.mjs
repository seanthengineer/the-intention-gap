import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { csvParse } from "d3-dsv";
import { geoAlbersUsa, geoBounds, geoContains, geoPath } from "d3-geo";
import { feature, mesh } from "topojson-client";
import { presimplify, quantile, simplify } from "topojson-simplify";

const SITE = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const REPO = resolve(process.env.INTENTION_GAP_REPO ?? join(SITE, ".."));
const OUT = join(SITE, "src", "data");
mkdirSync(OUT, { recursive: true });
mkdirSync(join(SITE, "public", "figures"), { recursive: true });

const manifest = new Map();
for (const name of readdirSync(join(REPO, "docs")).filter((n) => n.endsWith("_freeze.sha256"))) {
  for (const line of readFileSync(join(REPO, "docs", name), "utf8").split(/\r?\n/)) {
    const m = line.match(/^([0-9a-f]{64})\s+\*?(.+)$/);
    if (m) manifest.set(m[2].trim(), { sha256: m[1], manifest: name });
  }
}

const provenance = new Map();
function read(rel, binary = false) {
  const buf = readFileSync(join(REPO, rel));
  const sha256 = createHash("sha256").update(buf).digest("hex");
  const frozen = manifest.get(rel);
  if (frozen && frozen.sha256 !== sha256) throw new Error(`Frozen file changed: ${rel}`);
  provenance.set(rel, { path: rel, sha256, bytes: buf.length, frozenIn: frozen ? frozen.manifest : null });
  return binary ? buf : buf.toString("utf8");
}
const csv = (rel) => csvParse(read(rel));
const json = (rel) => JSON.parse(read(rel));
const num = (v) => (v === "" || v === undefined || v === null ? null : Number(v));
const round = (v, d = 6) => (v === null || Number.isNaN(v) ? null : Math.round(v * 10 ** d) / 10 ** d);

const P = "data/public";

const dash = json(`${P}/dashboard_summary.json`);
const nlsySens = dash.sensitivity.find((s) => s.scenario === "Primary definition");
const nlsy = {
  about: dash.about,
  sample: {
    eligible: dash.sample.eligible_women,
    labelled: dash.sample.labelled,
    births: dash.sample.births,
    unknown: dash.sample.unknown,
    age: dash.sample.age_at_baseline,
  },
  distribution: dash.distribution,
  calibration: dash.calibration,
  recalibration: dash.recalibration_curve.map((r) => [r.stated_pct, round(r.recalibrated, 4)]),
  forecast: { auc: dash.stated_forecast.auc, aucCi: dash.stated_forecast.auc_ci, brier: dash.stated_forecast.brier },
  slope: { value: nlsySens.slope, ci: nlsySens.slope_ci },
  heldOut: { n: dash.held_out.n, births: dash.held_out.births, models: dash.held_out.models },
};

const est = csv(`${P}/nsfg_m09/estimates.csv`).filter((r) => r.cohort === "conservative");
const estimate = (pop, measure) => {
  const r = est.find((x) => x.population === pop && x.measure === measure);
  return { n: num(r.n), est: num(r.estimate), lo: num(r.ci_low), hi: num(r.ci_high), rel: r.reliability };
};
const pops = ["all", "female", "male"];
const measures = ["wants", "intends", "divergence_among_wanters", "explicit_among_wanters", "sterility_among_wanters"];
const nsfgHeadline = Object.fromEntries(pops.map((p) => [p, Object.fromEntries(measures.map((m) => [m, estimate(p, m)]))]));
const dist = csv(`${P}/nsfg_m09/response_distributions.csv`).filter(
  (r) => r.cohort === "conservative" && r.item === "intention category among wanters",
);
const decomposition = Object.fromEntries(
  pops.map((p) => [
    p,
    dist
      .filter((r) => r.population === p)
      .map((r) => ({ category: r.response, n: num(r.n), est: num(r.estimate), lo: num(r.ci_low), hi: num(r.ci_high), rel: r.reliability })),
  ]),
);
const subgroups = csv(`${P}/nsfg_m09/subgroups.csv`)
  .filter((r) => r.cohort === "conservative")
  .map((r) => {
    const suppressed = r.reliability.startsWith("suppress");
    return {
      pop: r.population,
      g: r.grouping,
      level: r.level,
      m: r.measure,
      n: num(r.n),
      est: suppressed ? null : round(num(r.estimate)),
      lo: suppressed ? null : round(num(r.ci_low)),
      hi: suppressed ? null : round(num(r.ci_high)),
      rel: r.reliability,
    };
  });
const holdout = csv(`${P}/nsfg_m09/model_holdout.csv`);
const boot = Object.fromEntries(csv(`${P}/nsfg_m09/model_bootstrap.csv`).map((r) => [r.quantity, [num(r.ci_low), num(r.ci_high)]]));
const stability = csv(`${P}/nsfg_m09/model_stability.csv`);
const stab = (model) => {
  const v = stability.filter((r) => r.model === model).map((r) => num(r.roc_auc));
  return { mean: round(v.reduce((a, b) => a + b, 0) / v.length, 4), min: Math.min(...v), max: Math.max(...v), seeds: v.length };
};
const nsfg = {
  headline: nsfgHeadline,
  decomposition,
  subgroups,
  model: {
    holdout: holdout.map((r) => ({
      model: r.model,
      auc: num(r.roc_auc),
      aucCi: boot[`${r.model}_roc_auc`],
      prAuc: num(r.pr_auc),
      prevalence: num(r.prevalence),
      brierSkill: num(r.brier_skill),
      positives: num(r.tp) + num(r.fn),
      n: num(r.tp) + num(r.fn) + num(r.fp) + num(r.tn),
    })),
    logisticMinusDummy: boot["logistic-dummy_roc_auc"],
    stability: { logistic: stab("logistic"), boosting: stab("boosting"), dummy: stab("dummy") },
  },
};

const m10primary = csv(`${P}/m10/m10_primary.csv`);
const m10models = csv(`${P}/m10/m10_models.csv`).map((r) => ({
  age: r.age_group,
  model: r.model,
  est: num(r.estimate_per10),
  lo: num(r.ci_low),
  hi: num(r.ci_high),
  p: num(r.p_value),
  n: num(r.n),
}));
const m10rob = csv(`${P}/m10/m10_robustness.csv`).map((r) => ({
  age: r.age_group,
  analysis: r.analysis,
  variant: r.variant,
  est: num(r.estimate_per10),
  lo: num(r.ci_low),
  hi: num(r.ci_high),
  note: r.note,
}));
const byYear = csv(`${P}/m10/m10_desc_by_year.csv`).map((r) => ({
  year: num(r.year),
  v: r.variable,
  median: num(r.median),
  p25: num(r.p25),
  p75: num(r.p75),
  min: num(r.min),
  max: num(r.max),
  national: num(r.national_rate),
}));
const loso = csv(`${P}/m10/m10_loso.csv`).map((r) => ({
  age: r.age_group,
  state: r.dropped_state,
  fips: r.state_fips,
  est: num(r.estimate_per10),
  p: num(r.p_value),
  change: num(r.change_from_full),
}));
const variance = csv(`${P}/m10/m10_desc_variance.csv`);
const m10 = {
  primary: m10primary.map((r) => ({
    test: r.test,
    role: r.role,
    age: r.age_group,
    est: num(r.estimate_per10),
    lo: num(r.ci_low),
    hi: num(r.ci_high),
    p: num(r.p_value),
    wildP: num(r.wild_bootstrap_p),
    n: num(r.n),
    clusters: num(r.clusters),
  })),
  models: m10models,
  robustness: m10rob,
  byYear: byYear.filter((r) => ["rate_20-24", "rate_25-29", "burden30_pct", "young15_24_burden30_pct"].includes(r.v)),
  loso,
  withinShare: Object.fromEntries(variance.map((r) => [r.variable, num(r.within_share_of_variance)])),
};

const F = `${P}/m11/forecast`;
const records = csv(`${F}/m11_fc_tfr_backtest_records.csv`).filter((r) => r.method === "naive" && r.h === "1");
const observed = records.map((r) => [num(r.target), num(r.observed)]).sort((a, b) => a[0] - b[0]);
const fcRows = csv(`${F}/m11_fc_tfr_forecast.csv`);
const fc = fcRows.map((r) => ({
  year: num(r.year),
  h: num(r.h),
  f: num(r.forecast),
  l80: round(num(r.lower80), 5),
  u80: round(num(r.upper80), 5),
  l95: round(num(r.lower95), 5),
  u95: round(num(r.upper95), 5),
  s77l80: round(num(r.sens1977_lower80), 5),
  s77u80: round(num(r.sens1977_upper80), 5),
}));
const methodLines = {};
for (const r of csv(`${F}/m11_fc_tfr_forecast_all_methods.csv`)) (methodLines[r.method] ??= []).push([num(r.year), round(num(r.forecast), 5)]);
const selection = csv(`${F}/m11_fc_tfr_selection.csv`).map((r) => ({
  method: r.method,
  R: round(num(r.R), 4),
  h5: round(num(r.ratio_h5), 4),
  h10: round(num(r.ratio_h10), 4),
  h15: round(num(r.ratio_h15), 4),
  qualifies: r.qualifies === "True",
  selected: r.selected === "True",
}));
const originSens = csv(`${F}/m11_fc_rob_origin_sensitivity.csv`).map((r) => [num(r.origin), num(r.tfr_2040)]);
const methodWindow = csv(`${F}/m11_fc_rob_2040_by_method_and_window.csv`).map((r) => ({
  training: r.training,
  method: r.method,
  tfr2040: round(num(r.tfr_2040), 4),
}));
const coverage = csv(`${F}/m11_fc_interval_coverage_pooled.csv`).map((r) => ({
  interval: r.interval,
  method: r.method,
  level: num(r.level),
  coverage: round(num(r.coverage_h5_10_15), 4),
  lo: round(num(r.bootstrap_p05), 4),
  hi: round(num(r.bootstrap_p95), 4),
}));
const calibByH = csv(`${F}/m11_fc_interval_calibration.csv`)
  .filter((r) => r.method === "naive")
  .map((r) => ({ interval: r.interval, h: num(r.h), c80: round(num(r.coverage80), 4), c95: round(num(r.coverage95), 4), origins: num(r.origins) }))
  .concat(
    csv(`${F}/m11_fc_rob_interval_calibration_1977.csv`)
      .filter((r) => r.method === "naive")
      .map((r) => ({ interval: "since_1977", h: num(r.h), c80: round(num(r.coverage80), 4), c95: round(num(r.coverage95), 4), origins: num(r.origins) })),
  );
const traj = csv(`${F}/m11_fc_genz_trajectories.csv`).map((r) => ({
  c: num(r.cohort),
  y: num(r.year),
  age: num(r.ardy),
  cum: round(num(r.cumulative), 5),
  seg: r.segment,
  l80: round(num(r.lower80), 5),
  u80: round(num(r.upper80), 5),
}));
const endpoints = csv(`${F}/m11_fc_genz_endpoints_2040.csv`).map((r) => ({
  c: num(r.cohort),
  age2024: num(r.age_reached_2024),
  obs2024: num(r.observed_2024),
  age2040: num(r.age_reached_2040),
  p2040: round(num(r.projected_2040), 4),
  l80: round(num(r.lower80), 4),
  u80: round(num(r.upper80), 4),
  l95: round(num(r.lower95), 4),
  u95: round(num(r.upper95), 4),
  completion: r.completion_label,
}));
const observability = csv(`${P}/m11/m11_cohort_observability.csv`).map((r) => ({
  c: num(r.cohort),
  age2024: num(r.age_reached_in_2024),
  complete: r.hfd_complete_ages,
  age2040: num(r.age_reached_in_2040),
  forecastAges: r.ages_to_forecast_2026_2040,
  after2040: r.ages_unobserved_after_2040,
}));
const cohortCoverage = csv(`${F}/m11_fc_cohort_interval_coverage.csv`).map((r) => ({ h: num(r.h), c80: round(num(r.covered80), 4), c95: round(num(r.covered95), 4) }));
const m11 = {
  cohortCoverage,
  observed,
  forecast: fc,
  intervalLabel: fcRows[0].interval_label,
  methodLines,
  selection,
  originSens,
  methodWindow,
  coverage,
  calibByH,
  trajectories: traj,
  endpoints,
  observability,
};

const evidence = csv(`${P}/final/final_evidence_table.csv`).map((r) => ({
  id: r.id,
  chapter: r.chapter,
  quantity: r.quantity,
  type: r.estimand_type,
  population: r.population,
  period: r.period,
  est: num(r.estimate),
  lo: num(r.lower),
  hi: num(r.upper),
  unc: r.uncertainty_type,
  source: r.source_file,
  scale: num(r.source_scale),
}));
const populationMap = csv(`${P}/final/final_population_map.csv`);

const figureFiles = readdirSync(join(REPO, "assets", "figures")).filter((n) => n.endsWith(".png")).sort();
for (const name of figureFiles) writeFileSync(join(SITE, "public", "figures", name), read(`assets/figures/${name}`, true));

const atlasText = read("docs/visual_atlas.md");
const figures = [];
let chapter = null;
for (const block of atlasText.split(/\n(?=#{2,3} )/)) {
  const heading = block.match(/^(#{2,3}) (.+)/);
  if (!heading) continue;
  if (heading[1] === "##") {
    chapter = heading[2].trim();
    continue;
  }
  const img = block.match(/!\[([^\]]*)\]\(\.\.\/assets\/figures\/([^)]+\.png)\)/);
  if (!img) continue;
  const fields = {};
  for (const m of block.matchAll(/^- \*\*([^:*]+):\*\* (.+)$/gm)) fields[m[1].trim().toLowerCase()] = m[2].trim();
  figures.push({ file: img[2], title: heading[2].trim(), chapter, alt: img[1], fields });
}
const missing = figureFiles.filter((f) => !figures.some((x) => x.file === f));
if (missing.length) throw new Error(`Figures without atlas captions: ${missing.join(", ")}`);

const rawTopo = presimplify(JSON.parse(readFileSync(join(SITE, "node_modules", "us-atlas", "states-10m.json"), "utf8")));
const topo = simplify(rawTopo, quantile(rawTopo, 0.2));
const states = feature(topo, topo.objects.states).features;
const W = 975;
const H = 610;
const projection = geoAlbersUsa().scale(1300).translate([487.5, 305]);
const path = geoPath(projection).digits(1);
const bounds = states.map((s) => geoBounds(s));
const step = 9.5;
const dots = [];
for (let y = step / 2; y < H; y += step) {
  for (let x = step / 2; x < W; x += step) {
    const ll = projection.invert([x, y]);
    if (!ll) continue;
    for (let i = 0; i < states.length; i++) {
      const [[w, s], [e, n]] = bounds[i];
      const outLon = w <= e ? ll[0] < w || ll[0] > e : ll[0] < w && ll[0] > e;
      if (outLon || ll[1] < s || ll[1] > n) continue;
      if (geoContains(states[i], ll)) {
        dots.push([round(x, 1), round(y, 1), states[i].id]);
        break;
      }
    }
  }
}
for (const st of states) {
  if (dots.some((d) => d[2] === st.id)) continue;
  const c = path.centroid(st);
  if (Number.isFinite(c[0])) dots.push([round(c[0], 1), round(c[1], 1), st.id]);
}
const geo = {
  width: W,
  height: H,
  step,
  dots,
  states: states.map((s) => ({ id: s.id, name: s.properties.name, d: path(s) })),
  borders: path(mesh(topo, topo.objects.states, (a, b) => a !== b)),
  nation: path(mesh(topo, topo.objects.states, (a, b) => a === b)),
};

writeFileSync(join(OUT, "site-data.json"), JSON.stringify({ nlsy, nsfg, m10, m11, final: { populationMap, evidence }, figures }));
writeFileSync(join(OUT, "geo.json"), JSON.stringify(geo));
let commit = null;
try {
  commit = execFileSync("git", ["-C", REPO, "rev-parse", "HEAD"], { encoding: "utf8" }).trim();
} catch {}
const files = [...provenance.values()].sort((a, b) => a.path.localeCompare(b.path));
writeFileSync(
  join(OUT, "provenance.json"),
  JSON.stringify({ repository: "https://github.com/seanthengineer/the-intention-gap", commit, files }, null, 1),
);
const frozen = files.filter((f) => f.frozenIn).length;
console.log(`site data: ${files.length} source files read (${frozen} verified against freeze manifests), ${figures.length} figures, ${dots.length} map dots`);
