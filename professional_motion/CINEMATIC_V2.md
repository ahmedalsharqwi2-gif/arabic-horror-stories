# Horror cinematic renderer candidate

This is an opt-in renderer on the rebuild branch. The existing daily workflow and its publication receipts remain unchanged. It is not accepted for production merely because a still or regression render succeeds.

The v2 rig adds one bounded 512px soft-shadow map, deterministic 64px surface relief for timber, brass and plaster, a slow lateral dolly with a fixed authored look-at target, and 96 world-space dust points in interior corridor views. Bloom is restrained for the original style and remains absent in the reference style. Historical ship geometry, map routes, source claims, caption timing, logo proportions and publication account IDs are retained. All frame motion is a function of absolute time, so rendering partitions out of order does not change camera state.

From repository root:

```sh
node tests/cinematic_horror.test.mjs
node professional_motion/render.mjs --pipeline v2 --review --style reference \
  --delivery-dir /absolute/path/to/candidate/delivery \
  --output-dir /absolute/path/to/candidate/output
python -m professional_motion.finish \
  --delivery-dir /absolute/path/to/candidate/delivery \
  --output-dir /absolute/path/to/candidate/output
```

The delivery directory must contain an authored `story.json`, original `narration.wav` and measured `timing.json` with matching story/audio SHA-256 values. The renderer serves only story/timing JSON from an alternate delivery directory; it does not expose the directory's audio or provenance files. `--stills` is a visual-only check and can use a clearly synthetic fixture; it is not a narration test or full-film acceptance.

When testing a previously generated story and its exact original audio, pass `--archived-regression` to the finish step. Its report then records archived reuse and explicitly leaves new-topic acceptance false. Never reserve the old incident again, post a regression file, or call archived narration a new generated episode.

The original horror logo file is not present. `professional_motion/branding.json` accurately records `original_logo_installed: false`; no replacement image is generated.

A full new-topic film, verified audio, review evidence and safe migration/cutover checks are prerequisites before the old workflow can be disabled. The renderer alone does not switch a production owner or publish anything.
