# Shared horror motion preview

This workflow uses the shared renderer and automatic narration planner pinned to science PR #103 at `d6d3b983e210b9d0778429e1cc0c007604700e67`.

- With blank inputs, export a channel-specific visual fixture PNG.
- With `episode_path`, `timings_path` and `narration_path`, build the scene plan automatically from the checked episode text and real audio alignment, then export MP4 and plan JSON.
- Alternatively supply `plan_path` and optional `narration_path` for a prebuilt plan.

Episode JSON supplies `title`/`topic` and `narration`/`narration_script`. Timings are SRT sentence cues or JSON word records (`text,start,end` or `text,offset,duration`). Every narration word must match the timing text in order; the planner does not invent per-word timestamps. The channel is enforced.

TTS, factual checks, narration/ASR quality and duplicate reservation remain upstream. No publisher or stock file is invoked here. Production adoption requires exporting the existing pipeline's timing data into this contract, reviewing the approved Egyptian narration, checking the completed episode and enabling motion-specific visual checks before connecting to the current receipt-confirmed publisher.

Science, history and horror share layout/timing/export, while their scene modules and data differ. Procedural templates do not provide unlimited fresh photoreal images or a match for an unknown TTS voice.
