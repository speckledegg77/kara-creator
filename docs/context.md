# Kara Creator: Context

## Project purpose

`kara-creator` is a separate local-first authoring tool for preparing karaoke timing files.

It supports a future Karaoke round in the Musical Theatre Quiz app, but it remains separate until the authoring workflow is proven and the export schema is stable.

## Problem being solved

The Musical Theatre Quiz app may later support a Karaoke round where lyrics display in time with music.

The hard part is not displaying lyrics. The hard part is creating accurate timing data quickly.

Manual line-by-line syncing is too slow if many songs are needed. Kara Creator should reduce authoring effort from full manual syncing to light review and correction.

## Current status

Phase 1 has been validated in practice.

The working proof of concept can take:

- isolated vocal MP3
- exact lyrics TXT
- song name

and create:

- lyrics-aligner word-onset output
- word review JSON
- `karaoke-draft-v3` JSON
- an editable draft that can be corrected in the local browser editor

The workflow has been tested on two songs:

- `Miss the Mountains`
- `new_song_test`

Both produced usable drafts after limited manual correction.

## Current primary alignment engine

The current default alignment engine is `lyrics-aligner`, a singing-specific aligner.

Earlier testing with MFA was useful, but MFA struggled with sung vocal timing, especially:

- held notes
- repeated lyric phrases
- sung vowels being assigned to the wrong next word
- line boundaries around sustained words

MFA is no longer the main Phase 1 route. It can remain a comparison or fallback experiment.

## Current working pipeline

```text
isolated vocal MP3
        +
exact lyrics TXT
        |
        v
lyrics-aligner word onsets
        |
        v
word review JSON
        |
        v
karaoke-draft-v3 JSON
        |
        v
local browser editor
        |
        v
edited karaoke JSON
```

## Inputs

Current required inputs:

- isolated vocal audio file
- exact lyric text for that recording
- correct lyric line breaks
- song name

Current optional inputs:

- section headings such as `[VERSE]`, `[CHORUS]`
- blank lines between lyric groups
- custom pronunciations for unusual words
- metadata such as title, show key, version label, and notes

## Lyric section rules

Manual section headings should not be required.

Phase 2 should support this order:

1. If lyrics contain explicit `[SECTION]` headings, use them.
2. If lyrics contain blank-line groups, create automatic sections from those groups.
3. If lyrics are continuous, split automatically into sections of about 8 lyric lines.

Sections are useful for editor navigation and future section tools, but they should not be a manual burden.

## Instrumental placeholder rule

A line containing only one of these should be treated as an instrumental display placeholder:

```text
. . .
...
…
```

The tool should normalise these to:

```text
. . .
```

This line should appear in the editor and final JSON, but it should not be sent to `lyrics-aligner`, because it has no lyric words and needs no pronunciation.

## Outputs

Expected outputs:

- draft karaoke JSON
- edited karaoke JSON
- word review JSON for diagnostics
- run manifest
- optional LRC export later
- saved local project state later

## Key product idea

Use known lyrics and isolated vocals to create a draft alignment.

Then use a fast local editor to fix the small number of lines that need correction.

## Important distinction

This is not primarily a transcription tool.

It should not try to guess lyrics from audio alone.

It is an alignment tool: known lyrics plus vocal audio create timings.

## Relationship to Musical Theatre Quiz app

The main quiz app should not include the authoring pipeline.

The quiz app should later consume final exported JSON.

Kara Creator can remain local and separate until export quality is good enough.

## Default user environment

The user works on Windows and prefers PowerShell instructions.

Instructions should assume the user is a complete novice.

Use step-by-step commands and explain where files go.
