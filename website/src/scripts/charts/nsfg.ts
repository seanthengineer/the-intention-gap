import { scaleLinear } from "d3";
import data from "../../data/site-data.json";
import { bindTip, fmt, int, onResize, pct, segmented } from "../lib";
import { bottomAxis, ciWhisker, figureOf, gridX, svgIn, text } from "./common";

const H = data.nsfg.headline as Record<string, Record<string, { n: number; est: number; lo: number; hi: number; rel: string }>>;
const POP_LABEL: Record<string, string> = { all: "All", female: "Women", male: "Men" };

export function mountWantIntend(el: HTMLElement) {
  const fig = figureOf(el);
  let pop = "all";
  let width = 0;
  const draw = (w: number) => {
    width = w;
    const narrow = w < 560;
    const rows = [
      { key: "wants", label: "Want a child, or another child" },
      { key: "intends", label: "Intend to have one" },
    ];
    const rowH = narrow ? 96 : 88;
    const m = { t: 14, r: narrow ? 18 : 40, b: 40, l: narrow ? 8 : 250 };
    const height = m.t + rows.length * rowH + m.b;
    const x = scaleLinear().domain([0, 1]).range([m.l, w - m.r]);
    const d = H[pop];
    const svg = svgIn(
      el,
      w,
      height,
      `${POP_LABEL[pop]}: ${pct(d.wants.est)} want a child and ${pct(d.intends.est)} intend one. Weighted estimates with 95% intervals.`,
    );
    const g = svg.append("g");
    gridX(g, x, m.t, height - m.b, [0.25, 0.5, 0.75, 1]);
    bottomAxis(g, x, height - m.b + 6, [0, 0.25, 0.5, 0.75, 1], (v) => `${Math.round(v * 100)}%`);
    rows.forEach((r, i) => {
      const e = d[r.key];
      const top = m.t + i * rowH;
      const barY = narrow ? top + 30 : top + 18;
      const barH = narrow ? 26 : 30;
      if (narrow) text(g, m.l, top + 18, r.label, "anno");
      else text(g, m.l - 18, barY + barH / 2 + 5, r.label, "anno", "end").style("font-size", "14px");
      g.append("rect")
        .attr("x", x(0))
        .attr("y", barY)
        .attr("width", x(1) - x(0))
        .attr("height", barH)
        .attr("fill", "rgb(206 197 185 / 0.3)");
      const bar = g
        .append("rect")
        .attr("x", x(0))
        .attr("y", barY)
        .attr("width", x(e.est) - x(0))
        .attr("height", barH)
        .attr("fill", r.key === "wants" ? "var(--ink)" : "var(--oxblood)")
        .attr("tabindex", 0)
        .attr("aria-label", `${r.label}: ${pct(e.est)}`);
      ciWhisker(g, x(e.lo), x(e.hi), barY + barH + 7, "var(--ink)", 3);
      text(g, x(e.hi) + 12, barY + barH / 2 + 7, pct(e.est), "value").style("font-size", "19px");
      bindTip(bar.node()!, () => ({
        head: `${POP_LABEL[pop]}: ${r.label.toLowerCase()}`,
        rows: [
          ["Weighted estimate", pct(e.est)],
          ["95% interval", `${pct(e.lo)}–${pct(e.hi)}`],
          ["Respondents", int(e.n)],
        ],
        note: "Design-based (Korn–Graubard) interval. Stated answers at one interview.",
      }));
    });
  };
  const seg = fig.querySelector<HTMLElement>("[data-seg='pop']");
  if (seg) pop = segmented(seg, (v) => ((pop = v), draw(width)));
  onResize(el, draw);
}

const CAT: Record<string, { label: string; fill: string }> = {
  "positive intention": { label: "Intend one", fill: "var(--ink)" },
  "explicit negative": { label: "Say they do not intend one", fill: "var(--oxblood)" },
  "sterility-linked": { label: "Not asked: reported sterile", fill: "url(#ster)" },
  "unknown intention": { label: "Unknown", fill: "var(--rule)" },
  "not provided or other": { label: "Not provided", fill: "var(--rule-soft)" },
};

export function mountDecomposition(el: HTMLElement) {
  const D = data.nsfg.decomposition as Record<string, { category: string; n: number; est: number; lo: number; hi: number; rel: string }[]>;
  const draw = (w: number) => {
    const narrow = w < 640;
    const pops = ["all", "female", "male"];
    const rowH = 64;
    const m = { t: narrow ? 128 : 118, r: 12, b: 30, l: narrow ? 56 : 80 };
    const height = m.t + pops.length * rowH + m.b;
    const x = scaleLinear().domain([0, 1]).range([m.l, w - m.r]);
    const svg = svgIn(
      el,
      w,
      height,
      "Among people who want a child: 87.5% intend one, 6.6% say they do not, 4.7% were not asked because they or a partner were reported sterile, and about 1.3% are unknown or not provided. Women and men follow a similar pattern.",
    );
    const defs = svg.append("defs");
    const p = defs.append("pattern").attr("id", "ster").attr("width", 5).attr("height", 5).attr("patternUnits", "userSpaceOnUse").attr("patternTransform", "rotate(45)");
    p.append("rect").attr("width", 5).attr("height", 5).attr("fill", "rgb(125 41 38 / 0.18)");
    p.append("line").attr("x1", 0).attr("x2", 0).attr("y1", 0).attr("y2", 5).attr("stroke", "var(--oxblood)").attr("stroke-width", 1.6);
    const g = svg.append("g");
    bottomAxis(g, x, height - m.b + 4, [0, 0.25, 0.5, 0.75, 1], (v) => `${Math.round(v * 100)}%`);
    pops.forEach((pop, i) => {
      const y = m.t + i * rowH;
      text(g, m.l - 12, y + 22, POP_LABEL[pop], "anno", "end");
      text(g, m.l - 12, y + 38, `n ${int(D[pop][0].n)}`, "anno-muted", "end");
      let acc = 0;
      for (const c of D[pop]) {
        const seg = g
          .append("rect")
          .attr("x", x(acc))
          .attr("y", y + 8)
          .attr("width", Math.max(0.5, x(acc + c.est) - x(acc) - 1.5))
          .attr("height", 36)
          .attr("fill", CAT[c.category].fill)
          .attr("tabindex", 0)
          .attr("aria-label", `${POP_LABEL[pop]}, ${CAT[c.category].label}: ${pct(c.est)}`);
        bindTip(seg.node()!, () => ({
          head: `${POP_LABEL[pop]}: ${CAT[c.category].label}`,
          rows: [
            ["Share of those who want a child", pct(c.est)],
            ["95% interval", `${pct(c.lo)}–${pct(c.hi)}`],
          ],
          note:
            c.category === "sterility-linked"
              ? "A CDC recode classification: respondents not asked about intentions because they or their partner were reported sterile. Not a stated preference."
              : "Weighted, design-based estimate.",
        }));
        if (c.est > 0.04) text(g, x(acc) + 6, y + 31, pct(c.est), "value", "start").style("fill", c.category === "positive intention" || c.category === "explicit negative" ? "var(--paper-light)" : "var(--ink)").style("font-size", "13px").style("pointer-events", "none");
        acc += c.est;
      }
    });
    const all = D.all;
    const pos = all.find((c) => c.category === "positive intention")!.est;
    const exp = all.find((c) => c.category === "explicit negative")!.est;
    const ster = all.find((c) => c.category === "sterility-linked")!.est;
    const div = H.all.divergence_among_wanters.est;
    const bx0 = x(pos);
    const bx1 = x(pos + exp + ster);
    const by = m.t - 6;
    g.append("path").attr("d", `M${bx0},${by}V${by - 8}H${bx1}V${by}`).attr("fill", "none").attr("stroke", "var(--oxblood)");
    const sx0 = x(pos + exp);
    g.append("path").attr("d", `M${sx0},${by - 34}V${by - 42}H${bx1}V${by - 34}`).attr("fill", "none").attr("stroke", "var(--gray)");
    text(g, bx0 - 8, by - 2, `${pct(div)} want a child but do not intend one`, "anno", "end").style("fill", "var(--oxblood)");
    text(g, sx0 - 8, by - 34, `about ${Math.round((ster / div) * 100)}% of that is the sterility classification`, "anno-muted", "end");
    if (!narrow) {
      const keys = Object.keys(CAT);
      let lx = m.l;
      const ly = 14;
      keys.forEach((k) => {
        g.append("rect").attr("x", lx).attr("y", ly - 9).attr("width", 10).attr("height", 10).attr("fill", CAT[k].fill).attr("stroke", k === "sterility-linked" ? "var(--oxblood)" : "none");
        const t = text(g, lx + 16, ly, CAT[k].label, "anno-muted");
        lx += 16 + (t.node()!.getComputedTextLength?.() ?? 120) + 22;
      });
    }
  };
  onResize(el, draw);
}

const GROUP_LABEL: Record<string, string> = {
  age_group: "Age group",
  sex: "Sex",
  partnership: "Partnership",
  children_group: "Children already",
  education: "Education",
  race_ethnicity: "Race and ethnicity",
  poverty_group: "Household income vs poverty line",
  metro: "Where they live",
  religion: "Religion",
  insurance: "Health insurance",
  labor_force: "Main activity",
  interview_year: "Interview year",
  intention_branch: "Intention question asked",
};
const MEASURE_LABEL: Record<string, string> = {
  wants: "Want a child",
  intends: "Intend a child",
  divergence_among_wanters: "Want, but do not intend",
  explicit_among_wanters: "Explicit “no” among those who want",
};
const LEVEL_ORDER: Record<string, string[]> = {
  education: ["less than high school", "high school or GED", "some college or associate", "bachelor's or higher"],
  poverty_group: ["below 100% of poverty", "100-199%", "200-399%", "400% or more"],
  children_group: ["no children", "one child", "two or more"],
  partnership: ["married", "cohabiting", "neither"],
  metro: ["principal city", "other metropolitan", "nonmetropolitan"],
};
const REASON: Record<string, string> = {
  "suppress: relative CI width > 130%": "interval too wide relative to the estimate",
  "suppress: effective n < 30": "too few effective respondents",
  "suppress: CI width >= 30 pp": "interval 30 points wide or more",
};

export function mountSubgroups(el: HTMLElement) {
  const fig = figureOf(el);
  const rows = data.nsfg.subgroups as { pop: string; g: string; level: string; m: string; n: number; est: number | null; lo: number | null; hi: number | null; rel: string }[];
  const selG = fig.querySelector<HTMLSelectElement>("select[name='group']")!;
  const selM = fig.querySelector<HTMLSelectElement>("select[name='measure']")!;
  const selP = fig.querySelector<HTMLSelectElement>("select[name='pop']")!;
  const summary = fig.querySelector<HTMLElement>("[data-summary]");
  let width = 0;
  const refreshGroups = () => {
    const avail = [...new Set(rows.filter((r) => r.pop === selP.value).map((r) => r.g))];
    const keep = selG.value;
    selG.innerHTML = Object.keys(GROUP_LABEL)
      .filter((k) => avail.includes(k))
      .map((k) => `<option value="${k}">${GROUP_LABEL[k]}</option>`)
      .join("");
    selG.value = avail.includes(keep) ? keep : "age_group";
  };
  const draw = (w: number) => {
    width = w;
    const narrow = w < 600;
    const g0 = selG.value;
    const m0 = selM.value;
    const p0 = selP.value;
    let set = rows.filter((r) => r.pop === p0 && r.g === g0 && r.m === m0);
    const order = LEVEL_ORDER[g0];
    if (order) set = [...set].sort((a, b) => order.indexOf(a.level) - order.indexOf(b.level));
    const overall = H[p0][m0];
    const his = set.filter((r) => r.hi !== null).map((r) => r.hi as number);
    const maxV = m0 === "wants" || m0 === "intends" ? 1 : Math.max(0.2, Math.ceil(Math.max(overall.est, ...his) * 10) / 10);
    const rowH = narrow ? 54 : 40;
    const m = { t: 30, r: narrow ? 16 : 120, b: 42, l: narrow ? 12 : 250 };
    const height = m.t + set.length * rowH + m.b;
    const x = scaleLinear().domain([0, maxV]).range([m.l, w - m.r]);
    const svg = svgIn(el, w, height, `${MEASURE_LABEL[m0]} by ${GROUP_LABEL[g0].toLowerCase()}, ${POP_LABEL[p0].toLowerCase()}. Weighted estimates with 95% intervals; suppressed estimates are not drawn.`);
    const g = svg.append("g");
    const ticks = maxV === 1 ? [0, 0.25, 0.5, 0.75, 1] : Array.from({ length: Math.round(maxV * 10) + 1 }, (_, i) => i / 10);
    gridX(g, x, m.t - 6, height - m.b, ticks);
    bottomAxis(g, x, height - m.b + 6, ticks, (v) => `${Math.round(v * 100)}%`);
    g.append("line").attr("x1", x(overall.est)).attr("x2", x(overall.est)).attr("y1", m.t - 14).attr("y2", height - m.b).attr("stroke", "var(--oxblood)").attr("stroke-dasharray", "3 3");
    text(g, x(overall.est), m.t - 18, `overall ${pct(overall.est)}`, "anno-muted", "middle").style("fill", "var(--oxblood)");
    let shown = 0;
    set.forEach((r, i) => {
      const yy = m.t + i * rowH + rowH / 2 + (narrow ? 8 : 0);
      if (narrow) text(g, m.l, yy - 16, r.level.charAt(0).toUpperCase() + r.level.slice(1), "anno");
      else text(g, m.l - 16, yy + 4, r.level.charAt(0).toUpperCase() + r.level.slice(1), "anno", "end");
      if (!narrow) text(g, m.l - 16, yy + 18, `n ${int(r.n)}`, "anno-muted", "end").style("font-size", "10.5px");
      if (r.est === null) {
        const t = text(g, x(0) + 4, yy + 4, `Suppressed: ${REASON[r.rel] ?? "fails the NCHS standard"} (n ${int(r.n)})`, "anno-muted");
        t.style("font-style", "normal");
        return;
      }
      shown++;
      ciWhisker(g, x(r.lo!), x(r.hi!), yy, "var(--ink)");
      const c = g
        .append("circle")
        .attr("cx", x(r.est))
        .attr("cy", yy)
        .attr("r", 5.5)
        .attr("fill", "var(--ink)")
        .attr("tabindex", 0)
        .attr("aria-label", `${r.level}: ${pct(r.est)}`);
      bindTip(c.node()!, () => ({
        head: `${GROUP_LABEL[g0]}: ${r.level}`,
        rows: [
          [MEASURE_LABEL[m0], pct(r.est)],
          ["95% interval", `${pct(r.lo)}–${pct(r.hi)}`],
          ["Respondents (unweighted)", int(r.n)],
        ],
        note: "Design-based Korn–Graubard interval. Overlapping intervals mean the data cannot separate the groups.",
      }));
      if (!narrow) text(g, x(r.hi!) + 8, yy + 4, pct(r.est), "anno-muted");
    });
    if (summary) {
      const sup = set.length - shown;
      summary.textContent = `${shown} of ${set.length} estimates shown${sup ? `; ${sup} suppressed under the NCHS reliability standard and not drawn` : ""}.`;
    }
  };
  selP.addEventListener("change", () => (refreshGroups(), draw(width)));
  selG.addEventListener("change", () => draw(width));
  selM.addEventListener("change", () => draw(width));
  refreshGroups();
  onResize(el, draw);
}

export function mountAuc(el: HTMLElement) {
  const model = data.nsfg.model;
  const LABEL: Record<string, string> = { dummy: "No-information baseline", logistic: "Logistic regression", boosting: "Gradient boosting" };
  const draw = (w: number) => {
    const narrow = w < 560;
    const hold = model.holdout;
    const rowH = narrow ? 52 : 44;
    const m = { t: 40, r: 24, b: 48, l: narrow ? 12 : 210 };
    const height = m.t + (hold.length + 2) * rowH + 24 + m.b + (narrow ? 40 : 0);
    const x = scaleLinear().domain([0.3, 0.8]).range([m.l, w - m.r]);
    const svg = svgIn(
      el,
      w,
      height,
      "ROC AUC on the isolated holdout: baseline 0.50, logistic regression 0.51, gradient boosting 0.44. Repeated cross-validation suggested about 0.62 for logistic regression, which the holdout did not confirm.",
    );
    const g = svg.append("g");
    gridX(g, x, m.t - 10, height - m.b, [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]);
    bottomAxis(g, x, height - m.b + 6, [0.3, 0.4, 0.5, 0.6, 0.7, 0.8], (v) => v.toFixed(1));
    text(g, x(0.55), height - 8, narrow ? "ROC AUC (0.5 = chance)" : "ROC AUC (0.5 = no better than chance; 1.0 = perfect)", "axis-title", "middle");
    g.append("line").attr("x1", x(0.5)).attr("x2", x(0.5)).attr("y1", m.t - 16).attr("y2", height - m.b).attr("stroke", "var(--oxblood)");
    text(g, x(0.5) + 6, m.t - 20, "chance", "anno-muted").style("fill", "var(--oxblood)");
    text(g, narrow ? m.l : m.l - 14, m.t + 2, "Locked holdout", "label", narrow ? "start" : "end").style("fill", "var(--gray)");
    hold.forEach((h, i) => {
      const yy = m.t + 18 + i * rowH + (narrow ? 14 : 0);
      if (narrow) text(g, m.l, yy - 14, LABEL[h.model], "anno");
      else text(g, m.l - 14, yy + 4, LABEL[h.model], "anno", "end");
      if (h.aucCi && h.aucCi[1] > h.aucCi[0]) ciWhisker(g, x(h.aucCi[0]), x(h.aucCi[1]), yy, "var(--ink)");
      const c = g.append("circle").attr("cx", x(h.auc)).attr("cy", yy).attr("r", 6).attr("fill", h.model === "dummy" ? "var(--paper-light)" : "var(--ink)").attr("stroke", "var(--ink)").attr("stroke-width", 1.5).attr("tabindex", 0).attr("aria-label", `${LABEL[h.model]}: AUC ${h.auc.toFixed(2)}`);
      bindTip(c.node()!, () => ({
        head: LABEL[h.model],
        rows: [
          ["ROC AUC", h.auc.toFixed(3)],
          ["95% bootstrap interval", h.aucCi[1] > h.aucCi[0] ? `${h.aucCi[0].toFixed(2)}–${h.aucCi[1].toFixed(2)}` : "fixed at 0.50"],
          ["Average precision", h.prAuc.toFixed(3)],
          ["Share who said no", pct(h.prevalence)],
          ["Brier skill vs baseline", `${fmt(h.brierSkill * 100, 1, true)}%`],
        ],
        note: `Isolated cluster holdout: ${h.n} respondents, ${h.positives} who said no. Bootstrap, 2,000 replicates.`,
      }));
      if (!narrow) text(g, x(h.auc) + (h.model === "boosting" ? -12 : 12), yy - 9, h.auc.toFixed(2), "anno", h.model === "boosting" ? "end" : "start");
    });
    const y2 = m.t + 18 + hold.length * rowH + 22 + (narrow ? 10 : 0);
    text(g, narrow ? m.l : m.l - 14, y2 - 8, "Cross-validation", "label", narrow ? "start" : "end").style("fill", "var(--gray)");
    (["logistic", "boosting"] as const).forEach((k, i) => {
      const s = model.stability[k];
      const yy = y2 + 10 + i * rowH + (narrow ? 14 : 0);
      if (narrow) text(g, m.l, yy - 14, LABEL[k], "anno-muted");
      else text(g, m.l - 14, yy + 4, LABEL[k], "anno-muted", "end");
      g.append("line").attr("x1", x(s.min)).attr("x2", x(s.max)).attr("y1", yy).attr("y2", yy).attr("stroke", "var(--gray)").attr("stroke-width", 3).attr("stroke-linecap", "round").attr("opacity", 0.5);
      const c = g.append("circle").attr("cx", x(s.mean)).attr("cy", yy).attr("r", 5).attr("fill", "var(--paper-light)").attr("stroke", "var(--gray)").attr("stroke-width", 1.5).attr("tabindex", 0).attr("aria-label", `${LABEL[k]} cross-validation mean AUC ${s.mean.toFixed(2)}`);
      bindTip(c.node()!, () => ({
        head: `${LABEL[k]}: repeated cross-validation`,
        rows: [
          ["Mean ROC AUC", s.mean.toFixed(3)],
          [`Range over ${s.seeds} seeds`, `${s.min.toFixed(3)}–${s.max.toFixed(3)}`],
        ],
        note: "Grouped 5-fold cross-validation across all 80 clusters. A development check: the locked holdout above is the test that counts.",
      }));
    });
  };
  onResize(el, draw);
}
