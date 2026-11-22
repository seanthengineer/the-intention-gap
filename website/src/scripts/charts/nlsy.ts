import { line, scaleLinear, scaleSqrt } from "d3";
import data from "../../data/site-data.json";
import { bindTip, fmt, int, onResize, toggle } from "../lib";
import { bottomAxis, ciWhisker, figureOf, gridX, gridY, leftAxis, svgIn, text } from "./common";

const cal = data.nlsy.calibration;
const recal = data.nlsy.recalibration as [number, number][];
const dist = data.nlsy.distribution;

export function mountCalibration(el: HTMLElement) {
  const fig = figureOf(el);
  let showRecal = false;
  let showDist = false;
  const tRecal = fig.querySelector<HTMLButtonElement>("[data-toggle='recal']");
  const tDist = fig.querySelector<HTMLButtonElement>("[data-toggle='dist']");
  let width = 0;
  const draw = (w: number) => {
    width = w;
    const narrow = w < 560;
    const plotH = Math.round(Math.min(560, Math.max(320, w * (narrow ? 0.95 : 0.62))));
    const distH = showDist ? 110 : 0;
    const height = plotH + distH;
    const m = { t: 22, r: narrow ? 14 : 200, b: 46, l: 50 };
    const x = scaleLinear().domain([0, 100]).range([m.l, w - m.r]);
    const y = scaleLinear().domain([0, 100]).range([plotH - m.b, m.t]);
    const rScale = scaleSqrt().domain([0, 1200]).range([0, narrow ? 13 : 17]);
    const svg = svgIn(
      el,
      w,
      height,
      "Calibration chart. For each range of stated chance of a birth within five years, the share of women who had one. At a stated 0%, 18.4% had a birth. At a stated 100%, 73.0% did. Points lie above the diagonal at low stated chances and below it at high ones.",
    );
    const g = svg.append("g");
    gridY(g, y, m.l, x(100), [20, 40, 60, 80, 100]);
    gridX(g, x, m.t, y(0), [20, 40, 60, 80, 100]);
    leftAxis(g, y, m.l - 4, [0, 20, 40, 60, 80, 100], (v) => `${v}%`);
    bottomAxis(g, x, y(0) + 6, [0, 20, 40, 60, 80, 100], (v) => `${v}%`);
    text(g, x(50), plotH - 6, "Stated chance of a birth within five years (mean in range)", "axis-title", "middle");
    text(g, m.l - 4, m.t - 8, "Share who had a birth", "axis-title");

    g.append("line")
      .attr("x1", x(0))
      .attr("y1", y(0))
      .attr("x2", x(100))
      .attr("y2", y(100))
      .attr("stroke", "var(--gray)")
      .attr("stroke-dasharray", "4 4");
    const diagLabel = text(g, x(narrow ? 58 : 64), y(narrow ? 58 : 64) - 10, "Perfect calibration", "anno-muted", "end");
    diagLabel.attr("transform", `rotate(${(-Math.atan2(y(0) - y(100), x(100) - x(0)) * 180) / Math.PI}, ${x(narrow ? 58 : 64)}, ${y(narrow ? 58 : 64) - 10})`);

    if (showRecal) {
      g.append("path")
        .datum(recal)
        .attr("fill", "none")
        .attr("stroke", "var(--slate)")
        .attr("stroke-width", 2)
        .attr("d", line<[number, number]>().x((d) => x(d[0])).y((d) => y(d[1] * 100)));
      const at = recal.find((r) => r[0] === 66) ?? recal[recal.length - 1];
      text(g, x(at[0]) + 4, y(at[1] * 100) - 12, "Fitted correction (logistic)", "anno", "end").style("fill", "var(--slate)");
    }

    for (const c of cal) {
      const cx = x(c.mean_stated_pct);
      const cy = y(c.observed_pct);
      const col = c.small_group ? "var(--gray)" : "var(--oxblood)";
      g.append("line").attr("x1", cx).attr("x2", cx).attr("y1", y(c.ci_low_pct)).attr("y2", y(c.ci_high_pct)).attr("stroke", col).attr("stroke-width", 1.25);
      g.append("line").attr("x1", cx - 4).attr("x2", cx + 4).attr("y1", y(c.ci_low_pct)).attr("y2", y(c.ci_low_pct)).attr("stroke", col);
      g.append("line").attr("x1", cx - 4).attr("x2", cx + 4).attr("y1", y(c.ci_high_pct)).attr("y2", y(c.ci_high_pct)).attr("stroke", col);
      const dot = g
        .append("circle")
        .attr("cx", cx)
        .attr("cy", cy)
        .attr("r", Math.max(4, rScale(c.n)))
        .attr("fill", c.small_group ? "var(--paper-light)" : "rgb(125 41 38 / 0.16)")
        .attr("stroke", col)
        .attr("stroke-width", 1.5)
        .attr("tabindex", 0)
        .attr("aria-label", `Stated ${c.range_pct}%: ${fmt(c.observed_pct)}% had a birth, ${int(c.n)} women`)
        .style("cursor", "pointer");
      g.append("circle").attr("cx", cx).attr("cy", cy).attr("r", 1.6).attr("fill", col).style("pointer-events", "none");
      bindTip(dot.node()!, () => ({
        head: `Stated ${c.range_pct}%`,
        rows: [
          ["Women", int(c.n)],
          ["Had a birth", int(c.births)],
          ["Observed share", `${fmt(c.observed_pct)}%`],
          ["95% interval", `${fmt(c.ci_low_pct)}–${fmt(c.ci_high_pct)}%`],
          ["Mean stated", `${fmt(c.mean_stated_pct)}%`],
        ],
        note: c.small_group ? "Fewer than 50 women: wide interval." : "Wilson 95% interval. Unweighted sample.",
      }));
    }
    const c0 = cal.find((c) => c.range_pct === "0")!;
    const c100 = cal.find((c) => c.range_pct === "100")!;
    if (!narrow) {
      text(g, x(0) + 4, y(c0.observed_pct) + 40, `Said 0%: ${fmt(c0.observed_pct)}% had a birth`, "anno");
      text(g, x(100) - 26, y(c100.observed_pct) + 34, `Said 100%: ${fmt(c100.observed_pct)}% did`, "anno", "end");
      const lx = x(100) + 22;
      text(g, lx, m.t + 10, "Circle area: number of women", "anno-muted");
      [100, 600, 1200].forEach((n, i) => {
        const yy = m.t + 40 + i * 34;
        g.append("circle").attr("cx", lx + 18).attr("cy", yy).attr("r", rScale(n)).attr("fill", "none").attr("stroke", "var(--gray)");
        text(g, lx + 44, yy + 4, int(n), "anno-muted");
      });
      text(g, lx, m.t + 160, "Hollow: under 50 women", "anno-muted");
      text(g, lx, m.t + 180, "Lines: 95% Wilson interval", "anno-muted");
    }

    if (showDist) {
      const top = plotH + 10;
      const hh = distH - 34;
      const maxN = Math.max(...dist.counts.map((c) => c.n));
      const yd = scaleLinear().domain([0, maxN]).range([top + hh, top]);
      text(g, m.l - 4, top - 2, "How women answered: number giving each value", "axis-title");
      for (const c of dist.counts) {
        const bx = x(c.stated_pct);
        const bar = g
          .append("rect")
          .attr("x", bx - 2.5)
          .attr("width", 5)
          .attr("y", yd(c.n))
          .attr("height", yd(0) - yd(c.n))
          .attr("fill", c.stated_pct === 0 || c.stated_pct === 50 || c.stated_pct === 100 ? "var(--oxblood)" : "var(--ink)");
        bindTip(bar.node()!, () => ({
          head: `Answered ${c.stated_pct}%`,
          rows: [
            ["Women", int(c.n)],
            ["Share of 3,404", `${fmt((c.n / dist.n) * 100)}%`],
          ],
        }));
      }
      g.append("line").attr("x1", m.l).attr("x2", x(100)).attr("y1", yd(0)).attr("y2", yd(0)).attr("stroke", "var(--rule)");
      text(
        g,
        m.l,
        top + hh + 22,
        `${fmt(dist.share_pct.at_0_50_or_100)}% answered exactly 0, 50 or 100. ${dist.suppressed.values} rarely used values (${dist.suppressed.n} women) are not shown.`,
        "anno-muted",
      );
    }
  };
  if (tRecal) toggle(tRecal, (on) => ((showRecal = on), draw(width)));
  if (tDist) toggle(tDist, (on) => ((showDist = on), draw(width)));
  onResize(el, draw);
}

const MODEL_LABEL: Record<string, string> = {
  A: "Constant rate for everyone",
  B: "The stated chance, as given",
  C: "Stated chance, corrected",
  D: "Corrected, plus background",
};

export function mountBrier(el: HTMLElement) {
  const models = data.nlsy.heldOut.models;
  const draw = (w: number) => {
    const narrow = w < 560;
    const rowH = narrow ? 58 : 46;
    const m = { t: 30, r: 24, b: 44, l: narrow ? 12 : 230 };
    const height = m.t + models.length * rowH + m.b;
    const x = scaleLinear().domain([0.16, 0.28]).range([m.l, w - m.r]);
    const svg = svgIn(
      el,
      w,
      height,
      "Brier scores on 852 held-out women. Constant rate 0.230; stated chance 0.249; corrected stated chance 0.198; corrected with background characteristics 0.188. Lower is better.",
    );
    const g = svg.append("g");
    gridX(g, x, m.t - 8, height - m.b, [0.16, 0.18, 0.2, 0.22, 0.24, 0.26, 0.28]);
    bottomAxis(g, x, height - m.b + 6, [0.16, 0.2, 0.24, 0.28], (v) => v.toFixed(2));
    text(g, x(0.22), height - 6, narrow ? "Brier score (lower is better)" : "Brier score on unseen households (lower is better)", "axis-title", "middle");
    const base = models.find((mm) => mm.id === "A")!;
    g.append("line").attr("x1", x(base.brier)).attr("x2", x(base.brier)).attr("y1", m.t - 12).attr("y2", height - m.b).attr("stroke", "var(--gray)").attr("stroke-dasharray", "3 3");
    text(g, x(base.brier) + 5, m.t - 14, "baseline", "anno-muted");
    models.forEach((mm, i) => {
      const yy = m.t + i * rowH + rowH / 2 + (narrow ? 10 : 0);
      const col = mm.id === "B" ? "var(--oxblood)" : mm.id === "A" ? "var(--gray)" : "var(--ink)";
      if (narrow) {
        text(g, m.l, yy - 16, `${mm.id}  ${MODEL_LABEL[mm.id]}`, "anno");
      } else {
        text(g, m.l - 14, yy - 2, `${mm.id}  ${MODEL_LABEL[mm.id]}`, "anno", "end");
        text(g, m.l - 14, yy + 14, mm.auc ? `AUC ${mm.auc.toFixed(3)}` : "AUC 0.50 by construction", "anno-muted", "end");
      }
      ciWhisker(g, x(mm.brier_ci[0]), x(mm.brier_ci[1]), yy, col);
      const c = g.append("circle").attr("cx", x(mm.brier)).attr("cy", yy).attr("r", 5.5).attr("fill", col).attr("tabindex", 0).attr("aria-label", `${MODEL_LABEL[mm.id]}: Brier ${mm.brier.toFixed(3)}`);
      bindTip(c.node()!, () => ({
        head: `${mm.id}. ${mm.name}`,
        rows: [
          ["Brier score", mm.brier.toFixed(3)],
          ["95% interval", `${mm.brier_ci[0].toFixed(3)}–${mm.brier_ci[1].toFixed(3)}`],
          ["Skill vs constant", `${fmt(mm.brier_skill_vs_A * 100, 1, true)}%`],
          ["ROC AUC", mm.auc ? mm.auc.toFixed(3) : "0.50 (no ranking)"],
        ],
        note: "Household-cluster bootstrap, 2,000 replicates. 852 held-out women, 305 births.",
      }));
      text(g, x(mm.brier_ci[1]) + 8, yy + 4, mm.brier.toFixed(3), "value").style("font-size", "13px");
    });
  };
  onResize(el, draw);
}
