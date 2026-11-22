import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { ramp } from "./lib";

export function initCover() {
  const cover = document.querySelector<HTMLElement>(".cover")!;
  const scene = cover.querySelector<HTMLElement>(".cover-scene")!;
  const status = cover.querySelector<HTMLElement>(".cover-status")!;
  const easing = gsap.parseEase("power2.inOut");
  const media = gsap.matchMedia();

  media.add("(min-width: 940px) and (min-height: 700px) and (prefers-reduced-motion: no-preference)", () => {
    let previous = -1;
    const render = ({ progress }: ScrollTrigger) => {
      if (progress === previous) return;
      previous = progress;
      const flat = easing(ramp(progress, .12, .58));
      const paper = easing(ramp(progress, .70, 1));
      scene.style.setProperty("--cover-flat", String(flat));
      scene.style.setProperty("--cover-tilt", String(-.09 * (1 - flat)));
      scene.style.setProperty("--cover-offset", String(33 * (1 - flat)));
      scene.style.setProperty("--cover-title-exit", String(easing(ramp(progress, .29, .46))));
      const reading = easing(ramp(progress, .40, .59)) * (1 - easing(ramp(progress, .71, .82)));
      scene.style.setProperty("--cover-reading-in", String(reading));
      scene.style.setProperty("--cover-paper-copy", String(easing(ramp(progress, .88, .98))));
      scene.style.setProperty("--cover-paper-cut", `${100 * (1 - paper)}%`);
      cover.toggleAttribute("data-paper-footer", paper > .085);
      cover.toggleAttribute("data-paper-masthead", paper > .94);
      const beat = progress < .42 ? "Annual observations" : progress < .78 ? "Read the vertical scale" : "From rates to intentions";
      if (status.textContent !== beat) status.textContent = beat;
    };

    const trigger = ScrollTrigger.create({
      trigger: cover,
      start: "top top",
      end: "bottom bottom",
      onUpdate: render,
      onRefresh: render,
    });
    render(trigger);

    return () => {
      scene.removeAttribute("style");
      cover.removeAttribute("data-paper-footer");
      cover.removeAttribute("data-paper-masthead");
      status.textContent = "Annual observations";
    };
  });
}
