# Blender Tech Promo — 15s portrait

Adapted from the supplied Blender Python script: a 1080 × 1920, 30 fps, five-shot "Write → Test → Run" product promo. `tech_promo.py` builds the entire scene procedurally. The voiceover lines remain metadata; the exported MP4 has no narrated audio. `[PRODUCT NAME]` remains a placeholder.

The supplied code built the scene but didn't render it (`main(render=False)`). Its text faced away from the camera, its shot objects stayed visible outside their shot, and its wide process cards would be cropped in portrait. This version corrects those while preserving its timing, palette, copy, process, result, and CTA.

Run **Render Blender tech promo** in GitHub Actions (or push a change to this directory). Download the `blender-tech-promo-15s` artifact from the successful workflow run. Locally: `blender -b -t 2 --python blender-tech-promo/tech_promo.py -- --render`.
