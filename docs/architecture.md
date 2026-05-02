# Architecture

## Overview

The authoring tool has two main parts.

```text
Frontend editor in browser
        |
        | local API calls
        v
Python backend on your PC
        |
        | reads local project files
        v
Project folders and exported JSON
```

It runs locally. The browser is just the interface.

## Why this architecture

A browser interface is easier to use for editing timings.

A Python backend is better for audio processing and alignment tools.

Keeping it local avoids early hosting complexity and keeps source audio files on the user's PC.

## Main folders

```text
karaoke-authoring-tool
  backend
    app
      main.py
      api
      services
      models
      tools
  frontend
    src
      components
      pages
      lib
  projects
    local project files ignored by Git
  docs
    project documents
```

## Backend responsibilities

The backend should:

- accept audio and lyric inputs
- convert audio into a standard internal format
- normalise lyrics for alignment
- detect vocal sections and likely phrase boundaries
- run alignment
- produce draft JSON
- save and load projects
- export final JSON and LRC

## Frontend responsibilities

The frontend should:

- create and open projects
- upload or select audio and lyric files
- show waveform and playback cursor
- show timed phrases
- show confidence flags
- allow fast timing corrections
- export finished files

## Processing pipeline

```text
Input vocal + lyrics
        |
        v
Audio preparation
        |
        v
Lyric normalisation
        |
        v
Section detection
        |
        v
Alignment
        |
        v
Confidence scoring
        |
        v
Draft JSON
        |
        v
Review editor
        |
        v
Final JSON export
```

## Audio preparation

This stage should:

- convert MP3, M4A, or WAV into a standard WAV file
- make audio mono
- use a consistent sample rate
- measure duration
- detect long leading and trailing silence
- create waveform data for the editor

## Lyric normalisation

This stage should:

- keep the original display text
- create a cleaner alignment text
- preserve line order
- handle blank lines as possible section hints
- remove accidental junk lines when possible
- allow manual phrase split and merge later

## Section detection

This is important because global timing drifts.

The tool should treat each verse, chorus, or lyric paragraph as a smaller timing problem.

Inputs:

- lyric blank lines
- vocal gaps
- energy envelope
- manual section overrides

Output:

- section start and end estimates
- phrase groups per section

## Alignment layer

The exact aligner can change during testing.

The architecture should allow one alignment engine to be swapped for another.

Possible strategies:

- forced alignment from known lyrics
- ASR transcript used only as a sanity check
- hybrid alignment with section anchors

## Confidence scoring

Each phrase should get a confidence score.

Confidence should consider:

- whether the aligner found the phrase clearly
- whether phrase duration looks plausible
- whether phrase start sits near an onset
- whether phrase end sits near a gap
- whether repeated lines caused ambiguity

The editor should send low-confidence items to the top of the review queue.

## Export design

JSON is the main export.

LRC can be exported as a comparison format.

The final JSON should be stable enough for the future quiz app.
