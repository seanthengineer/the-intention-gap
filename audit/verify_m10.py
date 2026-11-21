"""Verification of the M10 housing-fertility analysis, with each check labelled by kind.

INDEPENDENT recomputation shares no code with analysis/m10_*.py, acs_housing,
m10_covariates or cdc_natality. It reads the raw API responses and CDC export
text files directly, rebuilds the housing measures, rates, analytical series and
lags, and re-estimates the main fixed-effects models with a separately
constructed within transformation (alternating projections, no dummy
variables) and its own CR1 cluster-robust variance.
RERUN checks call the pipeline's own functions again from saved inputs: they
show determinism (wild bootstrap p-values), not correctness.
RECONCILIATION checks compare stored values, hashes and reported numbers:
provenance hashes, the protocol lock, absence of the API key, and headline
numbers in docs/m10_housing_fertility.md.

Not covered: SIMEX, added-noise stability, diagnostic statistics other than
the variance decomposition, the figures' rendering (figures are drawn from the
stored tables checked here), and the B25072/B23025/B19013 variable labels.

    python audit/verify_m10.py
"""

import csv
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed" / "m10"
PUBLIC = ROOT / "data" / "public" / "m10"
CHAPTER = ROOT / "docs" / "m10_housing_fertility.md"
STATES = ["01", "02", "04", "05", "06", "08", "09", "10", "11", "12", "13", "15", "16", "17",
          "18", "19", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31",
          "32", "33", "34", "35", "36", "37", "38", "39", "40", "41", "42", "44", "45", "46",
          "47", "48", "49", "50", "51", "53", "54", "55", "56"]
YEARS = [2014, 2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024]
INDEPENDENT, RERUN, RECONCILIATION = "independent", "rerun", "reconciliation"


class Checks:
    def __init__(self):
        self.rows = []

    def add(self, kind, label, ok, detail):
        self.rows.append((kind, "PASS" if ok else "FAIL", label, detail))

    def close(self, kind, label, observed, expected, tol=1e-6):
        ok = bool(np.isclose(observed, expected, rtol=tol, atol=tol))
        self.add(kind, label, ok, f"recomputed {observed:.6f} vs stored {expected:.6f}")


# --------------------------------------------------------------- raw sources

def acs_value_table(directory: Path, table: str) -> dict:
    out = {}
    for year in YEARS:
        rows = json.loads((directory / f"acs1_{year}_{table}_data.json").read_text())
        header = rows[0]
        for row in rows[1:]:
            record = dict(zip(header, row))
            if record["state"] in STATES:
                out[(record["state"], year)] = record
    return out


def housing_from_raw() -> pd.DataFrame:
    general = acs_value_table(RAW / "acs_b25070", "B25070")
    young = acs_value_table(RAW / "acs_m10_covariates", "B25072")
    labour = acs_value_table(RAW / "acs_m10_covariates", "B23025")
    rows = []
    for key, r in general.items():
        g = {i: float(r[f"B25070_{i:03d}E"]) for i in range(1, 12)}
        y = {i: float(young[key][f"B25072_{i:03d}E"]) for i in range(1, 30)}
        lab = labour[key]
        rows.append({
            "state_fips": key[0], "year": key[1],
            "burden30": 100 * (g[7] + g[8] + g[9] + g[10]) / (g[1] - g[11]),
            "young15_24": 100 * (y[6] + y[7]) / (y[2] - y[8]),
            "young25_34": 100 * (y[13] + y[14]) / (y[9] - y[15]),
            "unemployment": 100 * float(lab["B23025_005E"]) / float(lab["B23025_003E"])})
    return pd.DataFrame(rows)


def natality_from_raw() -> pd.DataFrame:
    def read(path: Path) -> dict:
        out = {}
        with open(path, newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle, delimiter="\t")
            header = next(reader)
            state_col = 4  # "State Code" or "State of Residence Code"
            for row in reader:
                if not row or row[0] == "---":
                    break
                if row[0] == "":
                    out[(row[state_col], int(row[2]), row[6])] = (row[7], row[8], row[9])
        assert header[4].endswith("Code")
        return out
    original = read(RAW / "cdc_natality" / "cdc_wonder_natality_state_age_2014_2024.xls")
    expanded = read(RAW / "cdc_natality" /
                    "cdc_wonder_natality_expanded_state_age_2016_2024.xls")
    rows = []
    for state in STATES:
        for year in range(2014, 2025):
            for age in ("20-24", "25-29"):
                births, pop, rate = (original if year < 2016 else expanded)[(state, year, age)]
                rows.append({"state_fips": state, "year": year, "age_group": age,
                             "raw_births": int(births), "raw_population": int(pop),
                             "raw_rate": float(rate)})
    return pd.DataFrame(rows)


# --------------------------------------------------------------- estimation

def demean(values: np.ndarray, groups: list[np.ndarray], weights: np.ndarray,
           tol: float = 1e-13) -> np.ndarray:
    """Alternating projections onto the complement of the group-mean spaces."""
    out = values.astype(float).copy()
    for _ in range(10000):
        previous = out.copy()
        for g in groups:
            sums = np.bincount(g, weights=out * weights)
            counts = np.bincount(g, weights=weights)
            out = out - (sums / counts)[g]
        if np.max(np.abs(out - previous)) < tol:
            break
    return out


def within_fit(data: pd.DataFrame, y: str, xs: list[str], fe=("state_fips", "year"),
               weight: str | None = None) -> dict:
    groups = [pd.factorize(data[c])[0] for c in fe]
    w = data[weight].to_numpy(float) / data[weight].mean() if weight else np.ones(len(data))
    Y = demean(data[y].to_numpy(float), groups, w)
    X = np.column_stack([demean(data[c].to_numpy(float), groups, w) for c in xs])
    XtWX = X.T @ (X * w[:, None])
    beta = np.linalg.solve(XtWX, X.T @ (w * Y))
    u = Y - X @ beta
    cluster = pd.factorize(data["state_fips"])[0]
    G = cluster.max() + 1
    n = len(data)
    k = len(xs) + 1 + sum(len(np.unique(g)) - 1 for g in groups)
    meat = np.zeros((len(xs), len(xs)))
    for c in range(G):
        s = (X[cluster == c] * (w * u)[cluster == c][:, None]).sum(axis=0)
        meat += np.outer(s, s)
    inv = np.linalg.inv(XtWX)
    V = G / (G - 1) * (n - 1) / (n - k) * inv @ meat @ inv
    se = np.sqrt(np.diag(V))
    return {"beta": beta, "se": se, "n": n, "G": G, "k": k,
            "p": 2 * stats.t.sf(np.abs(beta / se), G - 1), "u": u, "X": X, "cluster": cluster}


# --------------------------------------------------------------- checks

def main() -> int:
    checks = Checks()
    needed = [RAW / "acs_b25070", RAW / "acs_m10_covariates", RAW / "cdc_natality",
              PROCESSED / "m10_panel_state_year_age.csv", PUBLIC / "m10_models.csv"]
    missing = [str(p) for p in needed if not p.exists()]
    if missing:
        print("SKIP: missing inputs: " + "; ".join(missing))
        return 2

    # provenance and protocol (reconciliation)
    for directory, key in ((RAW / "acs_b25070", None), (RAW / "acs_m10_covariates", "files")):
        prov = json.loads((directory / "provenance.json").read_text())
        entries = prov[key].items() if key else [
            (Path(v[k]["file"]).name, v[k]) for v in prov["years"].values() for k in v]
        bad = [name for name, e in entries
               if hashlib.sha256((directory / name).read_bytes()).hexdigest() != e["sha256"]]
        checks.add(RECONCILIATION, f"{directory.name} files match provenance hashes", not bad,
                   f"{len(list(entries)) if not isinstance(entries, list) else len(entries)} "
                   f"files; mismatches {bad}")
    for directory in (RAW / "cdc_natality", RAW / "nchs_nvsr"):
        prov = json.loads((directory / "provenance.json").read_text())
        files = prov.get("files") or prov.get("documents")
        bad = [n for n, e in files.items()
               if hashlib.sha256((directory / n).read_bytes()).hexdigest() != e["sha256"]]
        checks.add(RECONCILIATION, f"{directory.name} files match provenance hashes", not bad,
                   f"{len(files)} files; mismatches {bad}")
    lock = json.loads((ROOT / "docs" / "m10_protocol_lock.json").read_text())
    digest = hashlib.sha256((ROOT / "docs" / "m10_analysis_protocol.md").read_bytes()).hexdigest()
    checks.add(RECONCILIATION, "protocol matches its lock", digest == lock["sha256"],
               f"{digest[:16]}; amendments {len(lock['amendments'])}")
    key = os.environ.get("CENSUS_API_KEY", "")
    leaked = [str(p) for d in (RAW / "acs_b25070", RAW / "acs_m10_covariates", PROCESSED,
                               PUBLIC) for p in d.rglob("*")
              if key and p.is_file() and key.encode() in p.read_bytes()]
    checks.add(RECONCILIATION, "API key absent from saved files", not leaked,
               "checked" if key else "CENSUS_API_KEY not set; not checked")

    # housing, natality, joins, lags (independent)
    housing = housing_from_raw()
    natality = natality_from_raw()
    panel = pd.read_csv(PROCESSED / "m10_panel_state_year_age.csv",
                        dtype={"state_fips": str, "age_group": str})
    covariates = pd.read_csv(PROCESSED / "acs_m10_covariates.csv", dtype={"state_fips": str})
    merged = panel.merge(housing, on=["state_fips", "year"], how="left").merge(
        natality, on=["state_fips", "year", "age_group"], how="left").merge(
        covariates, on=["state_fips", "year"], how="left")
    checks.add(INDEPENDENT, "panel rows / unique keys / years / states",
               len(panel) == 1020 and not panel.duplicated(["state_fips", "year",
                                                            "age_group"]).any()
               and sorted(panel["year"].unique()) == YEARS
               and sorted(panel["state_fips"].unique()) == STATES,
               f"{len(panel)} rows")
    checks.add(INDEPENDENT, "30%+ burden equals raw B25070 recomputation",
               np.allclose(merged["burden30_pct"], merged["burden30"], rtol=1e-5),
               f"max diff {np.abs(merged['burden30_pct'] - merged['burden30']).max():.2e}")
    for column, mine in (("young15_24_burden30_pct", "young15_24"),
                         ("young25_34_burden30_pct", "young25_34"),
                         ("unemployment_pct", "unemployment")):
        checks.add(INDEPENDENT, f"{column} equals raw recomputation",
                   np.allclose(merged[column], merged[mine], rtol=1e-5),
                   f"max diff {np.abs(merged[column] - merged[mine]).max():.2e}")
    checks.add(INDEPENDENT, "births, denominators and rates equal raw exports",
               (merged["births"] == merged["raw_births"]).all()
               and np.allclose(merged["female_population"], merged["raw_population"])
               and np.allclose(merged["outcome_rate"], merged["raw_rate"]),
               "2014-2015 original export, 2016-2024 expanded export")
    recalculated = 1000 * natality["raw_births"] / natality["raw_population"]
    gap = (recalculated - natality["raw_rate"]).abs()
    checks.add(INDEPENDENT, f"rates recalculate from births / population ({len(natality)} rows)",
               bool(gap.max() <= 0.0005 + 1e-9), f"max diff {gap.max():.5f}")
    lookup = housing.set_index(["state_fips", "year"])["burden30"]
    expected_lag = [lookup.get((s, y - 1), np.nan) for s, y in zip(panel["state_fips"],
                                                                   panel["year"])]
    both_nan = np.isnan(expected_lag) & panel["burden30_pct_lag1"].isna()
    agree = np.isclose(expected_lag, panel["burden30_pct_lag1"], rtol=1e-5) | both_nan
    checks.add(INDEPENDENT, "lags match calendar year t-1 (no 2019->2021 bridge)",
               bool(agree.all()) and panel.loc[panel["year"].eq(2021),
                                               "burden30_pct_lag1"].isna().all(),
               f"{int(panel['burden30_pct_lag1'].notna().sum())} lagged rows")

    # 2024 NCHS benchmark (independent parse of the text extraction)
    text = (RAW / "nchs_nvsr" / "nvsr75-02.txt").read_text(encoding="utf-8", errors="replace")
    block = text[text.index("Table 6. Birth rates"):text.index("Table 7.")]
    names = dict(zip(natality.merge(panel[["state_fips", "state_name"]].drop_duplicates(),
                                    on="state_fips")["state_name"],
                     natality.merge(panel[["state_fips", "state_name"]].drop_duplicates(),
                                    on="state_fips")["state_fips"]))
    published = {}
    for line in block.splitlines():
        head = line.split(" .")[0].strip().rstrip(".").strip()
        if head in names:
            numbers = [t for t in line.replace(". ", " ").split() if t.replace(".", "")
                       .replace(",", "").replace("*", "").isdigit() or t == "*"]
            # columns from the right: 45-49, 40-44, 35-39, 30-34, 25-29, 20-24
            published[names[head]] = (float(numbers[-6]), float(numbers[-5])) \
                if len(numbers) >= 12 else None
    mine = natality[natality["year"].eq(2024)].set_index(["state_fips", "age_group"])[
        "raw_rate"]
    diffs = [abs(mine[(s, a)] - published[s][i]) for s in STATES if published.get(s)
             for i, a in enumerate(("20-24", "25-29"))]
    checks.add(INDEPENDENT, "2024 rates within NVSR 75-2 Table 6 published precision",
               len(diffs) == 102 and max(diffs) <= 0.05 + 1e-9,
               f"{len(diffs)} comparisons, max |diff| {max(diffs):.3f}")

    # descriptive (independent)
    variance = pd.read_csv(PUBLIC / "m10_desc_variance.csv").set_index("variable")
    state_year = merged[merged["age_group"].eq("20-24")]
    between = state_year.groupby("state_fips")["burden30"].mean().std()
    checks.close(INDEPENDENT, "between-state SD of 30%+ burden", between,
                 variance.loc["burden30_pct", "between_state_sd"], 1e-4)
    pre_post = pd.read_csv(PUBLIC / "m10_desc_pre_post.csv")
    for (age, period), part in merged.assign(
            period=np.where(merged["year"] < 2020, "2014-2019", "2021-2024")).groupby(
            ["age_group", "period"]):
        stored = pre_post[pre_post["age_group"].eq(age) & pre_post["period"].eq(period)]
        checks.close(INDEPENDENT, f"mean state rate {age} {period}", part["raw_rate"].mean(),
                     float(stored["mean_state_rate"].iloc[0]), 1e-5)

    # regressions (independent within transformation)
    models = pd.read_csv(PUBLIC / "m10_models.csv")
    data = merged.assign(rate_=merged["raw_rate"])
    fits = {}
    for age in ("20-24", "25-29"):
        d = data[data["age_group"].eq(age)].reset_index(drop=True)
        for label, xs, fe, sample in (
                ("C state + year FE (primary)", ["burden30"], ("state_fips", "year"), d),
                ("B state FE", ["burden30"], ("state_fips",), d),
                ("D + unemployment", ["burden30", "unemployment"], ("state_fips", "year"), d),
                ("E one-year lag", ["burden30_pct_lag1"], ("state_fips", "year"),
                 d.dropna(subset=["burden30_pct_lag1"]).reset_index(drop=True))):
            result = within_fit(sample, "rate_", xs, fe)
            stored = models[models["age_group"].eq(age) & models["model"].eq(label)].iloc[0]
            checks.close(INDEPENDENT, f"{age} {label}: 10*beta", 10 * result["beta"][0],
                         stored["estimate_per10"])
            checks.close(INDEPENDENT, f"{age} {label}: clustered SE", 10 * result["se"][0],
                         stored["se"])
            checks.add(INDEPENDENT, f"{age} {label}: clusters / n",
                       result["G"] == stored["clusters"] == 51 and result["n"] == stored["n"],
                       f"G {result['G']}, n {result['n']}")
            if label.startswith("C "):
                fits[age] = result
    # stacked contrast from the two within fits with a combined cluster score
    s1, s2 = fits["20-24"], fits["25-29"]
    psi = np.zeros(51)
    for result, sign in ((s1, 1.0), (s2, -1.0)):
        x, u = result["X"][:, 0], result["u"]
        np.add.at(psi, result["cluster"], sign * x * u / (x @ x))
    n, k = 1020, 2 + 1 + 101 + 9 + 9
    se_diff = np.sqrt(51 / 50 * (n - 1) / (n - k) * psi @ psi)
    primary = pd.read_csv(PUBLIC / "m10_primary.csv")
    stacked = primary[primary["model"].eq("stacked")].iloc[0]
    checks.close(INDEPENDENT, "stacked contrast 10*(b20-24 - b25-29)",
                 10 * (s1["beta"][0] - s2["beta"][0]), stacked["estimate_per10"])
    checks.close(INDEPENDENT, "stacked contrast clustered SE", 10 * se_diff, stacked["se"])

    # robustness (independent)
    robust = pd.read_csv(PUBLIC / "m10_robustness.csv")
    for age in ("20-24", "25-29"):
        d = data[data["age_group"].eq(age)].reset_index(drop=True)
        for variant, sample, weight in (
                ("2014-2019", d[d["year"] < 2020].reset_index(drop=True), None),
                ("2021-2024", d[d["year"] > 2020].reset_index(drop=True), None),
                ("excluding DC", d[d["state_fips"].ne("11")].reset_index(drop=True), None),
                ("female-population weighted", d, "female_population")):
            result = within_fit(sample, "rate_", ["burden30"], weight=weight)
            stored = robust[robust["age_group"].eq(age) & robust["variant"].eq(variant)].iloc[0]
            checks.close(INDEPENDENT, f"{age} robustness {variant}: 10*beta",
                         10 * result["beta"][0], stored["estimate_per10"])
            checks.close(INDEPENDENT, f"{age} robustness {variant}: SE",
                         10 * result["se"][0], stored["se"])
    loso = pd.read_csv(PUBLIC / "m10_loso.csv")
    for age in ("20-24", "25-29"):
        d = data[data["age_group"].eq(age)].reset_index(drop=True)
        values = [10 * within_fit(d[d["state_fips"].ne(s)].reset_index(drop=True), "rate_",
                                  ["burden30"])["beta"][0] for s in STATES]
        stored = loso[loso["age_group"].eq(age)]["estimate_per10"]
        checks.close(INDEPENDENT, f"{age} leave-one-state-out minimum", min(values), stored.min())
        checks.close(INDEPENDENT, f"{age} leave-one-state-out maximum", max(values), stored.max())

    # deterministic rerun of the wild bootstrap
    sys.path.insert(0, str(ROOT))
    from analysis import m10_models as m
    frame = m.load_analysis_frame()
    for age in ("20-24", "25-29"):
        rerun = m.wild_cluster_p(m.age_frame(frame, age), "outcome_rate", ["burden30_pct"],
                                 "burden30_pct")
        stored = primary[primary["test"].eq(f"beta {age} = 0 (model C)")].iloc[0]
        checks.close(RERUN, f"wild cluster bootstrap p, {age}", rerun,
                     stored["wild_bootstrap_p"], 1e-12)

    # coefficient figure: every plotted value against the stored tables
    import tempfile
    models_table = pd.read_csv(PUBLIC / "m10_models.csv")
    with tempfile.TemporaryDirectory() as tmp:
        plotted = m.figure_coefficients(models_table, robust, Path(tmp) / "figure.png")
    mismatched = []
    for row in plotted.itertuples():
        table = models_table if row.source == "models" else robust
        column = "model" if row.source == "models" else "variant"
        match = table[table["age_group"].eq(row.age_group) & table[column].eq(row.key)]
        if len(match) != 1 or not np.allclose(
                [row.estimate_per10, row.ci_low, row.ci_high],
                match[["estimate_per10", "ci_low", "ci_high"]].iloc[0].to_numpy(float),
                rtol=0, atol=0):
            mismatched.append((row.age_group, row.key))
    expected_rows = 2 * (4 + len(robust[robust["analysis"].ne("outcome")]) // 2)
    checks.add(RECONCILIATION, "coefficient figure plots exactly the stored estimates and CIs",
               not mismatched and len(plotted) == expected_rows,
               f"{len(plotted)} plotted rows; mismatches {mismatched}")
    tags_ok = all(("50%+" in r.label) == ("50%" in r.key) and ("B25072" in r.label)
                  == ("B25072" in r.key) for r in plotted.itertuples())
    checks.add(RECONCILIATION, "each figure row names its housing measure", tags_ok,
               "30%+ / 50%+ / B25072 / t-1 tags")

    # chapter reconciliation
    if CHAPTER.exists():
        text = CHAPTER.read_text(encoding="utf-8")
        for _, row in primary.iterrows():
            for value in (row["estimate_per10"], row["ci_low"], row["ci_high"]):
                token = f"{value:.2f}".replace("-", "−")
                checks.add(RECONCILIATION, f"chapter reports {row['test']} value {token}",
                           token in text, "found" if token in text else "not found")
    else:
        checks.add(RECONCILIATION, "chapter present", False, str(CHAPTER))

    print("M10 | VERIFICATION")
    for kind, status, label, detail in checks.rows:
        print(f"  {status}  [{kind}] {label}: {detail}")
    for kind in (INDEPENDENT, RERUN, RECONCILIATION):
        rows = [r for r in checks.rows if r[0] == kind]
        print(f"  {kind}: {sum(r[1] == 'PASS' for r in rows)} PASS, "
              f"{sum(r[1] == 'FAIL' for r in rows)} FAIL")
    failures = sum(r[1] == "FAIL" for r in checks.rows)
    print(f"Summary: {len(checks.rows) - failures} PASS, {failures} FAIL")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
