// My single-page research website has one public canonical URL.
export const prerender = true;

export function GET() {
  const url = "https://seanthengineer.github.io/the-intention-gap/";
  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>${url}</loc></url>
</urlset>`;
  return new Response(body, {
    headers: { "Content-Type": "application/xml; charset=utf-8" },
  });
}
