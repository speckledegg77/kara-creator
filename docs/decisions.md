# Decisions

Keep this file updated when a decision is made so the project does not keep reopening the same questions.

## Core decisions

- Build this as a separate project from the Musical Theatre Quiz app.
- Run the first version locally on the user's PC.
- Use a browser-based local interface rather than a hosted public app.
- Use PowerShell in instructions.
- Use exact lyric text as a required input.
- Use correct lyric line breaks as a required input.
- Use isolated vocal audio as the preferred authoring source.
- Do not rely on audio-only lyric transcription for the core workflow.
- Treat the tool as an authoring system, not just a JSON generator.
- Do not integrate with the quiz app until the authoring workflow is proven.

## Alignment decisions

- `lyrics-aligner` is the current default Phase 1 alignment engine.
- MFA was tested and is no longer the main path because it struggled with sung vocals, held notes, and repeated phrases.
- Word onsets from `lyrics-aligner` are useful as anchors.
- Word endings from the current pipeline should not be treated as authoritative.
- Line starts should come from word onsets where possible.
- Line ends can be inferred from the next line start, then corrected in the editor.
- The tool should support custom pronunciation overrides.

## Lyric input decisions

- Section headings such as `[VERSE]` and `[CHORUS]` are optional.
- Blank lines between lyric groups should create automatic sections.
- If there are no headings and no useful blank-line groups, the tool should auto-split into sections of about 8 lines.
- Sections are mainly for navigation, review, and future section tools.
- Exact lyric order must be preserved.
- Repeated lyric lines must keep separate IDs.
- Hyphenated words should be tokenised in a way that matches `lyrics-aligner`, for example `wide-eyed` becomes the aligner token `wideeyed`.
- Display text should preserve punctuation and spelling where possible.

## Instrumental placeholder decisions

- A line containing only `. . .`, `...`, or `…` means an instrumental or non-lyric display line.
- The canonical display text should be `. . .`.
- Instrumental placeholder lines should appear in the editor and final JSON.
- Instrumental placeholder lines should not be sent to `lyrics-aligner`.
- Instrumental placeholder lines should not require pronunciations.
- Instrumental placeholder lines should use `display_type: "instrumental"`.
- Instrumental placeholder lines should have an empty `words` array.
- If possible, an instrumental placeholder should be timed from the surrounding lyric lines.
- If timing cannot be inferred safely, it should be flagged for review.

## Technical direction

- Use Python for the current backend and pipeline tools.
- Use the `aligner-win` conda environment for `lyrics-aligner` work.
- Use a static HTML editor for the current MVP editor.
- A React frontend can still be considered later, but it is not required for the current proof of concept.
- Use JSON as the canonical output format.
- Allow LRC export only as a secondary convenience format.
- Store timings consistently in the working draft schema.
- Store sections as first-class objects in the JSON.
- Store confidence and review flags so weak timings can be reviewed first.

## Editing behaviour decisions

- Timing edits should ripple by default.
- The editor should support anchors and locks.
- The selected line should follow playback by default.
- The editor should support quick line start and end setting from the playhead.
- The editor should support export of edited JSON.
- Future editor work should add section-level shift and rescale.

## Scope decisions

- MVP target is phrase or line timing, not word-by-word highlighting.
- Word timing can be stored for diagnostics and future features.
- The first version should not include automatic vocal isolation.
- Vocal isolation can remain a separate source-prep step for now.
- The first version should not integrate into the quiz app.

## Quality bar

The tool is only useful if it reduces work.

A good draft should need a few minutes of correction for a clean, easy song.

If a song still requires line-by-line manual syncing, that song or alignment method is not MVP-ready.

## File safety decisions

- Do not commit commercial audio files.
- Do not commit isolated vocal stems from commercial recordings.
- Do not commit generated JSON files that contain copyrighted full lyrics unless you have made a deliberate decision to keep them in a private repo.
- Keep `incoming/`, `outputs/`, and run folders out of Git unless a specific safe fixture is created.
- Commit only code, docs, safe sample data, and schema examples.
