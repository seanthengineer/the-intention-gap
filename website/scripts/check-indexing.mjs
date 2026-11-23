import { readFileSync } from "node:fs";

const canonical = "https://seanthengineer.github.io/the-intention-gap/";
const html = readFileSync(new URL("../dist/index.html", import.meta.url), "utf8");
const sitemap = readFileSync(new URL("../dist/sitemap.xml", import.meta.url), "utf8");

if (/<meta\b[^>]*name=["'](?:robots|googlebot)["'][^>]*content=["'][^"']*noindex/i.test(html) ||
    /<meta\b[^>]*content=["'][^"']*noindex[^"']*["'][^>]*name=["'](?:robots|googlebot)/i.test(html)) {
  throw new Error("The website still blocks search indexing.");
}
if (!html.includes(`rel="canonical" href="${canonical}"`)) {
  throw new Error("The website is missing its canonical URL.");
}
if (!sitemap.includes(`<loc>${canonical}</loc>`)) {
  throw new Error("The sitemap does not list the public website URL.");
}
console.log("Indexing checks passed: no noindex, canonical URL and sitemap present.");
