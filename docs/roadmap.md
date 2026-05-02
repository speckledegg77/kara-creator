# Roadmap

## Current priority

Create a local-first authoring tool that proves whether isolated vocal audio plus exact lyrics can generate a usable karaoke JSON draft.

## Phase 0: Project setup

- [ ] Create new repo called `karaoke-authoring-tool`.
- [ ] Add these source documents.
- [ ] Add `.gitignore` to avoid committing audio and generated project files.
- [ ] Install required local tools.
- [ ] Confirm Python, Node.js, and FFmpeg work from PowerShell.

## Phase 1: Command-line proof of concept

Goal: prove the timing pipeline before building a polished editor.

- [ ] Create backend folder.
- [ ] Create Python virtual environment.
- [ ] Add audio preparation script.
- [ ] Add lyric normalisation script.
- [ ] Add basic section detection from blank lyric lines and vocal gaps.
- [ ] Add first draft JSON generator.
- [ ] Test with `I Miss the Mountains` isolated vocal and cleaned lyrics.
- [ ] Compare generated JSON against the existing viewer.

Done means:

- A command can create `karaoke.draft.json` from a vocal MP3 and lyrics TXT.
- The first two or three sections are close enough to review.
- Drift is better than the earlier flat timeline draft.

## Phase 2: Local editor MVP

Goal: make correction fast.

- [ ] Create frontend folder.
- [ ] Add waveform player.
- [ ] Load audio and JSON.
- [ ] Highlight active phrase.
- [ ] Add phrase list.
- [ ] Add section list.
- [ ] Add anchor start to playhead.
- [ ] Add anchor end to playhead.
- [ ] Add ripple forward behaviour.
- [ ] Add section shift.
- [ ] Add section rescale.
- [ ] Add JSON export.

Done means:

- A user can fix drift without manually adjusting every later line.

## Phase 3: Better alignment

Goal: reduce correction work.

- [ ] Test one or more forced alignment engines.
- [ ] Add confidence scoring.
- [ ] Flag low-confidence phrases.
- [ ] Add repeated-line handling.
- [ ] Add pronunciation overrides.
- [ ] Add better section boundary detection.

Done means:

- Clean isolated vocal files usually produce a draft that needs tweaking rather than manual syncing.

## Phase 4: Preview and export polish

- [ ] Add backing-track preview option.
- [ ] Add LRC export.
- [ ] Add final project save/load.
- [ ] Add review status per phrase.
- [ ] Add keyboard shortcuts.

## Phase 5: Prepare quiz app integration

Do this only after the authoring workflow works.

- [ ] Lock JSON schema.
- [ ] Create sample final JSON files.
- [ ] Build standalone karaoke display component.
- [ ] Test display with exported JSON.
- [ ] Plan future quiz app integration.

## Later ideas

- Batch processing for many songs.
- Word-by-word highlighting.
- Automatic vocal separation.
- Cloud version for trusted private use.
