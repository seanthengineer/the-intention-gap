import { scaleLinear } from "d3";
import data from "../../data/site-data.json";
import { bindTip, onResize } from "../lib";
import { bottomAxis, gridX, gridY, leftAxis, svgIn, text } from "./common";

type Row = Record<string, string>;
const rows = data.final.populationMap as Row[];
const yearsOf = (s: string) => [...s.matchAll(/(\d{4})-(\d{4})/g)].map((m) => [Number(m[1]), Number(m[2])] as [number, number]);
const byChapter = (c: string) => rows.find((r) => r.chapter === c)!;

export function mountEvidence(el: HTMLElement) {
  const nlsy = byChapter("M01-M08");
  const nsfg = byChapter("M09");
  const m10 = byChapter("M10");
  const m11 = byChapter("M11");
  const nlsyYears = yearsOf(nlsy.observation_years)[0];
  const nlsyCoh = yearsOf(nlsy.birth_cohorts)[0];
  const nsfgYears = yearsOf(nsfg.observation_years)[0];
  const nsfgCoh = yearsOf(nsfg.birth_cohorts)[0];
  const m10Periods = yearsOf(m10.observation_years);
  const m10Ages = (m10.ages.match(/(\d+)-(\d+) and (\d+)-(\d+)/) ?? []).slice(1).map(Number);
  const genz = yearsOf(m11.birth_cohorts)[0];
  const projected = yearsOf(m11.observation_years).find(([a]) => a > 2024)!;

  const draw = (width: number) => {
    const narrow = width < 640;
    const height = Math.round(Math.min(520, Math.max(340, width * 0.5)));
    const m = { t: 20, r: narrow ? 12 : 170, b: 40, l: 52 };
    const x = scaleLinear().domain([2005, 2041]).range([m.l, width - m.r]);
    const y = scaleLinear().domain([1974, 2014]).range([height - m.b, m.t]);
    const svg = svgIn(
      el,
      width,
      height,
      "Calendar year by birth cohort. Generation Z, born 1995 to 2012, is a horizontal band. The NLSY97 study covers women born 1980 to 1984, observed 2009 to 2023. The NSFG covers people born about 1995 to 2005, interviewed 2022 to 2023. The housing study covers ages 20 to 29 in 2014 to 2024. The forecast projects Generation Z cohorts from 2025 to 2040. No block follows Generation Z from stated desire to completed fertility.",
    );
    const g = svg.append("g");
    const defs = svg.append("defs");
    const hatch = defs.append("pattern").attr("id", "hatch").attr("width", 6).attr("height", 6).attr("patternUnits", "userSpaceOnUse").attr("patternTransform", "rotate(45)");
    hatch.append("line").attr("x1", 0).attr("x2", 0).attr("y1", 0).attr("y2", 6).attr("stroke", "var(--oxblood)").attr("stroke-width", 1.3);
    defs.append("clipPath").attr("id", "ev-clip").append("rect").attr("x", m.l).attr("y", m.t).attr("width", x(2041) - m.l).attr("height", y(1974) - m.t);

    gridY(g, y, m.l, x(2041), [1980, 1990, 2000, 2010]);
    gridX(g, x, m.t, y(1974), [2010, 2020, 2030, 2040]);
    leftAxis(g, y, m.l - 4, [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010], String);
    bottomAxis(g, x, y(1974) + 4, [2005, 2010, 2015, 2020, 2025, 2030, 2035, 2040], String);
    text(g, m.l - 4, height - 6, "Calendar year", "axis-title", "start").attr("x", x(2041)).attr("text-anchor", "end");
    text(g, 0, m.t - 6, "Birth cohort", "axis-title");

    const plot = g.append("g").attr("clip-path", "url(#ev-clip)");
    plot
      .append("rect")
      .attr("x", m.l)
      .attr("width", x(2041) - m.l)
      .attr("y", y(genz[1] + 1))
      .attr("height", y(genz[0]) - y(genz[1] + 1))
      .attr("fill", "rgb(206 197 185 / 0.35)");
    text(plot, m.l + 8, y(genz[1] + 1) + 16, "Generation Z, born 1995–2012", "anno-muted");

    for (const age of [20, 30, 45]) {
      plot
        .append("line")
        .attr("x1", x(2005))
        .attr("y1", y(2005 - age))
        .attr("x2", x(2041))
        .attr("y2", y(2041 - age))
        .attr("stroke", "var(--rule)")
        .attr("stroke-dasharray", "2 3");
      const lx = 2041 - 1;
      if (lx - age > 1975 && lx - age < 2013) text(plot, x(lx) - 4, y(lx - age) - 5, `age ${age}`, "anno-muted", "end");
    }

    const block = (yr: [number, number], coh: [number, number], fill: string, stroke: string, row: Row, label: string, note: string) => {
      const r = plot
        .append("rect")
        .attr("x", x(yr[0]))
        .attr("width", x(yr[1] + 1) - x(yr[0]))
        .attr("y", y(coh[1] + 1))
        .attr("height", y(coh[0]) - y(coh[1] + 1))
        .attr("fill", fill)
        .attr("stroke", stroke)
        .attr("stroke-width", 1)
        .attr("tabindex", 0)
        .attr("aria-label", `${label}: ${note}`)
        .style("cursor", "pointer");
      bindTip(r.node()!, () => tip(row, label, note));
      return r;
    };
    const tip = (row: Row, label: string, note: string) => ({
      head: label,
      rows: [
        ["Source", row.data_source.replace(/ \(.*\)$/, "")],
        ["Design", row.design.split(";")[0]],
        ["Years", row.observation_years],
        ["Ages", row.ages],
        ["Cohorts", row.birth_cohorts.replace(/ \(.*\)$/, "")],
      ] as [string, string][],
      note,
    });

    block(nlsyYears, nlsyCoh, "rgb(41 41 41 / 0.82)", "var(--ink)", nlsy, "Ch. 1 NLSY97", "Women born 1980–84, observed from 2009–10: expectations, then births.");
    block(nsfgYears, nsfgCoh, "var(--oxblood)", "var(--oxblood)", nsfg, "Ch. 2 NSFG 2022–23", "One interview of the oldest part of Generation Z: stated desire and intention.");
    block([projected[0], projected[1]], genz, "url(#hatch)", "var(--oxblood)", m11, "Ch. 4 projection to 2040", "Generation Z cohorts projected if 2024 rates persist. Not observed.");

    const lo = Math.min(...m10Ages);
    const hi = Math.max(...m10Ages);
    for (const [a, b] of m10Periods) {
      const poly = [
        [a, a - lo],
        [b + 1, b + 1 - lo],
        [b + 1, b + 1 - hi - 1],
        [a, a - hi - 1],
      ];
      const p = plot
        .append("path")
        .attr("d", "M" + poly.map(([px, py]) => `${x(px)},${y(py)}`).join("L") + "Z")
        .attr("fill", "rgb(63 99 131 / 0.22)")
        .attr("stroke", "var(--slate)")
        .attr("tabindex", 0)
        .attr("aria-label", "Chapter 3 housing panel: women aged 20 to 29 in each year; different cohorts each year.")
        .style("cursor", "pointer");
      bindTip(p.node()!, () => tip(m10, "Ch. 3 state panel", "Ages 20–29 each year: a different set of cohorts every year. An ecological design, not a cohort study."));
    }

    if (!narrow) {
      const lx = x(2041) + 14;
      const items: [string, string, string][] = [
        ["Ch. 1 Expectations", "rgb(41 41 41 / 0.82)", "NLSY97, born 1980–84"],
        ["Ch. 2 Intentions", "var(--oxblood)", "NSFG, one interview"],
        ["Ch. 3 Housing", "rgb(63 99 131 / 0.35)", "ages 20–29, state panel"],
        ["Ch. 4 Projection", "url(#hatch)", "Gen Z cohorts, 2025–2040"],
      ];
      items.forEach(([label, fill, sub], i) => {
        const yy = m.t + 14 + i * 48;
        g.append("rect").attr("x", lx).attr("y", yy - 10).attr("width", 12).attr("height", 12).attr("fill", fill).attr("stroke", fill.startsWith("url") ? "var(--oxblood)" : "none");
        text(g, lx + 20, yy, label, "anno");
        text(g, lx + 20, yy + 16, sub, "anno-muted");
      });
    }
  };
  onResize(el, draw);
}
