import { axisBottom, axisLeft, type ScaleLinear, select, type Selection } from "d3";

export type G = Selection<SVGGElement, unknown, null, undefined>;
export type S = Selection<SVGSVGElement, unknown, null, undefined>;

export function svgIn(el: HTMLElement, width: number, height: number, label: string): S {
  select(el).selectAll("svg").remove();
  return select(el)
    .append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", width)
    .attr("height", height)
    .attr("role", "img")
    .attr("aria-label", label) as unknown as S;
}

export function gridY(g: G, y: ScaleLinear<number, number>, x0: number, x1: number, ticks: number[]) {
  g.append("g")
    .selectAll("line")
    .data(ticks)
    .join("line")
    .attr("class", "grid-line")
    .attr("x1", x0)
    .attr("x2", x1)
    .attr("y1", (d) => y(d))
    .attr("y2", (d) => y(d));
}

export function gridX(g: G, x: ScaleLinear<number, number>, y0: number, y1: number, ticks: number[]) {
  g.append("g")
    .selectAll("line")
    .data(ticks)
    .join("line")
    .attr("class", "grid-line")
    .attr("y1", y0)
    .attr("y2", y1)
    .attr("x1", (d) => x(d))
    .attr("x2", (d) => x(d));
}

export function leftAxis(g: G, y: ScaleLinear<number, number>, x: number, ticks: number[], format: (v: number) => string) {
  g.append("g")
    .attr("class", "axis")
    .attr("transform", `translate(${x},0)`)
    .call(axisLeft(y).tickValues(ticks).tickSize(0).tickPadding(8).tickFormat((d) => format(Number(d))))
    .call((s) => s.select(".domain").remove());
}

export function bottomAxis(g: G, x: ScaleLinear<number, number>, y: number, ticks: number[], format: (v: number) => string) {
  g.append("g")
    .attr("class", "axis")
    .attr("transform", `translate(0,${y})`)
    .call(axisBottom(x).tickValues(ticks).tickSize(0).tickPadding(8).tickFormat((d) => format(Number(d))))
    .call((s) => s.select(".domain").remove());
}

export function text(g: G, x: number, y: number, s: string, cls = "anno", anchor: "start" | "middle" | "end" = "start") {
  return g.append("text").attr("class", cls).attr("x", x).attr("y", y).attr("text-anchor", anchor).text(s);
}

export function figureOf(el: HTMLElement) {
  return el.closest("figure") as HTMLElement;
}

export function ciWhisker(g: G, x1: number, x2: number, y: number, color: string, cap = 4) {
  g.append("line").attr("x1", x1).attr("x2", x2).attr("y1", y).attr("y2", y).attr("stroke", color).attr("stroke-width", 1.25);
  g.append("line").attr("x1", x1).attr("x2", x1).attr("y1", y - cap).attr("y2", y + cap).attr("stroke", color).attr("stroke-width", 1.25);
  g.append("line").attr("x1", x2).attr("x2", x2).attr("y1", y - cap).attr("y2", y + cap).attr("stroke", color).attr("stroke-width", 1.25);
}
