# One spark — a Geneva motion study

A **15-second, 1280 × 720, 30 fps** three-act motion-graphics piece made with [geneva-render/geneva](https://github.com/geneva-render/geneva) v1.6.0. All the visuals are editable HTML/CSS; the edit and audio track are defined in `sample.json`. The original soundtrack is generated procedurally and supplied as a WAV. Inter is bundled under its OFL license.

| Time | Act | Source |
| --- | --- | --- |
| 0–5 s | One spark | `assets/01-origin.html` |
| 5–10 s | Take shape | `assets/02-form.html` |
| 10–15 s | Move the world | `assets/03-possibility.html` |

## Render locally

Install [Geneva v1.6.0](https://github.com/geneva-render/geneva/releases/tag/v1.6.0), then from the repository root:

```sh
geneva validate geneva-sample/sample.json --probe
geneva frame geneva-sample/sample.json -o still.png --at 7s
geneva render geneva-sample/sample.json -o geneva-sample/sample.mp4
```

Alternatively run the repository's **Render Geneva sample** GitHub Actions workflow. Its artifact contains the MP4 and three review stills. Download the playable MP4 from the workflow artifact; GitHub Actions does not have write permission to commit generated files to this branch.
