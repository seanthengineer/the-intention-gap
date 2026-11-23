import { select } from "d3";
import { deferHideTip, hideTip, showTip } from "../lib";
import { atlas, atlasColor, availableMetrics, display, legend, metrics, observation, states, trend, trendPlot, type Metric } from "./housing-atlas-model";

function initAtlas(root: HTMLElement) {
  if (!atlas) return;
  const metricSelect = root.querySelector<HTMLSelectElement>("#atlas-metric")!;
  const yearSelect = root.querySelector<HTMLSelectElement>("#atlas-year")!;
  const stateSelect = root.querySelector<HTMLSelectElement>("#atlas-state-select")!;
  const map = root.querySelector<SVGSVGElement>(".atlas-map")!;
  const paths = [...map.querySelectorAll<SVGPathElement>("[data-state]")];
  const outline = root.querySelector<SVGPathElement>("[data-atlas-outline]")!;
  const dc = root.querySelector<SVGGElement>("[data-atlas-dc]")!;
  const currentName = root.querySelector<HTMLElement>(".atlas-selected-state h4")!;
  const currentValue = root.querySelector<HTMLElement>(".atlas-selected-value")!;
  const currentUnit = root.querySelector<HTMLElement>(".atlas-selected-unit")!;
  const currentYear = root.querySelector<HTMLElement>(".atlas-selected-year")!;
  const trendSvg = root.querySelector<SVGSVGElement>(".atlas-trend svg")!;
  const trendGrid = select(trendSvg.querySelector<SVGGElement>("[data-atlas-grid]")!);
  const trendPath = select(trendSvg.querySelector<SVGPathElement>("[data-atlas-trend-path]")!);
  const trendMarker = select(trendSvg.querySelector<SVGCircleElement>("[data-atlas-trend-marker]")!);
  const selectedYear = select(trendSvg.querySelector<SVGLineElement>("[data-atlas-trend-year]")!);
  const mapCells = [...root.querySelectorAll<HTMLTableCellElement>("[data-atlas-cell]")];
  const trendCells = [...root.querySelectorAll<HTMLTableCellElement>("[data-atlas-trend-cell]")];
  const legendItems = [...root.querySelectorAll<HTMLElement>("[data-atlas-bin]")];
  const stateName = new Map(states.map(({ id, name }) => [String(id), name]));
  const setTabStop = (target: SVGPathElement) => {
    for (const path of paths) path.setAttribute("tabindex", path === target ? "0" : "-1");
  };
  const getMetric = () => {
    const metric = metricSelect.value as Metric;
    return availableMetrics.includes(metric) ? metric : availableMetrics[0];
  };

  function update() {
    const metric = getMetric();
    const year = Number(yearSelect.value);
    const fips = stateSelect.value;
    const name = stateName.get(fips)!;
    const metricInfo = metrics[metric];
    const value = observation(fips, year, metric);
    const series = trend(fips, metric, year);

    select(map).attr("aria-label", metricInfo.title + ", " + year + ". Interactive map of U.S. states and the District of Columbia");
    select(map).selectAll<SVGPathElement, unknown>("[data-state]").each(function () {
      const key = this.dataset.state!;
      const stateValue = observation(key, year, metric);
      select(this)
        .attr("fill", atlasColor(stateValue, metric))
        .attr("aria-pressed", String(key === fips))
        .attr("aria-label", stateName.get(key) + ": " + display(stateValue, metric));
    });
    const selected = paths.find((path) => path.dataset.state === fips)!;
    setTabStop(selected);
    outline.setAttribute("d", selected.getAttribute("d")!);
    dc.dataset.selected = String(fips === "11");

    currentName.textContent = name;
    currentValue.textContent = display(value, metric);
    currentUnit.textContent = metricInfo.unit;
    currentYear.textContent = String(year);
    root.querySelector("[data-atlas-legend-unit]")!.textContent = metricInfo.unit;
    const bins = legend(metric);
    legendItems.forEach((item, i) => { item.textContent = bins[i].label; });

    trendSvg.setAttribute("aria-label", metricInfo.title + " in " + name + ", " + atlas!.years[0] + " to " + atlas!.years.at(-1) + ". Gap in 2020.");
    const lines = trendGrid.selectAll<SVGGElement, (typeof series.ticks)[number]>("g").data(series.ticks).join((enter) => {
      const tick = enter.append("g");
      tick.append("line").attr("x1", trendPlot.left).attr("x2", trendPlot.right);
      tick.append("text").attr("x", trendPlot.left - 7).attr("dy", "0.32em").attr("text-anchor", "end");
      return tick;
    });
    lines.attr("transform", (tick) => "translate(0," + tick.position + ")");
    lines.select("text").text((tick) => String(tick.value));
    trendPath.attr("d", series.path);
    selectedYear.attr("x1", series.selected.x).attr("x2", series.selected.x);
    trendMarker.attr("cx", series.selected.x).attr("cy", series.selected.y)
      .attr("visibility", series.selected.y === null ? "hidden" : "visible");

    root.querySelector("[data-atlas-map-caption]")!.textContent = metricInfo.title + ", " + year + " (" + metricInfo.unit + ")";
    root.querySelector("[data-atlas-trend-caption]")!.textContent = name + ": " + metricInfo.title + " (" + metricInfo.unit + ")";
    for (const cell of mapCells) cell.textContent = display(observation(cell.dataset.atlasCell!, year, metric), metric);
    for (const cell of trendCells) {
      const y = Number(cell.dataset.atlasTrendCell);
      cell.textContent = y === 2020 ? "No ACS 1-year release" : display(observation(fips, y, metric), metric);
    }
  }

  function choose(fips: string) {
    stateSelect.value = fips;
    hideTip();
    update();
  }

  function tooltip(fips: string, x: number, y: number, anchor: Element) {
    const metric = getMetric();
    const year = Number(yearSelect.value);
    const value = observation(fips, year, metric);
    showTip({
      head: stateName.get(fips) + " · " + year,
      rows: [[metrics[metric].title, display(value, metric)]],
      note: metrics[metric].unit,
    }, x, y, anchor);
  }

  for (const [index, path] of paths.entries()) {
    const fips = path.dataset.state!;
    path.setAttribute("role", "button");
    path.addEventListener("click", () => choose(fips));
    path.addEventListener("pointermove", (event) => {
      if (event.pointerType !== "touch") tooltip(fips, event.clientX, event.clientY, path);
    });
    path.addEventListener("pointerleave", () => {
      if (path !== document.activeElement) deferHideTip();
    });
    path.addEventListener("focus", () => {
      setTabStop(path);
      if (!path.matches(":focus-visible")) return;
      const rect = path.getBoundingClientRect();
      tooltip(fips, rect.right, rect.top, path);
    });
    path.addEventListener("blur", hideTip);
    path.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        choose(fips);
      } else if (e.key === "Escape") {
        hideTip();
      } else {
        const next = {
          ArrowLeft: index - 1, ArrowUp: index - 1,
          ArrowRight: index + 1, ArrowDown: index + 1,
          Home: 0, End: paths.length - 1,
        }[e.key];
        if (next === undefined) return;
        e.preventDefault();
        paths[(next + paths.length) % paths.length].focus();
      }
    });
  }
  dc.addEventListener("click", () => choose("11"));
  dc.addEventListener("pointermove", (event) => {
    if (event.pointerType !== "touch") tooltip("11", event.clientX, event.clientY, dc);
  });
  dc.addEventListener("pointerleave", deferHideTip);
  map.setAttribute("role", "group");
  for (const control of [metricSelect, yearSelect, stateSelect]) {
    control.addEventListener("change", () => {
      hideTip();
      update();
    });
  }
  root.querySelector<HTMLElement>(".atlas-controls")!.hidden = false;
  root.querySelector<HTMLElement>(".atlas-keys")!.hidden = false;
  root.querySelector<HTMLElement>(".atlas-fallback")!.hidden = true;
  root.setAttribute("data-atlas-ready", "");
  update();
}

document.querySelectorAll<HTMLElement>("#housing-atlas").forEach(initAtlas);
