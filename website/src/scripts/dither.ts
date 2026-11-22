import { ScrollTrigger } from "gsap/ScrollTrigger";
import { clamp, reducedMotion } from "./lib";

const LEVELS = [18, 12, 8, 6, 4, 3, 2];

function atkinson(gray: Float32Array, w: number, h: number) {
  const out = new Uint8Array(w * h);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = y * w + x;
      const old = gray[i];
      const v = old < 0.5 ? 0 : 1;
      out[i] = v;
      const err = (old - v) / 8;
      const spread = [
        [1, 0],
        [2, 0],
        [-1, 1],
        [0, 1],
        [1, 1],
        [0, 2],
      ];
      for (const [dx, dy] of spread) {
        const xx = x + dx;
        const yy = y + dy;
        if (xx >= 0 && xx < w && yy < h) gray[yy * w + xx] += err;
      }
    }
  }
  return out;
}

export function initDither(figure: HTMLElement) {
  const src = figure.dataset.src!;
  const canvas = figure.querySelector("canvas")!;
  const frame = figure.querySelector<HTMLElement>(".frame")!;
  const ink = figure.dataset.ink ?? "#292929";
  const paper = figure.dataset.paper ?? "#faf8f4";
  const contrast = Number(figure.dataset.contrast ?? 1.15);
  const lift = Number(figure.dataset.lift ?? 0.04);
  const img = new Image();
  img.decoding = "async";
  img.src = src;
  let cache: HTMLCanvasElement[] = [];
  let level = -1;

  const build = () => {
    const rect = frame.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const W = Math.max(1, Math.round(rect.width * dpr));
    const H = Math.max(1, Math.round(rect.height * dpr));
    canvas.width = W;
    canvas.height = H;
    const ratio = Math.max(W / img.naturalWidth, H / img.naturalHeight);
    const dw = img.naturalWidth * ratio;
    const dh = img.naturalHeight * ratio;
    const focusY = Number(figure.dataset.focusY ?? 0.5);
    cache = LEVELS.map((cellCss) => {
      const cell = Math.max(1, Math.round(cellCss * dpr * 0.75));
      const w = Math.ceil(W / cell);
      const h = Math.ceil(H / cell);
      const small = document.createElement("canvas");
      small.width = w;
      small.height = h;
      const sctx = small.getContext("2d", { willReadFrequently: true })!;
      sctx.drawImage(img, (w - dw / cell) / 2, (h - dh / cell) * focusY, dw / cell, dh / cell);
      const px = sctx.getImageData(0, 0, w, h);
      const gray = new Float32Array(w * h);
      for (let i = 0; i < w * h; i++) {
        const l = (0.2126 * px.data[i * 4] + 0.7152 * px.data[i * 4 + 1] + 0.0722 * px.data[i * 4 + 2]) / 255;
        gray[i] = clamp((l - 0.5) * contrast + 0.5 + lift, 0, 1);
      }
      const bits = atkinson(gray, w, h);
      const out = document.createElement("canvas");
      out.width = W;
      out.height = H;
      const o = out.getContext("2d")!;
      o.fillStyle = paper;
      o.fillRect(0, 0, W, H);
      o.fillStyle = ink;
      const dot = Math.max(1, cell - (cell > 3 ? 1 : 0));
      for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
          if (bits[y * w + x] === 0) o.fillRect(x * cell, y * cell, dot, dot);
        }
      }
      return out;
    });
    level = -1;
  };

  const show = (k: number) => {
    if (!cache.length || k === level) return;
    level = k;
    const ctx = canvas.getContext("2d")!;
    ctx.drawImage(cache[k], 0, 0);
  };

  img.onload = () => {
    build();
    if (reducedMotion()) {
      show(LEVELS.length - 1);
      return;
    }
    show(0);
    ScrollTrigger.create({
      trigger: frame,
      start: "top 92%",
      end: "top 30%",
      onUpdate: (self) => show(Math.round(self.progress * (LEVELS.length - 1))),
      onRefresh: (self) => show(Math.round(self.progress * (LEVELS.length - 1))),
    });
  };

  let lastW = 0;
  new ResizeObserver((e) => {
    const w = Math.round(e[0].contentRect.width);
    if (!img.complete || w === lastW) return;
    lastW = w;
    const keep = level;
    build();
    show(Math.max(0, keep));
  }).observe(frame);
}
