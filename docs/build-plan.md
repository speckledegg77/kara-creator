# Build Plan

This turns the roadmap into practical coding steps.

## Current state

Phase 1 is working.

The current implementation is not the original planned FastAPI plus React skeleton. The working MVP is currently:

```text
Python command-line pipeline
        +
lyrics-aligner in conda environment aligner-win
        +
static HTML editor
        +
optional local Flask launcher
```

This is acceptable for the proof of concept. Do not rewrite it into React or FastAPI until the authoring workflow is stable.

## Milestone 1: Source docs and repo

Status: done.

Files:

- `README.md`
- `docs/*`
- `.gitignore`

Checkpoint:

```powershell
cd C:\Users\mark\kara-creator
git status
```

## Milestone 2: Singing aligner setup

Status: done.

Expected pieces:

```text
alignment_lab
  singing-aligners
    lyrics-aligner
```

Environment:

```powershell
conda activate aligner-win
```

Current learning:

- The aligner runs locally on Windows in `aligner-win`.
- The old repo environment file was not reliable on Windows.
- A manually created conda environment was used instead.

## Milestone 3: Pipeline script

Status: done, but still being improved.

Main file:

```text
tools/run_lyrics_aligner_pipeline.py
```

Current command:

```powershell
conda activate aligner-win
cd C:\Users\mark\kara-creator

python .\tools\run_lyrics_aligner_pipeline.py `
  --audio ".\incoming\new-song-test\vocals.mp3" `
  --lyrics ".\incoming\new-song-test\lyrics.txt" `
  --name "new_song_test"
```

Expected outputs:

```text
outputs/<song>-word-review-lyrics-aligner.json
outputs/<song>-draft-lyrics-aligner-v3.json
alignment_lab/runs/<song>/<song>-run-manifest.json
```

## Milestone 4: Word review converter

Status: done.

Main file:

```text
tools/convert_lyrics_aligner_to_word_review_json.py
```

Purpose:

- Convert `lyrics-aligner` word-onset output into standard diagnostic word review JSON.
- Check that aligned words match the line map.
- Warn if tokenisation or word counts drift.

## Milestone 5: Draft builder

Status: done.

Main file:

```text
tools/build_karaoke_draft_from_word_starts.py
```

Purpose:

- Convert word starts into editable line timings.
- Infer line ends from the next line start.
- Add review flags for likely problem lines.
- Create `karaoke-draft-v3` JSON.

## Milestone 6: Local editor

Status: done enough for Phase 1.

Main file:

```text
tools/edit_karaoke_draft.html
```

Working features:

- load audio and draft JSON
- line cards rather than wide tables
- follow playback
- jump to line
- play line
- set start and end from playhead
- ripple forward
- anchors and locks
- export edited JSON

## Milestone 7: Local launcher

Status: started.

Main file:

```text
tools/kara_creator_launcher.py
```

Purpose:

- choose MP3 and lyrics TXT in browser
- provide song name
- run the existing pipeline
- show generated file paths
- open the editor

This still depends on the local Python process and `aligner-win` environment.

## Milestone 8: Optional sections and instrumental placeholders

Current next task.

Update:

```text
tools/run_lyrics_aligner_pipeline.py
```

Required behaviour:

1. Use explicit `[SECTION]` headings when present.
2. Otherwise use blank-line groups as automatic sections.
3. Otherwise split continuous lyrics into sections of about 8 lines.
4. Preserve lyric line order and word mapping.
5. Treat `. . .`, `...`, and `…` on their own line as instrumental placeholders.
6. Keep instrumental lines in the draft JSON and editor.
7. Do not send instrumental placeholders to `lyrics-aligner`.
8. Time instrumental placeholders from surrounding lyric lines where possible.

Checks:

```powershell
conda activate aligner-win
cd C:\Users\mark\kara-creator

python .\tools\run_lyrics_aligner_pipeline.py `
  --audio ".\incoming\sectionless-test\vocals.mp3" `
  --lyrics ".\incoming\sectionless-test\lyrics.txt" `
  --name "sectionless_test"
```

Expected result:

- no word mapping warnings
- draft JSON created
- editor loads the draft
- generated sections are usable
- `. . .` lines appear as editable cards

## Milestone 9: Section editing

Future task.

Required features:

- shift section earlier/later
- rescale section between two anchors
- lock section boundaries
- show section duration

## Milestone 10: Export polish

Future task.

Required features:

- final clean JSON export
- optional LRC export
- validation before export
- reload exported JSON

## Stop/go point

Continue if clean isolated vocal files usually become usable drafts with light correction.

Pause and revisit alignment if most songs still need line-by-line manual syncing.
