import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { axisBottom, axisLeft, line, scaleLinear, select } from "d3";
import data from "../data/site-data.json";
import geo from "../data/geo.json";
import { clamp, fmt, ramp, reducedMotion, rng } from "./lib";
import { Field, type Formation, formation, GRAY, INK, matchByX, OXBLOOD, orderBy, PALE, scatter, type Segment } from "./particles";
import { crowdFormation } from "./people";

gsap.registerPlugin(ScrollTrigger);

const observed = data.m11.observed as [number, number][];
const forecast = data.m11.forecast;

interface StageSpec {
  track: HTMLElement;
  canvas: HTMLCanvasElement;
  n: number;
  build: (field: Field, w: number, h: number) => void;
  overlay: (p: number) => void;
  discrete?: (p: number) => number;
}

function runStage(spec: StageSpec) {
  const field = new Field(spec.canvas, spec.n);
  const reduce = reducedMotion();
  let target = 0;
  let current = 0;
  let frame = 0;
  const draw = () => {
    field.render(current);
    spec.overlay(current);
  };
  const tick = () => {
    const diff = target - current;
    if (Math.abs(diff) < 0.0008) {
      current = target;
      draw();
      frame = 0;
      return;
    }
    current += diff * 0.2;
    draw();
    frame = requestAnimationFrame(tick);
  };
  const setTarget = (p: number) => {
    target = reduce && spec.discrete ? spec.discrete(p) : p;
    if (reduce) {
      current = target;
      draw();
      return;
    }
    if (!frame) frame = requestAnimationFrame(tick);
  };
  const rebuild = () => {
    field.resize();
    spec.build(field, field.width, field.height);
    draw();
  };
  rebuild();
  ScrollTrigger.create({
    trigger: spec.track,
    start: "top top",
    end: "bottom bottom",
    onUpdate: (self) => setTarget(self.progress),
    onRefresh: (self) => setTarget(self.progress),
  });
  let timer = 0;
  let lastW = window.innerWidth;
  window.addEventListener("resize", () => {
    clearTimeout(timer);
    timer = window.setTimeout(() => {
      if (Math.abs(window.innerWidth - lastW) < 2 && field.height > 0) {
        const r = spec.canvas.getBoundingClientRect();
        if (Math.abs(r.height - field.height) < 120) return;
      }
      lastW = window.innerWidth;
      rebuild();
      ScrollTrigger.refresh();
    }, 180);
  });
}

function relRect(el: Element, stage: Element) {
  const a = el.getBoundingClientRect();
  const b = stage.getBoundingClientRect();
  return { x: a.left - b.left, y: a.top - b.top, w: a.width, h: a.height };
}

function usFormation(n: number, cx: number, cy: number, maxW: number, maxH: number, alpha = 0.9, color = INK, radius = 0.36): Formation {
  const f = formation(n);
  const s = Math.min(maxW / geo.width, maxH / geo.height);
  const ox = cx - (geo.width * s) / 2;
  const oy = cy - (geo.height * s) / 2;
  const dots = geo.dots as [number, number, string][];
  for (let i = 0; i < n; i++) {
    const d = dots[i % dots.length];
    f.x[i] = ox + d[0] * s;
    f.y[i] = oy + d[1] * s;
    f.r[i] = Math.max(0.7, geo.step * s * radius);
    f.a[i] = i < dots.length ? alpha : 0;
    f.c[i] = color;
  }
  return f;
}

function unitColumns(
  f: Formation,
  start: number,
  x: (v: number) => number,
  y: (v: number) => number,
  ox: number,
  oy: number,
  size: number,
) {
  let i = start;
  for (const [year, tfr] of observed) {
    const count = Math.round(tfr * 10);
    for (let k = 0; k < count; k++) {
      f.x[i] = ox + x(year);
      f.y[i] = oy + y((k + 0.5) / 10);
      f.r[i] = size;
      f.a[i] = 0.88;
      f.c[i] = year === 2024 ? OXBLOOD : INK;
      i++;
    }
  }
  return i;
}

const unitCount = observed.reduce((s, [, v]) => s + Math.round(v * 10), 0);

function heroScales(width: number) {
  const narrow = width < 520;
  const height = Math.round(clamp(width * 0.66, 220, 430));
  const m = { t: 30, r: narrow ? 74 : 72, b: 30, l: 34 };
  const x = scaleLinear().domain([1951.5, 2025.5]).range([m.l, width - m.r]);
  const y = scaleLinear().domain([0, 4]).range([height - m.b, m.t]);
  return { x, y, height, m };
}

function drawHeroChart(el: HTMLElement) {
  const width = el.clientWidth;
  const { x, y, height } = heroScales(width);
  select(el).selectAll("svg").remove();
  const svg = select(el)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("height", height)
    .attr("role", "img")
    .attr(
      "aria-label",
      "U.S. period total fertility rate, 1953 to 2024. It rose to a peak of 3.74 births per woman in 1957 and fell to 1.59 in 2024.",
    );
  const g = svg.append("g");
  g.append("g")
    .selectAll("line")
    .data([1, 2, 3, 4])
    .join("line")
    .attr("class", "grid-line")
    .attr("x1", x.range()[0])
    .attr("x2", x.range()[1])
    .attr("y1", (d) => y(d))
    .attr("y2", (d) => y(d));
  g.append("g")
    .attr("class", "axis")
    .attr("transform", `translate(${x.range()[0] - 8},0)`)
    .call(axisLeft(y).tickValues([0, 1, 2, 3, 4]).tickSize(0).tickFormat((d) => String(d)))
    .call((s) => s.select(".domain").remove());
  g.append("g")
    .attr("class", "axis")
    .attr("transform", `translate(0,${y(0) + 6})`)
    .call(axisBottom(x).tickValues([1960, 1980, 2000, 2020]).tickSize(0).tickFormat((d) => String(d)))
    .call((s) => s.select(".domain").remove());
  g.append("text").attr("class", "axis-title").attr("x", x.range()[0] - 8).attr("y", y(4) - 14).text("Births per woman");
  g.append("path")
    .datum(observed)
    .attr("fill", "none")
    .attr("stroke", "var(--ink)")
    .attr("stroke-width", 1.25)
    .attr("d", line<[number, number]>().x((d) => x(d[0])).y((d) => y(d[1])));
  const peak = observed.reduce((a, b) => (b[1] > a[1] ? b : a));
  const last = observed[observed.length - 1];
  g.append("text").attr("class", "anno").attr("x", x(peak[0]) + 8).attr("y", y(peak[1]) - 6).text(`${peak[0]}: ${fmt(peak[1], 2)}`);
  g.append("text")
    .attr("class", "anno")
    .attr("x", x(last[0]) + 7)
    .attr("y", y(last[1]) + 4)
    .attr("fill", "var(--oxblood)")
    .style("fill", "var(--oxblood)")
    .text(`${last[0]}: ${fmt(last[1], 2)}`);
}

export function initOverview() {
  const track = document.getElementById("stage-overview");
  if (!track) return;
  const stage = track.querySelector<HTMLElement>(".stage")!;
  const chartEl = document.getElementById("hero-chart")!;
  const heroText = document.getElementById("hero-text")!;
  const statement = document.getElementById("crowd-statement")!;
  const n = unitCount + geo.dots.length;
  runStage({
    track,
    canvas: stage.querySelector("canvas")!,
    n,
    build(field, w, h) {
      drawHeroChart(chartEl);
      const { x, y } = heroScales(chartEl.clientWidth);
      const rect = relRect(chartEl, stage);
      const hero = formation(n);
      const colW = x(1954) - x(1953);
      const rowH = y(0) - y(0.1);
      const size = Math.max(0.8, Math.min(colW, rowH) * 0.34);
      const end = unitColumns(hero, 0, x, y, rect.x, rect.y, size);
      const narrow = w < 900;
      const us = usFormation(geo.dots.length, narrow ? w * 0.5 : rect.x + rect.w * 0.5, narrow ? h * 0.72 : rect.y + rect.h * 0.48, narrow ? w * 1.1 : rect.w * 1.25, h * 0.8, 0.1, GRAY, 0.3);
      for (let i = 0; i < geo.dots.length; i++) {
        hero.x[end + i] = us.x[i];
        hero.y[end + i] = us.y[i];
        hero.r[end + i] = us.r[i];
        hero.a[end + i] = us.a[i];
        hero.c[end + i] = PALE;
      }
      const mid = scatter(n, w, h, 41);
      const crowdTop = w < 900 ? 0.52 : 0.42;
      const crowd = matchByX(mid, crowdFormation(n, w, h * (1 - crowdTop), h * crowdTop), 5);
      const lift = new Float32Array(n);
      for (let i = 0; i < n; i++) lift[i] = hero.x[i] + (i >= end ? 600 : 0);
      field.setSegments([
        { start: 0.1, end: 0.42, from: hero, to: mid, stagger: 0.45, order: orderBy(lift, 0.2), wander: 26 },
        { start: 0.42, end: 0.8, from: mid, to: crowd, stagger: 0.35, order: orderBy(crowd.y, 0.35, 9), wander: 18 },
      ]);
    },
    overlay(p) {
      const out = ramp(p, 0.05, 0.2);
      heroText.style.opacity = String(1 - out);
      heroText.style.transform = `translateY(${-out * 36}px)`;
      heroText.style.visibility = out > 0.99 ? "hidden" : "visible";
      const svg = chartEl.querySelector("svg");
      if (svg) svg.style.opacity = String(1 - ramp(p, 0.08, 0.2));
      const cap = chartEl.parentElement?.querySelector<HTMLElement>(".hero-cap");
      if (cap) cap.style.opacity = String(1 - ramp(p, 0.06, 0.16));
      const s = ramp(p, 0.74, 0.86);
      statement.style.opacity = String(s);
      statement.style.transform = `translateY(${(1 - s) * 18}px)`;
      statement.style.visibility = s < 0.01 ? "hidden" : "visible";
    },
    discrete: (p) => (p < 0.45 ? 0 : 1),
  });
}

const TERMINAL = [
  "> study     M10 housing and fertility",
  "> unit      state-year, 50 states + DC",
  "> period    2014-2019, 2021-2024",
  "> outcome   births per 1,000 women",
  "> ages      20-24 and 25-29",
  "> exposure  renters paying 30%+ on rent",
  "> method    two-way fixed effects",
  "> reading   association, not cause",
];
const FIELD_CHARS = [".", ".", ":", "+", "-", "0", "1", "·"];

export function initAscii() {
  const track = document.getElementById("stage-ascii");
  if (!track) return;
  const stage = track.querySelector<HTMLElement>(".stage")!;
  const caption = document.getElementById("ascii-caption")!;
  const n = geo.dots.length;
  runStage({
    track,
    canvas: stage.querySelector("canvas")!,
    n,
    build(field, w, h) {
      const rand = rng(77);
      const charW = 9.05;
      const lineH = 27;
      const cols = Math.max(...TERMINAL.map((l) => l.length));
      const bx = Math.round(w / 2 - (cols * charW) / 2);
      const by = Math.round(h / 2 - (TERMINAL.length * lineH) / 2);
      const text = formation(n);
      const chars: string[] = new Array(n).fill(".");
      let i = 0;
      TERMINAL.forEach((ln, row) => {
        [...ln].forEach((ch, col) => {
          if (ch === " " || i >= n) return;
          text.x[i] = bx + col * charW + charW / 2;
          text.y[i] = by + row * lineH;
          text.a[i] = 1;
          text.c[i] = ch === ">" ? OXBLOOD : INK;
          text.g[i] = 1;
          text.r[i] = 1.2;
          chars[i] = ch;
          i++;
        });
      });
      const cells: [number, number][] = [];
      const gx = 19;
      const gy = 23;
      const pad = 26;
      for (let yy = gy; yy < h - 10; yy += gy) {
        for (let xx = gx / 2; xx < w; xx += gx) {
          const inside = xx > bx - pad && xx < bx + cols * charW + pad && yy > by - pad - 10 && yy < by + TERMINAL.length * lineH + pad;
          if (!inside) cells.push([xx, yy]);
        }
      }
      for (let k = cells.length - 1; k > 0; k--) {
        const j = Math.floor(rand() * (k + 1));
        [cells[k], cells[j]] = [cells[j], cells[k]];
      }
      for (let c = 0; i < n; i++, c++) {
        const cell = cells[c % Math.max(1, cells.length)] ?? [rand() * w, rand() * h];
        const dist = Math.hypot(cell[0] - w / 2, cell[1] - h / 2) / Math.hypot(w / 2, h / 2);
        text.x[i] = cell[0] + (c >= cells.length ? rand() * 6 : 0);
        text.y[i] = cell[1];
        text.a[i] = c >= cells.length ? 0 : 0.42 - dist * 0.3;
        text.c[i] = GRAY;
        text.g[i] = 1;
        text.r[i] = 1;
        chars[i] = FIELD_CHARS[Math.floor(rand() * FIELD_CHARS.length)];
      }
      field.setChars(chars);
      const narrow = w < 700;
      const us = usFormation(n, w / 2, h * 0.53, w * (narrow ? 0.94 : 0.8), h * 0.66, 0.92, INK, 0.34);
      const mid = scatter(n, w, h, 13);
      for (let k = 0; k < n; k++) mid.g[k] = 0.45;
      const usMatched = matchByX(mid, us, 17);
      field.setSegments([
        { start: 0.12, end: 0.46, from: text, to: mid, stagger: 0.4, order: orderBy(text.y, 0.5, 4), wander: 34 },
        { start: 0.46, end: 0.82, from: mid, to: usMatched, stagger: 0.32, order: orderBy(usMatched.x, 0.35, 8), wander: 22 },
      ]);
    },
    overlay(p) {
      const s = ramp(p, 0.82, 0.92);
      caption.style.opacity = String(s);
      caption.style.visibility = s < 0.01 ? "hidden" : "visible";
    },
    discrete: (p) => (p < 0.45 ? 0 : 1),
  });
}

export function initTimeline() {
  const track = document.getElementById("stage-timeline");
  if (!track) return;
  const stage = track.querySelector<HTMLElement>(".stage")!;
  const chartEl = document.getElementById("timeline-chart")!;
  const capStart = document.getElementById("timeline-cap-start")!;
  const capEnd = document.getElementById("timeline-cap-end")!;
  const n = geo.dots.length;
  let scales: { x: (v: number) => number; y: (v: number) => number } | null = null;
  const drawAxes = () => {
    const width = chartEl.clientWidth;
    const height = chartEl.clientHeight;
    const narrow = width < 560;
    const m = { t: 24, r: narrow ? 46 : 150, b: 34, l: 34 };
    const x = scaleLinear().domain([1951.5, 2040.5]).range([m.l, width - m.r]);
    const y = scaleLinear().domain([0, 4]).range([height - m.b, m.t]);
    scales = { x, y };
    select(chartEl).selectAll("svg").remove();
    const svg = select(chartEl)
      .append("svg")
      .attr("viewBox", `0 0 ${width} ${height}`)
      .attr("height", height)
      .attr("role", "img")
      .attr(
        "aria-label",
        "U.S. period total fertility rate observed from 1953 to 2024, then held at the 2024 level of 1.593 to 2040, with a widening range built from past forecast errors that failed its calibration check.",
      );
    svg
      .append("g")
      .selectAll("line")
      .data([1, 2, 3, 4])
      .join("line")
      .attr("class", "grid-line")
      .attr("x1", x.range()[0])
      .attr("x2", x.range()[1])
      .attr("y1", (d) => y(d))
      .attr("y2", (d) => y(d));
    svg
      .append("g")
      .attr("class", "axis")
      .attr("transform", `translate(${x.range()[0] - 8},0)`)
      .call(axisLeft(y).tickValues([0, 1, 2, 3, 4]).tickSize(0))
      .call((s) => s.select(".domain").remove());
    svg
      .append("g")
      .attr("class", "axis")
      .attr("transform", `translate(0,${y(0) + 6})`)
      .call(axisBottom(x).tickValues(narrow ? [1960, 2000, 2040] : [1960, 1980, 2000, 2020, 2040]).tickSize(0).tickFormat((d) => String(d)))
      .call((s) => s.select(".domain").remove());
    svg.append("text").attr("class", "axis-title").attr("x", x.range()[0] - 8).attr("y", y(4) - 12).text("Births per woman");
    svg
      .append("line")
      .attr("x1", x(2024.5))
      .attr("x2", x(2024.5))
      .attr("y1", y(0))
      .attr("y2", y(4))
      .attr("stroke", "var(--ink)")
      .attr("stroke-dasharray", "2 3");
    svg.append("text").attr("class", "anno-muted").attr("x", x(2024.5) + 6).attr("y", y(4) + 4).text("forecast");
    svg.append("text").attr("class", "anno-muted").attr("x", x(2024.5) - 6).attr("y", y(4) + 4).attr("text-anchor", "end").text("observed");
    const f2040 = forecast[forecast.length - 1];
    svg
      .append("path")
      .attr("fill", "none")
      .attr("stroke", "var(--oxblood)")
      .attr("stroke-width", 1.5)
      .attr("stroke-dasharray", "5 4")
      .attr("d", `M${x(2024)},${y(f2040.f)}H${x(2040)}`);
    if (!narrow) {
      const lx = x(2040) + 14;
      const t = svg.append("text").attr("class", "anno").attr("x", lx).attr("y", y(f2040.f) - 8);
      t.append("tspan").attr("x", lx).text("No change:");
      t.append("tspan").attr("x", lx).attr("dy", 16).text(`${fmt(f2040.f, 3)} in 2040`);
      const t2 = svg.append("text").attr("class", "anno-muted").attr("x", lx).attr("y", y(f2040.u80) - 2);
      t2.append("tspan").attr("x", lx).text("Shaded squares: range");
      t2.append("tspan").attr("x", lx).attr("dy", 15).text("from past errors;");
      t2.append("tspan").attr("x", lx).attr("dy", 15).text("failed calibration");
    }
  };
  runStage({
    track,
    canvas: stage.querySelector("canvas")!,
    n,
    build(field, w, h) {
      drawAxes();
      const { x, y } = scales!;
      const rect = relRect(chartEl, stage);
      const narrow = w < 700;
      const us = usFormation(n, w / 2, h * 0.53, w * (narrow ? 0.94 : 0.8), h * 0.66, 0.92, INK, 0.34);
      const chart = formation(n);
      const colW = x(1954) - x(1953);
      const rowH = y(0) - y(0.1);
      const size = Math.max(0.8, Math.min(colW, rowH) * 0.34);
      let i = unitColumns(chart, 0, x, y, rect.x, rect.y, size);
      for (const r of forecast) {
        for (let k = 0; k < 40 && i < n; k++) {
          const v = (k + 0.5) / 10;
          const inner = v >= r.l80 && v <= r.u80;
          const outer = !inner && v >= r.l95 && v <= r.u95;
          if (!inner && !outer) continue;
          chart.x[i] = rect.x + x(r.year);
          chart.y[i] = rect.y + y(v);
          chart.r[i] = size;
          chart.a[i] = inner ? 0.5 : 0.2;
          chart.c[i] = OXBLOOD;
          i++;
        }
      }
      const rand = rng(23);
      for (; i < n; i++) {
        chart.x[i] = rect.x + x(1952 + rand() * 88);
        chart.y[i] = rect.y + y(rand() * 4);
        chart.r[i] = 0.6;
        chart.a[i] = 0;
        chart.c[i] = PALE;
      }
      const matched = matchByX(us, chart, 29);
      field.setSegments([{ start: 0.08, end: 0.74, from: us, to: matched, stagger: 0.4, order: orderBy(us.x, 0.25, 6), wander: 16 }]);
    },
    overlay(p) {
      const svg = chartEl.querySelector("svg");
      if (svg) svg.style.opacity = String(ramp(p, 0.6, 0.8));
      const a = 1 - ramp(p, 0.08, 0.2);
      capStart.style.opacity = String(a);
      capEnd.style.opacity = String(ramp(p, 0.7, 0.85));
    },
    discrete: () => 1,
  });
}
