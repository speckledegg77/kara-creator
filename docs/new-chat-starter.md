# New Chat Starter

Copy and paste this into a new chat when working on Kara Creator Phase 2.

```text
I am building a separate local-first project called kara-creator.

I am a novice. Give step-by-step instructions. Use PowerShell commands. Do not assume I know where files go. When code changes are needed, provide full replacement files or complete new files.

Project goal:
Build a local Windows tool that creates karaoke timing JSON from an isolated vocal file plus exact lyrics. This is a separate project from my Musical Theatre Quiz app.

Core decision:
This is not a transcription tool. It should not rely on audio alone. It is a lyric-to-audio alignment tool using known lyrics and isolated vocals.

Current status:
Phase 1 has been validated.

We first tested MFA, but MFA struggled with sung vocals, especially held notes and repeated lyric phrases. We then tested a singing-specific aligner called lyrics-aligner. It worked much better.

Current working pipeline:
1. Isolated vocal MP3 plus exact lyrics TXT.
2. lyrics-aligner creates word onset timings.
3. Kara Creator converts word starts into a word-review JSON.
4. Kara Creator builds a karaoke-draft-v3 JSON.
5. The local editor lets me review and manually adjust line timings.
6. The edited JSON is exported.

Validated test results:
- First song: Miss the Mountains. The lyrics-aligner draft was close to ideal after a few manual edits.
- Second song: new_song_test. The full pipeline worked with 0 word-mapping warnings. The edited output was also good, with only limited manual corrections.

Important current files:
- tools/run_lyrics_aligner_pipeline.py
- tools/convert_lyrics_aligner_to_word_review_json.py
- tools/build_karaoke_draft_from_word_starts.py
- tools/edit_karaoke_draft.html
- tools/kara_creator_launcher.py, if already created
- config/custom_pronunciations.json
- outputs/test-draft-lyrics-aligner-v3-edited-1.json
- outputs/new_song_test-draft-lyrics-aligner-v3-edited-1.json

Current environment:
- Windows
- PowerShell
- Conda environment: aligner-win
- The singing aligner repo is at:
  C:\Users\mark\kara-creator\alignment_lab\singing-aligners\lyrics-aligner

Important workflow command:
conda activate aligner-win
cd C:\Users\mark\kara-creator

python .\tools\run_lyrics_aligner_pipeline.py `
  --audio ".\incoming\new-song-test\vocals.mp3" `
  --lyrics ".\incoming\new-song-test\lyrics.txt" `
  --name "new_song_test"

Current design question for Phase 2:
We want to remove the need to manually add lyric section headings such as [VERSE] or [CHORUS]. Section headings should become optional.

Preferred Phase 2 behaviour:
- Exact lyric line breaks remain required.
- Section headings are optional.
- If lyrics contain [SECTION] headings, use them.
- If lyrics contain blank lines between lyric groups, automatically create sections from those groups.
- If lyrics are continuous with no headings or blank groups, automatically split into sections every 6 to 8 lyric lines.
- The generated sections should mainly help editor navigation. They should not be required for alignment.

Extra Phase 2 requirement:
Support instrumental placeholder lines.

A line containing only ". . ." should be treated as an instrumental or non-lyric display line. It should appear in the editor and final karaoke JSON, but it should not be sent to lyrics-aligner as a word. It should not require a pronunciation.

Preferred behaviour:
- ". . ." on its own line becomes an editable timing line.
- It should display as ". . ." in the karaoke renderer.
- It should have an empty words array.
- It should have display_type: "instrumental".
- It should be timed from the surrounding lyric lines where possible.
- If it sits between two lyric lines, start near the previous line end and end just before the next lyric line starts.
- If it appears at the start or end of the song, use a fallback duration and flag it for review.
- Blank lines should still act as section breaks.
- Section headings like [VERSE] remain optional.
- The parser should accept ". . .", "...", or "…" and export them all as ". . .".

Next development task:
Please help me update the pipeline so it supports lyrics without manual section headings and supports instrumental placeholder lines. Start by modifying the lyrics parser in tools/run_lyrics_aligner_pipeline.py so it can:
1. use explicit [SECTION] headings when present,
2. otherwise use blank-line groups as auto sections,
3. otherwise split into automatic sections of about 8 lines,
4. preserve exact lyric line order and word mapping,
5. treat ". . ." on a line by itself as an instrumental display line, not as aligner text,
6. keep instrumental lines in the draft JSON and editor,
7. time instrumental lines from surrounding lyric lines where possible,
8. still produce karaoke-draft-v3 JSON that works in the existing editor.

Please give step-by-step PowerShell instructions and full replacement files.
```
