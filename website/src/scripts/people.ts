import { rng } from "./lib";
import { type Formation, formation, INK, OXBLOOD } from "./particles";

interface Person {
  x: number;
  ground: number;
  h: number;
  build: "a" | "b";
  hair: "short" | "long" | "bun" | "cap" | "hood";
  lower: "trousers" | "skirt" | "coat";
  stance: number;
  armL: number;
  armR: number;
  bag: "none" | "tote" | "backpack";
  tone: number;
  child?: boolean;
  accent?: boolean;
}

function drawPerson(c: CanvasRenderingContext2D, p: Person) {
  const u = p.h / (p.child ? 5.6 : 7.6);
  const top = p.ground - p.h;
  const x = p.x;
  const wide = p.build === "b" ? 1.08 : 0.94;
  const sw = u * 0.98 * wide;
  const ys = top + u * 1.32;
  const yw = top + u * 3.05;
  const yh = top + u * 3.75;
  const ww = u * (p.build === "b" ? 0.7 : 0.6);
  const hw = u * (p.build === "b" ? 0.76 : 0.82);

  const grad = c.createLinearGradient(x - sw, 0, x + sw, 0);
  grad.addColorStop(0, `rgba(0,0,0,${p.tone})`);
  grad.addColorStop(0.55, `rgba(0,0,0,${p.tone * 0.86})`);
  grad.addColorStop(1, `rgba(0,0,0,${p.tone * 0.62})`);
  c.fillStyle = grad;
  c.strokeStyle = grad;
  c.lineCap = "round";
  c.lineJoin = "round";

  if (p.hair === "long") {
    c.beginPath();
    c.ellipse(x, top + u * 0.95, u * 0.52, u * 0.98, 0, 0, Math.PI * 2);
    c.fill();
  }
  c.beginPath();
  c.ellipse(x, top + u * 0.52, u * 0.4, u * 0.52, 0, 0, Math.PI * 2);
  c.fill();
  if (p.hair === "bun") {
    c.beginPath();
    c.arc(x + u * 0.05, top + u * 0.02, u * 0.22, 0, Math.PI * 2);
    c.fill();
  }
  if (p.hair === "cap") {
    c.beginPath();
    c.ellipse(x, top + u * 0.26, u * 0.46, u * 0.26, 0, Math.PI, 0);
    c.fill();
    c.fillRect(x - u * 0.15, top + u * 0.22, u * 0.68, u * 0.1);
  }
  if (p.hair === "hood") {
    c.beginPath();
    c.ellipse(x, top + u * 0.6, u * 0.55, u * 0.68, 0, 0, Math.PI * 2);
    c.fill();
  }

  c.fillRect(x - u * 0.17, top + u * 0.9, u * 0.34, u * 0.5);

  c.beginPath();
  c.moveTo(x - sw * 0.55, ys - u * 0.12);
  c.quadraticCurveTo(x - sw * 1.02, ys - u * 0.08, x - sw, ys + u * 0.38);
  c.lineTo(x - ww, yw);
  c.lineTo(x - hw, yh);
  c.lineTo(x + hw, yh);
  c.lineTo(x + ww, yw);
  c.lineTo(x + sw, ys + u * 0.38);
  c.quadraticCurveTo(x + sw * 1.02, ys - u * 0.08, x + sw * 0.55, ys - u * 0.12);
  c.closePath();
  c.fill();

  if (p.bag === "backpack") {
    c.beginPath();
    c.roundRect(x - sw * 0.82, ys + u * 0.15, sw * 1.64, u * 1.75, u * 0.3);
    c.fill();
  }

  const armTop = ys + u * 0.3;
  const handY = top + u * (p.child ? 3.4 : 4.45);
  const arm = (side: number, out: number) => {
    c.lineWidth = u * 0.34;
    c.beginPath();
    c.moveTo(x + side * (sw - u * 0.12), armTop);
    c.quadraticCurveTo(x + side * (sw + u * 0.08 + out * 0.4), (armTop + handY) / 2, x + side * (sw + u * 0.02 + out), handY);
    c.stroke();
  };
  arm(-1, p.armL * u);
  arm(1, p.armR * u);

  if (p.bag === "tote") {
    const hx = x + (sw + u * 0.02 + p.armR * u);
    c.fillRect(hx - u * 0.3, handY - u * 0.1, u * 0.62, u * 0.85);
  }

  const knee = top + u * 5.55;
  const foot = p.ground;
  if (p.lower === "coat" || p.lower === "skirt") {
    const bottom = p.lower === "coat" ? top + u * 5.5 : top + u * 5.0;
    c.beginPath();
    c.moveTo(x - hw, yh - u * 0.1);
    c.lineTo(x - hw * (p.lower === "coat" ? 1.08 : 1.22), bottom);
    c.lineTo(x + hw * (p.lower === "coat" ? 1.08 : 1.22), bottom);
    c.lineTo(x + hw, yh - u * 0.1);
    c.closePath();
    c.fill();
  }
  const leg = (side: number) => {
    const hipX = x + side * hw * 0.48;
    const footX = x + side * (hw * 0.42 + p.stance * u * 0.55);
    c.lineWidth = u * 0.5;
    c.beginPath();
    c.moveTo(hipX, yh - u * 0.15);
    c.lineTo((hipX + footX) / 2, knee);
    c.stroke();
    c.lineWidth = u * 0.36;
    c.beginPath();
    c.moveTo((hipX + footX) / 2, knee);
    c.lineTo(footX, foot - u * 0.12);
    c.stroke();
    c.beginPath();
    c.ellipse(footX + side * u * 0.05, foot - u * 0.08, u * 0.24, u * 0.12, 0, 0, Math.PI * 2);
    c.fill();
  };
  leg(-1);
  leg(1);
}

function makeCrowd(w: number, h: number, seed: number): Person[] {
  const rand = rng(seed);
  const people: Person[] = [];
  const narrow = w < 700;
  const rows = [
    { count: narrow ? 6 : 11, h: h * 0.3, ground: h * 0.6, tone: 0.48 },
    { count: narrow ? 5 : 9, h: h * 0.42, ground: h * 0.76, tone: 0.6 },
    { count: narrow ? 3 : 7, h: h * 0.56, ground: h * 0.97, tone: 0.95 },
  ];
  const hairs: Person["hair"][] = ["short", "long", "bun", "cap", "hood", "short", "long"];
  const lowers: Person["lower"][] = ["trousers", "trousers", "skirt", "coat", "trousers"];
  const bags: Person["bag"][] = ["none", "none", "tote", "backpack", "none"];
  rows.forEach((row, ri) => {
    const span = w * (narrow ? 1.04 : 0.96);
    const start = (w - span) / 2;
    const stepX = span / row.count;
    for (let k = 0; k < row.count; k++) {
      const jitter = (rand() - 0.5) * stepX * 0.45;
      const scale = 0.88 + rand() * 0.2;
      people.push({
        x: start + stepX * (k + 0.5) + jitter + (ri % 2 ? stepX * 0.25 : 0),
        ground: row.ground + (rand() - 0.5) * h * 0.02,
        h: row.h * scale,
        build: rand() < 0.5 ? "a" : "b",
        hair: hairs[Math.floor(rand() * hairs.length)],
        lower: lowers[Math.floor(rand() * lowers.length)],
        stance: rand() * 0.6,
        armL: rand() * 0.25,
        armR: rand() * 0.3,
        bag: bags[Math.floor(rand() * bags.length)],
        tone: row.tone,
        accent: ri === 2 && k === Math.floor(row.count * 0.62),
      });
      if (ri === 1 && k === 2) {
        people.push({
          x: start + stepX * (k + 0.5) + jitter + row.h * 0.24,
          ground: row.ground,
          h: row.h * 0.5,
          build: "a",
          hair: "short",
          lower: "trousers",
          stance: 0.2,
          armL: 0.1,
          armR: 0,
          bag: "none",
          tone: row.tone,
          child: true,
        });
      }
    }
  });
  return people;
}

export function crowdFormation(n: number, w: number, h: number, top: number, seed = 1995): Formation {
  const scale = 0.5;
  const cw = Math.max(1, Math.round(w * scale));
  const ch = Math.max(1, Math.round(h * scale));
  const canvas = document.createElement("canvas");
  canvas.width = cw;
  canvas.height = ch;
  const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
  const people = makeCrowd(cw, ch, seed);
  const accentCanvas = document.createElement("canvas");
  accentCanvas.width = cw;
  accentCanvas.height = ch;
  const actx = accentCanvas.getContext("2d", { willReadFrequently: true })!;
  for (const p of people) drawPerson(ctx, p);
  for (const p of people.filter((q) => q.accent)) drawPerson(actx, { ...p, tone: 1 });
  const data = ctx.getImageData(0, 0, cw, ch).data;
  const accent = actx.getImageData(0, 0, cw, ch).data;
  const rand = rng(seed);
  const f = formation(n);
  let filled = 0;
  let guard = 0;
  while (filled < n && guard < n * 400) {
    guard++;
    const px = Math.floor(rand() * cw);
    const py = Math.floor(rand() * ch);
    const idx = (py * cw + px) * 4 + 3;
    const alpha = data[idx] / 255;
    if (alpha <= 0.02 || rand() > alpha) continue;
    f.x[filled] = (px + rand()) / scale;
    f.y[filled] = top + (py + rand()) / scale;
    f.r[filled] = 1.05 + alpha * 0.75;
    f.a[filled] = 0.42 + alpha * 0.5;
    f.c[filled] = accent[idx] > 40 ? OXBLOOD : INK;
    filled++;
  }
  for (; filled < n; filled++) {
    f.x[filled] = rand() * w;
    f.y[filled] = top + h * (0.4 + rand() * 0.6);
    f.a[filled] = 0;
  }
  return f;
}
