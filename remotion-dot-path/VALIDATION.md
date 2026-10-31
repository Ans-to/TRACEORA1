# Remotion text-on-path validation

- `npx tsc --noEmit` passed with strict TypeScript settings.
- Remotion Studio built successfully and exposes the `DotToPath` composition at 1920×1080, 30 fps, 210 frames.
- Headless Chrome on GitHub Actions rendered and inspected stills at frames 0, 26, 66, 108, 154, 188 and 209. Before the dot reaches a text segment, it is masked; afterward, the curved text and drawn path remain visible. The final frame holds the complete phrase and destination ring.
- All movement uses `useCurrentFrame()`, `useVideoConfig()`, an arc-length Bézier lookup and `interpolate()`. The text and stroke use the same route with separate dash offsets; the text reveal trails the dot by 1.2% of the route.
- **No new Remotion MP4 was rendered:** per the Remotion skill, a new composition opens in Studio for review unless the user explicitly requests export. The existing `animation/dot-to-path.mp4` is the prior HyperFrames version and does not include the new text.
