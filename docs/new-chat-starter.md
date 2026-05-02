# New Chat Starter

Copy and paste this into a new chat when working on the Karaoke Authoring Tool.

```text
I am building a separate local-first project called `karaoke-authoring-tool`.

I am a novice. Give step-by-step instructions. Use PowerShell commands. Do not assume I know where files go. When code changes are needed, provide full replacement files or complete new files.

Project goal:
Build a local tool that creates karaoke timing JSON from an isolated vocal file plus exact lyrics. The output will later support a Karaoke round in my Musical Theatre Quiz app, but this authoring tool is a separate project.

Core decision:
This is not a transcription tool. It should not rely on audio alone. It is a lyric-to-audio alignment tool using known lyrics and isolated vocals.

MVP target:
Generate a section-based draft JSON, then use a local editor to tweak timings quickly. The target is phrase or line timing first, not word-by-word highlighting.

Working assumptions:
- Runs locally on Windows.
- Use PowerShell for commands.
- Python backend for audio processing.
- React frontend for the editor.
- JSON is the canonical export format.
- LRC can be a secondary export only.
- Isolated vocal is required for generation in MVP.
- Exact lyrics are required.
- Timing edits should ripple forward by default.
- Sections should be first-class objects to prevent drift.
- Do not integrate with the Musical Theatre Quiz app until the authoring workflow works.

Important docs in this repo:
- README.md
- docs/context.md
- docs/decisions.md
- docs/roadmap.md
- docs/setup-windows.md
- docs/architecture.md
- docs/authoring-workflow.md
- docs/json-schema.md
- docs/testing-checklist.md
- docs/troubleshooting.md

Preferred workflow:
1. Build a command-line proof of concept first.
2. Test it on one known song using isolated vocal plus clean lyrics.
3. Improve section-based alignment.
4. Build the local editor.
5. Add ripple, anchor, and section rescale tools.
6. Export final JSON.
7. Only later plan quiz app integration.

If I upload files, treat uploaded files as the source of truth for that turn.

Current task:
[PASTE CURRENT TASK HERE]

What I tried:
[PASTE WHAT YOU TRIED HERE]

Error or problem:
[PASTE ERROR HERE]
```
