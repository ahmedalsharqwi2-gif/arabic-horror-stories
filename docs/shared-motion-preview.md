# Shared channel motion preview

The manual `Channel motion preview` workflow uses the shared renderer from science-discovery-shorts at pinned commit `e6171c7160e624d41910752980dab057b81a2ef5` (science PR #103). The shared engine owns Arabic headings, captions, timing validation and vertical MP4 export. This channel selects the `horror` scene module.

With blank inputs it exports a six-second visual fixture as a PNG. Supply a checked episode plan and a repository-local approved narration file to render a complete MP4. The plan must cover the real audio duration exactly, within the renderer's 120ms tolerance. No TTS provider is selected by this workflow.

This is a review path. It never invokes the publisher, reserves a topic, or writes publication receipts. Production still needs a source-checked plan adapter, approved Egyptian voice, full episode review, and visual quality checks appropriate to procedural scenes. The fixture is not a publishable episode.

See the pinned core's `motion/README.md` for the input contract and scene types. Upgrade the shared SHA only after its renderer checks pass.
