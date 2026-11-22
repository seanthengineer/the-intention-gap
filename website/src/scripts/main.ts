import { ScrollTrigger } from "gsap/ScrollTrigger";
import { mountEvidence } from "./charts/evidence";
import { mountBacktest, mountCohorts, mountCoverage, mountForecast } from "./charts/forecast";
import { mountLadder, mountLoso, mountRobustness, mountTrends } from "./charts/housing";
import { mountBrier, mountCalibration } from "./charts/nlsy";
import { mountAuc, mountDecomposition, mountSubgroups, mountWantIntend } from "./charts/nsfg";
import { initDither } from "./dither";
import { initNav } from "./nav";
import { initAscii, initOverview, initTimeline } from "./stages";

const CHARTS: Record<string, (el: HTMLElement) => void> = {
  evidence: mountEvidence,
  calibration: mountCalibration,
  brier: mountBrier,
  "want-intend": mountWantIntend,
  decomposition: mountDecomposition,
  subgroups: mountSubgroups,
  auc: mountAuc,
  trends: mountTrends,
  ladder: mountLadder,
  robustness: mountRobustness,
  loso: mountLoso,
  forecast: mountForecast,
  backtest: mountBacktest,
  coverage: mountCoverage,
  cohorts: mountCohorts,
};

function safely(name: string, fn: () => void) {
  try {
    fn();
  } catch (err) {
    console.error(`[intention-gap] ${name} failed`, err);
  }
}

function initLightbox() {
  const dialog = document.getElementById("lightbox") as HTMLDialogElement | null;
  if (!dialog) return;
  const img = dialog.querySelector("img")!;
  const cap = dialog.querySelector("[data-cap]")!;
  document.querySelectorAll<HTMLAnchorElement>("a[data-lightbox]").forEach((a) => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      img.src = a.href;
      img.alt = a.dataset.alt ?? "";
      cap.textContent = a.dataset.title ?? "";
      dialog.showModal();
    });
  });
  dialog.addEventListener("click", (e) => {
    if (e.target === dialog || (e.target as HTMLElement).closest("[data-close]")) dialog.close();
  });
}

async function start() {
  document.documentElement.classList.add("js");
  try {
    await Promise.race([document.fonts.ready, new Promise((r) => setTimeout(r, 1500))]);
  } catch {}
  safely("nav", initNav);
  document.querySelectorAll<HTMLElement>("[data-chart]").forEach((el) => {
    const fn = CHARTS[el.dataset.chart!];
    if (fn) safely(`chart ${el.dataset.chart}`, () => fn(el));
    const mo = new MutationObserver(() => {
      if (el.querySelector("svg")) {
        el.style.minHeight = "";
        mo.disconnect();
      }
    });
    mo.observe(el, { childList: true });
  });
  safely("overview stage", initOverview);
  safely("ascii stage", initAscii);
  safely("timeline stage", initTimeline);
  document.querySelectorAll<HTMLElement>("[data-dither]").forEach((el) => safely("photo", () => initDither(el)));
  safely("lightbox", initLightbox);
  let lastH = 0;
  let timer = 0;
  new ResizeObserver(() => {
    const h = document.documentElement.scrollHeight;
    if (Math.abs(h - lastH) < 2) return;
    lastH = h;
    clearTimeout(timer);
    timer = window.setTimeout(() => ScrollTrigger.refresh(), 120);
  }).observe(document.body);
  window.addEventListener("load", () => ScrollTrigger.refresh());
}

start();
