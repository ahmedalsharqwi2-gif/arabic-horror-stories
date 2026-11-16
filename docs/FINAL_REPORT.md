# Horror follow-up review — validation in progress

- Branch: rebuild/clean-pipeline; existing PR #95. Main and backup refs are not modified.
- Original owner-provided JPG installed byte-for-byte at brand/logo/logo.jpg. SHA-256: f4dd2c963a4541493ea44af45ee5398cdb063fc874a1e40a0fe7a4a276c2320a. Header, intro/outro scene header and thumbnail use the same BrandLogo component through a canonical public alias. Source hash and rendered-pixel checks remain mandatory.
- Actual local make test: 29 tests PASS, TypeScript PASS. This includes mocked 429/503, Retry-After (including discovery and model fallback), rate limits, persistent voice resume, source freshness and corroboration, immutable-logo tamper rejection. Tests do not contact Gemini.
- Live full review via repository-bound GitHub Actions is the next execution step. Earlier run failures are not used as evidence of this follow-up's result.
- Local make review is queued under a shared renderer lock. A missing local Gemini binding must fail preflight and may produce a clearly marked silent, incomplete visual preview; it can never become a narrated-film acceptance.
- publish_enabled remains false. No Buffer/YouTube publication or scheduling is attempted.

A terminal result, exact new error if any, actual video/contact-sheet artifact and measured QA will replace this in-progress observation after the run completes. Reference-level art direction and listening approval are not claimed.

## Measured-alignment and voiced review follow-up

The preceding missing-key/429 report is historical. Actual subsequent Actions runs in science, Nafhamha, history and horror passed Gemini Charon voice generation/reuse; alignment then failed and a silent visual fallback was retained. This revision adds original-text forced alignment with independent ASR, safe exact diagnostics, retained original Charon WAVs, and a clearly INCOMPLETE voiced review when alignment fails. No timing is estimated to fabricate success. Wrong-channel inherited history/horror stories are quarantined before new generation, with original hashes/history/cache retained. Generic maps no longer default to Earth; galaxy, star-cluster, star and light-path diagrams follow the scene focus. The original logos remain byte-identical.

Local Node tests, TypeScript and four alignment-unit tests were actually run and passed for this revision. Live rendered-film acceptance remains pending the actual new Actions result; a voiced incomplete video is not a fully aligned approved film. Publication remains false and no real scheduled post was created.
