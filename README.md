# Karaoke Authoring Tool

A local-first tool for creating karaoke timing JSON files from isolated vocal tracks and exact lyric text.

This project is separate from the Musical Theatre Quiz app. Its job is to create and edit karaoke assets. The quiz app can consume the exported JSON later.

## What this tool should do

The tool should help you turn:

- an isolated vocal audio file
- the exact lyrics for that version
- optional song metadata

into:

- a draft karaoke timing JSON file
- a reviewable editor project
- an exported final JSON file for later app use
- an optional LRC file for comparison

## What this tool should not try to do first

The first version should not try to build the whole karaoke quiz round.

It should not try to produce perfect word-by-word timing.

It should not rely on audio alone without lyrics.

It should not be added to the main quiz app until the authoring workflow works.

## Core principle

The goal is not perfect automatic syncing.

The goal is to reduce manual syncing to a short review process where you mostly anchor, nudge, split, merge, and export.

## Start here

Read these files in order:

1. `docs/00-novice-start-here.md`
2. `docs/context.md`
3. `docs/decisions.md`
4. `docs/roadmap.md`
5. `docs/setup-windows.md`
6. `docs/authoring-workflow.md`
7. `docs/json-schema.md`
8. `docs/testing-checklist.md`

## Default project approach

- Run locally on your PC.
- Use PowerShell for commands.
- Use a Python backend for audio processing.
- Use a React frontend for the editor.
- Keep generated audio files and local projects out of Git unless they are safe demo assets.

## Suggested repo name

`karaoke-authoring-tool`

## Link to quiz app project later

The main quiz app should only receive finished exported JSON files once this workflow is tested.

Do not add Python audio processing or alignment tooling to the Musical Theatre Quiz app.
