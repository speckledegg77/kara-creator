# Start Here: Novice Guide

This document explains what to do from a simple starting point.

## What you are building

You are building a local tool that runs on your PC.

It feels like a web app because you open parts of it in a browser, but it is not hosted online.

The current working target is:

1. Select an isolated vocal file.
2. Load exact lyrics.
3. Generate a draft karaoke timing JSON.
4. Open that draft in an editor.
5. Fix timing quickly using ripple, anchors, and locks.
6. Export an edited JSON file.

## What has already been proven

Phase 1 has been validated.

The current pipeline can create usable draft JSON from:

```text
vocals.mp3
lyrics.txt
```

The current aligner is `lyrics-aligner`, which works better for singing than the earlier MFA tests.

## What you need installed

You probably need:

- Git or GitHub Desktop
- VS Code
- Miniconda
- FFmpeg
- Python
- Node.js later, if the editor moves to React

Do not worry if those names are unfamiliar. The setup guide walks through them.

## Your usual current workflow

1. Open PowerShell.
2. Go to the project folder.
3. Activate the aligner environment.
4. Run the pipeline.
5. Open the editor.
6. Load the generated audio and JSON.
7. Review and edit timings.
8. Export edited JSON.
9. Check `git status` before committing.

Commands:

```powershell
conda activate aligner-win
cd C:\Users\mark\kara-creator

python .\tools\run_lyrics_aligner_pipeline.py `
  --audio ".\incoming\new-song-test\vocals.mp3" `
  --lyrics ".\incoming\new-song-test\lyrics.txt" `
  --name "new_song_test"

Start-Process .\tools\edit_karaoke_draft.html
```

## Lyrics format

Exact lyric line breaks matter.

Section headings are optional.

You can use:

```text
[VERSE]
First lyric line
Second lyric line
```

or just use blank lines:

```text
First lyric line
Second lyric line

Third lyric line
Fourth lyric line
```

Phase 2 should make blank-line groups and automatic sections work smoothly.

## Instrumental gaps

Use this on a line by itself to show a non-lyric instrumental gap:

```text
. . .
```

The tool should also accept:

```text
...
…
```

## How to ask for help in a new chat

Use `docs/new-chat-starter.md`.

Paste it at the start of a new chat. Then add what you are trying to do and any errors you see.

## How to report an error

Copy this format:

```text
What I tried:

What I expected:

What happened instead:

Exact error message:

Screenshot if useful:
```

## What good progress looks like

Good progress is not a polished interface.

Good progress is proving that an isolated vocal plus lyrics can produce a draft that needs light correction rather than full manual syncing.

If the draft still needs line-by-line repair, improve the alignment pipeline before polishing the editor.
