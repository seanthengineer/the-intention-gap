import { area, interpolateRgb, line, scaleLinear } from "d3";
import data from "../../data/site-data.json";
import geo from "../../data/geo.json";
import { bindTip, fmt, onResize, segmented } from "../lib";
import { bottomAxis, ciWhisker, figureOf, gridX, gridY, leftAxis, svgIn, text } from "./common";

type YearRow = { year: number; v: string; median: number; p25: number; p75: number; min: number; max: number; national: number | null };
const byYear = data.m10.byYear as YearRow[];

export function mountTrends(el: HTMLElement) {
  const draw = (w: number) => {
    const narrow = w < 760;
    const panelW = narrow ? w : (w - 48) / 2;
    const panelH = 300;
    const height = narrow ? panelH * 2 + 40 : panelH;
    const svg = svgIn(
      el,
      w,
      height,
      "Left: national birth rates per 1,000 women fell from 2014 to 2024, ages 20 to 24 from about 79 to 56 and ages 25 to 29 from about 106 to 90, with bands showing the middle half of states. Right: the state median share of renters paying 30% or more of income on rent stayed near 46 to 50% for all renter households, and was higher for householders aged 15 to 24. No 2020 ACS 1-year release.",
    );
    const panel = (ox: number, oy: number, title: string, series: { v: string; label: string; color: string; key: "national" | "median" }[], domain: [number, number], unit: string) => {
      const g = svg.append("g").attr("transform", `translate(${ox},${oy})`);
      const m = { t: 34, r: narrow ? 122 : 112, b: 30, l: 40 };
      const x = scaleLinear().domain([2013.6, 2024.4]).range([m.l, panelW - m.r]);
      const y = scaleLinear().domain(domain).range([panelH - m.b, m.t]);
      const ticks = y.ticks(4);
      gridY(g as never, y, m.l, panelW - m.r, ticks);
      leftAxis(g as never, y, m.l - 4, ticks, (v) => String(v) + unit);
      bottomAxis(g as never, x, panelH - m.b + 4, [2014, 2016, 2018, 2020, 2022, 2024], String);
      text(g as never, 0, 14, title, "axis-title");
      for (const s of series) {
        const rows = byYear.filter((r) => r.v === s.v).sort((a, b) => a.year - b.year);
        const segs: YearRow[][] = [];
        let cur: YearRow[] = [];
        for (const r of rows) {
          if (cur.length && r.year - cur[cur.length - 1].year > 1) {
            segs.push(cur);
            cur = [];
          }
          cur.push(r);
        }
        if (cur.length) segs.push(cur);
        for (const sg of segs) {
          g.append("path")
            .datum(sg)
            .attr("fill", s.color)
            .attr("opacity", 0.12)
            .attr("d", area<YearRow>().x((d) => x(d.year)).y0((d) => y(d.p25)).y1((d) => y(d.p75)));
          g.append("path")
            .datum(sg)
            .attr("fill", "none")
            .attr("stroke", s.color)
            .attr("stroke-width", 2)
            .attr("d", line<YearRow>().x((d) => x(d.year)).y((d) => y((d[s.key] ?? d.median) as number)));
          for (const d of sg) {
            const c = g
              .append("circle")
              .attr("cx", x(d.year))
              .attr("cy", y((d[s.key] ?? d.median) as number))
              .attr("r", 3)
              .attr("fill", s.color);
            bindTip(c.node()!, () => ({
              head: `${s.label}, ${d.year}`,
              rows: [
                [s.key === "national" ? "National rate" : "State median", fmt((d[s.key] ?? d.median) as number) + unit],
                ["Middle half of states", `${fmt(d.p25)}–${fmt(d.p75)}${unit}`],
                ["Lowest to highest state", `${fmt(d.min)}–${fmt(d.max)}${unit}`],
              ],
              note: "Bands show the spread across 51 jurisdictions, not confidence intervals.",
            }));
          }
        }
        const last = rows[rows.length - 1];
        text(g as never, x(last.year) + 8, y((last[s.key] ?? last.median) as number) + 4, s.label, "anno").style("fill", s.color);
      }
      if (series[0].v.includes("burden")) {
        text(g as never, x(2020), y(domain[0]) - 8, "no 2020 release", "anno-muted", "middle");
      }
    };
    panel(
      0,
      0,
      "Births per 1,000 women (national; band: middle half of states)",
      [
        { v: "rate_25-29", label: "Ages 25–29", color: "var(--ink)", key: "national" },
        { v: "rate_20-24", label: "Ages 20–24", color: "var(--oxblood)", key: "national" },
      ],
      [40, 125],
      "",
    );
    panel(
      narrow ? 0 : panelW + 48,
      narrow ? panelH + 40 : 0,
      "Renters paying 30%+ of income (state median and middle half)",
      [
        { v: "young15_24_burden30_pct", label: "Householders 15–24", color: "var(--slate)", key: "median" },
        { v: "burden30_pct", label: "All renters", color: "var(--ink)", key: "median" },
      ],
      [35, 70],
      "%",
    );
  };
  onResize(el, draw);
}

const SPEC: Record<string, { short: string; text: string }> = {
  "A pooled": { short: "A  All state-years pooled", text: "Compares every state-year with every other. States differ in many ways besides rent, so this mixes them all together." },
  "B state FE": { short: "B  Within each state", text: "Compares each state only with itself over time. But the national decline in births, common to all states, still leaks in." },
  "C state + year FE (primary)": { short: "C  Within state, net of national trend", text: "Also removes the change common to all states in each year. This is the specification the protocol fixed in advance as primary." },
  "D + unemployment": { short: "D  C, plus unemployment", text: "Adds the state unemployment rate as a control. The estimate barely moves." },
  "E one-year lag": { short: "E  C, using last year's burden", text: "Uses the previous year's rent burden, allowing a delay. One fewer year of data; the interval still includes zero." },
};

export function mountLadder(el: HTMLElement) {
  const fig = figureOf(el);
  const explain = fig.querySelector<HTMLElement>("[data-explain]");
  let age = "20-24";
  let step = "C state + year FE (primary)";
  let width = 0;
  const draw = (w: number) => {
    width = w;
    const narrow = w < 640;
    const models = data.m10.models.filter((r) => r.age === age);
    const rowH = narrow ? 58 : 46;
    const m = { t: 34, r: 24, b: 50, l: narrow ? 14 : 290 };
    const height = m.t + models.length * rowH + m.b;
    const x = scaleLinear().domain([-36, 6]).range([m.l, w - m.r]);
    const svg = svgIn(el, w, height, `Estimated change in births per 1,000 women aged ${age} for a 10-point higher rent-burden share, under five model specifications, with 95% state-clustered intervals.`);
    const g = svg.append("g");
    const ticks = [-35, -30, -25, -20, -15, -10, -5, 0, 5];
    gridX(g, x, m.t - 10, height - m.b, ticks);
    bottomAxis(g, x, height - m.b + 6, ticks, (v) => fmt(v, 0));
    text(g, x(-15), height - 10, "Births per 1,000 women, per 10-point higher rent burden", "axis-title", "middle");
    g.append("line").attr("x1", x(0)).attr("x2", x(0)).attr("y1", m.t - 16).attr("y2", height - m.b).attr("stroke", "var(--ink)");
    text(g, x(0) + 6, m.t - 18, "no association", "anno-muted");
    models.forEach((r, i) => {
      const yy = m.t + i * rowH + rowH / 2 + (narrow ? 10 : 0);
      const active = r.model === step;
      const primary = r.model.includes("primary");
      const col = active ? "var(--oxblood)" : "var(--ink)";
      const t = narrow ? text(g, m.l, yy - 16, SPEC[r.model].short, "anno") : text(g, m.l - 16, yy + 4, SPEC[r.model].short, "anno", "end");
      t.style("font-weight", active ? "600" : "400").style("cursor", "pointer");
      t.on("click", () => ((step = r.model), sync(), draw(width)));
      g.append("rect").attr("x", 0).attr("width", w).attr("y", yy - rowH / 2 + (narrow ? -10 : 0)).attr("height", rowH).attr("fill", active ? "rgb(125 41 38 / 0.06)" : "transparent").lower();
      ciWhisker(g, x(r.lo), x(r.hi), yy, col);
      const c = g
        .append("rect")
        .attr("x", x(r.est) - 6)
        .attr("y", yy - 6)
        .attr("width", 12)
        .attr("height", 12)
        .attr("fill", primary ? col : "var(--paper-light)")
        .attr("stroke", col)
        .attr("stroke-width", 1.5)
        .attr("tabindex", 0)
        .attr("aria-label", `${SPEC[r.model].short}: ${fmt(r.est, 2)}, 95% interval ${fmt(r.lo, 2)} to ${fmt(r.hi, 2)}`)
        .style("cursor", "pointer")
        .on("click", () => ((step = r.model), sync(), draw(width)));
      bindTip(c.node()!, () => ({
        head: SPEC[r.model].short.slice(3),
        rows: [
          ["Estimate", fmt(r.est, 2)],
          ["95% interval", `${fmt(r.lo, 2)} to ${fmt(r.hi, 2)}`],
          ["p-value", r.p.toFixed(3)],
          ["State-years", String(r.n)],
        ],
        note: "State-clustered 95% interval (51 clusters).",
      }));
      text(g, x(r.est), yy - 11, fmt(r.est, 2), "anno", "middle").style("fill", col).style("font-size", "11.5px");
    });
  };
  const sync = () => {
    if (explain) explain.textContent = SPEC[step].text;
    fig.querySelectorAll<HTMLButtonElement>("[data-step]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.step === step)));
  };
  fig.querySelectorAll<HTMLButtonElement>("[data-step]").forEach((b) => b.addEventListener("click", () => ((step = b.dataset.step!), sync(), draw(width))));
  const seg = fig.querySelector<HTMLElement>("[data-seg='age']");
  if (seg) age = segmented(seg, (v) => ((age = v), draw(width)));
  sync();
  onResize(el, draw);
}

const ROB_LABEL: Record<string, string> = {
  period: "Period",
  weighting: "Weighting",
  sample: "Sample",
  lag: "Lag",
  exposure: "Exposure",
  trends: "Trends",
  controls: "Controls",
  outcome: "Outcome",
};

export function mountRobustness(el: HTMLElement) {
  const fig = figureOf(el);
  let age = "20-24";
  let width = 0;
  const draw = (w: number) => {
    width = w;
    const narrow = w < 640;
    const prim = data.m10.primary.find((p) => p.age === age && p.test.includes("(model C)"))!;
    const rows = [
      { analysis: "primary", variant: "Primary model C (protocol)", est: prim.est, lo: prim.lo, hi: prim.hi, note: "" },
      ...data.m10.robustness.filter((r) => r.age === age && r.analysis !== "outcome"),
    ];
    const rowH = narrow ? 50 : 30;
    const m = { t: 22, r: 24, b: 48, l: narrow ? 14 : 360 };
    const height = m.t + rows.length * rowH + m.b;
    const x = scaleLinear().domain([-12, 6]).range([m.l, w - m.r]);
    const svg = svgIn(el, w, height, `Robustness checks for ages ${age}: estimates and 95% intervals under alternative periods, weights, samples, lags, exposures, trends, controls and outcomes.`);
    const g = svg.append("g");
    const ticks = [-12, -9, -6, -3, 0, 3, 6];
    gridX(g, x, m.t - 8, height - m.b, ticks);
    bottomAxis(g, x, height - m.b + 6, ticks, (v) => fmt(v, 0));
    text(g, x(-3), height - 10, "Births per 1,000 women, per 10-point higher burden", "axis-title", "middle");
    g.append("line").attr("x1", x(0)).attr("x2", x(0)).attr("y1", m.t - 12).attr("y2", height - m.b).attr("stroke", "var(--ink)");
    rows.forEach((r, i) => {
      const yy = m.t + i * rowH + rowH / 2 + (narrow ? 8 : 0);
      const isPrim = r.analysis === "primary";
      const col = isPrim ? "var(--oxblood)" : "var(--ink)";
      const label = isPrim ? r.variant : `${ROB_LABEL[r.analysis] ?? r.analysis}: ${r.variant}`;
      if (narrow) text(g, m.l, yy - 14, label, "anno-muted").style("font-size", "11.5px");
      else text(g, m.l - 14, yy + 4, label, isPrim ? "anno" : "anno-muted", "end");
      const lo = Math.max(r.lo, -12);
      const hi = Math.min(r.hi, 6);
      ciWhisker(g, x(lo), x(hi), yy, col, 3);
      const c = g.append("circle").attr("cx", x(r.est)).attr("cy", yy).attr("r", 4.5).attr("fill", col).attr("tabindex", 0).attr("aria-label", `${label}: ${fmt(r.est, 2)}`);
      bindTip(c.node()!, () => ({
        head: label,
        rows: [
          ["Estimate", fmt(r.est, 2)],
          ["95% interval", `${fmt(r.lo, 2)} to ${fmt(r.hi, 2)}`],
        ],
        note: isPrim ? "Protocol primary model." : r.note ? `Exploratory. ${r.note}.` : "Exploratory robustness check; not a protocol test.",
      }));
    });
  };
  const seg = fig.querySelector<HTMLElement>("[data-seg='age']");
  if (seg) age = segmented(seg, (v) => ((age = v), draw(width)));
  onResize(el, draw);
}

export function mountLoso(el: HTMLElement) {
  const fig = figureOf(el);
  const summary = fig.querySelector<HTMLElement>("[data-summary]");
  let age = "20-24";
  let width = 0;
  const draw = (w: number) => {
    width = w;
    const narrow = w < 640;
    const rows = data.m10.loso.filter((r) => r.age === age);
    const full = data.m10.primary.find((p) => p.age === age && p.test.includes("(model C)"))!;
    const byFips = new Map(rows.map((r) => [r.fips, r]));
    const maxAbs = Math.max(...rows.map((r) => Math.abs(r.change)));
    const legendH = 54;
    const mapW = w;
    const s = mapW / geo.width;
    const mapH = geo.height * s;
    const height = mapH + legendH + 10;
    const toward = interpolateRgb("#f1ede5", "#3f6383");
    const away = interpolateRgb("#f1ede5", "#7d2926");
    const color = (chg: number) => (chg < 0 ? away(Math.min(1, Math.abs(chg) / maxAbs) * 0.95 + 0.05) : toward(Math.min(1, chg / maxAbs) * 0.95 + 0.05));
    const svg = svgIn(el, w, height, `Map of the change in the primary estimate for ages ${age} when each state is left out. The largest change is ${fmt(maxAbs, 2)}.`);
    const g = svg.append("g").attr("transform", `scale(${s})`);
    const dots = geo.dots as [number, number, string][];
    const r = geo.step * 0.36;
    for (const [dx, dy, id] of dots) {
      const row = byFips.get(id);
      g.append("rect")
        .attr("x", dx - r)
        .attr("y", dy - r)
        .attr("width", r * 2)
        .attr("height", r * 2)
        .attr("fill", row ? color(row.change) : "var(--rule)");
    }
    const outlines = g.append("g");
    for (const st of geo.states) {
      const row = byFips.get(st.id);
      if (!st.d) continue;
      const p = outlines
        .append("path")
        .attr("d", st.d)
        .attr("fill", "transparent")
        .attr("stroke", "rgb(41 41 41 / 0.28)")
        .attr("stroke-width", 0.6 / s)
        .attr("tabindex", row ? 0 : -1)
        .attr("aria-label", row ? `Without ${row.state}: estimate ${fmt(row.est, 2)}` : st.name)
        .style("cursor", row ? "pointer" : "default");
      p.on("pointerenter focus", function () {
        (this as SVGPathElement).setAttribute("stroke", "var(--ink)");
        (this as SVGPathElement).setAttribute("stroke-width", String(1.8 / s));
      });
      p.on("pointerleave blur", function () {
        (this as SVGPathElement).setAttribute("stroke", "rgb(41 41 41 / 0.28)");
        (this as SVGPathElement).setAttribute("stroke-width", String(0.6 / s));
      });
      if (row)
        bindTip(p.node()!, () => ({
          head: `Leaving out ${row.state}`,
          rows: [
            ["Estimate without it", fmt(row.est, 2)],
            ["Change from full sample", fmt(row.change, 2, true)],
            ["p-value without it", row.p.toFixed(3)],
            ["Full-sample estimate", fmt(full.est, 2)],
          ],
          note: "Model C refitted on the other 50 jurisdictions. A sensitivity check, not a state-level result.",
        }));
    }
    const ly = mapH + 18;
    const lw = Math.min(320, w * 0.7);
    const lx = narrow ? 0 : w - lw - 10;
    const lg = svg.append("g").attr("transform", `translate(${lx},${ly})`);
    const n = 40;
    for (let i = 0; i < n; i++) {
      const v = -maxAbs + (2 * maxAbs * i) / (n - 1);
      lg.append("rect").attr("x", (i * lw) / n).attr("y", 0).attr("width", lw / n + 0.5).attr("height", 10).attr("fill", color(v));
    }
    text(lg as never, 0, 28, `${fmt(-maxAbs, 2)} more negative`, "anno-muted");
    text(lg as never, lw, 28, `closer to zero ${fmt(maxAbs, 2, true)}`, "anno-muted", "end");
    text(lg as never, lw / 2, 28, "0", "anno-muted", "middle");
    if (summary) {
      const lo = rows.reduce((a, b) => (b.est < a.est ? b : a));
      const hi = rows.reduce((a, b) => (b.est > a.est ? b : a));
      const sig = rows.filter((r) => r.p < 0.05);
      summary.textContent = `Ages ${age.replace("-", "–")}: leaving out any one jurisdiction moves the estimate between ${fmt(lo.est, 2)} (without ${lo.state}) and ${fmt(hi.est, 2)} (without ${hi.state}); the full-sample estimate is ${fmt(full.est, 2)}. ${sig.length ? `In ${sig.length} of 51 refits the p-value falls below 0.05 (${sig.map((r) => r.state).join(", ")}), which shows how close to the threshold the estimate sits, not a robust effect.` : "In no refit does the p-value fall below 0.05."}`;
    }
  };
  const seg = fig.querySelector<HTMLElement>("[data-seg='age']");
  if (seg) age = segmented(seg, (v) => ((age = v), draw(width)));
  onResize(el, draw);
}
