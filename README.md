# Dot → Path (HyperFrames)

Seven-second, 1920 × 1080, 30 fps (210-frame) motion study. A single dot travels an authored cubic SVG route and draws the line behind it before settling into a destination node.

The project is `animation/index.html`; it uses **HyperFrames 0.8.223** and a local copy of GSAP 3.14.2. The route, dot, halo, guide and ending ring are editable SVG elements. GSAP owns the sole seekable progress value; its `onUpdate` samples the measured SVG path and updates the dot and visible stroke together. There is no timer, autoplay, paid plugin, remote asset or authored CSS. The movement adapts the documented registry ideas `offset-path-traveler` and `svg-stroke-trace` without copying their CSS-based markup.

From `animation/`: `npx hyperframes preview`, `npx hyperframes lint --json`, `npx hyperframes check --json`, `npx hyperframes snapshot --at 0,1.5,3.5,5,6.966 --no-end`, `npx hyperframes render --output dot-to-path.mp4`. The desktop-app preview can be edited directly. The result is intentionally silent. See `VALIDATION.md` for inspected snapshots and render specifications.
