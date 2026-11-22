import { clamp } from "./lib";

export function initNav() {
  const links = [...document.querySelectorAll<HTMLAnchorElement>(".nav-links a[href^='#']")];
  const sections = links.map((a) => document.getElementById(a.hash.slice(1))).filter(Boolean) as HTMLElement[];
  const current = document.querySelector<HTMLElement>(".nav-toggle .current");
  const toggle = document.querySelector<HTMLButtonElement>(".nav-toggle");
  const sheet = document.getElementById("index-sheet");

  let frame = 0;
  const update = () => {
    frame = 0;
    const probe = window.innerHeight * 0.35;
    let active = -1;
    sections.forEach((s, i) => {
      const r = s.getBoundingClientRect();
      const p = clamp((probe - r.top) / Math.max(1, r.height));
      links[i].style.setProperty("--p", String(r.top <= probe && r.bottom > probe ? Math.max(0.04, p) : 0));
      if (r.top <= probe && r.bottom > probe) active = i;
    });
    links.forEach((a, i) => a.setAttribute("aria-current", String(i === active)));
    if (current) current.textContent = active >= 0 ? links[active].dataset.title ?? "" : "Contents";
  };
  window.addEventListener(
    "scroll",
    () => {
      if (!frame) frame = requestAnimationFrame(update);
    },
    { passive: true },
  );
  window.addEventListener("resize", update);
  update();

  if (toggle && sheet) {
    const close = () => {
      sheet.hidden = true;
      toggle.setAttribute("aria-expanded", "false");
      document.body.style.overflow = "";
    };
    toggle.addEventListener("click", () => {
      const open = sheet.hidden;
      sheet.hidden = !open;
      toggle.setAttribute("aria-expanded", String(open));
      document.body.style.overflow = open ? "hidden" : "";
      if (open) sheet.querySelector<HTMLAnchorElement>("a")?.focus();
    });
    sheet.querySelectorAll("a").forEach((a) => a.addEventListener("click", close));
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !sheet.hidden) {
        close();
        toggle.focus();
      }
    });
  }
}
