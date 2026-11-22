import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(SITE, "dist");
const files = [join(dist, "index.html"), ...readdirSync(join(dist, "_astro")).filter((f) => f.endsWith(".js")).map((f) => join(dist, "_astro", f))];
const rules = [
  [/—|&mdash;|&#8212;/g, "em dash"],
  [/\p{Extended_Pictographic}/gu, "emoji or pictograph"],
  [/groundbreaking|revolutioni[sz]|cutting-edge|actionable|unlock(ing)? insights|game-chang/gi, "marketing phrase"],
];
const problems = [];
for (const file of files) {
  const text = readFileSync(file, "utf8");
  for (const [re, label] of rules) {
    for (const m of text.matchAll(re)) {
      const at = Math.max(0, m.index - 50);
      problems.push(`${label} in ${file.slice(dist.length + 1)}: ...${text.slice(at, m.index + 50).replace(/\s+/g, " ")}...`);
    }
  }
}
if (problems.length) {
  console.error(`Text check FAILED (${problems.length}):\n  ` + problems.slice(0, 20).join("\n  "));
  process.exit(1);
}
console.log(`Text check passed: no em dashes, emoji or marketing phrases in ${files.length} built files.`);
