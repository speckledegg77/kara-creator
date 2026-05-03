# MVP Spec

## Purpose

Build a separate local-first authoring tool that creates karaoke timing JSON from isolated vocal audio and exact lyrics.

The tool supports future Karaoke round development in the Musical Theatre Quiz app, but it stays separate until the authoring workflow is proven.

## MVP goal

Create a draft timing file that needs light correction rather than full manual syncing.

The MVP is successful if a clean isolated vocal and matching lyrics can produce a draft where most timing issues can be corrected quickly in the editor.

## Current MVP status

Phase 1 has been validated.

The working pipeline uses:

- isolated vocal MP3
- exact lyrics TXT
- `lyrics-aligner`
- word review JSON
- `karaoke-draft-v3` JSON
- static HTML editor

Two songs have produced usable edited drafts.

## Required inputs

- isolated vocal audio file
- exact lyric text file
- correct lyric line breaks
- song name

Optional:

- explicit section headings
- blank lines between lyric groups
- `. . .` instrumental placeholders
- show key
- version label
- notes

## Required outputs

- draft karaoke JSON
- edited karaoke JSON
- run manifest
- optional word review JSON for diagnostics
- optional LRC export later

## User story

As a content author, I want to load an isolated vocal and exact lyrics, generate a draft karaoke file, quickly correct the parts that are off, and export a final JSON file for later use in the quiz app.

## Current screens and tools

## Tool 1: Pipeline command

Generates the draft:

```powershell
python .\tools\run_lyrics_aligner_pipeline.py `
  --audio ".\incoming\new-song-test\vocals.mp3" `
  --lyrics ".\incoming\new-song-test\lyrics.txt" `
  --name "new_song_test"
```

## Tool 2: Local launcher

A simple browser page can upload files and run the pipeline locally.

## Tool 3: Timing editor

Features:

- audio player
- line cards
- active line highlight
- follow playback
- jump to line
- play line
- set start from playhead
- set end from playhead
- ripple forward
- anchors
- locks
- export JSON

## Required backend or pipeline features

- file validation
- lyric normalisation
- optional section detection
- instrumental placeholder detection
- custom pronunciation support
- `lyrics-aligner` execution
- word review JSON creation
- draft timing generation
- stale file cleanup
- run manifest writing

## Required editor features

- audio playback
- line display
- active line highlighting
- timing edit controls
- ripple forward
- export button

## Timing model

MVP timing is line-level.

Word timings can be stored for diagnostics and future word-level highlighting.

Every line should have:

- ID
- display text
- start time
- end time
- review flags
- anchor state
- lock state
- manual edit state
- display type

## Section model

Sections remain first-class objects, but manual section headings are optional.

Sections can come from:

- `[SECTION]` headings
- blank-line lyric groups
- automatic grouping

Every section should have:

- ID
- label
- start time
- end time
- line array

## Instrumental placeholder model

A line containing `. . .`, `...`, or `…` on its own means an instrumental display line.

It should:

- display as `. . .`
- use `display_type: "instrumental"`
- have an empty `words` array
- not be sent to `lyrics-aligner`
- be editable in the timing editor
- be flagged if timing is uncertain

## Editing rules

- Do not allow impossible negative timings.
- Do not allow line end before line start.
- Prevent overlaps by default where practical.
- Use ripple editing rather than isolated edits.
- Keep manual corrections visible in the JSON.

## MVP exclusions

Not included in the MVP:

- cloud deployment
- direct quiz app integration
- word-by-word fill animation
- automatic vocal isolation
- full batch processing
- perfect syncing without review

## Acceptance test for a song

A song is acceptable for the MVP workflow if:

- most lines are roughly aligned
- repeated phrases can be corrected quickly
- instrumental gaps can be represented
- only a small number of individual lines need manual repair
- final review takes minutes, not a full manual syncing session
