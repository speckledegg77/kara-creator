# MVP Spec

## Purpose

Build a separate local-first authoring tool that creates karaoke timing JSON from isolated vocal audio and exact lyrics.

The tool supports future Karaoke round development in the Musical Theatre Quiz app, but it stays separate until the authoring workflow is proven.

## MVP goal

Create a draft timing file that needs light correction rather than full manual syncing.

The MVP is successful if a clean isolated vocal and matching lyrics can produce a section-based draft where most timing issues can be corrected through anchors, ripple edits, and section rescaling.

## Required inputs

- isolated vocal audio file
- exact lyric text file
- song title
- optional show key
- optional version label

## Required outputs

- draft karaoke JSON
- edited final karaoke JSON
- optional LRC export
- saved local project state

## User story

As a content author, I want to load an isolated vocal and exact lyrics, generate a draft karaoke file, quickly correct the parts that are off, and export a final JSON file for later use in the quiz app.

## MVP screens

## Screen 1: Project setup

Fields:

- project name
- song title
- show key
- version label

Actions:

- create project
- open existing project

## Screen 2: Source files

Inputs:

- vocal file
- lyric file or pasted lyrics
- optional backing track

Actions:

- validate files
- continue to lyric review

## Screen 3: Lyric review

Features:

- display lyric lines
- preserve blank-line section hints
- split line
- merge line
- add section break
- rename section

Actions:

- generate draft

## Screen 4: Timing editor

Features:

- audio player
- waveform
- phrase list
- active phrase highlight
- section list
- confidence flags
- low-confidence filter
- timing inspector

Core actions:

- anchor phrase start to playhead
- anchor phrase end to playhead
- ripple forward
- shift section
- rescale section
- split phrase
- merge phrase
- mark reviewed
- export JSON

## Screen 5: Export

Exports:

- final JSON
- optional LRC

## Required backend features

- project creation
- file validation
- audio conversion through FFmpeg
- lyric normalisation
- section detection
- draft timing generation
- JSON validation
- export writing

## Required frontend features

- project forms
- file inputs
- audio playback
- phrase display
- active phrase highlighting
- timing edit controls
- export button

## Timing model

MVP timing is phrase-level.

Word timing is not required.

Every phrase must have:

- ID
- display text
- start time in milliseconds
- end time in milliseconds
- confidence value
- flags array

## Section model

Sections are required.

Every section must have:

- ID
- label
- start time in milliseconds
- end time in milliseconds
- confidence value
- phrase array

## Editing rules

- Do not allow impossible negative timings.
- Do not allow phrase end before phrase start.
- Prevent overlaps by default.
- Use ripple editing rather than isolated edits.
- Keep manual corrections reversible where practical.

## MVP exclusions

Not included in the MVP:

- cloud deployment
- direct quiz app integration
- word-by-word fill animation
- automatic vocal isolation
- full batch processing
- perfect syncing without review

## First test case

Use one known isolated vocal and cleaned lyric file.

Measure:

- how close the draft is
- where drift begins
- how many edits are needed
- how long the review takes

## Build order

1. Docs and repo setup.
2. Backend skeleton.
3. Audio prep.
4. Lyric normalisation.
5. Draft JSON generator.
6. Simple viewer/editor.
7. Ripple editing.
8. Section editing.
9. Confidence review.
10. Export and reload.
