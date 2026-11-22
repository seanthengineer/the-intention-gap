export const REPO = "https://github.com/seanthengineer/the-intention-gap";
export const gh = (path: string) => `${REPO}/blob/main/${path}`;
export const ghTree = (path: string) => `${REPO}/tree/main/${path}`;
export const MINUS = "−";

export function num(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "n/a";
  const s = Math.abs(v).toFixed(digits);
  return v < 0 && Number(s) !== 0 ? MINUS + s : s;
}
export const pct = (v: number | null | undefined, digits = 1) => (v === null || v === undefined ? "n/a" : `${num(v * 100, digits)}%`);
export const int = (v: number) => v.toLocaleString("en-US");

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

export function md(s: string): string {
  return esc(s)
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, t, u) => {
      const href = /^https?:/.test(u) ? u : gh(`docs/${u}`.replace(/docs\/\.\.\//, ""));
      return `<a href="${href}">${t}</a>`;
    });
}
