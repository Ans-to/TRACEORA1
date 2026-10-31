
## Remotion text reveal variant

`remotion-dot-path/` recreates the route using the [Remotion agent skills](https://github.com/remotion-dev/skills): the traveling dot draws the path, and three curved text segments appear **only after the dot has passed their positions**. The text is set on the same SVG path via `<textPath>` and masked by a stroke that trails the dot by 1.2% of the route. All motion is computed deterministically from `useCurrentFrame()`; nothing ahead of the dot is shown. The original HyperFrames project remains available in `animation/`.

Run `cd remotion-dot-path && npm ci && npm run studio` for the interactive preview (composition `DotToPath`). Rendering can be requested from Remotion Studio or with `npm run render`.
