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
const verification = readFileSync(new URL("../dist/google2eb755841a1575e8.html", import.meta.url), "utf8").trim();
if (verification !== "google-site-verification: google2eb755841a1575e8.html") {
  throw new Error("Google Search Console verification file is missing or has the wrong contents.");
}
console.log("Indexing checks passed: no noindex, canonical URL, sitemap and Google verification file present.");
