# Roadmap

## Current priority

Move from the validated Phase 1 proof of concept into Phase 2 usability improvements.

The immediate Phase 2 goal is to reduce lyric preparation work by making section headings optional and supporting instrumental placeholder lines.

## Phase 0: Project setup

Status: complete enough for current work.

Done:

- Repository created as `kara-creator`.
- Source documents added.
- Git workflow started.
- Windows and PowerShell workflow established.
- FFmpeg available.
- Conda environment `aligner-win` created.
- `lyrics-aligner` cloned under `alignment_lab/singing-aligners/lyrics-aligner`.

Still worth checking:

- `.gitignore` blocks audio, incoming files, run folders, and generated lyric JSON.

## Phase 1: Command-line proof of concept

Status: validated.

Done:

- Tested MFA and identified limitations for sung vocals.
- Tested singing-specific `lyrics-aligner`.
- Built pipeline from vocal MP3 plus lyrics TXT to word review JSON and draft JSON.
- Built `karaoke-draft-v3` draft generation from word starts.
- Built local browser editor.
- Added manual correction and export.
- Added custom pronunciation support.
- Added stale aligner file cleanup before repeat runs.
- Tested on two songs.

Done means:

- A command can create a draft JSON from a vocal MP3 and lyrics TXT.
- The generated draft is close enough to correct in the editor.
- The workflow reduces manual syncing.

## Phase 2: Usability and lyric-prep improvements

Current focus.

Tasks:

- [ ] Make manual section headings optional.
- [ ] Use explicit `[SECTION]` headings when present.
- [ ] Use blank-line lyric groups as automatic sections when headings are absent.
- [ ] Auto-split continuous lyrics into sections of about 8 lines.
- [ ] Add `. . .`, `...`, and `…` instrumental placeholder support.
- [ ] Keep instrumental placeholders in the draft and editor.
- [ ] Prevent instrumental placeholders being sent to `lyrics-aligner`.
- [ ] Add review flags when instrumental timing must be checked.
- [ ] Update the launcher to explain the simpler lyric format.
- [ ] Test a song with no headings.
- [ ] Test a song with blank-line groups.
- [ ] Test a song with `. . .` instrumental placeholders.

Done means:

- The user can paste ordinary clean lyrics without manually labelling every verse or chorus.
- The editor still shows useful sections.
- Instrumental gaps can be represented and edited.

## Phase 3: Editor improvement

Goal: make correction faster and less fiddly.

Tasks:

- [ ] Improve save/export naming.
- [ ] Add a cleaner project result page after pipeline generation.
- [ ] Add section-level shift.
- [ ] Add section-level rescale.
- [ ] Add filter for flagged lines.
- [ ] Add reviewed status per line.
- [ ] Add loop current line.
- [ ] Add loop current section.
- [ ] Add optional backing track preview.

Done means:

- A user can fix a draft without scrolling or hunting for problem areas.

## Phase 4: Export polish

Tasks:

- [ ] Define final export JSON separately from diagnostic draft JSON.
- [ ] Add final export button.
- [ ] Add optional LRC export.
- [ ] Add JSON validation before export.
- [ ] Add reload test for exported JSON.

Done means:

- The output is stable enough to use as a sample input for a future quiz app karaoke display.

## Phase 5: Prepare quiz app integration

Do this only after the authoring workflow works.

Tasks:

- [ ] Lock the final JSON schema.
- [ ] Create safe sample final JSON files.
- [ ] Build a standalone karaoke display component.
- [ ] Test display with exported JSON.
- [ ] Plan future quiz app integration.

## Later ideas

- Batch processing for many songs.
- Word-by-word highlighting.
- Automatic vocal separation.
- Better pronunciation editing UI.
- Better waveform display.
- Cloud version for trusted private use.
