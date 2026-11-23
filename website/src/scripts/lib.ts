export function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export const clamp = (v: number, lo = 0, hi = 1) => (v < lo ? lo : v > hi ? hi : v);
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
export const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);
export const ramp = (p: number, a: number, b: number) => clamp((p - a) / (b - a));

export const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export const MINUS = "−";
export function fmt(v: number | null | undefined, digits = 1, signed = false): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "n/a";
  const s = Math.abs(v).toFixed(digits);
  if (v < 0 && Number(s) !== 0) return MINUS + s;
  return signed && v > 0 ? "+" + s : s;
}
export const pct = (v: number | null | undefined, digits = 1) => (v === null || v === undefined ? "n/a" : fmt(v * 100, digits) + "%");
export const int = (v: number) => v.toLocaleString("en-US");

export function onResize(el: Element, fn: (width: number) => void) {
  let last = -1;
  let frame = 0;
  const ro = new ResizeObserver((entries) => {
    const w = Math.round(entries[0].contentRect.width);
    if (w === last || w === 0) return;
    last = w;
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => fn(w));
  });
  ro.observe(el);
}

let tipEl: HTMLDivElement | null = null;
let tipAnchor: Element | null = null;
let tipTimer = 0;
let tipHtml = "";
function tipNode() {
  if (!tipEl) {
    tipEl = document.createElement("div");
    tipEl.className = "tip";
    tipEl.setAttribute("role", "status");
    tipEl.setAttribute("aria-live", "polite");
    tipEl.addEventListener("pointerenter", () => window.clearTimeout(tipTimer));
    tipEl.addEventListener("pointerleave", deferHideTip);
    document.body.appendChild(tipEl);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") hideTip();
    });
  }
  return tipEl;
}

export interface TipContent {
  head: string;
  rows: [string, string][];
  note?: string;
}

export function showTip(c: TipContent, x: number, y: number, anchor: Element) {
  window.clearTimeout(tipTimer);
  const el = tipNode();
  const keepPosition = el.dataset.show === "true" && tipAnchor === anchor;
  tipAnchor = anchor;
  const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
  const html =
    `<div class="t-head">${esc(c.head)}</div>` +
    c.rows.map(([k, v]) => `<div class="t-row"><span>${esc(k)}</span><span>${esc(v)}</span></div>`).join("") +
    (c.note ? `<div class="t-note">${esc(c.note)}</div>` : "");
  if (keepPosition && tipHtml === html) return;
  el.innerHTML = html;
  tipHtml = html;
  el.dataset.show = "true";
  const r = el.getBoundingClientRect();
  const maxLeft = window.innerWidth - r.width - 12;
  const maxTop = window.innerHeight - r.height - 12;
  let left = x + 16;
  let top = y + 16;
  if (keepPosition) {
    left = Number.parseFloat(el.style.left);
    top = Number.parseFloat(el.style.top);
  } else {
    if (left > maxLeft) left = x - r.width - 16;
    if (top > maxTop) top = y - r.height - 16;
  }
  el.style.left = `${Math.max(8, Math.min(maxLeft, left))}px`;
  el.style.top = `${Math.max(8, Math.min(maxTop, top))}px`;
}

export function hideTip() {
  window.clearTimeout(tipTimer);
  tipAnchor = null;
  if (tipEl) tipEl.dataset.show = "false";
}

export function deferHideTip() {
  window.clearTimeout(tipTimer);
  tipTimer = window.setTimeout(hideTip, 350);
}

export function bindTip(node: Element, content: () => TipContent) {
  if (!node.hasAttribute("tabindex")) node.setAttribute("tabindex", "0");
  if (!node.hasAttribute("aria-label")) node.setAttribute("aria-label", content().head);
  if (node instanceof SVGElement && !node.hasAttribute("role")) node.setAttribute("role", "img");
  node.addEventListener("pointerenter", (e) => showTip(content(), (e as PointerEvent).clientX, (e as PointerEvent).clientY, node));
  node.addEventListener("pointermove", (e) => showTip(content(), (e as PointerEvent).clientX, (e as PointerEvent).clientY, node));
  node.addEventListener("pointerleave", () => {
    if (node !== document.activeElement) deferHideTip();
  });
  node.addEventListener("focus", () => {
    const r = node.getBoundingClientRect();
    showTip(content(), r.right, r.top, node);
  });
  node.addEventListener("blur", hideTip);
}

export function segmented(root: HTMLElement, onChange: (value: string) => void) {
  const buttons = [...root.querySelectorAll<HTMLButtonElement>("button[data-value]")];
  for (const b of buttons) {
    b.addEventListener("click", () => {
      for (const o of buttons) o.setAttribute("aria-pressed", String(o === b));
      onChange(b.dataset.value!);
    });
  }
  const active = buttons.find((b) => b.getAttribute("aria-pressed") === "true") ?? buttons[0];
  return active?.dataset.value ?? "";
}

export function toggle(button: HTMLButtonElement, onChange: (on: boolean) => void) {
  button.addEventListener("click", () => {
    const on = button.getAttribute("aria-pressed") !== "true";
    button.setAttribute("aria-pressed", String(on));
    onChange(on);
  });
  return button.getAttribute("aria-pressed") === "true";
}
