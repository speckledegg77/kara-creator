# Decisions

Keep this file updated when a decision is made so the project does not keep reopening the same questions.

## Core decisions

- Build this as a separate project from the Musical Theatre Quiz app.
- Run the first version locally on the user's PC.
- Use a browser-based local interface rather than a hosted public app.
- Use PowerShell in instructions.
- Use exact lyric text as a required input.
- Use isolated vocal audio as the preferred authoring source.
- Do not rely on audio-only lyric transcription for the core workflow.
- Treat the tool as an authoring system, not just a JSON generator.

## Technical direction

- Use Python for backend audio processing.
- Use React for the local editor frontend.
- Use JSON as the canonical output format.
- Allow LRC export only as a secondary convenience format.
- Store timings in milliseconds.
- Store sections as first-class objects in the JSON.
- Store confidence flags so weak timings can be reviewed first.

## Editing behaviour decisions

- Timing edits should ripple by default.
- Changing a phrase start should move that phrase and later phrases in the section.
- Changing a phrase end should resize that phrase and ripple later phrases in the section.
- The editor should support section-level shift and rescale.
- The editor should support split and merge for phrases.
- The editor should support loop playback for the current phrase or section.

## Scope decisions

- MVP target is phrase or line timing, not word-by-word highlighting.
- Word timing can be stored later if alignment tools produce it reliably.
- The first version should not include automatic vocal isolation.
- Vocal isolation can remain a separate source-prep step for now.
- The first version should not integrate into the quiz app.

## Quality bar

The tool is only useful if it reduces work.

A good draft should need a few minutes of correction for a clean, easy song.

If a song still requires line-by-line manual syncing, that song or alignment method is not MVP-ready.

## File safety decisions

- Do not commit commercial audio files to Git.
- Keep local project source audio in a local `projects/` folder that Git ignores.
- Commit only code, docs, safe sample data, and schema examples.
