# Karaoke Authoring Tool: Context

## Project purpose

This is a separate local-first authoring tool for preparing karaoke timing files.

It supports a future Karaoke round in the Musical Theatre Quiz app, but it is not part of that app at the start.

## Problem being solved

The Musical Theatre Quiz app may later support a Karaoke round where lyrics display in time with music.

The hard part is not displaying lyrics. The hard part is creating accurate timing data quickly.

Manual line-by-line syncing is too slow if many songs are needed.

The tool must reduce authoring effort from manual syncing to light review and correction.

## Inputs

The expected authoring inputs are:

- isolated vocal audio file
- exact lyric text for that version
- optional metadata such as title, show key, version label, and notes
- optional playback or backing track for preview

## Outputs

The expected outputs are:

- section-based karaoke JSON
- optional LRC export
- saved project state for later editing

## Key product idea

Use known lyrics and isolated vocals to create a draft alignment.

Then use a fast editor to fix low-confidence lines or sections.

## Important distinction

This is not primarily a transcription tool.

It should not try to guess lyrics from audio alone.

It is an alignment tool: known lyrics plus vocal audio create timings.

## Current proof-of-concept learning

A flat line-timing JSON format is too limited for real editing.

A first rough draft from full audio drifted too much.

An isolated vocal file is a better source, but timing can still drift if alignment is treated as one long sequence.

The editor must support ripple timing so changing one line does not create overlaps.

The next generation should use section-based alignment and correction.

## Relationship to Musical Theatre Quiz app

The main quiz app should not include the authoring pipeline.

The quiz app should later consume final exported JSON.

The authoring tool can remain local and separate.

## Default user environment

The user works on Windows and prefers PowerShell instructions.

Instructions should assume the user is a complete novice.

Use step-by-step commands and explain where to type them.
