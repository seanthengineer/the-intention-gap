import { area, line, pointer, scaleLinear } from "d3";
import data from "../../data/site-data.json";
import { bindTip, fmt, hideTip, onResize, pct, showTip, toggle } from "../lib";
import { bottomAxis, figureOf, gridX, gridY, leftAxis, svgIn, text } from "./common";

const observed = data.m11.observed as [number, number][];
const fc = data.m11.forecast;
type FcRow = (typeof fc)[number];

export const METHOD: Record<string, string> = {
  naive: "No change (baseline)",
  mean10: "10-year mean",
  drift10: "10-year drift",
  drift10_damped: "Damped drift",
  converge30: "Converge to 30-year mean",
  ses: "Exponential smoothing",
  holt_damped: "Damped trend (Holt)",
  ar_level: "Autoregressive level",
  ari: "ARIMA",
};

export function mountForecast(el: HTMLElement) {
  const fig = figureOf(el);
  let showMethods = false;
  let showOrigins = false;
  let show77 = false;
  let width = 0;
  const draw = (w: number) => {
    width = w;
    const narrow = w < 640;
    const height = Math.round(Math.min(560, Math.max(340, w * (narrow ? 0.9 : 0.5))));
    const m = { t: 26, r: narrow ? 16 : 190, b: 40, l: 40 };
    const x = scaleLinear().domain([1952, 2040.5]).range([m.l, w - m.r]);
    const y = scaleLinear().domain([0.5, 4]).range([height - m.b, m.t]);
    const svg = svgIn(
      el,
      w,
      height,
      "U.S. period total fertility rate, observed 1953 to 2024 and forecast to 2040 at the 2024 level of 1.593 births per woman. Nominal 80% and 95% historical-error ranges widen to 1.05 to 2.42 and 0.84 to 3.03 by 2040. These ranges failed their calibration check and are not probability intervals.",
    );
    const g = svg.append("g");
    gridY(g, y, m.l, x(2040.5), [1, 1.5, 2, 2.5, 3, 3.5, 4]);
    leftAxis(g, y, m.l - 4, [1, 1.5, 2, 2.5, 3, 3.5, 4], (v) => v.toFixed(1));
    bottomAxis(g, x, height - m.b + 6, narrow ? [1960, 1990, 2020, 2040] : [1960, 1970, 1980, 1990, 2000, 2010, 2020, 2030, 2040], String);
    text(g, m.l - 4, m.t - 10, "Births per woman", "axis-title");

    const band = (lo: keyof FcRow, hi: keyof FcRow) =>
      area<FcRow>()
        .x((d) => x(d.year))
        .y0((d) => y(d[lo] as number))
        .y1((d) => y(d[hi] as number));
    const fcFull = [{ ...fc[0], year: 2024, f: fc[0].f, l80: fc[0].f, u80: fc[0].f, l95: fc[0].f, u95: fc[0].f, s77l80: fc[0].f, s77u80: fc[0].f } as FcRow, ...fc];
    g.append("path").datum(fcFull).attr("fill", "rgb(125 41 38 / 0.09)").attr("d", band("l95", "u95"));
    g.append("path").datum(fcFull).attr("fill", "rgb(125 41 38 / 0.16)").attr("d", band("l80", "u80"));
    if (show77) {
      g.append("path").datum(fcFull).attr("fill", "none").attr("stroke", "var(--slate)").attr("stroke-dasharray", "2 3").attr("stroke-width", 1.4).attr("d", line<FcRow>().x((d) => x(d.year)).y((d) => y(d.s77l80)));
      g.append("path").datum(fcFull).attr("fill", "none").attr("stroke", "var(--slate)").attr("stroke-dasharray", "2 3").attr("stroke-width", 1.4).attr("d", line<FcRow>().x((d) => x(d.year)).y((d) => y(d.s77u80)));
      if (!narrow && !showMethods) text(g, x(2040) + 10, y(fc[fc.length - 1].s77l80) + 4, "80%, errors since 1977", "anno").style("fill", "var(--slate)");
    }
    g.append("line").attr("x1", x(2024.5)).attr("x2", x(2024.5)).attr("y1", y(0.5)).attr("y2", y(4)).attr("stroke", "var(--ink)").attr("stroke-dasharray", "2 3");
    text(g, narrow ? x(2024.5) - 6 : x(2024.5) + 6, y(4) + 12, "forecast from 2025", "anno-muted", narrow ? "end" : "start");

    if (showMethods) {
      const lines = data.m11.methodLines as Record<string, [number, number][]>;
      const ends: { k: string; v: number }[] = [];
      for (const [k, pts] of Object.entries(lines)) {
        if (k === "naive") continue;
        const full: [number, number][] = [[2024, observed[observed.length - 1][1]], ...pts];
        g.append("path").datum(full).attr("fill", "none").attr("stroke", "var(--slate)").attr("stroke-width", 1.1).attr("opacity", 0.75).attr("d", line<[number, number]>().x((d) => x(d[0])).y((d) => y(d[1])));
        ends.push({ k, v: pts[pts.length - 1][1] });
      }
      if (!narrow) {
        if (show77) ends.push({ k: "s77", v: fc[fc.length - 1].s77l80 });
        ends.sort((a, b) => b.v - a.v);
        let lastY = -Infinity;
        for (const e of ends) {
          let yy = y(e.v) + 4;
          if (yy - lastY < 13) yy = lastY + 13;
          lastY = yy;
          text(g, x(2040) + 10, yy, e.k === "s77" ? "80% range, errors since 1977" : `${METHOD[e.k]} ${e.v.toFixed(2)}`, "anno-muted").style("fill", "var(--slate)").style("font-size", "11px");
        }
      }
    }
    if (showOrigins) {
      for (const [origin, v] of data.m11.originSens as [number, number][]) {
        g.append("line").attr("x1", x(origin)).attr("x2", x(2040)).attr("y1", y(v)).attr("y2", y(v)).attr("stroke", "var(--ochre)").attr("stroke-width", 1).attr("opacity", 0.8);
        g.append("circle").attr("cx", x(origin)).attr("cy", y(v)).attr("r", 2.5).attr("fill", "var(--ochre)");
      }
      const first = (data.m11.originSens as [number, number][])[0];
      if (!narrow) text(g, x(2040) + 10, y(first[1]) + 4, `Made in ${first[0]}: ${first[1].toFixed(2)}`, "anno").style("fill", "var(--ochre)");
    }

    g.append("path")
      .datum(observed)
      .attr("fill", "none")
      .attr("stroke", "var(--ink)")
      .attr("stroke-width", 1.8)
      .attr("d", line<[number, number]>().x((d) => x(d[0])).y((d) => y(d[1])));
    const last = fc[fc.length - 1];
    g.append("path").attr("d", `M${x(2024)},${y(last.f)}H${x(2040)}`).attr("stroke", "var(--oxblood)").attr("stroke-width", 2).attr("stroke-dasharray", "6 4").attr("fill", "none");
    if (!narrow) {
      const lx = x(2040) + 10;
      if (!showMethods) {
        text(g, lx, y(last.f) + 4, `No change: ${last.f.toFixed(3)}`, "anno").style("fill", "var(--oxblood)");
        text(g, lx, y(last.u80) + 4, `80% range to ${last.u80.toFixed(2)}`, "anno-muted");
        text(g, lx, y(last.l80) + 4, `80% range to ${last.l80.toFixed(2)}`, "anno-muted");
        text(g, lx, y(last.u95) + 4, `95% range to ${last.u95.toFixed(2)}`, "anno-muted");
      }
      const peak = observed.reduce((a, b) => (b[1] > a[1] ? b : a));
      text(g, x(peak[0]) + 8, y(peak[1]) - 4, `${peak[0]} peak ${peak[1].toFixed(2)}`, "anno");
    }

    const guide = g.append("line").attr("y1", y(0.5)).attr("y2", y(4)).attr("stroke", "var(--ink)").attr("opacity", 0);
    const marker = g.append("circle").attr("r", 4).attr("fill", "var(--paper-light)").attr("stroke", "var(--ink)").attr("stroke-width", 1.5).attr("opacity", 0);
    const hit = g.append("rect").attr("x", m.l).attr("y", m.t).attr("width", x(2040.5) - m.l).attr("height", y(0.5) - m.t).attr("fill", "transparent").style("cursor", "crosshair");
    const at = (yr: number) => {
      const year = Math.round(Math.min(2040, Math.max(1953, yr)));
      const o = observed.find(([yy]) => yy === year);
      const f = fc.find((r) => r.year === year);
      return { year, o, f };
    };
    hit.on("pointermove", (ev: PointerEvent) => {
      const [px] = pointer(ev);
      const { year, o, f } = at(x.invert(px));
      const v = o ? o[1] : f!.f;
      guide.attr("x1", x(year)).attr("x2", x(year)).attr("opacity", 0.35);
      marker.attr("cx", x(year)).attr("cy", y(v)).attr("opacity", 1);
      if (o) showTip({ head: `${year}, observed`, rows: [["Total fertility rate", o[1].toFixed(3)]], note: "Human Fertility Database." }, ev.clientX, ev.clientY);
      else
        showTip(
          {
            head: `${year}, forecast (${f!.h} ${f!.h === 1 ? "year" : "years"} ahead)`,
            rows: [
              ["No-change forecast", f!.f.toFixed(3)],
              ["80% historical-error range", `${f!.l80.toFixed(2)}–${f!.u80.toFixed(2)}`],
              ["95% historical-error range", `${f!.l95.toFixed(2)}–${f!.u95.toFixed(2)}`],
            ],
            note: "Ranges built from past forecast errors. They failed the calibration check: not probabilities.",
          },
          ev.clientX,
          ev.clientY,
        );
    });
    hit.on("pointerleave", () => {
      guide.attr("opacity", 0);
      marker.attr("opacity", 0);
      hideTip();
    });
  };
  const bind = (k: string, fn: (on: boolean) => void) => {
    const b = fig.querySelector<HTMLButtonElement>(`[data-toggle='${k}']`);
    if (b) toggle(b, (on) => (fn(on), draw(width)));
  };
  bind("methods", (on) => (showMethods = on));
  bind("origins", (on) => (showOrigins = on));
  bind("since1977", (on) => (show77 = on));
  onResize(el, draw);
}

export function mountBacktest(el: HTMLElement) {
  const draw = (w: number) => {
    const narrow = w < 640;
    const sel = [...data.m11.selection].sort((a, b) => a.R - b.R);
    const rowH = narrow ? 50 : 36;
    const m = { t: narrow ? 84 : 68, r: 24, b: 48, l: narrow ? 12 : 240 };
    const height = m.t + sel.length * rowH + m.b;
    const x = scaleLinear().domain([0.75, 2.05]).range([m.l, w - m.r]);
    const svg = svgIn(el, w, height, "Mean absolute error of nine forecasting methods relative to the no-change baseline at 5, 10 and 15 years ahead. A value below 0.90 at every horizon was needed to replace the baseline. ARIMA came closest overall at 0.942; no method qualified.");
    const g = svg.append("g");
    const ticks = [0.8, 0.9, 1, 1.2, 1.4, 1.6, 1.8, 2];
    gridX(g, x, m.t - 8, height - m.b, ticks);
    bottomAxis(g, x, height - m.b + 6, ticks, (v) => v.toFixed(1));
    text(g, x(1.4), height - 8, narrow ? "Error vs no change (below 1 = better)" : "Error relative to no change (below 1 = better)", "axis-title", "middle");
    g.append("rect").attr("x", x(0.75)).attr("width", x(0.9) - x(0.75)).attr("y", m.t - 14).attr("height", height - m.b - m.t + 14).attr("fill", "rgb(125 41 38 / 0.07)");
    g.append("line").attr("x1", x(0.9)).attr("x2", x(0.9)).attr("y1", m.t - 14).attr("y2", height - m.b).attr("stroke", "var(--oxblood)").attr("stroke-dasharray", "4 3");
    text(g, narrow ? x(0.75) : x(0.9) - 4, narrow ? m.t - 34 : m.t - 20, "needed: average 0.90", "anno", narrow ? "start" : "end").style("fill", "var(--oxblood)");
    g.append("line").attr("x1", x(1)).attr("x2", x(1)).attr("y1", m.t - 14).attr("y2", height - m.b).attr("stroke", "var(--ink)");
    text(g, x(1) + 4, m.t - 20, "no change", "anno-muted");
    const shapes: Record<string, (gg: typeof g, cx: number, cy: number) => void> = {
      h5: (gg, cx, cy) => void gg.append("circle").attr("cx", cx).attr("cy", cy).attr("r", 4.5).attr("fill", "var(--ink)"),
      h10: (gg, cx, cy) => void gg.append("rect").attr("x", cx - 4).attr("y", cy - 4).attr("width", 8).attr("height", 8).attr("fill", "var(--paper-light)").attr("stroke", "var(--ink)").attr("stroke-width", 1.4),
      h15: (gg, cx, cy) => void gg.append("path").attr("d", `M${cx},${cy - 5}L${cx + 5},${cy + 4}L${cx - 5},${cy + 4}Z`).attr("fill", "var(--gray)"),
    };
    sel.forEach((s, i) => {
      const yy = m.t + i * rowH + rowH / 2 + (narrow ? 8 : 0);
      (narrow ? text(g, m.l, yy - 14, METHOD[s.method], s.method === "naive" ? "anno" : "anno-muted") : text(g, m.l - 14, yy + 4, METHOD[s.method], s.method === "naive" ? "anno" : "anno-muted", "end")).style("fill", s.method === "naive" ? "var(--oxblood)" : null);
      const vals = [s.h5, s.h10, s.h15];
      g.append("line").attr("x1", x(Math.min(...vals))).attr("x2", x(Math.max(...vals))).attr("y1", yy).attr("y2", yy).attr("stroke", "var(--rule)").attr("stroke-width", 2);
      (["h5", "h10", "h15"] as const).forEach((h) => shapes[h](g, x(Math.min(2.05, s[h])), yy));
      g.append("line").attr("x1", x(s.R)).attr("x2", x(s.R)).attr("y1", yy - 9).attr("y2", yy + 9).attr("stroke", "var(--oxblood)").attr("stroke-width", 2.5);
      const hit = g.append("rect").attr("x", m.l).attr("y", yy - rowH / 2).attr("width", x(2.05) - m.l).attr("height", rowH).attr("fill", "transparent").attr("tabindex", 0).attr("aria-label", `${METHOD[s.method]}: overall ${s.R.toFixed(3)}`);
      bindTip(hit.node()!, () => ({
        head: METHOD[s.method],
        rows: [
          ["5 years ahead", s.h5.toFixed(3)],
          ["10 years ahead", s.h10.toFixed(3)],
          ["15 years ahead", s.h15.toFixed(3)],
          ["Overall ratio", s.R.toFixed(3)],
          ["Met the rule", s.selected ? "baseline" : "no"],
        ],
        note: "Mean absolute error relative to no change across pseudo-real-time origins 1952–2023.",
      }));
    });
    const ly = 12;
    const legend: [keyof typeof shapes, string][] = [
      ["h5", "5 years ahead"],
      ["h10", "10 years"],
      ["h15", "15 years"],
    ];
    let lx = m.l;
    g.append("line").attr("x1", lx + 2).attr("x2", lx + 2).attr("y1", ly - 7).attr("y2", ly + 7).attr("stroke", "var(--oxblood)").attr("stroke-width", 2.5);
    const tr = text(g, lx + 12, ly + 4, "average", "anno-muted");
    lx += 12 + (tr.node()!.getComputedTextLength?.() ?? 60) + 20;
    let rowY = ly;
    legend.forEach(([k, label]) => {
      if (lx + 110 > w) {
        lx = m.l;
        rowY += 20;
      }
      shapes[k](g, lx + 5, rowY);
      const t = text(g, lx + 16, rowY + 4, label, "anno-muted");
      lx += 16 + (t.node()!.getComputedTextLength?.() ?? 80) + 20;
    });
  };
  onResize(el, draw);
}

const INTERVAL: Record<string, { label: string; color: string; dash?: string }> = {
  historical_error: { label: "Past errors since 1952 (published)", color: "var(--oxblood)" },
  since_1977: { label: "Past errors since 1977", color: "var(--slate)", dash: "5 3" },
  model_based: { label: "Model-based (random walk)", color: "var(--gray)", dash: "2 3" },
};

export function mountCoverage(el: HTMLElement) {
  const draw = (w: number) => {
    const narrow = w < 640;
    const height = Math.round(Math.min(380, Math.max(280, w * 0.42)));
    const m = { t: 24, r: narrow ? 16 : 230, b: 44, l: 44 };
    const x = scaleLinear().domain([1, 16]).range([m.l, w - m.r]);
    const y = scaleLinear().domain([0, 1]).range([height - m.b, m.t]);
    const svg = svgIn(el, w, height, "Share of later outcomes that fell inside nominal 80% intervals, by years ahead. Intervals from errors since 1952 over-cover, near 100% beyond 8 years. Intervals from errors since 1977 under-cover badly at long horizons. A model-based spread falls to about 60%. None stays within the 65 to 95% band that the protocol required.");
    const g = svg.append("g");
    g.append("rect").attr("x", x(1)).attr("width", x(16) - x(1)).attr("y", y(0.95)).attr("height", y(0.65) - y(0.95)).attr("fill", "rgb(206 197 185 / 0.35)");
    gridY(g, y, m.l, x(16), [0.2, 0.4, 0.6, 0.8, 1]);
    leftAxis(g, y, m.l - 4, [0, 0.2, 0.4, 0.6, 0.8, 1], (v) => `${Math.round(v * 100)}%`);
    bottomAxis(g, x, height - m.b + 6, [1, 4, 8, 12, 16], String);
    text(g, x(8.5), height - 8, "Years ahead", "axis-title", "middle");
    text(g, m.l - 4, m.t - 10, "Outcomes inside the nominal 80% interval", "axis-title");
    g.append("line").attr("x1", x(1)).attr("x2", x(16)).attr("y1", y(0.8)).attr("y2", y(0.8)).attr("stroke", "var(--ink)").attr("stroke-dasharray", "1 3");
    text(g, x(16) - 2, y(0.65) - 6, "required band 65–95%", "anno-muted", "end");
    const rows = data.m11.calibByH;
    for (const [k, spec] of Object.entries(INTERVAL)) {
      const pts = rows.filter((r) => r.interval === k).sort((a, b) => a.h - b.h);
      g.append("path")
        .datum(pts)
        .attr("fill", "none")
        .attr("stroke", spec.color)
        .attr("stroke-width", 2)
        .attr("stroke-dasharray", spec.dash ?? null)
        .attr("d", line<(typeof pts)[number]>().x((d) => x(d.h)).y((d) => y(d.c80)));
      for (const p of pts) {
        const c = g.append("circle").attr("cx", x(p.h)).attr("cy", y(p.c80)).attr("r", 3).attr("fill", spec.color).attr("tabindex", 0).attr("aria-label", `${spec.label}, ${p.h} years ahead: ${pct(p.c80, 0)}`);
        bindTip(c.node()!, () => ({
          head: `${spec.label}`,
          rows: [
            ["Years ahead", String(p.h)],
            ["Inside 80% interval", pct(p.c80, 0)],
            ["Inside 95% interval", pct(p.c95, 0)],
            ["Forecast origins", String(p.origins)],
          ],
          note: "Pseudo-real time: only errors observable at each origin were used to build its interval.",
        }));
      }
      if (!narrow) {
        const lastP = pts[pts.length - 1];
        text(g, x(16) + 10, y(lastP.c80) + 4, spec.label, "anno").style("fill", spec.color);
      }
    }
  };
  onResize(el, draw);
}

export function mountCohorts(el: HTMLElement) {
  const fig = figureOf(el);
  const range = fig.querySelector<HTMLInputElement>("input[type='range']");
  const out = fig.querySelector<HTMLElement>("[data-cohort-card]");
  const traj = data.m11.trajectories;
  const ends = data.m11.endpoints;
  const obs = data.m11.observability;
  let cohort = 1995;
  let width = 0;
  const draw = (w: number) => {
    width = w;
    const narrow = w < 640;
    const height = Math.round(Math.min(500, Math.max(320, w * (narrow ? 0.9 : 0.5))));
    const m = { t: 26, r: narrow ? 30 : 70, b: 42, l: 44 };
    const x = scaleLinear().domain([12, 45.5]).range([m.l, w - m.r]);
    const y = scaleLinear().domain([0, 2.1]).range([height - m.b, m.t]);
    const svg = svgIn(el, w, height, `Cumulative births per woman by age for Generation Z birth cohorts, observed to 2024 and projected to the end of 2040 if 2024 rates persist. Selected: born ${cohort}.`);
    const g = svg.append("g");
    gridY(g, y, m.l, x(45.5), [0.5, 1, 1.5, 2]);
    leftAxis(g, y, m.l - 4, [0, 0.5, 1, 1.5, 2], (v) => v.toFixed(1));
    bottomAxis(g, x, height - m.b + 6, [15, 20, 25, 30, 35, 40, 45], String);
    text(g, x(28.5), height - 8, "Age reached during the year", "axis-title", "middle");
    text(g, m.l - 4, m.t - 10, "Cumulative births per woman", "axis-title");
    const cohorts = [...new Set(traj.map((t) => t.c))].sort();
    for (const c of cohorts) {
      if (c === cohort) continue;
      const pts = traj.filter((t) => t.c === c);
      g.append("path").datum(pts).attr("fill", "none").attr("stroke", "var(--rule)").attr("stroke-width", 1).attr("d", line<(typeof pts)[number]>().x((d) => x(d.age)).y((d) => y(d.cum)));
    }
    const sel = traj.filter((t) => t.c === cohort);
    const proj = sel.filter((t) => t.seg === "projected");
    const obsPts = sel.filter((t) => t.seg === "observed");
    if (proj.length) {
      const join = obsPts.length ? [{ ...obsPts[obsPts.length - 1], l80: obsPts[obsPts.length - 1].cum, u80: obsPts[obsPts.length - 1].cum }, ...proj] : proj;
      g.append("path").datum(join).attr("fill", "rgb(125 41 38 / 0.14)").attr("d", area<(typeof join)[number]>().x((d) => x(d.age)).y0((d) => y(d.l80 ?? d.cum)).y1((d) => y(d.u80 ?? d.cum)));
      g.append("path").datum(join).attr("fill", "none").attr("stroke", "var(--oxblood)").attr("stroke-width", 2).attr("stroke-dasharray", "6 4").attr("d", line<(typeof join)[number]>().x((d) => x(d.age)).y((d) => y(d.cum)));
    }
    if (obsPts.length) g.append("path").datum(obsPts).attr("fill", "none").attr("stroke", "var(--ink)").attr("stroke-width", 2.2).attr("d", line<(typeof obsPts)[number]>().x((d) => x(d.age)).y((d) => y(d.cum)));
    const e = ends.find((d) => d.c === cohort)!;
    g.append("circle").attr("cx", x(e.age2040)).attr("cy", y(e.p2040)).attr("r", 4.5).attr("fill", "var(--oxblood)");
    text(g, x(e.age2040) + (e.age2040 > 40 ? -8 : 8), y(e.p2040) - 10, `${e.p2040.toFixed(2)} by end-2040`, "anno", e.age2040 > 40 ? "end" : "start").style("fill", "var(--oxblood)");
    if (obsPts.length) {
      const lo = obsPts[obsPts.length - 1];
      g.append("circle").attr("cx", x(lo.age)).attr("cy", y(lo.cum)).attr("r", 3.5).attr("fill", "var(--ink)");
      text(g, x(lo.age) - 8, y(lo.cum) + 4, `${lo.cum.toFixed(2)} by 2024`, "anno", "end");
    }
    const guide = g.append("line").attr("y1", y(0)).attr("y2", y(2.1)).attr("stroke", "var(--ink)").attr("opacity", 0);
    const hit = g.append("rect").attr("x", m.l).attr("y", m.t).attr("width", x(45.5) - m.l).attr("height", y(0) - m.t).attr("fill", "transparent").style("cursor", "crosshair");
    hit.on("pointermove", (ev: PointerEvent) => {
      const [px] = pointer(ev);
      const age = Math.round(x.invert(px));
      const pt = sel.find((t) => t.age === age);
      if (!pt) return hideTip();
      guide.attr("x1", x(age)).attr("x2", x(age)).attr("opacity", 0.3);
      showTip(
        {
          head: `Born ${cohort}, age ${age} in ${pt.y}`,
          rows: [
            [pt.seg === "observed" ? "Observed, cumulative" : "Projected, cumulative", pt.cum.toFixed(3)],
            ...(pt.seg === "projected" && pt.l80 !== null ? ([["80% historical-error range", `${pt.l80.toFixed(2)}–${pt.u80!.toFixed(2)}`]] as [string, string][]) : []),
          ],
          note: pt.seg === "projected" ? "If 2024 age-specific rates persist. Range from past errors; not a probability." : "Human Fertility Database.",
        },
        ev.clientX,
        ev.clientY,
      );
    });
    hit.on("pointerleave", () => (guide.attr("opacity", 0), hideTip()));
    if (out) {
      const o = obs.find((d) => d.c === cohort)!;
      out.innerHTML = `
        <div><dt>Born</dt><dd>${cohort}</dd></div>
        <div><dt>Age in 2024</dt><dd>${o.age2024}</dd></div>
        <div><dt>Births per woman by 2024</dt><dd>${e.obs2024.toFixed(2)} <span>observed</span></dd></div>
        <div><dt>By the end of 2040</dt><dd>${e.p2040.toFixed(2)} <span>projected; 80% range ${e.l80.toFixed(2)}–${e.u80.toFixed(2)}</span></dd></div>
        <div><dt>Age reached in 2040</dt><dd>${e.age2040}</dd></div>
        <div><dt>Status by 2040</dt><dd class="status">${e.completion}</dd></div>
        <div class="ledger" aria-label="Ages observed to ${o.age2024}, projected to ${o.age2040}, not covered after">${ledger(o.age2024, o.age2040)}</div>`;
    }
  };
  const ledger = (a24: number, a40: number) => {
    const cells: string[] = [];
    for (let a = 12; a <= 55; a++) {
      const cls = a <= a24 ? "o" : a <= a40 ? "p" : "u";
      cells.push(`<i class="${cls}" title="age ${a}"></i>`);
    }
    return `<div class="cells">${cells.join("")}</div><div class="ledger-key"><span class="o">observed to age ${a24}</span><span class="p">projected to ${a40}</span><span class="u">beyond 2040</span></div>`;
  };
  if (range)
    range.addEventListener("input", () => {
      cohort = Number(range.value);
      const lab = fig.querySelector<HTMLElement>("[data-cohort-label]");
      if (lab) lab.textContent = String(cohort);
      draw(width);
    });
  onResize(el, draw);
}
