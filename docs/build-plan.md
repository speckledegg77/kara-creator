# Build Plan

This turns the roadmap into practical coding steps.

## Milestone 1: Empty project with docs

Files:

- `README.md`
- `docs/*`
- `.gitignore`

Checks:

```powershell
git status
```

Commit:

```powershell
git add -A
git commit -m "Add karaoke authoring project docs"
git push origin main
```

## Milestone 2: Backend skeleton

Goal:

Create a Python backend that can start locally.

Expected folders:

```text
backend
  app
    main.py
    api
    services
    models
    tools
```

Checks:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install "fastapi[standard]"
fastapi dev app\main.py
```

Expected result:

A local FastAPI server starts.

## Milestone 3: Audio preparation script

Goal:

Take an uploaded or local MP3 and create a standard WAV working file.

Expected behaviour:

```text
source/vocals.mp3 -> working/vocals.prepared.wav
```

Checks:

- prepared file exists
- duration is logged
- errors are readable

## Milestone 4: Lyric normaliser

Goal:

Take `lyrics.txt` and create phrase objects.

Expected output:

```text
working/phrases.raw.json
```

Checks:

- phrase order is correct
- blank lines become possible section hints
- original display text is preserved

## Milestone 5: Draft generator

Goal:

Create the first section-based JSON draft.

Expected output:

```text
working/karaoke.draft.json
```

Checks:

- JSON validates
- sections exist
- phrases have start and end times
- no impossible timings

## Milestone 6: Frontend skeleton

Goal:

Create a local React app that opens in the browser.

Expected folders:

```text
frontend
  src
```

Checks:

```powershell
cd frontend
npm install
npm run dev
```

Expected result:

A local page opens.

## Milestone 7: Editor MVP

Goal:

Load audio and JSON, show active lyrics, and export edits.

Required features:

- audio player
- active phrase highlight
- phrase list
- click phrase to jump
- start/end nudge
- ripple edit
- JSON export

## Milestone 8: Section editing

Goal:

Fix drift quickly.

Required features:

- section list
- shift section
- rescale section
- anchor section start
- anchor section end

## Milestone 9: Confidence-led review

Goal:

Make the editor tell the user what to check first.

Required features:

- confidence badges
- filter low confidence
- mark reviewed
- review progress count

## Stop/go point

After Milestone 9, decide whether the workflow is good enough.

Continue only if a clean isolated vocal can become a usable draft with light correction.
