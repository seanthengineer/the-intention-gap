import { clamp, easeInOut, rng } from "./lib";

export const PALETTE: [number, number, number][] = [
  [41, 41, 41],
  [125, 41, 38],
  [107, 104, 98],
  [63, 99, 131],
  [168, 160, 150],
];
export const INK = 0;
export const OXBLOOD = 1;
export const GRAY = 2;
export const SLATE = 3;
export const PALE = 4;

export interface Formation {
  x: Float32Array;
  y: Float32Array;
  r: Float32Array;
  a: Float32Array;
  c: Uint8Array;
  g: Float32Array;
}

export function formation(n: number): Formation {
  return {
    x: new Float32Array(n),
    y: new Float32Array(n),
    r: new Float32Array(n).fill(1.5),
    a: new Float32Array(n),
    c: new Uint8Array(n),
    g: new Float32Array(n),
  };
}

export interface Segment {
  start: number;
  end: number;
  from: Formation;
  to: Formation;
  stagger?: number;
  order?: Float32Array;
  wander?: number;
}

const GLYPH_PX = 15;

export class Field {
  readonly n: number;
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private dpr = 1;
  private segments: Segment[] = [];
  private jx: Float32Array;
  private jy: Float32Array;
  private chars: string[] = [];
  private glyphs = new Map<string, HTMLCanvasElement>();
  private colorCache = new Map<number, string>();
  width = 0;
  height = 0;

  constructor(canvas: HTMLCanvasElement, n: number, seed = 7) {
    this.n = n;
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d", { alpha: true })!;
    const rand = rng(seed);
    this.jx = new Float32Array(n);
    this.jy = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const ang = rand() * Math.PI * 2;
      const mag = 0.35 + rand() * 0.65;
      this.jx[i] = Math.cos(ang) * mag;
      this.jy[i] = Math.sin(ang) * mag;
    }
  }

  resize() {
    const rect = this.canvas.getBoundingClientRect();
    this.dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.width = rect.width;
    this.height = rect.height;
    this.canvas.width = Math.round(rect.width * this.dpr);
    this.canvas.height = Math.round(rect.height * this.dpr);
  }

  setChars(chars: string[]) {
    this.chars = chars;
  }

  setSegments(segments: Segment[]) {
    this.segments = segments;
  }

  private glyph(ch: string, color: number): HTMLCanvasElement {
    const key = `${ch}|${color}`;
    let g = this.glyphs.get(key);
    if (!g) {
      g = document.createElement("canvas");
      const s = Math.ceil(GLYPH_PX * 1.4 * this.dpr);
      g.width = s;
      g.height = s;
      const c = g.getContext("2d")!;
      c.scale(this.dpr, this.dpr);
      c.font = `400 ${GLYPH_PX}px "IBM Plex Mono", ui-monospace, monospace`;
      c.textAlign = "center";
      c.textBaseline = "middle";
      const [r, gg, b] = PALETTE[color];
      c.fillStyle = `rgb(${r},${gg},${b})`;
      c.fillText(ch, (GLYPH_PX * 1.4) / 2, (GLYPH_PX * 1.4) / 2 + 1);
      this.glyphs.set(key, g);
    }
    return g;
  }

  private rgb(c0: number, c1: number, t: number) {
    const q = Math.round(t * 8);
    const key = c0 * 1000 + c1 * 10 + q;
    let s = this.colorCache.get(key);
    if (!s) {
      const a = PALETTE[c0];
      const b = PALETTE[c1];
      const k = q / 8;
      s = `rgb(${Math.round(a[0] + (b[0] - a[0]) * k)},${Math.round(a[1] + (b[1] - a[1]) * k)},${Math.round(a[2] + (b[2] - a[2]) * k)})`;
      this.colorCache.set(key, s);
    }
    return s;
  }

  render(p: number) {
    const ctx = this.ctx;
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    ctx.clearRect(0, 0, this.width, this.height);
    if (!this.segments.length) return;
    let seg = this.segments[0];
    let t = 0;
    if (p >= this.segments[this.segments.length - 1].end) {
      seg = this.segments[this.segments.length - 1];
      t = 1;
    } else {
      for (const s of this.segments) {
        if (p < s.start) {
          seg = s;
          t = 0;
          break;
        }
        if (p <= s.end) {
          seg = s;
          t = (p - s.start) / (s.end - s.start);
          break;
        }
      }
    }
    const { from, to } = seg;
    const stagger = seg.stagger ?? 0.3;
    const wander = seg.wander ?? 0;
    const order = seg.order;
    const glyphSize = GLYPH_PX * 1.4;
    for (let i = 0; i < this.n; i++) {
      const d = order ? order[i] * stagger : 0;
      const ti = easeInOut(clamp((t - d) / (1 - stagger)));
      const bump = Math.sin(Math.PI * ti);
      const x = from.x[i] + (to.x[i] - from.x[i]) * ti + this.jx[i] * wander * bump;
      const y = from.y[i] + (to.y[i] - from.y[i]) * ti + this.jy[i] * wander * bump;
      const a = from.a[i] + (to.a[i] - from.a[i]) * ti;
      if (a < 0.01) continue;
      const r = from.r[i] + (to.r[i] - from.r[i]) * ti;
      const g = from.g[i] + (to.g[i] - from.g[i]) * ti;
      const c0 = from.c[i];
      const c1 = to.c[i];
      if (g > 0.02 && this.chars.length) {
        ctx.globalAlpha = a * g;
        const ch = this.chars[i % this.chars.length];
        const col = ti < 0.5 ? c0 : c1;
        if (ch !== " ") ctx.drawImage(this.glyph(ch, col), x - glyphSize / 2, y - glyphSize / 2, glyphSize, glyphSize);
      }
      if (g < 0.98) {
        ctx.globalAlpha = a * (1 - g);
        ctx.fillStyle = c0 === c1 ? this.rgb(c0, c0, 0) : this.rgb(c0, c1, ti);
        ctx.fillRect(x - r, y - r, r * 2, r * 2);
      }
    }
    ctx.globalAlpha = 1;
  }
}

export function orderBy(values: Float32Array | number[], noise = 0.15, seed = 3): Float32Array {
  const n = values.length;
  let lo = Infinity;
  let hi = -Infinity;
  for (let i = 0; i < n; i++) {
    lo = Math.min(lo, values[i]);
    hi = Math.max(hi, values[i]);
  }
  const rand = rng(seed);
  const out = new Float32Array(n);
  const span = hi - lo || 1;
  for (let i = 0; i < n; i++) out[i] = clamp(((values[i] - lo) / span) * (1 - noise) + rand() * noise);
  return out;
}

export function matchByX(from: Formation, to: Formation, seed = 11): Formation {
  const n = from.x.length;
  const rand = rng(seed);
  const a = [...Array(n).keys()].sort((i, j) => from.x[i] + rand() * 30 - (from.x[j] + rand() * 30));
  const b = [...Array(n).keys()].sort((i, j) => to.x[i] - to.x[j]);
  const out = formation(n);
  for (let k = 0; k < n; k++) {
    const src = a[k];
    const dst = b[k];
    out.x[src] = to.x[dst];
    out.y[src] = to.y[dst];
    out.r[src] = to.r[dst];
    out.a[src] = to.a[dst];
    out.c[src] = to.c[dst];
    out.g[src] = to.g[dst];
  }
  return out;
}

export function scatter(n: number, w: number, h: number, seed: number, margin = 24): Formation {
  const f = formation(n);
  const rand = rng(seed);
  for (let i = 0; i < n; i++) {
    f.x[i] = margin + rand() * (w - margin * 2);
    f.y[i] = margin + rand() * (h - margin * 2);
    f.r[i] = 0.8 + rand() * 0.9;
    f.a[i] = 0.25 + rand() * 0.45;
    f.c[i] = rand() < 0.06 ? OXBLOOD : INK;
  }
  return f;
}

export function scrollProgress(track: HTMLElement): number {
  const r = track.getBoundingClientRect();
  const total = r.height - window.innerHeight;
  if (total <= 0) return 0;
  return clamp(-r.top / total);
}
