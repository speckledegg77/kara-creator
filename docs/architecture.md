# Architecture

## Overview

Kara Creator is a local-first authoring tool.

Current working architecture:

```text
PowerShell / local launcher
        |
        v
Python pipeline tools
        |
        v
lyrics-aligner in conda environment
        |
        v
word review JSON
        |
        v
karaoke-draft-v3 JSON
        |
        v
static HTML editor in browser
        |
        v
edited JSON export
```

The browser is the interface. The processing happens locally on the user's PC.

## Why this architecture

A browser interface is easier to use for timing edits.

Python is better for audio processing and alignment tooling.

Keeping it local avoids early hosting complexity and keeps source audio files on the user's PC.

## Current main folders

```text
kara-creator
  tools
    run_lyrics_aligner_pipeline.py
    convert_lyrics_aligner_to_word_review_json.py
    build_karaoke_draft_from_word_starts.py
    edit_karaoke_draft.html
    kara_creator_launcher.py
  config
    custom_pronunciations.json
  incoming
    local uploaded song inputs ignored by Git
  outputs
    generated JSON outputs ignored by Git unless deliberately kept
  alignment_lab
    runs
      per-song run folders ignored by Git
    singing-aligners
      lyrics-aligner
  docs
```

## Current pipeline responsibilities

The pipeline should:

- accept an isolated vocal file and lyric file
- normalise lyrics for alignment
- preserve display lyrics separately from alignment tokens
- create a line map
- run `lyrics-aligner`
- create word review JSON
- create `karaoke-draft-v3` JSON
- clean stale aligner files before reruns
- write a run manifest

## Lyric parser responsibilities

The lyric parser should:

- keep original display text
- create cleaner alignment tokens
- preserve line order
- keep repeated lines as separate IDs
- use explicit section headings if present
- use blank-line groups as automatic sections if no headings are present
- auto-split continuous lyrics into sections of about 8 lines
- detect `. . .`, `...`, and `…` as instrumental placeholders
- exclude instrumental placeholders from aligner lyrics

## Alignment layer

The current primary engine is `lyrics-aligner`.

The architecture should still allow future alignment engines to be swapped in.

Possible future strategies:

- another singing-specific aligner
- MFA as a comparison or fallback
- ASR transcript used only as a sanity check
- hybrid alignment with manual anchors

## Draft builder responsibilities

The draft builder should:

- use word onsets as line anchors
- infer line ends from the next line start
- add review flags for likely weak timings
- insert instrumental placeholder lines into the timeline
- preserve sections
- create editor-friendly JSON

## Editor responsibilities

The current editor should:

- load audio and JSON
- show line cards
- follow playback
- jump to any line
- play the current line
- set start and end from the playhead
- ripple forward by default
- support anchors and locks
- export edited JSON

Future editor responsibilities:

- section shift
- section rescale
- filtered review queue
- backing track preview
- LRC export
- final clean JSON export

## Local launcher responsibilities

The launcher should:

- let the user choose an MP3 and lyrics TXT in the browser
- collect a song name
- run the existing pipeline
- show errors clearly
- show missing pronunciation words clearly
- show generated file paths
- open the editor

## Export design

`karaoke-draft-v3` is the current authoring draft format.

The future final export may be cleaner and may convert timings to milliseconds.

LRC can be exported as a convenience format later, but JSON remains canonical.
