# Start Here: Novice Guide

This document explains what to do from a completely blank starting point.

## What you are building

You are building a local tool that runs on your PC.

It will feel like a web app because you will open it in a browser, but it will not be hosted online.

The first working target is:

1. Select an isolated vocal file.
2. Load clean lyrics.
3. Generate a draft karaoke timing JSON.
4. Open that draft in an editor.
5. Fix timing quickly using ripple and section tools.
6. Export a final JSON file.

## What you need installed

You will probably need:

- GitHub Desktop or Git command line
- VS Code
- Python
- Node.js
- FFmpeg

Do not worry if those names are unfamiliar. The setup guide walks through them.

## How to work on this project

Use small steps.

Do not try to build the whole tool in one go.

The first real test should be a command-line proof of concept that takes:

```text
vocals.mp3
lyrics.txt
```

and creates:

```text
karaoke.draft.json
```

Only after that should the editor become the focus.

## Your usual workflow

1. Open PowerShell.
2. Go to the project folder.
3. Run the backend.
4. Run the frontend.
5. Open the local browser page.
6. Test with one known song.
7. Save results.
8. Commit changes to Git.

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

Good progress is not a polished interface on day one.

Good progress is proving that an isolated vocal plus lyrics can produce a draft that needs tweaking rather than full manual syncing.

If the draft still needs line-by-line repair, we improve the alignment pipeline before polishing the editor.
