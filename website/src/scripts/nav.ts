import { clamp } from "./lib";

export function initNav() {
  const masthead = document.querySelector<HTMLElement>(".masthead")!;
  const cover = document.querySelector<HTMLElement>(".cover")!;
  const current = document.querySelector<HTMLElement>(".nav-toggle .current")!;
  const toggle = document.querySelector<HTMLButtonElement>(".nav-toggle")!;
  const sheet = document.getElementById("index-sheet")!;
  const entries = [...masthead.querySelectorAll<HTMLAnchorElement>(".nav-links a")].map((link) => ({
    link,
    section: document.getElementById(link.hash.slice(1))!,
    sheetLink: sheet.querySelector<HTMLAnchorElement>(`a[href="${link.hash}"]`)!,
  }));
  const wide = window.matchMedia("(min-width: 1120px)");
  let frame = 0;

  const update = () => {
    frame = 0;
    const navHeight = masthead.offsetHeight;
    const probe = navHeight + Math.min(120, window.innerHeight * 0.15);
    const onCover = cover.getBoundingClientRect().bottom > probe;
    masthead.toggleAttribute("data-cover", onCover && !cover.hasAttribute("data-paper-masthead"));
    let active = onCover ? -1 : 0;

    entries.forEach(({ section }, i) => {
      if (!onCover && section.getBoundingClientRect().top <= probe) active = i;
    });

    entries.forEach(({ link, sheetLink, section }, i) => {
      if (i === active) {
        const { top, height } = section.getBoundingClientRect();
        link.setAttribute("aria-current", "location");
        sheetLink.setAttribute("aria-current", "location");
        const progress = String(clamp((probe - top) / Math.max(1, height), 0.06, 1));
        link.style.setProperty("--p", progress);
        masthead.style.setProperty("--chapter-progress", progress);
      } else {
        link.removeAttribute("aria-current");
        sheetLink.removeAttribute("aria-current");
        link.style.removeProperty("--p");
      }
    });
    if (active < 0) masthead.style.removeProperty("--chapter-progress");
    current.textContent = entries[active]?.link.dataset.title ?? "Contents";
  };

  const schedule = () => {
    if (!frame) frame = requestAnimationFrame(update);
  };
  window.addEventListener("scroll", schedule, { passive: true });
  window.addEventListener("resize", schedule);
  const layout = new ResizeObserver(schedule);
  layout.observe(document.body);
  update();

  const close = () => {
    sheet.hidden = true;
    toggle.setAttribute("aria-expanded", "false");
  };

  toggle.addEventListener("click", () => {
    if (!sheet.hidden) {
      close();
      return;
    }
    sheet.hidden = false;
    toggle.setAttribute("aria-expanded", "true");
    (sheet.querySelector<HTMLAnchorElement>("[aria-current]") ?? entries[0].sheetLink).focus();
  });
  wide.addEventListener("change", close);
  sheet.addEventListener("click", (event) => {
    const link = (event.target as Element).closest<HTMLAnchorElement>("a");
    if (!link) return;
    close();
    const section = document.getElementById(link.hash.slice(1));
    section?.setAttribute("tabindex", "-1");
    section?.focus({ preventScroll: true });
  });
  document.addEventListener("pointerdown", (event) => {
    if (!sheet.hidden && !sheet.contains(event.target as Node) && !toggle.contains(event.target as Node)) close();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !sheet.hidden) {
      close();
      toggle.focus();
    }
  });
  document.addEventListener("focusin", (event) => {
    if (!sheet.hidden && !sheet.contains(event.target as Node) && event.target !== toggle) close();
  });
}
